# -*- coding: utf-8 -*-
"""Colors and small widgets shared by the main window and the setup wizard (they also handle Arabic)."""
import customtkinter as ctk

from . import rtl
from .i18n import is_rtl

# ---- palette ----
BG = "#0a0d22"
SIDEBAR = "#0e1230"
CARD = "#141939"
CARD2 = "#1b2147"
BORDER = "#262e63"
TEXT = "#f1f3ff"
MUTED = "#8b93c4"
ACCENT = "#6d5cff"          # violet: selection
ACCENT_HOVER = "#8273ff"
GREEN = "#62f27b"
GREEN_DARK = "#2fbf4d"
AMBER = "#ffb84d"
RED = "#ff5a6e"
RED_DARK = "#7d2a3c"
RED_HOVER = "#a33a50"
BTN = "#232a5c"
BTN_HOVER = "#2f3877"
INK = "#07091a"             # dark text on bright buttons


def font(size, weight="normal", family="Segoe UI"):
    return ctk.CTkFont(family=family, size=size, weight=weight)


def vis(text, fnt=None, wrap=0):
    """Logical text -> what Tk should draw (Arabic is joined and reordered)."""
    if not is_rtl():
        return text
    if wrap and fnt is not None:
        return rtl.wrap_visual(text, fnt.measure, wrap)
    return "\n".join(rtl.to_visual(line) for line in text.split("\n"))


class TLabel(ctk.CTkLabel):
    """Label that aligns right and shapes Arabic when the app language is Arabic."""

    def __init__(self, parent, text="", size=13, weight="normal", color=TEXT, wrap=0, mono=False, **kw):
        self._fnt = font(size, weight, "Consolas" if mono else "Segoe UI")
        self._wrap, self._last = wrap, None
        r = is_rtl()
        kw.setdefault("anchor", "e" if r else "w")
        super().__init__(parent, text=vis(text, self._fnt, wrap), font=self._fnt, text_color=color,
                         justify="right" if r else "left", wraplength=0 if r else wrap, **kw)

    def set(self, text, color=None):
        key = (text, color)
        if key == self._last:
            return
        self._last = key
        opts = {"text": vis(text, self._fnt, self._wrap)}
        if color:
            opts["text_color"] = color
        self.configure(**opts)


class TButton(ctk.CTkButton):
    def __init__(self, parent, text="", size=13, weight="bold", primary=False, danger=False, **kw):
        fnt = font(size, weight)
        if primary:
            colors = dict(fg_color=GREEN, hover_color="#86ff99", text_color=INK)
        elif danger:
            colors = dict(fg_color=RED_DARK, hover_color=RED_HOVER, text_color=TEXT)
        else:
            colors = dict(fg_color=BTN, hover_color=BTN_HOVER, text_color=TEXT)
        for k, v in colors.items():
            kw.setdefault(k, v)
        kw.setdefault("corner_radius", 10)
        kw.setdefault("height", 36)
        self._fnt = fnt
        super().__init__(parent, text=vis(text, fnt), font=fnt, **kw)

    def set(self, text):
        self.configure(text=vis(text, self._fnt))


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER, **kw)


def switch(parent, text, variable, command=None):
    return ctk.CTkSwitch(parent, text=vis(text), variable=variable, command=command, font=font(13),
                         text_color=TEXT, progress_color=GREEN_DARK, button_color="#ffffff",
                         button_hover_color="#dfe3ff", fg_color=BTN)


def checkbox(parent, text, variable, command=None):
    return ctk.CTkCheckBox(parent, text=vis(text), variable=variable, command=command, font=font(13),
                           text_color=TEXT, checkbox_width=20, checkbox_height=20, corner_radius=6,
                           fg_color=GREEN_DARK, hover_color=GREEN, border_color=BORDER)


def entry(parent, width=70, placeholder="", **kw):
    return ctk.CTkEntry(parent, width=width, height=34, justify="center", fg_color=CARD2, border_color=BORDER,
                        text_color=TEXT, placeholder_text=vis(placeholder), font=font(13), **kw)


def hr(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=BORDER)
