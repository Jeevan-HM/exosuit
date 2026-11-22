"""Timing and physical-state contract tests for the OpenSim demo input."""

import csv
import math
from pathlib import Path
import tempfile
import unittest

from opensim_exosuit.profile import FIELDS, build_profile, export_csv


def configuration(**assistance):
    return {
        "assistance": assistance,
        "exosuit": {"pneumatics": {
            "max_pressure_psi": 30.0,
            "rise_time_constant_s": 0.08,
            "exhaust_time_constant_s": 0.12,
        }},
        "schedule": {"stride_duration_s": 1.2, "timings_s": [0.12, 0.20, 0.70, 0.15]},
    }


def row_at(rows, time_s):
    return next(row for row in rows if math.isclose(row["time_s"], time_s, abs_tol=1e-10))


class ProfileTests(unittest.TestCase):
    def test_first_row_is_initial_state_and_pressure_is_lagged(self):
        rows = build_profile(configuration(), duration_s=0.16)
        self.assertEqual(rows[0], dict.fromkeys(FIELDS, 0.0))
        self.assertEqual(row_at(rows, .13)["extension_pressure_psi"], 0)
        sample = row_at(rows, .14)
        expected = 25 * (1 - math.exp(-.01 / .08))
        self.assertAlmostEqual(sample["extension_pressure_psi"], expected, places=10)
        self.assertAlmostEqual(sample["torque_flexion_positive_nm"], -.4 * expected, places=10)
        self.assertLess(sample["extension_pressure_psi"], sample["extension_command_psi"])

    def test_both_bursts_use_one_extension_bank_and_legacy_timing(self):
        rows = build_profile(configuration(), duration_s=.95)
        self.assertEqual(row_at(rows, .12)["extension_command_psi"], 0)
        self.assertEqual(row_at(rows, .14)["extension_command_psi"], 25)
        self.assertEqual(row_at(rows, .72)["extension_command_psi"], 20)
        for row in rows:
            self.assertEqual(row["flexion_command_psi"], 0)
            self.assertEqual(row["flexion_pressure_psi"], 0)
            self.assertLessEqual(row["torque_flexion_positive_nm"], 0)

    def test_flexion_direction_routes_both_bursts_to_selected_bank(self):
        rows = build_profile(configuration(direction="flexion"), duration_s=.8)
        for row in rows:
            self.assertEqual(row["extension_pressure_psi"], 0)
            self.assertGreaterEqual(row["torque_flexion_positive_nm"], 0)
        self.assertEqual(row_at(rows, .72)["flexion_command_psi"], 20)

    def test_release_vents_with_residual_pressure_and_torque(self):
        rows = build_profile(configuration(), duration_s=1.1)
        release = row_at(rows, .9)
        later = row_at(rows, 1.0)
        self.assertEqual(release["extension_command_psi"], 0)
        self.assertGreater(release["extension_pressure_psi"], later["extension_pressure_psi"])
        self.assertGreater(later["extension_pressure_psi"], 0)
        self.assertLess(later["torque_flexion_positive_nm"], 0)
        self.assertAlmostEqual(later["extension_pressure_psi"],
                               release["extension_pressure_psi"] * math.exp(-.1 / .12), places=9)

    def test_exact_end_and_heelstrikes_between_outer_samples(self):
        config = configuration()
        config["schedule"] = {"stride_duration_s": .7, "timings_s": [.05, .1, .3, .1]}
        rows = build_profile(config, duration_s=1.61, dt_s=.5)
        self.assertEqual([row["time_s"] for row in rows], [0, .5, .7, 1., 1.4, 1.5, 1.61])
        fine = build_profile(config, duration_s=1.61, dt_s=.01)
        for row in rows:
            self.assertAlmostEqual(row["extension_pressure_psi"],
                                   row_at(fine, row["time_s"])["extension_pressure_psi"], places=8)
        # Pressure is not erased at the stride reset; the next pulse repeats.
        self.assertGreater(row_at(rows, .7)["extension_pressure_psi"], 0)
        self.assertGreater(row_at(fine, .9)["extension_pressure_psi"],
                           row_at(fine, .7)["extension_pressure_psi"])

    def test_pressure_and_torque_caps_and_disabled_profile(self):
        config = configuration(stance_psi=100, maximum_torque_nm=3)
        rows = build_profile(config, duration_s=.3)
        self.assertEqual(row_at(rows, .3)["extension_command_psi"], 30)
        self.assertEqual(row_at(rows, .3)["torque_flexion_positive_nm"], -3)
        config["device_enabled"] = False
        self.assertTrue(all(row["extension_pressure_psi"] == 0 for row in build_profile(config)))

    def test_finite_positive_duration_and_step_are_required(self):
        for value in (0, -1, math.inf, math.nan, "bad", None, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_profile({}, duration_s=value)
                with self.assertRaises(ValueError):
                    build_profile({}, dt_s=value)

    def test_rejects_malformed_parameters_and_schedule(self):
        invalids = [
            {"assistance": None},
            {"exosuit": {"pneumatics": []}},
            {"schedule": None},
            {"assistance": {"stance_psi": -1}},
            {"assistance": {"torque_gain_nm_per_psi": math.inf}},
            {"assistance": {"maximum_torque_nm": math.nan}},
            {"assistance": {"command_rate_hz": 0}},
            {"assistance": {"direction": "both"}},
            {"exosuit": {"pneumatics": {"rise_time_constant_s": -1}}},
            {"exosuit": {"pneumatics": {"max_pressure_psi": math.inf}}},
            {"device_enabled": "yes"},
            {"schedule": {"stride_duration_s": 0}},
            {"schedule": {"timings_s": [0, 1, .5, .2]}},
            {"schedule": {"timings_s": [0, .2, 1, .3]}},
            {"schedule": {"timings_s": [0, .2, .7]}},
            {"schedule": {"timings_s": "1234"}},
            {"schedule": {"timings_s": [0, .2, math.nan, .1]}},
        ]
        for config in invalids:
            with self.subTest(config=config), self.assertRaises(ValueError):
                build_profile(config)

    def test_csv_fields_and_exact_final_time(self):
        rows = build_profile({}, duration_s=.035, dt_s=.01)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "profile.csv"
            export_csv(path, rows)
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                restored = list(reader)
                self.assertEqual(tuple(reader.fieldnames), FIELDS)
            self.assertEqual(len(restored), len(rows))
            self.assertEqual(float(restored[-1]["time_s"]), .035)


if __name__ == "__main__":
    unittest.main()
