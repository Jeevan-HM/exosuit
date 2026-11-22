"""Reduced device layer for the human-centered simulator. All inputs are PSI.

This is deliberately a joint-moment surrogate, not soft-body dynamics.
The new-RL controller emits one pressure value for two onset/duration bursts.
"""
from dataclasses import dataclass
import math
import numpy as np


@dataclass
class AssistanceConfig:
    stance_psi: float = 25.0
    swing_psi: float = 20.0
    torque_gain_nm_per_psi: float = 0.4
    maximum_torque_nm: float = 15.0
    direction: str = "extension"
    pressure_time_constant_s: float = 0.0
    command_rate_hz: float = 100.0

    def validate(self):
        for k,v in vars(self).items():
            if k=="direction":continue
            if not math.isfinite(float(v)) or float(v)<0:raise ValueError(f"{k} must be finite and nonnegative")
        if self.command_rate_hz<=0:raise ValueError("command_rate_hz must be positive")
        if self.direction not in ("extension","flexion"):raise ValueError("direction must be extension or flexion")


class KneeAssistance:
    def __init__(self,config=None):
        self.config=config or AssistanceConfig();self.config.validate()
        self.timings_s=np.array([.12,.20,.70,.15])
        self.enabled=False;self.reset()

    def reset(self):
        self.heel_strike_time=None;self.actual_psi=0.;self.command_psi=0.
        self.torque_nm=0.;self.next_command_time=0.

    def set_timings(self,seconds):
        x=np.asarray(seconds,dtype=float)
        if x.shape!=(4,) or not np.all(np.isfinite(x)) or np.any(x<0):
            raise ValueError("Expected [stance_onset, stance_duration, swing_onset, swing_duration] seconds")
        t1,d1,t2,d2=x
        if t1+d1>t2+1e-12:raise ValueError("Stance and swing assistance bursts overlap")
        self.timings_s=x.copy()

    def heel_strike(self,time_s):
        self.heel_strike_time=float(time_s);self.next_command_time=float(time_s)

    def advance(self,time_s,dt_s):
        if not math.isfinite(time_s) or not math.isfinite(dt_s) or dt_s<=0:
            raise ValueError("Simulation time and step must be finite, with dt > 0")
        c=self.config
        if time_s+1e-12>=self.next_command_time:
            self.command_psi=0.
            if self.enabled and self.heel_strike_time is not None:
                phase=time_s-self.heel_strike_time
                t1,d1,t2,d2=self.timings_s
                # Preserve pressure_commands_v3.py's source-ordered <= endpoints.
                if phase<=t1:pass
                elif phase<=t1+d1:self.command_psi=c.stance_psi
                elif phase<=t2:pass
                elif phase<=t2+d2:self.command_psi=c.swing_psi
            self.next_command_time=time_s+1/c.command_rate_hz
        if not self.enabled:self.command_psi=0.
        tau=c.pressure_time_constant_s
        self.actual_psi=(self.command_psi if tau==0 else self.actual_psi+(self.command_psi-self.actual_psi)*(-math.expm1(-dt_s/tau)))
        magnitude=min(c.maximum_torque_nm,c.torque_gain_nm_per_psi*self.actual_psi)
        self.torque_nm=magnitude*(-1 if c.direction=="extension" else 1)
        return self.torque_nm
