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


class ImportCancelled(Exception):
    pass


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

    def run(self, image_path, progress=lambda _text: None):
        self.check_cancelled()
        assets = self.project / 'assets'
        assets.mkdir(parents=True, exist_ok=True)
        log = self.project / 'rendered' / 'setup.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        # The parent owns this directory so even a terminated/crashed native
        # recovery process cannot leave its staging files installed or orphaned.
        with tempfile.TemporaryDirectory(prefix='.setup-', dir=assets) as directory:
            staging = Path(directory)
            command = [sys.executable, '-u', '-m', 'tools.extract_assets', str(Path(image_path).resolve()),
                       '--output', str(staging.resolve()), '--progress-json']
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
            with log.open('w', encoding='utf-8') as output:
                output.write(f'Python: {sys.version}\n')
                output.flush()
                with subprocess.Popen(command, cwd=PROJECT_DIR, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                      errors='replace', **options) as process:
                    self.process = process
                    errors = deque(maxlen=12)
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
                                if isinstance(event, dict) and event.get('event') == 'progress':
                                    progress(event['message'])
                        code = process.wait()
                    finally:
                        if process.poll() is None:
                            terminate_tree(process)
                            process.wait()
                        self.process = None
                self.check_cancelled()
                if code:
                    detail = next((line for line in reversed(errors) if line.strip()), 'Recovery failed.')
                    raise ValueError(f'{detail}\nDetails: {log}')
            self.check_cancelled()
            progress('Installing prepared game files...')
            self.check_cancelled()
            files = [path for path in staging.rglob('*') if path.is_file()]
            for source in files:
                destination = assets / source.relative_to(staging)
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
