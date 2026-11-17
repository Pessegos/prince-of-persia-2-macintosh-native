"""Extract the resource files required by the rooftop prototype."""

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile
from threading import Lock

from tools.extract_enemy_profiles import extract_bytes
from tools.extract_audio import extract_audio
# The scene recoveries are named in SCENES and looked up when a scene runs.
from tools.extract_intro import (  # noqa: F401
    TREE_VARIANTS, extract_carpet, extract_intro, extract_ending, extract_discovery, extract_temple,
    extract_throne, extract_tower, extract_final_spell, extract_happy, extract_trees,
)
from tools.extract_attract import extract_attract, extract_credits_music
from tools.extract_caverns import (
    LEVEL_MESSAGE, PREPARING_MESSAGE, SAVING_MESSAGE, extract_cavern_levels, scenery_name)
from tools.extract_slots import COMBINATIONS_MESSAGE, ROOMS_MESSAGE
from pop2.caverns import FINAL_LEVELS, TEMPLE_LEVELS, scenery_resource
from pop2.import_advice import HEAD, TAIL, ImageProblem, image_format, os_problem, problem, unreadable_volume
from pop2.mac_resources import NoHfsVolume, get_resource_fork, parse_resource_fork
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


def _pattern(message):
    # A progress message format, its {fields} matching numbers.
    return re.compile(re.sub(r'\\\{\w+\\\}', r'(\\d+)', re.escape(message)) + '$')


class SceneryProgress:
    """The level scenery's progress (0-TOTAL) from the cavern export's own
    messages, which it passes on.

    Shares of a parallel export on a 16-core reference import (19.8 s): the
    levels' rooms by 3.4 s, the floor-slot dependency renders by 13.5 s,
    their combinations by 18.6 s, then the saved files. A serial export
    (one worker) prepares every level, then draws and saves each in turn.
    """

    LEVEL, ROOMS, COMBINATIONS, SAVING = 0.15, 0.5, 0.3, 0.05
    SERIAL_PREPARING = 0.3
    TOTAL = 1000

    def __init__(self, progress, steps, levels, parallel=True):
        self.progress, self.steps, self.levels, self.parallel = progress, steps, levels, parallel
        self.prepared = self.started = self.saved = 0
        self.rooms = self.combinations = 0.0
        self.shown = -1
        self.lock = Lock()

    def fraction(self):
        if self.parallel:
            value = (self.LEVEL * self.prepared / self.levels + self.ROOMS * self.rooms
                     + self.COMBINATIONS * self.combinations + self.SAVING * self.saved / self.levels)
        else:
            # Every level is prepared before the first one is saved.
            prepared = self.levels if self.saved else max(0, self.started - 1)
            value = (self.SERIAL_PREPARING * prepared / self.levels
                     + (1 - self.SERIAL_PREPARING) * self.saved / self.levels)
        return min(1.0, value)

    def __call__(self, message):
        self.progress(message)
        with self.lock:
            if _LEVEL.match(message):
                self.prepared += 1
            elif message == SAVING_MESSAGE:
                self.saved += 1
            elif _PREPARING.match(message):
                self.started += 1
            else:
                for pattern, name in ((_ROOMS, 'rooms'), (_COMBINATIONS, 'combinations')):
                    match = pattern.match(message)
                    if match and int(match.group(2)):
                        setattr(self, name, int(match.group(1)) / int(match.group(2)))
            value = round(self.TOTAL * self.fraction())
            if value != self.shown:
                self.shown = value
                self.steps('scenery', value, self.TOTAL)


_LEVEL, _ROOMS, _COMBINATIONS, _PREPARING = map(
    _pattern, (LEVEL_MESSAGE, ROOMS_MESSAGE, COMBINATIONS_MESSAGE, PREPARING_MESSAGE))
# extract_audio's message after each prepared song: 'Preparing music: name (3/70)'.
_SONG = re.compile(r'Preparing music: .*\((\d+)/(\d+)\)$')


def _music_progress(progress, steps):
    def song(message):
        progress(message)
        match = _SONG.match(message)
        if match:
            steps('music', int(match.group(1)), int(match.group(2)))
    return song


def _no_steps(_stage, _done, _total):
    pass


def _validation_problem(error, image, found, reading):
    """The import_advice kind of a failed check of the game files."""
    head, tail = image[:HEAD], image[-TAIL:]
    if isinstance(error, NoHfsVolume):
        kind = image_format(head, tail)
        return 'damaged' if kind == 'hfs' else kind
    if isinstance(error, FileNotFoundError):
        return 'unsupported' if found else 'no_game'
    # Reading the catalog failed, or the files it holds are not the game's.
    return unreadable_volume(head, tail) if reading else 'unsupported'


def extract_assets(image_path, output_dir=ASSET_DIR, progress=lambda _text: None, *, contents=True,
                   steps=_no_steps):
    """Import the game files; {name: contents} of the installed files.

    With `contents` false the audio files' contents are not read back (None).
    `steps(stage, done, total)` follows the stages the game-files window
    lists: image, scenery, music, scenes and demo.
    """
    image = Path(image_path).read_bytes()
    # Validate the complete set before replacing any installed game files.
    resources, reading = {}, True
    try:
        for name in RESOURCE_FILES:
            resources[name] = get_resource_fork(image, name)
        reading = False
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
        raise ImageProblem(_validation_problem(error, image, bool(resources), reading),
                           f"This is not a supported Macintosh PoP2 disk image: {error}") from error
    steps('image', 1, 1)
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
        workers = os.cpu_count() or 1
        steps('scenery', 0, SceneryProgress.TOTAL)
        caverns = background.submit(
            extract_cavern_levels, program, sceneries, resources["Prince.rsrc"], staging,
            SceneryProgress(progress, steps, len(numbers), workers > 1), workers=workers)
        steps('music', 0, 1)
        extract_audio(image, program, resources["Prince.rsrc"], staging / "audio",
                      _music_progress(progress, steps))
        steps('music', 1, 1)
        # The scenes need the prepared songs and manifest; each works in its
        # own directory and is merged back in the serial order.
        scenes = {name: helpers.submit(_recover_scene, name, image_path, _scene_directory(staging, name))
                  for name, *_rest in SCENES}
        prepared = staging / "audio/manifest.json"
        base = json.loads(prepared.read_text(encoding="ascii")) if prepared.is_file() else {}
        manifest = json.loads(json.dumps(base))
        steps('scenes', 0, len(SCENES))
        for index, (name, message, _function, _arguments, files) in enumerate(SCENES):
            progress(message)
            scenes[name].result()
            steps('scenes', index + 1, len(SCENES))
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
        steps('demo', 0, 1)
        progress("Recovering the original recorded demo and credits...")
        demo.result()
        extract_credits_music(image, staging)
        resources["attract.json"] = (staging / "attract.json").read_bytes()
        steps('demo', 1, 1)
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
    # The cavern export reports from its own thread beside the music.
    lock = Lock()

    def emit(line):
        with lock:
            sys.stdout.write(line + '\n')
            sys.stdout.flush()

    def progress(message):
        emit(json.dumps({'event': 'progress', 'message': message}) if args.progress_json else message)

    def steps(stage, done, total):
        if args.progress_json:
            emit(json.dumps({'event': 'step', 'stage': stage, 'done': done, 'total': total}))

    try:
        resources = extract_assets(args.image, args.output, progress, contents=not args.progress_json,
                                   steps=steps)
    except (OSError, ValueError) as error:
        kind = (error.kind if isinstance(error, ImageProblem)
                else os_problem(error, args.image) if isinstance(error, OSError) else 'failed')
        if args.progress_json:
            emit(json.dumps({'event': 'error', 'kind': kind, 'message': str(error)}))
        advice = problem(kind)
        parser.exit(1, f"Asset extraction failed: {error}\n{advice.title} {advice.advice}\n")
    if args.progress_json:
        return
    for name, resource in resources.items():
        if not name.startswith("audio/"):
            print(f"{name}: {len(resource):,} bytes")
    audio = [data for name, data in resources.items() if name.startswith("audio/")]
    print(f"audio/: {len(audio)} files, {sum(map(len, audio)):,} bytes")


if __name__ == "__main__":
    main()
