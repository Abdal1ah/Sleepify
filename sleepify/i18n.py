# -*- coding: utf-8 -*-
"""English / Arabic texts for the window and for the Telegram messages, plus helpers to use them."""
from datetime import datetime

STR = {
    "en": {
        # ---------- timer actions ----------
        "act_shutdown": "Shutdown", "act_restart": "Restart", "act_hibernate": "Hibernate",
        "act_sleep": "Sleep", "act_lock": "Lock", "act_display": "Screen off",
        # ---------- errors ----------
        "err_zero": "Time must be greater than zero.",
        "err_max": "The maximum is 24 hours.",
        "err_denied": "Windows refused the command.",
        "err_none": "There is no active timer.",
        "err_resched": "Could not reschedule, so the timer was cancelled.",
        "err_no_hib": "Hibernate is turned off on this PC. Turn it on in Settings, or run Command Prompt as Administrator and type: powercfg /h on",
        "err_late": "It is about to finish, too late to pause.",
        "err_not_paused": "The timer is not paused.",
        "err_numbers": "Please enter whole numbers only.",
        "err_time": "Type the time like 03:30 (or 3:30pm).",
        "err_warn": "Enter a number between 1 and 180.",
        "err_autostart": "Could not change the 'Start with Windows' setting.",
        "err_no_rule": "Choose at least one way to know the app is done.",
        "err_admin": "Could not restart as Administrator.",
        # ---------- buttons shared by the window and Telegram ----------
        "btn_extend": "+{mins} min", "btn_cancel": "Cancel", "btn_pause": "Pause", "btn_resume": "Resume",
        "btn_stopwatch": "Stop watching",
        # ---------- Telegram messages ----------
        "help": (
            "🤖 Sleepify - commands:\n\n"
            "/status - time left\n"
            "/shutdown 1h30m - shutdown timer\n"
            "/restart 20m - restart timer\n"
            "/hibernate 45m - hibernate timer\n"
            "/sleep 30m - sleep timer\n"
            "/lock [30m] - lock the PC (now, or after a time)\n"
            "/extend 10m - add time (default 10 min)\n"
            "/pause and /resume - pause the timer\n"
            "/at 03:30 [action] - do it at a clock time\n"
            "/watch - what Sleepify is watching\n"
            "/screenshot - a picture of the screen (if enabled)\n"
            "/stats - your last 7 days\n"
            "/cancel - cancel the timer\n\n"
            "Time: h = hours, m = minutes, s = seconds, e.g. 1h30m, 45m or 45m30s. A bare number means minutes."),
        "cmd_status": "Time left", "cmd_shutdown": "Shutdown timer, e.g. /shutdown 1h30m",
        "cmd_restart": "Restart timer", "cmd_hibernate": "Hibernate timer, e.g. /hibernate 45m",
        "cmd_sleep": "Sleep timer", "cmd_lock": "Lock the PC", "cmd_extend": "Add time, e.g. /extend 10m",
        "cmd_cancel": "Cancel the timer", "cmd_pause": "Pause the timer", "cmd_resume": "Resume the timer",
        "cmd_at": "Do it at a time, e.g. /at 03:30", "cmd_screenshot": "Screenshot of the PC",
        "cmd_stats": "Your last 7 days", "cmd_watch": "What is being watched", "cmd_help": "Show the commands",
        "status_none": "🔴 No timer is running.",
        "status_running": "🟢 Timer running\nAction: {action}\nTime left: {left}\nRuns at: {at}",
        "status_paused": "⏸️ Timer paused\nAction: {action}\nTime left: {left}",
        "bad_duration": "❌ Please write the time like this: /{cmd} 1h30m or /{cmd} 45m",
        "bad_duration_extend": "❌ Please write the time like this: /extend 10m",
        "started": "✅ Timer started: {action} in {dur}\nAt: {at}",
        "replaced": "(the previous timer was replaced)",
        "app_run_note": "⚠️ Keep Sleepify running in the tray. If it is closed, this timer is cancelled.",
        "extended": "⏰ Added {dur}. Time left {left}, runs at {at}",
        "cancelled": "✅ Timer cancelled.", "cancel_none": "ℹ️ There is no timer to cancel.",
        "paused_ok": "⏸️ Paused with {left} left.", "resumed_ok": "▶️ Resumed. Time left {left}, runs at {at}",
        "lock_now": "🔒 The PC is locked.",
        "unknown_cmd": "I don't know that command 🤔 Send /help",
        "warn_msg": "⚠️ {mins} min left, then: {action}. Save your work! 💾",
        "final": "🔔 {action} starts now!",
        "cancelled_pc": "✅ Timer cancelled from the PC.",
        "hib_failed": "❌ Hibernate failed. Make sure Hibernate is turned on (powercfg /h on).",
        "act_failed": "❌ {action} failed.",
        "exit_app_timer": "⚠️ Sleepify was closed, so the timer was cancelled.",
        "linked": "✅ Linked! This chat now controls this PC.\n\n",
        "at_ok": "✅ {action} scheduled at {time} ({date}).",
        "at_bad": "❌ Use it like this: /at 03:30 or /at 3:30pm hibernate",
        "schedules_none": "No schedules.", "schedule_line": "• {time}  {action}  ({days})",
        "screenshot_off": "📸 Screenshots are turned off. Turn them on in Sleepify → Settings.",
        "screenshot_wait": "📸 Taking a screenshot...",
        "screenshot_wait_more": "⏳ Please wait a few seconds between screenshots.",
        "screenshot_fail": "❌ Could not take a screenshot (is the screen locked?).",
        "screenshot_caption": "Screenshot",
        "stats_text": "📊 Last {n} days\nTimers started: {started}\nExecuted: {executed}\nCancelled: {cancelled}\nUsually ends around: {typical}",
        "cb_expired": "This button is too old.",
        "watch_none": "👁️ Nothing is being watched.",
        "watch_status": "👁️ Watching {app}\nCPU {cpu}%  |  disk {io} MB/s{net}{idle}",
        "watch_idle_in": "\nIdle: it counts as finished in about {mins} min",
        "watch_started": "👁️ Watching {app}. When it is done: {action}.",
        "watch_stopped": "✅ Stopped watching.",
        "watch_done": "✅ {app} is done ({reason}). {action} in {secs} seconds.",
        "watch_timeout": "⏱️ Gave up watching {app} after {hours} hours. The PC was left on.",
        "reason_closed": "it was closed", "reason_idle": "it went idle",
        # ---------- toasts (always English) ----------
        "toast_still_title": "Sleepify is still running", "toast_still_body": "It lives near the clock. Right-click the icon for options.",
        "toast_timer_lost": "The timer from last time was cancelled because Sleepify was closed.",
        "toast_shot_sent": "A screenshot was sent to your Telegram.",
        "toast_watch_done": "{app} is done. Action in {secs} seconds.",
        "toast_watch_timeout": "Stopped watching {app}: waited too long.",
        "tray_show": "Show Sleepify", "tray_cancel": "Cancel timer", "tray_exit": "Exit",
        # ---------- window ----------
        "nav_home": "Timer", "nav_watch": "Watch an app", "nav_schedule": "Schedule", "nav_history": "History",
        "nav_settings": "Settings",
        "home_title": "Timer", "new_timer": "New timer", "custom_time": "Custom time",
        "hours": "Hours", "minutes": "Minutes", "seconds": "Seconds", "start_timer": "Start timer",
        "keep_awake": "Keep the PC awake while waiting",
        "keep_on": "● Keeping the PC awake",
        "hint_windows": "Windows counts down by itself, so it still happens if you exit Sleepify.",
        "hint_app": "Sleepify runs this one, so keep it in the tray. Exit cancels it.",
        "state_running": "RUNNING", "state_paused": "PAUSED", "state_ready": "READY", "state_watching": "WATCHING",
        "action_at": "{action} at {at}", "pick_time": "Pick a time to start", "watching_app": "Watching {app}",
        "next_sched": "Next schedule", "no_sched": "No schedule set", "sched_in": "{action} at {time}, in {left}",
        "tile_watch": "Watching", "tile_none": "Nothing",
        "confirm_replace": "A timer is already running. Replace it?",
        "ask_enable_hib": "Hibernate is turned off in Windows. Turn it on now? (Windows will ask for permission.)",
        "hib_manual": "Could not ask for permission. Run Command Prompt as Administrator and type: powercfg /h on",
        "confirm_admin_restart": "A timer that Sleepify runs itself is active, and restarting cancels it. Continue?",
        "confirm_exit_app": "A timer run by Sleepify is active.\nIf you exit, it will be CANCELLED.\n\nExit anyway?",
        "confirm_exit_win": "A timer is running.\nWindows will still do it on time even after you exit.\n\nExit anyway?",
        # watch page
        "watch_title": "Watch an app",
        "watch_sub": "Choose an installer, game launcher or any program. Sleepify keeps the PC awake and, when the program has finished, runs the action you pick.",
        "choose_app": "Choose the app", "refresh": "Refresh", "show_background": "Show background programs",
        "live_title": "Live activity", "no_app_selected": "Pick an app from the list.",
        "no_apps": "No programs found.", "app_not_running": "{app} is not running",
        "cpu": "CPU", "disk": "Disk", "net": "Network",
        "status_busy": "Busy: it is still working.", "status_idle_in": "Idle. Counts as finished in {left}",
        "status_preview": "Preview only. Press Start watching to begin.",
        "rules_title": "When is it finished?", "rule_close": "When the app closes",
        "rule_idle": "When it has been idle for", "min_unit": "minutes",
        "idle_means": "Idle means all of these are below:", "rule_cpu": "CPU", "rule_disk": "Disk",
        "rule_net": "Network", "pct_unit": "%", "mbs_unit": "MB/s", "kbs_unit": "KB/s",
        "net_needs_admin": "Network per app needs Administrator. Turn it on in Settings.",
        "then_do": "Then do:", "grace_label": "after", "sec_unit": "seconds",
        "max_label": "Give up after", "hour_unit": "hours (0 = never)",
        "shot_on_finish": "Send a screenshot to Telegram when it finishes",
        "start_watch": "Start watching", "stop_watch": "Stop watching", "pick_app_first": "Pick an app first.",
        # schedule page
        "sched_title": "Schedule", "sched_sub": "Do something at a clock time, once or on chosen days.",
        "sched_add": "Add a schedule", "sched_time": "At", "sched_add_btn": "Add",
        "sched_hint": "No days selected = one time, at the next occurrence of that time. A warning appears before it happens.",
        "sched_list": "Your schedules", "sched_none": "No schedules yet.", "sched_once": "once ({date})",
        "delete": "Delete",
        "day0": "Mon", "day1": "Tue", "day2": "Wed", "day3": "Thu", "day4": "Fri", "day5": "Sat", "day6": "Sun",
        # history page
        "hist_title": "History", "hist_sub": "What Sleepify did on this PC.", "hist_recent": "Recent events",
        "hist_none": "Nothing yet.",
        "stat_started": "Timers (7 days)", "stat_executed": "Executed", "stat_cancelled": "Cancelled",
        "stat_typical": "Usually ends around",
        "ev_start": "Started {action} timer ({dur})", "ev_cancel": "Cancelled {action} timer",
        "ev_execute": "{action} done", "ev_extend": "Extended by {dur}", "ev_pause": "Paused",
        "ev_resume": "Resumed", "ev_missed": "Missed (PC was off or asleep)",
        "ev_watch_start": "Started watching {app}", "ev_watch_done": "{app} finished",
        "ev_schedule_add": "Schedule added", "ev_screenshot": "Screenshot sent",
        "ev_screenshot_setting": "Screenshot setting changed",
        # settings page
        "settings_title": "Settings", "set_general": "General", "language": "Language",
        "start_windows": "Start with Windows (hidden in the tray)",
        "warn_label": "Warn me before the action (minutes)", "save": "Save", "saved": "Saved",
        "set_telegram": "Telegram", "tg_setup": "Telegram setup",
        "tg_off": "Telegram is not set up.", "tg_on": "Connected {name}", "tg_connecting": "Connecting...",
        "shot_enable": "Allow /screenshot from Telegram",
        "shot_note": "Anyone who gets into your Telegram account could see your screen, so this is off by default. Every screenshot shows a notification on the PC and is written to the history.",
        "set_admin": "Administrator options", "net_enable": "Measure network use per app",
        "net_note": "Needs Administrator. Sees TCP traffic only (not UDP/QUIC). If it does not work, disk and CPU are still used.",
        "admin_yes": "Sleepify is running as Administrator.", "admin_no": "Sleepify is not running as Administrator.",
        "restart_admin": "Restart as Administrator",
        "hib_on": "Hibernate is turned on in Windows.", "hib_off": "Hibernate is turned off in Windows.",
        "hib_unknown": "Could not check Hibernate.", "hib_enable": "Turn on Hibernate (asks for permission)",
        "set_updates": "Updates", "upd_enable": "Check for new versions", "upd_repo": "GitHub repo",
        "upd_check": "Check now", "upd_version": "Version {v}", "upd_checking": "Checking...",
        "upd_available": "New version {v} is available.", "upd_latest": "You have the latest version ({v}).",
        "upd_no_repo": "Type the GitHub repo (owner/name) first.", "upd_badge": "Update {v} available",
        "set_support": "Help", "copy_diag": "Copy diagnostic info", "open_data": "Open the settings folder",
        "diag_copied": "Copied. Paste it where you ask for help.",
        "tg_connecting_short": "connecting",
        "side_tg_off": "○ Telegram off", "side_tg_on": "● Telegram connected", "side_tg_connecting": "● Telegram connecting",
        # wizard
        "wz_back": "Back", "wz_next": "Next", "wz_finish": "Finish",
        "wz_welcome": "Welcome to Sleepify",
        "wz_intro": "Control your PC's timer from your phone, through your own private Telegram bot. It takes about two minutes and you do it once.",
        "wz_device": "Name of this PC (shown in the messages)", "wz_need_name": "Please type a name for this PC.",
        "wz_already": "Telegram is already set up on this PC.", "wz_keep": "Save (keep my Telegram link)",
        "wz_change": "Change bot / link again", "wz_setup": "Set up Telegram", "wz_skip": "Skip - use Sleepify without Telegram",
        "wz_s2_title": "Step 1 of 2 - create your bot",
        "wz_s2_steps": "1. Open BotFather in Telegram (button below).\n2. Send it /newbot and answer its questions. The username must end with bot.\n3. BotFather replies with a token. Copy it and paste it here.",
        "wz_open_botfather": "Open BotFather in Telegram", "wz_paste_token": "Paste the token here",
        "wz_show_token": "Show the token", "wz_check_token": "Check the token",
        "wz_token_private": "Keep the token private: anyone who has it can control your bot.",
        "wz_bad_format": "That doesn't look like a bot token. It looks like 123456789:ABC...",
        "wz_checking": "Checking with Telegram...", "wz_invalid_token": "Telegram says this token is not valid.",
        "wz_tg_error": "Telegram answered with an error ({code}).", "wz_no_internet": "Could not reach Telegram. Check your internet connection.",
        "wz_bot_ok": "✓ Your bot is @{name}",
        "wz_s3_title": "Step 2 of 2 - link your Telegram",
        "wz_s3_intro": "Press the button, then press START in Telegram. Sleepify will notice by itself.",
        "wz_open_bot": "Open my bot in Telegram",
        "wz_s3_manual": "If the button doesn't work, open your bot yourself and send it this message:",
        "wz_waiting": "Waiting for you in Telegram...", "wz_new_code": "Make a new code",
        "wz_linked": "✓ Linked{who}", "wz_retrying": "Can't reach Telegram yet, retrying...",
        "wz_done_title": "All set!",
        "wz_done_body": "{name} is linked to @{bot}.\n\nWhen you press Finish, a message with the list of commands arrives in Telegram. Try /status.\n\nSleepify keeps running in the tray, near the clock.",
        "wz_multi": "Using more than one PC? Create one bot per PC (a new bot takes a minute) and give each PC a different name. Then you control each one from its own chat.",
    },
    "ar": {
        "act_shutdown": "إغلاق", "act_restart": "إعادة تشغيل", "act_hibernate": "Hibernate",
        "act_sleep": "سكون", "act_lock": "قفل", "act_display": "طفي الشاشة",
        "err_zero": "الوقت لازم يكون أكبر من صفر.",
        "err_max": "أقصى مدة 24 ساعة.",
        "err_denied": "ويندوز رفض الأمر.",
        "err_none": "مفيش مؤقت شغال.",
        "err_resched": "معرفتش أعيد جدولة المؤقت فاتلغى.",
        "err_no_hib": "الـ Hibernate مقفول على الجهاز ده. شغّله من الإعدادات، أو افتح Command Prompt كـ Administrator واكتب: powercfg /h on",
        "err_late": "المؤقت قرّب يخلص، فات وقت الإيقاف المؤقت.",
        "err_not_paused": "المؤقت مش موقوف.",
        "err_numbers": "اكتب أرقام صحيحة بس.",
        "err_time": "اكتب الوقت كده: 03:30 (أو 3:30pm).",
        "err_warn": "اكتب رقم بين 1 و180.",
        "err_autostart": "معرفتش أغيّر إعداد التشغيل مع ويندوز.",
        "err_no_rule": "اختار طريقة واحدة على الأقل نعرف بيها إن البرنامج خلص.",
        "err_admin": "معرفتش أعيد التشغيل كمسؤول.",
        "btn_extend": "زيادة {mins} دقايق", "btn_cancel": "إلغاء", "btn_pause": "إيقاف مؤقت", "btn_resume": "استكمال",
        "btn_stopwatch": "إيقاف المراقبة",
        "help": (
            "🤖 Sleepify - أوامر التحكم:\n\n"
            "/status - الوقت المتبقي\n"
            "/shutdown 1h30m - مؤقت إغلاق\n"
            "/restart 20m - مؤقت إعادة تشغيل\n"
            "/hibernate 45m - مؤقت Hibernate\n"
            "/sleep 30m - مؤقت سكون\n"
            "/lock [30m] - قفل الجهاز (دلوقتي أو بعد وقت)\n"
            "/extend 10m - تمديد المؤقت (الافتراضي 10 دقايق)\n"
            "/pause و /resume - إيقاف المؤقت واستكماله\n"
            "/at 03:30 [الإجراء] - تنفيذ في ساعة معينة\n"
            "/watch - إيه اللي بيراقبه Sleepify\n"
            "/screenshot - صورة للشاشة (لو متفعّلة)\n"
            "/stats - آخر 7 أيام\n"
            "/cancel - إلغاء المؤقت\n\n"
            "المدة: h = ساعات، m = دقايق، s = ثواني. مثال: 1h30m أو 45m أو 45m30s. رقم لوحده يعني دقايق."),
        "cmd_status": "الوقت المتبقي", "cmd_shutdown": "مؤقت إغلاق، مثال: /shutdown 1h30m",
        "cmd_restart": "مؤقت إعادة تشغيل", "cmd_hibernate": "مؤقت Hibernate، مثال: /hibernate 45m",
        "cmd_sleep": "مؤقت سكون", "cmd_lock": "قفل الجهاز", "cmd_extend": "تمديد المؤقت، مثال: /extend 10m",
        "cmd_cancel": "إلغاء المؤقت", "cmd_pause": "إيقاف المؤقت مؤقتًا", "cmd_resume": "استكمال المؤقت",
        "cmd_at": "تنفيذ في ساعة معينة، مثال: /at 03:30", "cmd_screenshot": "صورة لشاشة الجهاز",
        "cmd_stats": "إحصائيات آخر 7 أيام", "cmd_watch": "إيه اللي بيتراقب", "cmd_help": "عرض الأوامر",
        "status_none": "🔴 مفيش مؤقت شغال دلوقتي.",
        "status_running": "🟢 مؤقت شغال\nالإجراء: {action}\nباقي: {left}\nهيتنفذ الساعة: {at}",
        "status_paused": "⏸️ المؤقت موقوف\nالإجراء: {action}\nباقي: {left}",
        "bad_duration": "❌ اكتب المدة صح، مثال: /{cmd} 1h30m أو /{cmd} 45m",
        "bad_duration_extend": "❌ اكتب المدة صح، مثال: /extend 10m",
        "started": "✅ تمام، المؤقت اشتغل: {action} بعد {dur}\nالساعة: {at}",
        "replaced": "(المؤقت القديم اتبدل)",
        "app_run_note": "⚠️ سيب Sleepify شغال في الـ Tray، لو اتقفل المؤقت ده بيتلغي.",
        "extended": "⏰ اتمدد {dur}. باقي {left}، هيتنفذ الساعة {at}",
        "cancelled": "✅ المؤقت اتلغى.", "cancel_none": "ℹ️ مفيش مؤقت شغال عشان أكنسله.",
        "paused_ok": "⏸️ اتوقف المؤقت وباقي {left}.", "resumed_ok": "▶️ اتكمل المؤقت. باقي {left}، هيتنفذ الساعة {at}",
        "lock_now": "🔒 الجهاز اتقفل.",
        "unknown_cmd": "مش فاهم الأمر ده 🤔 اكتب /help",
        "warn_msg": "⚠️ باقي {mins} دقيقة وبعدها: {action}. احفظ شغلك! 💾",
        "final": "🔔 {action} بيبدأ دلوقتي!",
        "cancelled_pc": "✅ المؤقت اتلغى من الجهاز.",
        "hib_failed": "❌ الـ Hibernate فشل. اتأكد إنه مفعّل في الجهاز (powercfg /h on).",
        "act_failed": "❌ {action} فشل.",
        "exit_app_timer": "⚠️ Sleepify اتقفل، فالمؤقت اتلغى.",
        "linked": "✅ اتربط! الشات ده بقى بيتحكم في الجهاز ده.\n\n",
        "at_ok": "✅ اتجدول {action} الساعة {time} ({date}).",
        "at_bad": "❌ اكتبها كده: /at 03:30 أو /at 3:30pm hibernate",
        "schedules_none": "مفيش جداول.", "schedule_line": "• {time}  {action}  ({days})",
        "screenshot_off": "📸 لقطة الشاشة مقفولة. فعّلها من Sleepify ← الإعدادات.",
        "screenshot_wait": "📸 بجيب لقطة الشاشة...",
        "screenshot_wait_more": "⏳ استنى كام ثانية بين كل لقطة والتانية.",
        "screenshot_fail": "❌ معرفتش أصوّر الشاشة (الشاشة عليها قفل؟).",
        "screenshot_caption": "لقطة الشاشة",
        "stats_text": "📊 آخر {n} أيام\nمؤقتات بدأت: {started}\nاتنفذت: {executed}\nاتلغت: {cancelled}\nغالبًا بتخلص حوالي: {typical}",
        "cb_expired": "الزرار ده قديم.",
        "watch_none": "👁️ مفيش حاجة بتتراقب.",
        "watch_status": "👁️ بيراقب {app}\nالمعالج {cpu}%  |  القرص {io} MB/s{net}{idle}",
        "watch_idle_in": "\nخامل: هيتعتبر خلص بعد حوالي {mins} دقيقة",
        "watch_started": "👁️ بيراقب {app}. لما يخلص: {action}.",
        "watch_stopped": "✅ وقفت المراقبة.",
        "watch_done": "✅ {app} خلص ({reason}). {action} بعد {secs} ثانية.",
        "watch_timeout": "⏱️ بطلت أراقب {app} بعد {hours} ساعة. الجهاز فضل شغال.",
        "reason_closed": "اتقفل", "reason_idle": "بقى خامل",
        "toast_still_title": "Sleepify لسه شغال", "toast_still_body": "هتلاقيه جنب الساعة. كليك يمين على الأيقونة للخيارات.",
        "toast_timer_lost": "المؤقت اللي فات اتلغى لأن Sleepify اتقفل.",
        "toast_shot_sent": "اتبعتت لقطة شاشة على تليجرام.",
        "toast_watch_done": "{app} خلص. التنفيذ بعد {secs} ثانية.",
        "toast_watch_timeout": "وقفت مراقبة {app}: استنيت كتير.",
        "tray_show": "إظهار Sleepify", "tray_cancel": "إلغاء المؤقت", "tray_exit": "خروج",
        "nav_home": "المؤقت", "nav_watch": "مراقبة برنامج", "nav_schedule": "الجدول", "nav_history": "السجل",
        "nav_settings": "الإعدادات",
        "home_title": "المؤقت", "new_timer": "مؤقت جديد", "custom_time": "وقت مخصص",
        "hours": "ساعات", "minutes": "دقايق", "seconds": "ثواني", "start_timer": "ابدأ المؤقت",
        "keep_awake": "خلّي الجهاز صاحي أثناء الانتظار",
        "keep_on": "● الجهاز متثبّت صاحي",
        "hint_windows": "ويندوز هو اللي بيعد، فهيتنفذ حتى لو قفلت Sleepify.",
        "hint_app": "Sleepify هو اللي بينفذ ده، فسيبه في الـ Tray. الخروج بيلغيه.",
        "state_running": "شغال", "state_paused": "موقوف", "state_ready": "جاهز", "state_watching": "بيراقب",
        "action_at": "{action} الساعة {at}", "pick_time": "اختار وقت وابدأ", "watching_app": "بيراقب {app}",
        "next_sched": "الجدول الجاي", "no_sched": "مفيش جدول", "sched_in": "{action} الساعة {time}، بعد {left}",
        "tile_watch": "المراقبة", "tile_none": "مفيش",
        "confirm_replace": "فيه مؤقت شغال. أبدّله؟",
        "ask_enable_hib": "الـ Hibernate مقفول في ويندوز. أشغّله دلوقتي؟ (ويندوز هيطلب إذن.)",
        "hib_manual": "معرفتش أطلب الإذن. افتح Command Prompt كـ Administrator واكتب: powercfg /h on",
        "confirm_admin_restart": "فيه مؤقت بينفذه Sleepify نفسه، وإعادة التشغيل هتلغيه. أكمل؟",
        "confirm_exit_app": "فيه مؤقت بينفذه Sleepify.\nلو خرجت هيتلغي.\n\nتخرج برضو؟",
        "confirm_exit_win": "فيه مؤقت شغال.\nويندوز هيكمله في ميعاده حتى بعد ما تخرج.\n\nتخرج برضو؟",
        "watch_title": "مراقبة برنامج",
        "watch_sub": "اختار مثبّت أو لانشر ألعاب أو أي برنامج. Sleepify بيخلّي الجهاز صاحي، ولما البرنامج يخلص بينفذ الإجراء اللي تختاره.",
        "choose_app": "اختار البرنامج", "refresh": "تحديث", "show_background": "إظهار برامج الخلفية",
        "live_title": "النشاط دلوقتي", "no_app_selected": "اختار برنامج من القايمة.",
        "no_apps": "مفيش برامج.", "app_not_running": "{app} مش شغال",
        "cpu": "المعالج", "disk": "القرص", "net": "النت",
        "status_busy": "مشغول: لسه شغال.", "status_idle_in": "خامل. هيتعتبر خلص بعد {left}",
        "status_preview": "معاينة بس. دوس ابدأ المراقبة.",
        "rules_title": "إمتى نعتبره خلص؟", "rule_close": "لما البرنامج يتقفل",
        "rule_idle": "لما يبقى خامل لمدة", "min_unit": "دقايق",
        "idle_means": "خامل يعني إن كل ده أقل من:", "rule_cpu": "المعالج", "rule_disk": "القرص",
        "rule_net": "النت", "pct_unit": "%", "mbs_unit": "MB/s", "kbs_unit": "KB/s",
        "net_needs_admin": "النت لكل برنامج محتاج Administrator. فعّله من الإعدادات.",
        "then_do": "بعدها نفّذ:", "grace_label": "بعد", "sec_unit": "ثانية",
        "max_label": "بطّل بعد", "hour_unit": "ساعة (0 = أبدًا)",
        "shot_on_finish": "ابعت لقطة شاشة على تليجرام لما يخلص",
        "start_watch": "ابدأ المراقبة", "stop_watch": "إيقاف المراقبة", "pick_app_first": "اختار برنامج الأول.",
        "sched_title": "الجدول", "sched_sub": "نفّذ حاجة في ساعة معينة، مرة واحدة أو في أيام تختارها.",
        "sched_add": "إضافة جدول", "sched_time": "الساعة", "sched_add_btn": "إضافة",
        "sched_hint": "من غير أيام = مرة واحدة في أقرب ميعاد. هيظهر تحذير قبل التنفيذ.",
        "sched_list": "جداولك", "sched_none": "مفيش جداول لسه.", "sched_once": "مرة واحدة ({date})",
        "delete": "حذف",
        "day0": "إثن", "day1": "ثلا", "day2": "أرب", "day3": "خمي", "day4": "جمع", "day5": "سبت", "day6": "أحد",
        "hist_title": "السجل", "hist_sub": "اللي عمله Sleepify على الجهاز ده.", "hist_recent": "آخر الأحداث",
        "hist_none": "مفيش حاجة لسه.",
        "stat_started": "المؤقتات (7 أيام)", "stat_executed": "اتنفذ", "stat_cancelled": "اتلغى",
        "stat_typical": "غالبًا بيخلص حوالي",
        "ev_start": "بدأ مؤقت {action} ({dur})", "ev_cancel": "اتلغى مؤقت {action}",
        "ev_execute": "تم {action}", "ev_extend": "اتمدد {dur}", "ev_pause": "اتوقف",
        "ev_resume": "اتكمل", "ev_missed": "فات (الجهاز كان مطفي أو نايم)",
        "ev_watch_start": "بدأت مراقبة {app}", "ev_watch_done": "{app} خلص",
        "ev_schedule_add": "اتضاف جدول", "ev_screenshot": "اتبعتت لقطة شاشة",
        "ev_screenshot_setting": "اتغيّر إعداد لقطة الشاشة",
        "settings_title": "الإعدادات", "set_general": "عام", "language": "اللغة",
        "start_windows": "التشغيل مع ويندوز (مخفي في الـ Tray)",
        "warn_label": "نبّهني قبل التنفيذ (دقايق)", "save": "حفظ", "saved": "اتحفظ",
        "set_telegram": "تليجرام", "tg_setup": "إعداد تليجرام",
        "tg_off": "تليجرام مش متظبّط.", "tg_on": "متصل {name}", "tg_connecting": "بيتصل...",
        "shot_enable": "اسمح بأمر /screenshot من تليجرام",
        "shot_note": "أي حد يدخل حساب تليجرام بتاعك يقدر يشوف شاشتك، عشان كده مقفولة افتراضيًا. كل لقطة بيظهر عليها إشعار على الجهاز وبتتسجل في السجل.",
        "set_admin": "خيارات المسؤول", "net_enable": "قياس استهلاك النت لكل برنامج",
        "net_note": "محتاج Administrator. بيشوف TCP بس (مش UDP/QUIC). لو ماشتغلش، القرص والمعالج بيفضلوا شغالين.",
        "admin_yes": "Sleepify شغال كمسؤول.", "admin_no": "Sleepify مش شغال كمسؤول.",
        "restart_admin": "إعادة التشغيل كمسؤول",
        "hib_on": "الـ Hibernate مفعّل في ويندوز.", "hib_off": "الـ Hibernate مقفول في ويندوز.",
        "hib_unknown": "معرفتش أتأكد من الـ Hibernate.", "hib_enable": "تشغيل الـ Hibernate (هيطلب إذن)",
        "set_updates": "التحديثات", "upd_enable": "افحص النسخ الجديدة", "upd_repo": "ريبو GitHub",
        "upd_check": "افحص دلوقتي", "upd_version": "النسخة {v}", "upd_checking": "بيفحص...",
        "upd_available": "فيه نسخة جديدة {v}.", "upd_latest": "معاك آخر نسخة ({v}).",
        "upd_no_repo": "اكتب ريبو GitHub (owner/name) الأول.", "upd_badge": "تحديث {v} متاح",
        "set_support": "مساعدة", "copy_diag": "نسخ معلومات التشخيص", "open_data": "فتح فولدر الإعدادات",
        "diag_copied": "اتنسخت. الصقها وإنت بتطلب مساعدة.",
        "tg_connecting_short": "بيتصل",
        "side_tg_off": "○ تليجرام مقفول", "side_tg_on": "● تليجرام متصل", "side_tg_connecting": "● تليجرام بيتصل",
        "wz_back": "رجوع", "wz_next": "التالي", "wz_finish": "إنهاء",
        "wz_welcome": "أهلًا بيك في Sleepify",
        "wz_intro": "اتحكم في مؤقت جهازك من تليفونك عن طريق بوت تليجرام خاص بيك. بياخد حوالي دقيقتين وبتعمله مرة واحدة.",
        "wz_device": "اسم الجهاز ده (بيظهر في الرسايل)", "wz_need_name": "اكتب اسم للجهاز.",
        "wz_already": "تليجرام متظبّط على الجهاز ده.", "wz_keep": "حفظ (مع إبقاء ربط تليجرام)",
        "wz_change": "تغيير البوت / ربط من جديد", "wz_setup": "إعداد تليجرام", "wz_skip": "تخطي - استخدم Sleepify من غير تليجرام",
        "wz_s2_title": "الخطوة 1 من 2 - اعمل البوت بتاعك",
        "wz_s2_steps": "1. افتح BotFather في تليجرام (الزرار تحت).\n2. ابعتله /newbot وجاوب أسئلته. لازم اسم المستخدم ينتهي بـ bot.\n3. BotFather هيرد بتوكن. انسخه والصقه هنا.",
        "wz_open_botfather": "فتح BotFather في تليجرام", "wz_paste_token": "الصق التوكن هنا",
        "wz_show_token": "إظهار التوكن", "wz_check_token": "افحص التوكن",
        "wz_token_private": "خلي التوكن سري: أي حد معاه يقدر يتحكم في البوت بتاعك.",
        "wz_bad_format": "ده مش شكل توكن بوت. شكله زي 123456789:ABC...",
        "wz_checking": "بسأل تليجرام...", "wz_invalid_token": "تليجرام بيقول إن التوكن ده مش صحيح.",
        "wz_tg_error": "تليجرام رد بخطأ ({code}).", "wz_no_internet": "معرفتش أوصل لتليجرام. اتأكد من النت.",
        "wz_bot_ok": "✓ البوت بتاعك هو @{name}",
        "wz_s3_title": "الخطوة 2 من 2 - اربط حساب تليجرام",
        "wz_s3_intro": "دوس الزرار، وبعدين دوس START في تليجرام. Sleepify هيلاحظ لوحده.",
        "wz_open_bot": "فتح البوت بتاعي في تليجرام",
        "wz_s3_manual": "لو الزرار ماشتغلش، افتح البوت بنفسك وابعتله الرسالة دي:",
        "wz_waiting": "مستنيك في تليجرام...", "wz_new_code": "كود جديد",
        "wz_linked": "✓ اتربط{who}", "wz_retrying": "لسه مش قادر أوصل لتليجرام، بحاول تاني...",
        "wz_done_title": "كله جاهز!",
        "wz_done_body": "{name} اتربط بالبوت @{bot}.\n\nأول ما تدوس إنهاء هتوصلك رسالة على تليجرام فيها الأوامر. جرّب /status.\n\nSleepify هيفضل شغال في الـ Tray جنب الساعة.",
        "wz_multi": "عندك أكتر من جهاز؟ اعمل بوت لكل جهاز (بيستغرق دقيقة) وسمّي كل جهاز اسم مختلف. وبعدين تتحكم في كل واحد من الشات بتاعه.",
    },
}

LANG = "en"


def set_language(lang):
    global LANG
    LANG = lang if lang in STR else "en"


def get_language():
    return LANG


def is_rtl():
    return LANG == "ar"


def t(key, lang=None, **kw):
    table = STR.get(lang or LANG, STR["en"])
    text = table.get(key) or STR["en"][key]
    return text.format(**kw) if kw else text


def action_label(action, lang=None):
    return t("act_" + action, lang)


def fmt_clock(ts, lang=None):
    """3:21 PM / ٣:٢١ م  (with 'tomorrow' when it is on another day)."""
    lang = lang or LANG
    dt = datetime.fromtimestamp(ts)
    h12 = dt.hour % 12 or 12
    suffix = ("ص" if dt.hour < 12 else "م") if lang == "ar" else ("AM" if dt.hour < 12 else "PM")
    text = f"{h12}:{dt.minute:02d} {suffix}"
    days = (dt.date() - datetime.now().date()).days
    if days == 1:
        text += " (بكرة)" if lang == "ar" else " (tomorrow)"
    elif days > 1:
        text += f" (+{days})"
    return text
