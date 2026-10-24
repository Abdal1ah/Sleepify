# -*- coding: utf-8 -*-
"""The timer itself (no window in here), the clock-time schedules, and the history statistics."""
import json
import math
import os
import time
import uuid
from datetime import date, datetime, timedelta

from . import common as C
from .i18n import action_label, t

APP_RUN = tuple(a for a in C.ACTIONS if a not in C.WINDOWS_TIMED)
VERB = {"shutdown": "shut down", "restart": "restart", "hibernate": "hibernate",
        "sleep": "go to sleep", "lock": "lock", "display": "turn the screen off"}


class TimerCore:
    def __init__(self, hooks, warn_minutes=10, clock=time.time, keep_awake=True):
        self.h = hooks
        self.clock = clock
        self.warn_sec = warn_minutes * 60
        self.running = False
        self.paused = False
        self.paused_left = 0
        self.action = "shutdown"
        self.source = ""
        self.end_ts = 0.0
        self.total = 0                     # length of the timer, for the progress ring
        self.warned = False
        self.final_done = False
        self.watching = False                # set by the app while an app is being watched
        self.keep_awake_pref = keep_awake
        self._awake = False
        self._awake_t = 0.0

    # ---- state file ----
    def _save(self):
        try:
            if self.running:
                data = {"action": self.action, "end": self.end_ts, "source": self.source}
            elif self.paused:
                data = {"action": self.action, "paused_left": self.paused_left}
            else:
                return
            with open(C.STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            C.log_error(f"could not save state: {e}")

    def _clear(self):
        try:
            os.remove(C.STATE_FILE)
        except OSError:
            pass

    # ---- queries ----
    @property
    def active(self):
        return self.running or self.paused

    def remaining(self):
        if self.running:
            return max(0, math.ceil(self.end_ts - self.clock()))
        return self.paused_left if self.paused else 0

    def set_warn_minutes(self, minutes):
        self.warn_sec = minutes * 60
        if self.running and self.remaining() > self.warn_sec:
            self.warned = False

    def set_keep_awake_pref(self, on):
        self.keep_awake_pref = bool(on)
        self._awake_update(force=True)

    def set_watching(self, on):
        self.watching = bool(on)
        self._awake_update(force=True)

    def _awake_update(self, force=False):
        want = self.keep_awake_pref and (self.running or self.watching)
        now = self.clock()
        if force or want != self._awake or (want and now - self._awake_t > 60):
            self.h.keep_awake(want)
            self._awake, self._awake_t = want, now

    # ---- actions (the second value is a message key from the language table) ----
    def _schedule_in_windows(self, action, seconds):
        flag = "-s" if action == "shutdown" else "-r"
        return self.h.run(["shutdown", flag, "-t", str(seconds)]) == 0

    def start(self, seconds, action, source="app", warn_now=False):
        seconds = int(seconds)
        if action not in C.ACTIONS or seconds <= 0:
            return False, "err_zero"
        if seconds > C.MAX_SECONDS:
            return False, "err_max"
        if action == "hibernate" and self.h.hibernate_ok() is False:
            return False, "err_no_hib"
        self.h.run(["shutdown", "-a"])                # clear anything pending (ignore the result)
        if action in C.WINDOWS_TIMED and not self._schedule_in_windows(action, seconds):
            self.running = self.paused = False
            self._clear()
            self._awake_update()
            return False, "err_denied"
        self.running, self.paused = True, False
        self.action, self.source = action, source
        self.end_ts = self.clock() + seconds
        self.total = seconds
        self.warned = seconds <= self.warn_sec and not warn_now
        self.final_done = False
        self._save()
        self._awake_update()
        self.h.log(f"Started {C.ACTION_NAME[action]} timer {C.fmt_hms(seconds)} (by {source})")
        self.h.history("start", action=action, seconds=seconds, source=source)
        return True, "ok"

    def cancel(self, source="app"):
        if not self.active:
            return False, "err_none"
        left = self.remaining()
        if self.running and self.action in C.WINDOWS_TIMED:
            self.h.run(["shutdown", "-a"])
        self.running = self.paused = False
        self._clear()
        self._awake_update()
        self.h.log(f"Cancelled {C.ACTION_NAME[self.action]} timer, {C.fmt_hms(left)} was left (by {source})")
        self.h.history("cancel", action=self.action, seconds=left, source=source)
        if source == "app":
            self.h.tg(t("cancelled_pc"))
        return True, "ok"

    def extend(self, seconds, source="app"):
        if not self.active:
            return False, "err_none"
        seconds = int(seconds)
        if seconds <= 0:
            return False, "err_zero"
        new_rem = self.remaining() + seconds
        if new_rem > C.MAX_SECONDS:
            return False, "err_max"
        if self.paused:
            self.paused_left = new_rem
            self.total += seconds
            self._save()
        else:
            if self.action in C.WINDOWS_TIMED:
                self.h.run(["shutdown", "-a"])
                if not self._schedule_in_windows(self.action, new_rem):
                    self.running = False
                    self._clear()
                    self._awake_update()
                    return False, "err_resched"
            self.end_ts += seconds
            self.total += seconds
            if new_rem > self.warn_sec:
                self.warned = False
            if new_rem > 3:
                self.final_done = False
            self._save()
        self.h.log(f"Extended by {C.fmt_human(seconds)}, {C.fmt_hms(new_rem)} left (by {source})")
        self.h.history("extend", action=self.action, seconds=seconds, source=source)
        return True, "ok"

    def pause(self, source="app"):
        if not self.running:
            return False, "err_none"
        left = self.remaining()
        if left <= 5:
            return False, "err_late"
        if self.action in C.WINDOWS_TIMED:
            self.h.run(["shutdown", "-a"])
        self.running, self.paused, self.paused_left = False, True, left
        self._save()
        self._awake_update()
        self.h.log(f"Paused with {C.fmt_hms(left)} left (by {source})")
        self.h.history("pause", action=self.action, seconds=left, source=source)
        return True, "ok"

    def resume(self, source="app"):
        if not self.paused:
            return False, "err_not_paused"
        left, action, total = self.paused_left, self.action, self.total
        ok, msg = self.start(left, action, source=source)
        if ok:
            self.total = max(total, left)
            self.warned = left <= self.warn_sec
            self.h.history("resume", action=action, seconds=left, source=source)
        return ok, msg

    def resume_from_disk(self):
        """Call once at startup. Returns 'resumed', 'paused', 'app_timer_lost' or None."""
        try:
            with open(C.STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            action = data.get("action")
            if action not in C.ACTIONS:
                raise ValueError("bad action")
        except (OSError, ValueError, TypeError):
            return None
        now = self.clock()
        if "paused_left" in data:
            self.paused, self.running = True, False
            self.paused_left, self.action = int(data["paused_left"]), action
            self.total = self.paused_left
            return "paused"
        end = float(data.get("end", 0))
        if action in C.WINDOWS_TIMED and end - now > 2:
            rem = math.ceil(end - now)
            self.running, self.action, self.end_ts = True, action, end
            self.source = data.get("source", "")
            self.total = rem
            self.warned = rem <= self.warn_sec
            self.final_done = rem <= 3
            self._awake_update()
            self.h.log(f"Resumed {C.ACTION_NAME[action]} timer, {C.fmt_hms(rem)} left")
            return "resumed"
        self._clear()
        if action in APP_RUN and end > now:
            self.h.log(f"A {C.ACTION_NAME[action]} timer from the previous session was lost (app was closed)")
            return "app_timer_lost"
        return None

    # ---- called every ~250 ms ----
    def tick(self):
        self._awake_update()
        if not self.running:
            return
        now = self.clock()
        if self.action in APP_RUN and now - self.end_ts > 30:
            # the PC was asleep through the deadline - do NOT act right after waking up
            self.running = False
            self._clear()
            self._awake_update()
            self.h.log(f"{C.ACTION_NAME[self.action]} timer expired while the PC was asleep - skipped")
            self.h.history("missed", action=self.action, source=self.source)
            self.h.toast(C.APP_NAME, "The timer expired while the PC was asleep, so it was skipped.")
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

    def _buttons(self):
        return [[(t("btn_extend", mins=C.EXTEND_MINUTES), "ext"), (t("btn_cancel"), "cancel")]]

    def _warn(self, rem):
        mins = max(1, round(rem / 60))
        self.h.beep(1500, 2000)
        self.h.toast(f"Warning: {mins} min left", f"Your PC will {VERB[self.action]} in {mins} minute(s).")
        self.h.tg(t("warn_msg", mins=mins, action=action_label(self.action)), buttons=self._buttons())
        self.h.log(f"Warning shown, {C.fmt_hms(rem)} left")

    def _final(self):
        self.h.beep(1000, 3000)
        self.h.tg(t("final", action=action_label(self.action)))

    def _execute(self):
        action = self.action
        self.running = False
        self._clear()
        self._awake_update()
        self.h.log(f"Executing {C.ACTION_NAME[action]}")
        self.h.history("execute", action=action, source=self.source)
        if action in APP_RUN and not self.h.perform(action):
            self.h.log(f"{C.ACTION_NAME[action]} failed")
            self.h.toast(C.APP_NAME, f"{C.ACTION_NAME[action]} failed.")
            self.h.tg(t("hib_failed") if action == "hibernate" else t("act_failed", action=action_label(action)))


# ---------------------------------------------------------------- schedules (clock times)
class Scheduler:
    """Turns 'at 03:30' schedules into a normal timer shortly before the time, so the usual warning appears."""

    def __init__(self, core, hooks, get_list, save, clock=time.time):
        self.core, self.h = core, hooks
        self.get_list, self.save, self.clock = get_list, save, clock
        self.armed = set()
        self._next = 0.0

    @staticmethod
    def next_fire(s, now_dt):
        """Next time this schedule fires (for one-time schedules this may already be in the past)."""
        h, m = (int(x) for x in s["time"].split(":"))
        if not s["days"]:
            try:
                return datetime.combine(date.fromisoformat(s["date"]), datetime.min.time()).replace(hour=h, minute=m)
            except (KeyError, ValueError):
                return None
        for offset in range(8):
            day = now_dt.date() + timedelta(days=offset)
            cand = datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m)
            if day.weekday() in s["days"] and cand > now_dt:
                return cand
        return None

    def add(self, time_str, action, days=None):
        now_dt = datetime.fromtimestamp(self.clock())
        h, m = (int(x) for x in time_str.split(":"))
        item = {"id": uuid.uuid4().hex[:6], "time": f"{h:02d}:{m:02d}", "days": sorted(days or []),
                "action": action, "enabled": True}
        if not item["days"]:
            today = datetime.combine(now_dt.date(), datetime.min.time()).replace(hour=h, minute=m)
            item["date"] = (now_dt.date() if today > now_dt else now_dt.date() + timedelta(days=1)).isoformat()
        self.get_list().append(item)
        self.save()
        self.h.history("schedule_add", action=action, source=item["time"])
        return item

    def remove(self, sid):
        lst = self.get_list()
        lst[:] = [s for s in lst if s["id"] != sid]
        self.save()

    def tick(self):
        now = self.clock()
        if now < self._next:
            return
        self._next = now + 1.0
        now_dt = datetime.fromtimestamp(now)
        lst, changed = self.get_list(), False
        lead = max(self.core.warn_sec, 60)
        for s in list(lst):
            if not s.get("enabled", True):
                continue
            fire = self.next_fire(s, now_dt)
            if fire is None:
                continue
            secs = (fire - now_dt).total_seconds()
            key = f"{s['id']}@{fire.isoformat()}"
            if not s["days"] and secs <= 0:               # a one-time schedule is over
                if key not in self.armed:
                    self.h.log(f"Schedule {s['time']} was missed (Sleepify was not running)")
                    self.h.history("missed", action=s["action"], source="schedule")
                lst.remove(s)
                changed = True
                continue
            if 0 < secs <= lead and key not in self.armed:
                if self.core.active or self.core.watching:
                    continue                                # busy right now, try again next second
                self.armed.add(key)
                self.core.start(math.ceil(secs), s["action"], "schedule", warn_now=True)
        if changed:
            self.save()


# ---------------------------------------------------------------- history statistics
def compute_stats(events, now_dt, days=7):
    since = now_dt - timedelta(days=days)
    stats = {"started": 0, "executed": 0, "cancelled": 0, "watch_done": 0, "typical": None}
    minutes = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["ts"])
        except (KeyError, ValueError):
            continue
        if ts < since:
            continue
        kind = e.get("kind")
        if kind == "start":
            stats["started"] += 1
        elif kind == "cancel":
            stats["cancelled"] += 1
        elif kind == "watch_done":
            stats["watch_done"] += 1
        elif kind == "execute":
            stats["executed"] += 1
            m = ts.hour * 60 + ts.minute
            minutes.append(m + 1440 if m < 12 * 60 else m)       # after-midnight counts as "late evening"
    if minutes:
        avg = round(sum(minutes) / len(minutes)) % 1440
        stats["typical"] = (avg // 60, avg % 60)
    return stats
