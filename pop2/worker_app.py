"""Headless import/cache dispatch for the signed bundled Python interpreter."""

import json
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['--import-assets']:
        from tools.extract_assets import main as extract

        sys.argv = [sys.argv[0], *argv[1:]]
        extract()
    elif argv[:1] == ['--warm-map-cache']:
        from pop2.development_map import warm_development_maps

        warm_development_maps()
    elif argv == ['--smoke-runtime']:
        from importlib import import_module
        from pop2.paths import PROJECT_DIR

        for module in ('PIL.Image', 'pygame.mixer', 'numpy', 'mido', 'unicorn'):
            import_module(module)
        print(json.dumps(dict(project=str(PROJECT_DIR), python=sys.version,
                              executable=sys.executable)), flush=True)
    elif argv == ['--smoke-pool']:
        from concurrent.futures import ProcessPoolExecutor
        import os
        from tools.workers import watch_parent

        with ProcessPoolExecutor(2, initializer=watch_parent) as pool:
            children = [future.result() for future in (pool.submit(os.getpid) for _ in range(4))]
        if not children or os.getpid() in children:
            raise RuntimeError('Signed runtime worker pool did not spawn')
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
            raise RuntimeError('Signed runtime native callback/stop failed')
        print(json.dumps(dict(native_callback=True)), flush=True)
    else:
        raise SystemExit('Unknown import/cache worker mode')
