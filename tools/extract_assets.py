"""Extract the resource files required by the rooftop prototype."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import struct
import tempfile

from tools.extract_enemy_profiles import extract_bytes
from tools.extract_audio import extract_audio
from tools.extract_intro import (
    TREE_VARIANTS, extract_carpet, extract_intro, extract_ending, extract_discovery, extract_temple,
    extract_throne, extract_trees,
)
from tools.extract_attract import extract_attract, extract_credits_music
from tools.extract_caverns import extract_cavern_levels, scenery_name
from pop2.caverns import scenery_resource
from pop2.mac_resources import get_resource_fork, parse_resource_fork
from pop2.paths import ASSET_DIR


RESOURCE_FILES = ("Prince.rsrc", "Kid.rsrc", "Guard.rsrc", "Skeleton.rsrc", "Rooftops.rsrc", "NIS.rsrc", "Title.rsrc", "Desert.rsrc", "Caverns.rsrc", "NISTree.rsrc",
                  "Ruins.rsrc", "Head.rsrc", "TNIS1.rsrc", "TNIS2.rsrc", "TNIS3.rsrc", "ThroneNIS.rsrc",
                  "Horse.rsrc", "TempleNIS.rsrc")
REQUIRED_RESOURCES = {
    "Prince.rsrc": {"LEVL", "SEQS", "SHAP", "SHPL", "CTBL", "NFNT"},
    "Kid.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Guard.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Skeleton.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    "Rooftops.rsrc": {"PIEC", "SHAP", "CTBL"},
    "NIS.rsrc": {"SHAP", "CTBL", "TEXT", "ANI ", "SCRP"},
    "Title.rsrc": {"SHAP", "CTBL", "SCRP", "ANI "},
    "Desert.rsrc": {"CUST", "SHAP", "CTBL"},
    "Caverns.rsrc": {"PIEC", "SHAP", "CTBL"},
    "NISTree.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
    # Levels six and seven (environment 4) and their head/serpent set 5.
    "Ruins.rsrc": {"PIEC", "SHAP", "CTBL", "CUST"},
    "Head.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    # The carpet scene between levels five and six (NIS 1).
    "TNIS1.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
    "TNIS2.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
    "TNIS3.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
    # The vision at the throne in level eight (NIS 6).
    "ThroneNIS.rsrc": {"SHAP", "CTBL"},
    # The ride to the temple after level nine (NIS 2).
    "Horse.rsrc": {"SHAP", "CTBL"},
    "TempleNIS.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
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
    with (tempfile.TemporaryDirectory(prefix=".import-", dir=output_dir) as directory,
          ThreadPoolExecutor(2) as background):
        staging = Path(directory)
        for name, resource in resources.items():
            (staging / name).write_bytes(resource)
        # The recorded demo and the level scenery need only the program and
        # resource forks: they run beside the music and scenes. The scenery
        # is drawn by worker processes, the demo by a single simulation.
        demo = background.submit(extract_attract, program, dict(resources), staging, lambda _text: None)
        numbers = (3, 4, 5, 6, 7, 8, 9)
        caverns = background.submit(
            extract_cavern_levels, program, {number: resources[scenery_resource(number)] for number in numbers},
            resources["Prince.rsrc"], staging, progress, workers=os.cpu_count() or 1)
        extract_audio(image, program, resources["Prince.rsrc"], staging / "audio", progress)
        progress("Recovering the original opening scenes...")
        extract_intro(image, program, resources["NIS.rsrc"], staging, progress)
        resources["intro.json"] = (staging / "intro.json").read_bytes()
        progress("Recovering the original voyage scenes...")
        extract_ending(image, program, resources["NIS.rsrc"], staging, progress)
        resources["ending.json"] = (staging / "ending.json").read_bytes()
        progress("Recovering the original discovery scenes...")
        extract_discovery(image, program, resources["NIS.rsrc"], staging, progress)
        resources["discovery.json"] = (staging / "discovery.json").read_bytes()
        progress("Recovering the original tree scenes...")
        extract_trees(image, program, resources["NIS.rsrc"], resources["NISTree.rsrc"], staging, progress)
        progress("Recovering the original carpet scene...")
        extract_carpet(image, program, resources["NIS.rsrc"], resources, staging, progress)
        resources["carpet.json"] = (staging / "carpet.json").read_bytes()
        progress("Recovering the original vision at the throne...")
        extract_throne(image, program, resources["NIS.rsrc"], resources, staging, progress)
        resources["throne.json"] = (staging / "throne.json").read_bytes()
        progress("Recovering the original ride to the temple...")
        extract_temple(image, program, resources["NIS.rsrc"], resources, staging, progress)
        resources["temple.json"] = (staging / "temple.json").read_bytes()
        for variant in TREE_VARIANTS:
            resources[f"tree-{variant}.json"] = (staging / f"tree-{variant}.json").read_bytes()
        caverns.result()
        for number in numbers:
            resources[scenery_name(number)] = (staging / scenery_name(number)).read_bytes()
        progress("Recovering the original recorded demo and credits...")
        demo.result()
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
    parser.add_argument('--progress-json', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        def progress(message):
            print(json.dumps({'event': 'progress', 'message': message}) if args.progress_json else message,
                  flush=True)

        resources = extract_assets(args.image, args.output, progress)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Asset extraction failed: {error}\n")
    if args.progress_json:
        return
    for name, resource in resources.items():
        if not name.startswith("audio/"):
            print(f"{name}: {len(resource):,} bytes")
    audio = [data for name, data in resources.items() if name.startswith("audio/")]
    print(f"audio/: {len(audio)} files, {sum(map(len, audio)):,} bytes")


if __name__ == "__main__":
    main()
