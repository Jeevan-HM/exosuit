"""Physical-state/contract checks for the hardware-free pneumatic surrogate."""

import math
import unittest

from human.pneumatic import BankParameters, PneumaticExosuitConfig, PneumaticExosuit


def instant_config(**kwargs):
    parameters = dict(rise_tau_s=0, exhaust_tau_s=0)
    return PneumaticExosuitConfig(extension=BankParameters(**parameters),
                                 flexion=BankParameters(**parameters), **kwargs)


class PneumaticTests(unittest.TestCase):
    def test_legacy_both_bursts_route_to_one_extension_bank(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.heel_strike(0)
        device.set_timings([.1, .2, .7, .2])
        device.advance(.11, .01, knee_velocity_rad_s=1)
        self.assertEqual(device.command_psi, 25)
        self.assertEqual(device.actual_psi, 25)
        self.assertEqual(device.torque_nm, -10)
        self.assertEqual(device.telemetry()["flexion_pressure_psi"], 0)
        device.advance(.71, .01, knee_velocity_rad_s=1)
        self.assertEqual(device.command_psi, 20)
        self.assertEqual(device.torque_nm, -8)

    def test_legacy_routing_can_select_flexion_without_two_channel_inference(self):
        device = PneumaticExosuit(instant_config(legacy_bank="flexion"))
        device.enabled = True
        device.heel_strike(0)
        self.assertEqual(device.advance(.2, .01), 10)
        self.assertEqual(device.telemetry()["extension_pressure_psi"], 0)

    def test_no_pressure_before_heelstrike(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        self.assertEqual(device.advance(.2, .01), 0)
        self.assertEqual(device.actual_psi, 0)

    def test_independent_bank_torques_oppose_and_use_distinct_pressure_states(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.set_manual_pressures(extension_psi=20, flexion_psi=10)
        self.assertAlmostEqual(device.advance(0, .01), -4)
        telemetry = device.telemetry()
        self.assertEqual(telemetry["extension_pressure_psi"], 20)
        self.assertEqual(telemetry["flexion_pressure_psi"], 10)
        self.assertEqual(telemetry["extension_torque_nm"], -8)
        self.assertEqual(telemetry["flexion_torque_nm"], 4)

    def test_equal_banks_cancel_torque_but_preserve_pressure(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.set_manual_pressures(20, 20)
        self.assertEqual(device.advance(0, .01, knee_velocity_rad_s=2), 0)
        self.assertEqual(device.power_w, 0)
        self.assertEqual(device.telemetry()["extension_pressure_psi"], 20)
        self.assertEqual(device.telemetry()["flexion_pressure_psi"], 20)

    def test_first_order_rise_and_exhaust_match_analytic_solution(self):
        device = PneumaticExosuit()
        device.enabled = True
        device.set_manual_pressures(10, 0)
        device.advance(0, .08)
        expected = 10 * (1 - math.exp(-1))
        self.assertAlmostEqual(device.actual_psi, expected, places=11)
        device.set_manual_pressures(0, 0)
        device.advance(.08, .12)
        self.assertAlmostEqual(device.actual_psi, expected * math.exp(-1), places=11)
        self.assertGreater(device.actual_psi, 0)

    def test_large_outer_step_keeps_internal_command_updates_and_both_bursts(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.heel_strike(0)
        # Boundaries deliberately fall between 100 Hz samples.
        device.set_timings([.105, .2, .705, .2])
        device.advance(0, 1, knee_velocity_rad_s=1)
        self.assertEqual(device.command_psi, 0)
        self.assertEqual(device.actual_psi, 0)
        self.assertAlmostEqual(device.net_work_j, -(.4 * 25 * .2 + .4 * 20 * .2))

    def test_disable_vents_with_exhaust_lag_instead_of_erasing_pressure(self):
        device = PneumaticExosuit()
        device.enabled = True
        device.set_manual_pressures(20, 0)
        device.advance(0, .08)
        before = device.actual_psi
        device.enabled = False
        device.advance(.08, .01)
        self.assertEqual(device.command_psi, 0)
        self.assertGreater(device.actual_psi, 0)
        self.assertLess(device.actual_psi, before)

    def test_pressure_caps_and_telemetry_show_request_separately(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.set_manual_pressures(100, 4)
        device.advance(0, .01)
        telemetry = device.telemetry()
        self.assertEqual(telemetry["extension_requested_psi"], 100)
        self.assertEqual(telemetry["extension_command_psi"], 30)
        self.assertEqual(telemetry["extension_pressure_psi"], 30)
        self.assertTrue(telemetry["extension_pressure_saturated"])
        self.assertFalse(telemetry["flexion_pressure_saturated"])

    def test_total_torque_cap_preserves_component_sum(self):
        device = PneumaticExosuit(instant_config(maximum_net_torque_nm=3,
                              passive_damping_nm_s_per_rad=.5))
        device.enabled = True
        device.set_manual_pressures(20, 0)
        self.assertEqual(device.advance(0, .01, knee_velocity_rad_s=2), -3)
        telemetry = device.telemetry()
        self.assertTrue(telemetry["torque_saturated"])
        self.assertAlmostEqual(telemetry["active_torque_nm"] + telemetry["passive_torque_nm"], -3)
        self.assertAlmostEqual(telemetry["extension_torque_nm"] + telemetry["flexion_torque_nm"],
                               telemetry["active_torque_nm"])
        self.assertLessEqual(telemetry["passive_joint_power_w"], 0)

    def test_work_uses_actual_velocity_and_preserves_sign_and_energy_partition(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.set_manual_pressures(10, 0)
        device.advance(0, .1, knee_velocity_rad_s=-2)
        self.assertEqual(device.power_w, 8)
        self.assertAlmostEqual(device.net_work_j, .8)
        self.assertAlmostEqual(device.positive_work_j, .8)
        device.advance(.1, .1, knee_velocity_rad_s=1)
        self.assertEqual(device.power_w, -4)
        self.assertAlmostEqual(device.negative_work_j, .4)
        self.assertAlmostEqual(device.net_work_j, .4)
        self.assertAlmostEqual(device.positive_work_j - device.negative_work_j, device.net_work_j)

    def test_static_knee_zero_mechanical_work_despite_pressure(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.set_manual_pressures(20, 0)
        device.advance(0, .1, knee_velocity_rad_s=0)
        self.assertNotEqual(device.torque_nm, 0)
        self.assertEqual(device.net_work_j, 0)
        self.assertEqual(device.power_w, 0)

    def test_passive_damping_dissipates_energy(self):
        device = PneumaticExosuit(instant_config(passive_damping_nm_s_per_rad=.2))
        device.advance(0, .1, knee_velocity_rad_s=2)
        self.assertAlmostEqual(device.torque_nm, -.4)
        self.assertAlmostEqual(device.power_w, -.8)
        self.assertAlmostEqual(device.passive_dissipated_energy_j, .08)
        self.assertAlmostEqual(device.net_work_j, -.08)

    def test_calibration_curve_is_interpolated_and_never_extrapolated(self):
        bank = BankParameters(max_pressure_psi=20, rise_tau_s=0, exhaust_tau_s=0,
                              torque_curve_psi_nm=((0, 0), (10, 2), (20, 6)))
        device = PneumaticExosuit(PneumaticExosuitConfig(extension=bank))
        device.enabled = True
        device.set_manual_pressures(15, 0)
        self.assertEqual(device.advance(0, .01), -4)
        device.set_manual_pressures(25, 0)
        self.assertEqual(device.advance(.01, .01), -6)
        telemetry = device.telemetry()
        self.assertEqual(telemetry["extension_requested_psi"], 25)
        self.assertEqual(telemetry["extension_pressure_psi"], 20)
        self.assertTrue(telemetry["extension_pressure_saturated"])
        with self.assertRaisesRegex(ValueError, "extrapolation"):
            BankParameters(max_pressure_psi=25, torque_curve_psi_nm=((0, 0), (20, 6))).validate()

    def test_reset_clears_pressure_work_and_mode(self):
        device = PneumaticExosuit(instant_config())
        device.enabled = True
        device.set_manual_pressures(20, 0)
        device.advance(0, .1, knee_velocity_rad_s=1)
        device.reset()
        self.assertEqual(device.mode, "legacy")
        self.assertEqual(device.actual_psi, 0)
        self.assertEqual(device.net_work_j, 0)
        self.assertEqual(device.torque_nm, 0)

    def test_parameter_dicts_and_validation(self):
        device = PneumaticExosuit({"extension": {"rise_tau_s": .1}})
        self.assertEqual(device.config.extension.rise_tau_s, .1)
        for invalid in (dict(rise_tau_s=-1), dict(gain_nm_per_psi=math.inf),
                        dict(torque_curve_psi_nm=((0, 0), (0, 1)))):
            with self.assertRaises(ValueError):
                BankParameters(**invalid).validate()
        for pressures in ((-1, 0), (0, math.nan)):
            with self.assertRaises(ValueError):
                device.set_manual_pressures(*pressures)
        with self.assertRaises(ValueError):
            device.set_timings([.1, .8, .7, .1])
        with self.assertRaises(ValueError):
            device.advance(0, .01, knee_velocity_rad_s=math.nan)
        device.advance(0, .01)
        with self.assertRaises(ValueError):
            device.advance(0, .01)


if __name__ == "__main__":
    unittest.main()
