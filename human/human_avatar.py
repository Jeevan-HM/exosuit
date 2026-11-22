"""Solid clothed human drawn over the unchanged musculoskeletal simulation.

All shapes are MjvScene display geoms. They have no mass, collision, actuation,
or effect on the human controller. Arm anchors deliberately use actual joints;
some historical model body origins are mesh-authoring offsets, not anatomy.
"""
import numpy as np
import mujoco

SHIRT = np.array([0.14, 0.36, 0.40, 1.0])
SHORTS = np.array([0.075, 0.115, 0.19, 1.0])
SHOE = np.array([0.14, 0.17, 0.21, 1.0])
SOLE = np.array([0.76, 0.78, 0.77, 1.0])
HAIR = np.array([0.105, 0.075, 0.060, 1.0])


class HumanAvatar:
    """Append a familiar, clothed person to an existing rendering scene.

    ``draw(..., clear=True)`` is appropriate for viewer.user_scn. For an offline
    Renderer.scene, retain its ground/light scene and use clear=False after
    hiding the original anatomy with rendering-only visibility options.
    """
    def __init__(self, model, skin_tone=None):
        skin = np.asarray(skin_tone if skin_tone is not None
                          else [0.73, 0.50, 0.36, 1.0], dtype=float)
        if skin.shape == (3,):
            skin = np.r_[skin, 1.0]
        if skin.shape != (4,) or not np.isfinite(skin).all() or np.any(skin < 0) or np.any(skin > 1):
            raise ValueError("skin_tone must contain three or four color values in [0,1]")
        self.skin = skin.copy()
        self.visible = True
        self.last_geometry_count = 0
        joints = [f"{name}_{side}" for side in ("l", "r")
                  for name in ("hip_flexion", "knee_angle", "ankle_angle", "mtp_angle")]
        joints += [f"{side}_{name}" for side in ("l", "r")
                   for name in ("shoulder_flex", "elbow_flex", "wrist_flex")]
        self.joint_ids = {name: model.joint(name).id for name in joints}

    @staticmethod
    def point(data, body, local):
        state = data.body(body)
        return state.xpos + state.xmat.reshape(3, 3) @ np.asarray(local, dtype=float)

    def _joint(self, data, name):
        return data.xanchor[self.joint_ids[name]].copy()

    def _geom(self, scene, kind, size, position, rotation, color):
        if scene.ngeom >= scene.maxgeom:
            raise RuntimeError("Human avatar rendering scene is full")
        geom = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(geom, kind, np.asarray(size, dtype=float),
                           np.asarray(position, dtype=float),
                           np.asarray(rotation, dtype=float).reshape(9),
                           np.asarray(color, dtype=float))
        geom.specular = 0.04
        geom.shininess = 0.12
        scene.ngeom += 1
        return geom

    def _ellipsoid(self, scene, center, size, rotation, color):
        return self._geom(scene, mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                          size, center, rotation, color)

    def _line(self, scene, a, b, radius, color):
        geom = self._geom(scene, mujoco.mjtGeom.mjGEOM_CAPSULE,
                          [radius, 1, 0], np.zeros(3), np.eye(3), color)
        mujoco.mjv_connector(geom, mujoco.mjtGeom.mjGEOM_CAPSULE,
                            radius, np.asarray(a), np.asarray(b))
        return geom

    @staticmethod
    def _link_frame(a, b, forward):
        up = np.asarray(b) - np.asarray(a)
        up /= max(np.linalg.norm(up), 1e-12)
        front = np.asarray(forward) - up * np.dot(forward, up)
        if np.linalg.norm(front) < 1e-7:
            front = np.cross(up, [0.0, 1.0, 0.0])
        front /= max(np.linalg.norm(front), 1e-12)
        side = np.cross(front, up)
        return np.column_stack((front, up, side))

    def _limb(self, scene, a, b, forward, radius_front, radius_side, color):
        length = np.linalg.norm(b - a)
        frame = self._link_frame(a, b, forward)
        self._ellipsoid(scene, (a + b) * 0.5,
                        [radius_front, length * 0.55, radius_side], frame, color)

    def _local_ellipsoid(self, scene, data, body, center, size, color):
        return self._ellipsoid(scene, self.point(data, body, center), size,
                               data.body(body).xmat.reshape(3, 3), color)

    def _head(self, scene, data):
        # The historical empty head body has an unsuitable inertial xipos.
        # Its torso-relative geometric landmark is the reliable head center.
        rotation = data.body("torso").xmat.reshape(3, 3)
        center = self.point(data, "torso", [0.025, 0.54, 0.0])
        p = lambda local: center + rotation @ np.asarray(local)
        self._line(scene, self.point(data, "torso", [0.012, 0.385, 0.0]),
                   p([-0.005, -0.075, 0.0]), 0.043, self.skin)
        self._ellipsoid(scene, center, [0.080, 0.110, 0.073], rotation, self.skin)
        # Short hair cap and small ears soften the silhouette without adding a
        # glossy or exaggerated face.
        self._ellipsoid(scene, p([-0.055, 0.037, 0]),
                        [0.027, 0.068, 0.058], rotation, HAIR)
        self._ellipsoid(scene, p([-0.008, 0.077, 0]),
                        [0.063, 0.037, 0.060], rotation, HAIR)
        for side in (-1, 1):
            self._ellipsoid(scene, p([-0.004, -0.005, side * 0.073]),
                            [0.016, 0.025, 0.011], rotation, self.skin)
            z = side * 0.027
            self._ellipsoid(scene, p([0.074, 0.020, z]),
                            [0.0028, 0.0050, 0.0075], rotation,
                            [0.80, 0.79, 0.75, 1])
            self._ellipsoid(scene, p([0.077, 0.0195, z]),
                            [0.0023, 0.0031, 0.0031], rotation,
                            [0.105, 0.085, 0.070, 1])
            self._line(scene, p([0.072, 0.037, z - 0.009]),
                       p([0.072, 0.039, z + 0.009]), 0.0018, HAIR)
        self._ellipsoid(scene, p([0.081, -0.007, 0]),
                        [0.016, 0.020, 0.011], rotation, self.skin)
        mouth = [0.39, 0.235, 0.19, 1.0]
        self._line(scene, p([0.073, -0.044, -0.018]),
                   p([0.075, -0.047, 0]), 0.0014, mouth)
        self._line(scene, p([0.075, -0.047, 0]),
                   p([0.073, -0.044, 0.018]), 0.0014, mouth)

    def _arm(self, scene, data, side):
        shoulder = self._joint(data, f"{side}_shoulder_flex")
        elbow = self._joint(data, f"{side}_elbow_flex")
        wrist = self._joint(data, f"{side}_wrist_flex")
        forward = data.body("torso").xmat.reshape(3, 3)[:, 0]
        upper = elbow - shoulder
        self._line(scene, shoulder, elbow, 0.035, self.skin)
        self._limb(scene, shoulder, elbow, forward, 0.044, 0.042, self.skin)
        self._ellipsoid(scene, elbow, [0.033, 0.035, 0.033], np.eye(3), self.skin)
        self._line(scene, elbow, wrist, 0.025, self.skin)
        self._limb(scene, elbow, wrist, forward, 0.033, 0.032, self.skin)
        self._line(scene, shoulder, shoulder + upper * 0.29, 0.054, SHIRT)
        # Palm xipos is anatomically meaningful in this model; forearm/hand
        # body origins are not suitable endpoints for rendering the arms.
        hand = data.body(f"{side}_hand")
        palm = hand.xipos.copy()
        rotation = hand.xmat.reshape(3, 3)
        self._line(scene, wrist, palm, 0.025, self.skin)
        self._ellipsoid(scene, palm, [0.024, 0.053, 0.036], rotation, self.skin)
        for z, length in zip((-0.025, -0.008, 0.009, 0.025), (0.037, 0.049, 0.046, 0.034)):
            a = palm + rotation @ np.array([0.0, -0.025, z])
            b = palm + rotation @ np.array([0.0, -0.025 - length, z])
            self._line(scene, a, b, 0.007, self.skin)
        thumb_side = 1 if side == "l" else -1
        self._line(scene, palm + rotation @ np.array([0.0, 0.004, thumb_side * 0.025]),
                   palm + rotation @ np.array([0.015, -0.027, thumb_side * 0.049]),
                   0.010, self.skin)

    def _leg(self, scene, data, side):
        hip = self._joint(data, f"hip_flexion_{side}")
        knee = self._joint(data, f"knee_angle_{side}")
        ankle = self._joint(data, f"ankle_angle_{side}")
        femur = data.body(f"femur_{side}").xmat.reshape(3, 3)
        tibia = data.body(f"tibia_{side}").xmat.reshape(3, 3)
        self._line(scene, hip, knee, 0.049, self.skin)
        self._limb(scene, hip, knee, femur[:, 0], 0.069, 0.066, self.skin)
        self._ellipsoid(scene, knee, [0.050, 0.054, 0.050], tibia, self.skin)
        self._line(scene, knee, ankle, 0.033, self.skin)
        self._limb(scene, knee + (ankle - knee) * 0.10,
                   knee + (ankle - knee) * 0.80, tibia[:, 0], 0.050, 0.048, self.skin)
        self._ellipsoid(scene, ankle, [0.032, 0.041, 0.033], tibia, self.skin)
        # Short hems stay inside the wearable's upper cuff radius.
        self._limb(scene, hip - (knee - hip) * 0.10,
                   hip + (knee - hip) * 0.30, femur[:, 0], 0.074, 0.072, SHORTS)
        foot = f"calcn_{side}"
        self._local_ellipsoid(scene, data, foot, [0.090, -0.004, 0.0],
                              [0.135, 0.013, 0.055], SOLE)
        self._local_ellipsoid(scene, data, foot, [0.085, 0.024, 0.0],
                              [0.125, 0.041, 0.051], SHOE)
        self._line(scene, ankle, ankle - (ankle - knee) * 0.105,
                   0.035, [0.79, 0.80, 0.78, 1])
        for x in (0.055, 0.080, 0.105):
            self._line(scene, self.point(data, foot, [x, 0.061, -0.024]),
                       self.point(data, foot, [x, 0.061, 0.024]),
                       0.0018, [0.73, 0.75, 0.74, 1])

    def draw(self, scene, model, data, clear=False):
        if clear:
            scene.ngeom = 0
        start = scene.ngeom
        if not self.visible:
            self.last_geometry_count = 0
            return
        self._local_ellipsoid(scene, data, "pelvis", [-0.065, 0.008, 0],
                              [0.116, 0.113, 0.150], SHORTS)
        self._local_ellipsoid(scene, data, "torso", [0.016, 0.170, 0],
                              [0.113, 0.242, 0.161], SHIRT)
        # Upper sleeve joins bridge the chest to the actual shoulder anchors.
        for side, sign in (("l", -1), ("r", 1)):
            shoulder = self._joint(data, f"{side}_shoulder_flex")
            self._line(scene, self.point(data, "torso", [0.018, 0.345, sign * 0.115]),
                       shoulder, 0.058, SHIRT)
            self._arm(scene, data, side)
            self._leg(scene, data, side)
        self._head(scene, data)
        self.last_geometry_count = scene.ngeom - start
