# -*- coding: utf-8 -*-
"""Everything that touches Windows: running actions, keep-awake, autostart, screenshots, admin rights."""
import io
import os
import socket
import subprocess
import sys
import threading

from . import common as C

try:
    import winsound
except ImportError:  # not Windows
    winsound = None
try:
    import winreg
except ImportError:  # not Windows
    winreg = None
try:
    import ctypes
    from ctypes import wintypes
except ImportError:  # pragma: no cover
    ctypes = None

IS_WINDOWS = os.name == "nt"

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


# ---------------------------------------------------------------- admin rights
def is_admin():
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _shell_execute(verb, program, params, show=1):
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(None, verb, program, params, None, show)
        return rc > 32
    except Exception as e:
        C.log_error(f"ShellExecute failed: {e}")
        return False


def relaunch_as_admin():
    """Starts a new elevated copy (Windows shows the permission prompt). The caller then exits."""
    if not IS_WINDOWS:
        return False
    if C.FROZEN:
        program, params = sys.executable, "--restarted"
    else:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        program = pyw if os.path.exists(pyw) else sys.executable
        params = f'"{os.path.join(C.ROOT_DIR, "Sleepify.py")}" --restarted'
    return _shell_execute("runas", program, params)


def enable_hibernate_as_admin():
    return IS_WINDOWS and _shell_execute("runas", "powercfg.exe", "/h on", show=0)


# ---------------------------------------------------------------- keep awake / screenshot / windows
def set_keep_awake(on):
    """Tell Windows not to go to sleep (the screen may still turn off). Call from one thread only."""
    if not IS_WINDOWS:
        return False
    try:
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception as e:
        C.log_error(f"keep-awake failed: {e}")
        return False


def capture_screenshot(max_width=1600, quality=80):
    """JPEG bytes of the main screen."""
    from PIL import ImageGrab
    img = ImageGrab.grab().convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def visible_windows():
    """{pid: window title} for every visible top-level window (what Task Manager calls 'Apps')."""
    found = {}
    if not IS_WINDOWS:
        return found
    try:
        user32 = ctypes.windll.user32
        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                n = user32.GetWindowTextLengthW(hwnd)
                if n > 0:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    user32.GetWindowTextW(hwnd, buf, n + 1)
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    found.setdefault(pid.value, buf.value)
            return True
        user32.EnumWindows(EnumProc(cb), 0)
    except Exception as e:
        C.log_error(f"could not list windows: {e}")
    return found


# ---------------------------------------------------------------- start with Windows / shortcuts
def launch_target():
    """(program, arguments) that start Sleepify - the exe when installed, pythonw + script from source."""
    if C.FROZEN:
        return sys.executable, ""
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return exe, f'"{os.path.join(C.ROOT_DIR, "Sleepify.py")}"'


def autostart_command():
    target, args = launch_target()
    return " ".join(p for p in (f'"{target}"', args, "--hidden") if p)


def autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, C.RUN_KEY) as k:
            winreg.QueryValueEx(k, C.APP_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    if winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, C.RUN_KEY) as k:
            if enabled:
                winreg.SetValueEx(k, C.APP_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, C.APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        C.log_error(f"could not change the Start-with-Windows setting: {e}")
        return False


def _ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, creationflags=C.CNW)


def _q(text):
    """PowerShell single-quoted string literal."""
    return "'" + str(text).replace("'", "''") + "'"


def install_shortcuts():
    """From source: Desktop icon + start with Windows (no admin needed)."""
    from .icons import build_icons
    build_icons()
    target, args = launch_target()
    icon = f"{sys.executable},0" if C.FROZEN else C.ICO_FILE
    ps = f"""
$ErrorActionPreference = 'Stop'
$w = New-Object -ComObject WScript.Shell
$lnk = $w.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sleepify.lnk'))
$lnk.TargetPath = {_q(target)}
$lnk.Arguments = {_q(args)}
$lnk.WorkingDirectory = {_q(C.ROOT_DIR)}
$lnk.IconLocation = {_q(icon)}
$lnk.Description = 'Sleepify - PC sleep timer'
$lnk.Save()
Write-Output ('Created: ' + $lnk.FullName)
$old = Join-Path ([Environment]::GetFolderPath('Startup')) 'Sleepify.lnk'
if (Test-Path $old) {{ Remove-Item $old }}
"""
    try:
        r = _ps(ps)
    except OSError as e:
        print(f"Could not run PowerShell: {e}")
        return 1
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print((r.stderr or "").strip())
        return 1
    if not set_autostart(True):
        print("The desktop icon was created, but 'start with Windows' could not be set.")
        return 1
    print("\nDone. Double-click the Sleepify icon on your Desktop. It also starts by itself "
          "(hidden in the tray) every time you log in to Windows.")
    return 0


def remove_shortcuts():
    set_autostart(False)
    ps = """
$ErrorActionPreference = 'SilentlyContinue'
foreach ($d in @('Desktop', 'Startup')) {
  $p = Join-Path ([Environment]::GetFolderPath($d)) 'Sleepify.lnk'
  if (Test-Path $p) { Remove-Item $p; Write-Output ('Removed: ' + $p) }
}
"""
    try:
        r = _ps(ps)
    except OSError as e:
        print(f"Could not run PowerShell: {e}")
        return 1
    print((r.stdout or "").strip() or "Removed the start-with-Windows entry.")
    return 0


# ---------------------------------------------------------------- hooks used by the timer core
class Hooks:
    """Everything the timer core needs from the outside world (tests replace this class)."""

    def __init__(self):
        self.tray = None
        self.bot = None

    def run(self, cmd):
        try:
            return subprocess.run(cmd, capture_output=True, creationflags=C.CNW, timeout=20).returncode
        except Exception as e:
            C.log_error(f"command {cmd} failed: {e}")
            return 1

    def perform(self, action):
        """Runs an action that Sleepify itself carries out. Returns True on success."""
        try:
            if action == "hibernate":
                return self.run(["shutdown", "/h"]) == 0
            if not IS_WINDOWS:
                return False
            if action == "sleep":
                return bool(ctypes.windll.powrprof.SetSuspendState(False, False, False))
            if action == "lock":
                return bool(ctypes.windll.user32.LockWorkStation())
            if action == "display":          # SC_MONITORPOWER, 2 = off
                ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)
                return True
        except Exception as e:
            C.log_error(f"action {action} failed: {e}")
        return False

    def beep(self, freq, ms):
        if winsound is None:
            return

        def _go():
            try:
                winsound.Beep(freq, ms)
            except Exception as e:
                C.log_error(f"beep failed: {e}")
        threading.Thread(target=_go, daemon=True).start()

    def toast(self, title, message):
        if self.tray is None:
            return
        try:
            self.tray.notify(message, title)
        except Exception as e:
            C.log_error(f"notification failed: {e}")

    def tg(self, text, buttons=None):
        if self.bot is not None:
            self.bot.send(text, buttons=buttons)

    def log(self, text):
        C.log_event(text)

    def history(self, kind, **fields):
        C.add_history(kind, **fields)

    def keep_awake(self, on):
        return set_keep_awake(on)

    def hibernate_ok(self):
        """False only when Windows says hibernation is switched off; None = could not tell."""
        if winreg is None:
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power") as k:
                return bool(winreg.QueryValueEx(k, "HibernateEnabled")[0])
        except OSError:
            return None


# ---------------------------------------------------------------- single instance
_mutex_handle = None


def hold_mutex():
    """Named mutex so the installer can tell Sleepify is running (and ask to close it)."""
    global _mutex_handle
    try:
        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, C.MUTEX_NAME)
    except Exception:
        _mutex_handle = None


def _try_bind():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        # POSIX only: allow re-binding right after a restart. On Windows this option would let two copies
        # share the port, so it must NOT be set there.
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("127.0.0.1", C.SINGLE_PORT))
        srv.listen(5)
        return srv
    except OSError:
        srv.close()
        return None


def single_instance(wait_seconds=0):
    """Returns (server_socket, status): status is 'primary', 'forwarded' or 'busy'.
    wait_seconds > 0: keep trying to bind for that long first (used when Sleepify restarts itself)."""
    import time
    end = time.time() + wait_seconds
    while True:
        srv = _try_bind()
        if srv:
            return srv, "primary"
        if time.time() >= end:
            break
        time.sleep(0.3)
    try:
        with socket.create_connection(("127.0.0.1", C.SINGLE_PORT), timeout=3) as c:
            c.sendall(b"SLEEPIFY_SHOW\n")
            c.settimeout(3)
            if c.recv(16).strip() == b"OK":
                return None, "forwarded"
    except OSError:
        pass
    return None, "busy"


def listen_for_show(srv, inbox, stop):
    srv.settimeout(1.0)
    while not stop.is_set():
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        with conn:
            try:
                conn.settimeout(2)
                if conn.recv(64).startswith(b"SLEEPIFY_SHOW"):
                    conn.sendall(b"OK\n")
                    inbox.put(("show",))
            except OSError:
                pass
