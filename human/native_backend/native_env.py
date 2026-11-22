"""Minimal native-MuJoCo API used by the vendored MyoAssist reflex interface.

The data shim implements the one DMControl helper the controller reads:
object_velocity returns [linear, angular], in that order. Joint/contact state,
muscle actuation, and integration are the actual native MuJoCo arrays.
"""
from pathlib import Path
from types import SimpleNamespace
import mujoco
import numpy as np

MODEL_PATH = Path(__file__).resolve().parent / "historical" / "human22_historical.xml"


def compose_env_model(*args, **kwargs):
    """Return the portable, precomposed barefoot human model path."""
    return str(kwargs.get("native_model_path") or MODEL_PATH)


class _Data:
    def __init__(self, model, data):
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name):
        return getattr(self._data, name)

    def __setattr__(self, name, value):
        # Assignment must copy: never alias the keyframe's qpos/qvel arrays.
        target = getattr(self._data, name)
        if isinstance(target, np.ndarray):
            target[...] = value
        else:
            setattr(self._data, name, value)

    def object_velocity(self, name, objtype, local_frame=False):
        kinds = {"body": mujoco.mjtObj.mjOBJ_BODY, "site": mujoco.mjtObj.mjOBJ_SITE}
        kind = kinds[objtype]
        object_id = mujoco.mj_name2id(self._model, kind, name)
        if object_id < 0:
            raise KeyError(name)
        velocity = np.zeros(6)
        mujoco.mj_objectVelocity(self._model, self._data, kind, object_id, velocity, int(local_frame))
        return np.stack((velocity[3:], velocity[:3]))


class ReflexEnvV0:
    """Barefoot forward dynamics, without Gym or MyoSuite framework imports."""
    def __init__(self, model_path, frame_skip=10, seed=0, **kwargs):
        self.model = mujoco.MjModel.from_xml_path(model_path)
        self.data = mujoco.MjData(self.model)
        self.frame_skip = frame_skip
        self.sim = SimpleNamespace(model=self.model, data=_Data(self.model, self.data), forward=self.forward)
        self.external_dof = int(self.model.joint("knee_angle_l").dofadr[0])
        self.external_torque_nm = 0.0

    @property
    def dt(self):
        return self.model.opt.timestep * self.frame_skip

    def reset(self):
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        self.external_torque_nm = 0.0
        self.forward()

    def forward(self):
        mujoco.mj_forward(self.model, self.data)

    def step(self, excitation):
        self.data.ctrl[:] = np.clip(excitation, 0.0, 1.0)
        for _ in range(self.frame_skip):
            self.data.qfrc_applied[:] = 0.0
            # The model uses negative knee flexion. Public API uses positive
            # flexion torque, so reverse sign at the native DOF boundary.
            self.data.qfrc_applied[self.external_dof] = -self.external_torque_nm
            mujoco.mj_step(self.model, self.data)

