"""Render the bare OpenSim human following the supplied reference gait.

Run after ``python -m opensim_exosuit.walking``. Geometry and muscle paths use
OpenSim's actual poses at the recorded times. This is kinematic playback, not
a forward simulation, a patient response, or an estimate of muscle activity.
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/exosuit-opensim-matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
import numpy as np
import opensim as osim
from PIL import Image

from .preview import _mesh_triangles
from .walking import DEFAULT_OUTPUT


def _read_motion(model, path):
    table = osim.TimeSeriesTable(str(path))
    if table.getTableMetaDataAsString("inDegrees").lower() != "yes":
        raise ValueError("Expected the original degree-based normal_walking.mot")
    times = np.asarray(table.getIndependentColumn(), dtype=float)
    if len(times) < 3 or not np.all(np.isfinite(times)) or not np.all(np.diff(times) > 0):
        raise ValueError("Reference times must be finite and strictly increasing")
    columns = []
    for label in table.getColumnLabels():
        coordinate = model.updCoordinateSet().get(label)
        data = table.getDependentColumn(label)
        values = np.asarray([data[i] for i in range(data.size())], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError(f"Non-finite coordinate values: {label}")
        if coordinate.getMotionType() == osim.Coordinate.Rotational:
            values = np.radians(values)
        elif coordinate.getMotionType() != osim.Coordinate.Translational:
            raise ValueError(f"Unsupported coordinate type: {label}")
        # Translational values, including pelvis_ty, remain in metres. The six
        # coordinates absent from this file retain their original defaults.
        columns.append((coordinate, values))
    return times, columns


def _set_pose(model, state, columns, index, time):
    state.setTime(float(time))
    for coordinate, values in columns:
        coordinate.setValue(state, float(values[index]), False)
    model.realizePosition(state)


def _geometry_cache(model, directory):
    cached = []
    for component in model.getComponentsList():
        if any(word in component.getName().lower() for word in ("exosuit", "cuff", "pouch")):
            raise ValueError("The animation requires the human-only model")
        mesh = osim.Mesh.safeDownCast(component)
        if mesh is None or mesh.getFrame().getName() == "ground":
            continue
        triangles = _mesh_triangles(directory / mesh.get_mesh_file())
        scales = mesh.get_scale_factors()
        triangles *= np.array([scales.get(i) for i in range(3)])
        cached.append((mesh.getFrame(), triangles))
    if not cached:
        raise ValueError("The bare model contains no renderable bone geometry")
    return cached


def _world_triangles(frame, triangles, state):
    transform = frame.getTransformInGround(state)
    rotation = transform.R()
    matrix = np.array([[rotation.get(i, j) for j in range(3)] for i in range(3)])
    translation = np.array([transform.p().get(i) for i in range(3)])
    # OpenSim Y-up becomes Matplotlib Z-up for display only.
    return (triangles @ matrix.T + translation)[..., [0, 2, 1]]


def _muscle_segments(model, state):
    segments = []
    for muscle in model.getMuscles():
        path = muscle.getGeometryPath().getCurrentPath(state)
        points = []
        for index in range(path.getSize()):
            location = path.get(index).getLocationInGround(state)
            points.append([location.get(0), location.get(2), location.get(1)])
        segments.extend([points[index - 1], points[index]] for index in range(1, len(points)))
    return segments


def render_animation(directory=DEFAULT_OUTPUT, show_muscles=True):
    """Write a 600×700 GIF and poster using alternate recorded motion samples.

    With the bundled 51-row, one-second gait, frames are recorded samples at
    0.00, 0.04, ..., 0.96 seconds. Each lasts 40 ms. The terminal cycle boundary
    is not duplicated, and no pose is altered to force loop closure.
    """
    directory = Path(directory).resolve()
    osim.Logger.removeFileSink()
    osim.Logger.setLevelString("Warn")
    osim.ModelVisualizer.addDirToGeometrySearchPaths(str(directory / "Geometry"))
    model = osim.Model(str(directory / "human_walking.osim"))
    if model.getControllerSet().getSize():
        raise ValueError("Reference animation expects a model without controllers")
    state = model.initSystem()
    times, columns = _read_motion(model, directory / "normal_walking.mot")
    cache = _geometry_cache(model, directory)
    indices = list(range(0, len(times) - 1, 2))
    frame_times = times[indices]
    frame_ends = np.r_[frame_times[1:], times[-1]]
    durations_ms = np.rint((frame_ends - frame_times) * 1000).astype(int)
    if np.any(durations_ms <= 0) or np.any(durations_ms % 10):
        raise ValueError("Recorded frame timing must be representable by GIF's 10 ms clock")

    # Evaluate a fixed camera box over the full gait, rather than allowing it to
    # zoom or recenter whenever a moving foot changes the current pose bounds.
    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    for index in indices:
        _set_pose(model, state, columns, index, times[index])
        for frame, triangles in cache:
            vertices = _world_triangles(frame, triangles, state).reshape(-1, 3)
            low = np.minimum(low, vertices.min(axis=0))
            high = np.maximum(high, vertices.max(axis=0))
    padding = np.array([0.10, 0.08, 0.07])
    low -= padding
    high += padding

    background = "#f5f7fa"
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": "#263849"})
    figure = plt.figure(figsize=(6, 7), dpi=100, facecolor=background)
    figure.text(.5, .958, "Reference gait playback — human only", ha="center", fontsize=14,
                weight="bold")
    figure.text(.5, .920, "OpenSim Gait2392  •  No exosuit", ha="center", fontsize=11,
                color="#586a78")
    axis = figure.add_axes([-.045, .045, 1.09, .85], projection="3d", facecolor=background)
    axis.set_xlim(low[0], high[0])
    axis.set_ylim(low[1], high[1])
    axis.set_zlim(low[2], high[2])
    axis.set_box_aspect(high - low)
    axis.view_init(elev=9, azim=-68)
    axis.set_axis_off()
    artists = []
    _set_pose(model, state, columns, indices[0], frame_times[0])
    for frame, triangles in cache:
        artist = Poly3DCollection(_world_triangles(frame, triangles, state),
                                  facecolors="#d9cfb8", edgecolors="#877f70",
                                  linewidths=.055, zsort="average")
        axis.add_collection3d(artist)
        artists.append(artist)
    muscles = Line3DCollection(_muscle_segments(model, state) if show_muscles else [],
                               colors="#a9474b", linewidths=.85, alpha=.78)
    if show_muscles:
        axis.add_collection3d(muscles)
    timer = figure.text(.5, .060, "", ha="center", fontsize=11, color="#435b6b")
    figure.text(.5, .025, "Reference kinematics; muscle lines show anatomy, not activity.",
                ha="center", fontsize=8.5, color="#657785")

    frames = []
    poster_index = int(np.argmin(np.abs(frame_times - (times[0] + .72))))
    poster = None
    try:
        for frame_number, index in enumerate(indices):
            _set_pose(model, state, columns, index, times[index])
            for artist, (frame, triangles) in zip(artists, cache):
                artist.set_verts(_world_triangles(frame, triangles, state))
            if show_muscles:
                muscles.set_segments(_muscle_segments(model, state))
            timer.set_text(f"Time {times[index]:.2f} s  /  {times[-1] - times[0]:.2f} s reference cycle")
            figure.canvas.draw()
            rgba = np.asarray(figure.canvas.buffer_rgba())
            rendered = Image.fromarray(rgba[:, :, :3].copy())
            if frame_number == poster_index:
                poster = rendered.copy()
            frames.append(rendered.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    finally:
        plt.close(figure)
    gif_path = directory / "human_walking.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:],
                   duration=durations_ms.tolist(), loop=0, disposal=2,
                   optimize=True, comment=b"Reference gait playback - human only; actual OpenSim poses.")
    if poster is not None:
        poster.save(directory / "human_walking_poster.png")
    with Image.open(gif_path) as animation:
        if animation.n_frames != len(indices) or animation.size != (600, 700):
            raise RuntimeError("The saved animation did not preserve the expected frames")
        saved_duration = 0
        for index in range(animation.n_frames):
            animation.seek(index)
            saved_duration += animation.info["duration"]
        if saved_duration != int(durations_ms.sum()):
            raise RuntimeError("The saved animation changed the recorded frame timing")
    return gif_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-muscles", action="store_true")
    args = parser.parse_args()
    print(f"Rendered reference human gait: {render_animation(args.directory, not args.no_muscles)}")


if __name__ == "__main__":
    main()
