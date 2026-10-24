# -*- coding: utf-8 -*-
"""Paths, constants, logging and small helpers shared by every Sleepify module.

Other modules use  `from . import common as C`  and read  C.DATA_DIR, C.STATE_FILE ...  when they need them,
so tests can point those at a temporary folder.
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
from datetime import datetime

from . import VERSION  # noqa: F401  (re-exported)

APP_NAME = "Sleepify"
FROZEN = bool(getattr(sys, "frozen", False))
ROOT_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if FROZEN
            else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(rel):
    """Files shipped with the app (assets/...). Works from source and from the PyInstaller build."""
    return os.path.join(getattr(sys, "_MEIPASS", ROOT_DIR), rel)


def _data_dir():
    base = os.environ.get("SLEEPIFY_DATA_DIR") or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), "Sleepify")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    return base


DATA_DIR = _data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
STATE_FILE = os.path.join(DATA_DIR, "timer_state.json")
LOG_FILE = os.path.join(DATA_DIR, "log.txt")
ERROR_FILE = os.path.join(DATA_DIR, "error.log")
HISTORY_FILE = os.path.join(DATA_DIR, "history.jsonl")
ICON_DIR = os.path.join(DATA_DIR, "icons")
ICO_FILE = os.path.join(ICON_DIR, "app.ico")
BOT_PNG = os.path.join(ICON_DIR, "bot.png")
LEGACY_CONFIG = os.path.join(ROOT_DIR, "config.json")        # v0.x kept it next to the script

SINGLE_PORT = 47653                       # local port used to detect a running copy
MUTEX_NAME = "Sleepify_Single_Instance"   # the installer looks for this one
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAX_SECONDS = 24 * 3600
EXTEND_MINUTES = 10
CNW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# What a timer can do. Windows counts down shutdown/restart by itself (so they survive closing Sleepify);
# the others are run by Sleepify when the time is up.
ACTIONS = ("shutdown", "restart", "hibernate", "sleep", "lock", "display")
WINDOWS_TIMED = ("shutdown", "restart")
ACTION_NAME = {"shutdown": "Shutdown", "restart": "Restart", "hibernate": "Hibernate",
               "sleep": "Sleep", "lock": "Lock", "display": "Display off"}

TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")


def scrub(text):
    """Never let a bot token reach a log file or the screen."""
    return TOKEN_RE.sub("<token>", str(text))


_file_lock = threading.Lock()


def _append(path, line):
    try:
        with _file_lock, open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def log_event(text):
    _append(LOG_FILE, f"{datetime.now():%Y-%m-%d %H:%M:%S} | {scrub(text)}")


def log_error(text):
    _append(ERROR_FILE, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {scrub(text)}")


def add_history(kind, **fields):
    """One line per event in history.jsonl (used by the History page and /stats)."""
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind}
    rec.update({k: v for k, v in fields.items() if v is not None})
    _append(HISTORY_FILE, json.dumps(rec, ensure_ascii=False))


def read_history(limit=300):
    out = []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return out


def tail(path, lines=30):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


# ---------------------------------------------------------------- formatting / parsing
def fmt_hms(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def fmt_human(sec):
    sec = max(0, int(sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s and not h:
        parts.append(f"{s}s")
    return " ".join(parts) or "0s"


_DUR_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


def parse_duration(text):
    """'1h30m' / '45m' / '45m30s' / '90' (bare number = minutes) -> seconds, or None."""
    t_ = (text or "").strip().lower().replace(" ", "")
    if not t_:
        return None
    if t_.isdigit():
        return int(t_) * 60
    m = _DUR_RE.match(t_)
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


_CLOCK_RE = re.compile(r"^(\d{1,2})(?::?(\d{2}))?\s*(am|pm|a|p)?$", re.I)


def parse_clock(text):
    """'03:30' / '3:30pm' / '0330' / '15' -> (hour, minute) or None."""
    m = _CLOCK_RE.match((text or "").strip().lower().replace(".", ""))
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap.startswith("p") else 0)
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def default_device_name():
    try:
        return socket.gethostname() or "My PC"
    except OSError:
        return "My PC"


def version_tuple(text):
    nums = re.findall(r"\d+", str(text).split("-")[0])
    return tuple(int(n) for n in nums[:3]) or (0,)
