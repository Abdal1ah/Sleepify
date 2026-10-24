# -*- coding: utf-8 -*-
"""Settings stored in %APPDATA%\\Sleepify\\config.json."""
import copy
import json
import os
import uuid

from . import common as C

WATCH_DEFAULTS = {
    "action": "shutdown", "rule_close": True, "rule_idle": True, "idle_minutes": 5,
    "use_cpu": True, "cpu_limit": 3.0, "use_io": True, "io_limit_mb": 1.0,
    "use_net": False, "net_limit_kb": 100.0, "grace_seconds": 60, "max_hours": 12,
}

DEFAULTS = {
    "bot_token": "", "chat_id": None, "device_name": "", "language": "en", "telegram_skipped": False,
    "warning_minutes": 10, "keep_awake": True,
    "screenshot_enabled": False, "screenshot_on_finish": False,
    "per_app_network": False, "check_updates": True, "update_repo": "",
    "watch": WATCH_DEFAULTS, "schedules": [],
}


def _num(value, default, lo, hi, cast=float):
    try:
        return min(hi, max(lo, cast(value)))
    except (TypeError, ValueError):
        return default


def clean_watch(raw):
    w = copy.deepcopy(WATCH_DEFAULTS)
    if not isinstance(raw, dict):
        return w
    if raw.get("action") in C.ACTIONS:
        w["action"] = raw["action"]
    for k in ("rule_close", "rule_idle", "use_cpu", "use_io", "use_net"):
        if k in raw:
            w[k] = bool(raw[k])
    w["idle_minutes"] = _num(raw.get("idle_minutes"), 5, 1, 240, int)
    w["cpu_limit"] = _num(raw.get("cpu_limit"), 3.0, 0.1, 100.0)
    w["io_limit_mb"] = _num(raw.get("io_limit_mb"), 1.0, 0.01, 5000.0)
    w["net_limit_kb"] = _num(raw.get("net_limit_kb"), 100.0, 1.0, 1000000.0)
    w["grace_seconds"] = _num(raw.get("grace_seconds"), 60, 10, 600, int)
    w["max_hours"] = _num(raw.get("max_hours"), 12, 0, 72, int)
    return w


def clean_schedules(raw):
    out = []
    for s in raw if isinstance(raw, list) else []:
        try:
            h, m = str(s["time"]).split(":")
            if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                continue
            days = sorted({int(d) for d in s.get("days", []) if 0 <= int(d) <= 6})
            item = {"id": str(s.get("id") or uuid.uuid4().hex[:6]), "time": f"{int(h):02d}:{int(m):02d}",
                    "days": days, "action": s.get("action") if s.get("action") in C.ACTIONS else "shutdown",
                    "enabled": bool(s.get("enabled", True))}
            if not days and s.get("date"):
                item["date"] = str(s["date"])[:10]
            out.append(item)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def load_config():
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(C.CONFIG_FILE, encoding="utf-8-sig") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("config is not an object")
    except FileNotFoundError:
        return cfg
    except (OSError, ValueError) as e:
        C.log_error(f"config.json could not be read, using defaults: {e}")
        return cfg

    if raw.get("language") in ("en", "ar"):
        cfg["language"] = raw["language"]
    cfg["device_name"] = str(raw.get("device_name") or "").strip()[:30]
    for k in ("telegram_skipped", "keep_awake", "screenshot_enabled", "screenshot_on_finish",
              "per_app_network", "check_updates"):
        if k in raw:
            cfg[k] = bool(raw[k])
    cfg["warning_minutes"] = _num(raw.get("warning_minutes"), 10, 1, 180, int)
    cfg["update_repo"] = str(raw.get("update_repo") or "").strip()
    cfg["watch"] = clean_watch(raw.get("watch"))
    cfg["schedules"] = clean_schedules(raw.get("schedules"))

    token = str(raw.get("bot_token", "")).strip()
    try:
        chat_id = int(raw.get("chat_id"))
    except (TypeError, ValueError):
        chat_id = None
    if C.TOKEN_RE.fullmatch(token) and chat_id is not None:
        cfg["bot_token"], cfg["chat_id"] = token, chat_id
    return cfg


def save_config(cfg):
    data = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    tmp = C.CONFIG_FILE + ".tmp"
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, C.CONFIG_FILE)
        return True
    except OSError as e:
        C.log_error(f"could not save config: {e}")
        return False


def update_config(**changes):
    cfg = load_config()
    cfg.update(changes)
    return save_config(cfg)


def has_telegram(cfg):
    return bool(cfg.get("bot_token")) and cfg.get("chat_id") is not None


def migrate_legacy_config():
    """v0.x kept config.json next to the script. Copy it to %APPDATA%\\Sleepify once."""
    if os.path.exists(C.CONFIG_FILE) or not os.path.exists(C.LEGACY_CONFIG):
        return False
    try:
        with open(C.LEGACY_CONFIG, encoding="utf-8-sig") as f:
            raw = json.load(f)
        cfg = copy.deepcopy(DEFAULTS)
        cfg.update(bot_token=str(raw.get("bot_token", "")).strip(), chat_id=int(raw.get("chat_id")),
                   warning_minutes=int(raw.get("warning_minutes", 10)),
                   device_name=C.default_device_name(), language="ar")
        if not C.TOKEN_RE.fullmatch(cfg["bot_token"]):
            return False
        ok = save_config(cfg)
        if ok:
            C.log_event("Imported the old config.json into the new settings folder")
        return ok
    except (OSError, ValueError, TypeError) as e:
        C.log_error(f"old config.json could not be imported: {e}")
        return False
