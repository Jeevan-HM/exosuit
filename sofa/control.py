"""Pure pressure scheduling extracted from the supplied control scripts.

No source_reference module is imported: those programs start experiment I/O.
"""
from bisect import bisect_right
import csv
from pathlib import Path
from units import clamp, finite

RL_ACTION_RANGES = ((0.05, 0.20), (0.21, 0.41), (0.50, 0.70), (0.90, 1.00))


def validate_timings(values, duration):
    duration = finite(duration, "cycle duration")
    if duration <= 0 or len(values) != 4:
        raise ValueError("A positive cycle duration and four timing thresholds are required")
    out = tuple(finite(x, "timing") for x in values)
    if not (0 < out[0] < out[1] < out[2] < out[3] <= duration + 1e-12):
        raise ValueError("Timings must satisfy 0 < tA < tB < tC < tD <= cycle duration")
    return out


def timings_from_normalized_action(action, duration):
    """Same four denormalization intervals as main_RL_online.py."""
    if len(action) != 4:
        raise ValueError("The RL timing action must contain four numbers")
    vals = [finite(x, "action") for x in action]
    if any(abs(x) > 1 for x in vals):
        raise ValueError("Normalized RL actions must be in [-1, 1]")
    duration = finite(duration, "cycle duration")
    result = [(x + 1) * 0.5 * (hi - lo) * duration + lo * duration
              for x, (lo, hi) in zip(vals, RL_ACTION_RANGES)]
    return validate_timings(result, duration)


def heuristic_timings(percent, duration):
    if len(percent) != 3:
        raise ValueError("The heuristic requires three percentage thresholds")
    return validate_timings([finite(x) * duration / 100 for x in percent] + [duration], duration)


def pressure_for_phase(elapsed, timings, amplitude):
    """Pd order stays p0,p1; physical mapping is a separate configuration."""
    t = finite(elapsed, "phase time")
    amp = finite(amplitude, "amplitude_psi")
    if amp < 0:
        raise ValueError("Pressure amplitude cannot be negative")
    a, b, c, d = timings
    if t < 0 or t >= d:
        return (0.0, 0.0)
    return (0.0, amp) if t < a or b <= t < c else (amp, 0.0)


class PressureReplay:
    """Zero-order hold of explicit PSI columns, with a finite end-of-file tail."""
    def __init__(self, path, maximum, tail_s=0.1):
        self.maximum = finite(maximum)
        self.tail_s = finite(tail_s)
        if self.maximum <= 0 or self.tail_s < 0:
            raise ValueError("Invalid replay pressure limit or tail")
        self.rows = []
        with Path(path).open(newline="") as f:
            reader = csv.DictReader(f)
            required = {"time_s", "p0_psi", "p1_psi"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Replay CSV needs time_s,p0_psi,p1_psi columns")
            for row in reader:
                values = tuple(finite(row[k], k) for k in ("time_s", "p0_psi", "p1_psi"))
                if values[0] < 0 or any(v < 0 or v > self.maximum for v in values[1:]):
                    raise ValueError("Replay times/pressures are outside configured bounds")
                if self.rows and values[0] <= self.rows[-1][0]:
                    raise ValueError("Replay timestamps must be strictly increasing")
                self.rows.append(values)
        if not self.rows:
            raise ValueError("Replay CSV is empty")
        self.times = [r[0] for r in self.rows]

    def command(self, time_s):
        time_s = finite(time_s)
        i = bisect_right(self.times, time_s) - 1
        if i < 0 or time_s >= self.times[-1] + self.tail_s:
            return (0.0, 0.0)
        return self.rows[i][1:]


class PressureController:
    def __init__(self, config, base):
        self.cfg = config
        self.phase_origin = 0.0
        self.replay = None
        if config["mode"] == "replay":
            self.replay = PressureReplay(Path(base) / config["replay_file"],
                                         config["max_pressure_psi"], config["replay_tail_s"])

    def heel_strike(self, time_s):
        self.phase_origin = finite(time_s)

    def command(self, time_s):
        c = self.cfg
        if not c["actuation_enabled"]:
            return (0.0, 0.0)
        mode = c["mode"]
        if mode == "manual":
            out = c["manual_pressure_psi"]
        elif mode == "replay":
            if self.replay is None:
                raise ValueError("Replay mode requires loading a CSV when the scene is created")
            out = self.replay.command(time_s)
        elif mode == "timed":
            if c["profile"] == "heuristic":
                duration = c["heuristic_duration_s"]
                thresholds = heuristic_timings(c["heuristic_percent"], duration)
            else:
                duration = c["cycle_duration_s"]
                thresholds = validate_timings(c["timings_s"], duration)
            # Synthetic cycle reset for an isolated bench experiment. A real gait
            # event can explicitly reset the origin via heel_strike().
            phase = (time_s - self.phase_origin) % duration
            out = pressure_for_phase(phase, thresholds, c["pressure_amplitude_psi"])
        else:
            raise ValueError(f"Unknown input mode: {mode}")
        return tuple(clamp(finite(v, "pressure_psi"), 0.0, c["max_pressure_psi"]) for v in out)
