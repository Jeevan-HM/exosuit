"""OpenSim suit assembly assumptions, independent of other simulator runtimes."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DeviceMechanics:
    thigh_mass_kg: float = 0.25
    shank_mass_kg: float = 0.20
    thigh_cuff_radius_m: float = 0.075
    shank_cuff_radius_m: float = 0.060
    thigh_assembly_length_m: float = 0.22
    shank_assembly_length_m: float = 0.22
    thigh_center_distal_m: float = 0.22
    shank_center_distal_m: float = 0.18
    passive_knee_damping_nm_s_per_rad: float = 0.03
    side: str = "l"

    def validate(self):
        if self.side not in ("l", "r"):
            raise ValueError("Device side must be l or r")
        for name, value in vars(self).items():
            if name != "side" and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")
        for name in ("thigh_cuff_radius_m", "shank_cuff_radius_m",
                     "thigh_assembly_length_m", "shank_assembly_length_m"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("thigh_center_distal_m", "shank_center_distal_m"):
            if getattr(self, name) > 0.4:
                raise ValueError(f"{name} exceeds the modeled limb length")
        return self
