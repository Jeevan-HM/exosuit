"""Read and validate explicit model assumptions, without importing OpenSim."""

import json
import math
from pathlib import Path

from .mechanics import DeviceMechanics

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = PACKAGE_DIR / "config.json"
BASE_MODEL = PACKAGE_DIR / "assets/base/gait2392_simbody.osim"
DEFAULT_OUTPUT = PACKAGE_DIR / "output"


def load_settings(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text())
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported OpenSim exosuit configuration schema")
    model = config["model"]
    if model["side"] not in ("l", "r"):
        raise ValueError("model.side must be l or r")
    if model["knee_coordinate"] != f"knee_angle_{model['side']}":
        raise ValueError("The bundled Gait2392 model needs knee_angle_l or knee_angle_r matching side")
    if model["flexion_sign"] != -1:
        raise ValueError("The bundled Gait2392 knees have negative flexion; flexion_sign must be -1")
    DeviceMechanics(**config["exosuit"]["mechanics"], side=model["side"]).validate()
    demo = config["demo"]
    for name in ("duration_s", "sample_interval_s"):
        value = float(demo[name])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"demo.{name} must be finite and positive")
    if demo["sample_interval_s"] > demo["duration_s"]:
        raise ValueError("sample interval must not exceed the demo duration")
    for name in ("initial_knee_flexion_deg", "hip_flexion_deg"):
        value = float(demo[name])
        if not math.isfinite(value) or not 0 <= value <= 120:
            raise ValueError(f"demo.{name} must lie in 0–120 degrees")
    return config
