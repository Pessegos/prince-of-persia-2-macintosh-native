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
            for number in range(1, 10):
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

    if argv[:1] == ['--import-assets']:
        from tools.extract_assets import main as extract
        sys.argv = [sys.argv[0], *argv[1:]]
        extract()
    elif argv[:1] == ['--warm-map-cache']:
        from pop2.development_map import warm_development_maps
        warm_development_maps()
    elif argv == ['--smoke-test']:
        smoke_test()
    elif len(argv) == 2 and argv[0] == '--smoke-import':
        smoke_import(argv[1])
    elif argv == ['--smoke-pool']:
        from concurrent.futures import ProcessPoolExecutor
        import os
        from tools.workers import watch_parent
        with ProcessPoolExecutor(2, initializer=watch_parent) as pool:
            children = [future.result() for future in (pool.submit(os.getpid) for _ in range(4))]
        if not children or os.getpid() in children:
            raise RuntimeError('Frozen worker pool did not spawn')
        print(json.dumps(dict(worker_processes=len(set(children)))), flush=True)
    elif argv == ['--smoke-native']:
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
        from unicorn.m68k_const import UC_CPU_M68K_M68020
        machine = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        machine.ctl_set_cpu_model(UC_CPU_M68K_M68020)
        machine.mem_map(0x1000, 0x1000)
        machine.mem_write(0x1000, bytes.fromhex('4e714e71'))
        calls = []
        def stop(cpu, address, size, user):
            calls.append(address)
            cpu.emu_stop()
        machine.hook_add(UC_HOOK_CODE, stop)
        machine.emu_start(0x1000, 0x1004)
        if calls != [0x1000]:
            raise RuntimeError('Unicorn callback/stop smoke failed')
        print(json.dumps(dict(native_callback=True)), flush=True)
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
