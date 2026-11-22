"""Build a native muscle-driven OpenSim model with carried knee-suit mechanics.

The .osim contains a commandable joint-moment surrogate. Pressure dynamics are
provided by profile.py, not misrepresented as native OpenSim pressure states.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import opensim as osim

from .settings import BASE_MODEL, DEFAULT_CONFIG, DEFAULT_OUTPUT, load_settings

ACTUATOR_NAME = "exosuit_knee_moment"
DAMPER_NAME = "exosuit_knee_damping"


def _attach_cuff(model, parent_name, label, mass, radius, length, distal):
    """Weld a thin-shell equivalent mass to a limb, with inertia about its COM."""
    if mass == 0:
        return
    parent = model.updBodySet().get(parent_name)
    transverse = mass * (radius ** 2 / 2 + length ** 2 / 12)
    longitudinal = mass * radius ** 2
    body = osim.Body(f"exosuit_{label}", mass, osim.Vec3(0),
                     osim.Inertia(transverse, longitudinal, transverse))
    cuff = osim.Cylinder(radius, 0.025)
    cuff.setColor(osim.Vec3(0.08, 0.32, 0.86))
    cuff.setOpacity(0.85)
    body.attachGeometry(cuff)
    pouch_frame = osim.PhysicalOffsetFrame(
        f"exosuit_{label}_pouch_frame", body,
        osim.Transform(osim.Vec3(radius, 0, 0)))
    body.addComponent(pouch_frame)
    pouch = osim.Ellipsoid(0.025, length / 2, 0.035)
    pouch.setColor(osim.Vec3(0.88, 0.16, 0.18))
    pouch.setFrame(pouch_frame)
    pouch_frame.attachGeometry(pouch)
    weld = osim.WeldJoint(f"exosuit_{label}_weld", parent,
                         osim.Vec3(0, -distal, 0), osim.Vec3(0),
                         body, osim.Vec3(0), osim.Vec3(0))
    model.addBody(body)
    model.addJoint(weld)


def build_model(config, variant="assisted"):
    """Return a full 23-coordinate, 92-muscle model, without prescribed gait.

    bare: inherited human only; unpowered: cuff mass and damping;
    assisted: same worn mechanics plus a signed CoordinateActuator (Nm).
    """
    if variant not in ("bare", "unpowered", "assisted"):
        raise ValueError("variant must be bare, unpowered or assisted")
    osim.ModelVisualizer.addDirToGeometrySearchPaths(str(BASE_MODEL.parent / "Geometry"))
    model = osim.Model(str(BASE_MODEL))
    model.setName(f"pneumatic_knee_exosuit_{variant}")
    model.setDescription(
        "Generic Gait2392 human with a reduced pneumatic knee-suit moment model. "
        "Uncalibrated research prototype; no patient-specific impairment, autonomous "
        "walking controller, cloth FEM or hardware interface. "
        "Positive knee coordinate is extension; project telemetry is flexion-positive.")
    side = config["model"]["side"]
    coordinate = config["model"]["knee_coordinate"]
    model.getCoordinateSet().get(coordinate)  # Fail before changing an incompatible model.
    if variant != "bare":
        mechanics = config["exosuit"]["mechanics"]
        for part, body_name in (("thigh", f"femur_{side}"), ("shank", f"tibia_{side}")):
            _attach_cuff(model, body_name, f"{side}_{part}",
                         mechanics[f"{part}_mass_kg"],
                         mechanics[f"{part}_cuff_radius_m"],
                         mechanics[f"{part}_assembly_length_m"],
                         mechanics[f"{part}_center_distal_m"])
        damper = osim.SpringGeneralizedForce(coordinate)
        damper.setName(DAMPER_NAME)
        damper.set_stiffness(0)
        damper.set_rest_length(0)
        damper.set_viscosity(mechanics["passive_knee_damping_nm_s_per_rad"])
        model.addForce(damper)
    if variant == "assisted":
        actuator = osim.CoordinateActuator(coordinate)
        actuator.setName(ACTUATOR_NAME)
        actuator.setOptimalForce(1)  # Control value is native-coordinate torque in Nm.
        cap = float(config["assistance"]["maximum_torque_nm"])
        actuator.setMinControl(-cap)
        actuator.setMaxControl(cap)
        model.addForce(actuator)
    model.finalizeConnections()
    return model


def write_model(model, path):
    """Serialize relative mesh references; output/Geometry travels with the model."""
    path = Path(path)
    for component in model.getComponentsList():
        mesh = osim.Mesh.safeDownCast(component)
        if mesh is not None:
            mesh.set_mesh_file("Geometry/" + Path(mesh.get_mesh_file()).name)
    model.printToXML(str(path))
    return path


def build_project(output_dir=DEFAULT_OUTPUT, config_path=DEFAULT_CONFIG):
    from .profile import export_csv

    output_dir = Path(output_dir).resolve()
    if output_dir == BASE_MODEL.parent or BASE_MODEL.is_relative_to(output_dir):
        raise ValueError("Output must be separate from the original model assets")
    config = load_settings(config_path)
    profile = input_profile(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASE_MODEL.parent / "Geometry", output_dir / "Geometry", dirs_exist_ok=True)
    files = {}
    masses = {}
    for variant, filename in (("bare", "human_bare.osim"),
                              ("unpowered", "knee_exosuit_unpowered.osim"),
                              ("assisted", "knee_exosuit.osim")):
        model = build_model(config, variant)
        state = model.initSystem()
        masses[variant] = model.getTotalMass(state)
        files[variant] = str(write_model(model, output_dir / filename).name)
    export_csv(output_dir / "pressure_profile.csv", profile)
    walking_source = BASE_MODEL.parent.parent / "walking/normal.mot"
    shutil.copy2(walking_source, output_dir / "normal_walking.mot")
    (output_dir / "configuration.json").write_text(json.dumps(config, indent=2) + "\n")
    metadata = {
        "opensim_version": osim.GetVersionAndDate(),
        "base_model_sha256": hashlib.sha256(BASE_MODEL.read_bytes()).hexdigest(),
        "models": files,
        "total_mass_kg": masses,
        "human_coordinates": 23,
        "human_muscles": 92,
        "native_knee_coordinate": config["model"]["knee_coordinate"],
        "flexion_sign": config["model"]["flexion_sign"],
        "actuator_control_units": "native-coordinate torque Nm; optimal_force = 1",
        "actuator_bounds": "OpenSim optimization bounds, not a forward-dynamics clamp; external callers must clamp their input. The example profile is capped by the pneumatic helper.",
        "pressure_state_location": "Python profile helper, not a native .osim state",
        "full_model_controller": "none; commandable moment input with zero default control",
        "walking_playback": "normal_walking.mot: official Gait2392 normal gait, 51 frames over 1 second; in-place kinematic playback, not a prediction of assistance effects. Six omitted coordinates retain their model defaults.",
        "limitations": config["parameter_status"],
    }
    (output_dir / "model_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return output_dir


def input_profile(config):
    """Keep controller knots on the command grid, independent of report cadence."""
    from .profile import build_profile
    rate = float(config["assistance"]["command_rate_hz"])
    if not rate > 0:
        raise ValueError("assistance.command_rate_hz must be positive")
    return build_profile(config, config["demo"]["duration_s"], 1.0 / rate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(f"Built native OpenSim models in {build_project(args.output, args.config)}")


if __name__ == "__main__":
    main()
