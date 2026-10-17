# Sleepify 🌙

**A PC sleep timer for Windows that you can also control from your phone.**
Set a Shutdown or Hibernate timer, get a warning before it happens, and add or cancel time from Telegram, through your own private bot. No server, no account, no ads.

[English](#english) · [العربية](#العربية)

---

## English

### Features
- ⏱️ **Shutdown or Hibernate timer** (hours, minutes, seconds, or one-click 30 min / 1 h / 2 h)
- ⚠️ **Warning** before it happens (beep + notification, default 10 minutes, you can change it)
- ➕ **Extend** by 10 minutes with one click
- 📲 **Telegram remote control** from your phone: `/status`, `/shutdown`, `/hibernate`, `/extend`, `/cancel`
- 🟢🔴 **Tray icon** near the clock: green when a timer is running, red when not
- 🚀 Optional **start with Windows**, hidden in the tray
- 🇪🇬 Telegram messages in **English or Arabic**

### Install
1. Download **`SleepifySetup-x.y.z.exe`** from the [Releases](../../releases) page.
2. Run it. Windows may show *"Windows protected your PC"* because the file is new and not code-signed: click **More info → Run anyway**.
3. Choose where to install and whether you want a desktop shortcut and *Start with Windows*.
4. On the first launch, a short **setup** helps you connect Telegram (below). You can skip it and use Sleepify without Telegram.

### Connect Telegram (once, about 2 minutes)
Every person uses **their own bot**, so nobody else can control your PC.
1. In Telegram, open **@BotFather** and send `/newbot`. The username must end with `bot`.
2. Copy the **token** BotFather gives you and paste it in the Sleepify setup. It checks the token for you.
3. Sleepify shows a **random code**. Press *Open my bot in Telegram* and press **Start** (or send `/start CODE` to your bot). Sleepify links your account automatically.

Reopen the setup any time with the **Telegram setup** button.

### Commands
| Command | What it does |
|---|---|
| `/status` | Time left |
| `/shutdown 1h30m` | Shutdown timer |
| `/hibernate 45m` | Hibernate timer |
| `/extend 10m` | Add time (default 10 minutes) |
| `/cancel` | Cancel the timer |
| `/help` | List the commands |

Time format: `h` hours, `m` minutes, `s` seconds (`1h30m`, `45m`, `45m30s`). A bare number means minutes.

### More than one PC
Telegram lets only one program listen to a bot, so create **one bot per PC** (it takes a minute) and give each PC a different name in the setup. You then control each PC from its own chat.

### Good to know
- The PC must be **on and awake** to receive commands. Telegram cannot wake a PC that is off or hibernating.
- **Shutdown** is scheduled in Windows itself, so it still happens if you exit Sleepify.
- **Hibernate** is run by Sleepify, so keep it running in the tray. Choosing **Exit** cancels a Hibernate timer.
- Hibernate must be enabled in Windows. If it is not, open Command Prompt as Administrator and run `powercfg /h on`.
- Closing the window with **X** only hides it. Use the tray icon (right-click → Exit) to quit.

### Privacy and security
- There is **no Sleepify server**. Your PC talks directly to Telegram.
- Your bot token is stored on your PC in `%APPDATA%\Sleepify\config.json`. Never share it or commit it to Git. If it leaks, send `/revoke` to BotFather.
- Sleepify only obeys the **one Telegram account** you linked, and ignores messages older than 2 minutes.
- Settings, the usage log (`log.txt`) and errors (`error.log`) are all in `%APPDATA%\Sleepify`.

### Run from source
```bat
py -m pip install -r requirements.txt
py Sleepify.py
```
`py Sleepify.py --install` creates a desktop icon and *Start with Windows*; `--uninstall` removes them.

### Build the installer yourself
Needs [Inno Setup 6](https://jrsoftware.org/isdl.php). Then run `build.bat`. It creates `dist\Sleepify\Sleepify.exe` and `installer\Output\SleepifySetup-x.y.z.exe`.
On GitHub, pushing a tag such as `v1.0.0` builds and publishes the installer automatically (see `.github/workflows/build.yml`).

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
| The bot does not answer | Is the PC on? Is Sleepify running? The status line in the window says *connected* when it is |
| Hibernate fails | Run `powercfg /h on` as Administrator |

### License
[MIT](LICENSE). Made with ❤️ by Abdullah.

---

<div dir="rtl">

## العربية

### المميزات
- ⏱️ **مؤقت إغلاق أو Hibernate** (ساعات ودقائق وثوانٍ، أو أزرار جاهزة 30 دقيقة / ساعة / ساعتين)
- ⚠️ **تنبيه** قبل التنفيذ (صفارة وإشعار، الافتراضي 10 دقائق ويمكن تغييره)
- ➕ **تمديد** المؤقت 10 دقائق بضغطة واحدة
- 📲 **تحكم من الهاتف** عبر تليجرام: `/status` و`/shutdown` و`/hibernate` و`/extend` و`/cancel`
- 🟢🔴 **أيقونة بجانب الساعة**: خضراء أثناء عمل المؤقت وحمراء عند عدمه
- 🚀 **تشغيل مع ويندوز** اختياريًا، بشكل مخفي
- رسائل تليجرام بـ **العربية أو الإنجليزية**

### التثبيت
1. نزّل ملف **`SleepifySetup-x.y.z.exe`** من صفحة [Releases](../../releases).
2. شغّله. قد يظهر تحذير *Windows protected your PC* لأن الملف جديد وغير موقّع. اضغط **More info ثم Run anyway**.
3. اختر مكان التثبيت، وهل تريد أيقونة على سطح المكتب والتشغيل مع ويندوز.
4. عند أول تشغيل ستظهر نافذة **إعداد** قصيرة لربط تليجرام. يمكنك تخطيها واستخدام البرنامج بدون تليجرام.

### ربط تليجرام (مرة واحدة، حوالي دقيقتين)
كل شخص يستخدم **بوتًا خاصًا به**، فلا يستطيع أحد غيرك التحكم في جهازك.
1. افتح **@BotFather** في تليجرام وأرسل `/newbot`. يجب أن ينتهي اسم المستخدم بـ `bot`.
2. انسخ **التوكن** الذي يعطيه لك والصقه في نافذة الإعداد. سيتحقق منه البرنامج.
3. سيعرض Sleepify **كودًا عشوائيًا**. اضغط *Open my bot in Telegram* ثم **Start** (أو أرسل `/start CODE` لبوتك). سيربط البرنامج حسابك تلقائيًا.

### أكثر من جهاز
تليجرام يسمح لبرنامج واحد فقط بالاستماع إلى البوت، لذلك أنشئ **بوتًا لكل جهاز** (دقيقة واحدة) وأعطِ كل جهاز اسمًا مختلفًا في الإعداد، وتتحكم بكل جهاز من محادثته.

### مهم أن تعرف
- يجب أن يكون الجهاز **شغالًا** لاستقبال الأوامر. تليجرام لا يستطيع إيقاظ جهاز مطفأ أو في Hibernate.
- **الإغلاق** يُجدول داخل ويندوز نفسه، فيحدث حتى لو أغلقت Sleepify.
- **Hibernate** ينفذه Sleepify، لذا اتركه شغالًا بجانب الساعة. الخروج منه يلغي مؤقت Hibernate.
- يجب تفعيل Hibernate في ويندوز: افتح Command Prompt كمسؤول واكتب `powercfg /h on`.
- زر **X** يخفي النافذة فقط. للخروج: كليك يمين على الأيقونة ثم Exit.

### الخصوصية والأمان
- **لا يوجد خادم** خاص بـ Sleepify. جهازك يتصل بتليجرام مباشرة.
- التوكن محفوظ على جهازك في `%APPDATA%\Sleepify\config.json`. لا تشاركه ولا ترفعه على Git. إن تسرب أرسل `/revoke` إلى BotFather.
- البرنامج يطيع **حساب تليجرام الذي ربطته فقط**، ويتجاهل الرسائل الأقدم من دقيقتين.

### الرخصة
[MIT](LICENSE).

</div>
