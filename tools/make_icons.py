"""Builds assets/app.ico (installer + exe icon) and assets/bot.png (picture for your Telegram bot)
from assets/logo.jpg.   Run from the repository folder:   py tools/make_icons.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SLEEPIFY_DATA_DIR", os.path.join(ROOT, "build", "_data"))   # keep AppData clean

from sleepify import icons  # noqa: E402

assets = os.path.join(ROOT, "assets")
os.makedirs(assets, exist_ok=True)
icons.rounded(icons.make_base_icon(256)).save(
    os.path.join(assets, "app.ico"), format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
icons.make_base_icon(512).convert("RGB").save(os.path.join(assets, "bot.png"))
print("Created assets/app.ico and assets/bot.png")
