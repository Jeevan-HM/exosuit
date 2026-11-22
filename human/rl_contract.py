"""Hardware-free interface to the audited ``new-RL`` controller contracts.

Sources (relative to the user's new-RL directory):
* RL code/main_v9_noemgstate.py:165,181-184,204-240 (seconds profile).
* RL code/main_v1_noemgstate_percent.py:165,181-185,205-244 (fraction profile).
* pressure_commands_v3.py:212-250,259-260 (one pressure, PSI, 100 Hz).
* gait_timing_v6.py:307-324,356-458,462-466,548 (events and vector).
* RL code/DHDP.py:60-78 (positive costs, minimized actor loss).

These are explicit alternative contracts; do not choose a profile from a
checkpoint filename. gait_timing_v6 emits FRACTIONS and therefore must not be
fed unchanged to v9_seconds. The percent profile preserves the unusual d1/2
observation and action-alignment convention. Its source has broken line
continuations at 236-240; this module implements the written mathematical sum.

No source scripts are imported, sockets opened, or hardware commands sent.
Muscle activations are simulation proxies, NOT synthesized or predicted EMG.
The extractor uses measured event samples, without fixed-phase substitution.
Its five-stride average deliberately corrects the original four-summed/5 bug
at gait_timing_v6.py:562-576, instead of silently reproducing it.
"""

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple

import numpy as np


PROFILES = ("v9_seconds", "v1_percent")
PRESSURE_COMMAND_HZ = 100.0
STANCE_PRESSURE_PSI = 25.0
SWING_PRESSURE_PSI = 20.0
CONTACT_THRESHOLD_N = 100.0
FEATURE_NAMES = (
    "single_support_onset", "single_support_duration", "swing_peak_onset",
    "swing_peak_to_heelstrike_duration", "peak_knee_flexion_rad",
    "VL_activation_proxy", "RF_activation_proxy", "BF_activation_proxy",
    "stride_seconds",
)
ACTION_BOUNDS = {
    "v9_seconds": ((0.0, 0.3), (0.3, 0.8), (0.7, 1.4), (0.2, 0.4)),
    "v1_percent": ((0.0, 0.2), (0.0, 0.25), (0.5, 0.74), (0.0, 0.28)),
}


def _profile(profile):
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}; choose one of {PROFILES}")
    return profile


def _vector(values, length, name):
    try:
        result = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain {length} finite numeric values") from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must have shape ({length},) and finite values")
    return result


def _positive(value, name):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _action(action):
    values = _vector(action, 4, "action")
    if np.any(values < -1) or np.any(values > 1):
        raise ValueError("Normalized action must lie in [-1, 1]; clipping is not implicit")
    return values


@dataclass(frozen=True)
class TimingCommand:
    """Two onset-duration windows in seconds, driving one scalar pressure."""

    t1: float
    d1: float
    t2: float
    d2: float
    stride_seconds: float
    profile: str

    def as_tuple(self):
        return (self.t1, self.d1, self.t2, self.d2)

    def validation_errors(self):
        values = self.as_tuple() + (self.stride_seconds,)
        errors = []
        if self.profile not in PROFILES:
            errors.append("unknown_profile")
        if not all(math.isfinite(float(x)) for x in values):
            return tuple(errors + ["nonfinite_timing"])
        if self.stride_seconds <= 0:
            errors.append("nonpositive_stride")
        if min(self.as_tuple()) < 0:
            errors.append("negative_onset_or_duration")
        if self.t1 + self.d1 > self.t2 + 1e-12:
            errors.append("overlapping_pressure_windows")
        if self.t1 + self.d1 > self.stride_seconds + 1e-12:
            errors.append("stance_window_past_next_heelstrike")
        if self.t2 + self.d2 > self.stride_seconds + 1e-12:
            errors.append("swing_window_past_next_heelstrike")
        return tuple(errors)

    @property
    def valid(self):
        return not self.validation_errors()

    def require_valid(self):
        errors = self.validation_errors()
        if errors:
            raise ValueError("Invalid timing command: " + ", ".join(errors))
        return self


def action_to_timing(action, profile, stride_seconds):
    """Map [-1,1]^4 exactly; return invalid windows explicitly, never sort/clip.

    v9_seconds uses absolute seconds; v1_percent multiplies its four fractions
    by the latest gait duration. Some legal actor outputs produce overlapping
    or overlong windows. Call ``require_valid`` before simulating a command.
    """
    profile = _profile(profile)
    stride = _positive(stride_seconds, "stride_seconds")
    action = _action(action)
    bounds = np.asarray(ACTION_BOUNDS[profile])
    timings = bounds[:, 0] + 0.5 * (action + 1) * (bounds[:, 1] - bounds[:, 0])
    if profile == "v1_percent":
        timings = timings * stride
    return TimingCommand(*(float(x) for x in timings), stride, profile)


def pressure_psi(time_since_heelstrike, command):
    """Source-ordered endpoint semantics of pressure_commands_v3.py:234-243.

    At exactly t1 pressure is zero; at exactly t1+d1 it is 25 PSI. At t2 it
    remains zero unless the preceding stance window ends at that same sample.
    This is one shared pressure channel, not flexion/extension valve routing.
    """
    command.require_valid()
    t = float(time_since_heelstrike)
    if not math.isfinite(t):
        raise ValueError("time_since_heelstrike must be finite")
    if t <= command.t1:
        return 0.0
    if t <= command.t1 + command.d1:
        return STANCE_PRESSURE_PSI
    if t <= command.t2:
        return 0.0
    if t <= command.t2 + command.d2:
        return SWING_PRESSURE_PSI
    return 0.0


def sample_pressure_schedule(command, sample_hz=PRESSURE_COMMAND_HZ):
    """Return (seconds, PSI) from heelstrike, sampled at 100 Hz by default."""
    command.require_valid()
    hz = _positive(sample_hz, "sample_hz")
    times = np.arange(int(math.floor(command.stride_seconds * hz)) + 1) / hz
    return times, np.asarray([pressure_psi(t, command) for t in times])


def observation_from_features(features, profile):
    """Return five actor observations; first four feature units match profile."""
    profile = _profile(profile)
    features = _vector(features, 9, "features")
    _positive(features[8], "features.stride_seconds")
    state = features[:5].copy()
    if profile == "v1_percent":
        state[1] /= 2.0
    return tuple(float(x) for x in state)


def legacy_cost(features, action, profile):
    """Exact positive online legacy cost; VL/RF/BF inputs may be proxies.

    No assertion of EMG calibration or physiological validity is implied by
    reproducing these historical coefficients. Offline v2 is a different
    action-imitation objective and is deliberately not selected automatically.
    """
    profile = _profile(profile)
    features = _vector(features, 9, "features")
    action = _action(action)
    state = np.asarray(observation_from_features(features, profile))
    if profile == "v9_seconds":
        targets = np.array([0.232, 0.6, 1.2, 0.3, 0.698])
        state_weights = np.array([100., 100., 100., 100., 10.])
        action_weights = np.array([100., 50., 100., 50.])
        command = action_to_timing(action, profile, features[8])
        action_error = np.asarray(command.as_tuple()) - targets[:4]
        emg_weight = 50.0
    else:
        targets = np.array([0.124, 0.375 / 2, 0.71, 0.168, 0.698])
        state_weights = np.array([20., 20., 10., 15., 0.05])
        action_weights = np.array([2., 2., 1., 1.5])
        scaled_features = np.array([
            2 * features[0] / .2 - 1,
            2 * (features[1] / 2) / .25 - 1,
            2 * (features[2] - .5) / .24 - 1,
            2 * features[3] / .28 - 1,
        ])
        action_error = scaled_features - action
        emg_weight = 1.0
    return float(0.5 * (
        np.dot(state_weights, (state - targets) ** 2)
        + np.dot(action_weights, action_error ** 2)
        + emg_weight * float(np.sum(features[5:8])) ** 2
    ))


def reward_from_cost(cost):
    """Use with reward-maximizing RL only; legacy DHDP already minimizes cost."""
    value = float(cost)
    if not math.isfinite(value) or value < 0:
        raise ValueError("cost must be finite and nonnegative")
    return -value


@dataclass(frozen=True)
class StrideFeatures:
    heelstrike_start: float
    heelstrike_end: float
    profile: str
    vector: Optional[Tuple[float, ...]]
    errors: Tuple[str, ...] = ()
    events: Tuple[Tuple[str, float], ...] = ()
    muscle_signal_kind: str = "mean_simulated_activation_proxy"

    @property
    def valid(self):
        return self.vector is not None and not self.errors


def extract_strides(time, knee_angle_rad, left_grf_n, right_grf_n,
                    activation_proxy=None, profile="v1_percent",
                    threshold_n=CONTACT_THRESHOLD_N):
    """Extract completed strides from actual contact transitions and angle peaks.

    Inputs are synchronized N-vectors; activation_proxy, when supplied, is N×3
    in VL/RF/BF order and is averaged by trapezoidal time integration over the
    stride. It must be nonnegative. It is NOT transformed using subject MVC
    constants and NOT labeled experimental EMG. If absent, no complete vector
    is manufactured. The knee angle is flexion-positive radians.

    A heelstrike requires a false->true transition of left GRF >100 N. Initial
    contact alone is not a known heelstrike. First left-only support interval
    supplies t1,d1; first strict local knee maximum in subsequent left swing
    supplies t2 and d2 to next heelstrike. Missing/invalid events return flags.
    Fractions are emitted in v1_percent, seconds in v9_seconds. This preserves
    event definitions but removes the wall-clock/network latency of v6.
    """
    profile = _profile(profile)
    times = np.asarray(time, dtype=float)
    if times.ndim != 1 or times.size < 3 or not np.all(np.isfinite(times)):
        raise ValueError("time must be a finite vector with at least 3 samples")
    if np.any(np.diff(times) <= 0):
        raise ValueError("time must be strictly increasing")
    size = len(times)
    angle = _vector(knee_angle_rad, size, "knee_angle_rad")
    left = _vector(left_grf_n, size, "left_grf_n")
    right = _vector(right_grf_n, size, "right_grf_n")
    threshold = _positive(threshold_n, "threshold_n")
    if activation_proxy is not None:
        activation = np.asarray(activation_proxy, dtype=float)
        if (activation.shape != (size, 3) or not np.all(np.isfinite(activation))
                or np.any(activation < 0)):
            raise ValueError("activation_proxy must be finite, nonnegative, shape (N,3)")
    else:
        activation = None
    lcontact, rcontact = left > threshold, right > threshold
    heelstrikes = np.flatnonzero(lcontact[1:] & ~lcontact[:-1]) + 1
    output = []
    for start, end in zip(heelstrikes[:-1], heelstrikes[1:]):
        period = float(times[end] - times[start])
        errors, events = [], [("heelstrike_start", float(times[start])),
                              ("heelstrike_end", float(times[end]))]
        single = lcontact[start:end] & ~rcontact[start:end]
        starts = np.flatnonzero(single & np.r_[True, ~single[:-1]]) + start
        ss_start = ss_end = peak = None
        if len(starts) == 0:
            errors.append("missing_left_single_support")
        else:
            ss_start = int(starts[0])
            ends = np.flatnonzero(~(lcontact[ss_start:end] & ~rcontact[ss_start:end]))
            if len(ends) == 0:
                errors.append("single_support_has_no_end")
            else:
                ss_end = int(ss_start + ends[0])
                events.extend((("single_support_start", float(times[ss_start])),
                               ("single_support_end", float(times[ss_end]))))
        swing_start = ss_end if ss_end is not None else start
        for index in range(max(swing_start + 1, start + 1), end):
            if (not lcontact[index] and angle[index - 1] < angle[index]
                    and angle[index] > angle[index + 1]):
                peak = index
                events.append(("swing_knee_peak", float(times[index])))
                break
        if peak is None:
            errors.append("missing_strict_swing_knee_peak")
        if activation is None:
            errors.append("missing_activation_proxy")
        vector = None
        if not errors:
            timings = np.array([
                times[ss_start] - times[start], times[ss_end] - times[ss_start],
                times[peak] - times[start], times[end] - times[peak],
            ])
            if profile == "v1_percent":
                timings /= period
            # Avoid the trapz/trapezoid API difference across NumPy versions.
            segment = activation[start:end + 1]
            widths = np.diff(times[start:end + 1])[:, None]
            muscle_means = np.sum(.5 * (segment[:-1] + segment[1:]) * widths,
                                  axis=0) / period
            vector = tuple(float(x) for x in np.r_[timings, angle[peak], muscle_means, period])
        output.append(StrideFeatures(float(times[start]), float(times[end]), profile,
                                     vector, tuple(errors), tuple(events)))
    return output


class FiveStrideAggregator:
    """Nonoverlapping means of five valid strides, with optional settling skip.

    Original v6 intended one skipped settling stride then five averaged strides
    but actually sums four and divides five (562-576). Here warmup_strides=1
    explicitly skips one valid stride per block; default 0 means five valid
    strides. Invalid strides never contribute; no partial mean is returned.
    ``clear`` should be called after changing policy/action to avoid mixing
    responses to different commands. This module does not invent a settling
    delay or claim the average is an immediate next-state measurement.
    """

    def __init__(self, profile="v1_percent", warmup_strides=0):
        self.profile = _profile(profile)
        if not isinstance(warmup_strides, int) or warmup_strides < 0:
            raise ValueError("warmup_strides must be a nonnegative integer")
        self.warmup_strides = warmup_strides
        self.clear()

    def clear(self):
        self._pending = []
        self._warmup_remaining = self.warmup_strides

    @property
    def pending_count(self):
        return len(self._pending)

    def add(self, stride):
        if isinstance(stride, StrideFeatures):
            if stride.profile != self.profile:
                raise ValueError("Cannot aggregate different timing-unit profiles")
            if not stride.valid:
                return None
            stride = stride.vector
        vector = _vector(stride, 9, "stride features")
        _positive(vector[8], "stride features.stride_seconds")
        if self._warmup_remaining:
            self._warmup_remaining -= 1
            return None
        self._pending.append(vector.copy())
        if len(self._pending) < 5:
            return None
        result = tuple(float(x) for x in np.mean(self._pending, axis=0))
        self.clear()
        return result
