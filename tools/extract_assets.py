"""Extract the resource files required by the rooftop prototype."""

import argparse
import json
from pathlib import Path
import struct
import tempfile

from tools.extract_enemy_profiles import extract_bytes
from tools.extract_audio import extract_audio
from tools.extract_intro import extract_intro, extract_ending
from tools.extract_attract import extract_attract, extract_credits_music
from pop2.mac_resources import get_resource_fork, parse_resource_fork
from pop2.paths import ASSET_DIR


RESOURCE_FILES = ("Prince.rsrc", "Kid.rsrc", "Guard.rsrc", "Rooftops.rsrc", "NIS.rsrc", "Title.rsrc", "Desert.rsrc")
REQUIRED_RESOURCES = {
    "Prince.rsrc": {"LEVL", "SEQS", "SHAP", "SHPL", "CTBL", "NFNT"},
    "Kid.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Guard.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Rooftops.rsrc": {"PIEC", "SHAP", "CTBL"},
    "NIS.rsrc": {"SHAP", "CTBL", "TEXT"},
    "Title.rsrc": {"SHAP", "CTBL", "SCRP", "ANI "},
    "Desert.rsrc": {"CUST", "SHAP", "CTBL"},
}


def extract_assets(image_path, output_dir=ASSET_DIR, progress=lambda _text: None):
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
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".import-", dir=output_dir) as directory:
        staging = Path(directory)
        for name, resource in resources.items():
            (staging / name).write_bytes(resource)
        extract_audio(image, program, resources["Prince.rsrc"], staging / "audio", progress)
        progress("Recovering the original opening scenes...")
        extract_intro(image, program, resources["NIS.rsrc"], staging, progress)
        resources["intro.json"] = (staging / "intro.json").read_bytes()
        progress("Recovering the original voyage scenes...")
        extract_ending(image, program, resources["NIS.rsrc"], staging, progress)
        resources["ending.json"] = (staging / "ending.json").read_bytes()
        progress("Recovering the original recorded demo and credits...")
        extract_attract(program, resources, staging, progress)
        extract_credits_music(image, staging)
        resources["attract.json"] = (staging / "attract.json").read_bytes()
        # Audio is fully prepared before any installed resources are replaced.
        for path in (staging / "audio").rglob("*"):
            if path.is_file():
                name = path.relative_to(staging).as_posix()
                resources[name] = path.read_bytes()
        for name in resources:
            (output_dir / name).parent.mkdir(parents=True, exist_ok=True)
            (staging / name).replace(output_dir / name)
    return resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to the Macintosh PoP2 HFS image")
    parser.add_argument("--output", type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    try:
        resources = extract_assets(args.image, args.output, lambda message: print(message, flush=True))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Asset extraction failed: {error}\n")
    for name, resource in resources.items():
        if not name.startswith("audio/"):
            print(f"{name}: {len(resource):,} bytes")
    audio = [data for name, data in resources.items() if name.startswith("audio/")]
    print(f"audio/: {len(audio)} files, {sum(map(len, audio)):,} bytes")


if __name__ == "__main__":
    main()
