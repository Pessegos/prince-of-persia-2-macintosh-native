"""End a child process together with every process it started.

The import runs worker pools and MIDI renderers. On Windows the virtual
environment's launcher lets its child's own children break away from its
job, so terminating the launcher alone would leave them running and writing
into the staging directory that the parent is about to remove.
"""

import sys
import time


def _children(kernel32, ctypes, wintypes):
    """{parent PID: [child PID, ...]} from a process snapshot."""

    class Entry(ctypes.Structure):  # PROCESSENTRY32W
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('pid', wintypes.DWORD),
                    ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', ctypes.c_long), ('flags', wintypes.DWORD),
                    ('name', ctypes.c_wchar * 260)]

    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, wintypes.HANDLE(-1).value):
        return {}
    children = {}
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(Entry)
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            children.setdefault(entry.parent, []).append(entry.pid)
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return children


def terminate_tree(process, timeout=10):
    """Terminate `process` and (on Windows) its descendants; wait for them to exit."""
    pid = getattr(process, 'pid', None)
    root = getattr(process, '_handle', None)
    if sys.platform != 'win32' or not isinstance(pid, int) or not isinstance(root, int):
        process.terminate()
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.Process32FirstW.argtypes = kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, *(ctypes.POINTER(ctypes.c_uint64),) * 4)
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def created(handle):
        times = [ctypes.c_uint64() for _ in range(4)]
        if not kernel32.GetProcessTimes(handle, *map(ctypes.byref, times)):
            return None
        return times[0].value

    started = created(root)
    handles, ended, refused = [], {pid}, set()
    try:
        # A process may start another while the tree is being ended: repeat
        # until a snapshot finds nothing new below the root.
        while True:
            children = _children(kernel32, ctypes, wintypes)
            new = {child for parent in ended for child in children.get(parent, ())} - ended - refused
            if not new:
                break
            for child in new:
                # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE
                handle = kernel32.OpenProcess(0x00101001, False, child)
                when = handle and created(handle)
                # A recorded parent PID may have been reused: descendants
                # are never older than the root.
                if not handle or started is None or when is None or when < started:
                    if handle:
                        kernel32.CloseHandle(handle)
                    refused.add(child)
                    continue
                kernel32.TerminateProcess(handle, 1)
                handles.append(handle)
                ended.add(child)
        process.terminate()
        # Termination is asynchronous: wait until their files are closed.
        deadline = time.monotonic() + timeout
        for handle in handles:
            kernel32.WaitForSingleObject(handle, max(0, int((deadline - time.monotonic()) * 1000)))
    finally:
        for handle in handles:
            kernel32.CloseHandle(handle)
