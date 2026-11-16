"""Extract the resource files required by the rooftop prototype."""

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile

from tools.extract_enemy_profiles import extract_bytes
from tools.extract_audio import extract_audio
# The scene recoveries are named in SCENES and looked up when a scene runs.
from tools.extract_intro import (  # noqa: F401
    TREE_VARIANTS, extract_carpet, extract_intro, extract_ending, extract_discovery, extract_temple,
    extract_throne, extract_tower, extract_final_spell, extract_happy, extract_trees,
)
from tools.extract_attract import extract_attract, extract_credits_music
from tools.extract_caverns import extract_cavern_levels, scenery_name
from pop2.caverns import FINAL_LEVELS, TEMPLE_LEVELS, scenery_resource
from pop2.mac_resources import get_resource_fork, parse_resource_fork
from pop2.child_process import SINGLE_THREAD_BLAS
from pop2.paths import ASSET_DIR
from tools.workers import background_worker


RESOURCE_FILES = ("Prince.rsrc", "Kid.rsrc", "Guard.rsrc", "Skeleton.rsrc", "Rooftops.rsrc", "NIS.rsrc", "Title.rsrc", "Desert.rsrc", "Caverns.rsrc", "NISTree.rsrc",
                  "Ruins.rsrc", "Head.rsrc", "TNIS1.rsrc", "TNIS2.rsrc", "TNIS3.rsrc", "ThroneNIS.rsrc",
                  "Horse.rsrc", "TempleNIS.rsrc", "Temple.rsrc", "Birdhead.rsrc",
                  "FlameSword.rsrc", "Jinnee.rsrc", "TowerNIS.rsrc", "Final.rsrc", "Happy.rsrc")
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
    # Levels 10-13 (environment 2).
    "Temple.rsrc": {"PIEC", "SHAP", "CTBL", "CUST"},
    # The temple's opponents (set 7).
    "Birdhead.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    # Level twelve's flaming sword (opponent set 1, actor type 10).
    "FlameSword.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    # The genie of level twelve's flask (opponent set 9, actor type 12).
    "Jinnee.rsrc": {"FRAM", "AFRM", "SHAP", "SHPL", "CTBL"},
    # The flight to the tower after level thirteen (NIS 3), whose last shot
    # draws level fourteen's environment (Final.rsrc).
    "TowerNIS.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
    "Final.rsrc": {"PIEC", "SHAP", "CTBL", "CUST"},
    "Happy.rsrc": {"SHAP", "CTBL", "ANI ", "SCRP"},
}


# The story scenes, in the order a serial import recovers them: (name,
# progress message, recovery function, its resource-file arguments after
# the image and program (ALL_FILES: every file), files it adds besides
# its audio).
ALL_FILES = None
SCENES = (
    ("intro", "Recovering the original opening scenes...", "extract_intro", ("NIS.rsrc",), ("intro.json",)),
    ("ending", "Recovering the original voyage scenes...", "extract_ending", ("NIS.rsrc",), ("ending.json",)),
    ("discovery", "Recovering the original discovery scenes...", "extract_discovery", ("NIS.rsrc",),
     ("discovery.json",)),
    ("trees", "Recovering the original tree scenes...", "extract_trees", ("NIS.rsrc", "NISTree.rsrc"), ()),
    ("carpet", "Recovering the original carpet scene...", "extract_carpet", ("NIS.rsrc", ALL_FILES),
     ("carpet.json",)),
    ("throne", "Recovering the original vision at the throne...", "extract_throne", ("NIS.rsrc", ALL_FILES),
     ("throne.json",)),
    ("temple", "Recovering the original ride to the temple...", "extract_temple", ("NIS.rsrc", ALL_FILES),
     ("temple.json",)),
    ("tower", "Recovering the original flight to the tower...", "extract_tower", ("NIS.rsrc", ALL_FILES),
     ("tower.json",)),
    ("final_spell", "Recovering Jaffar's spell scene...", "extract_final_spell", ("NIS.rsrc", "Happy.rsrc"),
     ("final_spell.json",)),
    ("happy", "Recovering the happy ending...", "extract_happy", ("NIS.rsrc", "Happy.rsrc"), ("happy.json",)),
)
# Audio files every scene reads (never writes): the song MIDIs and the
# renderer's instrument bank.
SHARED_AUDIO = ("instruments.json", "instrument-*.wav", "cue-*.mid")


def _image_files(image_path):
    image = Path(image_path).read_bytes()
    return (image, get_resource_fork(image, "Prince of Persia 2", "APPL"),
            {name: get_resource_fork(image, name) for name in RESOURCE_FILES})


def _recorded_demo(image_path, output):
    """extract_attract in its own process: the simulation is pure Python and,
    as a thread, would share the importer's interpreter lock with the scenes."""
    _image, program, files = _image_files(image_path)
    extract_attract(program, files, output, lambda _text: None)


def _recover_scene(name, image_path, output):
    """One story scene into its own directory (a copy of the prepared audio
    manifest): the scenes are recovered side by side by worker processes."""
    image, program, files = _image_files(image_path)
    _name, _message, function, arguments, _files = next(scene for scene in SCENES if scene[0] == name)
    globals()[function](image, program, *(files if argument is ALL_FILES else files[argument]
                                           for argument in arguments), Path(output), lambda _text: None)


def _helper_pool():
    """The processes for the recorded demo and the story scenes, below
    normal priority beside the cavern workers (whose work takes longest)."""
    return ProcessPoolExecutor(SCENE_WORKERS, initializer=background_worker)


def _scene_directory(staging, name):
    """A private directory for scene `name`, sharing the prepared audio."""
    directory = staging / ".scenes" / name
    audio = directory / "audio"
    audio.mkdir(parents=True)
    if (staging / "audio/manifest.json").is_file():
        shutil.copyfile(staging / "audio/manifest.json", audio / "manifest.json")
    for pattern in SHARED_AUDIO:
        for path in (staging / "audio").glob(pattern):
            try:
                os.link(path, audio / path.name)
            except OSError:
                shutil.copyfile(path, audio / path.name)
    return directory


def _merge_scene(staging, directory, manifest, base):
    """Add a scene's files and manifest entries as if it had run in `staging`.

    Each scene started from the `base` manifest, so the entries it set are
    the ones it added or changed. Applied in scene order, they give the
    manifest (and key order) of one directory filled scene after scene.
    """
    private = directory / "audio/manifest.json"
    private = json.loads(private.read_text(encoding="ascii")) if private.is_file() else {}
    for key, value in private.items():
        if key not in base:
            manifest.setdefault(key, {}).update(value)
        elif isinstance(value, dict):
            manifest[key].update((name, entry) for name, entry in value.items()
                                 if name not in base[key] or base[key][name] != entry)
        elif value != base[key]:
            manifest[key] = value
    shared = {path.name for pattern in SHARED_AUDIO for path in (staging / "audio").glob(pattern)}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if not path.is_file() or relative.as_posix() == "audio/manifest.json" or (
                relative.parent.as_posix() == "audio" and relative.name in shared):
            continue
        (staging / relative).parent.mkdir(parents=True, exist_ok=True)
        path.replace(staging / relative)


# Processes for the recorded demo and the story scenes.
SCENE_WORKERS = 4


def extract_assets(image_path, output_dir=ASSET_DIR, progress=lambda _text: None, *, contents=True):
    """Import the game files; {name: contents} of the installed files.

    With `contents` false the audio files' contents are not read back (None).
    """
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
    image_path = Path(image_path).resolve()
    with (tempfile.TemporaryDirectory(prefix=".import-", dir=output_dir) as directory,
          ThreadPoolExecutor(1) as background, _helper_pool() as helpers):
        staging = Path(directory)
        for name, resource in resources.items():
            (staging / name).write_bytes(resource)
        # The recorded demo and the level scenery need only the program and
        # resource forks: they run beside the music and scenes. The scenery
        # is drawn by worker processes, the demo by a single simulation.
        demo = helpers.submit(_recorded_demo, image_path, staging)
        numbers = (3, 4, 5, 6, 7, 8, 9, *TEMPLE_LEVELS, *FINAL_LEVELS)
        # A temple CUST image can come from Kid.rsrc (level 13's room 4).
        sceneries = {number: (resources[scenery_resource(number)], resources["Kid.rsrc"])
                     if number in TEMPLE_LEVELS else resources[scenery_resource(number)]
                     for number in numbers}
        caverns = background.submit(
            extract_cavern_levels, program, sceneries,
            resources["Prince.rsrc"], staging, progress, workers=os.cpu_count() or 1)
        extract_audio(image, program, resources["Prince.rsrc"], staging / "audio", progress)
        # The scenes need the prepared songs and manifest; each works in its
        # own directory and is merged back in the serial order.
        scenes = {name: helpers.submit(_recover_scene, name, image_path, _scene_directory(staging, name))
                  for name, *_rest in SCENES}
        prepared = staging / "audio/manifest.json"
        base = json.loads(prepared.read_text(encoding="ascii")) if prepared.is_file() else {}
        manifest = json.loads(json.dumps(base))
        for name, message, _function, _arguments, files in SCENES:
            progress(message)
            scenes[name].result()
            _merge_scene(staging, staging / ".scenes" / name, manifest, base)
            for file in files:
                resources[file] = (staging / file).read_bytes()
        if manifest:
            prepared.write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
        shutil.rmtree(staging / ".scenes")
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
                resources[name] = path.read_bytes() if contents else None
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
    # For the worker processes started below (see pop2.child_process).
    for name, value in SINGLE_THREAD_BLAS.items():
        os.environ.setdefault(name, value)
    try:
        def progress(message):
            print(json.dumps({'event': 'progress', 'message': message}) if args.progress_json else message,
                  flush=True)

        resources = extract_assets(args.image, args.output, progress, contents=not args.progress_json)
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
