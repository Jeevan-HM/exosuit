"""Regression checks for simulation input, reporting and native moment limits."""

from copy import deepcopy
import math
import tempfile
import unittest

import opensim as osim

from opensim_exosuit.builder import ACTUATOR_NAME, build_project, input_profile
from opensim_exosuit.control import set_knee_moment
from opensim_exosuit.demo import diagnostic_model, simulate
from opensim_exosuit.profile import build_profile
from opensim_exosuit.settings import load_settings


class DemoTests(unittest.TestCase):
    def test_sparse_reporting_preserves_applied_torque_and_motion(self):
        """A telemetry interval must not silently remove the pressure bursts."""
        config = load_settings()
        controls = input_profile(config)
        coarse = deepcopy(config)
        coarse["demo"]["sample_interval_s"] = 1.2
        self.assertEqual(input_profile(coarse), controls)
        sparse_samples = build_profile(coarse, 2.4, 1.2)
        dense_samples = build_profile(config, 2.4, .01)
        previous_level = osim.Logger.getLevelString()
        osim.Logger.setLevelString("Error")
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = build_project(directory)
                dense = simulate(config, "assisted", dense_samples, output, controls)
                sparse = simulate(coarse, "assisted", sparse_samples, output, controls)
        finally:
            osim.Logger.setLevelString(previous_level)
        self.assertLess(len(sparse), len(dense))
        self.assertAlmostEqual(sparse[-1]["knee_flexion_deg"],
                               dense[-1]["knee_flexion_deg"], places=3)
        self.assertGreater(max(abs(r["active_torque_flexion_positive_nm"])
                               for r in dense), 9.)

    def test_control_boundary_clamps_actual_native_actuation(self):
        config = load_settings()
        profile = [{"time_s": 0., "torque_flexion_positive_nm": 0.},
                   {"time_s": 1., "torque_flexion_positive_nm": 0.}]
        model = diagnostic_model(config, "assisted", profile)
        state = model.initSystem()
        actuator = osim.ScalarActuator.safeDownCast(model.getForceSet().get(ACTUATOR_NAME))
        for request, expected in ((100., 15.), (-100., -15.), (4., 4.), (0., 0.)):
            report = set_knee_moment(model, state, config, request)
            model.realizeDynamics(state)
            self.assertEqual(report["applied_flexion_positive_nm"], expected)
            self.assertAlmostEqual(actuator.getActuation(state), -expected)
            self.assertEqual(report["saturated"], abs(request) > 15.)
        for invalid in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                set_knee_moment(model, state, config, invalid)


if __name__ == "__main__":
    unittest.main()
