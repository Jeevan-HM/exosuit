"""Actual OpenSim dynamics with finite feedback torques and virtual support.

All 23 human coordinates are unlocked and unprescribed. A sampled proportional
derivative controller applies bounded coordinate torques/forces; an explicit
virtual pelvis harness supplies support under normal gravity. The tutorial
motion is a controller target only. Reported angles, body poses and muscle-path
locations come from the integrated native State, never from motion playback.

This first prototype disables all 92 muscle forces and has no foot-ground
contact. It is supported torque-controlled motion, not unassisted walking,
human motor control, an exosuit response, or a rehabilitation prediction.
"""

import argparse
import csv
import json
import math
from pathlib import Path
import time

import numpy as np
import opensim as osim

from .builder import write_model
from .live_data import _quaternion
from .walking import DEFAULT_OUTPUT
from .walking_animation import _read_motion


DEFAULT_CONFIG = {
    "control_dt_s": .02,
    "integrator_accuracy": 1e-4,
    "integrator_max_step_s": .005,
    "knee_kp_nm_per_rad": 120.,
    "knee_kd_nm_s_per_rad": 6.,
    "knee_torque_limit_nm": 120.,
    "knee_disturbance_nm": 0.,
    "knee_disturbance_side": "r",
}


def _finite(value, name, *, minimum=None, maximum=None):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return result


class _Reference:
    """Periodic Fourier targets; these values are never returned as actual q."""

    def __init__(self, model, path):
        times, columns = _read_motion(model, path)
        if len(times) != 51 or not np.allclose(times, np.arange(51) / 50, atol=1e-10):
            raise ValueError("Expected the bundled one-second, 51-sample controller reference")
        self.coefficients = {coordinate.getName(): np.fft.rfft(values[:-1]) / 50
                             for coordinate, values in columns}
        self.defaults = {coordinate.getName(): coordinate.getDefaultValue()
                         for coordinate in model.getCoordinateSet()}

    def evaluate(self, name, time_s):
        coefficients = self.coefficients.get(name)
        if coefficients is None:
            return self.defaults[name], 0.0
        phase = time_s % 1.0
        value, velocity = coefficients[0].real, 0.0
        for harmonic, coefficient in enumerate(coefficients[1:], 1):
            factor = 1 if harmonic == 25 else 2
            omega = 2 * np.pi * harmonic
            sine, cosine = np.sin(omega * phase), np.cos(omega * phase)
            value += factor * (coefficient.real * cosine - coefficient.imag * sine)
            velocity -= factor * omega * (coefficient.real * sine + coefficient.imag * cosine)
        return float(value), float(velocity)


def _gains(name, config):
    """Explicit assumed support/tracking gains and finite generalized-force caps."""
    if name in ("pelvis_tx", "pelvis_tz"):
        return 2000., 200., 2000., 5.
    if name == "pelvis_ty":
        return 4000., 400., 3000., 5.
    if name.startswith("pelvis_"):
        return 1000., 80., 400., 1.
    if name.startswith("lumbar_"):
        return 700., 45., 250., 1.
    if name.startswith("hip_flexion_"):
        return 200., 15., 150., .3
    if name.startswith("hip_adduction_"):
        return 120., 10., 120., .3
    if name.startswith("hip_rotation_"):
        return 80., 6., 80., .3
    if name.startswith("knee_angle_"):
        return (config["knee_kp_nm_per_rad"], config["knee_kd_nm_s_per_rad"],
                config["knee_torque_limit_nm"], .3)
    if name.startswith("ankle_angle_"):
        return 60., 2., 60., .3
    if name.startswith("subtalar_angle_"):
        return 5., .1, 8., .2
    if name.startswith("mtp_angle_"):
        return 2., .03, 5., .1
    raise ValueError(f"No explicit controller gains defined for {name}")


class PhysicsSimulation:
    """Stateful native solver; step() advances physics before returning a frame.

    ``knee_disturbance_nm`` is a native-coordinate torque (positive extension)
    on the selected side, added to the bounded tracking controller. Both
    combined torque and the disturbance are finite and capped. Public ``model``
    and ``state`` expose the native objects for research diagnostics.
    """

    def __init__(self, directory=DEFAULT_OUTPUT, config=None):
        self.directory = Path(directory).resolve()
        self.config = dict(DEFAULT_CONFIG)
        if config is not None:
            if not isinstance(config, dict) or set(config) - set(DEFAULT_CONFIG):
                raise ValueError("Unsupported physics configuration")
            self.config.update(config)
        self._validate_config()
        osim.Logger.removeFileSink()
        osim.Logger.setLevelString("Warn")
        osim.ModelVisualizer.addDirToGeometrySearchPaths(str(self.directory / "Geometry"))
        self.model = osim.Model(str(self.directory / "human_walking.osim"))
        self.reference = _Reference(self.model, self.directory / "normal_walking.mot")
        self.model.setName("Human_Physics_Supported_Torque_Control")
        self.model.setDescription(
            "ACTUAL OPENSIM FORWARD DYNAMICS: all23 coordinates unlocked/unprescribed; "
            "bounded external PD tracking torques/forces, virtual pelvis support under normal gravity; "
            "all92 anatomical muscle forces disabled. No foot-ground contact. "
            "normal_walking.mot is a controller target only. Requires the Python feedback solver; "
            "this model alone does not contain the external feedback policy. "
            "Not unassisted walking, human motor control, an exosuit response or rehabilitation evidence.")
        self.coordinates = list(self.model.updCoordinateSet())
        self.actuators = {}
        for coordinate in self.coordinates:
            name = coordinate.getName()
            coordinate.setDefaultIsPrescribed(False)
            coordinate.setDefaultLocked(False)
            coordinate.setDefaultClamped(False)
            value, velocity = self.reference.evaluate(name, 0)
            coordinate.setDefaultValue(value)
            coordinate.setDefaultSpeedValue(velocity)
            actuator = osim.CoordinateActuator(name)
            actuator.setName("virtual_support_" + name if name.startswith("pelvis_") else "tracking_" + name)
            actuator.setOptimalForce(1.)
            cap = _gains(name, self.config)[2]
            actuator.setMinControl(-cap)
            actuator.setMaxControl(cap)
            self.model.addForce(actuator)
            damping = osim.SpringGeneralizedForce(name)
            damping.setName("native_passive_damping_" + name)
            damping.set_stiffness(0.)
            damping.set_rest_length(0.)
            # Continuous native velocity damping avoids an unstable sampled
            # derivative feedback term on the small distal joint inertias.
            gains = _gains(name, self.config)
            damping.set_viscosity(gains[1] + gains[3])
            self.model.addForce(damping)
        for muscle in self.model.updMuscles():
            muscle.set_appliesForce(False)
        self.model.finalizeConnections()
        self.model_path = write_model(self.model, self.directory / "human_physics.osim")
        # Execute the serialized model so the delivered artifact is also checked.
        self.model = osim.Model(str(self.model_path))
        self.coordinates = list(self.model.updCoordinateSet())
        for coordinate in self.coordinates:
            name = coordinate.getName()
            actuator_name = "virtual_support_" + name if name.startswith("pelvis_") else "tracking_" + name
            self.actuators[name] = osim.CoordinateActuator.safeDownCast(self.model.updForceSet().get(actuator_name))
        self.frames, self.frame_names = [], []
        for component in self.model.getComponentsList():
            mesh = osim.Mesh.safeDownCast(component)
            if mesh is None or mesh.getFrame().getName() == "ground":
                continue
            frame = mesh.getFrame()
            name = frame.getAbsolutePathString()
            if name not in self.frame_names:
                self.frame_names.append(name)
                self.frames.append(frame)
        self.reset()

    def _validate_config(self):
        limits = {"control_dt_s": (.001, .02), "integrator_accuracy": (1e-8, 1e-3),
                  "integrator_max_step_s": (.0001, .01), "knee_kp_nm_per_rad": (0, 300),
                  "knee_kd_nm_s_per_rad": (0, 20), "knee_torque_limit_nm": (1, 200),
                  "knee_disturbance_nm": (-30, 30)}
        for key, (minimum, maximum) in limits.items():
            self.config[key] = _finite(self.config[key], key, minimum=minimum, maximum=maximum)
        if self.config["knee_disturbance_side"] not in ("r", "l"):
            raise ValueError("knee_disturbance_side must be r or l")

    def reset(self):
        self.state = self.model.initSystem()
        self.mass_kg = self.model.getTotalMass(self.state)
        self.weight_n = -self.mass_kg * self.model.getGravity().get(1)
        self.sequence = 0
        self.control_updates = 0
        self.solver_wall_time_s = 0.0
        self.last_step_dt_s = 0.0
        self.applied = {}
        self.saturated = {}
        self._apply_feedback()
        self.model.realizeVelocity(self.state)
        for coordinate in self.coordinates:
            if coordinate.isPrescribed(self.state) or coordinate.getLocked(self.state):
                raise ValueError("The physics prototype cannot contain prescribed or locked coordinates")
        if len(self.coordinates) != 23 or self.model.getMuscles().getSize() != 92:
            raise ValueError("The full native human anatomy must be retained")
        return self.frame()

    def set_parameter(self, name, value):
        if name not in ("knee_kp_nm_per_rad", "knee_torque_limit_nm", "knee_disturbance_nm",
                        "knee_disturbance_side"):
            raise ValueError("Only knee proportional gain, torque limit, disturbance and disturbance side can change live; damping requires rebuilding the model")
        previous = dict(self.config)
        self.config[name] = value
        try:
            self._validate_config()
        except Exception:
            self.config = previous
            raise
        return dict(self.config)

    def _apply_feedback(self):
        self.model.realizeVelocity(self.state)
        now = self.state.getTime()
        for coordinate in self.coordinates:
            name = coordinate.getName()
            target, target_velocity = self.reference.evaluate(name, now)
            kp, kd, cap, _ = _gains(name, self.config)
            # The -kd*u term is supplied continuously by the native damper;
            # target position/velocity and position error are sampled here.
            requested = kp * (target - coordinate.getValue(self.state)) + kd * target_velocity
            if name == "pelvis_ty":
                requested += self.weight_n
            if name == "knee_angle_" + self.config["knee_disturbance_side"]:
                requested += self.config["knee_disturbance_nm"]
            applied = float(np.clip(requested, -cap, cap))
            actuator = self.actuators[name]
            actuator.overrideActuation(self.state, True)
            actuator.setOverrideActuation(self.state, applied)
            self.applied[name] = applied
            self.saturated[name] = abs(requested) > cap
        self.control_updates += 1

    def step(self, dt_s=.02):
        dt = _finite(dt_s, "dt_s", minimum=.0001, maximum=.2)
        end = self.state.getTime() + dt
        started = time.perf_counter()
        while self.state.getTime() < end - 1e-12:
            self._apply_feedback()
            target = min(end, self.state.getTime() + self.config["control_dt_s"])
            manager = osim.Manager(self.model)
            manager.setIntegratorAccuracy(self.config["integrator_accuracy"])
            manager.setIntegratorMaximumStepSize(self.config["integrator_max_step_s"])
            manager.setIntegratorInternalStepLimit(100000)
            manager.initialize(self.state)
            # Manager owns its advanced State. Copy it before the next input
            # mutation, then initialize a NEW Manager with the updated State.
            self.state = osim.State(manager.integrate(target))
            if not np.isclose(self.state.getTime(), target, atol=1e-9, rtol=0):
                raise RuntimeError("Native OpenSim solver did not reach the requested time")
        self.solver_wall_time_s += time.perf_counter() - started
        self.last_step_dt_s = dt
        self.sequence += 1
        return self.frame()

    def snapshot(self):
        """Return the current actual State without advancing simulation time."""
        return self.frame()

    def frame(self):
        self.model.realizePosition(self.state)
        poses = []
        for frame in self.frames:
            transform = frame.getTransformInGround(self.state)
            matrix = np.array([[transform.R().get(i, j) for j in range(3)] for i in range(3)])
            quaternion = _quaternion(matrix)
            poses.extend([transform.p().get(i) for i in range(3)])
            poses.extend(quaternion.tolist())
        muscles = []
        for muscle in self.model.getMuscles():
            path = muscle.getGeometryPath().getCurrentPath(self.state)
            points = []
            for index in range(path.getSize()):
                point = path.get(index).getLocationInGround(self.state)
                points.append([point.get(i) for i in range(3)])
            for start, end in zip(points[:-1], points[1:]):
                muscles.extend(start)
                muscles.extend(end)
        knees = {side: self.model.getCoordinateSet().get("knee_angle_" + side).getValue(self.state)
                 for side in ("r", "l")}
        result = {"time_s": self.state.getTime(), "sequence": self.sequence,
                  "knee_angle_r": knees["r"], "knee_angle_l": knees["l"],
                  "knee_flexion_deg": {side: -math.degrees(value) for side, value in knees.items()},
                  "reference_knee_flexion_deg": {side: -math.degrees(self.reference.evaluate("knee_angle_" + side, self.state.getTime())[0]) for side in ("r", "l")},
                  "pelvis_height_m": self.model.getCoordinateSet().get("pelvis_ty").getValue(self.state),
                  "poses": poses, "muscles": muscles,
                  "applied_knee_torque_nm": {side: self.applied["knee_angle_" + side] for side in ("r", "l")},
                  "knee_torque_saturated": {side: self.saturated["knee_angle_" + side] for side in ("r", "l")},
                  "status": "Native OpenSim dynamics · virtual pelvis support · muscle forces disabled · no foot contact",
                  "control_updates": self.control_updates, "solver_wall_time_s": self.solver_wall_time_s,
                  "last_step_dt_s": self.last_step_dt_s,
                  "physics": {"actual_integrated_state": True, "native_solver": "OpenSim Manager",
                              "coordinates_prescribed": False, "coordinates_locked": False,
                              "virtual_pelvis_support": True, "muscle_forces_enabled": False,
                              "foot_ground_contact": False, "reference_role": "controller target only"},
                  "units": {"time": "s", "knee_angle": "rad, native extension positive",
                            "knee_flexion": "deg, flexion positive", "position": "m, native ground Y-up",
                            "quaternion": "xyzw", "knee_control_torque": "Nm, native extension positive"}}
        if (not np.all(np.isfinite(poses)) or not np.all(np.isfinite(muscles))
                or not all(math.isfinite(value) for value in knees.values())
                or not math.isfinite(result["pelvis_height_m"])):
            raise RuntimeError("Non-finite native physics state")
        return result


def validate_physics(directory=DEFAULT_OUTPUT, duration_s=30.):
    """Integrate actual dynamics and verify a changed torque changes the output."""
    duration = _finite(duration_s, "duration_s", minimum=.1, maximum=60)
    simulation = PhysicsSimulation(directory)
    rows = []
    for _ in range(math.ceil(duration / .02)):
        sample = simulation.step(min(.02, duration - simulation.state.getTime()))
        rows.append({"time_s": sample["time_s"], "pelvis_height_m": sample["pelvis_height_m"],
                     "right_knee_flexion_deg": sample["knee_flexion_deg"]["r"],
                     "left_knee_flexion_deg": sample["knee_flexion_deg"]["l"],
                     "reference_right_knee_flexion_deg": sample["reference_knee_flexion_deg"]["r"],
                     "right_knee_torque_nm": sample["applied_knee_torque_nm"]["r"]})
    baseline = PhysicsSimulation(directory)
    perturbed = PhysicsSimulation(directory, {"knee_disturbance_nm": 5.})
    difference = 0.
    for _ in range(50):
        first, second = baseline.step(), perturbed.step()
        difference = max(difference, abs(first["knee_angle_r"] - second["knee_angle_r"]))
    if difference < 1e-4:
        raise ValueError("Knee output did not respond to changed native actuator torque")
    heights = [row["pelvis_height_m"] for row in rows]
    if min(heights) < .5 or max(heights) > 1.3:
        raise ValueError("Virtual support did not retain a bounded pelvis height")
    error = np.array([row["right_knee_flexion_deg"] - row["reference_right_knee_flexion_deg"] for row in rows])
    if np.max(abs(error)) < .01:
        raise ValueError("Actual integrated motion unexpectedly duplicates the controller reference")
    directory = Path(directory)
    with (directory / "physics_validation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    summary = {"scope": "Actual supported torque-driven OpenSim forward dynamics",
               "duration_s": simulation.state.getTime(), "output_samples": len(rows),
               "all_23_coordinates_unlocked_unprescribed": True,
               "muscle_forces": "disabled; all92 anatomical paths retained",
               "normal_gravity": True, "foot_ground_contact": False,
               "support": "Finite virtual pelvis position/velocity feedback forces and torques",
               "reference_use": "Controller target only; actual q/u integrated by native Manager",
               "pelvis_height_range_m": [min(heights), max(heights)],
               "right_knee_tracking_rmse_deg": float(np.sqrt(np.mean(error**2))),
               "five_nm_disturbance_maximum_knee_difference_deg": math.degrees(difference),
               "solver_wall_time_s": simulation.solver_wall_time_s,
               "parameters": simulation.config}
    (directory / "physics_validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--duration", type=float, default=30.)
    args = parser.parse_args()
    print(json.dumps(validate_physics(args.directory, args.duration), indent=2))


if __name__ == "__main__":
    main()
