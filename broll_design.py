"""Design layer for real-footage reels: text layouts over video, glass overlays, progress chart, level ladder.

Everything is drawn on top of a graded stock clip. Rules: text always sits on a scrim or glass so it is readable on
any footage; one focal point per scene; Instagram safe areas (top 150 px, bottom 330 px for UI).
"""
import math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import design as D

W, H = D.W, D.H
MX = D.MX
INK, ORANGE, WHITE = D.INK, D.ORANGE, (255, 255, 255)
LEVELS = [("The Basics", "400-800"), ("The Strategist", "800-1200"), ("The Competitor", "1200-1500"),
          ("The Expert", "1500-1800"), ("Candidate Master", "1800-2200"), ("Master & Beyond", "2200-2500+")]
LAYOUTS = ["top", "center", "lower", "question", "number", "quote"]


# ----------------------------------------------------------------------- scrims
def _vgrad(h, top_a, bot_a):
    a = np.linspace(top_a, bot_a, h)[:, None].repeat(W, 1)
    im = Image.new("RGBA", (W, h), (8, 7, 10, 0)); im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


def scrim(fr, layout):
    fr.alpha_composite(D.cached(("scrim_bottom",), lambda: _vgrad(760, 0, 200)), (0, H - 760))
    if layout in ("top", "number", "question"):
        fr.alpha_composite(D.cached(("scrim_top",), lambda: _vgrad(900, 190, 0)), (0, 0))
    if layout in ("center", "quote"):
        fr.alpha_composite(D.cached(("scrim_full",), lambda: Image.new("RGBA", (W, H), (8, 7, 10, 105))))
    if layout == "lower":
        fr.alpha_composite(D.cached(("scrim_low",), lambda: _vgrad(1100, 0, 170)), (0, H - 1100 - 300))


def glass(w, h, radius=36, dark=False):
    def mk():
        sh = D.soft_shadow(w, h, radius, blur=26, alpha=90, dy=16)
        pad = (sh.width - w) // 2
        im = sh.copy(); d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius,
                            fill=(20, 19, 24, 205) if dark else (255, 255, 255, 236),
                            outline=(255, 255, 255, 60) if dark else (255, 255, 255, 255), width=2)
        return im, pad
    return D.cached(("glass", w, h, radius, dark), mk)


# ----------------------------------------------------------------------- text layouts
def on_screen(fr, s, t, dur):
    lay = s.get("layout", "top")
    txt, hl = s.get("headline", ""), s.get("highlight", [])
    first = s.get("_first")
    if lay == "top":
        D.headline(fr, txt, hl, t, y=D.TOP + 40, dark=True, size=92, instant=first)
    elif lay == "center":
        lines, size, _ = D.headline_layout(txt, hl, 116)
        y = H / 2 - len(lines) * size * 0.62 - 120
        D.headline(fr, txt, hl, t, y=y, dark=True, size=116, instant=first)
    elif lay == "lower":
        lines, size, _ = D.headline_layout(txt, hl, 96)
        D.headline(fr, txt, hl, t, y=1360 - len(lines) * int(size * 1.2), dark=True, size=96, instant=first)
    elif lay == "question":
        w = W - 2 * MX
        f = D.font(D.F_BLACK, 70 if len(txt) < 32 else 58)
        lines = D.text_lines(txt, f, w - 110)[:3]
        h = 120 + len(lines) * int(f.size * 1.16)
        im, pad = glass(w, h)
        im = im.copy(); d = ImageDraw.Draw(im)
        d.text((pad + 52, pad + 34), "PARENTS ASK US", font=D.font(D.F_UI, 28), fill=D.ORANGE_D)
        for i, ln in enumerate(lines):
            d.text((pad + 52, pad + 78 + i * int(f.size * 1.16)), ln, font=f, fill=INK)
        k = 1 if first else D.ease_out(t / 0.5)
        D.paste(fr, im, W / 2, 330 + h / 2 + (1 - k) * 40, 1, k)
    elif lay == "number":
        n, tot = s.get("params", {}).get("n", 1), s.get("params", {}).get("total", 3)
        k = 1 if first else D.back(t / 0.45)
        num = D.cached(("bignum", n, tot), lambda: _bignum(n, tot))
        D.paste(fr, num, MX + num.width / 2, 330, 0.7 + 0.3 * k, min(1, 1 if first else t / 0.2))
        D.headline(fr, txt, hl, t - 0.15, y=470, dark=True, size=88, instant=first)
    elif lay == "quote":
        f = D.font(D.F_BLACK, 74 if len(txt) < 40 else 62)
        lines = D.text_lines(txt, f, W - 2 * MX - 40)[:4]
        d = ImageDraw.Draw(fr)
        a = 1 if first else min(1, t / 0.4)
        d.text((MX - 6, 520), "“", font=D.font(D.F_BLACK, 260), fill=ORANGE + (int(255 * a),))
        for i, ln in enumerate(lines):
            lt = 9 if first else t - 0.25 - 0.12 * i
            if lt > 0:
                d.text((MX, 760 + i * int(f.size * 1.18) + (1 - D.ease_out(lt / 0.4)) * 18), ln, font=f,
                       fill=(255, 255, 255, int(255 * min(1, lt / 0.3))))
        src = s.get("params", {}).get("source")
        if src and (first or t > 0.9):
            d.text((MX, 790 + len(lines) * int(f.size * 1.18)), "— " + src, font=D.font(D.F_UI2, 38), fill=(235, 200, 170))


def _bignum(n, tot):
    f, fs = D.font(D.F_BLACK, 170), D.font(D.F_BLACK, 60)
    a, b = f"{n}", f"/{tot}"
    im = Image.new("RGBA", (int(f.getlength(a) + fs.getlength(b) + 24), 210), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((0, 0), a, font=f, fill=ORANGE)
    d.text((f.getlength(a) + 12, 98), b, font=fs, fill=(235, 230, 240))
    return im


# ----------------------------------------------------------------------- overlays (glass cards)
def overlay(fr, s, t, dur, ctx):
    ov = s.get("overlay", "none"); p = s.get("params", {})
    if ov == "chart" and ctx.get("progress"):
        progress_chart(fr, ctx["progress"], t, dur)
    elif ov == "ladder":
        ladder(fr, p.get("from_level"), p.get("to_level"), t, dur)
    elif ov == "key_card" and p.get("key"):
        key_badge(fr, p, t)
    elif ov == "stat" and p.get("value"):
        stat(fr, p["value"], p.get("label", ""), t)
    elif ov == "list" and p.get("items"):
        items(fr, p["items"][:3], t, dur)


def _curve(a, b, n=60, seed=0):
    """Smooth, monotone-ish improvement curve from a to b (illustrative shape; real start and end values)."""
    rng = random.Random(seed)
    xs = np.linspace(0, 1, n)
    base = a + (b - a) * (1 - (1 - xs) ** 1.6)
    wob = np.array([rng.uniform(-1, 1) for _ in xs]) * (b - a) * 0.025
    wob = np.convolve(wob, np.ones(5) / 5, "same"); wob[0] = wob[-1] = 0
    ys = np.maximum.accumulate(base + wob * (1 - xs))
    ys[0], ys[-1] = a, b
    return xs, ys


def progress_chart(fr, prog, t, dur):
    a, b, period = prog["from"], prog["to"], prog.get("period", "")
    w, h = W - 2 * MX, 720
    im, pad = glass(w, h)
    im = im.copy(); d = ImageDraw.Draw(im)
    d.text((pad + 50, pad + 40), "RATING PROGRESS", font=D.font(D.F_UI, 30), fill=D.INK2)
    x0, x1, y0, y1 = pad + 70, pad + w - 70, pad + h - 120, pad + 210
    lo, hi = a - (b - a) * 0.15, b + (b - a) * 0.12
    Y = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    for v in (a, b):
        d.line([(x0, Y(v)), (x1, Y(v))], fill=(225, 220, 214), width=2)
    xs, ys = _curve(a, b, seed=a * 7 + b)
    k = D.ease_in_out((t - 0.4) / max(0.8, dur - 1.6))
    m = max(2, int(k * len(xs)))
    pts = [(x0 + (x1 - x0) * x, Y(y)) for x, y in zip(xs[:m], ys[:m])]
    if len(pts) > 1:
        area = pts + [(pts[-1][0], y0), (pts[0][0], y0)]
        fill = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(fill).polygon(area, fill=ORANGE + (40,))
        im.alpha_composite(fill)
        d = ImageDraw.Draw(im)
        d.line(pts, fill=ORANGE, width=10, joint="curve")
        tx, ty = pts[-1]
        d.ellipse([tx - 16, ty - 16, tx + 16, ty + 16], fill=WHITE, outline=ORANGE, width=8)
    cur = int(a + (b - a) * k) if k < 1 else b
    d.text((pad + w - 50, pad + 30), f"{cur}", font=D.font(D.F_BLACK, 96), fill=INK, anchor="ra")
    d.text((x0, y0 + 26), str(a), font=D.font(D.F_UI, 32), fill=D.INK2)
    d.text((x0 + 86, y0 + 26), "start", font=D.font(D.F_UI2, 28), fill=D.INK2)
    if period:
        d.text((x1, y0 + 26), period, font=D.font(D.F_UI, 32), fill=D.INK2, anchor="ra")
    if k >= 1:
        badge = D.chip(f"+{b - a} points", 38, icon="check")
        im.alpha_composite(badge, (pad + 40, pad + 100))
    d.text((pad + 50, pad + h - 48), "Real student result · illustrative curve", font=D.font(D.F_UI2, 22), fill=(160, 155, 150))
    e = D.ease_out(t / 0.5)
    D.paste(fr, im, W / 2, 1000 + (1 - e) * 60, 1, min(1, t / 0.25))


def ladder(fr, a, b, t, dur):
    """The 6-level Learning Path as a ladder parents understand like school grades. a/b = level index 0..5."""
    w, rh = W - 2 * MX, 108
    h = 120 + rh * 6
    im, pad = glass(w, h)
    im = im.copy(); d = ImageDraw.Draw(im)
    d.text((pad + 50, pad + 38), "OUR 6-LEVEL LEARNING PATH", font=D.font(D.F_UI, 28), fill=D.INK2)
    climb = None
    if a is not None and b is not None:
        climb = a + (b - a) * D.ease_in_out((t - 0.9) / max(0.8, dur - 2.0))
    for i, (name, rng_) in enumerate(LEVELS):
        y = pad + 100 + (5 - i) * rh
        lt = t - 0.15 * i
        if lt <= 0:
            continue
        on = climb is not None and abs(climb - i) < 0.5
        col = ORANGE if on else (246, 242, 237)
        d.rounded_rectangle([pad + 40, y + 10, pad + w - 40, y + rh - 10], radius=22, fill=col)
        d.text((pad + 74, y + rh / 2), f"{i + 1}", font=D.font(D.F_BLACK, 44), fill=WHITE if on else ORANGE, anchor="lm")
        d.text((pad + 140, y + rh / 2), name, font=D.font(D.F_UI, 38), fill=WHITE if on else INK, anchor="lm")
        d.text((pad + w - 70, y + rh / 2), rng_, font=D.font(D.F_UI2, 32), fill=WHITE if on else D.INK2, anchor="rm")
    e = D.ease_out(t / 0.5)
    D.paste(fr, im, W / 2, 960 + (1 - e) * 50, 1, min(1, t / 0.25))


def key_badge(fr, p, t):
    w = W - 2 * MX
    f = D.font(D.F_BLACK, 54)
    lines = D.text_lines(p.get("title", ""), f, w - 120)[:3]
    h = 150 + 64 * len(lines)
    im, pad = glass(w, h, dark=True)
    im = im.copy()
    d = ImageDraw.Draw(im)
    tx = pad + 60
    d.rounded_rectangle([pad + 28, pad + 40, pad + 36, pad + h - 40], 4, fill=ORANGE)     # accent bar
    d.text((tx, pad + 46), "THE CHESSTALENTSFACTORY METHOD", font=D.font(D.F_UI, 30), fill=ORANGE)
    for i, ln in enumerate(lines):
        d.text((tx, pad + 100 + i * 64), ln, font=f, fill=WHITE)
    e = D.ease_out(t / 0.5)
    D.paste(fr, im, W / 2, 1150 + (1 - e) * 60, 1, min(1, t / 0.25))


def stat(fr, value, label, t):
    w, h = 720, 330
    im, pad = glass(w, h)
    im = im.copy(); d = ImageDraw.Draw(im)
    d.text((pad + w / 2, pad + 140), value, font=D.font(D.F_BLACK, 150), fill=ORANGE, anchor="mm")
    for i, ln in enumerate(D.text_lines(label.upper(), D.font(D.F_UI, 34), w - 80)[:2]):
        d.text((pad + w / 2, pad + 250 + i * 42), ln, font=D.font(D.F_UI, 34), fill=INK, anchor="mm")
    k = D.back(t / 0.5)
    D.paste(fr, im, W / 2, 1080, 0.85 + 0.15 * k, min(1, t / 0.2))


def items(fr, its, t, dur):
    step = max(0.45, min(0.9, (dur - 1.4) / max(1, len(its))))
    for i, it in enumerate(its):
        lt = t - (0.4 + i * step)
        if lt < 0:
            continue
        ch = D.chip(it, 46, icon="check")
        k = D.ease_out(lt / 0.5)
        D.paste(fr, ch, MX - 20 + ch.width / 2 - (1 - k) * 80, 820 + i * 175, 1, min(1, lt / 0.25))
