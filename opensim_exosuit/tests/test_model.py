"""Native OpenSim checks for device mechanics and portable delivered models."""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import opensim as osim

from opensim_exosuit.builder import (
    ACTUATOR_NAME,
    DAMPER_NAME,
    build_model,
    build_project,
)
from opensim_exosuit.demo import diagnostic_model
from opensim_exosuit.settings import BASE_MODEL, load_settings


class NativeModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_settings()

    def test_full_models_preserve_anatomy_and_free_coordinates(self):
        """Adding the suit must not silently turn the human into a knee fixture."""
        source = osim.Model(str(BASE_MODEL))
        expected_coordinates = {
            coordinate.getName() for coordinate in source.getCoordinateSet()
        }
        expected_muscles = {muscle.getName() for muscle in source.getMuscles()}
        for variant in ("bare", "unpowered", "assisted"):
            with self.subTest(variant=variant):
                model = build_model(self.config, variant)
                state = model.initSystem()
                self.assertEqual(model.getCoordinateSet().getSize(), 23)
                self.assertEqual(model.getMuscles().getSize(), 92)
                self.assertEqual(
                    {coordinate.getName() for coordinate in model.getCoordinateSet()},
                    expected_coordinates,
                )
                self.assertEqual(
                    {muscle.getName() for muscle in model.getMuscles()},
                    expected_muscles,
                )
                self.assertTrue(all(
                    not coordinate.getDefaultLocked()
                    and not coordinate.getDefaultIsPrescribed()
                    for coordinate in model.getCoordinateSet()
                ))
                self.assertTrue(all(muscle.appliesForce(state)
                                    for muscle in model.getMuscles()))
                self.assertEqual(model.getControllerSet().getSize(), 0)

    def test_worn_variants_add_same_mass_and_physical_cuff_inertia(self):
        """Compare carried mass and native COM inertia, including the axis order."""
        masses = {}
        for variant in ("bare", "unpowered", "assisted"):
            model = build_model(self.config, variant)
            state = model.initSystem()
            masses[variant] = model.getTotalMass(state)
            if variant == "bare":
                continue
            # Known thin-shell assembly properties for the bundled assumptions;
            # native inertia is about each cuff COM and its long axis is local Y.
            expected = {
                "exosuit_l_thigh": (0.25, (0.0017114583333333333,
                                            0.00140625,
                                            0.0017114583333333333)),
                "exosuit_l_shank": (0.20, (0.0011666666666666668,
                                            0.00072,
                                            0.0011666666666666668)),
            }
            for name, (mass, moments) in expected.items():
                with self.subTest(variant=variant, body=name):
                    body = model.getBodySet().get(name)
                    self.assertAlmostEqual(body.getMass(), mass, places=12)
                    for axis, inertia in enumerate(moments):
                        self.assertAlmostEqual(
                            body.getInertia().getMoments().get(axis), inertia,
                            places=12,
                        )
                        self.assertAlmostEqual(
                            body.getInertia().getProducts().get(axis), 0,
                            places=12,
                        )
                        self.assertAlmostEqual(body.getMassCenter().get(axis), 0)
        self.assertAlmostEqual(masses["bare"], 75.1646, places=8)
        self.assertAlmostEqual(masses["unpowered"] - masses["bare"], .45,
                               places=10)
        self.assertAlmostEqual(masses["assisted"], masses["unpowered"],
                               places=10)

    def test_positive_native_torque_accelerates_knee_toward_extension(self):
        """Measure the actuator's causal effect at an identical physical state."""
        profile = [
            {"time_s": 0., "torque_flexion_positive_nm": 0.},
            {"time_s": 1., "torque_flexion_positive_nm": 0.},
        ]
        model = diagnostic_model(self.config, "assisted", profile)
        state = model.initSystem()
        model.equilibrateMuscles(state)
        knee = model.getCoordinateSet().get("knee_angle_l")
        actuator = osim.ScalarActuator.safeDownCast(
            model.getForceSet().get(ACTUATOR_NAME))
        actuator.overrideActuation(state, True)
        accelerations = {}
        for torque in (0., 4., -4., 0.):
            # The override setter invalidates the dynamics cache. Re-realizing
            # acceleration prevents an old zero-input result from passing.
            actuator.setOverrideActuation(state, torque)
            model.realizeAcceleration(state)
            self.assertAlmostEqual(actuator.getActuation(state), torque,
                                   places=12)
            accelerations[torque] = knee.getAccelerationValue(state)
            self.assertTrue(math.isfinite(accelerations[torque]))
        self.assertLess(knee.getValue(state), 0)  # Flexed initial posture.
        self.assertGreater(accelerations[4.] - accelerations[0.], 0)
        self.assertLess(accelerations[-4.] - accelerations[0.], 0)
        self.assertAlmostEqual(
            accelerations[4.] - accelerations[0.],
            accelerations[0.] - accelerations[-4.], places=9,
        )
        # Flexion-positive project telemetry reverses the native acceleration.
        self.assertLess(self.config["model"]["flexion_sign"]
                        * (accelerations[4.] - accelerations[0.]), 0)

    def test_native_suit_damper_dissipates_in_both_directions(self):
        model = build_model(self.config, "unpowered")
        state = model.initSystem()
        knee = model.getCoordinateSet().get("knee_angle_l")
        force = model.getForceSet().get(DAMPER_NAME)
        for speed in (-2., 0., 2.):
            with self.subTest(speed=speed):
                knee.setSpeedValue(state, speed)
                model.realizeDynamics(state)
                values = force.getRecordValues(state)
                self.assertEqual(values.getSize(), 1)
                torque = values.get(0)
                self.assertAlmostEqual(torque, -.03 * speed, places=12)
                if speed:
                    self.assertLess(torque * speed, 0)
                else:
                    self.assertEqual(torque, 0)

    def test_exported_model_loads_after_relocation_in_fresh_process(self):
        """No process-global geometry registration may hide a broken export."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = build_project(root / "build")
            relocated = root / "independent_location"
            relocated.mkdir()
            shutil.copytree(output / "Geometry", relocated / "Geometry")
            model_path = relocated / "knee_exosuit.osim"
            shutil.copy2(output / model_path.name, model_path)
            document = ET.parse(model_path)
            dependencies = {element.text for element in document.iter("mesh_file")}
            self.assertEqual(len(dependencies), 20)
            for reference in dependencies:
                with self.subTest(reference=reference):
                    self.assertFalse(Path(reference).is_absolute())
                    self.assertTrue(reference.startswith("Geometry/"))
                    target = (relocated / reference).resolve()
                    self.assertTrue(target.is_relative_to(relocated.resolve()))
                    self.assertTrue(target.is_file())
            self.assertNotIn(str(BASE_MODEL.parent), model_path.read_text())
            # This interpreter never imports our builder and never adds its
            # geometry search path; the working directory has no Geometry/.
            child_working_dir = root / "unrelated_working_directory"
            child_working_dir.mkdir()
            code = """
import json
import sys
import opensim as osim
model = osim.Model(sys.argv[1])
state = model.initSystem()
model.equilibrateMuscles(state)
model.realizeDynamics(state)
assert model.getCoordinateSet().getSize() == 23
assert model.getMuscles().getSize() == 92
assert abs(model.getTotalMass(state) - 75.6146) < 1e-8
assert model.getForceSet().get('exosuit_knee_moment').getConcreteClassName() == 'CoordinateActuator'
print('RELOCATED_MODEL_OK')
"""
            result = subprocess.run(
                [sys.executable, "-c", code, str(model_path)],
                cwd=child_working_dir, capture_output=True, text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RELOCATED_MODEL_OK", result.stdout)
            self.assertNotIn("couldn't find", (result.stdout + result.stderr).lower())

    def test_original_assets_match_pinned_source_manifest(self):
        manifest = json.loads((BASE_MODEL.parent / "source_manifest.json").read_text())
        self.assertEqual(manifest["commit"],
                         "d9b05d470b1a481c222372c85b75772faf8f7792")
        self.assertEqual(len(manifest["files"]), 21)
        for entry in manifest["files"]:
            with self.subTest(asset=entry["path"]):
                contents = (BASE_MODEL.parent / entry["path"]).read_bytes()
                self.assertEqual(len(contents), entry["bytes"])
                self.assertEqual(hashlib.sha256(contents).hexdigest(),
                                 entry["sha256"])
                blob = f"blob {len(contents)}\0".encode() + contents
                self.assertEqual(hashlib.sha1(blob).hexdigest(),
                                 entry["upstream_git_blob_sha1"])

    def test_rejects_settings_that_invert_side_or_define_invalid_mechanics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            invalid = []
            for key, value in (("side", "right"),
                               ("knee_coordinate", "knee_angle_r"),
                               ("flexion_sign", 1)):
                config = deepcopy(self.config)
                config["model"][key] = value
                invalid.append(config)
            for key, value in (("thigh_mass_kg", -1),
                               ("shank_cuff_radius_m", 0),
                               ("passive_knee_damping_nm_s_per_rad", -1),
                               ("thigh_center_distal_m", 1)):
                config = deepcopy(self.config)
                config["exosuit"]["mechanics"][key] = value
                invalid.append(config)
            for config in invalid:
                with self.subTest(config=config):
                    path.write_text(json.dumps(config))
                    with self.assertRaises(ValueError):
                        load_settings(path)


if __name__ == "__main__":
    unittest.main()
