"""Forward-dynamics verification on a seated mechanical knee test fixture.

Only the assisted knee is free. Muscles are disabled in this diagnostic copy;
the released full models retain all 92 muscles and all 23 coordinates. A named
fixture spring stabilizes the isolated leg. This is not a gait simulation.
"""

import argparse
import csv
import json
import math
from pathlib import Path

import opensim as osim

from .builder import ACTUATOR_NAME, build_model, build_project, input_profile, write_model
from .profile import build_profile
from .settings import DEFAULT_CONFIG, DEFAULT_OUTPUT, load_settings

FIXTURE_STIFFNESS = 25.0
FIXTURE_DAMPING = 1.5


def diagnostic_model(config, variant, profile):
    model = build_model(config, variant)
    model.setName(f"seated_knee_fixture_{variant}")
    coordinate_name = config["model"]["knee_coordinate"]
    sign = config["model"]["flexion_sign"]
    initial = sign * math.radians(config["demo"]["initial_knee_flexion_deg"])
    for coordinate in model.updCoordinateSet():
        name = coordinate.getName()
        if name.startswith("hip_flexion_"):
            coordinate.setDefaultValue(math.radians(config["demo"]["hip_flexion_deg"]))
        elif name.startswith("knee_angle_"):
            coordinate.setDefaultValue(initial)
        coordinate.setDefaultLocked(name != coordinate_name)
        coordinate.setDefaultSpeedValue(0)
    for muscle in model.updMuscles():
        muscle.set_appliesForce(False)
    fixture = osim.SpringGeneralizedForce(coordinate_name)
    fixture.setName("test_fixture_return_spring")
    fixture.set_stiffness(FIXTURE_STIFFNESS)
    fixture.set_rest_length(initial)
    fixture.set_viscosity(FIXTURE_DAMPING)
    model.addForce(fixture)
    if variant == "assisted":
        controller = osim.PrescribedController()
        controller.setName("illustrative_pressure_profile_controller")
        actuator = osim.Actuator.safeDownCast(model.updForceSet().get(ACTUATOR_NAME))
        controller.addActuator(actuator)
        function = osim.PiecewiseLinearFunction()
        for row in profile:
            function.addPoint(row["time_s"], sign * row["torque_flexion_positive_nm"])
        controller.prescribeControlForActuator(ACTUATOR_NAME, function)
        model.addController(controller)
    model.setDescription(
        "Seated MECHANICAL TEST FIXTURE: all coordinates except one knee locked; "
        "muscle forces disabled; added 25 Nm/rad return spring and 1.5 Nms/rad "
        "fixture damping. Timed torque is an illustrative pneumatic surrogate. "
        "Not a walking, muscle-effort, patient-response or rehabilitation prediction.")
    model.finalizeConnections()
    return model


def write_storage(path, columns, samples, description):
    """Write an OpenSim-readable time-series table in SI units/radians."""
    with Path(path).open("w") as stream:
        stream.write(description + "\n")
        stream.write("version=1\n")
        stream.write(f"nRows={len(samples)}\nnColumns={len(columns)}\n")
        stream.write("inDegrees=no\nendheader\n")
        stream.write("\t".join(columns) + "\n")
        for sample in samples:
            stream.write("\t".join(f"{float(value):.12g}" for value in sample) + "\n")


def simulate(config, variant, profile, output_dir, control_profile=None):
    output_dir = Path(output_dir)
    model = diagnostic_model(config, variant, control_profile or profile)
    model_path = write_model(model, output_dir / f"seated_{variant}.osim")
    # Verify serialization, native component connections and relative geometry.
    model = osim.Model(str(model_path))
    state = model.initSystem()
    model.equilibrateMuscles(state)
    knee = model.getCoordinateSet().get(config["model"]["knee_coordinate"])
    sign = config["model"]["flexion_sign"]
    coordinates = list(model.getCoordinateSet())
    names = model.getStateVariableNames()
    state_names = [names.get(i) for i in range(names.getSize())]
    manager = osim.Manager(model)
    manager.setIntegratorAccuracy(1e-7)
    manager.setIntegratorMaximumStepSize(0.005)
    manager.initialize(state)
    telemetry, motion, states = [], [], []
    actuator = (osim.ScalarActuator.safeDownCast(model.getForceSet().get(ACTUATOR_NAME))
                if variant == "assisted" else None)
    active_work = 0.0
    previous = None
    for row in profile:
        time = row["time_s"]
        state = manager.integrate(time) if time > 0 else state
        model.realizeAcceleration(state)
        q, u = knee.getValue(state), knee.getSpeedValue(state)
        native_torque = actuator.getActuation(state) if actuator else 0.0
        power = native_torque * u
        if previous is not None:
            active_work += 0.5 * (previous[1] + power) * (time - previous[0])
        previous = (time, power)
        sample = {
            "time_s": time,
            "knee_flexion_deg": math.degrees(sign * q),
            "knee_flexion_velocity_rad_s": sign * u,
            "knee_native_coordinate_rad": q,
            "active_torque_flexion_positive_nm": sign * native_torque,
            "active_joint_power_w": power,
            "active_joint_work_j": active_work,
            "total_mass_kg": model.getTotalMass(state),
        }
        if not all(math.isfinite(value) for value in sample.values()):
            raise RuntimeError(f"Non-finite {variant} simulation at {time}")
        telemetry.append(sample)
        motion.append([time] + [c.getValue(state) for c in coordinates])
        values = model.getStateVariableValues(state)
        states.append([time] + [values.get(i) for i in range(values.size())])
    with (output_dir / f"seated_{variant}.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(telemetry[0]))
        writer.writeheader()
        writer.writerows(telemetry)
    write_storage(output_dir / f"seated_{variant}.mot",
                  ["time"] + [c.getName() for c in coordinates], motion,
                  "Actual seated mechanical-fixture forward dynamics; coordinates in radians")
    write_storage(output_dir / f"seated_{variant}_states.sto",
                  ["time"] + state_names, states,
                  "Actual OpenSim states from the seated mechanical test fixture")
    # Validate the delivered native table. Locked coordinates are discrete
    # modeling options; continuous states are saved explicitly in the .sto.
    table = osim.TimeSeriesTable(str(output_dir / f"seated_{variant}_states.sto"))
    if table.getNumRows() != len(profile) or table.getNumColumns() != len(state_names):
        raise RuntimeError("Delivered OpenSim state trajectory failed round-trip validation")
    return telemetry


def run_demo(output_dir=DEFAULT_OUTPUT, config_path=DEFAULT_CONFIG, render=True):
    output_dir = build_project(output_dir, config_path)
    config = load_settings(config_path)
    profile = build_profile(config, config["demo"]["duration_s"],
                            config["demo"]["sample_interval_s"])
    controls = input_profile(config)
    results = {variant: simulate(config, variant, profile, output_dir, controls)
               for variant in ("bare", "unpowered", "assisted")}
    summary = {
        "test": "seated mechanical fixture, not gait or rehabilitation efficacy",
        "duration_s": config["demo"]["duration_s"],
        "samples_per_condition": len(profile),
        "muscle_forces": "disabled in diagnostic copies only",
        "unlocked_coordinates": [config["model"]["knee_coordinate"]],
        "fixture_stiffness_nm_per_rad": FIXTURE_STIFFNESS,
        "fixture_damping_nm_s_per_rad": FIXTURE_DAMPING,
        "conditions": {},
    }
    for variant, rows in results.items():
        summary["conditions"][variant] = {
            "knee_flexion_range_deg": [min(x["knee_flexion_deg"] for x in rows),
                                       max(x["knee_flexion_deg"] for x in rows)],
            "peak_active_torque_nm": (max(abs(x["torque_flexion_positive_nm"]) for x in controls)
                                     if variant == "assisted" else 0.0),
            "active_joint_work_j": rows[-1]["active_joint_work_j"],
            "total_mass_kg": rows[0]["total_mass_kg"],
        }
    (output_dir / "validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    if render:
        from .preview import render_preview
        render_preview(output_dir, config, profile, results)
    return output_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    osim.Logger.setLevelString("Warn")
    print(f"Verified OpenSim model and diagnostic trajectories: {run_demo(args.output, args.config, not args.no_render)}")


if __name__ == "__main__":
    main()
