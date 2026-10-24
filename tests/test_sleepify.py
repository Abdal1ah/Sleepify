"""Logic tests for Sleepify (no window is opened). Run with:  py -m pytest -q"""
import json
import os
import queue
import re
import shutil
import string
import struct
import threading
import time
from datetime import datetime

import pytest

from sleepify import common as C
from sleepify import config as cfgmod
from sleepify import i18n, icons, monitor, rtl, system, telegram, updates
from sleepify.core import APP_RUN, Scheduler, TimerCore, compute_stats

TOKEN = "1234567890:" + "A" * 35       # fake token with the right shape


# ---------------------------------------------------------------- helpers
class FakeHooks:
    def __init__(self):
        self.cmds, self.beeps, self.toasts, self.tgs, self.logs, self.events, self.awake = [], [], [], [], [], [], []
        self.performed = []
        self.rc = {}
        self.hib = True
        self.perform_ok = True

    def run(self, cmd):
        self.cmds.append(cmd)
        return self.rc.get(tuple(cmd[:2]), 0)

    def perform(self, action):
        self.performed.append(action)
        return self.perform_ok

    def beep(self, f, ms): self.beeps.append((f, ms))
    def toast(self, t, m): self.toasts.append((t, m))
    def tg(self, text, buttons=None): self.tgs.append((text, buttons))
    def log(self, text): self.logs.append(text)
    def history(self, kind, **kw): self.events.append((kind, kw))
    def keep_awake(self, on): self.awake.append(on)
    def hibernate_ok(self): return self.hib


class Clock:
    def __init__(self, t=1_000_000.0): self.t = t
    def __call__(self): return self.t


@pytest.fixture(autouse=True)
def clean_files(tmp_path, monkeypatch):
    for name, fn in (("STATE_FILE", "state.json"), ("CONFIG_FILE", "config.json"), ("LEGACY_CONFIG", "legacy.json"),
                     ("HISTORY_FILE", "history.jsonl"), ("LOG_FILE", "log.txt"), ("ERROR_FILE", "error.log")):
        monkeypatch.setattr(C, name, str(tmp_path / fn))
    monkeypatch.setattr(C, "DATA_DIR", str(tmp_path))
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def make_core(warn=10):
    h, clk = FakeHooks(), Clock()
    return TimerCore(h, warn, clk), h, clk


# ---------------------------------------------------------------- parsing / formatting
@pytest.mark.parametrize("text,expected", [
    ("1h30m", 5400), ("45m", 2700), ("45m30s", 2730), ("90", 5400), ("30s", 30), ("2h", 7200),
    (" 1h 30m ", 5400), ("٣٠", 1800), ("", None), ("abc", None), ("1x", None), ("m", None), ("10m5h", None),
])
def test_parse_duration(text, expected):
    assert C.parse_duration(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("03:30", (3, 30)), ("3:30pm", (15, 30)), ("12am", (0, 0)), ("0330", (3, 30)), ("15", (15, 0)),
    ("25:00", None), ("3:75", None), ("13pm", None), ("", None), ("noon", None),
])
def test_parse_clock(text, expected):
    assert C.parse_clock(text) == expected


def test_formatting_and_versions():
    assert C.fmt_hms(3725) == "01:02:05" and C.fmt_human(5400) == "1h 30m" and C.fmt_human(45) == "45s"
    assert C.version_tuple("v1.2.10") > C.version_tuple("1.2.9") and C.version_tuple("1.1.0-dev") == (1, 1, 0)
    ts = datetime(2026, 1, 1, 15, 5).timestamp()
    assert i18n.fmt_clock(ts, "en").startswith("3:05 PM") and i18n.fmt_clock(ts, "ar").startswith("3:05 م")


# ---------------------------------------------------------------- timer core
def test_shutdown_timer_full_life():
    core, h, clk = make_core()
    assert core.start(1200, "shutdown") == (True, "ok")
    assert ["shutdown", "-s", "-t", "1200"] in h.cmds
    clk.t += 600; core.tick()                                   # 10 minutes left -> warning
    assert core.warned and h.beeps == [(1500, 2000)] and len(h.toasts) == 1
    text, buttons = h.tgs[-1]
    assert "10" in text and [b[1] for b in buttons[0]] == ["ext", "cancel"]
    core.tick(); assert len(h.beeps) == 1                       # not repeated
    clk.t += 597; core.tick()
    assert h.beeps[-1] == (1000, 3000)
    clk.t += 3; core.tick()
    assert not core.running and not os.path.exists(C.STATE_FILE) and h.performed == []
    assert [e[0] for e in h.events] == ["start", "execute"]


def test_restart_uses_the_restart_flag():
    core, h, clk = make_core()
    core.start(90, "restart")
    assert ["shutdown", "-r", "-t", "90"] in h.cmds


@pytest.mark.parametrize("action", APP_RUN)
def test_actions_run_by_sleepify(action):
    core, h, clk = make_core()
    core.start(60, action)
    assert not any(c[:2] in (["shutdown", "-s"], ["shutdown", "-r"]) for c in h.cmds)   # Windows gets no timer
    clk.t += 60; core.tick()
    assert h.performed == [action] and not core.running


def test_action_failure_is_reported():
    core, h, clk = make_core()
    h.perform_ok = False
    core.start(5, "sleep"); clk.t += 5; core.tick()
    assert h.toasts and "Sleep" in h.tgs[-1][0]
    core2, h2, clk2 = make_core(); h2.perform_ok = False
    core2.start(5, "hibernate"); clk2.t += 5; core2.tick()
    assert "powercfg" in h2.tgs[-1][0]


def test_extend_rearms_the_warning():
    core, h, clk = make_core()
    core.start(700, "shutdown"); clk.t += 150; core.tick()
    assert core.warned and len(h.beeps) == 1
    assert core.extend(600) == (True, "ok") and core.warned is False and core.total == 1300
    assert h.cmds[-2:] == [["shutdown", "-a"], ["shutdown", "-s", "-t", "1150"]]
    clk.t += 560; core.tick()
    assert len(h.beeps) == 2


def test_short_timer_has_no_warning_but_final_beep():
    core, h, clk = make_core()
    core.start(30, "shutdown"); core.tick()
    assert core.warned and not h.beeps
    clk.t += 27; core.tick()
    assert h.beeps == [(1000, 3000)]


def test_warn_now_warns_at_once():
    core, h, clk = make_core()
    core.start(300, "shutdown", "schedule", warn_now=True); core.tick()
    assert len(h.beeps) == 1 and "5" in h.tgs[-1][0]


def test_hibernate_turned_off_is_refused():
    core, h, clk = make_core()
    h.hib = False
    assert core.start(60, "hibernate") == (False, "err_no_hib")
    assert "powercfg" in i18n.t("err_no_hib")
    h.hib = None
    assert core.start(60, "hibernate")[0] is True


def test_pc_slept_through_the_deadline():
    core, h, clk = make_core()
    core.start(120, "hibernate"); clk.t += 4000; core.tick()
    assert not core.running and h.performed == [] and h.events[-1][0] == "missed"


def test_cancel_and_validation():
    core, h, clk = make_core()
    core.start(500, "shutdown")
    assert core.cancel("app")[0] and not core.running and h.tgs
    assert h.cmds[-1] == ["shutdown", "-a"]
    assert core.cancel("app") == (False, "err_none")
    assert core.start(0, "shutdown") == (False, "err_zero") and core.start(10 ** 7, "shutdown") == (False, "err_max")
    assert core.start(60, "explode") == (False, "err_zero")
    h.rc[("shutdown", "-s")] = 5
    assert core.start(100, "shutdown") == (False, "err_denied") and not core.running


def test_pause_and_resume():
    core, h, clk = make_core()
    core.start(1000, "shutdown"); clk.t += 100
    assert core.pause() == (True, "ok") and core.paused and not core.running and core.remaining() == 900
    assert h.cmds[-1] == ["shutdown", "-a"] and json.load(open(C.STATE_FILE))["paused_left"] == 900
    clk.t += 5000; core.tick()                                  # time passes while paused: nothing happens
    assert core.paused and core.remaining() == 900
    assert core.extend(60)[0] and core.remaining() == 960
    assert core.resume() == (True, "ok") and core.running and core.remaining() == 960 and core.total == 1060
    assert ["shutdown", "-s", "-t", "960"] in h.cmds
    assert core.resume() == (False, "err_not_paused")
    clk.t += 957; assert core.pause() == (False, "err_late")


def test_resume_from_disk():
    core, h, clk = make_core()
    core.start(900, "shutdown")
    other = TimerCore(FakeHooks(), 10, clk); clk.t += 100
    assert other.resume_from_disk() == "resumed" and other.remaining() == 800 and not other.warned
    core.pause(); third = TimerCore(FakeHooks(), 10, clk)
    assert third.resume_from_disk() == "paused" and third.paused and third.remaining() == core.paused_left
    core.cancel("x"); core.start(900, "hibernate")
    fourth = TimerCore(FakeHooks(), 10, clk)
    assert fourth.resume_from_disk() == "app_timer_lost" and not fourth.running and not os.path.exists(C.STATE_FILE)


def test_keep_awake_follows_the_timer():
    core, h, clk = make_core()
    core.start(100, "shutdown"); assert h.awake[-1] is True
    core.cancel("x"); assert h.awake[-1] is False
    core.set_watching(True); assert h.awake[-1] is True
    core.set_watching(False); assert h.awake[-1] is False
    core.set_keep_awake_pref(False); core.start(100, "shutdown"); assert h.awake[-1] is False


# ---------------------------------------------------------------- schedules
def dt_ts(*a): return datetime(*a).timestamp()


def make_sched(now_ts):
    core, h, clk = make_core(10)
    clk.t = now_ts
    store = []
    return Scheduler(core, h, lambda: store, lambda: None, clk), core, h, clk, store


def test_next_fire_for_days_and_once():
    sc, *_ = make_sched(dt_ts(2026, 10, 19, 12, 0))                 # a Monday
    now = datetime(2026, 10, 19, 12, 0)
    mon_fri = {"time": "03:30", "days": [0, 1, 2, 3, 4], "action": "shutdown"}
    assert Scheduler.next_fire(mon_fri, now) == datetime(2026, 10, 20, 3, 30)
    sat = {"time": "09:00", "days": [5], "action": "shutdown"}
    assert Scheduler.next_fire(sat, now) == datetime(2026, 10, 24, 9, 0)
    once = {"time": "03:30", "days": [], "date": "2026-10-20", "action": "shutdown"}
    assert Scheduler.next_fire(once, now) == datetime(2026, 10, 20, 3, 30)


def test_add_once_picks_today_or_tomorrow():
    sc, core, h, clk, store = make_sched(dt_ts(2026, 10, 19, 12, 0))
    assert sc.add("13:00", "shutdown")["date"] == "2026-10-19"
    assert sc.add("11:00", "shutdown")["date"] == "2026-10-20"


def test_schedule_arms_with_a_warning_then_executes():
    sc, core, h, clk, store = make_sched(dt_ts(2026, 10, 19, 23, 0))
    sc.add("23:30", "shutdown")
    clk.t += 1000; sc.tick(); assert not core.running             # 13 minutes early: too soon
    clk.t += 220; sc.tick()                                        # 9 min 20 s left: arms with the warning
    assert core.running and core.source == "schedule" and ["shutdown", "-s", "-t", "580"] in h.cmds
    core.tick(); assert len(h.beeps) == 1
    clk.t += 581; sc._next = 0; sc.tick()
    core.tick()
    assert not core.running and store == []                       # a one-time schedule is removed afterwards


def test_schedule_waits_while_a_timer_is_running_and_reports_missed():
    sc, core, h, clk, store = make_sched(dt_ts(2026, 10, 19, 23, 0))
    sc.add("23:05", "shutdown")
    core.start(3600, "hibernate")
    clk.t += 120; sc.tick()
    assert core.action == "hibernate"                              # the manual timer wins
    clk.t += 400; sc._next = 0; sc.tick()
    assert store == [] and any(e[0] == "missed" for e in h.events)


def test_repeating_schedule_survives_and_is_not_rearmed_after_cancel():
    sc, core, h, clk, store = make_sched(dt_ts(2026, 10, 19, 23, 0))
    sc.add("23:30", "shutdown", [0])
    clk.t += 1300; sc.tick(); assert core.running
    core.cancel("app"); clk.t += 5; sc._next = 0; sc.tick()
    assert not core.running and len(store) == 1                    # cancelled by the user: stays cancelled


# ---------------------------------------------------------------- watching an app
class FakeSampler:
    def __init__(self): self.s = {"running": True, "cpu": 50.0, "io": 5 * 1048576, "net": None, "count": 2, "unreadable": 0}
    def sample(self): return dict(self.s)


def make_watch(**over):
    cfg = {"app": "setup.exe", **cfgmod.WATCH_DEFAULTS, **over}
    clk, smp = Clock(), FakeSampler()
    return monitor.WatchJob(cfg, smp, clk), smp, clk


def run_for(job, clk, seconds, step=2):
    for _ in range(int(seconds / step)):
        clk.t += step
        job.tick(step)


def test_watch_finishes_when_the_app_goes_idle():
    job, smp, clk = make_watch(idle_minutes=5)
    run_for(job, clk, 600); assert job.state == "waiting"            # busy: CPU 50%, disk 5 MB/s
    smp.s.update(cpu=0.5, io=1000)
    run_for(job, clk, 200); assert job.state == "waiting" and job.idle_left() > 0
    smp.s.update(cpu=40.0); run_for(job, clk, 4)                       # busy again -> the idle clock restarts
    assert job.idle_since is None
    smp.s.update(cpu=0.5); run_for(job, clk, 310)
    assert job.state == "done" and job.reason == "idle"


def test_watch_finishes_when_the_app_closes():
    job, smp, clk = make_watch()
    run_for(job, clk, 10); smp.s["running"] = False
    run_for(job, clk, 4); assert job.state == "waiting"                # a short gap is not enough
    run_for(job, clk, 6); assert job.state == "done" and job.reason == "closed"


def test_watch_rules_and_limits():
    job, smp, clk = make_watch(rule_close=False, use_cpu=False, use_io=True, io_limit_mb=2.0)
    smp.s.update(cpu=90.0, io=1 * 1048576)                              # CPU ignored, disk below the limit
    run_for(job, clk, 330); assert job.state == "done" and job.reason == "idle"
    job2, smp2, clk2 = make_watch(rule_close=False, use_net=True, net_limit_kb=100, use_cpu=False, use_io=False)
    smp2.s["net"] = 500 * 1024
    run_for(job2, clk2, 400); assert job2.state == "waiting"            # still downloading
    smp2.s["net"] = None                                                 # unavailable -> not counted as activity
    run_for(job2, clk2, 320); assert job2.state == "done"


def test_watch_gives_up_after_the_maximum_time():
    job, smp, clk = make_watch(max_hours=1)
    run_for(job, clk, 3700, step=10); assert job.state == "timeout"


def test_real_sampler_sees_this_process():
    name = os.path.basename(__import__("sys").executable)
    s = monitor.AppSampler(name)
    s.sample(); time.sleep(0.3)
    out = s.sample()
    assert out["running"] and out["count"] >= 1 and out["cpu"] >= 0
    assert monitor.AppSampler("no-such-program-xyz.exe").sample()["running"] is False


def test_list_apps_groups_by_name():
    rows = monitor.list_apps(windows={}, include_background=True)
    assert rows and all({"name", "count", "title"} <= set(r) for r in rows)
    assert len({r["name"].lower() for r in rows}) == len(rows)


def test_tcp_table_parsing():
    buf = struct.pack("<I", 2) + struct.pack("<6I", 5, 1, 2, 3, 4, 77) + struct.pack("<6I", 2, 1, 2, 3, 4, 88)
    assert monitor.parse_tcp4_table(buf) == [(5, 1, 2, 3, 4, 77), (2, 1, 2, 3, 4, 88)]
    row6 = struct.pack("<16sII16sIIII", b"a" * 16, 0, 80, b"b" * 16, 0, 443, 5, 99)
    assert monitor.parse_tcp6_table(struct.pack("<I", 1) + row6)[0][-2:] == (5, 99)
   # assert monitor.TcpEstats().available() is False and monitor.TcpEstats().rate({1}, 0) is None


# ---------------------------------------------------------------- telegram commands
def make_ctx(core, sched=None, cfg=None, watch=None):
    stopped = []
    ctx = telegram.Context(core, sched or Scheduler(core, core.h, lambda: [], lambda: None, core.clock),
                           lambda: cfg or {"screenshot_enabled": False}, lambda: watch, lambda: stopped.append(1),
                           lambda: [])
    ctx.stopped = stopped
    return ctx


def labels(buttons): return [b[1] for row in (buttons or []) for b in row]


def test_commands_in_english():
    core, h, clk = make_core(); ctx = make_ctx(core)
    run = lambda cmd, args="": telegram.run_command(ctx, cmd, args)
    assert "No timer" in run("status").text and run("status").buttons is None
    r = run("shutdown", "1h30m"); assert core.running and "Shutdown" in r.text and labels(r.buttons) == ["ext", "cancel"]
    r = run("status"); assert "01:30:00" in r.text and labels(r.buttons) == ["ext", "pause", "cancel"]
    assert "Added" in run("extend").text and core.remaining() == 5400 + 600
    assert "Paused" in run("pause").text and labels(run("status").buttons) == ["resume", "cancel"]
    assert "Resumed" in run("resume").text
    r = run("hibernate", "45m"); assert "replaced" in r.text and "tray" in r.text and core.action == "hibernate"
    assert "cancelled" in run("cancel").text and "no timer" in run("cancel").text
    assert run("restart", "10m").text.startswith("✅") and core.action == "restart"
    assert run("sleep", "10m").text.startswith("✅") and run("lock", "10m").text.startswith("✅")
    assert run("shutdown", "blah").text.startswith("❌") and "/shutdown" in run("help").text
    assert "don't know" in run("foo").text and run("lock").text.startswith("🔒") and h.performed == ["lock"]


def test_commands_in_arabic():
    i18n.set_language("ar")
    core, h, clk = make_core(); ctx = make_ctx(core)
    run = lambda cmd, args="": telegram.run_command(ctx, cmd, args).text
    assert "مفيش" in run("status") and "اشتغل" in run("shutdown", "10m") and "اتمدد" in run("extend", "5m")
    assert "اتوقف" in run("pause") and "اتكمل" in run("resume") and "اتلغى" in run("cancel")
    h.hib = False
    assert "powercfg" in run("hibernate", "5m")


def test_at_schedules_stats_and_screenshot():
    core, h, clk = make_core(); sched = Scheduler(core, h, lambda: store, lambda: None, clk); store = []
    ctx = make_ctx(core, sched)
    assert "scheduled" in telegram.run_command(ctx, "at", "03:30 hibernate").text and store[0]["action"] == "hibernate"
    assert "Use it like" in telegram.run_command(ctx, "at", "banana").text
    assert "03:30" in telegram.run_command(ctx, "schedules", "").text
    assert "off" in telegram.run_command(ctx, "screenshot", "").text
    ctx2 = make_ctx(core, sched, cfg={"screenshot_enabled": True})
    assert telegram.run_command(ctx2, "screenshot", "").special == "screenshot"
    assert "Last 7 days" in telegram.run_command(ctx, "stats", "").text


def test_watch_commands_and_buttons():
    core, h, clk = make_core()
    job, smp, wclk = make_watch()
    job.tick(); ctx = make_ctx(core, watch=job)
    r = telegram.run_command(ctx, "status", ""); assert "setup.exe" in r.text and "stopwatch" in labels(r.buttons)
    assert "Watching setup.exe" in telegram.run_command(ctx, "watch", "").text
    assert "Stopped" in telegram.run_callback(ctx, "stopwatch").text and ctx.stopped
    assert "Nothing" in telegram.run_command(make_ctx(core), "watch", "").text


def test_inline_button_taps():
    core, h, clk = make_core(); ctx = make_ctx(core)
    core.start(600, "shutdown")
    assert "Added" in telegram.run_callback(ctx, "ext").text and core.remaining() == 1200
    telegram.run_callback(ctx, "pause"); assert core.paused
    telegram.run_callback(ctx, "resume"); assert core.running
    telegram.run_callback(ctx, "cancel"); assert not core.active
    assert "don't know" in telegram.run_callback(ctx, "wat").text


# ---------------------------------------------------------------- telegram bot
def make_bot():
    q = queue.Queue()
    return telegram.TelegramBot(TOKEN, 111, q, "Home PC"), q


def upd(chat, frm, text, date=None):
    return {"update_id": 1, "message": {"chat": {"id": chat}, "from": {"id": frm}, "text": text,
                                        "date": date or int(time.time())}}


def cb_upd(frm, chat, data, age=0):
    return {"update_id": 2, "callback_query": {"id": "cb1", "from": {"id": frm}, "data": data,
                                               "message": {"chat": {"id": chat}, "date": int(time.time()) - age}}}


def test_only_the_owner_can_send_commands():
    bot, q = make_bot()
    bot._handle(upd(222, 222, "/cancel")); assert q.empty()
    bot._handle(upd(111, 222, "/cancel")); assert q.empty()
    bot._handle(upd(111, 111, "/cancel", int(time.time()) - 500)); assert q.empty()
    bot._handle(upd(111, 111, "/shutdown@My_bot 1h")); assert q.get_nowait() == ("tg", "shutdown", "1h")
    bot._handle(upd(111, 111, "hello")); assert q.get_nowait() == ("tg", "help", "")


def test_only_the_owner_can_tap_buttons(monkeypatch):
    bot, q = make_bot(); answered = []
    monkeypatch.setattr(bot, "answer_callback", lambda i, text="": answered.append(text))
    bot._handle(cb_upd(222, 111, "cancel")); assert q.empty() and not answered      # stranger
    bot._handle(cb_upd(111, 222, "cancel")); assert q.empty()                         # other chat
    bot._handle(cb_upd(111, 111, "cancel", age=7200)); assert q.empty() and answered  # too old
    bot._handle(cb_upd(111, 111, "ext")); assert q.get_nowait() == ("cb", "ext", "cb1")


class Resp:
    def __init__(self, data): self.data = data
    def json(self): return self.data


def test_bot_loop_connects_at_once_and_handles_messages(monkeypatch):
    bot, q = make_bot(); calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url.split("/")[-1], dict(params or {})))
        if url.endswith("/getMe"):
            return Resp({"ok": True, "result": {"username": "Sleepify_A_bot"}})
        if sum(1 for c in calls if c[0] == "getUpdates") == 1:
            return Resp({"ok": True, "result": [{"update_id": 5, "message": {
                "chat": {"id": 111}, "from": {"id": 111}, "text": "/status", "date": int(time.time())}}]})
        bot.stop.set()
        return Resp({"ok": True, "result": []})

    monkeypatch.setattr(telegram.requests, "get", fake_get)
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: Resp({"ok": True, "result": True}))
    bot._loop()
    assert bot.online and bot.username == "Sleepify_A_bot" and q.get_nowait() == ("tg", "status", "")
    ups = [c for c in calls if c[0] == "getUpdates"]
    assert ups[1][1]["offset"] == 6 and "callback_query" in ups[0][1]["allowed_updates"]


def test_bad_token_gives_a_clear_error_without_the_token(monkeypatch):
    bot, q = make_bot(); bot.stop.wait = lambda t: None

    def fake_get(url, params=None, timeout=None):
        if not url.endswith("/getMe"):
            bot.stop.set()
        return Resp({"ok": False, "error_code": 401, "description": "Unauthorized"})
    monkeypatch.setattr(telegram.requests, "get", fake_get)
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: Resp({"ok": True}))
    bot._loop()
    assert not bot.online and "401" in bot.last_error and TOKEN not in bot.last_error


def test_messages_carry_the_device_name_and_buttons(monkeypatch):
    bot, q = make_bot(); sent = {}
    monkeypatch.setattr(telegram, "tg_api", lambda token, method, params=None, post=False, timeout=10, files=None: sent.update(params))
    bot.send("hello", buttons=[[("Cancel", "cancel")]], wait=True)
    assert sent["text"] == "💻 Home PC\nhello" and sent["chat_id"] == 111
    assert json.loads(sent["reply_markup"])["inline_keyboard"][0][0] == {"text": "Cancel", "callback_data": "cancel"}


def test_token_never_appears_in_logs():
    assert TOKEN not in C.scrub(f"HTTPSConnectionPool: https://api.telegram.org/bot{TOKEN}/getUpdates failed")


# ---------------------------------------------------------------- pairing
def test_pair_code_shape():
    codes = {telegram.new_pair_code() for _ in range(50)}
    assert all(len(c) == 6 and set(c) <= set(telegram.CODE_ALPHABET) for c in codes) and len(codes) > 40


def private_msg(text, chat_id=77, sender=77, kind="private", name="Sam"):
    return {"update_id": 9, "message": {"chat": {"id": chat_id, "type": kind}, "from": {"id": sender, "first_name": name}, "text": text}}


def test_pairing_accepts_only_the_right_code_from_a_private_chat():
    code, m = "K7M2QX", telegram.match_pair_update
    assert m(private_msg("/start K7M2QX"), code) == (77, "Sam") and m(private_msg("/start@my_bot k7m2qx"), code) == (77, "Sam")
    assert m(private_msg("K7M2QX"), code) == (77, "Sam")
    for bad in (private_msg("/start WRONG1"), private_msg("/start"), private_msg("hello K7M2QX there"),
                private_msg("/start K7M2QX", kind="group"), private_msg("/start K7M2QX", sender=5), {"update_id": 1}):
        assert m(bad, code) is None


def test_pairing_watcher_finds_the_owner(monkeypatch):
    calls = []

    def fake_api(token, method, params=None, post=False, timeout=10, files=None):
        calls.append((method, dict(params or {})))
        if method == "getUpdates" and len([c for c in calls if c[0] == "getUpdates"]) == 1:
            return [private_msg("/start NOPE12", chat_id=1, sender=1), {**private_msg("/start K7M2QX"), "update_id": 12}]
        return []
    monkeypatch.setattr(telegram, "tg_api", fake_api)
    w = telegram.PairingWatcher(TOKEN, "K7M2QX"); w.start(); w.join(timeout=5)
    assert w.result == (77, "Sam") and ("getUpdates", {"offset": 13, "timeout": 0}) in calls


def test_token_shape_check():
    assert telegram.valid_token_format(TOKEN) and not telegram.valid_token_format("PASTE_TOKEN_HERE")


# ---------------------------------------------------------------- config / history / updates
def test_config_roundtrip_defaults_and_cleaning():
    cfg = cfgmod.load_config()
    assert cfg["language"] == "en" and not cfgmod.has_telegram(cfg) and cfg["watch"]["idle_minutes"] == 5 and cfg["keep_awake"]
    cfg.update(bot_token=TOKEN, chat_id=123, device_name="Home PC", language="ar", warning_minutes=15, screenshot_enabled=True)
    cfg["schedules"] = [{"id": "a1", "time": "3:5", "days": [0, 9], "action": "nope"}, {"time": "99:00"}, "junk"]
    cfg["watch"]["idle_minutes"] = 9999
    assert cfgmod.save_config(cfg)
    again = cfgmod.load_config()
    assert cfgmod.has_telegram(again) and again["language"] == "ar" and again["warning_minutes"] == 15
    assert again["screenshot_enabled"] is True and again["watch"]["idle_minutes"] == 240
    assert again["schedules"] == [{"id": "a1", "time": "03:05", "days": [0], "action": "shutdown", "enabled": True}]
    assert cfgmod.update_config(warning_minutes=20) and cfgmod.load_config()["bot_token"] == TOKEN


def test_broken_config_and_legacy_import():
    with open(C.CONFIG_FILE, "w") as f:
        f.write("{not json")
    assert not cfgmod.has_telegram(cfgmod.load_config())
    os.remove(C.CONFIG_FILE)
    with open(C.LEGACY_CONFIG, "w") as f:
        json.dump({"bot_token": TOKEN, "chat_id": 424242424, "warning_minutes": 12}, f)
    assert cfgmod.migrate_legacy_config() is True
    cfg = cfgmod.load_config()
    assert cfgmod.has_telegram(cfg) and cfg["chat_id"] == 424242424 and cfg["language"] == "ar" and cfg["device_name"]
    assert cfgmod.migrate_legacy_config() is False


def test_history_and_stats():
    base = datetime(2026, 10, 19, 12, 0)
    for day, hour in ((18, 3), (17, 2), (16, 3)):
        C.add_history("start", action="shutdown", seconds=100)
        C.add_history("execute", action="shutdown")
    events = C.read_history()
    for e, h in zip(events[1::2], (3, 2, 3)):           # put the "execute" events at known times
        e["ts"] = datetime(2026, 10, 18, h, 0).isoformat()
    for e in events[0::2]:
        e["ts"] = datetime(2026, 10, 18, 1, 0).isoformat()
    events.append({"ts": datetime(2026, 9, 1).isoformat(), "kind": "cancel"})        # too old
    events.append({"ts": datetime(2026, 10, 18, 5, 0).isoformat(), "kind": "cancel"})
    st = compute_stats(events, base)
    assert (st["started"], st["executed"], st["cancelled"]) == (3, 3, 1) and st["typical"] == (2, 40)


def test_update_check(monkeypatch):
    class R:
        status_code = 200
        def json(self): return {"tag_name": "v1.2.0", "html_url": "https://example/rel"}
    monkeypatch.setattr(updates.requests, "get", lambda *a, **k: R())
    assert updates.check_latest("me/Sleepify", "1.1.0") == ("1.2.0", "https://example/rel")
    assert updates.check_latest("me/Sleepify", "1.2.0") is None and updates.check_latest("", "1.0.0") is None
    monkeypatch.setattr(updates.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert updates.check_latest("me/Sleepify", "1.0.0") is None
    assert updates.repo_name({"update_repo": " a/b "}) == "a/b"


# ---------------------------------------------------------------- languages
def placeholders(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_both_languages_match_key_for_key():
    en, ar = i18n.STR["en"], i18n.STR["ar"]
    assert set(en) == set(ar)
    for key in en:
        assert en[key].strip() and ar[key].strip()
        assert placeholders(en[key]) == placeholders(ar[key]), key


def test_every_key_used_in_the_code_exists():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sleepify")
    used = set()
    for name in os.listdir(root):
        if name.endswith(".py"):
            used |= set(re.findall(r'\bt\(\s*"([a-z0-9_]+)"', open(os.path.join(root, name), encoding="utf-8").read()))
    assert not [k for k in used if not k.endswith("_") and k not in i18n.STR["en"]]   # 'act_' etc. are prefixes
    for action in C.ACTIONS:
        assert "act_" + action in i18n.STR["en"]
    for key in ("err_zero", "err_max", "err_denied", "err_none", "err_resched", "err_no_hib", "err_late", "err_not_paused"):
        assert key in i18n.STR["en"]


def test_arabic_is_shaped_and_ordered_like_a_real_bidi_engine():
    assert rtl.has_arabic("سلام") and not rtl.has_arabic("hello 123")
    assert rtl.to_visual("Telegram only") == "Telegram only"
    try:
        from bidi import get_display
    except ImportError:
        pytest.skip("python-bidi not installed")
    for text in ("الوقت المتبقي 01:30:00 Shutdown", "Telegram: متصل", "طفي الشاشة", "زيادة 10 دقايق", "Windows 11 جاهز", "50% خلص", "Sleepify هو اللي بينفذ ده",
                 "الساعة 3:21 م"):
        try:
            oracle = get_display(rtl.shape(text), base_dir="R")
        except TypeError:
            oracle = get_display(rtl.shape(text), base_level=1)
        assert rtl.to_visual(text) == oracle, text


def test_brackets_are_mirrored_so_they_look_right_when_drawn_left_to_right():
    v = rtl.to_visual("مرحبا (تجربة) هنا")
    assert v.index("(") < v.index(")")            # drawn left to right it must still read as ( ... )


def test_arabic_wrapping_keeps_lines_in_reading_order():
    lines = rtl.wrap_visual("اختار مثبّت أو لانشر ألعاب أو أي برنامج", lambda s: len(s) * 8, 120).split("\n")
    assert len(lines) > 1 and all(len(l) * 8 <= 130 for l in lines)


# ---------------------------------------------------------------- system / icons
def test_autostart_command_is_quoted_and_hidden():
    cmd = system.autostart_command()
    assert cmd.endswith("--hidden") and cmd.startswith('"')


def test_second_launch_asks_the_first_to_show_itself(monkeypatch):
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    monkeypatch.setattr(C, "SINGLE_PORT", port)
    srv, status = system.single_instance()
    assert status == "primary"
    inbox, stop = queue.Queue(), threading.Event()
    threading.Thread(target=system.listen_for_show, args=(srv, inbox, stop), daemon=True).start()
    srv2, status2 = system.single_instance()
    assert status2 == "forwarded" and srv2 is None and inbox.get(timeout=3) == ("show",)
    stop.set(); srv.close()


def test_pictures_and_icons(tmp_path, monkeypatch):
    assert icons.ring_image(120, 0.4, "#62f27b").size == (120, 120)
    assert icons.ring_image(120, 1.0, "#62f27b").size == (120, 120) and icons.ring_image(120, 0, "#62f27b").size == (120, 120)
    assert icons.sparkline_image([1, 3, 2, 5], 200, 40, "#6d5cff", limit=3).size == (200, 40)
    assert icons.sparkline_image([], 200, 40, "#6d5cff").size == (200, 40)

    icon_dir = tmp_path / "icons"
    monkeypatch.setattr(C, "ICON_DIR", str(icon_dir)); monkeypatch.setattr(C, "ICO_FILE", str(icon_dir / "app.ico"))
    monkeypatch.setattr(C, "BOT_PNG", str(icon_dir / "bot.png")); monkeypatch.setattr(icons, "_logo_warned", False)
    monkeypatch.setattr(C, "ROOT_DIR", str(tmp_path / "nowhere"))
    monkeypatch.setattr(C, "resource_path", lambda rel: str(tmp_path / "nowhere" / rel))      # no bundled logo
    on, off = icons.build_icons()
    assert on.size == (64, 64) and os.path.exists(C.ICO_FILE)
    fallback_size = os.path.getsize(C.ICO_FILE)
    logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.jpg")
    shutil.copy2(logo, icon_dir / "logo.jpg")
    os.utime(icon_dir / "logo.jpg", (1_600_000_000, 1_600_000_000))                              # an OLD date, like a copied file
    icons.build_icons()
    assert os.path.getsize(C.ICO_FILE) != fallback_size
    stamp = os.path.getmtime(C.ICO_FILE); time.sleep(1.1); icons.build_icons()
    assert os.path.getmtime(C.ICO_FILE) == stamp
