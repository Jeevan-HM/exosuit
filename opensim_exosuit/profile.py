"""Hardware-free, nominal pressure schedule for an OpenSim knee-torque demo.

Heel strikes here are scheduled illustrative inputs, not detected gait events.
Both legacy bursts drive the same selected bank: ``swing_psi`` does not imply a
second physical flexion channel. The pressure dynamics and linear torque gain
are simulation assumptions, not calibrated hardware or clinical parameters.
Passive damping is zero here; the OpenSim model owns its joint damping.
"""

import csv
import math
from collections.abc import Mapping
from pathlib import Path

from .pneumatic import BankParameters, PneumaticExosuit, PneumaticExosuitConfig


FIELDS = (
    "time_s",
    "extension_command_psi",
    "flexion_command_psi",
    "extension_pressure_psi",
    "flexion_pressure_psi",
    "torque_flexion_positive_nm",
)


def _number(value, name, *, positive=False):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if isinstance(value, bool) or not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    if positive and result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _section(value, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a dictionary")
    return value


def _sample(device, time_s):
    telemetry = device.telemetry()
    return {
        "time_s": time_s,
        "extension_command_psi": telemetry["extension_command_psi"],
        "flexion_command_psi": telemetry["flexion_command_psi"],
        "extension_pressure_psi": telemetry["extension_pressure_psi"],
        "flexion_pressure_psi": telemetry["flexion_pressure_psi"],
        "torque_flexion_positive_nm": telemetry["net_torque_nm"],
    }


def build_profile(config: dict, duration_s: float = 2.4, dt_s: float = 0.01) -> list[dict]:
    """Sample assumed pressure dynamics without importing OpenSim.

    The first row is the zero-pressure initial state. Every subsequent row's
    pressure and torque are the state *at* ``time_s``, after advancing from the
    previous row. Command columns contain the most recently sampled command
    used by ``PneumaticExosuit.advance``; a command change at an interval's end
    is applied when the next interval starts. Command samples retain the
    existing legacy strict-onset/inclusive-end timing behavior.

    Rows include the requested sample grid, the exact final time, and every
    nominal heel strike. A heel strike restarts the command schedule without
    erasing pressure: finite exhaust dynamics can leave residual torque.
    """
    config = _section(config, "config")
    assistance = _section(config.get("assistance", {}), "assistance")
    exosuit = _section(config.get("exosuit", {}), "exosuit")
    pneumatics = _section(exosuit.get("pneumatics", {}), "exosuit.pneumatics")
    schedule = _section(config.get("schedule", {}), "schedule")
    duration = _number(duration_s, "duration_s", positive=True)
    dt = _number(dt_s, "dt_s", positive=True)
    stride = _number(schedule.get("stride_duration_s", 1.2),
                     "schedule.stride_duration_s", positive=True)
    if not math.isfinite(duration / min(dt, stride)):
        raise ValueError("Requested sample count exceeds finite clock resolution")

    defaults = PneumaticExosuitConfig()
    bank_defaults = BankParameters()
    bank_values = {
        "gain_nm_per_psi": _number(assistance.get("torque_gain_nm_per_psi",
                                                 bank_defaults.gain_nm_per_psi),
                                   "assistance.torque_gain_nm_per_psi"),
        "max_pressure_psi": _number(pneumatics.get("max_pressure_psi",
                                                  bank_defaults.max_pressure_psi),
                                    "exosuit.pneumatics.max_pressure_psi"),
        "rise_tau_s": _number(pneumatics.get("rise_time_constant_s", bank_defaults.rise_tau_s),
                              "exosuit.pneumatics.rise_time_constant_s"),
        "exhaust_tau_s": _number(pneumatics.get("exhaust_time_constant_s",
                                               bank_defaults.exhaust_tau_s),
                                 "exosuit.pneumatics.exhaust_time_constant_s"),
        "maximum_torque_nm": _number(assistance.get("maximum_torque_nm",
                                                   defaults.maximum_net_torque_nm),
                                     "assistance.maximum_torque_nm"),
    }
    direction = assistance.get("direction", defaults.legacy_bank)
    device = PneumaticExosuit(PneumaticExosuitConfig(
        stance_psi=_number(assistance.get("stance_psi", defaults.stance_psi),
                           "assistance.stance_psi"),
        swing_psi=_number(assistance.get("swing_psi", defaults.swing_psi),
                          "assistance.swing_psi"),
        legacy_bank=direction,
        command_rate_hz=_number(assistance.get("command_rate_hz", defaults.command_rate_hz),
                                "assistance.command_rate_hz", positive=True),
        maximum_net_torque_nm=bank_values["maximum_torque_nm"],
        passive_damping_nm_s_per_rad=0.0,
        extension=BankParameters(**bank_values),
        flexion=BankParameters(**bank_values),
    ))
    timing_input = schedule.get("timings_s", device.timings_s)
    if isinstance(timing_input, (str, bytes, Mapping)):
        raise ValueError("schedule.timings_s must contain four nonnegative numbers")
    try:
        timings = tuple(_number(value, "schedule.timings_s") for value in timing_input)
    except TypeError as exc:
        raise ValueError("schedule.timings_s must contain four nonnegative numbers") from exc
    device.set_timings(timings)
    timing_end = max(timings[0] + timings[1], timings[2] + timings[3])
    if timing_end > stride + 8 * math.ulp(stride):
        raise ValueError("Assistance timing windows must end within the stride")
    for flag_name, flag in (("device_enabled", config.get("device_enabled", True)),
                            ("exosuit.enabled", exosuit.get("enabled", True))):
        if not isinstance(flag, bool):
            raise ValueError(f"{flag_name} must be a boolean")
    device.enabled = config.get("device_enabled", True) and exosuit.get("enabled", True)
    device.heel_strike(0.0)

    rows = [_sample(device, 0.0)]
    cursor = 0.0
    sample_index = heel_index = command_index = 1
    command_rate = device.config.command_rate_hz
    # Grid values are multiplied from integer indices rather than accumulated.
    # Canonical command ticks also keep the legacy inclusive endpoints stable
    # when output sampling changes. The existing device owns pressure dynamics.
    # Heel strikes are separate integration boundaries, even when dt > stride.
    while cursor < duration:
        sample_time = sample_index * dt
        heel_time = heel_index * stride
        command_time = (heel_index - 1) * stride + command_index / command_rate
        end = min(sample_time, heel_time, command_time, duration)
        tolerance = 8 * math.ulp(end)
        at_sample = abs(end - sample_time) <= tolerance
        at_heel = abs(end - heel_time) <= tolerance
        at_command = abs(end - command_time) <= tolerance
        at_end = abs(end - duration) <= tolerance
        if at_heel:
            end = heel_time
        if at_end:
            end = duration
        if end <= cursor:
            raise ValueError("Requested sample period is below simulation clock resolution")
        device.advance(cursor, end - cursor)
        cursor = end
        if at_heel:
            device.heel_strike(end)
            heel_index += 1
            command_index = 1
        elif at_command:
            # advance() samples at the next interval's start. Fix that boundary
            # to the same integer-derived tick irrespective of the sample grid.
            device.next_command_time = end
            command_index += 1
        if at_sample:
            sample_index += 1
        if at_sample or at_heel or at_end:
            rows.append(_sample(device, end))
    return rows


def export_csv(path, rows):
    """Write sampled gauge PSI and flexion-positive torque to a UTF-8 CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
