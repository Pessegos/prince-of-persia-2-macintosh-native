"""Runtime and setup regression tests.

Importing this package (unittest discovery does, before any test module)
points POP2_USER_DATA at a temporary directory, so no test reads or writes
the player's real saves or screenshot preferences; subprocesses inherit it.
See tests/desktop.py for the shared-desktop mode.
"""

import atexit
import os
import shutil
import tempfile

if not os.environ.get("POP2_USER_DATA"):
    _user_data = tempfile.mkdtemp(prefix="pop2-test-user-data-")
    os.environ["POP2_USER_DATA"] = _user_data
    atexit.register(shutil.rmtree, _user_data, ignore_errors=True)
