# -*- coding: utf-8 -*-
"""The main window: a sidebar and five pages (Home, Watch an app, Schedule, History, Settings)."""
import os
import platform
import queue
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime

import customtkinter as ctk
import pystray
from tkinter import messagebox

from . import VERSION
from . import common as C
from . import config as cfgmod
from . import icons, monitor, system, updates
from . import i18n
from .core import APP_RUN, Scheduler, compute_stats
from .i18n import action_label, fmt_clock, is_rtl, t
from .telegram import Context, TelegramBot, run_callback, run_command
from .widgets import (ACCENT, ACCENT_HOVER, AMBER, BG, BORDER, BTN, BTN_HOVER, CARD, CARD2, GREEN, GREEN_DARK, INK,
                      MUTED, RED_DARK, RED_HOVER, SIDEBAR, TEXT, TButton, TLabel, card, checkbox, entry, font, hr, switch, vis)
from .wizard import SetupWizard

PAGES = ("home", "watch", "schedule", "history", "settings")
QUICK = (("15m", 900), ("30m", 1800), ("1h", 3600), ("2h", 7200))


def _err(key):
    return t(key)


class Page(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

    def on_show(self):
        pass

    def refresh(self):
        pass

    def title(self, key, sub=None):
        TLabel(self, t(key), 24, "bold").pack(fill="x", pady=(2, 0))
        if sub:
            TLabel(self, t(sub), 12, color=MUTED, wrap=620).pack(fill="x", pady=(0, 10))


def action_menu(parent, command=None, width=140):
    """Drop-down with the six actions. Returns (menu, getter, setter)."""
    labels = [vis(action_label(a)) for a in C.ACTIONS]
    menu = ctk.CTkOptionMenu(parent, values=labels, width=width, height=34, font=font(13), dropdown_font=font(13),
                             fg_color=CARD2, button_color=BTN, button_hover_color=BTN_HOVER,
                             dropdown_fg_color=CARD2, dropdown_hover_color=BTN, text_color=TEXT, command=command)
    menu.set(labels[0])

    def get():
        return C.ACTIONS[labels.index(menu.get())]

    def set_(action):
        menu.set(labels[C.ACTIONS.index(action)])
    return menu, get, set_


# =============================================================== Home
class HomePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title("home_title")
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure((0, 1), weight=1, uniform="a")
        cols.grid_rowconfigure(0, weight=1)
        left, right = card(cols), card(cols)
        left.grid(row=0, column=1 if is_rtl() else 0, padx=(0, 8) if not is_rtl() else (8, 0), sticky="nsew")
        right.grid(row=0, column=0 if is_rtl() else 1, padx=(8, 0) if not is_rtl() else (0, 8), sticky="nsew")
        self._ring_key = None
        self.selected = app.core.action

        # ---- ring ----
        box = ctk.CTkFrame(left, fg_color="transparent", width=250, height=250)
        box.pack(pady=(18, 6))
        box.pack_propagate(False)
        self.ring = ctk.CTkLabel(box, text="")
        self.ring.place(relx=0.5, rely=0.5, anchor="center")
        self.time_lbl = TLabel(box, "--:--:--", 31, "bold", mono=True, anchor="center")
        self.time_lbl.place(relx=0.5, rely=0.44, anchor="center")
        self.state_lbl = TLabel(box, "", 11, "bold", color=MUTED, anchor="center")
        self.state_lbl.place(relx=0.5, rely=0.62, anchor="center")
        self.info_lbl = TLabel(left, "", 13, color=MUTED, anchor="center")
        self.info_lbl.pack(fill="x", padx=10)
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(10, 8))
        row.grid_columnconfigure((0, 1, 2), weight=1, uniform="b")
        self.b_ext = TButton(row, t("btn_extend", mins=C.EXTEND_MINUTES), 12, command=app.ui_extend)
        self.b_pause = TButton(row, t("btn_pause"), 12, command=app.ui_pause)
        self.b_cancel = TButton(row, t("btn_cancel"), 12, danger=True, command=app.ui_cancel)
        for i, b in enumerate((self.b_ext, self.b_pause, self.b_cancel)):
            b.grid(row=0, column=i, padx=3, sticky="ew")
        self.awake_var = ctk.BooleanVar(value=app.cfg["keep_awake"])
        switch(left, t("keep_awake"), self.awake_var, self._awake_changed).pack(anchor="e" if is_rtl() else "w", padx=16, pady=(2, 14))

        # ---- new timer ----
        TLabel(right, t("new_timer"), 15, "bold").pack(fill="x", padx=16, pady=(14, 6))
        grid = ctk.CTkFrame(right, fg_color="transparent")
        grid.pack(fill="x", padx=12)
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="c")
        self.chips = {}
        for i, a in enumerate(C.ACTIONS):
            b = TButton(grid, action_label(a), 12, height=32, command=lambda a=a: self.select(a))
            b.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            self.chips[a] = b
        self.hint = TLabel(right, "", 11, color=MUTED, wrap=280)
        self.hint.pack(fill="x", padx=16, pady=(4, 6))
        q = ctk.CTkFrame(right, fg_color="transparent")
        q.pack(fill="x", padx=12)
        q.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="d")
        for i, (label, secs) in enumerate(QUICK):
            TButton(q, label, 13, height=34, command=lambda s=secs: self._quick(s)).grid(row=0, column=i, padx=3, sticky="ew")
        hr(right).pack(fill="x", padx=16, pady=12)
        TLabel(right, t("custom_time"), 12, "bold", color=MUTED).pack(fill="x", padx=16, pady=(0, 4))
        c = ctk.CTkFrame(right, fg_color="transparent")
        c.pack(fill="x", padx=12)
        c.grid_columnconfigure((0, 1, 2), weight=1, uniform="e")
        self.e_h, self.e_m, self.e_s = (entry(c, 60, t(k)) for k in ("hours", "minutes", "seconds"))
        for i, e in enumerate((self.e_h, self.e_m, self.e_s)):
            e.grid(row=0, column=i, padx=3, sticky="ew")
        TButton(right, t("start_timer"), 15, primary=True, height=42, command=self._start_custom).pack(
            fill="x", padx=15, pady=(12, 16))
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", pady=(10, 0))
        strip.grid_columnconfigure((0, 1), weight=1, uniform="t")
        self.tile_sched = self._tile(strip, 1 if is_rtl() else 0, "next_sched")
        self.tile_watch = self._tile(strip, 0 if is_rtl() else 1, "tile_watch")
        self._tile_t = 0.0
        self.select(self.selected)

    def _tile(self, parent, col, title_key):
        c = card(parent)
        c.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0))
        TLabel(c, t(title_key), 11, "bold", color=MUTED).pack(fill="x", padx=14, pady=(10, 0))
        v = TLabel(c, "", 13, wrap=250)
        v.pack(fill="x", padx=14, pady=(0, 10))
        return v

    # ---- actions on this page ----
    def select(self, action):
        self.selected = action
        self.app.last_action = action
        for a, b in self.chips.items():
            on = a == action
            b.configure(fg_color=ACCENT if on else BTN, hover_color=ACCENT_HOVER if on else BTN_HOVER)
        if action in C.WINDOWS_TIMED:
            self.hint.set(t("hint_windows"), MUTED)
        else:
            self.hint.set(t("hint_app"), AMBER)

    def _quick(self, seconds):
        self.app.ui_start(seconds, self.selected)

    def _start_custom(self):
        try:
            vals = []
            for e in (self.e_h, self.e_m, self.e_s):
                txt = e.get().strip()
                v = int(txt) if txt else 0
                if v < 0:
                    raise ValueError
                vals.append(v)
        except ValueError:
            messagebox.showerror(C.APP_NAME, t("err_numbers"), parent=self.app)
            return
        total = vals[0] * 3600 + vals[1] * 60 + vals[2]
        if total <= 0:
            messagebox.showerror(C.APP_NAME, t("err_zero"), parent=self.app)
            return
        self.app.ui_start(total, self.selected)

    def _awake_changed(self):
        self.app.set_keep_awake(self.awake_var.get())

    # ---- live update ----
    def refresh(self):
        core = self.app.core
        rem = core.remaining()
        if core.running:
            warn = rem <= core.warn_sec
            color = AMBER if warn else GREEN
            frac = rem / max(1, core.total)
            self.time_lbl.set(C.fmt_hms(rem), color)
            self.state_lbl.set(t("state_running"), color)
            self.info_lbl.set(t("action_at", action=action_label(core.action), at=fmt_clock(core.end_ts)), TEXT)
        elif core.paused:
            color, frac = ACCENT_HOVER, rem / max(1, core.total)
            self.time_lbl.set(C.fmt_hms(rem), color)
            self.state_lbl.set(t("state_paused"), color)
            self.info_lbl.set(action_label(core.action), TEXT)
        else:
            color, frac = MUTED, 0.0
            self.time_lbl.set("--:--:--", MUTED)
            if self.app.watch is not None:
                self.state_lbl.set(t("state_watching"), GREEN)
                self.info_lbl.set(t("watching_app", app=self.app.watch.app), TEXT)
            else:
                self.state_lbl.set(t("state_ready"), MUTED)
                self.info_lbl.set(t("pick_time"), MUTED)
        key = (round(frac * 240), color, core.active)
        if key != self._ring_key:
            self._ring_key = key
            img = icons.ring_image(250, frac, color if core.active else BORDER, track="#222a5a")
            self._ring_img = ctk.CTkImage(light_image=img, dark_image=img, size=(250, 250))
            self.ring.configure(image=self._ring_img)
        self.b_ext.configure(state="normal" if core.active else "disabled")
        self.b_cancel.configure(state="normal" if core.active else "disabled")
        self.b_pause.configure(state="normal" if core.active else "disabled")
        self.b_pause.set(t("btn_resume") if core.paused else t("btn_pause"))
        self.awake_var.set(self.app.cfg["keep_awake"])
        now = time.time()
        if now - self._tile_t >= 1.0:
            self._tile_t = now
            now_dt = datetime.now()
            best = None
            for sc in self.app.cfg["schedules"]:
                if sc.get("enabled", True):
                    fire = Scheduler.next_fire(sc, now_dt)
                    if fire and fire > now_dt and (best is None or fire < best[0]):
                        best = (fire, sc)
            if best:
                self.tile_sched.set(t("sched_in", action=action_label(best[1]["action"]), time=best[1]["time"],
                                      left=C.fmt_human((best[0] - now_dt).total_seconds())), TEXT)
            else:
                self.tile_sched.set(t("no_sched"), MUTED)
            job = self.app.watch
            self.tile_watch.set(t("watching_app", app=job.app) if job else t("tile_none"), TEXT if job else MUTED)


# =============================================================== Watch an app
class WatchPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", scrollbar_button_color=BTN,
                         scrollbar_button_hover_color=BTN_HOVER)
        self.app = app
        self.selected = ""
        self.preview = None
        self.hist = {k: [] for k in ("cpu", "io")}
        self._last_sample = 0.0
        self.rows = {}
        TLabel(self, t("watch_title"), 24, "bold").pack(fill="x", pady=(2, 0))
        TLabel(self, t("watch_sub"), 12, color=MUTED, wrap=600).pack(fill="x", pady=(0, 10))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        top.grid_columnconfigure((0, 1), weight=1, uniform="w")
        left, right = card(top), card(top)
        left.grid(row=0, column=1 if is_rtl() else 0, sticky="nsew", padx=(0, 6) if not is_rtl() else (6, 0))
        right.grid(row=0, column=0 if is_rtl() else 1, sticky="nsew", padx=(6, 0) if not is_rtl() else (0, 6))

        # ---- app list ----
        head = ctk.CTkFrame(left, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        TLabel(head, t("choose_app"), 14, "bold").pack(side="right" if is_rtl() else "left")
        TButton(head, t("refresh"), 11, height=26, width=70, command=self.refresh_apps).pack(side="left" if is_rtl() else "right")
        self.bg_var = ctk.BooleanVar(value=False)
        checkbox(left, t("show_background"), self.bg_var, self.refresh_apps).pack(anchor="e" if is_rtl() else "w", padx=14)
        self.listbox = ctk.CTkScrollableFrame(left, height=210, fg_color=CARD2, corner_radius=10,
                                              scrollbar_button_color=BTN)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        # ---- live numbers ----
        TLabel(right, t("live_title"), 14, "bold").pack(fill="x", padx=14, pady=(12, 2))
        self.sel_lbl = TLabel(right, t("no_app_selected"), 13, color=MUTED, wrap=270)
        self.sel_lbl.pack(fill="x", padx=14)
        nums = ctk.CTkFrame(right, fg_color="transparent")
        nums.pack(fill="x", padx=10, pady=(8, 2))
        nums.grid_columnconfigure((0, 1, 2), weight=1, uniform="n")
        self.n_cpu, self.n_io, self.n_net = (TLabel(nums, "-", 16, "bold", anchor="center") for _ in range(3))
        for i, (lab, w) in enumerate((("cpu", self.n_cpu), ("disk", self.n_io), ("net", self.n_net))):
            w.grid(row=0, column=i)
            TLabel(nums, t(lab), 10, color=MUTED, anchor="center").grid(row=1, column=i)
        self.spark_cpu = ctk.CTkLabel(right, text="")
        self.spark_cpu.pack(padx=12, pady=(8, 2))
        self.spark_io = ctk.CTkLabel(right, text="")
        self.spark_io.pack(padx=12, pady=(0, 2))
        self.status_lbl = TLabel(right, "", 12, color=MUTED, wrap=270)
        self.status_lbl.pack(fill="x", padx=14, pady=(2, 12))

        # ---- rules ----
        rules = card(self)
        rules.pack(fill="x", pady=(12, 8))
        w = app.cfg["watch"]
        TLabel(rules, t("rules_title"), 14, "bold").pack(fill="x", padx=14, pady=(12, 4))
        self.v = {k: ctk.BooleanVar(value=w[k]) for k in ("rule_close", "rule_idle", "use_cpu", "use_io", "use_net")}
        checkbox(rules, t("rule_close"), self.v["rule_close"]).pack(anchor="e" if is_rtl() else "w", padx=14, pady=3)
        self.f_idle = self._rule_row(rules, "rule_idle", "idle_minutes", w["idle_minutes"], "min_unit")
        TLabel(rules, t("idle_means"), 12, color=MUTED).pack(fill="x", padx=14, pady=(8, 2))
        self.f_cpu = self._rule_row(rules, "use_cpu", "cpu_limit", w["cpu_limit"], "pct_unit", label_key="rule_cpu")
        self.f_io = self._rule_row(rules, "use_io", "io_limit_mb", w["io_limit_mb"], "mbs_unit", label_key="rule_disk")
        self.f_net = self._rule_row(rules, "use_net", "net_limit_kb", w["net_limit_kb"], "kbs_unit", label_key="rule_net")
        self.net_note = TLabel(rules, "", 11, color=AMBER, wrap=560)
        self.net_note.pack(fill="x", padx=14)
        hr(rules).pack(fill="x", padx=14, pady=10)
        TLabel(rules, t("then_do"), 12, color=MUTED).pack(fill="x", padx=14, pady=(0, 4))
        line = ctk.CTkFrame(rules, fg_color="transparent")
        line.pack(fill="x", padx=12, pady=2)
        self.act_menu, self.get_action, self.set_action = action_menu(line, width=150)
        self.set_action(w["action"])
        self.act_menu.pack(side="right" if is_rtl() else "left", padx=2)
        self.f_grace = self._inline(line, "grace_label", w["grace_seconds"], "sec_unit")
        line2 = ctk.CTkFrame(rules, fg_color="transparent")
        line2.pack(fill="x", padx=12, pady=2)
        self.f_max = self._inline(line2, "max_label", w["max_hours"], "hour_unit")
        self.shot_var = ctk.BooleanVar(value=app.cfg["screenshot_on_finish"])
        self.shot_cb = checkbox(rules, t("shot_on_finish"), self.shot_var)
        self.shot_cb.pack(anchor="e" if is_rtl() else "w", padx=14, pady=(6, 2))
        self.btn = TButton(rules, t("start_watch"), 15, primary=True, height=42, command=self._toggle)
        self.btn.pack(fill="x", padx=14, pady=(10, 14))
        self.refresh_apps()

    def _rule_row(self, parent, var_key, field, value, unit_key, label_key=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=2)
        text = t(label_key or var_key)
        cb = checkbox(row, text, self.v[var_key])
        e = entry(row, 64)
        e.insert(0, f"{value:g}" if isinstance(value, float) else str(value))
        u = TLabel(row, t(unit_key), 12, color=MUTED, anchor="w")
        if is_rtl():
            u.pack(side="right", padx=(0, 4)); e.pack(side="right", padx=4); cb.pack(side="right")
        else:
            cb.pack(side="left"); e.pack(side="left", padx=8); u.pack(side="left")
        return e

    def _inline(self, parent, label_key, value, unit_key):
        side = "right" if is_rtl() else "left"
        lab = TLabel(parent, t(label_key), 12, color=MUTED)
        e = entry(parent, 58)
        e.insert(0, str(value))
        u = TLabel(parent, t(unit_key), 12, color=MUTED)
        for w_ in (lab, e, u):
            w_.pack(side=side, padx=4)
        return e

    # ---- the list of apps ----
    def refresh_apps(self):
        for w in self.listbox.winfo_children():
            w.destroy()
        self.rows = {}
        try:
            apps = monitor.list_apps(include_background=self.bg_var.get())
        except Exception as e:
            C.log_error(f"could not list apps: {e}")
            apps = []
        if not apps:
            TLabel(self.listbox, t("no_apps"), 12, color=MUTED, wrap=260).pack(fill="x", pady=8)
        for a in apps[:250]:
            title = f"  ·  {a['title'][:26]}" if a["title"] else ""
            b = TButton(self.listbox, f"{a['name']}{title}", 12, weight="normal", height=28, fg_color="transparent",
                        hover_color=BTN, anchor="e" if is_rtl() else "w", command=lambda n=a["name"]: self.select(n))
            b.pack(fill="x", pady=1)
            self.rows[a["name"]] = b
        self._mark()

    def _mark(self):
        for name, b in self.rows.items():
            b.configure(fg_color=ACCENT if name == self.selected else "transparent")

    def select(self, name):
        self.selected = name
        self.preview = monitor.AppSampler(name, estats=self.app.estats_if_enabled())
        self.hist = {k: [] for k in ("cpu", "io")}
        self._last_sample = 0.0
        self.sel_lbl.set(name, TEXT)
        self._mark()

    # ---- live preview ----
    def on_show(self):
        self.refresh_apps()

    def refresh(self):
        job = self.app.watch
        enabled = self.app.net_available()
        self.net_note.set("" if enabled else t("net_needs_admin"))
        self.btn.set(t("stop_watch") if job else t("start_watch"))
        self.btn.configure(fg_color=RED_DARK if job else GREEN, hover_color=RED_HOVER if job else "#86ff99",
                           text_color=TEXT if job else INK)
        self.shot_cb.configure(state="normal" if self.app.cfg["screenshot_enabled"] else "disabled")
        now = time.time()
        if job is not None:
            s, hist, limit_cpu, limit_io = job.last, job.hist, job.cfg["cpu_limit"], job.cfg["io_limit_mb"]
            name = job.app
        elif self.preview is not None:
            if now - self._last_sample >= 2.0:
                self._last_sample = now
                s = self.preview.sample()
                self.hist["cpu"].append(s["cpu"])
                self.hist["io"].append(s["io"] / 1048576.0)
                for k in self.hist:
                    del self.hist[k][:-60]
                self._sample = s
            s, hist = getattr(self, "_sample", None), self.hist
            limit_cpu, limit_io = self._num(self.f_cpu, 3.0), self._num(self.f_io, 1.0)
            name = self.selected
        else:
            return
        if s is None:
            return
        self.sel_lbl.set(name if s.get("running", True) else t("app_not_running", app=name), TEXT if s.get("running", True) else AMBER)
        self.n_cpu.set(f"{s['cpu']:.1f}%")
        self.n_io.set(f"{s['io'] / 1048576:.1f} MB/s")
        self.n_net.set("-" if s.get("net") is None else f"{s['net'] / 1024:.0f} KB/s")
        for lbl, key, color, limit in ((self.spark_cpu, "cpu", GREEN, limit_cpu), (self.spark_io, "io", ACCENT_HOVER, limit_io)):
            vals = list(hist[key])
            if len(vals) >= 2:
                img = icons.sparkline_image(vals, 280, 44, color, limit=limit, bg=CARD)
                ci = ctk.CTkImage(light_image=img, dark_image=img, size=(280, 44))
                lbl.configure(image=ci)
                lbl._ci = ci
        if job is not None:
            left = job.idle_left()
            if left is None:
                self.status_lbl.set(t("status_busy"), AMBER)
            else:
                self.status_lbl.set(t("status_idle_in", left=C.fmt_hms(left)), GREEN)
        else:
            self.status_lbl.set(t("status_preview"), MUTED)

    @staticmethod
    def _num(widget, default):
        try:
            return float(widget.get().replace(",", "."))
        except ValueError:
            return default

    def _toggle(self):
        if self.app.watch is not None:
            self.app.stop_watch()
            return
        if not self.selected:
            messagebox.showinfo(C.APP_NAME, t("pick_app_first"), parent=self.app)
            return
        try:
            cfg = {
                "app": self.selected, "action": self.get_action(),
                "rule_close": self.v["rule_close"].get(), "rule_idle": self.v["rule_idle"].get(),
                "use_cpu": self.v["use_cpu"].get(), "use_io": self.v["use_io"].get(), "use_net": self.v["use_net"].get(),
                "idle_minutes": int(float(self.f_idle.get().replace(",", "."))),
                "cpu_limit": float(self.f_cpu.get().replace(",", ".")),
                "io_limit_mb": float(self.f_io.get().replace(",", ".")),
                "net_limit_kb": float(self.f_net.get().replace(",", ".")),
                "grace_seconds": int(float(self.f_grace.get())), "max_hours": int(float(self.f_max.get())),
            }
        except ValueError:
            messagebox.showerror(C.APP_NAME, t("err_numbers"), parent=self.app)
            return
        if not (cfg["rule_close"] or cfg["rule_idle"]):
            messagebox.showerror(C.APP_NAME, t("err_no_rule"), parent=self.app)
            return
        clean = cfgmod.clean_watch(cfg)
        clean["app"] = cfg["app"]
        self.app.cfg["screenshot_on_finish"] = bool(self.shot_var.get())
        self.app.start_watch(clean)


# =============================================================== Schedule
class SchedulePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title("sched_title", "sched_sub")
        form = card(self)
        form.pack(fill="x", pady=(0, 10))
        TLabel(form, t("sched_add"), 14, "bold").pack(fill="x", padx=14, pady=(12, 6))
        line = ctk.CTkFrame(form, fg_color="transparent")
        line.pack(fill="x", padx=12)
        side = "right" if is_rtl() else "left"
        TLabel(line, t("sched_time"), 12, color=MUTED).pack(side=side, padx=4)
        self.e_time = entry(line, 80, "03:30")
        self.e_time.pack(side=side, padx=4)
        self.act_menu, self.get_action, self.set_action = action_menu(line, width=150)
        self.act_menu.pack(side=side, padx=8)
        days = ctk.CTkFrame(form, fg_color="transparent")
        days.pack(fill="x", padx=12, pady=8)
        days.grid_columnconfigure(tuple(range(7)), weight=1, uniform="d")
        self.day_vars = []
        self.day_btns = []
        for i in range(7):
            var = ctk.BooleanVar(value=False)
            b = TButton(days, t(f"day{i}"), 11, height=30, command=lambda i=i: self._toggle_day(i))
            b.grid(row=0, column=(6 - i) if is_rtl() else i, padx=2, sticky="ew")
            self.day_vars.append(var)
            self.day_btns.append(b)
        TLabel(form, t("sched_hint"), 11, color=MUTED, wrap=600).pack(fill="x", padx=14)
        TButton(form, t("sched_add_btn"), 14, primary=True, height=38, command=self._add).pack(
            fill="x", padx=14, pady=(8, 14))
        TLabel(self, t("sched_list"), 14, "bold").pack(fill="x", pady=(4, 4))
        self.listing = ctk.CTkScrollableFrame(self, fg_color="transparent", height=230, scrollbar_button_color=BTN)
        self.listing.pack(fill="both", expand=True)
        self._built = None

    def _toggle_day(self, i):
        self.day_vars[i].set(not self.day_vars[i].get())
        self.day_btns[i].configure(fg_color=ACCENT if self.day_vars[i].get() else BTN)

    def _add(self):
        clock = C.parse_clock(self.e_time.get())
        if clock is None:
            messagebox.showerror(C.APP_NAME, t("err_time"), parent=self.app)
            return
        days = [i for i, v in enumerate(self.day_vars) if v.get()]
        self.app.scheduler.add(f"{clock[0]:02d}:{clock[1]:02d}", self.get_action(), days)
        self._built = None
        self.refresh()

    def on_show(self):
        self._built = None
        self.refresh()

    def refresh(self):
        items = self.app.cfg["schedules"]
        sig = tuple((s["id"], s["time"], tuple(s["days"]), s["action"], s.get("enabled", True), s.get("date")) for s in items)
        if sig == self._built:
            return
        self._built = sig
        for w in self.listing.winfo_children():
            w.destroy()
        if not items:
            TLabel(self.listing, t("sched_none"), 12, color=MUTED).pack(fill="x", pady=10)
        for s in items:
            row = card(self.listing)
            row.pack(fill="x", pady=3)
            when = " ".join(t(f"day{d}") for d in s["days"]) if s["days"] else t("sched_once", date=s.get("date", ""))
            side = "right" if is_rtl() else "left"
            TLabel(row, s["time"], 20, "bold", mono=True, anchor="center").pack(side=side, padx=(14, 8), pady=10)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side=side, fill="x", expand=True)
            TLabel(info, action_label(s["action"]), 13, "bold").pack(fill="x")
            TLabel(info, when, 11, color=MUTED).pack(fill="x")
            var = ctk.BooleanVar(value=s.get("enabled", True))
            sw = ctk.CTkSwitch(row, text="", variable=var, width=44, progress_color=GREEN_DARK, fg_color=BTN,
                               command=lambda s=s, v=var: self._enable(s, v.get()))
            sw.pack(side="left" if not is_rtl() else "right", padx=6)
            TButton(row, t("delete"), 11, danger=True, width=60, height=28,
                    command=lambda sid=s["id"]: self._delete(sid)).pack(side="left" if not is_rtl() else "right", padx=8)

    def _enable(self, s, on):
        s["enabled"] = bool(on)
        self.app.save_cfg()

    def _delete(self, sid):
        self.app.scheduler.remove(sid)
        self._built = None
        self.refresh()


# =============================================================== History
class HistoryPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title("hist_title", "hist_sub")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="s")
        self.stat = {}
        for i, key in enumerate(("started", "executed", "cancelled", "typical")):
            c = card(row)
            c.grid(row=0, column=(3 - i) if is_rtl() else i, padx=4, sticky="nsew")
            v = TLabel(c, "-", 22, "bold", anchor="center")
            v.pack(pady=(12, 0))
            TLabel(c, t("stat_" + key), 11, color=MUTED, anchor="center", wrap=130).pack(pady=(0, 12), padx=6)
            self.stat[key] = v
        TLabel(self, t("hist_recent"), 14, "bold").pack(fill="x", pady=(14, 4))
        self.listing = ctk.CTkScrollableFrame(self, fg_color=CARD, corner_radius=14, height=290, scrollbar_button_color=BTN)
        self.listing.pack(fill="both", expand=True)

    def on_show(self):
        events = C.read_history(300)
        st = compute_stats(events, datetime.now())
        self.stat["started"].set(str(st["started"]))
        self.stat["executed"].set(str(st["executed"]))
        self.stat["cancelled"].set(str(st["cancelled"]))
        typ = st["typical"]
        self.stat["typical"].set("-" if typ is None else fmt_clock(datetime.now().replace(hour=typ[0], minute=typ[1]).timestamp()).split(" (")[0])
        for w in self.listing.winfo_children():
            w.destroy()
        if not events:
            TLabel(self.listing, t("hist_none"), 12, color=MUTED).pack(fill="x", pady=10, padx=10)
        for e in reversed(events[-80:]):
            kind = e.get("kind", "")
            try:
                when = datetime.fromisoformat(e["ts"]).strftime("%m-%d  %H:%M")
            except (KeyError, ValueError):
                when = ""
            act = action_label(e["action"]) if e.get("action") in C.ACTIONS else ""
            text = t("ev_" + kind, action=act, app=e.get("app", ""), src=e.get("source", ""),
                     dur=C.fmt_human(e.get("seconds", 0))) if ("ev_" + kind) in i18n.STR["en"] else kind
            line = ctk.CTkFrame(self.listing, fg_color="transparent")
            line.pack(fill="x", padx=8, pady=1)
            side = "right" if is_rtl() else "left"
            TLabel(line, when, 11, color=MUTED, mono=True, width=96).pack(side=side)
            TLabel(line, text, 12).pack(side=side, fill="x", expand=True)


# =============================================================== Settings
class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", scrollbar_button_color=BTN,
                         scrollbar_button_hover_color=BTN_HOVER)
        self.app = app
        cfg = app.cfg
        TLabel(self, t("settings_title"), 24, "bold").pack(fill="x", pady=(2, 8))

        # ---- general ----
        g = self._card("set_general")
        row = ctk.CTkFrame(g, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        TLabel(row, t("language"), 13).pack(side="right" if is_rtl() else "left")
        seg = ctk.CTkSegmentedButton(row, values=["English", vis("العربية")], font=font(13, "bold"),
                                     fg_color=BTN, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                                     unselected_color=BTN, unselected_hover_color=BTN_HOVER, text_color=TEXT,
                                     command=self._language)
        seg.set("English" if cfg["language"] == "en" else vis("العربية"))
        seg.pack(side="left" if is_rtl() else "right")
        self.autostart_var = ctk.BooleanVar(value=system.autostart_enabled())
        switch(g, t("start_windows"), self.autostart_var, self._autostart).pack(anchor="e" if is_rtl() else "w", padx=14, pady=6)
        self.awake_var = ctk.BooleanVar(value=cfg["keep_awake"])
        switch(g, t("keep_awake"), self.awake_var, lambda: app.set_keep_awake(self.awake_var.get())).pack(
            anchor="e" if is_rtl() else "w", padx=14, pady=6)
        wrow = ctk.CTkFrame(g, fg_color="transparent")
        wrow.pack(fill="x", padx=14, pady=(6, 12))
        side = "right" if is_rtl() else "left"
        TLabel(wrow, t("warn_label"), 13).pack(side=side)
        self.e_warn = entry(wrow, 56)
        self.e_warn.insert(0, str(cfg["warning_minutes"]))
        self.e_warn.pack(side=side, padx=8)
        TButton(wrow, t("save"), 12, height=30, width=60, command=self._save_warn).pack(side=side)
        self.warn_note = TLabel(wrow, "", 11, color=GREEN)
        self.warn_note.pack(side=side, padx=8)

        # ---- telegram ----
        tg = self._card("set_telegram")
        self.tg_lbl = TLabel(tg, "", 13, color=MUTED)
        self.tg_lbl.pack(fill="x", padx=14, pady=(2, 6))
        TButton(tg, t("tg_setup"), 13, command=app.open_wizard).pack(fill="x", padx=14, pady=(0, 8))
        self.shot_var = ctk.BooleanVar(value=cfg["screenshot_enabled"])
        switch(tg, t("shot_enable"), self.shot_var, self._shot).pack(anchor="e" if is_rtl() else "w", padx=14, pady=4)
        TLabel(tg, t("shot_note"), 11, color=MUTED, wrap=560).pack(fill="x", padx=14, pady=(0, 12))

        # ---- admin options ----
        ad = self._card("set_admin")
        self.net_var = ctk.BooleanVar(value=cfg["per_app_network"])
        switch(ad, t("net_enable"), self.net_var, self._net).pack(anchor="e" if is_rtl() else "w", padx=14, pady=6)
        TLabel(ad, t("net_note"), 11, color=MUTED, wrap=560).pack(fill="x", padx=14)
        self.admin_lbl = TLabel(ad, "", 12, color=MUTED)
        self.admin_lbl.pack(fill="x", padx=14, pady=(6, 4))
        self.admin_btn = TButton(ad, t("restart_admin"), 13, command=app.restart_as_admin)
        self.admin_btn.pack(fill="x", padx=14, pady=(2, 8))
        hr(ad).pack(fill="x", padx=14, pady=6)
        self.hib_lbl = TLabel(ad, "", 12, color=MUTED, wrap=560)
        self.hib_lbl.pack(fill="x", padx=14)
        TButton(ad, t("hib_enable"), 13, command=app.enable_hibernate).pack(fill="x", padx=14, pady=(6, 14))

        # ---- updates ----
        up = self._card("set_updates")
        self.upd_var = ctk.BooleanVar(value=cfg["check_updates"])
        switch(up, t("upd_enable"), self.upd_var, self._upd).pack(anchor="e" if is_rtl() else "w", padx=14, pady=6)
        urow = ctk.CTkFrame(up, fg_color="transparent")
        urow.pack(fill="x", padx=14, pady=(0, 6))
        TLabel(urow, t("upd_repo"), 12, color=MUTED).pack(side=side)
        self.e_repo = entry(urow, 190)
        self.e_repo.insert(0, cfg["update_repo"] or updates.repo_name(cfg))
        self.e_repo.pack(side=side, padx=8)
        TButton(urow, t("upd_check"), 12, height=30, command=self._check_now).pack(side=side)
        self.upd_lbl = TLabel(up, t("upd_version", v=VERSION), 12, color=MUTED, wrap=560)
        self.upd_lbl.pack(fill="x", padx=14, pady=(0, 12))

        # ---- support ----
        sp = self._card("set_support")
        TButton(sp, t("copy_diag"), 13, command=app.copy_diagnostics).pack(fill="x", padx=14, pady=(2, 6))
        TButton(sp, t("open_data"), 13, command=lambda: os.startfile(C.DATA_DIR) if hasattr(os, "startfile") else None).pack(
            fill="x", padx=14, pady=(0, 6))
        self.diag_lbl = TLabel(sp, "", 11, color=GREEN)
        self.diag_lbl.pack(fill="x", padx=14, pady=(0, 12))

    def _card(self, title_key):
        c = card(self)
        c.pack(fill="x", pady=6)
        TLabel(c, t(title_key), 14, "bold").pack(fill="x", padx=14, pady=(12, 4))
        return c

    # ---- handlers ----
    def _language(self, value):
        self.app.set_language("en" if value == "English" else "ar")

    def _autostart(self):
        if not system.set_autostart(self.autostart_var.get()):
            messagebox.showerror(C.APP_NAME, t("err_autostart"), parent=self.app)
            self.autostart_var.set(system.autostart_enabled())

    def _save_warn(self):
        try:
            n = int(self.e_warn.get().strip())
            if not 1 <= n <= 180:
                raise ValueError
        except ValueError:
            messagebox.showerror(C.APP_NAME, t("err_warn"), parent=self.app)
            return
        self.app.core.set_warn_minutes(n)
        self.app.cfg["warning_minutes"] = n
        self.app.save_cfg()
        self.warn_note.set(t("saved"), GREEN)
        self.after(2500, lambda: self.warn_note.set(""))

    def _shot(self):
        self.app.cfg["screenshot_enabled"] = bool(self.shot_var.get())
        self.app.save_cfg()
        C.add_history("screenshot_setting", source="on" if self.shot_var.get() else "off")

    def _net(self):
        self.app.cfg["per_app_network"] = bool(self.net_var.get())
        self.app.save_cfg()

    def _upd(self):
        self.app.cfg["check_updates"] = bool(self.upd_var.get())
        self.app.save_cfg()

    def _check_now(self):
        repo = self.e_repo.get().strip()
        self.app.cfg["update_repo"] = repo
        self.app.save_cfg()
        self.upd_lbl.set(t("upd_checking"), MUTED)
        self.app.check_updates_async(manual=True)

    def refresh(self):
        app = self.app
        bot = app.bot
        if bot is None:
            self.tg_lbl.set(t("tg_off"), MUTED)
        elif bot.online:
            self.tg_lbl.set(t("tg_on", name=f"@{bot.username}" if bot.username else ""), GREEN)
        else:
            self.tg_lbl.set(t("tg_connecting"), AMBER)
        admin = system.is_admin()
        self.admin_lbl.set(t("admin_yes") if admin else t("admin_no"), GREEN if admin else AMBER)
        self.admin_btn.configure(state="disabled" if admin or not system.IS_WINDOWS else "normal")
        ok = app.hooks.hibernate_ok()
        self.hib_lbl.set(t("hib_on") if ok else (t("hib_off") if ok is False else t("hib_unknown")),
                         GREEN if ok else (AMBER if ok is False else MUTED))
        if app.update_info:
            self.upd_lbl.set(t("upd_available", v=app.update_info[0]), AMBER)
        elif app.update_checked:
            self.upd_lbl.set(t("upd_latest", v=VERSION), GREEN)

    def on_show(self):
        self.refresh()

    def show_diag_done(self):
        self.diag_lbl.set(t("diag_copied"), GREEN)
        self.after(3000, lambda: self.diag_lbl.set(""))


# =============================================================== The window
class App(ctk.CTk):
    def __init__(self, cfg, core, hooks, scheduler, icon_pair, srv, start_hidden):
        super().__init__()
        self.cfg, self.core, self.hooks, self.scheduler = cfg, core, hooks, scheduler
        self.icon_on, self.icon_off = icon_pair
        self.srv = srv
        self.inbox = queue.Queue()
        self.stop_event = threading.Event()
        self.bot = None
        self.wizard = None
        self.watch = None
        self.net_speed = monitor.NetSpeed()
        self.estats = monitor.TcpEstats()
        self.update_info = None
        self.update_checked = False
        self.last_action = core.action
        self.current = "home"
        self.pages = {}
        self._closing = False
        self._tip_shown = False
        self._tray_state = None
        self._tray_title = ""
        self._last_shot = 0.0
        self._slow = 0.0

        ctk.set_appearance_mode("dark")
        self.title(C.APP_NAME)
        self.geometry("900x640")
        self.minsize(900, 640)
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.report_callback_exception = lambda *a: C.log_error("".join(traceback.format_exception(*a)))

        self._start_bot()
        self._start_tray()
        self._build_shell()
        threading.Thread(target=system.listen_for_show, args=(srv, self.inbox, self.stop_event), daemon=True).start()

        resumed = core.resume_from_disk()
        if resumed == "app_timer_lost":
            self.after(1500, lambda: hooks.toast(C.APP_NAME, t("toast_timer_lost", lang="en")))
        self.needs_setup = not cfgmod.has_telegram(cfg) and not cfg.get("telegram_skipped")
        self.after(300, self._set_window_icon)
        if self.needs_setup:
            self.after(500, self.open_wizard)
        elif start_hidden:
            self.attributes("-alpha", 0.0)
            self.after(600, self._finish_hide)
        self.after(200, self._tick)
        if cfg["check_updates"]:
            self.after(8000, lambda: self.check_updates_async())

    # ---------- shell ----------
    def _build_shell(self):
        old = getattr(self, "shell", None)
        if old is not None:
            old.destroy()
        self.shell = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.shell.pack(fill="both", expand=True)
        rtl_ = is_rtl()
        side = ctk.CTkFrame(self.shell, width=206, fg_color=SIDEBAR, corner_radius=0)
        side.pack(side="right" if rtl_ else "left", fill="y")
        side.pack_propagate(False)
        body = ctk.CTkFrame(self.shell, fg_color=BG, corner_radius=0)
        body.pack(side="left" if rtl_ else "right", fill="both", expand=True, padx=18, pady=14)

        head = ctk.CTkFrame(side, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(18, 14))
        self.logo_img = ctk.CTkImage(light_image=self.icon_on, dark_image=self.icon_on, size=(40, 40))
        TLabel(head, "Sleepify", 20, "bold").pack(side="right" if rtl_ else "left", padx=(0, 0) if rtl_ else (0, 0))
        ctk.CTkLabel(head, image=self.logo_img, text="").pack(side="right" if rtl_ else "left", padx=8)
        self.nav = {}
        for page in PAGES:
            b = TButton(side, t("nav_" + page), 14, height=42, fg_color="transparent", hover_color=CARD,
                        text_color=MUTED, anchor="e" if rtl_ else "w", corner_radius=12,
                        command=lambda p=page: self.show(p))
            b.pack(fill="x", padx=12, pady=2)
            self.nav[page] = b

        ctk.CTkFrame(side, fg_color="transparent").pack(fill="both", expand=True)
        self.upd_btn = TButton(side, "", 12, height=32, fg_color="#5a4310", hover_color="#7a5a14", text_color=AMBER,
                               command=self._open_update)
        self.keep_lbl = TLabel(side, "", 11, color=GREEN, anchor="e" if rtl_ else "w")
        self.keep_lbl.pack(fill="x", padx=18)
        self.tg_lbl = TLabel(side, "", 11, color=MUTED, anchor="e" if rtl_ else "w")
        self.tg_lbl.pack(fill="x", padx=18, pady=(4, 0))
        TLabel(side, f"v{VERSION}", 10, color=MUTED, anchor="e" if rtl_ else "w").pack(fill="x", padx=18, pady=(4, 14))

        self.pages = {"home": HomePage(body, self), "watch": WatchPage(body, self),
                      "schedule": SchedulePage(body, self), "history": HistoryPage(body, self),
                      "settings": SettingsPage(body, self)}
        self.show(self.current)

    def show(self, name):
        self.current = name
        for p, page in self.pages.items():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for p, b in self.nav.items():
            b.configure(fg_color=CARD2 if p == name else "transparent", text_color=TEXT if p == name else MUTED)
        self.pages[name].on_show()
        self.pages[name].refresh()

    # ---------- window helpers ----------
    def _set_window_icon(self):
        try:
            self.iconbitmap(C.ICO_FILE)
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
            self.hooks.toast(t("toast_still_title", lang="en"), t("toast_still_body", lang="en"))

    def save_cfg(self):
        cfgmod.save_config(self.cfg)

    def set_language(self, lang):
        if lang == self.cfg["language"]:
            return
        self.cfg["language"] = lang
        i18n.set_language(lang)
        self.save_cfg()
        self.current = "settings"
        self._build_shell()
        self._start_bot()                 # the bot menu texts follow the language

    def set_keep_awake(self, on):
        self.cfg["keep_awake"] = bool(on)
        self.core.set_keep_awake_pref(on)
        self.save_cfg()

    # ---------- telegram ----------
    def _start_bot(self):
        self._stop_bot()
        if cfgmod.has_telegram(self.cfg):
            self.bot = TelegramBot(self.cfg["bot_token"], self.cfg["chat_id"], self.inbox, self.cfg["device_name"])
            self.hooks.bot = self.bot
            self.bot.start()

    def _stop_bot(self):
        if self.bot is not None:
            self.bot.stop.set()
        self.bot = None
        self.hooks.bot = None

    def context(self):
        return Context(self.core, self.scheduler, lambda: self.cfg, lambda: self.watch, self.stop_watch,
                       lambda: C.read_history(300))

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
        self._build_shell()

    def apply_new_config(self, cfg):
        self.cfg.clear()
        self.cfg.update(cfg)
        i18n.set_language(self.cfg["language"])
        self.save_cfg()

    def do_screenshot(self):
        if not self.cfg["screenshot_enabled"] or self.bot is None:
            return
        if time.time() - self._last_shot < 10:
            self.bot.send(t("screenshot_wait_more"))
            return
        self._last_shot = time.time()
        bot = self.bot

        def work():
            try:
                data = system.capture_screenshot()
                bot.send_photo(data, t("screenshot_caption"))
                C.add_history("screenshot", source="telegram")
            except Exception as e:
                C.log_error(f"screenshot failed: {e}")
                bot.send(t("screenshot_fail"))
        threading.Thread(target=work, daemon=True).start()
        self.hooks.toast(C.APP_NAME, t("toast_shot_sent", lang="en"))

    # ---------- user actions ----------
    def ui_start(self, seconds, action):
        if self.core.active and not messagebox.askyesno(C.APP_NAME, t("confirm_replace"), parent=self):
            return
        ok, msg = self.core.start(seconds, action, "app")
        if not ok:
            if msg == "err_no_hib" and messagebox.askyesno(C.APP_NAME, t("ask_enable_hib"), parent=self):
                self.enable_hibernate()
            elif msg != "err_no_hib":
                messagebox.showerror(C.APP_NAME, t(msg), parent=self)
        self.refresh_all()

    def ui_extend(self):
        ok, msg = self.core.extend(C.EXTEND_MINUTES * 60, "app")
        if not ok:
            messagebox.showerror(C.APP_NAME, t(msg), parent=self)
        self.refresh_all()

    def ui_pause(self):
        ok, msg = (self.core.resume("app") if self.core.paused else self.core.pause("app"))
        if not ok:
            messagebox.showerror(C.APP_NAME, t(msg), parent=self)
        self.refresh_all()

    def ui_cancel(self):
        self.core.cancel("app")
        self.refresh_all()

    def enable_hibernate(self):
        if not system.enable_hibernate_as_admin():
            messagebox.showinfo(C.APP_NAME, t("hib_manual"), parent=self)

    def restart_as_admin(self):
        if self.core.running and self.core.action in APP_RUN:
            if not messagebox.askyesno(C.APP_NAME, t("confirm_admin_restart"), parent=self):
                return
        if system.relaunch_as_admin():
            self.quit_app(force=True)
        else:
            messagebox.showerror(C.APP_NAME, t("err_admin"), parent=self)

    def net_available(self):
        return bool(self.cfg["per_app_network"]) and self.estats.available()

    def estats_if_enabled(self):
        return self.estats if self.net_available() else None

    # ---------- watching an app ----------
    def start_watch(self, wcfg):
        self.stop_watch(silent=True)
        sampler = monitor.AppSampler(wcfg["app"], estats=self.estats_if_enabled())
        self.watch = monitor.WatchJob(wcfg, sampler)
        self.core.set_watching(True)
        self.cfg["watch"] = {k: v for k, v in wcfg.items() if k != "app"}
        self.save_cfg()
        C.add_history("watch_start", app=wcfg["app"], action=wcfg["action"])
        self.hooks.log(f"Watching {wcfg['app']} then {C.ACTION_NAME[wcfg['action']]}")
        self.hooks.tg(t("watch_started", app=wcfg["app"], action=action_label(wcfg["action"])),
                      buttons=[[(t("btn_stopwatch"), "stopwatch")]])

    def stop_watch(self, silent=False):
        if self.watch is not None:
            self.hooks.log(f"Stopped watching {self.watch.app}")
            self.watch = None
            self.core.set_watching(False)
            if not silent:
                self.hooks.tg(t("watch_stopped"))

    def _watch_tick(self):
        job = self.watch
        if job is None:
            return
        job.tick()
        if job.state == "waiting":
            return
        self.watch = None
        self.core.set_watching(False)
        if job.state == "timeout":
            self.hooks.log(f"Gave up watching {job.app} after {job.cfg['max_hours']} h")
            self.hooks.toast(C.APP_NAME, t("toast_watch_timeout", lang="en", app=job.app))
            self.hooks.tg(t("watch_timeout", app=job.app, hours=job.cfg["max_hours"]))
            return
        action, grace = job.cfg["action"], job.cfg["grace_seconds"]
        C.add_history("watch_done", app=job.app, action=action, source=job.reason)
        self.hooks.log(f"{job.app} is done ({job.reason})")
        self.core.start(grace, action, "watch")
        self.hooks.toast(C.APP_NAME, t("toast_watch_done", lang="en", app=job.app, secs=grace))
        self.hooks.tg(t("watch_done", app=job.app, reason=t("reason_" + job.reason), secs=grace,
                        action=action_label(action)),
                      buttons=[[(t("btn_extend", mins=C.EXTEND_MINUTES), "ext"), (t("btn_cancel"), "cancel")]])
        if job.cfg.get("screenshot_on_finish") or self.cfg["screenshot_on_finish"]:
            self._last_shot = 0
            self.do_screenshot()

    # ---------- tray ----------
    def _start_tray(self):
        q = self.inbox
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: t("tray_show", lang="en"), lambda icon, item: q.put(("show",)), default=True),
            pystray.MenuItem(lambda item: t("tray_cancel", lang="en"), lambda icon, item: q.put(("cancel",)),
                             enabled=lambda item: self.core.active),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: t("tray_exit", lang="en"), lambda icon, item: q.put(("quit",))),
        )
        self.tray = pystray.Icon(C.APP_NAME, self.icon_off, "Sleepify", menu)
        self.hooks.tray = self.tray
        try:
            self.tray.run_detached()
        except Exception as e:
            C.log_error(f"tray icon failed to start: {e}")

    def _refresh_tray(self, on, text):
        try:
            if on != self._tray_state:
                self._tray_state = on
                self.tray.icon = self.icon_on if on else self.icon_off
                self.tray.update_menu()
            if text != self._tray_title:
                self._tray_title = text
                self.tray.title = text
        except Exception as e:
            C.log_error(f"tray update failed: {e}")

    # ---------- updates ----------
    def check_updates_async(self, manual=False):
        repo = updates.repo_name(self.cfg)

        def work():
            info = updates.check_latest(repo)
            self.inbox.put(("update", info, manual, bool(repo)))
        threading.Thread(target=work, daemon=True).start()

    def _open_update(self):
        if self.update_info:
            webbrowser.open(self.update_info[1])

    # ---------- diagnostics ----------
    def diagnostics_text(self):
        bot = self.bot
        lines = [f"Sleepify {VERSION}", f"Python {sys.version.split()[0]}  frozen={C.FROZEN}",
                 f"Windows {platform.platform()}", f"admin={system.is_admin()}  language={self.cfg['language']}",
                 f"telegram={'connected' if bot and bot.online else ('connecting' if bot else 'off')}"
                 f"  last_error={bot.last_error if bot else ''}",
                 f"hibernate_ok={self.hooks.hibernate_ok()}  keep_awake={self.cfg['keep_awake']}"
                 f"  per_app_network={self.cfg['per_app_network']}  net_error={self.estats.last_error}",
                 f"timer: running={self.core.running} paused={self.core.paused} action={self.core.action}"
                 f"  watching={self.watch.app if self.watch else None}",
                 "", "--- error.log (last 25 lines) ---", C.scrub(C.tail(C.ERROR_FILE, 25)),
                 "--- log.txt (last 15 lines) ---", C.scrub(C.tail(C.LOG_FILE, 15))]
        return "\n".join(lines)

    def copy_diagnostics(self):
        self.clipboard_clear()
        self.clipboard_append(self.diagnostics_text())
        self.update()
        page = self.pages.get("settings")
        if page:
            page.show_diag_done()

    # ---------- main loop ----------
    def _tick(self):
        try:
            self._drain_inbox()
            if self._closing:
                return
            self.core.tick()
            self.scheduler.tick()
            self._watch_tick()
            self.refresh_all()
        except Exception:
            C.log_error(traceback.format_exc())
        if not self._closing:
            self.after(250, self._tick)

    def refresh_all(self):
        core = self.core
        page = self.pages.get(self.current)
        if page is not None:
            page.refresh()
        running = core.active or self.watch is not None
        rem = core.remaining()
        self.keep_lbl.set(t("keep_on") if self.core._awake else "", GREEN)
        bot = self.bot
        if bot is None:
            self.tg_lbl.set(t("side_tg_off"), MUTED)
        elif bot.online:
            self.tg_lbl.set(t("side_tg_on"), GREEN)
        else:
            self.tg_lbl.set(t("side_tg_connecting"), AMBER)
        if self.update_info and not self.upd_btn.winfo_ismapped():
            self.upd_btn.set(t("upd_badge", v=self.update_info[0]))
            self.upd_btn.pack(fill="x", padx=14, pady=(0, 8), before=self.keep_lbl)
        if core.running:
            text = f"Sleepify - {C.ACTION_NAME[core.action]} {C.fmt_hms(rem)}"
        elif core.paused:
            text = f"Sleepify - paused {C.fmt_hms(rem)}"
        elif self.watch is not None:
            text = f"Sleepify - watching {self.watch.app}"
        else:
            text = "Sleepify"
        self._refresh_tray(running, text)

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
            elif kind in ("tg", "cb"):
                reply = (run_command(self.context(), item[1], item[2]) if kind == "tg"
                         else run_callback(self.context(), item[1]))
                if self.bot is not None:
                    self.bot.send(reply.text, buttons=reply.buttons)
                    if kind == "cb":
                        self.bot.answer_callback(item[2])
                if reply.special == "screenshot":
                    self.do_screenshot()
            elif kind == "update":
                _, info, manual, had_repo = item
                self.update_info = info
                self.update_checked = True
                page = self.pages.get("settings")
                if manual and page is not None:
                    page.upd_lbl.set(t("upd_available", v=info[0]) if info else
                                     (t("upd_latest", v=VERSION) if had_repo else t("upd_no_repo")),
                                     AMBER if info else GREEN)

    # ---------- exit ----------
    def quit_app(self, force=False):
        if self.core.running and not force:
            self.show_window()
            key = "confirm_exit_app" if self.core.action in APP_RUN else "confirm_exit_win"
            if not messagebox.askyesno(C.APP_NAME, t(key), parent=self):
                return
        if self.core.running and self.core.action in APP_RUN:
            self.core.cancel("exit")
            if self.bot:
                self.bot.send(t("exit_app_timer"), wait=True)
        self.core.set_watching(False)
        self.core.set_keep_awake_pref(False)
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
