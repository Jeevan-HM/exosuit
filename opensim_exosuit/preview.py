"""Render actual OpenSim geometry and diagnostic results without a GUI install."""

import os
from pathlib import Path
import xml.etree.ElementTree as ET

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/exosuit-opensim-matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import opensim as osim


def _mesh_triangles(path):
    root = ET.parse(path)
    points = np.fromstring(root.find(".//Points/DataArray").text, sep=" ").reshape(-1, 3)
    polys = root.findall(".//Polys/DataArray")
    arrays = {array.get("Name"): np.fromstring(array.text, sep=" ", dtype=int) for array in polys}
    faces, start = [], 0
    for end in arrays["offsets"]:
        indices = arrays["connectivity"][start:end]
        for index in range(1, len(indices) - 1):
            faces.append([indices[0], indices[index], indices[index + 1]])
        start = end
    return points[np.asarray(faces)]


def _surface_triangles(kind, dimensions):
    if kind == "Cylinder":
        radius, height = dimensions
        theta = np.linspace(0, 2 * np.pi, 33)
        points = np.array([[radius * np.cos(t), y, radius * np.sin(t)]
                           for y in (-height, height) for t in theta])
        faces = []
        for i in range(32):
            faces.extend(([i, i + 1, i + 33], [i + 1, i + 34, i + 33]))
        return points[np.asarray(faces)]
    u, v = np.linspace(0, 2 * np.pi, 25), np.linspace(0, np.pi, 13)
    points = np.array([[dimensions[0] * np.cos(a) * np.sin(b),
                        dimensions[1] * np.cos(b),
                        dimensions[2] * np.sin(a) * np.sin(b)] for a in u for b in v])
    faces = []
    for i in range(24):
        for j in range(12):
            n = i * 13 + j
            faces.extend(([n, n + 13, n + 1], [n + 1, n + 13, n + 14]))
    return points[np.asarray(faces)]


def _draw_model(axis, model, state, output_dir):
    all_points = []
    for component in model.getComponentsList():
        geometry = osim.Geometry.safeDownCast(component)
        if geometry is None:
            continue
        frame = geometry.getFrame()
        if frame.getName() == "ground":
            continue
        kind = geometry.getConcreteClassName()
        if kind == "Mesh":
            mesh = osim.Mesh.safeDownCast(geometry)
            triangles = _mesh_triangles(output_dir / mesh.get_mesh_file())
            scale = mesh.get_scale_factors()
            triangles *= np.array([scale.get(i) for i in range(3)])
            color = "#d9d2bf"
        elif kind in ("Cylinder", "Ellipsoid"):
            xml = ET.fromstring(geometry.dump())
            dimensions = ([float(xml.findtext("radius")), float(xml.findtext("half_height"))]
                          if kind == "Cylinder" else
                          np.fromstring(xml.findtext("radii"), sep=" "))
            triangles = _surface_triangles(kind, dimensions)
            color = "#2771d6" if kind == "Cylinder" else "#df4a49"
        else:
            continue
        transform = frame.getTransformInGround(state)
        rotation = transform.R()
        matrix = np.array([[rotation.get(i, j) for j in range(3)] for i in range(3)])
        position = np.array([transform.p().get(i) for i in range(3)])
        world = triangles @ matrix.T + position
        # Matplotlib uses Z-up; OpenSim uses Y-up.
        world = world[..., [0, 2, 1]]
        all_points.append(world.reshape(-1, 3))
        collection = Poly3DCollection(world, facecolors=color, edgecolors="#807d75",
                                      linewidths=0.07, shade=True,
                                      alpha=1.0, zsort="average")
        axis.add_collection3d(collection)
    points = np.concatenate(all_points)
    low, high = points.min(axis=0), points.max(axis=0)
    pad = (high - low) * 0.05
    for setter, i in ((axis.set_xlim, 0), (axis.set_ylim, 1), (axis.set_zlim, 2)):
        setter(low[i] - pad[i], high[i] + pad[i])
    axis.set_box_aspect(high - low + 2 * pad)
    axis.view_init(elev=12, azim=-63)
    axis.set_axis_off()


def render_preview(output_dir, config, profile, results):
    output_dir = Path(output_dir)
    rows = results["assisted"]
    snapshot = max(rows, key=lambda row: abs(row["active_torque_flexion_positive_nm"]))
    model = osim.Model(str(output_dir / "seated_assisted.osim"))
    state = model.initSystem()
    knee = model.getCoordinateSet().get(config["model"]["knee_coordinate"])
    knee.setValue(state, config["model"]["flexion_sign"] * np.radians(snapshot["knee_flexion_deg"]), False)
    model.realizePosition(state)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": "#35445b", "text.color": "#14243c",
                         "xtick.color": "#59677b", "ytick.color": "#59677b"})
    figure = plt.figure(figsize=(14, 8), facecolor="#f4f7fb")
    figure.text(0.055, 0.93, "PNEUMATIC KNEE EXOSUIT", fontsize=22, weight="bold")
    figure.text(0.055, 0.89, "OpenSim 4.6  /  Generic human model  /  Left-knee assistance",
                fontsize=12, color="#59677b")
    geometry_axis = figure.add_axes([0.025, 0.12, 0.49, 0.71], projection="3d", facecolor="#f4f7fb")
    _draw_model(geometry_axis, model, state, output_dir)
    figure.text(0.07, 0.17, "Blue: cuffs    Red: actuator envelopes", fontsize=10, color="#59677b")
    figure.text(0.07, 0.135, f"Actual model pose at t = {snapshot['time_s']:.2f} s", fontsize=10, color="#59677b")

    pressure_axis = figure.add_axes([0.57, 0.55, 0.38, 0.26], facecolor="white")
    direction = config["assistance"]["direction"]
    pressure_axis.plot([r["time_s"] for r in profile],
                       [r[f"{direction}_command_psi"] for r in profile],
                       color="#a8b5c5", linestyle="--", label="Sampled command")
    pressure_axis.plot([r["time_s"] for r in profile],
                       [r[f"{direction}_pressure_psi"] for r in profile],
                       color="#2771d6", linewidth=2.2, label="Modeled pressure")
    pressure_axis.set_title("Pneumatic response", loc="left", fontsize=13, weight="bold", pad=10)
    pressure_axis.set_ylabel("Gauge PSI")
    pressure_axis.legend(loc="upper right", frameon=False, fontsize=9)
    pressure_axis.grid(axis="y", color="#e7edf4")
    pressure_axis.set_xlim(0, config["demo"]["duration_s"])

    motion_axis = figure.add_axes([0.57, 0.19, 0.38, 0.25], facecolor="white")
    for variant, color, label, style in (("bare", "#b2bcc9", "Bare human", ":"),
                                         ("unpowered", "#60768f", "Suit unpowered", "--"),
                                         ("assisted", "#df4a49", "Suit assisted", "-")):
        motion_axis.plot([r["time_s"] for r in results[variant]],
                         [r["knee_flexion_deg"] for r in results[variant]],
                         color=color, label=label, linestyle=style, linewidth=2)
    motion_axis.set_title("Forward-simulated knee response", loc="left", fontsize=13, weight="bold", pad=10)
    motion_axis.set_ylabel("Knee flexion (degrees)")
    motion_axis.set_xlabel("Time (seconds)")
    motion_axis.set_xlim(0, config["demo"]["duration_s"])
    motion_axis.grid(axis="y", color="#e7edf4")
    motion_axis.legend(frameon=False, loc="lower right", fontsize=9)
    figure.text(0.055, 0.07,
                "Mechanical test fixture: seated, one free knee, muscle forces disabled, added return spring.",
                fontsize=10, color="#59677b")
    figure.text(0.055, 0.04,
                "Full exported model retains 92 muscles and 23 coordinates. Device parameters are uncalibrated; no patient data shown.",
                fontsize=10, color="#59677b")
    figure.savefig(output_dir / "preview.png", dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)
    return output_dir / "preview.png"
