"""Build a native Run-compatible KINEMATIC reference walking model.

Every coordinate is prescribed; all muscle forces are disabled. Constraint
reactions support the prescribed pose against ordinary gravity. This is a
visual diagnostic, not autonomous balance, foot contact, forward-controlled
walking, muscle-force prediction, or evidence about rehabilitation outcomes.

OpenSim 4.6 ExpressionBasedFunction documents only first derivatives, so the
native prescribed coordinates use SimmSpline (which supplies second
derivatives). Playback repeats the one-second reference for 119 seconds, then
smoothly stops over the final cycle of a 120-second demonstration. A constant
tail makes subsequent extrapolation hold the final pose numerically.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import opensim as osim

from .builder import write_model
from .walking import DEFAULT_OUTPUT
from .walking_animation import _read_motion


def _periodic_values(samples, phases):
    """Real Fourier interpolant through the 50 source points, without t=1."""
    count = len(samples)
    coefficients = np.fft.rfft(samples) / count
    result = np.full_like(np.asarray(phases, dtype=float), coefficients[0].real)
    for index, coefficient in enumerate(coefficients[1:], 1):
        factor = 1 if count % 2 == 0 and index == count // 2 else 2
        angle = 2 * np.pi * index * np.asarray(phases)
        result += factor * (coefficient.real * np.cos(angle) - coefficient.imag * np.sin(angle))
    return result


def _spline(samples, horizon):
    # Keep the native 20 ms source samples through every repeated cycle. The
    # Fourier construction closes the loop without using the mismatched t=1
    # boundary sample as a second value for the same periodic phase.
    times = np.arange(round(horizon * 50) + 1, dtype=float) / 50
    values = _periodic_values(samples, np.remainder(times, 1.0))
    stop = np.clip(times - (horizon - 1), 0, 1)
    fade = 1 - 10 * stop**3 + 15 * stop**4 - 6 * stop**5
    values = samples[0] + fade * (values - samples[0])
    # A long sequence of identical tail points removes the spline's terminal
    # derivative; its native linear extrapolation then retains the final pose.
    tail = horizon + np.arange(1, 101, dtype=float) / 50
    times = np.r_[times, tail]
    values = np.r_[values, np.full(len(tail), samples[0])]
    function = osim.SimmSpline()
    for time, value in zip(times, values):
        function.addPoint(float(time), float(value))
    return function


def _value(function, time):
    return function.calcValue(osim.Vector(1, float(time)))


def _derivative(function, time):
    derivative = osim.StdVectorInt()
    derivative.append(0)
    return function.calcDerivative(derivative, osim.Vector(1, float(time)))


def _validate(model_path, directory, source_hash, source_columns, source_times, horizon):
    """Round-trip load and actually integrate native OpenSim past twenty cycles."""
    model = osim.Model(str(model_path))
    if (model.getCoordinateSet().getSize() != 23 or model.getMuscles().getSize() != 92
            or model.getBodySet().getSize() != 12 or model.getControllerSet().getSize()):
        raise ValueError("Unexpected human anatomy or controllers in playback model")
    for coordinate in model.getCoordinateSet():
        if not coordinate.getDefaultIsPrescribed():
            raise ValueError("Every coordinate must be prescribed for kinematic playback")
        if not np.isclose(_derivative(coordinate.getPrescribedFunction(), horizon + 10), 0, atol=1e-12):
            raise ValueError("The playback must hold its final pose beyond its explicit horizon")
    if any(muscle.get_appliesForce() for muscle in model.getMuscles()):
        raise ValueError("Muscle forces must be disabled in this visual diagnostic")
    for coordinate, values in source_columns:
        function = model.getCoordinateSet().get(coordinate.getName()).getPrescribedFunction()
        reproduced = np.array([_value(function, time) for time in source_times[:-1]])
        if not np.allclose(reproduced, values[:-1], atol=1e-10, rtol=0):
            raise ValueError("The initial reference cycle changed its fifty source samples")
    state = model.initSystem()
    manager = osim.Manager(model)
    manager.setIntegratorAccuracy(1e-6)
    manager.setIntegratorMaximumStepSize(.02)
    manager.initialize(state)
    rows, maximum_error = [], 0.0
    pelvis = model.getCoordinateSet().get("pelvis_ty")
    right = model.getCoordinateSet().get("knee_angle_r")
    left = model.getCoordinateSet().get("knee_angle_l")
    for time in np.arange(0, 20.251, .25):
        if time:
            state = manager.integrate(float(time))
        model.realizePosition(state)
        for coordinate in model.getCoordinateSet():
            expected = _value(coordinate.getPrescribedFunction(), time)
            maximum_error = max(maximum_error, abs(coordinate.getValue(state) - expected))
        rows.append({"time_s": float(time), "pelvis_height_m": pelvis.getValue(state),
                     "right_knee_flexion_deg": float(-np.degrees(right.getValue(state))),
                     "left_knee_flexion_deg": float(-np.degrees(left.getValue(state)))})
    heights = np.array([row["pelvis_height_m"] for row in rows])
    if not np.all(np.isfinite(heights)) or heights.min() < .5 or maximum_error > 1e-6:
        raise ValueError("Native playback integration did not maintain the prescribed walking pose")
    if source_hash != hashlib.sha256((directory / "human_walking.osim").read_bytes()).hexdigest():
        raise ValueError("The original bare human model was modified")
    with (directory / "playback_validation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return {"native_manager_integrated_until_s": rows[-1]["time_s"],
            "validation_sample_count": len(rows), "pelvis_height_range_m": [float(heights.min()), float(heights.max())],
            "maximum_prescribed_coordinate_error_native_units": maximum_error,
            "all_23_coordinates_prescribed": True, "all_92_muscle_forces_disabled": True,
            "original_model_sha256_unchanged": source_hash,
            "native_model_roundtrip_load": "passed", "reference_50_sample_match": "passed",
            "final_pose_hold_derivative": "below 1e-12 in native units per second",
            "gravity_m_s2": [model.getGravity().get(index) for index in range(3)]}


def build_prescribed_walk(directory=DEFAULT_OUTPUT, horizon_s=120.0) -> Path:
    """Create a separate model that walks visually when native Run is pressed."""
    if not np.isfinite(horizon_s) or horizon_s < 22 or horizon_s != round(horizon_s):
        raise ValueError("Playback horizon must be a finite whole number of seconds, at least 22")
    directory = Path(directory).resolve()
    original = directory / "human_walking.osim"
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    osim.Logger.removeFileSink()
    osim.Logger.setLevelString("Warn")
    osim.ModelVisualizer.addDirToGeometrySearchPaths(str(directory / "Geometry"))
    model = osim.Model(str(original))
    times, columns = _read_motion(model, directory / "normal_walking.mot")
    if len(times) != 51 or not np.allclose(times, np.arange(51) / 50, atol=1e-10):
        raise ValueError("Expected the fifty-interval, one-second bundled normal gait")
    source = {coordinate.getName(): values for coordinate, values in columns}
    model.setName("Human_Walking_Playback")
    model.setDescription(
        "KINEMATIC REFERENCE PLAYBACK — ALL 23 COORDINATES PRESCRIBED, ALL MUSCLE FORCES DISABLED. "
        "Press Run to view the generic bare human reference gait without falling. "
        "119 seconds of repeated reference cycles, then one cycle fading to a held pose. "
        "NOT autonomous walking, balance control, measured foot contact, forward muscle simulation, "
        "or a rehabilitation result. Original human_walking.osim is unchanged. Normal gravity remains active.")
    omitted, endpoint_difference = [], {}
    for coordinate in model.updCoordinateSet():
        name = coordinate.getName()
        coordinate.setDefaultLocked(False)
        coordinate.setDefaultClamped(False)
        if name in source:
            values = source[name]
            function = _spline(values[:-1], horizon_s)
            endpoint_difference[name] = float(values[-1] - values[0])
        else:
            function = osim.Constant(coordinate.getDefaultValue())
            omitted.append(name)
        coordinate.setPrescribedFunction(function)
        coordinate.setDefaultIsPrescribed(True)
        coordinate.setDefaultValue(_value(function, 0))
        coordinate.setDefaultSpeedValue(_derivative(function, 0))
    for muscle in model.updMuscles():
        muscle.set_appliesForce(False)
    model.finalizeConnections()
    previous_precision = osim.IO.GetPrecision()
    try:
        osim.IO.SetPrecision(17)
        path = write_model(model, directory / "human_walking_playback.osim")
    finally:
        osim.IO.SetPrecision(previous_precision)
    # OpenSim's legacy SimmSpline array serializer uses six significant
    # digits independently of IO.SetPrecision. Preserve the exact native knot
    # values when writing these generated playback functions to XML.
    document = ET.parse(path)
    for coordinate in model.getCoordinateSet():
        function = osim.SimmSpline.safeDownCast(coordinate.getPrescribedFunction())
        if function is None:
            continue
        element = document.find(f".//Coordinate[@name='{coordinate.getName()}']/prescribed_function/SimmSpline")
        element.find("x").text = " ".join(format(function.getX(index), ".17g")
                                           for index in range(function.getSize()))
        element.find("y").text = " ".join(format(function.getY(index), ".17g")
                                           for index in range(function.getSize()))
    document.write(path, encoding="utf-8", xml_declaration=True)
    validation = _validate(path, directory, original_hash, columns, times, horizon_s)
    validation.update({"model_file": path.name, "scope": "KINEMATIC REFERENCE PLAYBACK ONLY",
                       "repeat_period_s": 1, "repeat_until_s": horizon_s - 1,
                       "smooth_stop_cycle_s": [horizon_s - 1, horizon_s],
                       "constant_spline_tail_until_s": horizon_s + 2,
                       "missing_source_coordinates_held_at_defaults": omitted,
                       "source_endpoint_difference_native_units": endpoint_difference,
                       "loop_seam": "Fourier interpolation uses the first fifty samples, excludes the duplicate cycle endpoint; no measured contact events",
                       "function_choice": "Native SimmSpline supports second derivatives; ExpressionBasedFunction in OpenSim 4.6 supports first derivatives only",
                       "run_instruction": "Open human_walking_playback.osim, keep its adjacent Geometry folder, then press native Run. No motion-file import required."})
    (directory / "playback_validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--horizon", type=float, default=120.0)
    args = parser.parse_args()
    print(f"Created and validated native kinematic playback: {build_prescribed_walk(args.directory, args.horizon)}")


if __name__ == "__main__":
    main()
