"""Windowless import for launchers: `PoP2Mac.exe --prepare --game=IMAGE`.

A launcher (RecompLauncher, a script) runs it once the player has picked a
disk image. It imports the image exactly as the game-files window does, into
the same folder, prints `progress <0-1> <text>` lines while it works and
exits 0 when the game files are ready, 1 when the image cannot be used (the
reason is printed, as the window would say it) and 2 for a missing --game.
Without --prepare nothing changes: the game opens its own window as before.
From the sources: python -m pop2.prepare_game --game=IMAGE
"""

from pathlib import Path
import sys

from pop2.asset_import import STAGES, AssetImport, ImportCancelled, ImportFailed, overall
from pop2.import_advice import os_problem, preflight, problem
from pop2.paths import PROJECT_DIR
from pop2.preferences import remember

LABELS = {key: label for key, label, _weight in STAGES}


def game_argument(argv):
    """The image named by `--game=PATH` or `--game PATH`, or None."""
    for index, item in enumerate(argv):
        if item.startswith('--game='):
            return item.split('=', 1)[1] or None
        if item == '--game' and index + 1 < len(argv):
            return argv[index + 1]
    return None


class Progress:
    """Prints a `progress` line whenever the shown fraction or text changes."""

    def __init__(self, output):
        self.output = output
        self.stages = {}
        self.shown = None
        self.text = 'Reading the game image'

    def say(self, text=None):
        if text:
            self.text = ' '.join(text.split())
        line = f'progress {overall(self.stages) / 100:.3f} {self.text}'
        if line != self.shown:
            self.shown = line
            print(line, file=self.output, flush=True)

    def step(self, stage, done, total):
        self.stages[stage] = (done, total)
        # A new stage names itself; its own messages follow.
        self.say(LABELS.get(stage) if done == 0 else None)


def report_problem(kind, output, detail=''):
    advice = problem(kind)
    message = f'{advice.title} {advice.advice}'
    print(f'error {message}', file=output, flush=True)
    if detail:
        print(detail, file=sys.stderr, flush=True)
    return 1


def prepare(argv, project=PROJECT_DIR, output=None, task=None):
    """Import the image named in `argv` into `project`; the exit code."""
    output = output or sys.stdout
    image = game_argument(argv)
    if image is None:
        print('error Name the disk image with --game=PATH.', file=output, flush=True)
        return 2
    kind = preflight(image, project)
    if kind:
        return report_problem(kind, output)
    progress = Progress(output)
    progress.say()
    try:
        (task or AssetImport(project)).run(image, progress.say, progress.step)
    except ImportCancelled:
        return report_problem('failed', output)
    except ImportFailed as error:
        return report_problem(error.kind, output, str(error))
    except OSError as error:
        return report_problem(os_problem(error, image), output, str(error))
    # The game-files window offers this image again when a later version
    # needs the files prepared anew.
    remember(game_image=str(Path(image).resolve()))
    print('progress 1.000 Game files ready', file=output, flush=True)
    return 0


def main(argv=None):
    return prepare(list(sys.argv[1:] if argv is None else argv))


if __name__ == '__main__':
    sys.exit(main())
