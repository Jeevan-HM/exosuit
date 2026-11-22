"""The simulation interface uses PSI gauge; mechanical calculations use SI."""
import math

PA_PER_PSI = 6894.757293168


def finite(value, name="value"):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def psi_to_pa(psi):
    return finite(psi, "pressure_psi") * PA_PER_PSI


def pa_to_psi(pa):
    return finite(pa, "pressure_pa") / PA_PER_PSI


def clamp(value, low, high):
    return min(high, max(low, value))
