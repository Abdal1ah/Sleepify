# -*- coding: utf-8 -*-
"""First-run setup: language, name of this PC, your own bot's token, then link your account with a code."""
import threading
import traceback
import webbrowser

import customtkinter as ctk
from tkinter import messagebox

from . import common as C
from . import config as cfgmod
from . import i18n
from .i18n import is_rtl, t
from .telegram import (PairingWatcher, TelegramError, new_pair_code, tg_api, valid_token_format)
from .widgets import (AMBER, BG, GREEN, MUTED, RED, TEXT, TButton, TLabel, checkbox, entry, font, vis)


class SetupWizard(ctk.CTkToplevel):
    def __init__(self, app, cfg):
        super().__init__(app)
        self.app = app
        self.cfg = cfg
        self.d = {"language": cfg.get("language", "en"), "device_name": cfg.get("device_name") or C.default_device_name(),
                  "bot_token": "", "username": "", "chat_id": None, "first_name": ""}
        self.watcher = None
        self.job = None
        self.alive = True
        self.step = 0
        self.code = ""
        self.title("Sleepify")
        self.geometry("540x620")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=28, pady=22)
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self._safe(lambda: self.attributes("-topmost", False)))
        self.after(150, lambda: self._safe(self.grab_set))
        self.after(300, lambda: self._safe(lambda: self.iconbitmap(C.ICO_FILE)))
        self._step0()
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

    def _text(self, text, size=13, color=TEXT, bold=False, pady=(0, 8), wrap=480):
        lbl = TLabel(self.body, text, size, "bold" if bold else "normal", color=color, wrap=wrap)
        lbl.pack(fill="x", pady=pady)
        return lbl

    def _nav(self, back=None, nxt=None, nxt_text=None, nxt_enabled=True):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(side="bottom", fill="x", pady=(10, 0))
        row.grid_columnconfigure((0, 1), weight=1)
        if back:
            TButton(row, t("wz_back"), 13, height=40, command=back).grid(row=0, column=1 if is_rtl() else 0, padx=(0, 6), sticky="ew")
        self.btn_next = TButton(row, nxt_text or t("wz_next"), 14, primary=True, height=40, command=nxt,
                                state="normal" if nxt_enabled else "disabled")
        self.btn_next.grid(row=0, column=0 if is_rtl() else 1, padx=(6, 0), sticky="ew")

    # ---------- step 0: language ----------
    def _step0(self):
        self._clear(0)
        TLabel(self.body, "Sleepify", 30, "bold", anchor="center").pack(fill="x", pady=(40, 4))
        TLabel(self.body, "Choose your language  ·  اختر لغتك", 14, color=MUTED, anchor="center").pack(fill="x", pady=(0, 30))
        for code, label in (("en", "English"), ("ar", "العربية")):
            b = ctk.CTkButton(self.body, text=vis(label) if code == "ar" else label, height=56, font=font(20, "bold"),
                              fg_color="#232a5c", hover_color="#6d5cff", corner_radius=14,
                              command=lambda c=code: self._pick_language(c))
            b.pack(fill="x", pady=8)

    def _pick_language(self, code):
        self.d["language"] = code
        i18n.set_language(code)
        self._step1()

    # ---------- step 1: welcome ----------
    def _step1(self):
        self._clear(1)
        linked = cfgmod.has_telegram(self.cfg)
        self._text(t("wz_welcome"), 24, bold=True, pady=(0, 6))
        self._text(t("wz_intro"), color=MUTED, pady=(0, 14))
        self._text(t("wz_device"), 12, MUTED, True, pady=(0, 3))
        self.e_device = entry(self.body, 300)
        self.e_device.configure(justify="right" if is_rtl() else "left")
        self.e_device.insert(0, self.d["device_name"])
        self.e_device.pack(fill="x", pady=(0, 18))
        if linked:
            self._text(t("wz_already"), 12, GREEN, pady=(0, 6))
            TButton(self.body, t("wz_keep"), 14, primary=True, height=42, command=self._save_keep).pack(fill="x", pady=(0, 8))
            TButton(self.body, t("wz_change"), 13, height=40, command=self._to_step2).pack(fill="x")
        else:
            TButton(self.body, t("wz_setup"), 14, primary=True, height=42, command=self._to_step2).pack(fill="x", pady=(0, 8))
            TButton(self.body, t("wz_skip"), 13, height=40, command=self._skip).pack(fill="x")

    def _read_step1(self):
        name = self.e_device.get().strip()[:30]
        if not name:
            messagebox.showerror("Sleepify", t("wz_need_name"), parent=self)
            return False
        self.d["device_name"] = name
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
        self._text(t("wz_s2_title"), 20, bold=True, pady=(0, 8))
        self._text(t("wz_s2_steps"), pady=(0, 10))
        TButton(self.body, t("wz_open_botfather"), 13, height=40,
                command=lambda: webbrowser.open("https://t.me/BotFather")).pack(fill="x", pady=(0, 10))
        self.e_token = entry(self.body, 300, t("wz_paste_token"), show="•")
        self.e_token.pack(fill="x")
        self.show_var = ctk.BooleanVar(value=False)
        checkbox(self.body, t("wz_show_token"), self.show_var,
                 lambda: self.e_token.configure(show="" if self.show_var.get() else "•")).pack(
            anchor="e" if is_rtl() else "w", pady=(8, 8))
        TButton(self.body, t("wz_check_token"), 13, height=40, command=self._verify).pack(fill="x")
        self.v_lbl = self._text("", 12, MUTED, pady=(8, 0))
        self._text(t("wz_token_private"), 11, MUTED, pady=(8, 0))
        self._nav(back=self._step1, nxt=self._step3, nxt_enabled=False)

    def _verify(self):
        token = self.e_token.get().strip()
        if not valid_token_format(token):
            self.v_lbl.set(t("wz_bad_format"), RED)
            return
        self.v_lbl.set(t("wz_checking"), AMBER)
        job = {"done": False}
        self.job = job

        def work():
            try:
                me = tg_api(token, "getMe")
                job.update(ok=True, token=token, username=(me or {}).get("username", ""))
            except TelegramError as e:
                job.update(ok=False, msg=t("wz_invalid_token") if e.code == 401 else t("wz_tg_error", code=e.code))
            except Exception:
                job.update(ok=False, msg=t("wz_no_internet"))
            job["done"] = True
        threading.Thread(target=work, daemon=True).start()

    def _on_verified(self, job):
        if self.step != 2:
            return
        if job.get("ok"):
            self.d["bot_token"], self.d["username"] = job["token"], job["username"]
            self.v_lbl.set(t("wz_bot_ok", name=job["username"]), GREEN)
            self.btn_next.configure(state="normal")
        else:
            self.v_lbl.set(job.get("msg", ""), RED)
            self.btn_next.configure(state="disabled")

    # ---------- step 3: link the account ----------
    def _step3(self):
        self._clear(3)
        self.code = new_pair_code()
        self.d["chat_id"] = None
        self._text(t("wz_s3_title"), 20, bold=True, pady=(0, 8))
        self._text(t("wz_s3_intro"), pady=(0, 6))
        TLabel(self.body, self.code, 34, "bold", color=GREEN, mono=True, anchor="center").pack(fill="x", pady=(4, 6))
        TButton(self.body, t("wz_open_bot"), 14, primary=True, height=42, command=self._open_bot).pack(fill="x", pady=(0, 8))
        self._text(t("wz_s3_manual"), 12, MUTED, pady=(0, 2))
        TLabel(self.body, f"/start {self.code}", 14, "bold", mono=True, anchor="center").pack(fill="x", pady=(0, 10))
        self.link_lbl = self._text(t("wz_waiting"), 13, AMBER, pady=(0, 6))
        TButton(self.body, t("wz_new_code"), 13, height=38, command=self._step3).pack(fill="x")
        self._nav(back=self._step2, nxt=self._step4, nxt_enabled=False)
        self.watcher = PairingWatcher(self.d["bot_token"], self.code)
        self.watcher.start()

    def _open_bot(self):
        webbrowser.open(f"https://t.me/{self.d['username']}?start={self.code}")

    def _on_linked(self):
        if self.step != 3:
            return
        who = f" ({self.d['first_name']})" if self.d["first_name"] else ""
        self.link_lbl.set(t("wz_linked", who=who), GREEN)
        self.btn_next.configure(state="normal")

    # ---------- step 4: done ----------
    def _step4(self):
        self._clear(4)
        self._text(t("wz_done_title"), 24, bold=True, pady=(0, 8))
        self._text(t("wz_done_body", name=self.d["device_name"], bot=self.d["username"]), pady=(0, 10))
        self._text(t("wz_multi"), 12, MUTED)
        self._nav(back=None, nxt=self._finish, nxt_text=t("wz_finish"))

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
                C.log_error(f"welcome message failed: {e}")
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
                    self.link_lbl.set(t("wz_retrying"), AMBER)
        except Exception:
            C.log_error(traceback.format_exc())
        self.after(300, self._poll)

    def close(self):
        self.alive = False
        self._stop_watcher()
        i18n.set_language(self.app.cfg["language"])
        self.app.wizard_closed()
        try:
            self.destroy()
        except Exception:
            pass
