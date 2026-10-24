# -*- coding: utf-8 -*-
"""Starting Sleepify."""
import ctypes
import os
import sys
import traceback

from . import common as C
from . import config as cfgmod
from . import i18n, system
from .core import Scheduler, TimerCore
from .icons import build_icons


def _install_excepthooks():
    import threading

    def hook(exc_type, exc, tb):
        C.log_error("".join(traceback.format_exception(exc_type, exc, tb)))
    sys.excepthook = hook
    threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)


def main():
    argv = sys.argv[1:]
    if "--install" in argv:
        sys.exit(system.install_shortcuts())
    if "--uninstall" in argv:
        sys.exit(system.remove_shortcuts())
    _install_excepthooks()
    try:  # own taskbar identity (so Windows doesn't group us under Python)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sleepify.PCSleepTimer")
    except Exception:
        pass

    # after "Restart as Administrator" the old copy needs a moment to close
    srv, status = system.single_instance(wait_seconds=12 if "--restarted" in argv else 0)
    if status == "forwarded":
        return                       # the running copy will show its window
    if status == "busy":
        from tkinter import messagebox
        messagebox.showerror(C.APP_NAME, f"Port {C.SINGLE_PORT} is used by another program, "
                                         "so Sleepify can't start. Change SINGLE_PORT in sleepify/common.py.")
        return
    system.hold_mutex()

    cfgmod.migrate_legacy_config()
    cfg = cfgmod.load_config()
    i18n.set_language(cfg["language"])
    hooks = system.Hooks()
    core = TimerCore(hooks, cfg["warning_minutes"], keep_awake=cfg["keep_awake"])
    scheduler = Scheduler(core, hooks, lambda: cfg["schedules"], lambda: cfgmod.save_config(cfg))

    from .gui import App               # imported here: it loads the window libraries
    app = App(cfg, core, hooks, scheduler, build_icons(), srv, "--hidden" in argv)
    app.mainloop()
    os._exit(0)     # the tray thread must not keep a hidden process alive
