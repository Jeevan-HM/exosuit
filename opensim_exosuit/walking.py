"""Prepare the bare human walking model and plot the reference knee trajectory.

Motion is the unchanged official OpenSim tutorial normal gait, not a forward
walking simulation. Four knee-motion regions are delimited by angle extrema;
the source does not contain measured heel-strike or toe-off events.
"""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/exosuit-opensim-matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import opensim as osim

from .builder import write_model
from .settings import BASE_MODEL, PACKAGE_DIR

WALKING_SOURCE = PACKAGE_DIR / "assets/walking/normal.mot"
DEFAULT_OUTPUT = PACKAGE_DIR.parent / "human_walking"


def read_trajectory(path=WALKING_SOURCE):
    table = osim.TimeSeriesTable(str(path))
    if table.getTableMetaDataAsString("inDegrees").lower() != "yes":
        raise ValueError("Expected the bundled degree-based reference motion")
    time = np.asarray(table.getIndependentColumn(), dtype=float)
    if len(time) < 5 or not np.all(np.isfinite(time)) or not np.all(np.diff(time) > 0):
        raise ValueError("Motion times must be finite and strictly increasing")
    angles = {}
    for side in ("r", "l"):
        column = table.getDependentColumn(f"knee_angle_{side}")
        angles[side] = -np.asarray([column[i] for i in range(column.size())])
        if not np.all(np.isfinite(angles[side])):
            raise ValueError("Knee angles must be finite")
    cycle = 100 * (time - time[0]) / (time[-1] - time[0])
    return time, cycle, angles


def knee_landmarks(time, cycle, flexion):
    """Find this reference gait's ordered extrema in explicit search windows."""
    indices = []
    for lower, upper, kind in ((0, 30, "max"), (25, 55, "min"), (55, 85, "max")):
        candidates = np.flatnonzero((cycle >= lower) & (cycle <= upper))
        if len(candidates) == 0:
            raise ValueError("Motion does not cover the required phase search window")
        selected = (np.argmax if kind == "max" else np.argmin)(flexion[candidates])
        indices.append(int(candidates[selected]))
    if not indices[0] < indices[1] < indices[2]:
        raise ValueError("Could not identify an ordered flexion/extension sequence")
    labels = ("Early-stance flexion peak", "Stance extension minimum", "Swing flexion peak")
    return [{"label": label, "sample_index": index, "time_s": float(time[index]),
             "gait_cycle_percent": float(cycle[index]), "knee_flexion_deg": float(flexion[index])}
            for index, label in zip(indices, labels)]


def plot_trajectory(time, cycle, angles, output_dir):
    landmarks = knee_landmarks(time, cycle, angles["r"])
    boundaries = [0] + [point["gait_cycle_percent"] for point in landmarks] + [100]
    labels = ("Phase 1\nEarly-stance\nflexion", "Phase 2\nStance\nextension",
              "Phase 3\nLate-stance / swing\nflexion", "Phase 4\nSwing\nextension")
    plt.rcParams.update({"font.family": "STIXGeneral", "font.size": 15,
                         "axes.labelsize": 18, "xtick.labelsize": 13,
                         "ytick.labelsize": 14})
    figure, axis = plt.subplots(figsize=(13.5, 8.5))
    figure.subplots_adjust(left=.09, right=.97, bottom=.21, top=.74)
    figure.suptitle("Human walking — right-knee angle trajectory", x=.53, y=.98,
                   fontsize=23, fontweight="bold")
    figure.text(.53, .915, "Bare human  |  One reference gait cycle  |  Flexion positive",
                ha="center", fontsize=15, color="#526373")
    for index, (start, end, label) in enumerate(zip(boundaries[:-1], boundaries[1:], labels)):
        axis.axvspan(start, end, facecolor=("#f9eafa" if index % 2 == 0 else "#e8f9fa"), zorder=0)
        transform = axis.get_xaxis_transform()
        axis.plot([start, end], [1.025, 1.025], transform=transform,
                  color="#2b2b2b", linewidth=1.3, clip_on=False)
        for edge in (start, end):
            axis.plot([edge, edge], [1.016, 1.034], transform=transform,
                      color="#2b2b2b", linewidth=1.3, clip_on=False)
        axis.text((start + end) / 2, 1.055, label, transform=transform,
                  ha="center", va="bottom", fontsize=14, linespacing=1.15)
    axis.plot(cycle, angles["r"], color="#6aa9c9", linewidth=5.5,
              solid_capstyle="round", solid_joinstyle="round", zorder=3)
    for point in landmarks:
        x, y = point["gait_cycle_percent"], point["knee_flexion_deg"]
        axis.axvline(x, color="#6d6d6d", linestyle=(0, (3, 3)), linewidth=1.2, zorder=2)
        axis.scatter([x], [y], s=145, facecolor="#e52222", edgecolor="white", linewidth=1.0, zorder=4)
        text = f"{y:.2f}° at {x:.0f}%\n({point['time_s']:.2f} s)"
        offset = ((18, 15) if point is landmarks[0] else
                  (12, 16) if point is landmarks[1] else (18, -34))
        axis.annotate(text, (x, y), xytext=offset, textcoords="offset points", fontsize=13,
                      color="#253c4d", ha="left", va="bottom")
    axis.set_xlim(0, 100)
    axis.set_ylim(-2, 70)
    axis.set_xticks(np.arange(0, 101, 10))
    axis.set_yticks(np.arange(0, 61, 10))
    axis.set_xlabel("Gait cycle (%)", labelpad=10)
    axis.set_ylabel("Knee flexion angle (degrees)", labelpad=10)
    axis.grid(axis="y", color="#d5dde1", linewidth=.8, alpha=.7)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(handles=[Line2D([0], [0], color="#6aa9c9", linewidth=5, label="Right knee angle"),
                         Line2D([0], [0], marker="o", linestyle="none", color="#e52222",
                                markersize=10, label="Knee-angle extrema")],
                loc="upper left", frameon=True, facecolor="white", edgecolor="#d0d7dc", fontsize=13)
    figure.text(.09, .105, "Phase divisions follow knee-angle extrema; foot-contact events were not recorded in this motion file.",
                fontsize=12, color="#4e606d")
    figure.text(.09, .070, "Source: OpenSim Gait2392 tutorial normal.mot • 51 samples over 1.00 second",
                fontsize=12, color="#4e606d")
    for extension in ("png", "svg"):
        figure.savefig(output_dir / f"knee_angle_trajectory.{extension}", dpi=220,
                       facecolor="white")
    plt.close(figure)
    return landmarks


def prepare(output_dir=DEFAULT_OUTPUT):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASE_MODEL.parent / "Geometry", output_dir / "Geometry", dirs_exist_ok=True)
    osim.ModelVisualizer.addDirToGeometrySearchPaths(str(BASE_MODEL.parent / "Geometry"))
    model = osim.Model(str(BASE_MODEL))
    model.setName("Human_Walking")
    model.setDescription("Generic Gait2392 human only, without a wearable device. "
                         "normal_walking.mot is tutorial reference kinematics for in-place "
                         "playback, not a forward simulation or patient-specific result.")
    state = model.initSystem()
    model.equilibrateMuscles(state)
    if model.getBodySet().getSize() != 12 or model.getMuscles().getSize() != 92:
        raise RuntimeError("Unexpected source human anatomy")
    if any("exosuit" in component.getName().lower() for component in model.getComponentsList()):
        raise RuntimeError("A wearable component remains in the bare human model")
    write_model(model, output_dir / "human_walking.osim")
    shutil.copy2(WALKING_SOURCE, output_dir / "normal_walking.mot")
    shutil.copy2(PACKAGE_DIR / "assets/LICENSE_CC_BY_3.0.txt", output_dir / "MODEL_LICENSE.txt")
    time, cycle, angles = read_trajectory()
    with (output_dir / "knee_angle_trajectory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "gait_cycle_percent", "right_knee_flexion_deg", "left_knee_flexion_deg"])
        writer.writerows(zip(time, cycle, angles["r"], angles["l"]))
    landmarks = plot_trajectory(time, cycle, angles, output_dir)
    metadata = {"source_motion": "OpenSim Gait2392 tutorial normal.mot",
                "source_motion_sha256": hashlib.sha256(WALKING_SOURCE.read_bytes()).hexdigest(),
                "sample_count": len(time), "duration_s": float(time[-1] - time[0]),
                "model": "Generic Gait2392 human only; no exosuit",
                "model_total_mass_kg": model.getTotalMass(state),
                "knee_flexion_convention": "negative of the native knee_angle_l/r columns, in degrees",
                "plotted_knee": "right", "phase_boundaries": "knee extrema, not measured contact events",
                "landmarks": landmarks,
                "stance_swing_contact_events": "not available in this source file",
                "scope": "Reference kinematic playback and plot, not autonomous or clinically validated walking"}
    (output_dir / "trajectory_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output_dir / "README.md").write_text(
        "# Bare human walking\n\n"
        "For live OpenSim physics and a knee-angle plot, double-click "
        "`../Run_OpenSim_Physics.command` and keep its window open. The local viewer "
        "at http://127.0.0.1:8765/ uses actual integrated joint states. This is "
        "supported torque-controlled motion: virtual pelvis support, muscle "
        "forces disabled, no foot-ground contact. All coordinates are free. "
        "See [the simulation instructions](../README.md) for controls and scope.\n\n"
        "Open `human_walking.osim` with its adjacent `Geometry/` folder, then load "
        "`normal_walking.mot`. This is the generic Gait2392 human with no exosuit, "
        "cuffs, added device inertia, damping or assistance actuator.\n\n"
        "For continuous playback with synchronized degree-based knee plots, open "
        "`live_walking.html`, or double-click `../View_Reference_Walking.command`. "
        "The one-second reference cycle loops indefinitely. Pause, restart, speed, "
        "knee selection and the timeline affect the anatomy and plots together.\n\n"
        "For the green Run button in OpenSim Creator, open `human_walking_playback.osim`. "
        "This explicitly kinematic version prescribes the gait, so it does not fall "
        "through the displayed floor. It plays for 120 seconds, settles over its "
        "final cycle and then holds the final pose. Its motion is imposed, not "
        "predicted by a human motor controller. The separate unconstrained "
        "`human_walking.osim` has no ground-contact forces or walking controller; "
        "using free forward dynamics on that research model will fall under gravity.\n\n"
        "In OpenSim Creator: Preview Experimental Data → load model → human_walking.osim → "
        "load model trajectory sto/mot file → normal_walking.mot. Move the 0–1 second time slider. "
        "In standard OpenSim: File → Open Model, File → Load Motion, then Play/Loop.\n\n"
        "`knee_angle_trajectory.png` is the phase-annotated right-knee figure. "
        "An editable vector version is `knee_angle_trajectory.svg`. The CSV stores "
        "both knees; flexion is positive. Phase divisions are based on knee extrema, "
        "not measured heel strike/toe off. No error band is estimated.\n\n"
        "`human_walking.gif` is the looping human-only preview when the animation "
        "export has been run. It uses native OpenSim bone geometry and anatomical "
        "muscle paths; their color does not estimate muscle activity.\n\n"
        "Source anatomy and credits: [official Gait2392 model](https://github.com/opensim-org/opensim-models/"
        "blob/d9b05d470b1a481c222372c85b75772faf8f7792/Models/Gait2392_Simbody/gait2392_thelen2003muscle.osim). "
        "The original model credits are retained; CC BY 3.0 legal text is in MODEL_LICENSE.txt. "
        "Changes: model name/description and relative geometry paths only.\n\n"
        "Source motion: [official normal.mot](https://github.com/opensim-org/opensim-models/"
        "blob/d9b05d470b1a481c222372c85b75772faf8f7792/Tutorials/Intro_to_Musculoskeletal_Modeling/normal.mot). "
        "The original motion is unchanged and contains 17 coordinates over 1 second. "
        "Six omitted coordinates remain at zero defaults for in-place playback. "
        "This is reference motion, without a human motor controller, force/contact data, "
        "muscle activity estimates or a prediction of patient behavior.\n\n"
        "Rebuild from the simulation folder: `.opensim-venv/bin/python -m opensim_exosuit.walking`. "
        "Then export the animation with `.opensim-venv/bin/python -m opensim_exosuit.walking_animation`.\n"
        "Build the live viewer with `.opensim-venv/bin/python -m opensim_exosuit.live_viewer`.\n"
        "Build the native Run-button playback with `.opensim-venv/bin/python -m opensim_exosuit.prescribed_walk`.\n"
    )
    return output_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    osim.Logger.setLevelString("Warn")
    print(f"Prepared bare human walking and knee trajectory: {prepare(args.output)}")


if __name__ == "__main__":
    main()
