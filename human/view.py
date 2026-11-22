"""Watch a muscle-driven human wearing the pneumatic knee exosuit.

On macOS launch with mjpython. Space pauses; R resets; A toggles assistance;
V hides or shows the suit. M selects independent manual pressure control,
T selects timed single-bank control, E/F select extension/flexion, and Up/Down
change the selected manual pressure by 1 PSI. A fall remains visible until R.
The timed mode uses a fixed four-value preset, not a trained walking policy.
"""

import argparse
import json
import math
import time
from queue import Empty, SimpleQueue

import mujoco
import mujoco.viewer

from .device_factory import make_device
from .environment import load_config
from .exosuit_visuals import visuals_from_config,configure_rendering
from .native_backend import HumanBackend
from .rl_contract import action_to_timing
from .human_avatar import HumanAvatar
from .rendering import prepare_human_appearance


def _clamp_pressure(value):
    """The viewer's manual control range is 0 to 30 gauge PSI."""
    return max(0.0, min(30.0, float(value)))


def _telemetry(device):
    """Give the viewer the same two-bank fields for the legacy device fallback."""
    if hasattr(device, "telemetry"):
        return device.telemetry()
    bank = device.config.direction
    result = {
        "mode": "legacy", "enabled": bool(device.enabled), "legacy_bank": bank,
        "active_torque_nm": float(device.torque_nm),
        "net_torque_nm": float(device.torque_nm),
    }
    for name in ("extension", "flexion"):
        result[f"{name}_command_psi"] = float(device.command_psi) if name == bank else 0.0
        result[f"{name}_pressure_psi"] = float(device.actual_psi) if name == bank else 0.0
    return result


def _apply_mode(device, controls):
    if hasattr(device, "set_manual_pressures"):
        if controls["mode"] == "manual":
            device.set_manual_pressures(
                controls["manual"]["extension"], controls["manual"]["flexion"])
        else:
            device.set_legacy_mode(controls["bank"])
    else:
        device.config.direction = controls["bank"]


def _handle_event(key, controls, device, device_present):
    """Apply queued key events on the simulation thread, never the GUI thread."""
    if key == 32:
        controls["paused"] = not controls["paused"]
    elif key in (ord("R"), ord("r")):
        controls["reset"] = True
    elif key in (ord("V"), ord("v")):
        if device_present:
            controls["visible"] = not controls["visible"]
    elif key in (ord("E"), ord("e")):
        controls["bank"] = "extension"
    elif key in (ord("F"), ord("f")):
        controls["bank"] = "flexion"
    elif key in (ord("A"), ord("a")):
        if device_present:
            device.enabled = not device.enabled
            # Refresh the requested pressure on the next simulation step.
            _apply_mode(device, controls)
    elif key in (ord("M"), ord("m")):
        if device_present and hasattr(device, "set_manual_pressures"):
            controls["mode"] = "manual"
            _apply_mode(device, controls)
            device.enabled = True
    elif key in (ord("T"), ord("t")):
        if device_present:
            controls["mode"] = "legacy"
            _apply_mode(device, controls)
            device.enabled = True
    elif key in (265, 264):  # GLFW_KEY_UP, GLFW_KEY_DOWN.
        if device_present and hasattr(device, "set_manual_pressures"):
            change = 1.0 if key == 265 else -1.0
            bank = controls["bank"]
            controls["manual"][bank] = _clamp_pressure(controls["manual"][bank] + change)
            controls["mode"] = "manual"
            _apply_mode(device, controls)
            device.enabled = True


def _overlay(state, telemetry, controls, device_mass_kg, device_present):
    if state["fallen"]:
        status = "FALL - press R to reset"
    elif controls["paused"]:
        status = "Paused"
    else:
        status = "Running"
    mode = ("Independent manual banks" if telemetry["mode"] == "manual"
            else "Timed single bank: " + telemetry["legacy_bank"])
    actual = max(telemetry["extension_pressure_psi"], telemetry["flexion_pressure_psi"])
    if not device_present:
        assistance = "No exosuit"
        mode = "Unassisted human"
    elif telemetry["enabled"]:
        assistance = "Enabled"
    else:
        assistance = "Venting" if actual > 0.05 else "Off, suit worn"
    labels = "\n".join((
        "Simulation time", "State", "Assistance", "Mode", "Selected bank",
        "Extension command", "Extension pressure", "Flexion command",
        "Flexion pressure", "Net active torque", "Carried device mass",
        "Manual setpoints E / F", "Suit appearance"))
    values = "\n".join((
        f"{state['time_s']:.2f} s", status, assistance, mode, controls["bank"],
        f"{telemetry['extension_command_psi']:.1f} PSI",
        f"{telemetry['extension_pressure_psi']:.1f} PSI",
        f"{telemetry['flexion_command_psi']:.1f} PSI",
        f"{telemetry['flexion_pressure_psi']:.1f} PSI",
        f"{telemetry['active_torque_nm']:+.2f} Nm (positive = flexion)",
        f"{device_mass_kg:.2f} kg",
        f"{controls['manual']['extension']:.1f} / {controls['manual']['flexion']:.1f} PSI",
        "Visible" if device_present and controls["visible"] else "Hidden"))
    instructions = (
        "Space pause  |  R reset  |  A assistance  |  V suit visibility\n"
        "E extension / F flexion  |  Up / Down manual PSI\n"
        "M independent manual banks  |  T timed selected bank\n"
        "Drag rotate  |  Wheel zoom\n"
        "Generic human; assumed suit parameters; illustrative pouch swelling")
    return [
        (mujoco.mjtFontScale.mjFONTSCALE_100, mujoco.mjtGridPos.mjGRID_TOPLEFT, labels, values),
        (mujoco.mjtFontScale.mjFONTSCALE_100, mujoco.mjtGridPos.mjGRID_BOTTOMLEFT,
         instructions, ""),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--assist", action="store_true",
                        help="Enable the timed pressure schedule at startup")
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="Close after this many wall seconds; 0 keeps the viewer open")
    parser.add_argument("--stride-seconds", type=float, default=1.15,
                        help="Period used to decode the fixed four-value timing preset")
    parser.add_argument("--action", nargs=4, type=float, default=[0.0, 0.0, 0.0, 0.0])
    parser.add_argument("--no-exosuit", action="store_true",
                        help="Remove device mass, appearance and active assistance")
    parser.add_argument("--anatomy", action="store_true",help="Show the underlying bone and muscle visualization")
    parser.add_argument("--bank", choices=("extension", "flexion"),
                        help="Bank used by the legacy single-channel timed schedule")
    parser.add_argument("--manual", nargs=2, type=float, metavar=("EXT_PSI", "FLEX_PSI"),
                        help="Enable independent hypothetical pressure banks, each clamped to 0..30 PSI")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds < 0:
        parser.error("--seconds must be finite and nonnegative")
    if not math.isfinite(args.stride_seconds) or args.stride_seconds <= 0:
        parser.error("--stride-seconds must be finite and positive")
    if args.manual is not None and not all(math.isfinite(value) for value in args.manual):
        parser.error("--manual pressures must be finite")

    config = load_config(args.config)
    config.setdefault("exosuit", {}).setdefault("enabled", True)
    if args.no_exosuit:
        config["exosuit"]["enabled"] = False
        config["device_enabled"] = False
    device_present = bool(config["exosuit"].get("enabled", True))
    command = action_to_timing(
        args.action, config["action_profile"], args.stride_seconds).require_valid()
    device = make_device(config)
    device.set_timings(command.as_tuple())
    pneumatic = hasattr(device, "telemetry")
    default_bank = (device.config.legacy_bank if pneumatic else device.config.direction)
    controls = {
        "paused": False, "reset": False, "visible": device_present,
        "mode": "manual" if args.manual is not None and device_present else "legacy",
        "bank": args.bank or default_bank,
        "manual": dict(zip(("extension", "flexion"),
                           map(_clamp_pressure, args.manual or (0.0, 0.0)))),
    }
    if controls["mode"] == "manual" and not hasattr(device, "set_manual_pressures"):
        parser.error("Independent manual banks require the pneumatic exosuit")
    _apply_mode(device, controls)
    device.enabled = device_present and (args.assist or args.manual is not None)
    visuals = visuals_from_config(config)
    visuals.visible = controls["visible"]
    events = SimpleQueue()

    def keyboard(key):
        events.put(key)

    human = HumanBackend(exosuit=config.get("exosuit"))
    configure_rendering(human.model)
    avatar=HumanAvatar(human.model) if not args.anatomy else None
    state = human.reset()
    last_contact = state["left_grf_n"] > config["grf_threshold_n"]
    print(json.dumps({
        "controls": "Space pause; R reset; A assistance; V suit; M manual; T timed; E/F bank; Up/Down PSI",
        "timings_s": command.as_tuple(), "device_present": device_present,
        "mode": controls["mode"], "legacy_bank": controls["bank"],
        "device_mass_kg": float(getattr(human, "device_mass_kg", 0.0)),
        "human": "generic frozen reflex controller",
        "pressure_units": "gauge PSI", "suit_parameters": "uncalibrated assumptions",
    }))
    try:
        with mujoco.viewer.launch_passive(
                human.model, human.data, key_callback=keyboard,
                show_left_ui=False, show_right_ui=False) as viewer:
            opened = time.monotonic()
            with viewer.lock():
                if avatar is not None:prepare_human_appearance(human.model,viewer.opt)
                viewer.cam.azimuth = -100
                viewer.cam.elevation = -8
                viewer.cam.distance = 3.4
            while viewer.is_running():
                if args.seconds > 0 and time.monotonic() - opened >= args.seconds:
                    break
                started = time.monotonic()
                with viewer.lock():
                    while True:
                        try:
                            key = events.get_nowait()
                        except Empty:
                            break
                        _handle_event(key, controls, device, device_present)
                    if controls["reset"]:
                        enabled = bool(device.enabled)
                        state = human.reset()
                        device.reset()
                        device.set_timings(command.as_tuple())
                        _apply_mode(device, controls)
                        device.enabled = enabled and device_present
                        controls["reset"] = False
                        controls["paused"] = False
                        last_contact = state["left_grf_n"] > config["grf_threshold_n"]
                    if not controls["paused"] and not state["fallen"]:
                        duration = human.human_control_dt_s
                        if pneumatic:
                            torque = device.advance(
                                state["time_s"], duration,
                                knee_angle_rad=state["knee_angle_rad"],
                                knee_velocity_rad_s=state["knee_velocity_rad_s"])
                        else:
                            torque = device.advance(state["time_s"], duration)
                        state = human.step(duration, torque)
                        contact = state["left_grf_n"] > config["grf_threshold_n"]
                        if contact and not last_contact:
                            device.heel_strike(state["time_s"])
                        last_contact = contact
                        if state["fallen"]:
                            print("Fall detected. Press R to reset.")
                    telemetry = _telemetry(device)
                    visuals.visible = controls["visible"] and device_present
                    if avatar is not None:avatar.draw(viewer.user_scn,human.model,human.data,clear=True)
                    visuals.draw(viewer.user_scn, human.model, human.data, telemetry, clear=avatar is None)
                    viewer.cam.lookat[:] = human.data.body("pelvis").xpos
                    texts = _overlay(state, telemetry, controls,
                                     float(getattr(human, "device_mass_kg", 0.0)), device_present)
                viewer.set_texts(texts)
                viewer.sync()
                time.sleep(max(0.0, human.human_control_dt_s - (time.monotonic() - started)))
    finally:
        human.close()


if __name__ == "__main__":
    main()
