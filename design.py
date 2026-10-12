"""ChessTalentsFactory motion design system (v2, premium).

Everything visual lives here: palette, type, backgrounds, cards, chips, kinetic headlines, captions, the scene
blocks, the end card and the sound design. make_explainer.py only decides WHAT to show; this decides HOW.

Design rules
- Type: Montserrat Black for headlines (tight, confident), Inter for UI and captions.
- One accent colour (CTF orange). Keywords sit on an orange marker, never just recoloured.
- Generous safe margins (72 px sides, 150 px top, 330 px bottom for Instagram UI).
- Soft, consistent shadows; white "paper" cards with an orange accent bar.
- Backgrounds are calm studios with depth (soft light, subtle chessboard floor, blurred pieces): the content is the hero.
- Motion: ease-out entrances, staggered reveals, slow background drift, crossfade+scale transitions.
- Sound: tonal swells and soft ticks only. No noise-based effects.
"""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import brand
import make_reel as R

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 25, 24000
KIT = os.path.join(HERE, "assets", "kit")
FD = os.path.join(HERE, "fonts")
F_BLACK = os.path.join(FD, "Montserrat-Black.ttf")
F_XB = os.path.join(FD, "Montserrat-ExtraBold.ttf")
F_UI = os.path.join(FD, "Inter-Bold.ttf")
F_UI2 = os.path.join(FD, "Inter-SemiBold.ttf")

INK = (17, 17, 22)
INK2 = (88, 86, 96)
ORANGE = brand.ORANGE
ORANGE_D = (214, 92, 22)
CREAM = (250, 246, 241)
LINE = (234, 227, 219)
GREEN = (26, 150, 90)
MX = 72                     # side margin
TOP = 150                   # headline top (below brand bar)

# ======================================================================= creator looks (set per reel by studio.py)
LOOK = {"light": "studio", "marker": "fill"}


def set_look(light="studio", marker="fill"):
    LOOK["light"] = light if light in ("studio", "paper", "warm") else "studio"
    LOOK["marker"] = marker if marker in ("fill", "underline") else "fill"


# ======================================================================= utilities
_c = {}


def cached(key, fn):
    if key not in _c:
        _c[key] = fn()
    return _c[key]


def font(path, size):
    return cached(("font", path, size), lambda: ImageFont.truetype(path, size))


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_out(t): t = clamp(t); return t * t * (3 - 2 * t)
def back(t, s=1.4): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2


def with_alpha(im, a):
    if a >= 0.999:
        return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def paste(fr, im, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.004:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    im = with_alpha(im, alpha)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    if x >= 0 and y >= 0 and x + im.width <= W and y + im.height <= H:
        fr.alpha_composite(im, (x, y))
    else:
        tmp = Image.new("RGBA", fr.size, (0, 0, 0, 0)); tmp.paste(im, (x, y)); fr.alpha_composite(tmp)


def soft_shadow(w, h, radius, blur=28, alpha=55, dy=18):
    def mk():
        pad = blur * 2
        im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad + dy), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle([pad, pad + dy, pad + w, pad + h + dy], radius=radius, fill=(40, 24, 10, alpha))
        return im.filter(ImageFilter.GaussianBlur(blur))
    return cached(("shadow", w, h, radius, blur, alpha, dy), mk)


def panel(w, h, radius=34, accent=True, fill=(255, 255, 255), border=LINE):
    """White paper card with a soft shadow and an orange accent bar on the left."""
    def mk():
        sh = soft_shadow(w, h, radius)
        pad = (sh.width - w) // 2
        im = sh.copy()
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill, outline=border, width=2)
        if accent:
            m = Image.new("L", (w, h), 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
            bar = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(bar).rectangle([0, 0, 12, h], fill=ORANGE)
            bar.putalpha(Image.fromarray(np.minimum(np.array(bar.getchannel("A")), np.array(m))))
            im.alpha_composite(bar, (pad, pad))
        return im, pad
    return cached(("panel", w, h, radius, accent, fill, border), mk)


def text_lines(txt, f, maxw):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        t2 = (cur + " " + w).strip()
        if cur and f.getlength(t2) > maxw:
            lines.append(cur); cur = w
        else:
            cur = t2
    if cur:
        lines.append(cur)
    return lines


# ======================================================================= backgrounds (cached, slightly larger for drift)
BGW, BGH = int(W * 1.06), int(H * 1.06)


def _grad(top, bottom, w=BGW, h=BGH, curve=1.0):
    a = np.linspace(0, 1, h)[:, None] ** curve
    arr = (np.array(top)[None, None, :] * (1 - a[..., None]) + np.array(bottom)[None, None, :] * a[..., None])
    arr = np.repeat(arr, w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def _glow(im, cx, cy, r, color, alpha):
    g = Image.new("L", im.size, 0)
    ImageDraw.Draw(g).ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], fill=int(255 * alpha))
    im.paste(color, (0, 0), g.filter(ImageFilter.GaussianBlur(r * 0.45)))


def _ghost_pieces(im, items, blur=10, alpha=0.08, color=(40, 30, 20)):
    import chess
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for x, y, s, p in items:
        pc = R.piece_img(chess.Piece(p, chess.BLACK), s)
        tint = Image.new("RGBA", pc.size, color + (0,)); tint.putalpha(pc.getchannel("A").point(lambda v: int(v * alpha)))
        layer.alpha_composite(tint, (x, y))
    im.paste(layer.filter(ImageFilter.GaussianBlur(blur)), (0, 0), layer.filter(ImageFilter.GaussianBlur(blur)))


def _soft_board(im, hz):
    """Low-contrast perspective chessboard floor that fades into the wall: chess identity without noise."""
    d = ImageDraw.Draw(im, "RGBA")
    w, h = im.size
    zn, zf, S, vx = 1.0, 7.0, 210.0, w / 2
    def Y(z): return hz + (h - hz) * (1 / z - 1 / zf) / (1 / zn - 1 / zf)
    rows = 11
    zs = [zf - (zf - zn) * (j / rows) ** 0.8 for j in range(rows + 1)]
    for j in range(rows):
        z0, z1 = zs[j], zs[j + 1]
        for u in range(-16, 16):
            if (j + u) % 2:
                pts = [(vx + u * S / z0, Y(z0)), (vx + (u + 1) * S / z0, Y(z0)),
                       (vx + (u + 1) * S / z1, Y(z1)), (vx + u * S / z1, Y(z1))]
                d.polygon(pts, fill=(120, 80, 50, 34))
    fade = Image.new("L", im.size, 0); fd = ImageDraw.Draw(fade)
    for y in range(int(hz), h):
        fd.line([(0, y), (w, y)], fill=int(255 * clamp(1 - (y - hz) / 420)))
    base = im.copy()
    wall = _grad((246, 238, 229), (240, 229, 217), w, h)
    im.paste(wall, (0, 0), fade.point(lambda v: int(v * 0.85)))
    return im


def bg_studio():
    def mk():
        im = _grad((252, 249, 245), (245, 234, 222), curve=1.2)
        _glow(im, BGW // 2, int(BGH * 0.55), 640, (255, 255, 255), 0.85)
        _ghost_pieces(im, [(-60, 260, 420, 1), (BGW - 330, 120, 380, 6), (BGW - 300, 900, 300, 3)], blur=14, alpha=0.06)
        im = _soft_board(im, int(BGH * 0.66))
        _glow(im, BGW // 2, int(BGH * 0.86), 430, (255, 251, 246), 0.7)
        return im.convert("RGBA")
    return cached("bg_studio", mk)


def bg_dark():
    def mk():
        im = _grad((30, 28, 34), (12, 12, 15), curve=0.9)
        _glow(im, int(BGW * 0.82), int(BGH * 0.12), 520, (120, 60, 20), 0.55)
        _glow(im, int(BGW * 0.15), int(BGH * 0.9), 460, (60, 40, 30), 0.35)
        _ghost_pieces(im, [(BGW - 420, BGH - 760, 520, 6), (-120, 340, 380, 2)], blur=8, alpha=0.10, color=(255, 255, 255))
        return im.convert("RGBA")
    return cached("bg_dark", mk)


def bg_warm():
    def mk():
        im = _grad((255, 247, 238), (247, 140, 52), curve=1.6)
        _glow(im, BGW // 2, int(BGH * 0.58), 620, (255, 236, 214), 0.55)
        _ghost_pieces(im, [(-80, 1150, 420, 6), (BGW - 360, 1250, 380, 1)], blur=12, alpha=0.10, color=(120, 50, 10))
        return im.convert("RGBA")
    return cached("bg_warm", mk)


def bg_paper():
    """Editorial look: clean cream paper, fine grid, one soft orange glow. Quiet and premium."""
    def mk():
        im = _grad((251, 248, 243), (244, 238, 230), curve=1.0)
        d = ImageDraw.Draw(im, "RGBA")
        for x in range(0, BGW, 72):
            d.line([(x, 0), (x, BGH)], fill=(120, 90, 60, 26))
        for y in range(0, BGH, 72):
            d.line([(0, y), (BGW, y)], fill=(120, 90, 60, 26))
        _glow(im, int(BGW * 0.85), int(BGH * 0.2), 380, (255, 214, 176), 0.5)
        _glow(im, BGW // 2, int(BGH * 0.8), 520, (255, 255, 255), 0.75)
        _ghost_pieces(im, [(BGW - 360, BGH - 820, 420, 6)], blur=12, alpha=0.06)
        return im.convert("RGBA")
    return cached("bg_paper", mk)


def draw_bg(fr, kind, t):
    """Slow drift (Ken Burns) on the background only, so text and characters stay razor sharp."""
    if kind == "studio":
        kind = LOOK["light"]
    bg = {"studio": bg_studio, "dark": bg_dark, "warm": bg_warm, "paper": bg_paper}[kind]()
    k = ease_in_out(t / 8.0)
    ox, oy = int((BGW - W) * (0.5 + 0.25 * (k - 0.5))), int((BGH - H) * (0.65 - 0.3 * k))
    fr.paste(bg.crop((ox, oy, ox + W, oy + H)), (0, 0))


# ======================================================================= characters
def kit(name, height):
    def mk():
        im = Image.open(os.path.join(KIT, name + ".png")).convert("RGBA")
        return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)
    return cached(("kit", name, height), mk)


def floor_shadow(fr, cx, y, w, a):
    sh = cached(("fs", w), lambda: _fs(w))
    fr.alpha_composite(with_alpha(sh, a), (int(cx - sh.width / 2), int(y - sh.height / 2)))


def _fs(w):
    im = Image.new("RGBA", (w + 120, w // 5 + 120), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([60, 60, 60 + w, 60 + w // 5], fill=(60, 35, 15, 70))
    return im.filter(ImageFilter.GaussianBlur(22))


def character(fr, name, cx, feet_y, height, t, enter=0.0, slide_from=None):
    lt = t - enter
    if lt < 0:
        return
    im = kit(name, height)
    k = ease_out(lt / 0.6)
    x = cx if slide_from is None else slide_from + (cx - slide_from) * k
    rise = 0 if slide_from is not None else (1 - k) * 60
    breath = 1 + 0.01 * math.sin(2 * math.pi * lt / 3.0)
    bob = 4 * math.sin(2 * math.pi * lt / 3.0 + 0.6)
    floor_shadow(fr, x, feet_y - 4, int(im.width * 0.72), min(1, lt / 0.4))
    if abs(breath - 1) > 0.003:
        im = im.resize((im.width, int(im.height * breath)), Image.BILINEAR)
    im = with_alpha(im, min(1, lt / 0.3))
    tmp_x, tmp_y = int(x - im.width / 2), int(feet_y - im.height + bob + rise)
    if tmp_x >= 0 and tmp_y >= 0 and tmp_x + im.width <= W and tmp_y + im.height <= H:
        fr.alpha_composite(im, (tmp_x, tmp_y))
    else:
        tmp = Image.new("RGBA", fr.size, (0, 0, 0, 0)); tmp.paste(im, (tmp_x, tmp_y)); fr.alpha_composite(tmp)


# ======================================================================= headline (kinetic, marker highlight)
def _word_img(w, size, hl, dark):
    under = hl and LOOK["marker"] == "underline"
    def mk():
        f = font(F_BLACK, size)
        tw = int(f.getlength(w)); asc, desc = f.getmetrics()
        if under:                                       # orange word with a thick orange underline
            im = Image.new("RGBA", (tw + 8, asc + desc + 18), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            d.rounded_rectangle([2, asc + 2, tw + 4, asc + 14], radius=6, fill=ORANGE + (110,))
            d.text((2, 0), w, font=f, fill=ORANGE)
            return im
        padx, pady = (18, 6) if hl else (0, 0)
        im = Image.new("RGBA", (tw + 2 * padx + 6, asc + desc + 2 * pady + 6), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if hl:
            d.rounded_rectangle([0, int(asc * 0.18), tw + 2 * padx, asc + desc + 2 * pady - int(desc * 0.2)],
                                radius=14, fill=ORANGE)
        col = (255, 255, 255) if (hl or dark) else INK
        d.text((padx, pady), w, font=f, fill=col)
        return im
    return cached(("w", w, size, hl, dark, under), mk)


def headline_layout(text, highlight, size=88, maxw=W - 2 * MX):
    hl = {h.lower().strip(".,!?'’") for hh in highlight for h in hh.split()}
    words = text.split()
    while True:
        f = font(F_BLACK, size)
        lines, cur = [], []
        for w in words:
            pad = 36 if LOOK["marker"] == "fill" else 8
            ww = f.getlength(" ".join(cur + [w])) + (pad * sum(1 for x in cur + [w] if x.lower().strip(".,!?'’") in hl))
            if cur and ww > maxw:
                lines.append(cur); cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(cur)
        if len(lines) <= 3 or size <= 58:
            return lines, size, hl
        size -= 6


def headline(fr, text, highlight, t, y=TOP, dark=False, size=88, instant=False):
    lines, size, hl = headline_layout(text, highlight, size)
    lh = int(size * 1.2)
    f = font(F_BLACK, size)
    i = 0
    for li, line in enumerate(lines):
        imgs = [_word_img(w, size, w.lower().strip(".,!?'’") in hl, dark) for w in line]
        gap = int(size * 0.26)
        total = sum(im.width for im in imgs) + gap * (len(imgs) - 1)
        x = (W - total) / 2
        for w, im in zip(line, imgs):
            lt = 9 if instant else t - 0.05 - 0.065 * i
            if lt > 0:
                k = ease_out(lt / 0.42)
                yy = y + li * lh + (1 - k) * 34
                fr.alpha_composite(with_alpha(im, k), (int(x), int(yy)))
            x += im.width + gap; i += 1
    return y + len(lines) * lh          # bottom of the headline (for layouts that need it)


# ======================================================================= chrome: brand bar, progress, captions
def brand_bar(fr, t_global, total, dark=False):
    # progress bar (thin, top)
    d = ImageDraw.Draw(fr, "RGBA")
    x0, x1, y = MX, W - MX, 52
    d.rounded_rectangle([x0, y, x1, y + 6], radius=3, fill=(255, 255, 255, 70) if dark else (30, 20, 10, 28))
    k = clamp(t_global / max(0.1, total))
    if k > 0:
        d.rounded_rectangle([x0, y, x0 + (x1 - x0) * k, y + 6], radius=3, fill=ORANGE + (255,))
    lg = cached(("barlogo", dark), lambda: _bar_logo(dark))
    fr.alpha_composite(lg, (int(W / 2 - lg.width / 2), 78))


def _bar_logo(dark):
    lg = brand.logo(250)
    if dark:
        card = Image.new("RGBA", (lg.width + 36, lg.height + 20), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=card.height // 2,
                                               fill=(255, 255, 255, 235))
        card.alpha_composite(lg, (18, 10))
        return card
    return lg


def captions(fr, words, t, dark=False):
    """Dark glass caption pill, 2 lines max, the word being spoken in orange."""
    if not words:
        return
    idx = max([i for i, (ts, _) in enumerate(words) if ts <= t] or [0])
    chunk_n = 5
    start = (idx // chunk_n) * chunk_n
    chunk = words[start:start + chunk_n]
    f = font(F_UI, 46)
    txt = " ".join(w for _, w in chunk)
    lines = text_lines(txt, f, W - 2 * MX - 90)
    lh = 60
    pw = int(max(f.getlength(l) for l in lines) + 64); ph = lh * len(lines) + 34
    bg = cached(("cap", pw, ph), lambda: _cap_bg(pw, ph))
    x0, y0 = int((W - pw) / 2), 1590 - ph // 2
    fr.alpha_composite(bg, (x0 - 30, y0 - 30))
    d = ImageDraw.Draw(fr)
    k = 0
    for li, line in enumerate(lines):
        x = (W - f.getlength(line)) / 2
        for w in line.split():
            gi = start + k
            col = ORANGE if gi == idx else ((255, 255, 255) if gi < idx else (205, 205, 212))
            d.text((x, y0 + 14 + li * lh), w, font=f, fill=col)
            x += f.getlength(w + " "); k += 1


def _cap_bg(w, h):
    im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([30, 36, 30 + w, 36 + h], radius=28, fill=(0, 0, 0, 60))
    im = im.filter(ImageFilter.GaussianBlur(12))
    ImageDraw.Draw(im).rounded_rectangle([30, 30, 30 + w, 30 + h], radius=28, fill=(18, 17, 22, 222))
    return im


# ======================================================================= components
def chip(text, size=42, icon=None, dark=False):
    def mk():
        f = font(F_UI, size); tw = f.getlength(text)
        h = int(size * 2.15); iw = int(h * 0.62) if icon else 0
        w = int(tw + 64 + iw + (14 if icon else 0))
        sh = soft_shadow(w, h, h // 2, blur=18, alpha=45, dy=10)
        pad = (sh.width - w) // 2
        im = sh.copy(); d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=h // 2, fill=(255, 255, 255) if not dark else (36, 34, 42),
                            outline=LINE if not dark else (70, 66, 80), width=2)
        x = pad + 26
        if icon:
            r = iw // 2; cx, cy = x + r, pad + h / 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ORANGE)
            if icon == "check":
                d.line([(cx - r * .42, cy + r * .02), (cx - r * .1, cy + r * .34), (cx + r * .45, cy - r * .32)], fill=(255, 255, 255), width=max(4, r // 5))
            elif icon == "x":
                d.line([(cx - r * .36, cy - r * .36), (cx + r * .36, cy + r * .36)], fill=(255, 255, 255), width=max(4, r // 5))
                d.line([(cx - r * .36, cy + r * .36), (cx + r * .36, cy - r * .36)], fill=(255, 255, 255), width=max(4, r // 5))
            else:
                d.text((cx, cy + 1), icon, font=font(F_BLACK, int(r * 1.1)), fill=(255, 255, 255), anchor="mm")
            x += iw + 14
        d.text((x + 6, pad + h / 2 + 1), text, font=f, fill=INK if not dark else (255, 255, 255), anchor="lm")
        return im
    return cached(("chip", text, size, icon, dark), mk)


def stat_card(label, value, color=INK, w=470, h=250):
    im, pad = panel(w, h)
    im = im.copy(); d = ImageDraw.Draw(im)
    d.text((pad + 44, pad + 40), label.upper(), font=font(F_UI, 30), fill=INK2)
    d.text((pad + 42, pad + 80), value, font=font(F_BLACK, 112), fill=color)
    return im


def bubble(fr, cx, cy, t, enter=0.0):
    lt = t - enter
    if lt < 0:
        return
    def mk():
        im = Image.new("RGBA", (320, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for (x, y, r) in [(160, 100, 84), (100, 112, 58), (222, 112, 60), (130, 64, 52), (196, 66, 54)]:
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
        d.ellipse([70, 196, 100, 226], fill=(255, 255, 255)); d.ellipse([44, 232, 62, 250], fill=(255, 255, 255))
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.paste((60, 40, 20, 40), (0, 6), im.getchannel("A"))
        out = sh.filter(ImageFilter.GaussianBlur(10)); out.alpha_composite(im)
        return out
    im = cached("bubble2", mk).copy(); d = ImageDraw.Draw(im)
    for i in range(3):
        a = 0.5 + 0.5 * math.sin(lt * 6 - i * 0.9)
        d.ellipse([112 + i * 46 - 12, 98 - 12 - 7 * a, 112 + i * 46 + 12, 98 + 12 - 7 * a], fill=(190, 186, 196))
    paste(fr, im, cx, cy, 0.6 + 0.4 * back(lt / 0.45), min(1, lt / 0.2))


def star(size, fill):
    def mk():
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        c, r1, r2 = size / 2, size / 2 - 2, size / 4.6
        d.polygon([(c + (r1 if i % 2 == 0 else r2) * math.sin(i * math.pi / 5),
                    c - (r1 if i % 2 == 0 else r2) * math.cos(i * math.pi / 5)) for i in range(10)], fill=fill)
        return im
    return cached(("star", size, fill), mk)


def trophy_icon(size):
    def mk():
        s = size; im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        gold, dark = (247, 186, 40), (210, 140, 20)
        d.ellipse([s * .1, s * .15, s * .32, s * .45], outline=gold, width=max(3, s // 20))
        d.ellipse([s * .68, s * .15, s * .9, s * .45], outline=gold, width=max(3, s // 20))
        d.pieslice([s * .22, -s * .25, s * .78, s * .62], 0, 180, fill=gold)
        d.rectangle([s * .45, s * .6, s * .55, s * .76], fill=dark)
        d.rounded_rectangle([s * .3, s * .76, s * .7, s * .9], radius=s // 30, fill=INK)
        return im
    return cached(("trophy", size), mk)


def medal(size):
    def mk():
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.polygon([(size * .3, 0), (size * .45, size * .45), (size * .55, size * .45), (size * .7, 0)], fill=ORANGE_D)
        d.ellipse([size * .16, size * .34, size * .84, size * .99], fill=(247, 186, 40), outline=(214, 146, 24), width=max(3, size // 18))
        im.alpha_composite(star(int(size * .38), (255, 244, 205)), (int(size * .31), int(size * .48)))
        return im
    return cached(("medal", size), mk)


def list_rows(fr, items, t, dur, y0, icon="check", maxw=None, numbered=False, dark=False, step=None):
    """Rows of chips sliding in one by one, left aligned to the margin."""
    n = max(1, len(items))
    step = step or max(0.45, min(0.9, (dur - 1.4) / n))
    for i, it in enumerate(items):
        lt = t - (0.55 + i * step)
        if lt < 0:
            continue
        ch = chip(it, 44, icon=str(i + 1) if numbered else icon, dark=dark)
        k = ease_out(lt / 0.5)
        x = MX - 20 + ch.width / 2 - (1 - k) * 80
        paste(fr, ch, x, y0 + i * 168, 1, min(1, lt / 0.25))


# ======================================================================= scene blocks: (fr, t, dur, scene) -> bg kind
def b_pain(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    pose = "girl_thinking" if s["params"].get("pose") == "thinking" else "girl_sad"
    character(fr, pose, W / 2, 1460, 760, t, 0.1)
    bubble(fr, W / 2 + 300, 760, t, 0.8)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_rating_drop(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    character(fr, "girl_thinking", W / 2 - 40, 1470, 720, t, 0.0)
    a, b = s["params"]["from"], s["params"]["to"]
    k = ease_in_out((t - 0.7) / max(0.8, dur - 1.6))
    lt = t - 0.3
    if lt > 0:
        val = int(a + (b - a) * k)
        c = stat_card("Rating", str(val), (196, 40, 40) if k > 0.05 else INK, w=430, h=240)
        paste(fr, c, W - MX - 190, 640, 0.85 + 0.15 * back(lt / 0.5), min(1, lt / 0.2))
        if k > 0.1:
            d = ImageDraw.Draw(fr)
            cx, cy = W - MX - 60, 560
            d.polygon([(cx - 22, cy - 10), (cx + 22, cy - 10), (cx, cy + 22)], fill=(196, 40, 40))
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_wrong_way(fr, t, dur, s):
    draw_bg(fr, "dark", t)
    items = s["params"].get("items") or ["Random videos", "Endless blitz", "No plan"]
    n = len(items[:3])
    step = max(0.5, (dur - 1.6) / n)
    for i, it in enumerate(items[:3]):
        lt = t - (0.5 + i * step)
        if lt < 0:
            continue
        w, h = W - 2 * MX, 196
        im, pad = panel(w, h, accent=False, fill=(34, 32, 40), border=(62, 58, 72))
        im = im.copy(); d = ImageDraw.Draw(im)
        cx, cy = pad + 92, pad + h / 2
        d.ellipse([cx - 44, cy - 44, cx + 44, cy + 44], fill=(60, 30, 30))
        d.line([(cx - 16, cy - 16), (cx + 16, cy + 16)], fill=(255, 110, 90), width=8)
        d.line([(cx - 16, cy + 16), (cx + 16, cy - 16)], fill=(255, 110, 90), width=8)
        f = font(F_XB, 56 if len(it) < 18 else 46)
        d.text((pad + 170, cy), it, font=f, fill=(255, 255, 255), anchor="lm")
        strike = clamp((lt - 0.55) / 0.35)
        if strike > 0:
            d.line([(pad + 166, cy + 3), (pad + 166 + (f.getlength(it) + 12) * strike, cy + 3)], fill=(255, 110, 90), width=7)
        k = ease_out(lt / 0.5)
        paste(fr, im, W / 2 + (1 - k) * 120, 760 + i * 240, 1, min(1, lt / 0.25))
    headline(fr, s["headline"], s["highlight"], t, dark=True, instant=s.get("_first"))


def b_mentor(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    character(fr, "girl_standing", W / 2 - 190, 1490, 600, t, 0.0)
    character(fr, "coach_standing", W / 2 + 180, 1490, 860, t, 0.35, slide_from=W + 320)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_roadmap(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    lt = t - 0.2
    w, h = 560, 640
    im, pad = panel(w, h, accent=False)
    im = im.copy(); d = ImageDraw.Draw(im)
    d.text((pad + 48, pad + 44), "YOUR ROADMAP", font=font(F_UI, 32), fill=INK2)
    n_on = int(clamp((t - 0.8) / max(0.6, dur - 2.0)) * 11)
    for i in range(12):
        r, col = divmod(i, 3)
        cx, cy = pad + 120 + col * 160, pad + 160 + r * 116
        if i == 11:
            im.alpha_composite(trophy_icon(104), (int(cx - 52), int(cy - 56)))
        elif i < n_on:
            d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=ORANGE)
            im.alpha_composite(star(44, (255, 255, 255)), (int(cx - 22), int(cy - 23)))
        else:
            d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=LINE, width=6)
    if lt > 0:
        paste(fr, im, MX + 280, 900, 0.9 + 0.1 * back(lt / 0.5), min(1, lt / 0.25))
    character(fr, "girl_standing", W - MX - 150, 1500, 560, t, 0.5)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_method_steps(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    character(fr, "coach_standing", W - MX - 110, 1540, 820, t, 0.0)
    list_rows(fr, (s["params"].get("steps") or ["Find the gaps", "Train in order", "Review every game"])[:3], t, dur,
              620, numbered=True)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_faq_answer(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    character(fr, "coach_standing", W - MX - 110, 1540, 820, t, 0.0)
    list_rows(fr, (s["params"].get("points") or ["Small groups", "Same level", "Clear plan"])[:3], t, dur, 620)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_authority(fr, t, dur, s):
    draw_bg(fr, "warm", t)
    character(fr, "pair_hands", W / 2, 1560, 700, t, 0.0)
    bottom = headline_bottom(s)
    for i, bdg in enumerate((s["params"].get("badges") or [])[:3]):
        lt = t - (0.55 + i * min(0.5, max(0.3, (dur - 1.4) / 3)))
        if lt < 0:
            continue
        ch = chip(bdg, 40, icon="check")
        paste(fr, ch, W / 2, bottom + 70 + i * 128, 0.8 + 0.2 * back(lt / 0.45), min(1, lt / 0.2))
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def headline_bottom(s):
    lines, size, _ = headline_layout(s["headline"], s["highlight"])
    return TOP + len(lines) * int(size * 1.2)


def b_faq_question(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    character(fr, "girl_thinking", W / 2, 1490, 700, t, 0.4)
    q = s["params"].get("question") or s["headline"]
    lt = t
    w, h = W - 2 * MX, 380
    im, pad = panel(w, h)
    im = im.copy(); d = ImageDraw.Draw(im)
    d.text((pad + 56, pad + 46), "PARENTS ASK US", font=font(F_UI, 30), fill=ORANGE_D)
    f = font(F_BLACK, 64 if len(q) < 30 else 54)
    for li, ln in enumerate(text_lines(q, f, w - 120)[:3]):
        d.text((pad + 56, pad + 100 + li * int(f.size * 1.15)), ln, font=f, fill=INK)
    paste(fr, im, W / 2, 470, 0.92 + 0.08 * back(lt / 0.5), min(1, lt / 0.2))


def b_progress(fr, t, dur, s):
    draw_bg(fr, "warm", t)
    k = ease_in_out((t - 0.4) / max(1.0, dur - 1.2))
    d = ImageDraw.Draw(fr)
    pts = [(MX + 30 + i * 84, 1230 - (i * 46 + 50 * math.sin(i * 1.25))) for i in range(11)]
    n = max(2, int(2 + k * (len(pts) - 2)))
    d.line(pts[:n], fill=(255, 255, 255), width=14, joint="curve")
    for p in pts[:n]:
        d.ellipse([p[0] - 13, p[1] - 13, p[0] + 13, p[1] + 13], fill=ORANGE_D, outline=(255, 255, 255), width=5)
    character(fr, "girl_standing", W - MX - 160, 1560, 600, t, 0.2)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_rating_up(fr, t, dur, s):
    import guard
    draw_bg(fr, "warm", t)
    character(fr, "pair_hands", W / 2, 1580, 760, t, 0.0)
    gain = 300
    for c in guard.approved():
        if c.get("id") == "avg_gain":
            nums = [int(n) for n in c.get("numbers", []) if str(n).isdigit()]
            gain = nums[0] if nums else gain
    k = ease_out((t - 0.6) / max(1.0, dur - 1.6))
    lt = t - 0.3
    if lt > 0:
        paste(fr, stat_card("Avg. rating gain", f"+{int(gain * k)}"), W / 2, 640, 0.85 + 0.15 * back(lt / 0.45), min(1, lt / 0.2))
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_trophy(fr, t, dur, s):
    draw_bg(fr, "warm", t)
    rng = random.Random(7)
    d = ImageDraw.Draw(fr)
    if t > 0.3:
        for i in range(56):
            x0 = rng.uniform(0, W); sp = rng.uniform(220, 460); ph = rng.uniform(0, 3)
            y = (rng.uniform(-500, 0) + (t - 0.3) * sp) % (H + 200) - 100
            col = rng.choice([(255, 255, 255), (255, 214, 90), (226, 96, 30), (40, 38, 46)])
            x = x0 + 30 * math.sin(t * 3 + ph)
            d.rounded_rectangle([x, y, x + 12, y + 20], radius=3, fill=col)
    character(fr, "girl_trophy", W / 2, 1610, 1060, t, 0.0)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_limited(fr, t, dur, s):
    draw_bg(fr, "dark", t)
    w, h = 640, 560
    im, pad = panel(w, h, accent=False)
    im = im.copy(); d = ImageDraw.Draw(im)
    filled = int(clamp((t - 0.6) / max(0.8, dur - 1.6)) * 20)
    for i in range(28):
        r, col = divmod(i, 7)
        x, y = pad + 50 + col * 80, pad + 120 + r * 100
        d.rounded_rectangle([x, y, x + 60, y + 64], radius=12, fill=ORANGE if i < filled else (238, 233, 228))
    d.text((pad + 50, pad + 44), "THIS MONTH", font=font(F_UI, 32), fill=INK2)
    paste(fr, im, W / 2, 920, 0.9 + 0.1 * back((t - 0.2) / 0.45), min(1, max(0, t - 0.2) / 0.2))
    headline(fr, s["headline"], s["highlight"], t, dark=True, instant=s.get("_first"))


def b_before_after(fr, t, dur, s):
    draw_bg(fr, "warm", t)
    p = s["params"]; a, b = p["from"], p["to"]
    late = t > dur * 0.62
    character(fr, "girl_trophy" if late else "girl_standing", W - MX - 180, 1600, 940 if late else 600, t,
              dur * 0.62 if late else 0.0)
    k = ease_in_out((t - 0.7) / max(1.0, dur - 1.8))
    lt = t - 0.3
    if lt > 0:
        val = f"{int(a + (b - a) * k)}" + ("+" if k >= 1 and "+" in str(p.get("label", "")) else "")
        paste(fr, stat_card("Rating", val, GREEN if k >= 1 else INK), MX + 245, 680, 0.85 + 0.15 * back(lt / 0.5), min(1, lt / 0.2))
        if p.get("label") and k > 0.3:
            paste(fr, chip(p["label"], 40, icon="check"), MX + 230, 900, back((k - 0.3) / 0.3), 1)
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def b_success_timeline(fr, t, dur, s):
    draw_bg(fr, "studio", t)
    character(fr, "girl_trophy", W - MX - 120, 1560, 700, t, 0.0)
    ms = s["params"].get("milestones") or []
    n = max(1, len(ms)); step = max(0.5, (dur - 1.6) / n)
    x0, y_top, gap = MX + 40, 640, 180
    d = ImageDraw.Draw(fr)
    shown = sum(1 for i in range(len(ms)) if t - (0.5 + i * step) > 0)
    if shown > 1:
        d.line([(x0, y_top), (x0, y_top + (shown - 1) * gap)], fill=ORANGE, width=6)
    f = font(F_UI, 42)
    for i, m in enumerate(ms):
        lt = t - (0.5 + i * step)
        if lt < 0:
            continue
        y = y_top + i * gap
        md = medal(92)
        fr.alpha_composite(with_alpha(md, min(1, lt / 0.2)), (x0 - 46, int(y - 46 + (1 - ease_out(lt / 0.4)) * 24)))
        lines = text_lines(m, f, 560)
        a = int(255 * min(1, lt / 0.3))
        for li, ln in enumerate(lines):
            d.text((x0 + 70, y - 26 * len(lines) + li * 54), ln, font=f, fill=INK + (a,))
    headline(fr, s["headline"], s["highlight"], t, instant=s.get("_first"))


def book_cover(w=300):
    """Stylised Square 65 cover (our own drawing, no copyrighted art): black cover, 8x8 board + the orange 65th square."""
    def mk():
        h = int(w * 1.45)
        sh = soft_shadow(w, h, 10, blur=24, alpha=110, dy=18)
        pad = (sh.width - w) // 2
        im = sh.copy(); d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=10, fill=(22, 21, 26))
        d.rectangle([pad, pad, pad + 14, pad + h], fill=(10, 10, 12))                        # spine
        cs = (w - 92) / 8; x0, y0 = pad + 34, pad + int(h * 0.1)
        for r in range(8):
            for c in range(8):
                col = (66, 64, 74) if (r + c) % 2 else (38, 37, 44)
                d.rectangle([x0 + c * cs, y0 + r * cs, x0 + (c + 1) * cs - 2, y0 + (r + 1) * cs - 2], fill=col)
        d.rounded_rectangle([x0 + 8 * cs + 8, y0 + 7 * cs, x0 + 9 * cs + 6, y0 + 8 * cs - 2], radius=4, fill=ORANGE)
        yb = y0 + 8 * cs
        d.text((pad + w / 2, yb + h * 0.11), "SQUARE 65", font=font(F_BLACK, int(w * 0.15)), fill=(255, 255, 255), anchor="mm")
        d.text((pad + w / 2, yb + h * 0.19), "65 keys to win in chess", font=font(F_UI2, int(w * 0.058)),
               fill=(200, 196, 206), anchor="mm")
        d.text((pad + w / 2, pad + h - h * 0.07), "IM ALBERTO CHUECA", font=font(F_UI, int(w * 0.056)), fill=ORANGE, anchor="mm")
        return im
    return cached(("book", w), mk)


def b_key_card(fr, t, dur, s):
    draw_bg(fr, "dark", t)
    p = s["params"]; n = p.get("key", 1)
    k = ease_out(t / 0.6)
    paste(fr, book_cover(320), MX + 180, 690 + (1 - k) * 60, 0.92 + 0.08 * k, min(1, t / 0.35))
    lt = t - 0.35
    if lt > 0:
        lab = cached("keylab", lambda: _txt("SQUARE 65 · KEY", font(F_UI, 36), ORANGE))
        paste(fr, lab, MX + 420 + lab.width / 2, 520, 1, min(1, lt / 0.25))
        num = cached(("keynum", n), lambda: _keynum(n, font(F_BLACK, 190), font(F_BLACK, 70)))
        paste(fr, num, MX + 418 + num.width / 2, 660, 0.85 + 0.15 * back(lt / 0.45), min(1, lt / 0.2))
        by = cached("keyby", lambda: _txt("by IM Alberto Chueca", font(F_UI2, 34), (190, 186, 198)))
        paste(fr, by, MX + 420 + by.width / 2, 800, 1, clamp((lt - 0.3) / 0.3))
    d = ImageDraw.Draw(fr)
    d.line([(MX, 1000), (MX + 120 * ease_out((t - 0.6) / 0.5), 1000)], fill=ORANGE, width=8)
    title = p.get("title", "")
    ft = font(F_BLACK, 64 if len(title) < 48 else 54)
    lines = text_lines(title, ft, W - 2 * MX)[:4]
    lh = int(ft.size * 1.18)
    for li, ln in enumerate(lines):
        lt2 = t - 0.7 - li * 0.12
        if lt2 > 0:
            a = int(255 * min(1, lt2 / 0.3))
            d.text((MX, 1040 + li * lh + (1 - ease_out(lt2 / 0.4)) * 20), ln, font=ft, fill=(255, 255, 255, a))
    lt3 = t - 1.2
    if lt3 > 0 and p.get("chapter"):
        ch = chip(p["chapter"].upper(), 32, dark=True)
        paste(fr, ch, MX - 14 + ch.width / 2, 1080 + len(lines) * lh + 30, 1, min(1, lt3 / 0.3))


def _keynum(n, f, fs):
    a, b = str(n), "/65"
    wa, wb = f.getlength(a), fs.getlength(b)
    im = Image.new("RGBA", (int(wa + wb + 20), int(f.size * 1.2)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((0, 0), a, font=f, fill=ORANGE)
    d.text((wa + 12, f.size * 0.62), b, font=fs, fill=(150, 146, 160))
    return im


DRAW = {"pain": b_pain, "rating_drop": b_rating_drop, "wrong_way": b_wrong_way, "mentor": b_mentor,
        "roadmap": b_roadmap, "method_steps": b_method_steps, "authority": b_authority,
        "faq_question": b_faq_question, "faq_answer": b_faq_answer, "progress": b_progress,
        "rating_up": b_rating_up, "trophy": b_trophy, "limited": b_limited,
        "before_after": b_before_after, "success_timeline": b_success_timeline, "key_card": b_key_card}
DARK_BLOCKS = {"wrong_way", "limited", "key_card"}


# ======================================================================= end card
def end_card(fr, t, dur, kind):
    draw_bg(fr, "dark", t)
    CT = brand.cta(kind)
    lg = cached("endlogo", lambda: brand.logo_card(640))
    paste(fr, lg, W / 2, 470, 0.9 + 0.1 * back(t / 0.5), min(1, t / 0.25))
    title = {"keyword": "Free training video for parents", "vsl": "Free training video for parents",
             "call": "Get a clear plan for your child", "comment": "New tips for chess parents daily"}.get(kind, "")
    f = font(F_BLACK, 70)
    lines = text_lines(title, f, W - 2 * MX)
    for li, ln in enumerate(lines):
        lt = t - 0.35 - li * 0.1
        if lt > 0:
            im = cached(("endt", ln), lambda ln=ln: _txt(ln, f, (255, 255, 255)))
            paste(fr, im, W / 2, 720 + li * 86 + (1 - ease_out(lt / 0.4)) * 24, 1, min(1, lt / 0.3))
    label = {"keyword": f'COMMENT "{brand.KEYWORD}"', "vsl": "WATCH THE FREE VIDEO", "call": "BOOK A CALL",
             "comment": "FOLLOW US"}.get(kind, "BOOK A CALL")
    lt = t - 0.8
    if lt > 0:
        btn = cached(("btn", label), lambda: _button(label))
        pulse = 1 + 0.025 * math.sin(max(0, t - 1.6) * 5.5) - 0.06 * math.exp(-((t - 1.45) * 9) ** 2)
        paste(fr, btn, W / 2, 1010 + 86 * (len(lines) - 1), (0.8 + 0.2 * back(lt / 0.45)) * pulse, min(1, lt / 0.2))
        sub = "@" + brand.IG_HANDLE if kind in ("keyword", "comment") else CT["url"]()
        im = cached(("ends", sub), lambda: _txt(sub, font(F_UI2, 44), (215, 210, 220)))
        paste(fr, im, W / 2, 1160 + 86 * (len(lines) - 1), 1, clamp((lt - 0.3) / 0.3))
    ct = clamp((t - 0.9) / 0.6)
    if t > 0.9:
        bx = W / 2 + 230 - 150 * ease_out(ct); by = 1100 + 86 * (len(lines) - 1) - 60 * ease_out(ct)
        d = ImageDraw.Draw(fr)
        d.polygon([(bx, by), (bx, by + 62), (bx + 16, by + 48), (bx + 30, by + 76), (bx + 42, by + 70),
                   (bx + 28, by + 44), (bx + 48, by + 42)], fill=(255, 255, 255), outline=INK)


def _txt(s, f, col):
    im = Image.new("RGBA", (int(f.getlength(s)) + 10, int(f.size * 1.3)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((5, 0), s, font=f, fill=col)
    return im


def _button(label):
    f = font(F_BLACK, 56)
    w, h = int(f.getlength(label) + 120), 132
    sh = soft_shadow(w, h, h // 2, blur=26, alpha=120, dy=14)
    pad = (sh.width - w) // 2
    im = sh.copy(); d = ImageDraw.Draw(im)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=h // 2, fill=ORANGE)
    d.rounded_rectangle([pad + 4, pad + 4, pad + w - 4, pad + h // 2], radius=h // 2, fill=(255, 150, 70))
    d.rounded_rectangle([pad, pad + 10, pad + w, pad + h], radius=h // 2, fill=ORANGE)
    d.text((pad + w / 2, pad + h / 2 + 4), label, font=f, fill=(255, 255, 255), anchor="mm")
    return im


# ======================================================================= sound design (tonal, no noise)
def env(n, a, r):
    t = np.arange(n) / SR
    return np.clip(t / a, 0, 1) * np.clip((n / SR - t) / r, 0, 1)


def swell(dur=0.55):
    """Soft tonal transition: two gliding sines with a smooth envelope (an 'air' swell without hiss)."""
    n = int(SR * dur); t = np.arange(n) / SR
    f1 = 330 * (1 + 0.5 * t / dur); f2 = 495 * (1 + 0.5 * t / dur)
    ph1 = 2 * np.pi * np.cumsum(f1) / SR; ph2 = 2 * np.pi * np.cumsum(f2) / SR
    s = (np.sin(ph1) * 0.6 + np.sin(ph2) * 0.4) * env(n, dur * 0.55, dur * 0.4) ** 2
    return (s * 0.22).astype(np.float32)


def tick():
    n = int(SR * 0.06); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 70) * 0.18).astype(np.float32)


def chime():
    n = int(SR * 1.6); t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in [(1046.5, .5, 3.0), (1568, .3, 3.6), (2093, .15, 4.5)])
    return (s * env(n, 0.005, 0.3) * 0.35).astype(np.float32)


def music(total):
    """Warm, modern bed: soft pad + gentle muted plucks, 92 bpm. Sits low under the voice."""
    n = int(total * SR); t = np.arange(n) / SR
    chords = [(220.0, 277.18, 329.63, 415.3), (185.0, 233.08, 277.18, 369.99),
              (196.0, 246.94, 293.66, 369.99), (164.81, 207.65, 246.94, 329.63)]
    out = np.zeros(n, np.float32)
    bar = 60 / 92 * 4
    for i in range(int(total / bar) + 1):
        a0, b0 = int(i * bar * SR), min(n, int((i + 1) * bar * SR) + int(0.4 * SR))
        if a0 >= n:
            break
        tt = (np.arange(b0 - a0) / SR)
        e = np.clip(tt / 0.6, 0, 1) * np.clip((bar + 0.4 - tt) / 0.6, 0, 1)
        for f in chords[i % 4]:
            out[a0:b0] += (0.016 * np.sin(2 * np.pi * f / 2 * tt) + 0.006 * np.sin(2 * np.pi * f * tt)) * e
        for k in range(8):
            s0 = a0 + int(k * bar / 8 * SR)
            if s0 >= n or k in (3, 7):
                continue
            f = chords[i % 4][(k * 2) % 4] * 2
            ln = min(int(0.4 * SR), n - s0); tk = np.arange(ln) / SR
            out[s0:s0 + ln] += 0.022 * np.sin(2 * np.pi * f * tk) * np.exp(-tk * 9) * (1 - np.exp(-tk * 400))
    fade = np.clip(t / 1.2, 0, 1) * np.clip((total - t) / 1.5, 0, 1)
    return out * fade
