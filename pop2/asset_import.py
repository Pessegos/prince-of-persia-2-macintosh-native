"""Run first-use recovery outside Tk and publish only a completed import."""

from collections import deque
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event

from pop2.paths import PROJECT_DIR
from pop2.process_job import terminate_tree
from pop2.child_process import SINGLE_THREAD_BLAS, worker_command, worker_environment


# The stages the import reports (tools.extract_assets, then the installation
# by AssetImport), as listed by the game-files window, with their shares of
# its progress bar: drawing the level scenery takes most of an import.
STAGES = (
    ('image', 'Reading the game image', 3),
    ('scenery', 'Drawing the level scenery', 70),
    ('music', 'Preparing the music and sounds', 8),
    ('scenes', 'Preparing the cutscenes', 12),
    ('demo', 'Preparing the demo and credits', 3),
    ('install', 'Installing the files', 4),
)


def overall(stages):
    """The import's progress, 0-100, from `stages` ({stage: (done, total)})
    weighted by their STAGES shares."""
    share = 0.0
    for key, _label, weight in STAGES:
        done, total = stages.get(key, (0, 0))
        share += weight * (min(done, total) / total if total else 0.0)
    return 100 * share / sum(weight for *_rest, weight in STAGES)


class ImportCancelled(Exception):
    pass


class ImportFailed(ValueError):
    """The recovery process stopped; `kind` is its import_advice kind and
    `log` the file holding its output."""

    def __init__(self, kind, message, log):
        super().__init__(message)
        self.kind, self.log = kind, log


class AssetImport:
    def __init__(self, project):
        self.project = Path(project)
        self.cancelled = Event()
        self.process = None

    def cancel(self):
        self.cancelled.set()
        process = self.process
        if process is not None and process.poll() is None:
            try:
                # Worker pools and MIDI renderers end with the recovery.
                terminate_tree(process)
            except OSError:
                if process.poll() is None:
                    raise

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise ImportCancelled()

    def run(self, image_path, progress=lambda _text: None, steps=lambda _stage, _done, _total: None):
        """Import `image_path`. `progress(text)` receives the recovery's
        messages and `steps(stage, done, total)` its stages (see
        tools.extract_assets), ending with 'install' as files are installed."""
        self.check_cancelled()
        assets = self.project / 'assets'
        assets.mkdir(parents=True, exist_ok=True)
        log = self.project / 'rendered' / 'setup.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        # The parent owns this directory so even a terminated/crashed native
        # recovery process cannot leave its staging files installed or orphaned.
        with tempfile.TemporaryDirectory(prefix='.setup-', dir=assets) as directory:
            staging = Path(directory)
            command = worker_command('tools.extract_assets', Path(image_path).resolve(),
                                     '--output', staging.resolve(), '--progress-json')
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
            with log.open('w', encoding='utf-8') as output:
                output.write(f'Python: {sys.version}\n')
                output.flush()
                with subprocess.Popen(command, cwd=PROJECT_DIR, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                      errors='replace', env={**SINGLE_THREAD_BLAS, **worker_environment()},
                                      **options) as process:
                    self.process = process
                    errors = deque(maxlen=12)
                    kind, reported = 'failed', None
                    try:
                        if self.cancelled.is_set():
                            self.cancel()
                        for line in process.stdout:
                            output.write(line)
                            output.flush()
                            try:
                                event = json.loads(line)
                            except ValueError:
                                errors.append(line.rstrip())
                            else:
                                if not isinstance(event, dict):
                                    continue
                                if event.get('event') == 'progress':
                                    progress(event['message'])
                                elif event.get('event') == 'step':
                                    steps(event['stage'], event['done'], event['total'])
                                elif event.get('event') == 'error':
                                    kind, reported = event.get('kind', kind), event.get('message')
                        code = process.wait()
                    finally:
                        if process.poll() is None:
                            terminate_tree(process)
                            process.wait()
                        self.process = None
                self.check_cancelled()
                if code:
                    detail = reported or next((line for line in reversed(errors) if line.strip()),
                                              'Recovery failed.')
                    raise ImportFailed(kind, f'{detail}\nDetails: {log}', log)
            self.check_cancelled()
            progress('Installing prepared game files...')
            self.check_cancelled()
            files = [path for path in staging.rglob('*') if path.is_file()]
            steps('install', 0, len(files))
            for index, source in enumerate(files, 1):
                destination = assets / source.relative_to(staging)
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
                steps('install', index, len(files))
