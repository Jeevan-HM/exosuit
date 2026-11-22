"""Export native OpenSim anatomy and reference poses for the browser viewer.

Bone vertices stay in their own OpenSim physical frame. Frame poses and muscle
line endpoints are evaluated by OpenSim at all 51 recorded motion samples in
ground coordinates (Y-up, metres). This is bare-human kinematic reference
playback, not a forward walking simulation or an estimate of muscle activity.
"""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import opensim as osim

from .walking import DEFAULT_OUTPUT
from .walking_animation import _read_motion, _set_pose


def _indexed_mesh(path, scales):
    """Read bundled ASCII VTK PolyData while retaining shared mesh vertices."""
    root = ET.parse(path)
    point_array = root.find(".//Points/DataArray")
    if point_array is None or point_array.get("format", "ascii") != "ascii":
        raise ValueError(f"Expected an ASCII VTK point array: {path}")
    points = np.fromstring(point_array.text or "", sep=" ").reshape(-1, 3)
    points *= scales
    arrays = {}
    for array in root.findall(".//Polys/DataArray"):
        if array.get("format", "ascii") != "ascii":
            raise ValueError(f"Expected ASCII VTK polygons: {path}")
        arrays[array.get("Name")] = np.fromstring(array.text or "", sep=" ", dtype=int)
    faces, start = [], 0
    for end in arrays["offsets"]:
        polygon = arrays["connectivity"][start:end]
        if len(polygon) < 3:
            raise ValueError(f"Degenerate VTK polygon in {path}")
        faces.extend((polygon[0], polygon[index], polygon[index + 1])
                     for index in range(1, len(polygon) - 1))
        start = end
    triangles = np.asarray(faces, dtype=int)
    if (not len(points) or not len(triangles) or triangles.min() < 0
            or triangles.max() >= len(points) or not np.all(np.isfinite(points))):
        raise ValueError(f"Invalid mesh topology or vertices: {path}")
    # Sum face cross products for area-weighted averaged vertex normals. Apply
    # nonuniform mesh scale before this calculation, not to the final normals.
    normals = np.zeros_like(points)
    edges = points[triangles]
    face_normals = np.cross(edges[:, 1] - edges[:, 0], edges[:, 2] - edges[:, 0])
    for corner in range(3):
        np.add.at(normals, triangles[:, corner], face_normals)
    lengths = np.linalg.norm(normals, axis=1)
    zero = lengths <= np.finfo(float).eps
    # Isolated or cancelling vertices have no averaged surface direction.
    # The stable fallback only affects such degenerate vertices.
    normals[zero] = (0, 1, 0)
    lengths[zero] = 1
    normals /= lengths[:, None]
    return points, normals, triangles


def _quaternion(matrix):
    """Convert an orthonormal ground rotation matrix to normalized xyzw."""
    if (not np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-10)
            or not np.isclose(np.linalg.det(matrix), 1, atol=1e-10)):
        raise ValueError("OpenSim returned a non-orthonormal frame rotation")
    trace = np.trace(matrix)
    if trace > 0:
        scale = 2 * np.sqrt(trace + 1)
        result = np.array(((matrix[2, 1] - matrix[1, 2]) / scale,
                           (matrix[0, 2] - matrix[2, 0]) / scale,
                           (matrix[1, 0] - matrix[0, 1]) / scale, .25 * scale))
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            scale = 2 * np.sqrt(1 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2])
            result = np.array((.25 * scale, (matrix[0, 1] + matrix[1, 0]) / scale,
                               (matrix[0, 2] + matrix[2, 0]) / scale,
                               (matrix[2, 1] - matrix[1, 2]) / scale))
        elif index == 1:
            scale = 2 * np.sqrt(1 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2])
            result = np.array(((matrix[0, 1] + matrix[1, 0]) / scale, .25 * scale,
                               (matrix[1, 2] + matrix[2, 1]) / scale,
                               (matrix[0, 2] - matrix[2, 0]) / scale))
        else:
            scale = 2 * np.sqrt(1 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1])
            result = np.array(((matrix[0, 2] + matrix[2, 0]) / scale,
                               (matrix[1, 2] + matrix[2, 1]) / scale, .25 * scale,
                               (matrix[1, 0] - matrix[0, 1]) / scale))
    return result / np.linalg.norm(result)


def _rotation_from_quaternion(quaternion):
    x, y, z, w = quaternion
    return np.array(((1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)),
                     (2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)),
                     (2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y))))


def verify_live_data(data, expected_times=None, expected_angles=None):
    """Check the saved viewer contract, numerical values and source alignment."""
    times = np.asarray(data["times"], dtype=float)
    if (data["schema_version"] != 1 or len(times) != 51
            or not np.all(np.isfinite(times)) or not np.all(np.diff(times) > 0)
            or not np.isclose(times[0], 0) or not np.isclose(times[-1], 1)
            or not np.isclose(data["duration_s"], 1)):
        raise ValueError("Expected the 51 recorded samples of the one-second reference gait")
    if expected_times is not None and not np.allclose(times, expected_times, atol=1e-9):
        raise ValueError("Exported times differ from the source motion")
    frame_count = len(data["frame_names"])
    if frame_count != 12 or len(set(data["frame_names"])) != frame_count:
        raise ValueError("Expected twelve distinct physical body frames")
    if data["source"]["muscle_count"] != 92 or len(data["muscle_names"]) != 92:
        raise ValueError("The bare source must retain all 92 muscle paths")
    if any(any(token in name.lower() for token in ("exosuit", "cuff", "pouch", "ground"))
           for name in data["frame_names"] + [mesh["name"] for mesh in data["meshes"]]):
        raise ValueError("Ground or wearable geometry remains in the live scene")
    poses = np.asarray(data["poses"], dtype=float)
    if poses.shape != (51, frame_count * 7) or not np.all(np.isfinite(poses)):
        raise ValueError("Invalid native frame poses")
    quaternions = poses.reshape(51, frame_count, 7)[:, :, 3:]
    if not np.allclose(np.linalg.norm(quaternions, axis=2), 1, atol=2e-6):
        raise ValueError("Frame quaternions must be unit length")
    for side in ("r", "l"):
        angles = np.asarray(data["knee_flexion_deg"][side], dtype=float)
        if angles.shape != (51,) or not np.all(np.isfinite(angles)):
            raise ValueError("Invalid knee-angle samples")
        if expected_angles is not None and not np.allclose(
                angles, np.round(expected_angles[side], 2), atol=1e-9):
            raise ValueError("Exported knee angles differ from source motion")
    low, high = np.asarray(data["bounds"]["min"]), np.asarray(data["bounds"]["max"])
    if (low.shape != (3,) or high.shape != (3,) or not np.all(np.isfinite([low, high]))
            or not np.all(high > low)):
        raise ValueError("Invalid whole-motion world bounds")
    for mesh in data["meshes"]:
        positions = np.asarray(mesh["positions"], dtype=float).reshape(-1, 3)
        normals = np.asarray(mesh["normals"], dtype=float).reshape(-1, 3)
        indices = np.asarray(mesh["indices"])
        if (positions.shape != normals.shape or not np.all(np.isfinite([positions, normals]))
                or not 0 <= mesh["frame_index"] < frame_count or indices.size % 3
                or indices.dtype.kind not in "iu" or indices.min() < 0
                or indices.max() >= len(positions)
                or not np.allclose(np.linalg.norm(normals, axis=1), 1, atol=2e-6)):
            raise ValueError("Invalid indexed bone geometry")
    if len(data["muscles"]) != 51 or len(data["muscle_segment_counts"]) != 51:
        raise ValueError("Missing muscle samples")
    for lines, counts in zip(data["muscles"], data["muscle_segment_counts"]):
        lines = np.asarray(lines, dtype=float)
        if (lines.ndim != 1 or lines.size % 6 or not np.all(np.isfinite(lines))
                or len(counts) != 92 or min(counts) < 1 or sum(counts) * 6 != lines.size):
            raise ValueError("Each gait sample must include all 92 native muscle paths")
        vertices = lines.reshape(-1, 3)
        if np.any(vertices < low - 2e-6) or np.any(vertices > high + 2e-6):
            raise ValueError("Muscle paths fall outside exported world bounds")
    return True


def export_live_data(directory=DEFAULT_OUTPUT) -> Path:
    """Write a verified browser scene from the bare model and unchanged motion."""
    directory = Path(directory).resolve()
    model_path, motion_path = directory / "human_walking.osim", directory / "normal_walking.mot"
    osim.Logger.removeFileSink()
    osim.Logger.setLevelString("Warn")
    osim.ModelVisualizer.addDirToGeometrySearchPaths(str(directory / "Geometry"))
    model = osim.Model(str(model_path))
    if (model.getBodySet().getSize() != 12 or model.getMuscles().getSize() != 92
            or model.getCoordinateSet().getSize() != 23 or model.getControllerSet().getSize()):
        raise ValueError("Live export requires the unmodified bare Gait2392 human")
    for component in model.getComponentsList():
        if any(token in component.getName().lower() for token in ("exosuit", "cuff", "pouch")):
            raise ValueError("Wearable components are not allowed in the bare-human scene")
        if osim.CoordinateActuator.safeDownCast(component) is not None:
            raise ValueError("Assistance actuators are not allowed in the bare-human scene")
    state = model.initSystem()
    times, columns = _read_motion(model, motion_path)
    expected_angles = {side: -np.degrees(next(values for coordinate, values in columns
                                            if coordinate.getName() == f"knee_angle_{side}"))
                       for side in ("r", "l")}
    frames, frame_names, meshes, local_points = [], [], [], []
    for component in model.getComponentsList():
        mesh = osim.Mesh.safeDownCast(component)
        if mesh is None or mesh.getFrame().getName() == "ground":
            continue
        frame = mesh.getFrame()
        frame_name = frame.getAbsolutePathString()
        if frame_name not in frame_names:
            frame_names.append(frame_name)
            frames.append(frame)
        points, normals, indices = _indexed_mesh(
            directory / mesh.get_mesh_file(), np.array([mesh.get_scale_factors().get(i) for i in range(3)]))
        meshes.append({"name": mesh.getName(), "frame_index": frame_names.index(frame_name),
                       "positions": np.round(points, 6).ravel().tolist(),
                       "normals": np.round(normals, 6).ravel().tolist(),
                       "indices": indices.ravel().tolist()})
        local_points.append(points)

    poses, muscle_samples, segment_counts = [], [], []
    angles = {"r": [], "l": []}
    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    previous_quaternions = [None] * len(frames)
    for index, time in enumerate(times):
        _set_pose(model, state, columns, index, time)
        pose, matrices, translations = [], [], []
        for frame_index, frame in enumerate(frames):
            transform = frame.getTransformInGround(state)
            matrix = np.array([[transform.R().get(i, j) for j in range(3)] for i in range(3)])
            translation = np.array([transform.p().get(i) for i in range(3)])
            quaternion = _quaternion(matrix)
            previous = previous_quaternions[frame_index]
            if previous is not None and np.dot(previous, quaternion) < 0:
                quaternion *= -1
            if not np.allclose(_rotation_from_quaternion(quaternion), matrix, atol=1e-10):
                raise ValueError("Quaternion conversion changed the native OpenSim rotation")
            previous_quaternions[frame_index] = quaternion
            pose.extend(np.round(np.r_[translation, quaternion], 6).tolist())
            matrices.append(matrix)
            translations.append(translation)
        poses.append(pose)
        for mesh, points in zip(meshes, local_points):
            frame_index = mesh["frame_index"]
            vertices = points @ matrices[frame_index].T + translations[frame_index]
            low, high = np.minimum(low, vertices.min(axis=0)), np.maximum(high, vertices.max(axis=0))
        lines, counts = [], []
        for muscle in model.getMuscles():
            path = muscle.getGeometryPath().getCurrentPath(state)
            points = []
            for point_index in range(path.getSize()):
                point = path.get(point_index).getLocationInGround(state)
                points.append([point.get(i) for i in range(3)])
            counts.append(len(points) - 1)
            for start, end in zip(points[:-1], points[1:]):
                lines.extend(start)
                lines.extend(end)
        vertices = np.asarray(lines).reshape(-1, 3)
        low, high = np.minimum(low, vertices.min(axis=0)), np.maximum(high, vertices.max(axis=0))
        muscle_samples.append(np.round(lines, 6).tolist())
        segment_counts.append(counts)
        for side in ("r", "l"):
            value = -np.degrees(model.getCoordinateSet().get(f"knee_angle_{side}").getValue(state))
            angles[side].append(round(float(value), 2))

    data = {"schema_version": 1, "duration_s": float(times[-1] - times[0]),
            "times": np.round(times, 8).tolist(), "knee_flexion_deg": angles,
            "frame_names": frame_names, "meshes": meshes, "poses": poses,
            "muscles": muscle_samples, "muscle_segment_counts": segment_counts,
            "muscle_names": [muscle.getName() for muscle in model.getMuscles()],
            "bounds": {"min": np.round(low - 1e-5, 6).tolist(),
                       "max": np.round(high + 1e-5, 6).tolist()},
            "source": {"model": "OpenSim Gait2392 bare human; no exosuit",
                       "model_file": model_path.name, "motion_file": motion_path.name,
                       "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                       "motion_sha256": hashlib.sha256(motion_path.read_bytes()).hexdigest(),
                       "body_count": 12, "coordinate_count": 23, "muscle_count": 92,
                       "mesh_count": len(meshes), "sample_count": len(times),
                       "axes": "OpenSim native Y-up; positions in metres; quaternion order xyzw",
                       "knee_angles": "Flexion positive, negative of native knee_angle_r/l in degrees",
                       "muscles": "All native anatomical paths; uniform display color does not encode activity",
                       "scope": "Reference kinematic playback; no forward walking simulation or patient data",
                       "missing_coordinates": "Six coordinates absent from the motion retain model defaults",
                       "ground_geometry": "Excluded; the source treadmill is not part of this human-only scene"}}
    verify_live_data(data, times, expected_angles)
    path = directory / "live_data.json"
    path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    verify_live_data(json.loads(path.read_text()), times, expected_angles)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(f"Exported native human gait scene: {export_live_data(args.directory)}")


if __name__ == "__main__":
    main()
