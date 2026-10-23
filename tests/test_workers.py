import os
import subprocess
import sys
import textwrap
import time
import unittest
from unittest.mock import Mock

from pop2.paths import PROJECT_DIR
from pop2.process_job import terminate_tree

# The parent leaves without shutting its pool down, as a terminated import does.
PROBE = textwrap.dedent('''
    import os
    from concurrent.futures import ProcessPoolExecutor
    from tools.workers import watch_parent

    if __name__ == '__main__':
        pool = ProcessPoolExecutor(2, initializer=watch_parent)
        print(*{pool.submit(os.getpid).result() for _ in range(8)}, flush=True)
        os._exit(0)
''')

GRANDPARENT = textwrap.dedent('''
    import subprocess, sys, time
    grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    print(grandchild.pid, flush=True)
    time.sleep(60)
''')


def running(pid):
    if sys.platform == 'win32':
        import ctypes

        kernel32 = ctypes.WinDLL('kernel32')
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) != 0  # WAIT_OBJECT_0
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        # A finished child of the vanished parent is reaped by init.
        with open(f'/proc/{pid}/stat') as stat:
            return stat.read().split(')')[-1].split()[0] != 'Z'
    except OSError:
        return True


class WorkerTests(unittest.TestCase):
    def test_pool_workers_exit_when_their_parent_ends_without_shutdown(self):
        result = subprocess.run([sys.executable, '-c', PROBE], cwd=PROJECT_DIR, capture_output=True,
                                text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        pids = [int(pid) for pid in result.stdout.split()]
        self.assertTrue(pids)
        deadline = time.monotonic() + 20
        while any(map(running, pids)) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual([pid for pid in pids if running(pid)], [])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows process trees')
    def test_terminating_the_tree_ends_processes_the_child_started(self):
        child = subprocess.Popen([sys.executable, '-c', GRANDPARENT], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.stdout.close)
        grandchild = int(child.stdout.readline())
        self.assertTrue(running(grandchild))
        terminate_tree(child)
        child.wait()
        self.assertFalse(running(grandchild))

    def test_a_mock_process_is_only_terminated(self):
        process = Mock()
        terminate_tree(process)
        process.terminate.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
