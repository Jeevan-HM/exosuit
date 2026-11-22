"""Build an offline continuous walking viewer with synchronized knee plots."""

import argparse
import json
from pathlib import Path

from .live_data import export_live_data
from .settings import PACKAGE_DIR
from .walking import DEFAULT_OUTPUT, prepare


def build_live_viewer(directory=DEFAULT_OUTPUT):
    directory = Path(directory).resolve()
    if not (directory / "human_walking.osim").is_file() or not (directory / "normal_walking.mot").is_file():
        prepare(directory)
    data_path = export_live_data(directory)
    data = json.loads(data_path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported walking scene schema")
    template = (PACKAGE_DIR / "live_viewer.template.html").read_text()
    if template.count("__LIVE_DATA_JSON__") != 1:
        raise ValueError("The live viewer must contain exactly one scene placeholder")
    # The page is self-contained and can be opened directly from disk. Escape
    # HTML delimiters in metadata without changing JSON's interpreted values.
    serialized = json.dumps(data, separators=(",", ":"), ensure_ascii=True,
                            allow_nan=False).replace("<", "\\u003c")
    target = directory / "live_walking.html"
    target.write_text(template.replace("__LIVE_DATA_JSON__", serialized))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(f"Built continuous OpenSim walking viewer: {build_live_viewer(args.directory)}")


if __name__ == "__main__":
    main()
