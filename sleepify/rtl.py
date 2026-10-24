# -*- coding: utf-8 -*-
"""Arabic text for Tk.

Tk 8.6 draws text strictly left-to-right and does not join Arabic letters. So for Arabic screens we
(1) shape the letters with arabic-reshaper and (2) put the text runs in visual order ourselves.
`to_visual()` takes a normal (logical) Arabic string and returns the string to hand to a Tk label.
"""
try:
    import arabic_reshaper
except ImportError:                      # still works, just without joined letters
    arabic_reshaper = None

_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")


def _type(ch):
    """Simplified Unicode bidi classes: R (Arabic/Hebrew), L, EN (digit), AN (Arabic-Indic digit), CS, ES, ET, N."""
    o = ord(ch)
    if 0x0660 <= o <= 0x0669:
        return "AN"
    if 0x0590 <= o <= 0x08FF or 0xFB1D <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return "R"
    if ch in "0123456789":
        return "EN"
    if ch.isalpha():
        return "L"
    if ch in ":,./":
        return "CS"
    if ch in "+-":
        return "ES"
    if ch in "%$#":
        return "ET"
    return "N"


def has_arabic(text):
    return any(_type(c) == "R" for c in text)


def shape(text):
    return arabic_reshaper.reshape(text) if arabic_reshaper else text


def _levels(types):
    """Embedding levels for a right-to-left paragraph (the weak/neutral rules of the Unicode bidi algorithm)."""
    n, t_ = len(types), list(types)
    last = "sos"
    for i in range(n):                                    # W2: digits after Arabic letters are Arabic numbers
        if t_[i] in ("R", "L"):
            last = t_[i]
        elif t_[i] == "EN" and last == "R":
            t_[i] = "AN"
    for i in range(1, n - 1):                             # W4: one separator between two numbers
        if t_[i] == "CS" and t_[i - 1] == t_[i + 1] and t_[i - 1] in ("EN", "AN"):
            t_[i] = t_[i - 1]
        elif t_[i] == "ES" and t_[i - 1] == "EN" and t_[i + 1] == "EN":
            t_[i] = "EN"
    i = 0
    while i < n:                                          # W5: %, $ next to a European number
        if t_[i] == "ET":
            j = i
            while j < n and t_[j] == "ET":
                j += 1
            if (i > 0 and t_[i - 1] == "EN") or (j < n and t_[j] == "EN"):
                t_[i:j] = ["EN"] * (j - i)
            i = j
        else:
            i += 1
    t_ = ["N" if x in ("CS", "ES", "ET") else x for x in t_]          # W6
    last = "sos"
    for i in range(n):                                    # W7: European numbers after Latin text are Latin
        if t_[i] in ("R", "L"):
            last = t_[i]
        elif t_[i] == "EN" and last == "L":
            t_[i] = "L"

    def strong(x):
        return "L" if x == "L" else "R"                   # numbers count as R when resolving neutrals
    levels = [0] * n
    i = 0
    while i < n:
        if t_[i] != "N":
            levels[i] = 1 if t_[i] == "R" else 2
            i += 1
            continue
        j = i
        while j < n and t_[j] == "N":
            j += 1
        before = strong(t_[i - 1]) if i > 0 else "R"
        after = strong(t_[j]) if j < n else "R"
        for k in range(i, j):
            levels[k] = 2 if (before == after == "L") else 1
        i = j
    return levels


def to_visual(line):
    """Logical Arabic line -> the string to hand to Tk (base direction right-to-left)."""
    if not line or not has_arabic(line):
        return line
    s = shape(line)
    levels = _levels([_type(c) for c in s])
    chars = [c.translate(_MIRROR) if lv == 1 else c for c, lv in zip(s, levels)]
    for lvl in range(max(levels), 0, -1):                 # L2: reverse every run at this level or higher
        i = 0
        while i < len(chars):
            if levels[i] >= lvl:
                j = i
                while j < len(chars) and levels[j] >= lvl:
                    j += 1
                chars[i:j] = chars[i:j][::-1]
                levels[i:j] = levels[i:j][::-1]
                i = j
            else:
                i += 1
    return "".join(chars)


def wrap_visual(text, measure, width):
    """Word-wrap logical text to `width` pixels (measure(str) -> px) and return visual lines.
    Tk cannot wrap Arabic itself, because the string it gets is already in visual order."""
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = f"{line} {word}" if line else word
            if line and measure(to_visual(cand)) > width:
                lines.append(to_visual(line))
                line = word
            else:
                line = cand
        lines.append(to_visual(line))
    return "\n".join(lines)
