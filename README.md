# Sleepify 🌙

**A PC timer for Windows that you can also control from your phone.**
Shut down, restart, hibernate, sleep or lock your PC after a time, at a clock time, or **when an installer or download has finished**. Keeps the PC awake while it waits, warns you first, and works in **English and Arabic**. No server, no account, no ads.

[English](#english) · [العربية](#العربية)

---

## English

### What it does
| | |
|---|---|
| ⏱️ **Timers** | Shutdown, Restart, Hibernate, Sleep, Lock or Screen off, after a time. Quick buttons (15 m / 30 m / 1 h / 2 h) or your own time. Pause, resume, +10 min. |
| 👁️ **Watch an app** | Pick an installer, game launcher or any program. Sleepify keeps the PC awake and runs your action when the program **closes** or has been **idle** (low CPU, low disk, optionally low network). You can see its activity live. |
| 🔋 **Keep awake** | While a timer runs or an app is watched, Windows will not go to sleep (the screen can still turn off). Much lighter than looping a video. |
| 🌙 **Schedule** | At a clock time, once or on chosen days (e.g. every night at 3:30). A warning appears first. |
| 📲 **Telegram** | Control everything from your phone through **your own private bot**: timers, `/status`, pause, buttons on the warning, and an optional `/screenshot`. |
| 📊 **History** | What happened and when, with simple statistics. |
| 🌍 **English / Arabic** | The whole window and the Telegram messages. |
| 🟢🔴 **Tray icon** | Near the clock: green while something is running, red when idle. |

### Install
1. Download **`SleepifySetup-x.y.z.exe`** from the [Releases](../../releases) page.
2. Run it. Windows may show *"Windows protected your PC"* because the file is new and not code-signed: click **More info → Run anyway**.
3. Choose where to install, and whether you want a desktop shortcut and *Start with Windows*.
4. On the first launch a short **setup** asks for your language and helps you connect Telegram. You can skip Telegram and use Sleepify without it.

### Connect Telegram (once, about 2 minutes)
Everyone uses **their own bot**, so nobody else can control your PC.
1. In Telegram open **@BotFather** and send `/newbot` (the username must end with `bot`).
2. Paste the **token** it gives you into the Sleepify setup. Sleepify checks it for you.
3. Sleepify shows a **random code**. Press *Open my bot in Telegram* and press **Start** (or send `/start CODE`). Your account is linked automatically.

### Watch an app: how it decides it is finished
Windows does not let normal programs see network use per app, so Sleepify uses what it **can** see without Administrator rights: the **CPU** and **disk** activity of the program and of everything it started. A download or an installation keeps writing to the disk, so low disk + low CPU for several minutes means *finished*. You can see the live numbers and a graph, and set your own limits.
Optional, in *Settings → Administrator options*: measure **network use per app** (TCP only). You turn it on yourself and restart Sleepify as Administrator.

### Telegram commands
| Command | What it does |
|---|---|
| `/status` | Time left (with buttons: +10 / Pause / Cancel) |
| `/shutdown 1h30m` `/restart 20m` `/hibernate 45m` `/sleep 30m` | Timers |
| `/lock` or `/lock 30m` | Lock the PC now or after a time |
| `/extend 10m` `/pause` `/resume` `/cancel` | Control the running timer |
| `/at 03:30 [action]` | Do it at a clock time (e.g. `/at 3:30pm hibernate`) |
| `/watch` | What Sleepify is watching right now |
| `/screenshot` | A picture of the screen. **Off by default** (turn it on in Settings) |
| `/stats` | Your last 7 days |

Time format: `h` hours, `m` minutes, `s` seconds (`1h30m`, `45m`). A bare number means minutes.

### More than one PC
Telegram lets only one program listen to a bot, so create **one bot per PC** (a minute each) and give each PC a different name in the setup. You then control each PC from its own chat.

### Good to know
- The PC must be **on and awake** to receive commands. Telegram cannot wake a PC that is off or hibernating.
- **Shutdown** and **Restart** are counted by Windows itself, so they still happen if you exit Sleepify. **Hibernate, Sleep, Lock, Screen off** are run by Sleepify: keep it in the tray (the **X** only hides the window; use the tray icon → Exit to quit, which cancels those timers).
- Laptops: keep it plugged in and do not close the lid, closing the lid still puts the PC to sleep.
- Hibernate must be enabled in Windows. *Settings → Administrator options* can turn it on for you (Windows asks permission).

### Privacy and security
- There is **no Sleepify server**. Your PC talks directly to Telegram.
- Your bot token is stored in `%APPDATA%\Sleepify\config.json`. Never share it or commit it to Git. If it leaks, send `/revoke` to BotFather.
- Sleepify only obeys the **one Telegram account** you linked, ignores messages older than 2 minutes, and ignores old buttons.
- Screenshots are **off by default**. When on, every screenshot shows a notification on the PC and is written to the history. Anyone who gets into your Telegram account could ask for one, so keep Telegram two-step verification on.
- Settings, history (`history.jsonl`), the log (`log.txt`) and errors (`error.log`) are in `%APPDATA%\Sleepify`.

### Run from source
```bat
py -m pip install -r requirements.txt
py Sleepify.py
```
`py Sleepify.py --install` creates a desktop icon and *Start with Windows*; `--uninstall` removes them.

### Build the installer yourself
Needs [Inno Setup 6](https://jrsoftware.org/isdl.php). Run `build.bat`. It creates `dist\Sleepify\Sleepify.exe` and `installer\Output\SleepifySetup-x.y.z.exe`.
On GitHub, pushing a tag such as `v1.1.0` builds and publishes the installer automatically (`.github/workflows/build.yml`). Code signing is optional: see [docs/SIGNING.md](docs/SIGNING.md).

### Tests
```bat
py -m pip install pytest
py -m pytest -q tests
```

### Troubleshooting
| Problem | What to try |
|---|---|
| The tray icon is missing | Click the `^` arrow near the clock and drag it out |
| "Telegram: connecting..." for long | Check your internet; open `%APPDATA%\Sleepify\error.log` |
| The bot does not answer | Is the PC on and Sleepify running? The sidebar says *Telegram connected* when it is |
| Hibernate fails | Settings → Administrator options → *Turn on Hibernate* |
| Something else | Settings → Help → *Copy diagnostic info*, and paste it into an issue |

### License
[MIT](LICENSE). Made with ❤️ by Abdullah.

---

<div dir="rtl">

## العربية

### إيه اللي بيعمله
- ⏱️ **مؤقتات**: إغلاق، إعادة تشغيل، Hibernate، سكون، قفل، أو إطفاء الشاشة بعد وقت معين، مع إيقاف مؤقت واستكمال وتمديد.
- 👁️ **مراقبة برنامج**: اختار مثبّت أو لانشر ألعاب أو أي برنامج، وSleepify يخلّي الجهاز صاحي وينفذ الإجراء لما البرنامج **يتقفل** أو **يبقى خامل** (نشاط المعالج والقرص قليل). بتشوف النشاط لحظة بلحظة.
- 🔋 **إبقاء الجهاز صاحي** أثناء الانتظار، من غير فيديو بيستهلك الجهاز.
- 🌙 **جدول** في ساعة معينة، مرة واحدة أو في أيام تختارها، مع تحذير قبلها.
- 📲 **تحكم من تليجرام** عن طريق بوت خاص بيك، مع أزرار على رسالة التحذير و`/screenshot` اختياري.
- 📊 **سجل** وإحصائيات، والبرنامج كله **بالعربي والإنجليزي**.

### التثبيت
1. نزّل `SleepifySetup-x.y.z.exe` من صفحة [Releases](../../releases).
2. شغّله. لو ظهر تحذير *Windows protected your PC* اضغط **More info ثم Run anyway** (لأن الملف جديد وغير موقّع).
3. اختار مكان التثبيت وهل تريد أيقونة على سطح المكتب والتشغيل مع ويندوز.
4. أول مرة هتظهر نافذة إعداد: اختار لغتك واربط تليجرام (أو تخطّاها).

### ربط تليجرام (مرة واحدة)
كل شخص بيستخدم **بوت خاص بيه**. افتح **@BotFather** وابعت `/newbot`، والصق التوكن في نافذة الإعداد، وبعدين دوس *Open my bot* ثم **Start** (أو ابعت `/start CODE`)، فيتربط حسابك تلقائيًا.

### مراقبة برنامج: بيعرف إنه خلص إزاي
ويندوز مش بيسمح للبرامج العادية تشوف النت لكل برنامج لوحده، فSleepify بيعتمد على اللي يقدر يشوفه بدون صلاحيات مسؤول: نشاط **المعالج** و**القرص** للبرنامج وكل اللي شغّله. التحميل والتثبيت بيكتبوا على القرص باستمرار، فلو القرص والمعالج هادين لعدة دقائق يبقى خلص. وفي *الإعدادات ← خيارات المسؤول* تقدر تفعّل **قياس النت لكل برنامج** بنفسك.

### مهم أن تعرف
- الجهاز لازم يكون **شغال** عشان يستقبل الأوامر.
- **الإغلاق وإعادة التشغيل** بيعدهم ويندوز نفسه فبيحصلوا حتى لو قفلت Sleepify. أما **Hibernate والسكون والقفل وإطفاء الشاشة** فبينفذها Sleepify، فسيبه شغال بجانب الساعة.
- في اللابتوب: سيبه في الشاحن ومتقفلش الغطا.
- **لا يوجد خادم** خاص بـ Sleepify. التوكن محفوظ على جهازك ولا تشاركه. لقطة الشاشة **مقفولة افتراضيًا**.
- أكتر من جهاز: اعمل **بوت لكل جهاز**.

### الرخصة
[MIT](LICENSE).

</div>
