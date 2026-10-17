"""Logic tests for Sleepify (no window is opened). Run with:  py -m pytest -q"""
import json
import os
import queue
import shutil
import threading
import time

import pytest

import Sleepify as S

TOKEN = "1234567890:" + "A" * 35       # fake token with the right shape


# ---------------------------------------------------------------- helpers
class FakeHooks:
    def __init__(self):
        self.cmds, self.beeps, self.toasts, self.tgs, self.logs = [], [], [], [], []
        self.rc = {}
        self.hib = True

    def run(self, cmd):
        self.cmds.append(cmd)
        return self.rc.get(tuple(cmd[:2]), 0)

    def beep(self, f, ms): self.beeps.append((f, ms))
    def toast(self, t, m): self.toasts.append((t, m))
    def tg(self, text): self.tgs.append(text)
    def log(self, text): self.logs.append(text)
    def hibernate_ok(self): return self.hib


class Clock:
    def __init__(self): self.t = 1_000_000.0
    def __call__(self): return self.t


@pytest.fixture(autouse=True)
def clean_files(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(S, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(S, "LEGACY_CONFIG", str(tmp_path / "legacy_config.json"))
    monkeypatch.setattr(S, "DATA_DIR", str(tmp_path))
    S.set_language("en")
    yield
    S.set_language("en")


def make_core(warn=10):
    h, clk = FakeHooks(), Clock()
    return S.TimerCore(h, warn, clk), h, clk


# ---------------------------------------------------------------- durations / formatting
@pytest.mark.parametrize("text,expected", [
    ("1h30m", 5400), ("45m", 2700), ("45m30s", 2730), ("90", 5400), ("30s", 30), ("2h", 7200),
    (" 1h 30m ", 5400), ("٣٠", 1800), ("", None), ("abc", None), ("1x", None), ("m", None), ("10m5h", None),
])
def test_parse_duration(text, expected):
    assert S.parse_duration(text) == expected


def test_formatting():
    assert S.fmt_hms(3725) == "01:02:05"
    assert S.fmt_human(5400) == "1h 30m"
    assert S.fmt_human(45) == "45s"


# ---------------------------------------------------------------- timer core
def test_shutdown_timer_full_life():
    core, h, clk = make_core()
    assert core.start(1200, "S") == (True, "ok")
    assert ["shutdown", "-s", "-t", "1200"] in h.cmds
    clk.t += 600; core.tick()                                   # 10 minutes left -> warning
    assert core.warned and h.beeps == [(1500, 2000)] and len(h.toasts) == 1 and len(h.tgs) == 1
    core.tick(); assert len(h.beeps) == 1                       # not repeated
    clk.t += 597; core.tick()                                   # 3 s left -> final beep
    assert h.beeps[-1] == (1000, 3000)
    clk.t += 3; core.tick()
    assert not core.running and not os.path.exists(S.STATE_FILE)
    assert ["shutdown", "/h"] not in h.cmds


def test_extend_rearms_the_warning():
    core, h, clk = make_core()
    core.start(700, "S"); clk.t += 150; core.tick()
    assert core.warned and len(h.beeps) == 1
    assert core.extend(600) == (True, "ok")
    assert core.warned is False
    assert h.cmds[-2:] == [["shutdown", "-a"], ["shutdown", "-s", "-t", "1150"]]
    clk.t += 560; core.tick()
    assert len(h.beeps) == 2


def test_short_timer_has_no_warning_but_final_beep():
    core, h, clk = make_core()
    core.start(30, "S"); core.tick()
    assert core.warned and not h.beeps
    clk.t += 27; core.tick()
    assert h.beeps == [(1000, 3000)]


def test_hibernate_runs_from_the_app():
    core, h, clk = make_core()
    core.start(60, "H")
    assert ["shutdown", "-s", "-t", "60"] not in h.cmds           # Windows is NOT given a timer
    clk.t += 60; core.tick()
    assert ["shutdown", "/h"] in h.cmds and not core.running


def test_hibernate_failure_is_reported():
    core, h, clk = make_core()
    h.rc[("shutdown", "/h")] = 1
    core.start(5, "H"); clk.t += 5; core.tick()
    assert h.toasts and any("Hibernate" in x for x in h.tgs)


def test_hibernate_turned_off_is_refused_with_a_hint():
    core, h, clk = make_core()
    h.hib = False
    assert core.start(60, "H") == (False, "err_no_hib")
    assert "powercfg" in S.t("err_no_hib")
    h.hib = None                                                   # unknown -> allowed
    assert core.start(60, "H")[0] is True


def test_pc_slept_through_the_deadline_does_not_hibernate_on_wake():
    core, h, clk = make_core()
    core.start(120, "H"); clk.t += 4000; core.tick()
    assert not core.running and ["shutdown", "/h"] not in h.cmds


def test_cancel_and_validation():
    core, h, clk = make_core()
    core.start(500, "S")
    assert core.cancel("app")[0] and not core.running and h.tgs
    assert h.cmds[-1] == ["shutdown", "-a"]
    assert core.cancel("app") == (False, "err_none")
    assert core.start(0, "S") == (False, "err_zero")
    assert core.start(10 ** 7, "S") == (False, "err_max")
    h.rc[("shutdown", "-s")] = 5
    assert core.start(100, "S") == (False, "err_denied") and not core.running


def test_resume_from_disk():
    core, h, clk = make_core()
    core.start(900, "S")
    other = S.TimerCore(FakeHooks(), 10, clk); clk.t += 100
    assert other.resume_from_disk() == "resumed" and other.remaining() == 800 and not other.warned
    core.cancel("x")
    core.start(900, "H")
    third = S.TimerCore(FakeHooks(), 10, clk)
    assert third.resume_from_disk() == "hibernate_lost" and not third.running
    assert not os.path.exists(S.STATE_FILE)


# ---------------------------------------------------------------- telegram commands + languages
def test_commands_in_english():
    core, h, clk = make_core()
    assert "No timer" in S.run_command(core, "status", "")
    assert "Shutdown" in S.run_command(core, "shutdown", "1h30m") and core.running
    assert "01:30:00" in S.run_command(core, "status", "")
    assert "Added" in S.run_command(core, "extend", "") and core.remaining() == 5400 + 600
    r = S.run_command(core, "hibernate", "45m")
    assert "replaced" in r and "tray" in r and core.action == "H"
    assert "cancelled" in S.run_command(core, "cancel", "")
    assert "no timer" in S.run_command(core, "cancel", "")
    assert S.run_command(core, "shutdown", "blah").startswith("❌")
    assert "/shutdown" in S.run_command(core, "help", "")
    assert "don't know" in S.run_command(core, "foo", "")


def test_commands_in_arabic():
    S.set_language("ar")
    core, h, clk = make_core()
    assert "مفيش" in S.run_command(core, "status", "")
    assert "اشتغل" in S.run_command(core, "shutdown", "10m")
    assert "اتمدد" in S.run_command(core, "extend", "5m")
    assert "اتلغى" in S.run_command(core, "cancel", "")
    h.hib = False
    assert "powercfg" in S.run_command(core, "hibernate", "5m")


def test_both_languages_have_the_same_messages():
    assert set(S.STR["en"]) == set(S.STR["ar"])
    for key in S.STR["en"]:
        assert S.STR["ar"][key].strip() and S.STR["en"][key].strip()
    assert [c for c, _ in S.bot_commands()] == ["status", "shutdown", "hibernate", "extend", "cancel", "help"]


# ---------------------------------------------------------------- telegram security
def make_bot():
    q = queue.Queue()
    return S.TelegramBot(TOKEN, 111, q, "Home PC"), q


def upd(chat, frm, text, date=None):
    return {"update_id": 1, "message": {"chat": {"id": chat}, "from": {"id": frm}, "text": text,
                                        "date": date or int(time.time())}}


def test_only_the_owner_can_send_commands():
    bot, q = make_bot()
    bot._handle(upd(222, 222, "/cancel")); assert q.empty()                 # stranger
    bot._handle(upd(111, 222, "/cancel")); assert q.empty()                 # right chat, wrong sender
    bot._handle(upd(111, 111, "/cancel", int(time.time()) - 500)); assert q.empty()   # old message
    bot._handle(upd(111, 111, "/shutdown@My_bot 1h")); assert q.get_nowait() == ("tg", "shutdown", "1h")
    bot._handle(upd(111, 111, "hello")); assert q.get_nowait() == ("tg", "help", "")


def test_token_never_appears_in_logs():
    leaked = f"HTTPSConnectionPool: https://api.telegram.org/bot{TOKEN}/getUpdates failed"
    assert TOKEN not in S.scrub(leaked)


class Resp:
    def __init__(self, data): self.data = data
    def json(self): return self.data


def test_bot_loop_connects_at_once_and_handles_messages(monkeypatch):
    bot, q = make_bot()
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url.split("/")[-1], dict(params or {})))
        if url.endswith("/getMe"):
            return Resp({"ok": True, "result": {"username": "Sleepify_A_bot"}})
        if sum(1 for c in calls if c[0] == "getUpdates") == 1:
            return Resp({"ok": True, "result": [{"update_id": 5, "message": {
                "chat": {"id": 111}, "from": {"id": 111}, "text": "/status", "date": int(time.time())}}]})
        bot.stop.set()
        return Resp({"ok": True, "result": []})

    monkeypatch.setattr(S.requests, "get", fake_get)
    monkeypatch.setattr(S.requests, "post", lambda *a, **k: Resp({"ok": True, "result": True}))
    bot._loop()
    assert bot.online and bot.username == "Sleepify_A_bot"
    assert q.get_nowait() == ("tg", "status", "")
    assert [c for c in calls if c[0] == "getUpdates"][1][1]["offset"] == 6


def test_bad_token_gives_a_clear_error_without_the_token(monkeypatch):
    bot, q = make_bot()
    bot.stop.wait = lambda t: None

    def fake_get(url, params=None, timeout=None):
        if not url.endswith("/getMe"):
            bot.stop.set()
        return Resp({"ok": False, "error_code": 401, "description": "Unauthorized"})

    monkeypatch.setattr(S.requests, "get", fake_get)
    monkeypatch.setattr(S.requests, "post", lambda *a, **k: Resp({"ok": True}))
    bot._loop()
    assert not bot.online and "401" in bot.last_error and TOKEN not in bot.last_error


def test_messages_carry_the_device_name(monkeypatch):
    bot, q = make_bot()
    sent = {}
    monkeypatch.setattr(S, "tg_api", lambda token, method, params=None, post=False, timeout=10: sent.update(params))
    bot.send("hello", wait=True)
    assert sent["text"] == "💻 Home PC\nhello" and sent["chat_id"] == 111


# ---------------------------------------------------------------- pairing code
def test_pair_code_shape():
    for _ in range(50):
        code = S.new_pair_code()
        assert len(code) == 6 and set(code) <= set(S.CODE_ALPHABET)
    assert len({S.new_pair_code() for _ in range(50)}) > 40


def private_msg(text, chat_id=77, sender=77, kind="private", name="Sam"):
    return {"update_id": 9, "message": {"chat": {"id": chat_id, "type": kind}, "from": {"id": sender, "first_name": name},
                                        "text": text}}


def test_pairing_accepts_only_the_right_code_from_a_private_chat():
    code = "K7M2QX"
    assert S.match_pair_update(private_msg("/start K7M2QX"), code) == (77, "Sam")
    assert S.match_pair_update(private_msg("/start@my_bot k7m2qx"), code) == (77, "Sam")
    assert S.match_pair_update(private_msg("K7M2QX"), code) == (77, "Sam")
    assert S.match_pair_update(private_msg("/start WRONG1"), code) is None
    assert S.match_pair_update(private_msg("/start"), code) is None
    assert S.match_pair_update(private_msg("hello K7M2QX there"), code) is None
    assert S.match_pair_update(private_msg("/start K7M2QX", kind="group"), code) is None
    assert S.match_pair_update(private_msg("/start K7M2QX", sender=5), code) is None
    assert S.match_pair_update({"update_id": 1}, code) is None


def test_pairing_watcher_finds_the_owner(monkeypatch):
    calls = []

    def fake_api(token, method, params=None, post=False, timeout=10):
        calls.append((method, dict(params or {})))
        if method == "getUpdates" and not any(c[0] == "getUpdates" and c[1].get("timeout") == 0 for c in calls[:-1]):
            if len([c for c in calls if c[0] == "getUpdates"]) == 1:
                return [private_msg("/start NOPE12", chat_id=1, sender=1),
                        {**private_msg("/start K7M2QX"), "update_id": 12}]
        return []

    monkeypatch.setattr(S, "tg_api", fake_api)
    w = S.PairingWatcher(TOKEN, "K7M2QX")
    w.start(); w.join(timeout=5)
    assert w.result == (77, "Sam")
    assert ("getUpdates", {"offset": 13, "timeout": 0}) in calls      # message was confirmed


def test_token_shape_check():
    assert S.valid_token_format(TOKEN) and S.valid_token_format("  " + TOKEN + " ")
    assert not S.valid_token_format("PASTE_TOKEN_HERE") and not S.valid_token_format("")


# ---------------------------------------------------------------- config
def test_config_roundtrip_and_defaults():
    cfg = S.load_config()
    assert cfg["language"] == "en" and not S.has_telegram(cfg) and cfg["warning_minutes"] == 10
    cfg.update(bot_token=TOKEN, chat_id=123, device_name="Home PC", language="ar", warning_minutes=15)
    assert S.save_config(cfg)
    again = S.load_config()
    assert S.has_telegram(again) and again["language"] == "ar" and again["warning_minutes"] == 15
    assert S.update_config(warning_minutes=20) and S.load_config()["warning_minutes"] == 20
    assert S.load_config()["bot_token"] == TOKEN                    # the rest is untouched


def test_broken_or_placeholder_config_is_ignored():
    with open(S.CONFIG_FILE, "w") as f:
        f.write("{not json")
    assert not S.has_telegram(S.load_config())
    with open(S.CONFIG_FILE, "w") as f:
        json.dump({"bot_token": "PASTE_TOKEN_HERE", "chat_id": 1}, f)
    assert not S.has_telegram(S.load_config())


def test_old_config_next_to_the_script_is_imported_once():
    with open(S.LEGACY_CONFIG, "w") as f:
        json.dump({"bot_token": TOKEN, "chat_id": 424242424, "warning_minutes": 12}, f)
    assert S.migrate_legacy_config() is True
    cfg = S.load_config()
    assert S.has_telegram(cfg) and cfg["chat_id"] == 424242424 and cfg["warning_minutes"] == 12
    assert cfg["language"] == "ar" and cfg["device_name"]
    assert S.migrate_legacy_config() is False                       # not imported twice


# ---------------------------------------------------------------- start with Windows / paths
def test_autostart_command_is_quoted_and_hidden():
    cmd = S.autostart_command()
    assert cmd.endswith("--hidden") and cmd.startswith('"')


def test_resource_and_data_paths():
    assert S.resource_path("assets").endswith("assets")
    assert os.path.isdir(S.DATA_DIR)


# ---------------------------------------------------------------- single instance
def test_second_launch_asks_the_first_to_show_itself(monkeypatch):
    import socket
    with socket.socket() as probe:                     # any free port, so tests never collide
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    monkeypatch.setattr(S, "SINGLE_PORT", free_port)
    srv, status = S.single_instance()
    assert status == "primary"
    inbox, stop = queue.Queue(), threading.Event()
    threading.Thread(target=S.listen_for_show, args=(srv, inbox, stop), daemon=True).start()
    srv2, status2 = S.single_instance()
    assert status2 == "forwarded" and srv2 is None
    assert inbox.get(timeout=3) == ("show",)
    stop.set(); srv.close()


# ---------------------------------------------------------------- icons
def test_icons_come_from_the_logo_and_regenerate_when_it_changes(tmp_path, monkeypatch):
    icon_dir = tmp_path / "icons"
    monkeypatch.setattr(S, "ICON_DIR", str(icon_dir))
    monkeypatch.setattr(S, "ICO_FILE", str(icon_dir / "app.ico"))
    monkeypatch.setattr(S, "BOT_PNG", str(icon_dir / "bot.png"))
    monkeypatch.setattr(S, "_logo_warned", False)
    monkeypatch.setattr(S, "APP_DIR", str(tmp_path / "nowhere"))          # no bundled logo -> fallback icon
    on, off = S.build_icons()
    assert on.size == (64, 64) and off.size == (64, 64) and os.path.exists(S.ICO_FILE)
    fallback_size = os.path.getsize(S.ICO_FILE)

    logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.jpg")
    icon_dir.mkdir(exist_ok=True)
    shutil.copy2(logo, icon_dir / "logo.jpg")
    os.utime(icon_dir / "logo.jpg", (1_600_000_000, 1_600_000_000))       # an OLD date, like a copied file
    S.build_icons()
    assert os.path.getsize(S.ICO_FILE) != fallback_size
    stamp_time = os.path.getmtime(S.ICO_FILE)
    time.sleep(1.1)
    S.build_icons()
    assert os.path.getmtime(S.ICO_FILE) == stamp_time                      # unchanged logo -> not rewritten
