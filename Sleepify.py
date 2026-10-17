# -*- coding: utf-8 -*-
"""
Sleepify - PC sleep timer (Shutdown / Hibernate) with a tray icon and Telegram remote control.
License: MIT

  Run from source          :  py Sleepify.py        (use pyw to hide the console window)
  Start hidden in the tray :  Sleepify.py --hidden
  From source only         :  py Sleepify.py --install     desktop icon + start with Windows
                              py Sleepify.py --uninstall   remove them again

Settings, logs and timer state live in  %APPDATA%\\Sleepify
(set the SLEEPIFY_DATA_DIR environment variable to use another folder).
"""
import ctypes
import json
import math
import os
import queue
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime

# pythonw.exe / windowed exe have no stdout / stderr
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import requests
import customtkinter as ctk
import pystray
from PIL import Image, ImageChops, ImageDraw
from tkinter import messagebox

try:
    import winsound
except ImportError:  # not Windows
    winsound = None
try:
    import winreg
except ImportError:  # not Windows
    winreg = None

# --------------------------------------------------------------------------
# Paths and constants
# --------------------------------------------------------------------------
APP_NAME = "Sleepify"
VERSION = "1.0.0"
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))


def resource_path(rel):
    """Files shipped with the app (assets/...). Works from source and from the PyInstaller build."""
    return os.path.join(getattr(sys, "_MEIPASS", APP_DIR), rel)


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
ICON_DIR = os.path.join(DATA_DIR, "icons")
ICO_FILE = os.path.join(ICON_DIR, "app.ico")
BOT_PNG = os.path.join(ICON_DIR, "bot.png")
LEGACY_CONFIG = os.path.join(APP_DIR, "config.json")     # v0.x kept it next to the script

SINGLE_PORT = 47653           # local port used to detect a running copy
MUTEX_NAME = "Sleepify_Single_Instance"   # the installer looks for this one
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAX_SECONDS = 24 * 3600
EXTEND_MINUTES = 10
CNW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ACTION_NAME = {"S": "Shutdown", "H": "Hibernate"}
RES = Image.Resampling.LANCZOS

# colors
BG = "#0d1033"
CARD = "#171b4d"
TEXT = "#ffffff"
GRAY = "#8d93bd"
GREEN = "#7dff5a"
AMBER = "#ffb84d"
RED = "#ff5a5a"
BTN = "#2a2f73"
BTN_HOVER = "#3a4094"
GREEN_BTN = "#5fe03d"
GREEN_BTN_HOVER = "#7dff5a"
RED_BTN = "#7a2a3a"
RED_BTN_HOVER = "#a03548"


# --------------------------------------------------------------------------
# Messages sent to Telegram (English / Arabic). The window itself is English only.
# --------------------------------------------------------------------------
STR = {
    "en": {
        "help": (
            "🤖 Sleepify - commands:\n\n"
            "/status - time left\n"
            "/shutdown 1h30m - shutdown timer\n"
            "/hibernate 45m - hibernate timer\n"
            "/extend 10m - add time (default 10 min)\n"
            "/cancel - cancel the timer\n"
            "/help - this list\n\n"
            "Time: h = hours, m = minutes, s = seconds, e.g. 1h30m, 45m or 45m30s.\n"
            "A bare number means minutes (/shutdown 90)."),
        "cmd_status": "Time left",
        "cmd_shutdown": "Shutdown timer, e.g. /shutdown 1h30m",
        "cmd_hibernate": "Hibernate timer, e.g. /hibernate 45m",
        "cmd_extend": "Add time, e.g. /extend 10m",
        "cmd_cancel": "Cancel the timer",
        "cmd_help": "Show the commands",
        "status_none": "🔴 No timer is running.",
        "status_running": "🟢 Timer running\nAction: {action}\nTime left: {left}\nRuns at: {at}",
        "bad_duration": "❌ Please write the time like this: /{cmd} 1h30m or /{cmd} 45m",
        "bad_duration_extend": "❌ Please write the time like this: /extend 10m",
        "started": "✅ Timer started: {action} in {dur}\nAt: {at}",
        "replaced": "(the previous timer was replaced)",
        "hib_note": "⚠️ Keep Sleepify running in the tray. If it is closed, the Hibernate timer is cancelled.",
        "extended": "⏰ Added {dur}. Time left {left}, runs at {at}",
        "cancelled": "✅ Timer cancelled.",
        "cancel_none": "ℹ️ There is no timer to cancel.",
        "unknown_cmd": "I don't know that command 🤔 Send /help",
        "warn_shutdown": "⚠️ {mins} min left, then the PC shuts down. Save your work! 💾",
        "warn_hibernate": "⚠️ {mins} min left, then the PC hibernates. Save your work! 💾",
        "final": "🔔 {action} starts now!",
        "cancelled_pc": "✅ Timer cancelled from the PC.",
        "hib_failed": "❌ Hibernate failed. Make sure Hibernate is turned on (powercfg /h on).",
        "exit_hib": "⚠️ Sleepify was closed, so the Hibernate timer was cancelled.",
        "linked": "✅ Linked! This chat now controls this PC.\n\n",
        "err_zero": "Time must be greater than zero.",
        "err_max": "The maximum is 24 hours.",
        "err_denied": "Windows refused the shutdown command.",
        "err_none": "No active timer.",
        "err_resched": "Could not reschedule, so the timer was cancelled.",
        "err_no_hib": "Hibernate is turned off on this PC. Run Command Prompt as Administrator and type: powercfg /h on",
    },
    "ar": {
        "help": (
            "🤖 Sleepify - أوامر التحكم:\n\n"
            "/status - الوقت المتبقي\n"
            "/shutdown 1h30m - مؤقت إغلاق\n"
            "/hibernate 45m - مؤقت Hibernate\n"
            "/extend 10m - تمديد المؤقت (الافتراضي 10 دقايق)\n"
            "/cancel - إلغاء المؤقت\n"
            "/help - الأوامر\n\n"
            "المدة: h = ساعات، m = دقايق، s = ثواني. مثال: 1h30m أو 45m أو 45m30s.\n"
            "رقم لوحده يعني دقايق (مثال: /shutdown 90)."),
        "cmd_status": "الوقت المتبقي",
        "cmd_shutdown": "مؤقت إغلاق، مثال: /shutdown 1h30m",
        "cmd_hibernate": "مؤقت Hibernate، مثال: /hibernate 45m",
        "cmd_extend": "تمديد المؤقت، مثال: /extend 10m",
        "cmd_cancel": "إلغاء المؤقت",
        "cmd_help": "عرض الأوامر",
        "status_none": "🔴 مفيش مؤقت شغال دلوقتي.",
        "status_running": "🟢 مؤقت شغال\nالإجراء: {action}\nباقي: {left}\nهيتنفذ الساعة: {at}",
        "bad_duration": "❌ اكتب المدة صح، مثال: /{cmd} 1h30m أو /{cmd} 45m",
        "bad_duration_extend": "❌ اكتب المدة صح، مثال: /extend 10m",
        "started": "✅ تمام، المؤقت اشتغل: {action} بعد {dur}\nالساعة: {at}",
        "replaced": "(المؤقت القديم اتبدل)",
        "hib_note": "⚠️ سيب Sleepify شغال في الـ Tray، لو اتقفل مؤقت الـ Hibernate بيتلغي.",
        "extended": "⏰ اتمدد {dur}. باقي {left}، هيتنفذ الساعة {at}",
        "cancelled": "✅ المؤقت اتلغى.",
        "cancel_none": "ℹ️ مفيش مؤقت شغال عشان أكنسله.",
        "unknown_cmd": "مش فاهم الأمر ده 🤔 اكتب /help",
        "warn_shutdown": "⚠️ باقي {mins} دقيقة والجهاز هيقفل. احفظ شغلك! 💾",
        "warn_hibernate": "⚠️ باقي {mins} دقيقة والجهاز هيعمل Hibernate. احفظ شغلك! 💾",
        "final": "🔔 الجهاز بينفذ {action} دلوقتي!",
        "cancelled_pc": "✅ المؤقت اتلغى من الجهاز.",
        "hib_failed": "❌ الـ Hibernate فشل. اتأكد إنه مفعّل في الجهاز (powercfg /h on).",
        "exit_hib": "⚠️ Sleepify اتقفل، فمؤقت الـ Hibernate اتلغى.",
        "linked": "✅ اتربط! الشات ده بقى بيتحكم في الجهاز ده.\n\n",
        "err_zero": "الوقت لازم يكون أكبر من صفر.",
        "err_max": "أقصى مدة 24 ساعة.",
        "err_denied": "ويندوز رفض أمر الإغلاق.",
        "err_none": "مفيش مؤقت شغال.",
        "err_resched": "معرفتش أعيد جدولة المؤقت فاتلغى.",
        "err_no_hib": "الـ Hibernate مقفول على الجهاز ده. افتح Command Prompt كـ Administrator واكتب: powercfg /h on",
    },
}
LANG = "en"


def set_language(lang):
    global LANG
    LANG = lang if lang in STR else "en"


def t(key, lang=None, **kw):
    table = STR.get(lang or LANG, STR["en"])
    text = table.get(key) or STR["en"][key]
    return text.format(**kw) if kw else text


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")


def scrub(text):
    """Never let a bot token reach a log file or the screen."""
    return _TOKEN_RE.sub("<token>", str(text))


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


def fmt_clock(ts):
    dt = datetime.fromtimestamp(ts)
    text = dt.strftime("%I:%M %p").lstrip("0")
    days = (dt.date() - datetime.now().date()).days
    if days == 1:
        text += " (tomorrow)"
    elif days > 1:
        text += f" (+{days} days)"
    return text


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


def default_device_name():
    try:
        return socket.gethostname() or "My PC"
    except OSError:
        return "My PC"


# --------------------------------------------------------------------------
# Config  (%APPDATA%\Sleepify\config.json)
# --------------------------------------------------------------------------
def load_config():
    cfg = {"bot_token": "", "chat_id": None, "warning_minutes": 10,
           "device_name": "", "language": "en", "telegram_skipped": False}
    try:
        with open(CONFIG_FILE, encoding="utf-8-sig") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("config is not an object")
    except FileNotFoundError:
        return cfg
    except (OSError, ValueError) as e:
        log_error(f"config.json could not be read, using defaults: {e}")
        return cfg

    try:
        cfg["warning_minutes"] = min(180, max(1, int(raw.get("warning_minutes", 10))))
    except (TypeError, ValueError):
        pass
    cfg["device_name"] = str(raw.get("device_name") or "").strip()[:30]
    if raw.get("language") in STR:
        cfg["language"] = raw["language"]
    cfg["telegram_skipped"] = bool(raw.get("telegram_skipped", False))

    token = str(raw.get("bot_token", "")).strip()
    try:
        chat_id = int(raw.get("chat_id"))
    except (TypeError, ValueError):
        chat_id = None
    if _TOKEN_RE.fullmatch(token) and chat_id is not None:
        cfg["bot_token"], cfg["chat_id"] = token, chat_id
    return cfg


def save_config(cfg):
    data = {k: cfg.get(k) for k in
            ("bot_token", "chat_id", "warning_minutes", "device_name", "language", "telegram_skipped")}
    tmp = CONFIG_FILE + ".tmp"
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_FILE)
        return True
    except OSError as e:
        log_error(f"could not save config: {e}")
        return False


def update_config(**changes):
    cfg = load_config()
    cfg.update(changes)
    return save_config(cfg)


def has_telegram(cfg):
    return bool(cfg.get("bot_token")) and cfg.get("chat_id") is not None


def migrate_legacy_config():
    """v0.x kept config.json next to the script. Copy it to %APPDATA%\\Sleepify once."""
    if os.path.exists(CONFIG_FILE) or not os.path.exists(LEGACY_CONFIG):
        return False
    try:
        with open(LEGACY_CONFIG, encoding="utf-8-sig") as f:
            raw = json.load(f)
        cfg = {"bot_token": str(raw.get("bot_token", "")).strip(), "chat_id": int(raw.get("chat_id")),
               "warning_minutes": int(raw.get("warning_minutes", 10)),
               "device_name": default_device_name(), "language": "ar", "telegram_skipped": False}
        if not _TOKEN_RE.fullmatch(cfg["bot_token"]):
            return False
        ok = save_config(cfg)
        if ok:
            log_event("Imported the old config.json into the new settings folder")
        return ok
    except (OSError, ValueError, TypeError) as e:
        log_error(f"old config.json could not be imported: {e}")
        return False


# --------------------------------------------------------------------------
# Icons (generated from assets/logo.jpg, or drawn if there is no logo)
# --------------------------------------------------------------------------
_logo_warned = False


def find_logo():
    """logo.jpg/.png in your settings folder, then the bundled assets, then the old icons folder."""
    dirs = [ICON_DIR, resource_path("assets"), os.path.join(APP_DIR, "icons")]
    for d in dirs:
        for name in ("logo.jpg", "logo.jpeg", "logo.png"):
            path = os.path.join(d, name)
            if os.path.exists(path):
                return path
    try:  # v0.x: any .jpg dropped into the old icons folder
        legacy = os.path.join(APP_DIR, "icons")
        for name in sorted(os.listdir(legacy)):
            if name.lower().endswith((".jpg", ".jpeg")):
                return os.path.join(legacy, name)
    except OSError:
        pass
    return None


def _rounded(img, radius_frac=0.22):
    size = img.size[0]
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, size * 4 - 1, size * 4 - 1), radius=int(size * 4 * radius_frac), fill=255)
    mask = big.resize((size, size), RES)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _draw_fallback(size):
    s = size * 4
    bg = (23, 27, 80, 255)
    green = (125, 255, 90, 255)
    img = Image.new("RGBA", (s, s), bg)
    d = ImageDraw.Draw(img)
    d.ellipse((s * 0.14, s * 0.22, s * 0.86, s * 0.94), fill=green)          # crescent moon
    d.ellipse((s * 0.30, s * 0.10, s * 1.00, s * 0.80), fill=bg)
    cx, cy, r, w = s * 0.46, s * 0.50, s * 0.17, int(s * 0.055)               # power symbol
    d.arc((cx - r, cy - r, cx + r, cy + r), start=300, end=240, fill=green, width=w)
    d.line((cx, cy - r * 1.25, cx, cy - r * 0.1), fill=green, width=w)
    for y in (cy - r * 1.25, cy - r * 0.1):
        d.ellipse((cx - w / 2, y - w / 2, cx + w / 2, y + w / 2), fill=green)
    return img.resize((size, size), RES)


def make_base_icon(size):
    """Square icon (symbol only, no text) at the requested size."""
    global _logo_warned
    try:
        logo = find_logo()
        if logo is None:
            raise FileNotFoundError("no logo image found")
        im = Image.open(logo).convert("RGB")
        r, g, b = im.split()
        m = ImageChops.darker(
            ImageChops.darker(
                ImageChops.subtract(g, r).point(lambda v: 255 if v > 60 else 0),
                ImageChops.subtract(g, b).point(lambda v: 255 if v > 60 else 0)),
            g.point(lambda v: 255 if v > 150 else 0))
        box = m.getbbox()
        if box:
            # the little sparkle stars are paler than the green symbol, so add room on top for them
            box = (box[0], box[1] - int(0.15 * (box[3] - box[1])), box[2], box[3])
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            half = max(box[2] - box[0], box[3] - box[1]) / 2 * 1.1
            half = min(half, cx, cy, im.size[0] - cx, im.size[1] - cy)
            crop = im.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))
            return crop.resize((size, size), RES).convert("RGBA")
    except Exception as e:
        if not _logo_warned:
            _logo_warned = True
            log_error(f"logo image not used, drawing a default icon instead: {e}")
    return _draw_fallback(size)


def to_red(img):
    """Shift the green parts of the icon to red (the blue/purple background stays)."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    h, s, v = rgba.convert("RGB").convert("HSV").split()
    table = [(int((i - 85) * 0.25)) % 256 if 35 <= i <= 125 else i for i in range(256)]
    out = Image.merge("HSV", (h.point(table), s, v)).convert("RGB")
    out.putalpha(alpha)
    return out


def build_icons():
    """Returns (icon_on, icon_off) as 64x64 images; writes app.ico / bot.png when the logo changes."""
    try:
        os.makedirs(ICON_DIR, exist_ok=True)
        logo = find_logo()
        stamp = "none" if logo is None else f"{os.path.basename(logo)}|{os.path.getsize(logo)}|{int(os.path.getmtime(logo))}"
        stamp_file = os.path.join(ICON_DIR, "logo.stamp")
        try:
            with open(stamp_file, encoding="utf-8") as f:
                old_stamp = f.read().strip()
        except OSError:
            old_stamp = ""
        changed = stamp != old_stamp
        if changed or not os.path.exists(ICO_FILE):
            _rounded(make_base_icon(256)).save(
                ICO_FILE, format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        if changed or not os.path.exists(BOT_PNG):
            make_base_icon(512).convert("RGB").save(BOT_PNG)
        if changed:
            with open(stamp_file, "w", encoding="utf-8") as f:
                f.write(stamp)
    except Exception as e:
        log_error(f"could not write icon files: {e}")
    base = _rounded(make_base_icon(256))
    return base.resize((64, 64), RES), to_red(base).resize((64, 64), RES)


# --------------------------------------------------------------------------
# Start with Windows (registry Run key, no admin needed) and desktop shortcut
# --------------------------------------------------------------------------
def launch_target():
    """(program, arguments) that start Sleepify - the exe when installed, pythonw + script from source."""
    if FROZEN:
        return sys.executable, ""
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return exe, f'"{os.path.abspath(__file__)}"'


def autostart_command():
    target, args = launch_target()
    return " ".join(p for p in (f'"{target}"', args, "--hidden") if p)


def autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    if winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        log_error(f"could not change the Start-with-Windows setting: {e}")
        return False


def _ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, creationflags=CNW)


def _q(text):
    """PowerShell single-quoted string literal."""
    return "'" + str(text).replace("'", "''") + "'"


def install_shortcuts():
    """From source: Desktop icon + start with Windows (no admin needed)."""
    build_icons()
    target, args = launch_target()
    icon = f"{sys.executable},0" if FROZEN else ICO_FILE
    ps = f"""
$ErrorActionPreference = 'Stop'
$w = New-Object -ComObject WScript.Shell
$lnk = $w.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sleepify.lnk'))
$lnk.TargetPath = {_q(target)}
$lnk.Arguments = {_q(args)}
$lnk.WorkingDirectory = {_q(APP_DIR)}
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


# --------------------------------------------------------------------------
# System hooks (everything that touches Windows / the outside world)
# --------------------------------------------------------------------------
class Hooks:
    def __init__(self):
        self.tray = None
        self.bot = None

    def run(self, cmd):
        try:
            return subprocess.run(cmd, capture_output=True, creationflags=CNW, timeout=20).returncode
        except Exception as e:
            log_error(f"command {cmd} failed: {e}")
            return 1

    def beep(self, freq, ms):
        if winsound is None:
            return

        def _go():
            try:
                winsound.Beep(freq, ms)
            except Exception as e:
                log_error(f"beep failed: {e}")
        threading.Thread(target=_go, daemon=True).start()

    def toast(self, title, message):
        if self.tray is None:
            return
        try:
            self.tray.notify(message, title)
        except Exception as e:
            log_error(f"notification failed: {e}")

    def tg(self, text):
        if self.bot is not None:
            self.bot.send(text)

    def log(self, text):
        log_event(text)

    def hibernate_ok(self):
        """False only when Windows says hibernation is switched off; None = could not tell."""
        if winreg is None:
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power") as k:
                return bool(winreg.QueryValueEx(k, "HibernateEnabled")[0])
        except OSError:
            return None


# --------------------------------------------------------------------------
# Timer core (no GUI in here)
# --------------------------------------------------------------------------
class TimerCore:
    def __init__(self, hooks, warn_minutes=10, clock=time.time):
        self.h = hooks
        self.clock = clock
        self.warn_sec = warn_minutes * 60
        self.running = False
        self.action = "S"            # S = Shutdown, H = Hibernate
        self.end_ts = 0.0
        self.warned = False
        self.final_done = False

    # ---- state file ----
    def _save(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"action": self.action, "end": self.end_ts}, f)
        except OSError as e:
            log_error(f"could not save state: {e}")

    def _clear(self):
        try:
            os.remove(STATE_FILE)
        except OSError:
            pass

    # ---- queries ----
    def remaining(self):
        if not self.running:
            return 0
        return max(0, math.ceil(self.end_ts - self.clock()))

    def set_warn_minutes(self, minutes):
        self.warn_sec = minutes * 60
        if self.running and self.remaining() > self.warn_sec:
            self.warned = False

    # ---- actions (the second value is a message key from STR) ----
    def start(self, seconds, action, source="app"):
        seconds = int(seconds)
        if seconds <= 0:
            return False, "err_zero"
        if seconds > MAX_SECONDS:
            return False, "err_max"
        if action == "H" and self.h.hibernate_ok() is False:
            return False, "err_no_hib"
        self.h.run(["shutdown", "-a"])            # clear anything pending (ignore result)
        if action == "S":
            if self.h.run(["shutdown", "-s", "-t", str(seconds)]) != 0:
                self.running = False
                self._clear()
                return False, "err_denied"
        self.running = True
        self.action = action
        self.end_ts = self.clock() + seconds
        self.warned = seconds <= self.warn_sec
        self.final_done = False
        self._save()
        self.h.log(f"Started {ACTION_NAME[action]} timer {fmt_hms(seconds)} (by {source})")
        return True, "ok"

    def cancel(self, source="app"):
        if not self.running:
            return False, "err_none"
        left = self.remaining()
        if self.action == "S":
            self.h.run(["shutdown", "-a"])
        self.running = False
        self._clear()
        self.h.log(f"Cancelled {ACTION_NAME[self.action]} timer, {fmt_hms(left)} was left (by {source})")
        if source == "app":
            self.h.tg(t("cancelled_pc"))
        return True, "ok"

    def extend(self, seconds, source="app"):
        if not self.running:
            return False, "err_none"
        seconds = int(seconds)
        if seconds <= 0:
            return False, "err_zero"
        new_rem = math.ceil(self.end_ts + seconds - self.clock())
        if new_rem > MAX_SECONDS:
            return False, "err_max"
        if self.action == "S":
            self.h.run(["shutdown", "-a"])
            if self.h.run(["shutdown", "-s", "-t", str(new_rem)]) != 0:
                self.running = False
                self._clear()
                return False, "err_resched"
        self.end_ts += seconds
        if new_rem > self.warn_sec:
            self.warned = False
        if new_rem > 3:
            self.final_done = False
        self._save()
        self.h.log(f"Extended by {fmt_human(seconds)}, {fmt_hms(new_rem)} left (by {source})")
        return True, "ok"

    def resume_from_disk(self):
        """Call once at startup. Returns 'resumed', 'hibernate_lost' or None."""
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            action, end = data.get("action"), float(data.get("end", 0))
        except (OSError, ValueError, TypeError):
            return None
        now = self.clock()
        if action == "S" and end - now > 2:
            rem = math.ceil(end - now)
            self.running, self.action, self.end_ts = True, "S", end
            self.warned = rem <= self.warn_sec
            self.final_done = rem <= 3
            self.h.log(f"Resumed Shutdown timer, {fmt_hms(rem)} left")
            return "resumed"
        self._clear()
        if action == "H" and end > now:
            self.h.log("A Hibernate timer from the previous session was lost (app was closed)")
            return "hibernate_lost"
        return None

    # ---- called every ~250 ms ----
    def tick(self):
        if not self.running:
            return
        now = self.clock()
        if self.action == "H" and now - self.end_ts > 30:
            # the PC was asleep through the deadline - do NOT hibernate right after waking up
            self.running = False
            self._clear()
            self.h.log("Hibernate timer expired while the PC was asleep - skipped")
            self.h.toast(APP_NAME, "The Hibernate timer expired while the PC was asleep, so it was skipped.")
            return
        rem = max(0, math.ceil(self.end_ts - now))
        if not self.warned and rem <= self.warn_sec:
            self.warned = True
            if rem > 3:
                self._warn(rem)
        if not self.final_done and rem <= 3:
            self.final_done = True
            self._final()
        if rem <= 0:
            self._execute()

    def _warn(self, rem):
        mins = max(1, round(rem / 60))
        shut = self.action == "S"
        self.h.beep(1500, 2000)
        self.h.toast(f"Warning: {mins} min left",
                     f"Your PC will {'shut down' if shut else 'hibernate'} in {mins} minute(s). Please save your work.")
        self.h.tg(t("warn_shutdown" if shut else "warn_hibernate", mins=mins))
        self.h.log(f"Warning shown, {fmt_hms(rem)} left")

    def _final(self):
        self.h.beep(1000, 3000)
        self.h.tg(t("final", action=ACTION_NAME[self.action]))

    def _execute(self):
        action = self.action
        self.running = False
        self._clear()
        self.h.log(f"Executing {ACTION_NAME[action]}")
        if action == "H":
            if self.h.run(["shutdown", "/h"]) != 0:
                self.h.log("Hibernate command failed")
                self.h.toast(APP_NAME, "Hibernate failed. Is Hibernate enabled? (powercfg /h on)")
                self.h.tg(t("hib_failed"))


# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------
class TelegramError(Exception):
    def __init__(self, code, description):
        super().__init__(f"Telegram error {code}: {description}")
        self.code = code


def tg_api(token, method, params=None, post=False, timeout=10):
    """Calls the Telegram Bot API and returns the 'result' part. Raises TelegramError / requests errors."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    if post:
        r = requests.post(url, data=params, timeout=timeout)
    else:
        r = requests.get(url, params=params, timeout=timeout)
    data = r.json()
    if not data.get("ok"):
        raise TelegramError(data.get("error_code"), data.get("description"))
    return data.get("result")


def run_command(core, cmd, args):
    """Runs a Telegram command and returns the reply text (in the chosen language)."""
    if cmd in ("start", "help"):
        return t("help")

    if cmd == "status":
        if not core.running:
            return t("status_none")
        return t("status_running", action=ACTION_NAME[core.action], left=fmt_hms(core.remaining()),
                 at=fmt_clock(core.end_ts))

    if cmd in ("shutdown", "hibernate"):
        sec = parse_duration(args)
        if sec is None:
            return t("bad_duration", cmd=cmd)
        action = "S" if cmd == "shutdown" else "H"
        replaced = core.running
        ok, msg = core.start(sec, action, "telegram")
        if not ok:
            return "❌ " + t(msg)
        text = t("started", action=ACTION_NAME[action], dur=fmt_human(sec), at=fmt_clock(core.end_ts))
        if replaced:
            text += "\n" + t("replaced")
        if action == "H":
            text += "\n" + t("hib_note")
        return text

    if cmd == "extend":
        sec = parse_duration(args) if args.strip() else EXTEND_MINUTES * 60
        if sec is None:
            return t("bad_duration_extend")
        ok, msg = core.extend(sec, "telegram")
        if not ok:
            return "❌ " + t(msg)
        return t("extended", dur=fmt_human(sec), left=fmt_hms(core.remaining()), at=fmt_clock(core.end_ts))

    if cmd == "cancel":
        ok, msg = core.cancel("telegram")
        return t("cancelled") if ok else t("cancel_none")

    return t("unknown_cmd")


def bot_commands():
    return [(c, t("cmd_" + c)) for c in ("status", "shutdown", "hibernate", "extend", "cancel", "help")]


class TelegramBot:
    def __init__(self, token, chat_id, inbox, device_name=""):
        self.token = token
        self.chat_id = chat_id
        self.inbox = inbox
        self.device = device_name
        self.stop = threading.Event()
        self.online = False
        self.last_error = ""
        self.username = ""

    def send(self, text, wait=False):
        header = f"💻 {self.device}\n" if self.device else ""

        def _do():
            try:
                tg_api(self.token, "sendMessage", {"chat_id": self.chat_id, "text": header + text}, post=True)
            except Exception as e:
                log_error(f"sendMessage failed: {e}")
        if wait:
            _do()
        else:
            threading.Thread(target=_do, daemon=True).start()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        try:
            me = tg_api(self.token, "getMe")
            self.online = True
            self.username = (me or {}).get("username", "")
        except Exception as e:
            self.last_error = scrub(e)[:80]
            log_error(f"getMe failed: {e}")
        try:
            tg_api(self.token, "setMyCommands", {"commands": json.dumps(
                [{"command": c, "description": d} for c, d in bot_commands()], ensure_ascii=False)}, post=True)
        except Exception as e:
            log_error(f"setMyCommands failed: {e}")

        offset = None
        backoff = 2
        while not self.stop.is_set():
            try:
                params = {"timeout": 25, "allowed_updates": json.dumps(["message"])}
                if offset is not None:
                    params["offset"] = offset
                updates = tg_api(self.token, "getUpdates", params, timeout=35)
                self.online, self.last_error, backoff = True, "", 2
                for upd in updates or []:
                    offset = upd["update_id"] + 1
                    self._handle(upd)
            except Exception as e:
                self.online = False
                self.last_error = scrub(e)[:80]
                log_error(f"Telegram polling: {e}")
                self.stop.wait(backoff)
                backoff = min(backoff * 2, 60)

    def _handle(self, upd):
        msg = upd.get("message")
        if not msg:
            return
        # only YOU: both the chat and the sender must be your id
        if msg.get("chat", {}).get("id") != self.chat_id or msg.get("from", {}).get("id") != self.chat_id:
            return
        # ignore old messages (for example sent while the PC was off)
        if time.time() - msg.get("date", 0) > 120:
            return
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            self.inbox.put(("tg", "help", ""))
            return
        parts = text.split(maxsplit=1)
        cmd = parts[0][1:].split("@")[0].lower()
        self.inbox.put(("tg", cmd, parts[1] if len(parts) > 1 else ""))


# ---- pairing: link the owner's Telegram account to this PC with a one-time code ----
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no 0/O/1/I to avoid typos


def new_pair_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def valid_token_format(token):
    return bool(_TOKEN_RE.fullmatch((token or "").strip()))


def match_pair_update(upd, code):
    """Returns (chat_id, first_name) if this update is the owner sending the pairing code, else None."""
    msg = upd.get("message") or {}
    chat = msg.get("chat") or {}
    sender = msg.get("from") or {}
    if chat.get("type") != "private" or sender.get("id") != chat.get("id") or chat.get("id") is None:
        return None
    parts = (msg.get("text") or "").split()
    if len(parts) >= 2 and parts[0].split("@")[0].lower() == "/start":
        cand = parts[1]
    elif len(parts) == 1:
        cand = parts[0]
    else:
        return None
    if cand.strip().upper() != code.upper():
        return None
    return chat["id"], sender.get("first_name", "")


class PairingWatcher(threading.Thread):
    """Waits (in the background) for the pairing code to arrive at the user's own bot."""

    def __init__(self, token, code):
        super().__init__(daemon=True)
        self.token, self.code = token, code
        self.stop = threading.Event()
        self.result = None          # (chat_id, first_name)
        self.error = ""

    def run(self):
        offset = None
        while not self.stop.is_set():
            try:
                params = {"timeout": 5, "allowed_updates": json.dumps(["message"])}
                if offset is not None:
                    params["offset"] = offset
                updates = tg_api(self.token, "getUpdates", params, timeout=15)
                self.error = ""
                for upd in updates or []:
                    offset = upd["update_id"] + 1
                    hit = match_pair_update(upd, self.code)
                    if hit:
                        try:   # confirm it, so Telegram does not deliver the code message again
                            tg_api(self.token, "getUpdates", {"offset": offset, "timeout": 0})
                        except Exception:
                            pass
                        self.result = hit
                        return
            except Exception as e:
                self.error = scrub(e)[:80]
                self.stop.wait(3)


# --------------------------------------------------------------------------
# Single instance: launching the app again just shows the running window
# --------------------------------------------------------------------------
_mutex_handle = None


def hold_mutex():
    """Named mutex so the installer can tell Sleepify is running (and ask to close it)."""
    global _mutex_handle
    try:
        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    except Exception:
        _mutex_handle = None


def single_instance():
    """Returns (server_socket, status): status is 'primary', 'forwarded' or 'busy'."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        # POSIX only: allow re-binding right after a restart. On Windows this option would let two copies
        # share the port, so it must NOT be set there.
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("127.0.0.1", SINGLE_PORT))
        srv.listen(5)
        return srv, "primary"
    except OSError:
        srv.close()
    try:
        with socket.create_connection(("127.0.0.1", SINGLE_PORT), timeout=3) as c:
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


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
def font(size, weight="normal", family="Segoe UI"):
    return ctk.CTkFont(family=family, size=size, weight=weight)


class SetupWizard(ctk.CTkToplevel):
    """First-run setup: device name + language, your own bot's token, then link your account."""

    def __init__(self, app, cfg):
        super().__init__(app)
        self.app = app
        self.cfg = cfg
        self.d = {"language": cfg.get("language", "en"),
                  "device_name": cfg.get("device_name") or default_device_name(),
                  "bot_token": "", "username": "", "chat_id": None, "first_name": ""}
        self.watcher = None
        self.job = None
        self.alive = True
        self.step = 0
        self.code = ""
        self.title("Sleepify setup")
        self.geometry("520x580")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=26, pady=20)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self._safe(lambda: self.attributes("-topmost", False)))
        self.after(150, lambda: self._safe(self.grab_set))
        self.after(300, lambda: self._safe(lambda: self.iconbitmap(ICO_FILE)))
        self._step1()
        self.after(300, self._poll)

    # ---------- helpers ----------
    @staticmethod
    def _safe(fn):
        try:
            fn()
        except Exception:
            pass

    def _clear(self, step):
        self.step = step
        self._stop_watcher()
        for w in self.body.winfo_children():
            w.destroy()

    def _stop_watcher(self):
        if self.watcher is not None:
            self.watcher.stop.set()
            self.watcher = None

    def _text(self, text, size=13, color=TEXT, bold=False, pady=(0, 8), wrap=466):
        lbl = ctk.CTkLabel(self.body, text=text, font=font(size, "bold" if bold else "normal"),
                           text_color=color, wraplength=wrap, justify="left")
        lbl.pack(anchor="w", pady=pady)
        return lbl

    def _button(self, parent, text, command, primary=False, **kw):
        return ctk.CTkButton(parent, text=text, command=command, height=38, font=font(13, "bold"),
                             fg_color=GREEN_BTN if primary else BTN,
                             hover_color=GREEN_BTN_HOVER if primary else BTN_HOVER,
                             text_color="#0d1033" if primary else TEXT, **kw)

    def _nav(self, back=None, nxt=None, nxt_text="Next", nxt_enabled=True):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(side="bottom", fill="x", pady=(10, 0))
        row.grid_columnconfigure((0, 1), weight=1)
        if back:
            self._button(row, "Back", back).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.btn_next = self._button(row, nxt_text, nxt, primary=True,
                                     state="normal" if nxt_enabled else "disabled")
        self.btn_next.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ---------- step 1: welcome ----------
    def _step1(self):
        self._clear(1)
        linked = has_telegram(self.cfg)
        self._text("Welcome to Sleepify", 24, bold=True, pady=(0, 6))
        self._text("Control your PC's shutdown timer from your phone, through your own private Telegram bot. "
                   "It takes about two minutes and you only do it once.", color=GRAY, pady=(0, 14))
        self._text("Name of this PC (shown in the messages)", 12, GRAY, True, pady=(0, 3))
        self.e_device = ctk.CTkEntry(self.body, height=36)
        self.e_device.insert(0, self.d["device_name"])
        self.e_device.pack(fill="x", pady=(0, 12))
        self._text("Language of the Telegram messages", 12, GRAY, True, pady=(0, 3))
        self.seg_lang = ctk.CTkSegmentedButton(
            self.body, values=["Arabic", "English"], height=34, font=font(13, "bold"), fg_color=BTN,
            selected_color="#2fa81f", selected_hover_color="#3cc828", unselected_color=BTN,
            unselected_hover_color=BTN_HOVER, text_color=TEXT)
        self.seg_lang.set("Arabic" if self.d["language"] == "ar" else "English")
        self.seg_lang.pack(fill="x", pady=(0, 16))

        if linked:
            self._text("Telegram is already set up on this PC.", 12, GREEN, pady=(0, 6))
            self._button(self.body, "Save (keep my Telegram link)", self._save_keep, primary=True).pack(fill="x", pady=(0, 8))
            self._button(self.body, "Change bot / link again", self._to_step2).pack(fill="x")
        else:
            self._button(self.body, "Set up Telegram", self._to_step2, primary=True).pack(fill="x", pady=(0, 8))
            self._button(self.body, "Skip - use Sleepify without Telegram", self._skip).pack(fill="x")

    def _read_step1(self):
        name = self.e_device.get().strip()[:30]
        if not name:
            messagebox.showerror("Sleepify", "Please type a name for this PC.", parent=self)
            return False
        self.d["device_name"] = name
        self.d["language"] = "ar" if self.seg_lang.get() == "Arabic" else "en"
        return True

    def _to_step2(self):
        if self._read_step1():
            self._step2()

    def _skip(self):
        if not self._read_step1():
            return
        new = dict(self.cfg)
        new.update(language=self.d["language"], device_name=self.d["device_name"],
                   bot_token="", chat_id=None, telegram_skipped=True)
        self.app.apply_new_config(new)
        self.close()

    def _save_keep(self):
        if not self._read_step1():
            return
        new = dict(self.cfg)
        new.update(language=self.d["language"], device_name=self.d["device_name"])
        self.app.apply_new_config(new)
        self.close()

    # ---------- step 2: bot token ----------
    def _step2(self):
        self._clear(2)
        self._text("Step 1 of 2 - create your bot", 20, bold=True, pady=(0, 8))
        self._text("1. Open BotFather in Telegram (button below).\n"
                   "2. Send it  /newbot  and answer its questions. The bot's username must end with  bot.\n"
                   "3. BotFather replies with a token. Copy it and paste it here.", pady=(0, 10))
        self._button(self.body, "Open BotFather in Telegram",
                     lambda: webbrowser.open("https://t.me/BotFather")).pack(fill="x", pady=(0, 10))
        self.e_token = ctk.CTkEntry(self.body, height=36, show="•", placeholder_text="Paste the token here")
        self.e_token.pack(fill="x")
        self.show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.body, text="Show the token", variable=self.show_var, font=font(12), text_color=GRAY,
                        checkbox_width=18, checkbox_height=18, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER,
                        command=lambda: self.e_token.configure(show="" if self.show_var.get() else "•")
                        ).pack(anchor="w", pady=(6, 8))
        self._button(self.body, "Check the token", self._verify).pack(fill="x")
        self.v_lbl = self._text("", 12, GRAY, pady=(8, 0))
        self._text("Keep the token private: anyone who has it can control your bot.", 11, GRAY, pady=(8, 0))
        self._nav(back=self._step1, nxt=self._step3, nxt_enabled=False)

    def _verify(self):
        token = self.e_token.get().strip()
        if not valid_token_format(token):
            self.v_lbl.configure(text="That doesn't look like a bot token. It looks like 123456789:ABC...", text_color=RED)
            return
        self.v_lbl.configure(text="Checking with Telegram...", text_color=AMBER)
        job = {"done": False}
        self.job = job

        def work():
            try:
                me = tg_api(token, "getMe")
                job.update(ok=True, token=token, username=(me or {}).get("username", ""))
            except TelegramError as e:
                job.update(ok=False, msg="Telegram says this token is not valid." if e.code == 401
                           else f"Telegram answered with an error ({e.code}).")
            except Exception:
                job.update(ok=False, msg="Could not reach Telegram. Check your internet connection.")
            job["done"] = True
        threading.Thread(target=work, daemon=True).start()

    def _on_verified(self, job):
        if self.step != 2:
            return
        if job.get("ok"):
            self.d["bot_token"], self.d["username"] = job["token"], job["username"]
            self.v_lbl.configure(text=f"✓ Your bot is @{job['username']}", text_color=GREEN)
            self.btn_next.configure(state="normal")
        else:
            self.v_lbl.configure(text=job.get("msg", "Check failed."), text_color=RED)
            self.btn_next.configure(state="disabled")

    # ---------- step 3: link the account ----------
    def _step3(self):
        self._clear(3)
        self.code = new_pair_code()
        self.d["chat_id"] = None
        self._text("Step 2 of 2 - link your Telegram", 20, bold=True, pady=(0, 8))
        self._text("Press the button, then press START in Telegram. Sleepify will notice by itself.", pady=(0, 6))
        self.code_lbl = ctk.CTkLabel(self.body, text=self.code, font=font(34, "bold", "Consolas"), text_color=GREEN)
        self.code_lbl.pack(pady=(4, 6))
        self._button(self.body, "Open my bot in Telegram", self._open_bot, primary=True).pack(fill="x", pady=(0, 8))
        self._text("If the button doesn't work, open your bot yourself and send it this message:", 12, GRAY, pady=(0, 2))
        self.cmd_lbl = self._text(f"/start {self.code}", 14, TEXT, True, pady=(0, 10))
        self.link_lbl = self._text("Waiting for you in Telegram...", 13, AMBER, pady=(0, 6))
        self._button(self.body, "Make a new code", self._step3).pack(fill="x")
        self._nav(back=self._step2, nxt=self._step4, nxt_enabled=False)
        self.watcher = PairingWatcher(self.d["bot_token"], self.code)
        self.watcher.start()

    def _open_bot(self):
        webbrowser.open(f"https://t.me/{self.d['username']}?start={self.code}")

    def _on_linked(self):
        if self.step != 3:
            return
        who = f" ({self.d['first_name']})" if self.d["first_name"] else ""
        self.link_lbl.configure(text=f"✓ Linked{who}", text_color=GREEN)
        self.btn_next.configure(state="normal")

    # ---------- step 4: done ----------
    def _step4(self):
        self._clear(4)
        self._text("All set!", 24, bold=True, pady=(0, 8))
        self._text(f"{self.d['device_name']} is linked to @{self.d['username']}.\n\n"
                   "When you press Finish, a message will arrive in your Telegram with the list of commands. "
                   "Try /status.\n\nSleepify keeps running in the tray, near the clock.", pady=(0, 10))
        self._text("Using more than one PC? Create one bot per PC (a new bot takes a minute) and give each "
                   "PC a different name. Then you control each one from its own chat.", 12, GRAY)
        self._nav(back=None, nxt=self._finish, nxt_text="Finish")

    def _finish(self):
        new = dict(self.cfg)
        new.update(language=self.d["language"], device_name=self.d["device_name"], bot_token=self.d["bot_token"],
                   chat_id=self.d["chat_id"], telegram_skipped=False)
        self.app.apply_new_config(new)

        def welcome():
            try:
                tg_api(new["bot_token"], "sendMessage",
                       {"chat_id": new["chat_id"], "text": f"💻 {new['device_name']}\n" + t("linked") + t("help")},
                       post=True)
            except Exception as e:
                log_error(f"welcome message failed: {e}")
        threading.Thread(target=welcome, daemon=True).start()
        self.close()

    # ---------- background polling of the helper threads ----------
    def _poll(self):
        if not self.alive:
            return
        try:
            if self.job is not None and self.job.get("done"):
                job, self.job = self.job, None
                self._on_verified(job)
            w = self.watcher
            if w is not None:
                if w.result and not self.d["chat_id"]:
                    self.d["chat_id"], self.d["first_name"] = w.result
                    self._on_linked()
                elif w.error and self.step == 3:
                    self.link_lbl.configure(text="Can't reach Telegram yet, retrying...", text_color=AMBER)
        except Exception:
            log_error(traceback.format_exc())
        self.after(300, self._poll)

    def close(self):
        self.alive = False
        self._stop_watcher()
        self.app.wizard_closed()
        try:
            self.destroy()
        except Exception:
            pass


class App(ctk.CTk):
    def __init__(self, cfg, core, hooks, icons, srv, start_hidden):
        super().__init__()
        self.cfg, self.core, self.hooks = cfg, core, hooks
        self.icon_on, self.icon_off = icons
        self.srv = srv
        self.inbox = queue.Queue()
        self.stop_event = threading.Event()
        self.bot = None
        self.wizard = None
        self._cache = {}
        self._closing = False
        self._tip_shown = False
        self._tray_state = None
        self._tray_title = ""

        ctk.set_appearance_mode("dark")
        self.title(APP_NAME)
        self.geometry("460x640")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.report_callback_exception = lambda *a: log_error("".join(traceback.format_exception(*a)))

        self._build_ui()
        self._start_bot()
        self._start_tray()
        threading.Thread(target=listen_for_show, args=(srv, self.inbox, self.stop_event), daemon=True).start()

        resumed = core.resume_from_disk()
        if resumed == "hibernate_lost":
            self.after(1500, lambda: hooks.toast(
                APP_NAME, "The Hibernate timer from last time was cancelled because Sleepify was closed."))

        self.needs_setup = not has_telegram(cfg) and not cfg.get("telegram_skipped")
        self.after(300, self._set_window_icon)
        if self.needs_setup:
            self.after(500, self.open_wizard)           # first run: show the setup
        elif start_hidden:
            self.attributes("-alpha", 0.0)
            self.after(600, self._finish_hide)
        self.after(200, self._tick)

    # ---------- window helpers ----------
    def _set_window_icon(self):
        try:
            self.iconbitmap(ICO_FILE)
        except Exception:
            pass

    def _finish_hide(self):
        self.withdraw()
        self.attributes("-alpha", 1.0)

    def show_window(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))
        try:
            self.focus_force()
        except Exception:
            pass

    def hide_window(self):
        self.withdraw()
        if not self._tip_shown:
            self._tip_shown = True
            self.hooks.toast(APP_NAME + " is still running",
                             "It lives near the clock. Right-click the icon for options.")

    # ---------- Telegram bot lifecycle ----------
    def _start_bot(self):
        self._stop_bot()
        if has_telegram(self.cfg):
            self.bot = TelegramBot(self.cfg["bot_token"], self.cfg["chat_id"], self.inbox, self.cfg["device_name"])
            self.hooks.bot = self.bot
            self.bot.start()

    def _stop_bot(self):
        if self.bot is not None:
            self.bot.stop.set()
        self.bot = None
        self.hooks.bot = None

    def open_wizard(self):
        if self.wizard is not None:
            try:
                if self.wizard.winfo_exists():
                    self.wizard.lift()
                    return
            except Exception:
                pass
        self.show_window()
        self._stop_bot()           # the wizard listens to the same bot, only one listener is allowed
        self.wizard = SetupWizard(self, dict(self.cfg))

    def wizard_closed(self):
        self.wizard = None
        self._start_bot()

    def apply_new_config(self, cfg):
        self.cfg = cfg
        set_language(cfg["language"])
        save_config(cfg)

    # ---------- UI ----------
    def _build_ui(self):
        pad = 20
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=pad, pady=(10, 2))
        self.logo_img = ctk.CTkImage(light_image=self.icon_on, dark_image=self.icon_on, size=(44, 44))
        ctk.CTkLabel(head, image=self.logo_img, text="").pack(side="left")
        tbox = ctk.CTkFrame(head, fg_color="transparent")
        tbox.pack(side="left", padx=12)
        ctk.CTkLabel(tbox, text="Sleepify", font=font(24, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(tbox, text=f"PC sleep timer  ·  v{VERSION}", font=font(12), text_color=GRAY).pack(anchor="w")

        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=pad, pady=6)
        self.status_lbl = ctk.CTkLabel(card, text="", font=font(12, "bold"))
        self.status_lbl.pack(pady=(10, 0))
        self.time_lbl = ctk.CTkLabel(card, text="--:--:--", font=font(50, "bold", "Consolas"))
        self.time_lbl.pack()
        self.info_lbl = ctk.CTkLabel(card, text="", font=font(13))
        self.info_lbl.pack(pady=(0, 10))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=pad, pady=2)
        row.grid_columnconfigure((0, 1), weight=1)
        self.btn_extend = ctk.CTkButton(row, text=f"+{EXTEND_MINUTES} min", height=38, font=font(14, "bold"),
                                        fg_color=BTN, hover_color=BTN_HOVER, command=self._extend)
        self.btn_extend.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.btn_cancel = ctk.CTkButton(row, text="Cancel timer", height=38, font=font(14, "bold"),
                                        fg_color=RED_BTN, hover_color=RED_BTN_HOVER, command=self._cancel)
        self.btn_cancel.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        ctk.CTkLabel(self, text="Action", font=font(12, "bold"), text_color=GRAY).pack(
            anchor="w", padx=pad + 2, pady=(8, 2))
        self.action_btn = ctk.CTkSegmentedButton(
            self, values=["Shutdown", "Hibernate"], command=self._on_action_change, height=34,
            font=font(13, "bold"), fg_color=BTN, selected_color="#2fa81f", selected_hover_color="#3cc828",
            unselected_color=BTN, unselected_hover_color=BTN_HOVER, text_color=TEXT)
        self.action_btn.set("Shutdown")
        self.action_btn.pack(fill="x", padx=pad)
        self.hint_lbl = ctk.CTkLabel(self, text="", font=font(11), text_color=GRAY, wraplength=410, justify="left")
        self.hint_lbl.pack(anchor="w", padx=pad + 2, pady=(4, 0))
        self._on_action_change("Shutdown")

        quick = ctk.CTkFrame(self, fg_color="transparent")
        quick.pack(fill="x", padx=pad, pady=(10, 0))
        quick.grid_columnconfigure((0, 1, 2), weight=1)
        for i, (label, secs) in enumerate((("30 min", 1800), ("1 hour", 3600), ("2 hours", 7200))):
            ctk.CTkButton(quick, text=label, height=36, font=font(13, "bold"), fg_color=BTN, hover_color=BTN_HOVER,
                          command=lambda s=secs: self._start(s)).grid(row=0, column=i, padx=3, sticky="ew")

        cust = ctk.CTkFrame(self, fg_color="transparent")
        cust.pack(fill="x", padx=pad, pady=(8, 0))
        cust.grid_columnconfigure((0, 1, 2), weight=1)
        self.e_h = ctk.CTkEntry(cust, placeholder_text="Hours", justify="center", height=34)
        self.e_m = ctk.CTkEntry(cust, placeholder_text="Minutes", justify="center", height=34)
        self.e_s = ctk.CTkEntry(cust, placeholder_text="Seconds", justify="center", height=34)
        for i, e in enumerate((self.e_h, self.e_m, self.e_s)):
            e.grid(row=0, column=i, padx=3, sticky="ew")
        ctk.CTkButton(self, text="Start timer", height=40, font=font(15, "bold"), fg_color=GREEN_BTN,
                      hover_color=GREEN_BTN_HOVER, text_color="#0d1033",
                      command=self._start_custom).pack(fill="x", padx=pad + 3, pady=(8, 0))

        warn = ctk.CTkFrame(self, fg_color="transparent")
        warn.pack(fill="x", padx=pad, pady=(10, 0))
        ctk.CTkLabel(warn, text="Warn me before the action (minutes)", font=font(12), text_color=GRAY).pack(
            side="left", padx=(2, 8))
        self.e_warn = ctk.CTkEntry(warn, width=56, justify="center", height=30)
        self.e_warn.insert(0, str(self.core.warn_sec // 60))
        self.e_warn.pack(side="left")
        ctk.CTkButton(warn, text="Save", width=56, height=30, fg_color=BTN, hover_color=BTN_HOVER,
                      command=self._save_warn).pack(side="left", padx=6)
        self.warn_note = ctk.CTkLabel(warn, text="", font=font(11), text_color=GREEN)
        self.warn_note.pack(side="left")

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=pad, pady=(10, 0))
        self.tg_lbl = ctk.CTkLabel(foot, text="", font=font(11))
        self.tg_lbl.pack(side="left", padx=(2, 0))
        ctk.CTkButton(foot, text="Telegram setup", width=112, height=26, font=font(11), fg_color=BTN,
                      hover_color=BTN_HOVER, command=self.open_wizard).pack(side="right")
        self.autostart_var = ctk.BooleanVar(value=autostart_enabled())
        ctk.CTkCheckBox(self, text="Start with Windows", variable=self.autostart_var, command=self._toggle_autostart,
                        font=font(12), text_color=GRAY, checkbox_width=18, checkbox_height=18,
                        fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER).pack(anchor="w", padx=pad + 2, pady=(8, 8))

    def _set(self, widget, **kw):
        key = id(widget)
        if self._cache.get(key) != kw:
            widget.configure(**kw)
            self._cache[key] = dict(kw)

    def _selected_action(self):
        return "S" if self.action_btn.get() == "Shutdown" else "H"

    def _on_action_change(self, value):
        if value == "Hibernate":
            self.hint_lbl.configure(
                text="Hibernate is run by Sleepify itself: keep it running in the tray. "
                     "Closing the window is fine, but Exit from the tray cancels the timer.",
                text_color=AMBER)
        else:
            self.hint_lbl.configure(
                text="Windows does the countdown, so the shutdown still happens even if you exit Sleepify.",
                text_color=GRAY)

    def _toggle_autostart(self):
        if not set_autostart(self.autostart_var.get()):
            messagebox.showerror(APP_NAME, "Could not change the 'Start with Windows' setting.", parent=self)
            self.autostart_var.set(autostart_enabled())

    # ---------- button handlers ----------
    def _error(self, key):
        messagebox.showerror(APP_NAME, t(key, "en"), parent=self)

    def _start(self, seconds):
        if self.core.running and not messagebox.askyesno(
                APP_NAME, "A timer is already running. Replace it?", parent=self):
            return
        ok, msg = self.core.start(seconds, self._selected_action(), "app")
        if not ok:
            self._error(msg)
        self._refresh()

    def _num(self, entry):
        text = entry.get().strip()
        value = int(text) if text else 0
        if value < 0:
            raise ValueError
        return value

    def _start_custom(self):
        try:
            total = self._num(self.e_h) * 3600 + self._num(self.e_m) * 60 + self._num(self.e_s)
        except ValueError:
            messagebox.showerror(APP_NAME, "Please enter whole numbers only.", parent=self)
            return
        if total <= 0:
            messagebox.showerror(APP_NAME, "Enter a time greater than zero.", parent=self)
            return
        self._start(total)

    def _extend(self):
        ok, msg = self.core.extend(EXTEND_MINUTES * 60, "app")
        if not ok:
            self._error(msg)
        self._refresh()

    def _cancel(self):
        self.core.cancel("app")
        self._refresh()

    def _save_warn(self):
        try:
            n = int(self.e_warn.get().strip())
            if not 1 <= n <= 180:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_NAME, "Enter a number between 1 and 180.", parent=self)
            return
        self.core.set_warn_minutes(n)
        self.cfg["warning_minutes"] = n
        saved = save_config(self.cfg)
        self.warn_note.configure(text="Saved" if saved else "Applied (could not write the settings file)")
        self.after(3000, lambda: self.warn_note.configure(text=""))

    # ---------- tray ----------
    def _start_tray(self):
        q = self.inbox
        menu = pystray.Menu(
            pystray.MenuItem("Show Sleepify", lambda icon, item: q.put(("show",)), default=True),
            pystray.MenuItem("Cancel timer", lambda icon, item: q.put(("cancel",)),
                             enabled=lambda item: self.core.running),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda icon, item: q.put(("quit",))),
        )
        self.tray = pystray.Icon(APP_NAME, self.icon_off, "Sleepify - no active timer", menu)
        self.hooks.tray = self.tray
        try:
            self.tray.run_detached()
        except Exception as e:
            log_error(f"tray icon failed to start: {e}")

    def _refresh_tray(self, running, rem):
        title = (f"Sleepify - {ACTION_NAME[self.core.action]} in {fmt_hms(rem)}"
                 if running else "Sleepify - no active timer")
        try:
            if running != self._tray_state:
                self._tray_state = running
                self.tray.icon = self.icon_on if running else self.icon_off
                self.tray.update_menu()
            if title != self._tray_title:
                self._tray_title = title
                self.tray.title = title
        except Exception as e:
            log_error(f"tray update failed: {e}")

    # ---------- main loop ----------
    def _tick(self):
        try:
            self._drain_inbox()
            if self._closing:
                return
            self.core.tick()
            self._refresh()
        except Exception:
            log_error(traceback.format_exc())
        if not self._closing:
            self.after(250, self._tick)

    def _drain_inbox(self):
        while not self._closing:
            try:
                item = self.inbox.get_nowait()
            except queue.Empty:
                return
            kind = item[0]
            if kind == "show":
                self.show_window()
            elif kind == "cancel":
                self.core.cancel("app")
            elif kind == "quit":
                self.quit_app()
            elif kind == "tg":
                self.hooks.tg(run_command(self.core, item[1], item[2]))

    def _refresh(self):
        c = self.core
        running = c.running
        rem = c.remaining()
        if running:
            warn_phase = rem <= c.warn_sec
            self._set(self.status_lbl, text="TIMER RUNNING", text_color=AMBER if warn_phase else GREEN)
            self._set(self.time_lbl, text=fmt_hms(rem), text_color=AMBER if warn_phase else GREEN)
            self._set(self.info_lbl, text=f"{ACTION_NAME[c.action]} at {fmt_clock(c.end_ts)}", text_color=TEXT)
        else:
            self._set(self.status_lbl, text="NO ACTIVE TIMER", text_color=GRAY)
            self._set(self.time_lbl, text="--:--:--", text_color=GRAY)
            self._set(self.info_lbl, text="Pick a time below to start", text_color=GRAY)
        state = "normal" if running else "disabled"
        self._set(self.btn_extend, state=state)
        self._set(self.btn_cancel, state=state)

        if self.bot is None:
            self._set(self.tg_lbl, text="Telegram: not set up", text_color=GRAY)
        elif self.bot.online:
            who = f" (@{self.bot.username})" if self.bot.username else ""
            self._set(self.tg_lbl, text=f"Telegram: connected{who}", text_color=GREEN)
        else:
            err = f" {self.bot.last_error}" if self.bot.last_error else ""
            self._set(self.tg_lbl, text=f"Telegram: connecting...{err}"[:46], text_color=AMBER)
        self._refresh_tray(running, rem)

    # ---------- exit ----------
    def quit_app(self):
        if self.core.running:
            self.show_window()
            if self.core.action == "H":
                msg = "A Hibernate timer is running.\nIf you exit Sleepify the timer will be CANCELLED.\n\nExit anyway?"
            else:
                msg = "A Shutdown timer is running.\nWindows will still shut the PC down on time even after you exit.\n\nExit anyway?"
            if not messagebox.askyesno(APP_NAME, msg, parent=self):
                return
            if self.core.action == "H":
                self.core.cancel("exit")
                if self.bot:
                    self.bot.send(t("exit_hib"), wait=True)
        self._closing = True
        self.stop_event.set()
        self._stop_bot()
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.srv.close()
        except Exception:
            pass
        self.destroy()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def _install_excepthooks():
    def hook(exc_type, exc, tb):
        log_error("".join(traceback.format_exception(exc_type, exc, tb)))
    sys.excepthook = hook
    threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)


def main():
    if "--install" in sys.argv:
        sys.exit(install_shortcuts())
    if "--uninstall" in sys.argv:
        sys.exit(remove_shortcuts())
    _install_excepthooks()
    try:  # own taskbar identity (so Windows doesn't group us under Python)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sleepify.PCSleepTimer")
    except Exception:
        pass

    srv, status = single_instance()
    if status == "forwarded":
        return                       # the running copy will show its window
    if status == "busy":
        messagebox.showerror(APP_NAME, f"Port {SINGLE_PORT} is used by another program, "
                                       "so Sleepify can't start. Change SINGLE_PORT in Sleepify.py.")
        return
    hold_mutex()

    migrate_legacy_config()
    cfg = load_config()
    set_language(cfg["language"])
    hooks = Hooks()
    core = TimerCore(hooks, cfg["warning_minutes"])
    app = App(cfg, core, hooks, build_icons(), srv, "--hidden" in sys.argv)
    app.mainloop()
    os._exit(0)     # the tray thread must not keep a hidden process alive


if __name__ == "__main__":
    main()
