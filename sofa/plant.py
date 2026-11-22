"""Pressure dynamics and applied torques; SOFA integrates the knee state."""
import bisect
import copy
import json
import math
from pathlib import Path
from control import PressureController, heuristic_timings, validate_timings
from units import PA_PER_PSI, clamp, finite, psi_to_pa

BASE = Path(__file__).resolve().parent


def load_config(path=None):
    path = Path(path) if path else BASE / "config.json"
    c = json.loads(path.read_text())
    validate_config(c)
    return c


def validate_config(c):
    if c.get("schema_version") != 1:
        raise ValueError("Unsupported configuration schema")
    positive = ("dt_s", "command_rate_hz", "max_pressure_psi", "mass_kg", "length_m",
                "fill_time_constant_s", "vent_time_constant_s", "tracking_period_s")
    for k in positive:
        if finite(c[k], k) <= 0:
            raise ValueError(f"{k} must be positive")
    if c["dt_s"] > 1 / c["command_rate_hz"] + 1e-12:
        raise ValueError("SOFA dt must be no larger than the command sample period")
    if set(c["channel_map"]) != {"flexion", "extension"} or len(c["channel_map"]) != 2:
        raise ValueError("channel_map must contain flexion and extension exactly once")
    if c["mode"] not in ("timed", "manual", "replay") or c["profile"] not in ("rl", "heuristic"):
        raise ValueError("Unknown mode/profile")
    for k in ("pressure_amplitude_psi", "torque_scale", "assumed_gain_nm_per_psi",
              "damping_nm_s_per_rad", "passive_stiffness_nm_per_rad", "gravity_m_s2",
              "wearer_torque_limit_nm", "tracking_kp_nm_per_rad", "tracking_kd_nm_s_per_rad"):
        if finite(c[k], k) < 0:
            raise ValueError(f"{k} cannot be negative")
    for v in [c["pressure_amplitude_psi"], *c["manual_pressure_psi"]]:
        if not 0 <= finite(v) <= c["max_pressure_psi"]:
            raise ValueError("Requested PSI is outside the configured simulation pressure range")
    if len(c["manual_pressure_psi"]) != 2:
        raise ValueError("Exactly two manual channel pressures are required")
    if not 0 <= finite(c["min_angle_deg"]) <= finite(c["initial_angle_deg"]) <= finite(c["max_angle_deg"]) <= 120:
        raise ValueError("Angles must satisfy 0 <= min <= initial <= max <= 120 degrees")
    validate_timings(c["timings_s"], c["cycle_duration_s"])
    heuristic_timings(c["heuristic_percent"], c["heuristic_duration_s"])
    if c["torque_model"] not in ("measured_pair", "assumed"):
        raise ValueError("Choose measured_pair or assumed torque model")
    return c


def bracket(axis, value):
    value = clamp(value, axis[0], axis[-1])
    i = max(0, min(len(axis) - 2, bisect.bisect_right(axis, value) - 1))
    return i, (value - axis[i]) / (axis[i + 1] - axis[i])


class TorqueTable:
    def __init__(self, path):
        self.data = json.loads(Path(path).read_text())
        if self.data.get("pressure_unit") != "psi" or self.data.get("torque_unit") != "N m":
            raise ValueError("Calibration must use PSI and N m")
        self.angles = self.data["angles_deg"]
        self.pressures = self.data["pressures_psi"]
        for axis in (self.angles, self.pressures):
            if len(axis) < 2 or any(finite(a) >= finite(b) for a, b in zip(axis, axis[1:])):
                raise ValueError("Calibration axes must be finite and strictly increasing")
        for bank in ("flexion", "extension"):
            grid = self.data[bank]["mean_nm"]
            if len(grid) != len(self.angles) or any(len(row) != len(self.pressures) for row in grid):
                raise ValueError("Invalid calibration grid shape")
            for row in grid:
                if any(finite(v) < 0 for v in row):
                    raise ValueError("Torque magnitudes must be finite and nonnegative")

    def torque(self, bank, angle_deg, pressure_psi):
        i, u = bracket(self.angles, finite(angle_deg))
        j, v = bracket(self.pressures, finite(pressure_psi))
        g = self.data[bank]["mean_nm"]
        return ((1-u) * ((1-v)*g[i][j] + v*g[i][j+1])
                + u * ((1-v)*g[i+1][j] + v*g[i+1][j+1]))


class ExosuitPlant:
    def __init__(self, config, base=BASE):
        self.cfg = copy.deepcopy(validate_config(config))
        self.base = Path(base)
        self.controller = PressureController(self.cfg, self.base)
        self.table = (TorqueTable(self.base / self.cfg["calibration_file"])
                      if self.cfg["torque_model"] == "measured_pair" else None)
        if self.table:
            if (self.cfg["min_angle_deg"] < self.table.angles[0]
                    or self.cfg["max_angle_deg"] > self.table.angles[-1]
                    or self.cfg["max_pressure_psi"] > self.table.pressures[-1]):
                raise ValueError("Measured mode must stay inside the calibration angle/pressure domain")
        self.inertia = self.cfg["mass_kg"] * self.cfg["length_m"]**2 / 3
        self.reset()

    def reset(self):
        self.pressure = [0.0, 0.0]
        self.command = (0.0, 0.0)
        self.next_command_time = 0.0
        self.controller.phase_origin = 0.0

    def applied_torque(self, time_s, angle_rad, velocity_rad_s, dt):
        """Evaluate at SOFA's current q,qdot; no position integration here."""
        c = self.cfg
        time_s, angle_rad, velocity_rad_s, dt = map(finite, (time_s, angle_rad, velocity_rad_s, dt))
        if not 0 < dt <= 1/c["command_rate_hz"] + 1e-12:
            raise ValueError("Invalid pressure integration time step")
        if time_s + 1e-12 >= self.next_command_time:
            self.command = self.controller.command(time_s)
            self.next_command_time = (math.floor((time_s + 1e-10)*c["command_rate_hz"]) + 1)/c["command_rate_hz"]
        # Disable takes effect immediately, with the chamber pressure then decaying.
        if not c["actuation_enabled"]:
            self.command = (0.0, 0.0)
        for i, desired in enumerate(self.command):
            tau = c["fill_time_constant_s"] if desired > self.pressure[i] else c["vent_time_constant_s"]
            self.pressure[i] += (desired - self.pressure[i]) * (1 - math.exp(-dt/tau))
        banks = dict(zip(c["channel_map"], self.pressure))
        angle_deg = math.degrees(angle_rad)
        if self.table:
            tf = self.table.torque("flexion", angle_deg, banks["flexion"])
            te = self.table.torque("extension", angle_deg, banks["extension"])
        else:
            ratio = clamp(angle_deg / 120, 0, 1)
            gain = c["assumed_gain_nm_per_psi"]
            tf = gain * (1 - 0.75*ratio) * banks["flexion"]
            te = gain * (0.35 + 0.65*ratio) * banks["extension"]
        robot = (tf - te) * c["torque_scale"]
        gravity = c["mass_kg"] * c["gravity_m_s2"] * c["length_m"] / 2 * math.cos(angle_rad)
        passive = -c["damping_nm_s_per_rad"]*velocity_rad_s - c["passive_stiffness_nm_per_rad"]*angle_rad
        human, target = 0.0, None
        if c["wearer_tracking"]:
            w = 2*math.pi/c["tracking_period_s"]
            lo, hi = max(10,c["min_angle_deg"]), min(85,c["max_angle_deg"])
            mid, amp = math.radians((lo+hi)/2), math.radians((hi-lo)/2)
            qref = mid - amp*math.cos(w*time_s)
            vref, aref = amp*w*math.sin(w*time_s), amp*w*w*math.cos(w*time_s)
            human = clamp(self.inertia*aref - gravity - passive
                          + c["tracking_kp_nm_per_rad"]*(qref-angle_rad)
                          + c["tracking_kd_nm_s_per_rad"]*(vref-velocity_rad_s),
                          -c["wearer_torque_limit_nm"], c["wearer_torque_limit_nm"])
            target = math.degrees(qref)
        return {"time_s": time_s, "angle_deg": angle_deg,
                "velocity_deg_s": math.degrees(velocity_rad_s), "target_deg": target,
                "p0_command_psi": self.command[0], "p1_command_psi": self.command[1],
                "p0_psi": self.pressure[0], "p1_psi": self.pressure[1],
                "p0_pa": psi_to_pa(self.pressure[0]), "p1_pa": psi_to_pa(self.pressure[1]),
                "flexion_psi": banks["flexion"], "extension_psi": banks["extension"],
                "suit_torque_nm": robot, "human_torque_nm": human,
                "gravity_torque_nm": gravity, "passive_torque_nm": passive,
                "net_torque_nm": robot + human + gravity + passive}

    def project_limits(self, q, v):
        lo, hi = map(math.radians, (self.cfg["min_angle_deg"], self.cfg["max_angle_deg"]))
        if q < lo:
            return lo, max(v, 0.0)
        if q > hi:
            return hi, min(v, 0.0)
        return q, v
