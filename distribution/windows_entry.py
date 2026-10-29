"""Frozen entry shared by the windowed game and its console worker helper."""

if __name__ == '__main__':
    # Must run before parsing app arguments or importing gameplay. Spawned
    # ProcessPoolExecutor workers take PyInstaller's multiprocessing route.
    import multiprocessing
    import sys
    multiprocessing.freeze_support()

    # The console helper's stdout carries import progress. Its pool children
    # use a windowed bootloader so spawning them cannot flash console windows.
    from pathlib import Path
    multiprocessing.set_executable(str(Path(sys.executable).with_name('PoP2Mac-worker.exe')))

    from pop2.packaged_app import main
    main()
