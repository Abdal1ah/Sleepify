# -*- coding: utf-8 -*-
"""Telegram: the Bot API, the commands you can send, the buttons, and linking your account with a code."""
import json
import secrets
import threading
import time
from collections import namedtuple
from datetime import datetime

import requests

from . import common as C
from .core import APP_RUN, compute_stats
from .i18n import action_label, fmt_clock, t

Reply = namedtuple("Reply", "text buttons special", defaults=(None, None))


class TelegramError(Exception):
    def __init__(self, code, description):
        super().__init__(f"Telegram error {code}: {description}")
        self.code = code


def tg_api(token, method, params=None, post=False, timeout=10, files=None):
    """Calls the Telegram Bot API and returns the 'result' part. Raises TelegramError / requests errors."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    if post or files:
        r = requests.post(url, data=params, files=files, timeout=timeout)
    else:
        r = requests.get(url, params=params, timeout=timeout)
    data = r.json()
    if not data.get("ok"):
        raise TelegramError(data.get("error_code"), data.get("description"))
    return data.get("result")


def keyboard(buttons):
    """[[ (label, data), ... ], ...] -> reply_markup JSON."""
    return json.dumps({"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row]
                                           for row in buttons]}, ensure_ascii=False)


# ---------------------------------------------------------------- commands
class Context:
    """What the commands need from the app."""

    def __init__(self, core, scheduler, get_cfg, get_watch, stop_watch, get_events):
        self.core, self.scheduler = core, scheduler
        self.get_cfg, self.get_watch, self.stop_watch, self.get_events = get_cfg, get_watch, stop_watch, get_events


def _status(ctx):
    core = ctx.core
    lines = []
    if core.running:
        lines.append(t("status_running", action=action_label(core.action), left=C.fmt_hms(core.remaining()),
                       at=fmt_clock(core.end_ts)))
        buttons = [[(t("btn_extend", mins=C.EXTEND_MINUTES), "ext"), (t("btn_pause"), "pause"),
                    (t("btn_cancel"), "cancel")]]
    elif core.paused:
        lines.append(t("status_paused", action=action_label(core.action), left=C.fmt_hms(core.remaining())))
        buttons = [[(t("btn_resume"), "resume"), (t("btn_cancel"), "cancel")]]
    else:
        lines.append(t("status_none"))
        buttons = None
    job = ctx.get_watch()
    if job is not None:
        lines.append(_watch_text(job))
        buttons = (buttons or []) + [[(t("btn_stopwatch"), "stopwatch")]]
    return Reply("\n\n".join(lines), buttons)


def _watch_text(job):
    s = job.last or {"cpu": 0, "io": 0, "net": None, "running": True}
    left = job.idle_left()
    net = "" if s.get("net") is None else f" | net {s['net'] / 1024:.0f} KB/s"
    idle = "" if left is None else t("watch_idle_in", mins=max(1, round(left / 60)))
    return t("watch_status", app=job.app, cpu=f"{s['cpu']:.1f}", io=f"{s['io'] / 1048576:.1f}", net=net, idle=idle)


def run_command(ctx, cmd, args):
    """Runs one Telegram command and returns a Reply (text, optional buttons, optional special)."""
    core = ctx.core
    args = (args or "").strip()

    if cmd in ("start", "help"):
        return Reply(t("help"))
    if cmd == "status":
        return _status(ctx)

    if cmd in ("shutdown", "restart", "hibernate", "sleep", "lock", "display"):
        if cmd == "lock" and not args:                      # lock the PC right now
            ok = core.h.perform("lock")
            return Reply(t("lock_now") if ok else t("act_failed", action=action_label("lock")))
        sec = C.parse_duration(args)
        if sec is None:
            return Reply(t("bad_duration", cmd=cmd))
        replaced = core.active
        ok, msg = core.start(sec, cmd, "telegram")
        if not ok:
            return Reply("❌ " + t(msg))
        text = t("started", action=action_label(cmd), dur=C.fmt_human(sec), at=fmt_clock(core.end_ts))
        if replaced:
            text += "\n" + t("replaced")
        if cmd in APP_RUN:
            text += "\n" + t("app_run_note")
        return Reply(text, [[(t("btn_extend", mins=C.EXTEND_MINUTES), "ext"), (t("btn_cancel"), "cancel")]])

    if cmd == "extend":
        sec = C.parse_duration(args) if args else C.EXTEND_MINUTES * 60
        if sec is None:
            return Reply(t("bad_duration_extend"))
        ok, msg = core.extend(sec, "telegram")
        if not ok:
            return Reply("❌ " + t(msg))
        return Reply(t("extended", dur=C.fmt_human(sec), left=C.fmt_hms(core.remaining()),
                       at=fmt_clock(core.end_ts) if core.running else "-"))

    if cmd == "cancel":
        ok, _ = core.cancel("telegram")
        return Reply(t("cancelled") if ok else t("cancel_none"))
    if cmd == "pause":
        ok, msg = core.pause("telegram")
        return Reply(t("paused_ok", left=C.fmt_hms(core.remaining())) if ok else "❌ " + t(msg))
    if cmd == "resume":
        ok, msg = core.resume("telegram")
        return Reply(t("resumed_ok", left=C.fmt_hms(core.remaining()), at=fmt_clock(core.end_ts)) if ok
                     else "❌ " + t(msg))

    if cmd == "at":
        parts = args.split()
        clock = C.parse_clock(parts[0]) if parts else None
        action = (parts[1].lower() if len(parts) > 1 else "shutdown")
        if clock is None or action not in C.ACTIONS:
            return Reply(t("at_bad"))
        item = ctx.scheduler.add(f"{clock[0]:02d}:{clock[1]:02d}", action)
        return Reply(t("at_ok", action=action_label(action), time=item["time"], date=item["date"]))
    if cmd == "schedules":
        items = ctx.scheduler.get_list()
        if not items:
            return Reply(t("schedules_none"))
        return Reply("\n".join(t("schedule_line", time=s["time"], action=action_label(s["action"]),
                                 days=",".join(str(d + 1) for d in s["days"]) or s.get("date", "")) for s in items))

    if cmd == "screenshot":
        if not ctx.get_cfg().get("screenshot_enabled"):
            return Reply(t("screenshot_off"))
        return Reply(t("screenshot_wait"), special="screenshot")

    if cmd == "stats":
        st = compute_stats(ctx.get_events(), datetime.now())
        typical = "-" if st["typical"] is None else fmt_clock_hm(*st["typical"])
        return Reply(t("stats_text", n=7, started=st["started"], executed=st["executed"],
                       cancelled=st["cancelled"], typical=typical))

    if cmd == "watch":
        job = ctx.get_watch()
        if job is None:
            return Reply(t("watch_none"))
        return Reply(_watch_text(job), [[(t("btn_stopwatch"), "stopwatch")]])
    if cmd == "stopwatch":
        return _stop_watch(ctx)

    return Reply(t("unknown_cmd"))


def fmt_clock_hm(h, m):
    return fmt_clock(datetime.now().replace(hour=h, minute=m, second=0).timestamp()).split(" (")[0]


def _stop_watch(ctx):
    if ctx.get_watch() is None:
        return Reply(t("watch_none"))
    ctx.stop_watch()
    return Reply(t("watch_stopped"))


def run_callback(ctx, data):
    """A tap on an inline button."""
    if data == "ext":
        return run_command(ctx, "extend", "")
    if data in ("cancel", "pause", "resume"):
        return run_command(ctx, data, "")
    if data == "stopwatch":
        return _stop_watch(ctx)
    return Reply(t("unknown_cmd"))


def bot_commands():
    names = ("status", "shutdown", "restart", "hibernate", "sleep", "lock", "extend", "cancel", "pause",
             "resume", "at", "screenshot", "stats", "watch", "help")
    return [(c, t("cmd_" + c)) for c in names]


# ---------------------------------------------------------------- the bot (runs in the background)
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

    def _header(self):
        return f"💻 {self.device}\n" if self.device else ""

    def send(self, text, buttons=None, wait=False):
        params = {"chat_id": self.chat_id, "text": self._header() + text}
        if buttons:
            params["reply_markup"] = keyboard(buttons)

        def _do():
            try:
                tg_api(self.token, "sendMessage", params, post=True)
            except Exception as e:
                C.log_error(f"sendMessage failed: {e}")
        if wait:
            _do()
        else:
            threading.Thread(target=_do, daemon=True).start()

    def send_photo(self, jpeg_bytes, caption=""):
        def _do():
            try:
                tg_api(self.token, "sendPhoto", {"chat_id": self.chat_id, "caption": self._header() + caption},
                       files={"photo": ("screen.jpg", jpeg_bytes, "image/jpeg")}, timeout=60)
            except Exception as e:
                C.log_error(f"sendPhoto failed: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def answer_callback(self, cb_id, text=""):
        def _do():
            try:
                tg_api(self.token, "answerCallbackQuery", {"callback_query_id": cb_id, "text": text[:150]}, post=True)
            except Exception as e:
                C.log_error(f"answerCallbackQuery failed: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        try:
            me = tg_api(self.token, "getMe")
            self.online = True
            self.username = (me or {}).get("username", "")
        except Exception as e:
            self.last_error = C.scrub(e)[:80]
            C.log_error(f"getMe failed: {e}")
        try:
            tg_api(self.token, "setMyCommands", {"commands": json.dumps(
                [{"command": c, "description": d} for c, d in bot_commands()], ensure_ascii=False)}, post=True)
        except Exception as e:
            C.log_error(f"setMyCommands failed: {e}")

        offset = None
        backoff = 2
        while not self.stop.is_set():
            try:
                params = {"timeout": 25, "allowed_updates": json.dumps(["message", "callback_query"])}
                if offset is not None:
                    params["offset"] = offset
                updates = tg_api(self.token, "getUpdates", params, timeout=35)
                self.online, self.last_error, backoff = True, "", 2
                for upd in updates or []:
                    offset = upd["update_id"] + 1
                    self._handle(upd)
            except Exception as e:
                self.online = False
                self.last_error = C.scrub(e)[:80]
                C.log_error(f"Telegram polling: {e}")
                self.stop.wait(backoff)
                backoff = min(backoff * 2, 60)

    def _handle(self, upd):
        cb = upd.get("callback_query")
        if cb:                                             # a tap on a button
            msg = cb.get("message") or {}
            if cb.get("from", {}).get("id") != self.chat_id or msg.get("chat", {}).get("id") != self.chat_id:
                return
            if time.time() - msg.get("date", 0) > 3600:     # old buttons must not act on a newer timer
                self.answer_callback(cb["id"], t("cb_expired"))
                return
            self.inbox.put(("cb", cb.get("data", ""), cb["id"]))
            return
        msg = upd.get("message")
        if not msg:
            return
        # only YOU: both the chat and the sender must be your id
        if msg.get("chat", {}).get("id") != self.chat_id or msg.get("from", {}).get("id") != self.chat_id:
            return
        if time.time() - msg.get("date", 0) > 120:          # ignore old messages (sent while the PC was off)
            return
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            self.inbox.put(("tg", "help", ""))
            return
        parts = text.split(maxsplit=1)
        self.inbox.put(("tg", parts[0][1:].split("@")[0].lower(), parts[1] if len(parts) > 1 else ""))


# ---------------------------------------------------------------- linking your account with a one-time code
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no 0/O/1/I to avoid typos


def new_pair_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def valid_token_format(token):
    return bool(C.TOKEN_RE.fullmatch((token or "").strip()))


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
                self.error = C.scrub(e)[:80]
                self.stop.wait(3)
