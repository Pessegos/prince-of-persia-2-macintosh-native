"""Windowed game entry; asset recovery uses the separate signed interpreter."""

if __name__ == '__main__':
    # Must run before parsing app arguments or importing gameplay. Spawned
    # ProcessPoolExecutor workers take PyInstaller's multiprocessing route.
    import multiprocessing
    multiprocessing.freeze_support()

    from pop2.packaged_app import main
    main()
