# Changelog

## 1.1.0
- **Watch an app**: pick an installer / game launcher / any program; Sleepify keeps the PC awake and runs your action when the program closes or has been idle (CPU, disk, and optionally per-app network).
- **Keep awake** while a timer runs or an app is watched (the screen may still turn off).
- **More actions**: Shutdown, Restart, Hibernate, Sleep, Lock, Screen off.
- **Schedules**: at a clock time, once or on chosen days, with the usual warning.
- **Pause / resume** a timer.
- **History** page with statistics.
- **Telegram**: buttons on the warning (+10 min / Cancel), `/pause`, `/resume`, `/at`, `/watch`, `/stats`, `/restart`, `/sleep`, `/lock`, and an opt-in `/screenshot`.
- **New window design**, and the whole app in **English or Arabic**.
- Optional Administrator features: per-app network measurement, turning Hibernate on.
- Update check (GitHub releases), diagnostics copy button, code split into the `sleepify/` package.

## 1.0.0
- First public version: Shutdown / Hibernate timer, tray icon, warning, +10 min, quick buttons.
- Telegram remote control through your own bot, with a first-run setup that checks the token and links your account with a one-time code.
- Settings moved to `%APPDATA%\Sleepify` (an old `config.json` next to the script is imported once).
- Windows installer (Inno Setup) and automatic builds with GitHub Actions.
