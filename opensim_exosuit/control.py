"""Finite, bounded software input for the commandable OpenSim knee moment.

This is a simulation control boundary, not hardware safety or clinical logic.
OpenSim CoordinateActuator min/max controls alone do not clamp forward inputs.
"""

import math

import opensim as osim

from .builder import ACTUATOR_NAME


def set_knee_moment(model, state, config, torque_flexion_positive_nm):
    """Set a held moment on this State, returning applied torque and saturation.

    Call before Manager.initialize(). When changing input between integration
    intervals, copy the last integrated State and create a new Manager. Mutating
    the old external State does not update a Manager's internally owned State.
    The demo uses a continuous native PrescribedController instead.
    """
    requested = float(torque_flexion_positive_nm)
    cap = float(config["assistance"]["maximum_torque_nm"])
    if not math.isfinite(requested) or not math.isfinite(cap) or cap < 0:
        raise ValueError("Moment input must be finite and its limit finite and nonnegative")
    sign = config["model"]["flexion_sign"]
    if sign not in (-1, 1):
        raise ValueError("flexion_sign must be -1 or +1")
    applied = max(-cap, min(cap, requested))
    actuator = osim.ScalarActuator.safeDownCast(model.getForceSet().get(ACTUATOR_NAME))
    actuator.overrideActuation(state, True)
    actuator.setOverrideActuation(state, sign * applied)
    return {"requested_flexion_positive_nm": requested,
            "applied_flexion_positive_nm": applied,
            "applied_native_nm": sign * applied,
            "saturated": applied != requested}
