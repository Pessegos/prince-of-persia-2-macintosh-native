"""Extract the resource files required by the rooftop prototype."""

import argparse
import json
from pathlib import Path
import struct
import tempfile

from extract_enemy_profiles import extract_bytes
from mac_resources import get_resource_fork, parse_resource_fork


PROJECT_DIR = Path(__file__).resolve().parent
ASSET_DIR = PROJECT_DIR / "assets"
RESOURCE_FILES = ("Prince.rsrc", "Kid.rsrc", "Guard.rsrc", "Rooftops.rsrc")
REQUIRED_RESOURCES = {
    "Prince.rsrc": {"LEVL", "SEQS", "SHAP", "SHPL", "CTBL", "NFNT"},
    "Kid.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Guard.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Rooftops.rsrc": {"PIEC", "SHAP", "CTBL"},
}


def extract_assets(image_path, output_dir=ASSET_DIR):
    image = Path(image_path).read_bytes()
    # Validate the complete set before replacing any installed game files.
    try:
        resources = {name: get_resource_fork(image, name) for name in RESOURCE_FILES}
        for name, data in resources.items():
            missing = REQUIRED_RESOURCES[name] - parse_resource_fork(data).keys()
            if missing:
                raise ValueError(f"{name} is missing resources: {', '.join(sorted(missing))}")
        program = get_resource_fork(image, "Prince of Persia 2", "APPL")
        profiles = extract_bytes(program, resources["Prince.rsrc"])
        resources["enemy_profiles.json"] = (
            json.dumps(profiles, indent=2) + "\n"
        ).encode("ascii")
    except (FileNotFoundError, ValueError, KeyError, IndexError, struct.error) as error:
        raise ValueError(f"This is not a supported Macintosh PoP2 disk image: {error}") from error
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".import-", dir=output_dir) as directory:
        staging = Path(directory)
        for name, resource in resources.items():
            (staging / name).write_bytes(resource)
        for name in resources:
            (staging / name).replace(output_dir / name)
    return resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to the Macintosh PoP2 HFS image")
    parser.add_argument("--output", type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    try:
        resources = extract_assets(args.image, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Asset extraction failed: {error}\n")
    for name, resource in resources.items():
        print(f"{name}: {len(resource):,} bytes")


if __name__ == "__main__":
    main()
