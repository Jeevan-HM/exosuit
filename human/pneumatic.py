"""Reduced pneumatic knee exosuit: two pressure banks, joint torque and work.

PSI values are gauge pressure throughout. Legacy timing is the single-channel
25 PSI stance / 20 PSI swing protocol in new-RL/pressure_commands_v3.py:234-250;
both bursts route to ONE explicitly selected bank. Independent manual banks
are a separate simulation mode, not a claim about the legacy hardware wiring.

Pressure rise/exhaust time constants and pressure-to-torque gains are assumed
until measured. This is a pressure-state/joint-moment surrogate, not chamber
FEM, a thermodynamic gas model, validated soft-actuator deformation, or a
hardware driver. Joint work uses the caller's actual simulated knee velocity;
it is not compressor energy or metabolic expenditure. No mass is inferred.
"""

from dataclasses import dataclass, field
import math
from typing import Optional, Tuple


def _finite(value, name, minimum=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return value


@dataclass
class BankParameters:
    gain_nm_per_psi: float = 0.4
    max_pressure_psi: float = 30.0
    rise_tau_s: float = 0.08
    exhaust_tau_s: float = 0.12
    deadband_psi: float = 0.0
    maximum_torque_nm: float = 15.0
    torque_curve_psi_nm: Optional[Tuple[Tuple[float, float], ...]] = None

    def validate(self):
        for name in ("gain_nm_per_psi", "max_pressure_psi", "rise_tau_s",
                     "exhaust_tau_s", "deadband_psi", "maximum_torque_nm"):
            _finite(getattr(self, name), name)
        if self.torque_curve_psi_nm is not None:
            curve = self.torque_curve_psi_nm
            if len(curve) < 2:
                raise ValueError("Torque curve needs at least two pressure/torque points")
            previous = -1.0
            for point in curve:
                if len(point) != 2:
                    raise ValueError("Torque curve points must be [gauge PSI, torque magnitude Nm]")
                pressure = _finite(point[0], "torque curve pressure")
                _finite(point[1], "torque curve torque")
                if pressure <= previous:
                    raise ValueError("Torque curve pressures must strictly increase")
                previous = pressure
            if float(curve[0][0]) != 0 or float(curve[0][1]) != 0:
                raise ValueError("Torque curve must start at [0 PSI, 0 Nm]")
            if self.max_pressure_psi > float(curve[-1][0]):
                raise ValueError("max_pressure_psi exceeds torque-curve range; extrapolation is forbidden")
            if self.deadband_psi != 0:
                raise ValueError("A measured torque curve already includes its deadband; set deadband_psi=0")
        return self


@dataclass
class PneumaticExosuitConfig:
    stance_psi: float = 25.0
    swing_psi: float = 20.0
    legacy_bank: str = "extension"
    command_rate_hz: float = 100.0
    maximum_net_torque_nm: float = 15.0
    passive_damping_nm_s_per_rad: float = 0.0
    extension: BankParameters = field(default_factory=BankParameters)
    flexion: BankParameters = field(default_factory=BankParameters)

    def validate(self):
        for name in ("stance_psi", "swing_psi", "maximum_net_torque_nm",
                     "passive_damping_nm_s_per_rad"):
            _finite(getattr(self, name), name)
        if _finite(self.command_rate_hz, "command_rate_hz") <= 0:
            raise ValueError("command_rate_hz must be > 0")
        if self.legacy_bank not in ("extension", "flexion"):
            raise ValueError("legacy_bank must be extension or flexion")
        for name in ("extension", "flexion"):
            value = getattr(self, name)
            if isinstance(value, dict):
                value = BankParameters(**value)
                setattr(self, name, value)
            if not isinstance(value, BankParameters):
                raise ValueError(f"{name} must be BankParameters or a parameter dictionary")
            value.validate()
        return self


def _clip(value, maximum):
    return max(-maximum, min(maximum, value))


def _magnitude(pressure, parameters):
    """Torque lookup never evaluates outside supplied calibration range."""
    if parameters.torque_curve_psi_nm is None:
        raw = parameters.gain_nm_per_psi * max(0.0, pressure - parameters.deadband_psi)
    else:
        curve = parameters.torque_curve_psi_nm
        if pressure > float(curve[-1][0]) + 1e-10:
            raise ValueError("Pressure outside torque-curve range; extrapolation is forbidden")
        raw = float(curve[-1][1])
        for (p0, t0), (p1, t1) in zip(curve[:-1], curve[1:]):
            if pressure <= p1:
                raw = t0 + (pressure - p0) * (t1 - t0) / (p1 - p0)
                break
    return min(raw, parameters.maximum_torque_nm), raw > parameters.maximum_torque_nm


class PneumaticExosuit:
    """Two independent gauge-pressure states with flexion-positive net torque.

    ``advance(time_s, dt_s, knee_angle_rad, knee_velocity_rad_s)`` advances the
    device over that interval, returning its ending joint torque. The human
    integrator applies that sampled torque. The current knee velocity must be
    supplied for meaningful power/work: zero is only a compatibility default.
    Commands are sampled internally at command_rate_hz even for larger steps.
    Pressure integration is exact first order between command updates. Work is
    integrated by trapezoids between those updates using the supplied velocity
    held over this one human-control step; no prescribed gait is introduced.

    Disabling commands both banks to vent; finite exhaust time can leave a
    decaying residual torque. reset() initializes both banks at zero pressure.
    Scalar command_psi/actual_psi compatibility aliases refer to legacy_bank;
    telemetry() must be used to inspect both banks in manual mode.
    """

    def __init__(self, config=None):
        if isinstance(config, dict):
            config = PneumaticExosuitConfig(**config)
        self.config = (config or PneumaticExosuitConfig()).validate()
        self.timings_s = (0.12, 0.20, 0.70, 0.15)
        self.enabled = False
        self.reset()

    def reset(self):
        self.mode = "legacy"
        self.heel_strike_time = None
        self.next_command_time = 0.0
        self._last_end_time = None
        self._manual = {"extension": 0.0, "flexion": 0.0}
        self._requested = {"extension": 0.0, "flexion": 0.0}
        self._command = {"extension": 0.0, "flexion": 0.0}
        self._pressure = {"extension": 0.0, "flexion": 0.0}
        self._pressure_saturated = {"extension": False, "flexion": False}
        self._bank_torque_saturated = {"extension": False, "flexion": False}
        self.extension_torque_nm = self.flexion_torque_nm = 0.0
        self.active_torque_nm = self.passive_torque_nm = self.torque_nm = 0.0
        self.power_w = self.active_power_w = self.passive_power_w = 0.0
        self.net_work_j = self.positive_work_j = self.negative_work_j = 0.0
        self.active_work_j = self.passive_dissipated_energy_j = 0.0
        self.torque_saturated = False
        self.knee_angle_rad = self.knee_velocity_rad_s = 0.0

    @property
    def command_psi(self):
        return self._command[self.config.legacy_bank]

    @property
    def actual_psi(self):
        return self._pressure[self.config.legacy_bank]

    def set_timings(self, seconds):
        try:
            values = tuple(_finite(value, "timing") for value in seconds)
        except TypeError as exc:
            raise ValueError("Timings must be [stance onset,duration,swing onset,duration]") from exc
        if len(values) != 4:
            raise ValueError("Timings must have exactly four elements")
        t1, d1, t2, _ = values
        if t1 + d1 > t2 + 1e-12:
            raise ValueError("Stance and swing pressure windows overlap")
        self.timings_s = values

    def set_manual_pressures(self, extension_psi=0.0, flexion_psi=0.0):
        self._manual = {"extension": _finite(extension_psi, "extension_psi"),
                        "flexion": _finite(flexion_psi, "flexion_psi")}
        self.mode = "manual"
        self.next_command_time = 0.0  # Apply changed command at the next advance.

    def set_legacy_mode(self, bank=None):
        if bank is not None:
            if bank not in ("extension", "flexion"):
                raise ValueError("bank must be extension or flexion")
            self.config.legacy_bank = bank
        self.mode = "legacy"
        self.next_command_time = 0.0

    def heel_strike(self, time_s):
        self.heel_strike_time = _finite(time_s, "heelstrike time")
        self.next_command_time = self.heel_strike_time

    def _sample_commands(self, time_s):
        requested = {"extension": 0.0, "flexion": 0.0}
        if self.enabled:
            if self.mode == "manual":
                requested = self._manual.copy()
            elif self.heel_strike_time is not None:
                phase = time_s - self.heel_strike_time
                t1, d1, t2, d2 = self.timings_s
                pressure = 0.0
                if phase <= t1:
                    pass
                elif phase <= t1 + d1:
                    pressure = self.config.stance_psi
                elif phase <= t2:
                    pass
                elif phase <= t2 + d2:
                    pressure = self.config.swing_psi
                requested[self.config.legacy_bank] = pressure
        self._requested = requested
        for bank in requested:
            maximum = getattr(self.config, bank).max_pressure_psi
            self._command[bank] = min(requested[bank], maximum)
            self._pressure_saturated[bank] = requested[bank] > maximum

    def _update_torque(self, velocity):
        extension, ext_sat = _magnitude(self._pressure["extension"], self.config.extension)
        flexion, flex_sat = _magnitude(self._pressure["flexion"], self.config.flexion)
        self._bank_torque_saturated = {"extension": ext_sat, "flexion": flex_sat}
        active = flexion - extension
        passive = -self.config.passive_damping_nm_s_per_rad * velocity
        desired = active + passive
        cap = self.config.maximum_net_torque_nm
        clipped = _clip(desired, cap)
        self.torque_saturated = abs(desired) > cap
        # Scale both contributions consistently if the total joint torque caps.
        scale = clipped / desired if self.torque_saturated else 1.0
        self.extension_torque_nm, self.flexion_torque_nm = -extension * scale, flexion * scale
        self.active_torque_nm = active * scale
        self.passive_torque_nm = passive * scale
        self.torque_nm = self.active_torque_nm + self.passive_torque_nm
        self.active_power_w = self.active_torque_nm * velocity
        self.passive_power_w = self.passive_torque_nm * velocity
        self.power_w = self.torque_nm * velocity

    def _integrate_work(self, previous_power, previous_active, previous_passive, dt):
        p0, p1 = previous_power, self.power_w
        signed = .5 * (p0 + p1) * dt
        if p0 >= 0 and p1 >= 0:
            positive, negative = signed, 0.0
        elif p0 <= 0 and p1 <= 0:
            positive, negative = 0.0, -signed
        else:
            fraction = abs(p0) / (abs(p0) + abs(p1))
            area0, area1 = .5 * abs(p0) * fraction * dt, .5 * abs(p1) * (1 - fraction) * dt
            positive, negative = (area0, area1) if p0 > 0 else (area1, area0)
        self.net_work_j += signed
        self.positive_work_j += positive
        self.negative_work_j += negative
        self.active_work_j += .5 * (previous_active + self.active_power_w) * dt
        self.passive_dissipated_energy_j -= .5 * (previous_passive + self.passive_power_w) * dt

    def advance(self, time_s, dt_s, knee_angle_rad=0.0, knee_velocity_rad_s=0.0):
        time_s = _finite(time_s, "time_s")
        dt_s = _finite(dt_s, "dt_s")
        if dt_s <= 0:
            raise ValueError("dt_s must be > 0")
        angle = float(knee_angle_rad)
        velocity = float(knee_velocity_rad_s)
        if not math.isfinite(angle) or not math.isfinite(velocity):
            raise ValueError("Knee angle and velocity must be finite")
        if self._last_end_time is not None and time_s < self._last_end_time - 1e-10:
            raise ValueError("Device time moved backward or intervals overlap; reset before replay")
        self.knee_angle_rad, self.knee_velocity_rad_s = angle, velocity
        cursor, end = time_s, time_s + dt_s
        if not math.isfinite(end) or end <= time_s:
            raise ValueError("Requested interval exceeds finite clock resolution")
        if dt_s * self.config.command_rate_hz > 100000:
            raise ValueError("Advance in smaller intervals (at most 100000 command updates per call)")
        while cursor < end - 1e-12:
            if cursor + 1e-12 >= self.next_command_time:
                self._sample_commands(cursor)
                self.next_command_time = cursor + 1.0 / self.config.command_rate_hz
            span = min(end, self.next_command_time) - cursor
            if span <= 0:
                raise ValueError("Command period is below simulation clock resolution")
            # A zero time constant is an instantaneous jump at this boundary,
            # rather than an artificial half-step ramp in work integration.
            for bank in ("extension", "flexion"):
                parameters = getattr(self.config, bank)
                target, current = self._command[bank], self._pressure[bank]
                tau = parameters.rise_tau_s if target >= current else parameters.exhaust_tau_s
                if tau == 0:
                    self._pressure[bank] = target
            self._update_torque(velocity)
            before = (self.power_w, self.active_power_w, self.passive_power_w)
            for bank in ("extension", "flexion"):
                parameters = getattr(self.config, bank)
                target, current = self._command[bank], self._pressure[bank]
                tau = parameters.rise_tau_s if target >= current else parameters.exhaust_tau_s
                pressure = target if tau == 0 else current + (target - current) * (-math.expm1(-span / tau))
                self._pressure[bank] = max(0.0, min(parameters.max_pressure_psi, pressure))
            self._update_torque(velocity)
            self._integrate_work(*before, span)
            cursor += span
        self._last_end_time = end
        return self.torque_nm

    def telemetry(self):
        """JSON-compatible samples; torque and work are mechanical joint values."""
        result = {
            "mode": self.mode, "enabled": bool(self.enabled),
            "legacy_bank": self.config.legacy_bank,
            "knee_angle_rad": self.knee_angle_rad,
            "knee_velocity_rad_s": self.knee_velocity_rad_s,
            "active_torque_nm": self.active_torque_nm,
            "passive_torque_nm": self.passive_torque_nm,
            "net_torque_nm": self.torque_nm,
            "torque_saturated": self.torque_saturated,
            "joint_power_w": self.power_w,
            "active_joint_power_w": self.active_power_w,
            "passive_joint_power_w": self.passive_power_w,
            "net_joint_work_j": self.net_work_j,
            "positive_joint_work_j": self.positive_work_j,
            "negative_joint_work_j": self.negative_work_j,
            "active_joint_work_j": self.active_work_j,
            "passive_dissipated_energy_j": self.passive_dissipated_energy_j,
            "parameter_status": "uncalibrated pressure-state/joint-moment surrogate; optional supplied torque curves",
            "energy_semantics": "sampled joint mechanical work; not pneumatic input energy or metabolic cost",
        }
        for bank in ("extension", "flexion"):
            parameters = getattr(self.config, bank)
            result.update({
                f"{bank}_requested_psi": self._requested[bank],
                f"{bank}_command_psi": self._command[bank],
                f"{bank}_pressure_psi": self._pressure[bank],
                f"{bank}_pressure_saturated": self._pressure_saturated[bank],
                f"{bank}_torque_nm": getattr(self, f"{bank}_torque_nm"),
                f"{bank}_torque_saturated": self._bank_torque_saturated[bank],
                f"{bank}_torque_model": "supplied_pressure_curve" if parameters.torque_curve_psi_nm is not None else "assumed_linear_gain",
            })
        return result
