"""Forward muscle-driven human model, with a frozen published reflex controller.

The default matched historical pairing completes a 30-second unassisted
diagnostic. This is not a validated subject model. Fall detection is returned
directly and the simulation never silently resets. See VALIDATION.md.
"""
from pathlib import Path
import math
import tempfile
import numpy as np
from .vendor.reflex_interface import myoLeg_reflex

ROOT = Path(__file__).resolve().parent


class HumanBackend:
    """Positive angle and external torque mean knee flexion; all units are SI.

    ``step(duration_s, external_knee_torque_nm)`` is deterministic for the frozen
    controller. Pressure conversion belongs outside this class. VL and BF are
    explicit aliases for lumped vasti and hamstring groups, not isolated EMG.
    """
    def __init__(self, parameter_path=None, model_path=None, exosuit=None):
        self._device_model_dir=None
        self.device_mass_kg=0.;self.device_passive_damping=0.
        if exosuit and exosuit.get('enabled',True):
            from ..exosuit_mechanics import DeviceMechanics,write_augmented_model
            mechanics=DeviceMechanics(**exosuit.get('mechanics',{})).validate()
            if mechanics.side!='l':raise ValueError('The current exosuit controller and visuals use the left knee')
            self._device_model_dir=tempfile.TemporaryDirectory(prefix='knee_exosuit_')
            model_path=write_augmented_model(model_path or ROOT/'historical/human22_historical.xml',
                        Path(self._device_model_dir.name)/'human_with_exosuit.xml',mechanics)
            self.device_mass_kg=mechanics.thigh_mass_kg+mechanics.shank_mass_kg
            self.device_passive_damping=mechanics.passive_knee_damping_nm_s_per_rad
        self.parameter_path = Path(parameter_path or ROOT / "parameters/tutorial_prep.txt")
        raw = np.loadtxt(self.parameter_path)
        if raw.ndim != 1 or len(raw) not in (77, 81) or not np.isfinite(raw).all():
            raise ValueError("Expected a finite 77- or 81-element official reflex parameter vector")
        # The last four original parameters drive an ankle exoskeleton, and are
        # deliberately excluded when applying independent knee assistance here.
        self.params = raw[:77].copy()
        self.controller = myoLeg_reflex(
            control_params=self.params, msk_key="myolegs22", device_key="native_barefoot",
            exo_bool=False, delayed=False, init_pose="walk_left", sim_time=1e9,
            native_model_path=str(Path(model_path).resolve()) if model_path else None,
        )
        self.env = self.controller.env
        self.model = self.env.model
        self.data = self.env.data
        self.physics_dt_s = float(self.model.opt.timestep)
        self.human_control_dt_s = float(self.env.dt)
        self.reset()

    def reset(self, seed=0):
        # Official controller has no stochastic reset in this configuration.
        self.seed = int(seed)
        self.controller.reset(self.params.copy())
        self._remainder = 0.0
        self._fallen = False
        self._initial_x = float(self.data.body("pelvis").xpos[0])
        return self.sample()

    def step(self, duration_s, external_knee_torque_nm=0.0):
        if not math.isfinite(duration_s) or duration_s <= 0:
            raise ValueError("duration_s must be finite and positive")
        if not math.isfinite(external_knee_torque_nm):
            raise ValueError("external_knee_torque_nm must be finite")
        self.env.external_torque_nm = float(external_knee_torque_nm)
        self._remainder += float(duration_s)
        count = int((self._remainder + 1e-12) / self.env.dt)
        self._remainder -= count * self.env.dt
        for _ in range(count):
            if self._fallen:
                break
            self.controller.get_sensor_data()
            excitation = self.controller.reflex2mujoco(self.controller.update(self.controller.SENSOR_DATA))
            self.env.step(excitation)
            self.controller.update_footstep()
            self._fallen = self._is_fallen()
        return self.sample()

    def _is_fallen(self):
        height = float(self.data.body("pelvis").xpos[2])
        pitch = float(self.controller.get_intrinsic_EulerXYZ(self.data.body("pelvis").xquat)[1])
        return (not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all()
                or height < 0.65 or abs(pitch) > np.deg2rad(60))

    def _activation(self, muscle_name):
        actuator = self.model.actuator(muscle_name)
        address = int(self.model.actuator_actadr[actuator.id])
        return float(self.data.act[address])

    def sample(self):
        knee = self.data.joint("knee_angle_l")
        pelvis = self.data.body("pelvis")
        velocity = self.env.sim.data.object_velocity("pelvis", "body", local_frame=False)[0]
        left_load = sum(float(self.data.sensor(s).data[0]) for s in ("l_foot", "l_toes"))
        right_load = sum(float(self.data.sensor(s).data[0]) for s in ("r_foot", "r_toes"))
        vl = self._activation("vasti_l")
        rf = self._activation("rectfem_l")
        bf = self._activation("hamstrings_l")
        return {
            "time": float(self.data.time),
            "time_s": float(self.data.time),
            "knee_angle_rad": -float(knee.qpos[0]),
            "knee_velocity_rad_s": -float(knee.qvel[0]),
            "left_grf_n": left_load,
            "right_grf_n": right_load,
            "vl_activation": vl, "rf_activation": rf, "bf_activation": bf,
            "activation_vl_proxy": vl,
            "activation_rf_proxy": rf,
            "activation_bf_proxy": bf,
            "activation_aliases": {"VL": "left lumped vasti", "RF": "left rectus femoris", "BF": "left lumped hamstrings"},
            "pelvis_height_m": float(pelvis.xpos[2]),
            "pelvis_speed_m_s": float(velocity[0]),
            "forward_position_m": float(pelvis.xpos[0]),
            "forward_speed_m_s": float(velocity[0]),
            "distance_m": float(pelvis.xpos[0]) - self._initial_x,
            "fallen": bool(self._fallen),
            "muscle_excitation": self.data.ctrl.copy().tolist(),
            "muscle_activation": self.data.act.copy().tolist(),
            "all_activations": self.data.act.copy().tolist(),
            "physics_dt_s": self.physics_dt_s,
            "human_control_dt_s": self.human_control_dt_s,
            "body_mass_kg": float(self.model.body_mass.sum()),
            "device_mass_kg": self.device_mass_kg,
            "human_mass_kg": float(self.model.body_mass.sum())-self.device_mass_kg,
            "exosuit_passive_torque_nm": -self.device_passive_damping*(-float(knee.qvel[0])),
            "external_knee_torque_nm": float(self.env.external_torque_nm),
            "validation_status": "generic_forward_dynamics_not_subject_validated",
        }

    def close(self):
        if self._device_model_dir is not None:
            self._device_model_dir.cleanup();self._device_model_dir=None
