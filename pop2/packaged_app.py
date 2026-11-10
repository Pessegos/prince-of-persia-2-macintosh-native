"""Portable executable dispatch and diagnostics (no gameplay rule changes)."""

import json
from pathlib import Path
import sys


def smoke_test():
    """Exercise bundled libraries/support art, then gameplay when imported."""
    import tkinter as tk
    from PIL import Image
    from pop2.paths import PROJECT_DIR
    from pop2.app_window import ICON_DIR
    import run_game

    errors = run_game.dependency_errors()
    if errors:
        raise RuntimeError('\n'.join(errors))
    support = Path(__file__).parent
    for name in ('cavern_retouch.png', 'save_quill.png', 'screenshot_lava.png'):
        with Image.open(support / name) as image:
            image.load()
    for name in ('cavern_retouch.json', 'lava_recess.json'):
        json.loads((support / name).read_text())
    if not (ICON_DIR / 'prince.ico').is_file():
        raise RuntimeError('Bundled application icon is missing')
    root = tk.Tk()
    root.withdraw()
    levels = []
    audio = None
    original = tk.Tk
    try:
        if not run_game.missing_assets():
            from pop2.audio import AudioEngine
            from pop2.scene_prototype import ScenePrototype
            tk.Tk = lambda: root
            audio = AudioEngine()
            scene = ScenePrototype(peaceful=True, audio=audio, with_intro=True)
            root.after(300, root.quit)
            root.mainloop()
            if scene.native_viewport.getbbox() is None:
                raise RuntimeError('Initial scene is blank')
            from pop2.caverns import scenery_available

            last = 15 if scenery_available(14) else 14
            for number in range(1, last):
                scene.load_level(number)
                scene.render()
                if scene.native_viewport.getbbox() is None:
                    raise RuntimeError(f'Level {number} is blank')
                levels.append(number)
    finally:
        tk.Tk = original
        if audio is not None:
            audio.close()
        root.destroy()
    print(json.dumps(dict(dependencies=True, support_art=True, tk=True, levels=levels,
                          project=str(PROJECT_DIR))), flush=True)


def smoke_import(image):
    """Test real first-run UI cancellation and completion without showing it."""
    import tkinter as tk
    from tkinter import filedialog
    from time import monotonic
    from pop2.paths import PROJECT_DIR
    from pop2.setup_game import GameSetup

    original_root, original_picker = tk.Tk, filedialog.askopenfilename
    times = {}
    try:
        filedialog.askopenfilename = lambda **_kwargs: image
        for cancel in (True, False):
            root = original_root()
            root.withdraw()
            tk.Tk = lambda: root
            setup = GameSetup(PROJECT_DIR)
            started = monotonic()
            cancelling = False
            failure = ''

            def progress(*_args):
                nonlocal cancelling
                if cancel and setup.status.get().startswith('Cavern scenery:') and not cancelling:
                    cancelling = True
                    root.after_idle(setup.close)

            setup.status.trace_add('write', progress)
            def check_error():
                nonlocal failure
                if not setup.importing and not setup.completed and not cancelling:
                    failure = setup.status.get()
                    setup.close()
                else:
                    root.after(100, check_error)

            root.after_idle(setup.choose)
            root.after(100, check_error)
            completed = setup.run()
            if failure:
                raise RuntimeError(f'Frozen import failed: {failure}')
            if completed != (not cancel) or setup.task.process is not None:
                raise RuntimeError('Frozen first-run import did not finish/stop correctly')
            if cancel and (not cancelling or list((PROJECT_DIR / 'assets').iterdir())):
                raise RuntimeError(f'Cancelled={cancelling}; remaining files: '
                                   f'{list((PROJECT_DIR / "assets").iterdir())}')
            times['cancel' if cancel else 'complete'] = round(monotonic() - started, 2)
    finally:
        tk.Tk, filedialog.askopenfilename = original_root, original_picker
    print(json.dumps(dict(import_seconds=times)), flush=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    from pop2.paths import OUTPUT_DIR

    # Windowed builds have no stdio. Keep actual diagnostics beside the game.
    if sys.stdout is None or sys.stderr is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stream = (OUTPUT_DIR / 'game.log').open('a', encoding='utf-8', buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    else:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

    if argv[:1] in (['--import-assets'], ['--warm-map-cache'], ['--smoke-pool'], ['--smoke-native']):
        if getattr(sys, 'frozen', False):
            import subprocess
            from pop2.child_process import runtime_command, worker_environment

            subprocess.run(runtime_command(*argv), env=worker_environment(), check=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            from pop2.worker_app import main as worker

            worker(argv)
    elif argv == ['--smoke-test']:
        smoke_test()
    elif len(argv) == 2 and argv[0] == '--smoke-import':
        smoke_import(argv[1])
    else:
        import run_game
        try:
            run_game.main(argv)
        except (Exception, SystemExit) as error:
            if isinstance(error, SystemExit) and not error.code:
                return
            import traceback
            traceback.print_exc()
            if Path(sys.executable).stem == 'PoP2Mac':
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, f'{error}\n\nDetails: {OUTPUT_DIR / "game.log"}',
                                                'Prince of Persia 2', 0x10)
            raise
