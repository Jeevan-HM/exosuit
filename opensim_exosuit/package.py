"""Package native models, source assets and reproducible helpers for sharing."""

import argparse
from pathlib import Path
import zipfile

from .settings import PACKAGE_DIR

PROJECT_DIR = PACKAGE_DIR.parent
DEFAULT_ARCHIVE = PROJECT_DIR / "OpenSim_Knee_Exosuit.zip"


def package(archive_path=DEFAULT_ARCHIVE):
    archive_path = Path(archive_path).resolve()
    required = (PACKAGE_DIR / "output/knee_exosuit.osim",
                PACKAGE_DIR / "output/validation.json",
                PACKAGE_DIR / "output/preview.png")
    if any(not path.is_file() for path in required):
        raise FileNotFoundError("Build and verify the model first: python -m opensim_exosuit.demo")
    if archive_path.is_relative_to(PACKAGE_DIR):
        raise ValueError("Write the archive outside its own source package")
    files = [p for p in PACKAGE_DIR.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"]
    files += [PROJECT_DIR / "Build_OpenSim_Model.command"]
    prefix = "OpenSim_Knee_Exosuit"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{prefix}/START_HERE.txt", (
            "OpenSim pneumatic knee exosuit\n\n"
            "Open opensim_exosuit/output/knee_exosuit.osim in OpenSim 4.6.\n"
            "Keep its Geometry folder beside the model.\n"
            "Walking playback: load output/normal_walking.mot against the full\n"
            "model (paths relative to opensim_exosuit/). This is a reference\n"
            "gait animation, not a prediction of exosuit assistance effects.\n"
            "Preview: opensim_exosuit/output/preview.png\n"
            "Instructions: opensim_exosuit/README.md\n"
            "Mac rebuild: double-click Build_OpenSim_Model.command.\n\n"
            "Full model: generic Gait2392 human, 92 muscles, 23 coordinates.\n"
            "Verified demo: seated mechanical test with one free knee, disabled\n"
            "muscle forces, and an added fixture spring. This is not validated\n"
            "walking, patient response or rehabilitation efficacy. Device\n"
            "parameters are assumptions. No hardware is controlled.\n\n"
            "Source attribution and CC BY 3.0 license: opensim_exosuit/assets/.\n"
        ))
        for path in sorted(files):
            archive.write(path, f"{prefix}/{path.relative_to(PROJECT_DIR).as_posix()}")
    with zipfile.ZipFile(archive_path) as archive:
        corrupted = archive.testzip()
        if corrupted:
            raise RuntimeError(f"Archive integrity check failed: {corrupted}")
    return archive_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()
    print(f"Packaged verified model: {package(args.output)}")


if __name__ == "__main__":
    main()
