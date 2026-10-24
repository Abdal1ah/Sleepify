# -*- coding: utf-8 -*-
"""Icons (made from assets/logo.jpg, or drawn when there is no logo) and small pictures for the window."""
import math
import os

from PIL import Image, ImageChops, ImageDraw

from . import common as C

RES = Image.Resampling.LANCZOS
_logo_warned = False


def find_logo():
    """logo.jpg/.png in your settings folder, then the bundled assets, then the old icons folder."""
    old = os.path.join(C.ROOT_DIR, "icons")
    for d in (C.ICON_DIR, C.resource_path("assets"), old):
        for name in ("logo.jpg", "logo.jpeg", "logo.png"):
            path = os.path.join(d, name)
            if os.path.exists(path):
                return path
    try:  # v0.x: any .jpg dropped into the old icons folder
        for name in sorted(os.listdir(old)):
            if name.lower().endswith((".jpg", ".jpeg")):
                return os.path.join(old, name)
    except OSError:
        pass
    return None


def rounded(img, radius_frac=0.22):
    size = img.size[0]
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, size * 4 - 1, size * 4 - 1), radius=int(size * 4 * radius_frac), fill=255)
    out = img.convert("RGBA")
    out.putalpha(big.resize((size, size), RES))
    return out


def _draw_fallback(size):
    s = size * 4
    bg, green = (23, 27, 80, 255), (125, 255, 90, 255)
    img = Image.new("RGBA", (s, s), bg)
    d = ImageDraw.Draw(img)
    d.ellipse((s * 0.14, s * 0.22, s * 0.86, s * 0.94), fill=green)          # crescent moon
    d.ellipse((s * 0.30, s * 0.10, s * 1.00, s * 0.80), fill=bg)
    cx, cy, r, w = s * 0.46, s * 0.50, s * 0.17, int(s * 0.055)               # power symbol
    d.arc((cx - r, cy - r, cx + r, cy + r), start=300, end=240, fill=green, width=w)
    d.line((cx, cy - r * 1.25, cx, cy - r * 0.1), fill=green, width=w)
    for y in (cy - r * 1.25, cy - r * 0.1):
        d.ellipse((cx - w / 2, y - w / 2, cx + w / 2, y + w / 2), fill=green)
    return img.resize((size, size), RES)


def make_base_icon(size):
    """Square icon (symbol only, no text) at the requested size."""
    global _logo_warned
    try:
        logo = find_logo()
        if logo is None:
            raise FileNotFoundError("no logo image found")
        im = Image.open(logo).convert("RGB")
        r, g, b = im.split()
        m = ImageChops.darker(
            ImageChops.darker(
                ImageChops.subtract(g, r).point(lambda v: 255 if v > 60 else 0),
                ImageChops.subtract(g, b).point(lambda v: 255 if v > 60 else 0)),
            g.point(lambda v: 255 if v > 150 else 0))
        box = m.getbbox()
        if box:
            box = (box[0], box[1] - int(0.15 * (box[3] - box[1])), box[2], box[3])   # room for the stars
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            half = max(box[2] - box[0], box[3] - box[1]) / 2 * 1.1
            half = min(half, cx, cy, im.size[0] - cx, im.size[1] - cy)
            crop = im.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))
            return crop.resize((size, size), RES).convert("RGBA")
    except Exception as e:
        if not _logo_warned:
            _logo_warned = True
            C.log_error(f"logo image not used, drawing a default icon instead: {e}")
    return _draw_fallback(size)


def to_red(img):
    """Shift the green parts of the icon to red (the blue/purple background stays)."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    h, s, v = rgba.convert("RGB").convert("HSV").split()
    table = [(int((i - 85) * 0.25)) % 256 if 35 <= i <= 125 else i for i in range(256)]
    out = Image.merge("HSV", (h.point(table), s, v)).convert("RGB")
    out.putalpha(alpha)
    return out


def build_icons():
    """Returns (icon_on, icon_off) as 64x64 images; writes app.ico / bot.png when the logo changes."""
    try:
        os.makedirs(C.ICON_DIR, exist_ok=True)
        logo = find_logo()
        stamp = "none" if logo is None else f"{os.path.basename(logo)}|{os.path.getsize(logo)}|{int(os.path.getmtime(logo))}"
        stamp_file = os.path.join(C.ICON_DIR, "logo.stamp")
        try:
            with open(stamp_file, encoding="utf-8") as f:
                old_stamp = f.read().strip()
        except OSError:
            old_stamp = ""
        changed = stamp != old_stamp
        if changed or not os.path.exists(C.ICO_FILE):
            rounded(make_base_icon(256)).save(
                C.ICO_FILE, format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        if changed or not os.path.exists(C.BOT_PNG):
            make_base_icon(512).convert("RGB").save(C.BOT_PNG)
        if changed:
            with open(stamp_file, "w", encoding="utf-8") as f:
                f.write(stamp)
    except Exception as e:
        C.log_error(f"could not write icon files: {e}")
    base = rounded(make_base_icon(256))
    return base.resize((64, 64), RES), to_red(base).resize((64, 64), RES)


# ---------------------------------------------------------------- pictures drawn for the window
def _hex(color, alpha=255):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def ring_image(size, fraction, color, track="#262d63", width_frac=0.07, dashed=False):
    """Smooth progress ring (supersampled). fraction 0..1 of the circle is filled, starting at the top."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = int(s * width_frac)
    pad = w // 2 + int(s * 0.01)
    box = (pad, pad, s - pad, s - pad)
    d.ellipse(box, outline=_hex(track), width=w)
    fraction = max(0.0, min(1.0, fraction))
    if fraction > 0:
        if fraction >= 0.999:
            d.ellipse(box, outline=_hex(color), width=w)
        else:
            d.arc(box, start=-90, end=-90 + 360 * fraction, fill=_hex(color), width=w)
            r = (s - 2 * pad) / 2
            cx = cy = s / 2
            for ang in (-90, -90 + 360 * fraction):           # round caps
                x = cx + (r - w / 2 + w / 2) * math.cos(math.radians(ang))
                y = cy + (r - w / 2 + w / 2) * math.sin(math.radians(ang))
                d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=_hex(color))
    return img.resize((size, size), RES)


def sparkline_image(values, width, height, color, limit=None, bg="#151a3d", limit_color="#ffb84d"):
    """Tiny activity graph. `limit` draws a dashed horizontal line (the idle limit)."""
    sc = 3
    w, h = width * sc, height * sc
    img = Image.new("RGBA", (w, h), _hex(bg))
    d = ImageDraw.Draw(img)
    vals = [max(0.0, float(v)) for v in values]
    top = max(vals + [limit or 0, 1e-9]) * 1.15
    if limit:
        y = h - 4 * sc - (h - 8 * sc) * (limit / top)
        for x in range(0, w, 10 * sc):
            d.line((x, y, x + 5 * sc, y), fill=_hex(limit_color), width=max(1, sc // 2 + 1))
    if len(vals) >= 2:
        pts = [(i * (w - 1) / (len(vals) - 1), h - 4 * sc - (h - 8 * sc) * (v / top)) for i, v in enumerate(vals)]
        area = pts + [(w - 1, h), (0, h)]
        fill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(fill).polygon(area, fill=_hex(color, 50))
        img.alpha_composite(fill)
        d = ImageDraw.Draw(img)
        d.line(pts, fill=_hex(color), width=2 * sc, joint="curve")
    return img.resize((width, height), RES)
