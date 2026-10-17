"""Test setup: use a throw-away settings folder and keep GUI/tray libraries from needing a display."""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="sleepify_tests_")
os.environ["SLEEPIFY_DATA_DIR"] = _TMP                  # must be set before Sleepify is imported
if sys.platform != "win32":
    os.environ.setdefault("PYSTRAY_BACKEND", "dummy")   # pystray needs a backend on Linux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
