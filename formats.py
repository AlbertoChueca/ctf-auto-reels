"""Shared premium system for the faceless formats (text reels, chat reels, carousels, challenges).

Design direction: "quiet luxury" - a dark, cinematic chess set (real positions, shallow depth of field, warm key
light) behind big, confident type. One accent colour (CTF orange). Nothing that looks like clip-art or stock.
Sound: a warm, real-sounding piano/bass/soft-kick bed (or your own tracks in assets/music/), mastered to a
consistent loudness. No noise-based effects anywhere.

Everything here is pure code (PIL + numpy + ffmpeg): no image or video AI, so nothing looks "generated".
"""
import glob, hashlib, io, json, math, os, random, re, subprocess, time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import brand

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 30, 48000
FD = os.path.join(HERE, "fonts")
F_BLACK = os.path.join(FD, "Montserrat-Black.ttf")
F_XB = os.path.join(FD, "Montserrat-ExtraBold.ttf")
F_UI = os.path.join(FD, "Inter-Bold.ttf")
F_UI2 = os.path.join(FD, "Inter-SemiBold.ttf")

ORANGE = brand.ORANGE
ORANGE_SOFT = (255, 168, 92)
CREAM = (246, 240, 232)
MUTED = (176, 170, 164)
INK = (14, 13, 16)
MX = 84                      # side margin
SAFE_TOP, SAFE_BOTTOM = 250, 420   # keep text clear of the Instagram UI
LOG = os.path.join(HERE, "formats_log.json")
TOPICS = os.path.join(HERE, "parent_topics.json")


# ======================================================================= small utils
_cache = {}


def cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def font(path, size):
    return cached(("font", path, size), lambda: ImageFont.truetype(path, size))


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_out(t): t = clamp(t); return t * t * (3 - 2 * t)
def back(t, s=1.3): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2


def alpha(im, a):
    if a >= 1:
        return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def paste(fr, im, cx, cy, scale=1.0, a=1.0):
    if a <= 0.01:
        return
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    fr.alpha_composite(alpha(im, a), (int(cx - im.width / 2), int(cy - im.height / 2)))


def shadow_of(im, blur=24, a=150, dy=16):
    sh = Image.new("RGBA", (im.width + 4 * blur, im.height + 4 * blur + dy), (0, 0, 0, 0))
    m = im.getchannel("A").point(lambda v: int(v * a / 255))
    blk = Image.new("RGBA", im.size, (0, 0, 0, 255)); blk.putalpha(m)
    sh.alpha_composite(blk, (2 * blur, 2 * blur + dy))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(im, (2 * blur, 2 * blur))
    return sh


# ======================================================================= chess pieces + boards
LIGHT_SQ, DARK_SQ = (236, 222, 200), (168, 116, 78)          # warm maple / walnut
HL = (245, 128, 32)


def piece_img(symbol, size):
    def mk():
        import chess, chess.svg, cairosvg
        svg = chess.svg.piece(chess.Piece.from_symbol(symbol), size=size)
        return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=size,
                                                      output_height=size))).convert("RGBA")
    return cached(("piece", symbol, size), mk)


def board_img(board, size=880, flip=False, highlight=(), arrows=(), coords=True, dim=None, hide=()):
    """Clean, premium board (python-chess Board). highlight: squares; arrows: [(from, to)]; dim: squares to fade."""
    import chess
    sq = size // 8
    im = Image.new("RGBA", (sq * 8, sq * 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for r in range(8):
        for f in range(8):
            x, y = f * sq, r * sq
            light = (r + f) % 2 == 0
            d.rectangle([x, y, x + sq, y + sq], fill=LIGHT_SQ if light else DARK_SQ)
    def xy(s):
        f, r = chess.square_file(s), chess.square_rank(s)
        return ((7 - f) if flip else f) * sq, (r if flip else 7 - r) * sq
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    for s in highlight:
        x, y = xy(s); od.rectangle([x, y, x + sq, y + sq], fill=HL + (120,))
    im.alpha_composite(ov)
    if coords:
        fc = font(F_UI, max(14, sq // 6))
        for i in range(8):
            fl = "abcdefgh"[7 - i if flip else i]; rk = str(i + 1 if flip else 8 - i)
            d.text((i * sq + sq - fc.size * 0.9, 8 * sq - fc.size * 1.35), fl, font=fc,
                   fill=DARK_SQ if (7 + i) % 2 == 0 else LIGHT_SQ)
            d.text((6, i * sq + 4), rk, font=fc, fill=DARK_SQ if i % 2 == 0 else LIGHT_SQ)
    for s, p in board.piece_map().items():
        if s in hide:
            continue
        x, y = xy(s)
        pi = piece_img(p.symbol(), sq)
        if dim and s in dim:
            pi = alpha(pi, 0.25)
        im.alpha_composite(pi, (x, y))
    for a, b in arrows:
        draw_arrow(im, xy(a), xy(b), sq)
    return im


def square_xy(s, sq, flip=False):
    import chess
    f, r = chess.square_file(s), chess.square_rank(s)
    return ((7 - f) if flip else f) * sq, (r if flip else 7 - r) * sq


def draw_arrow(im, a, b, sq, color=(245, 128, 32, 230)):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    x0, y0 = a[0] + sq / 2, a[1] + sq / 2; x1, y1 = b[0] + sq / 2, b[1] + sq / 2
    ang = math.atan2(y1 - y0, x1 - x0); L = math.hypot(x1 - x0, y1 - y0)
    hl = sq * 0.42; w = sq * 0.17
    ex, ey = x1 - math.cos(ang) * hl * 0.9, y1 - math.sin(ang) * hl * 0.9
    d.line([(x0 + math.cos(ang) * sq * 0.2, y0 + math.sin(ang) * sq * 0.2), (ex, ey)], fill=color, width=int(w))
    p1 = (x1, y1)
    p2 = (ex + math.cos(ang + math.pi / 2) * hl * 0.55, ey + math.sin(ang + math.pi / 2) * hl * 0.55)
    p3 = (ex + math.cos(ang - math.pi / 2) * hl * 0.55, ey + math.sin(ang - math.pi / 2) * hl * 0.55)
    d.polygon([p1, p2, p3], fill=color)
    im.alpha_composite(ov)


def framed_board(board_im, pad=26):
    """Board inside a dark walnut frame with a soft shadow."""
    w, h = board_im.width + 2 * pad, board_im.height + 2 * pad
    fr = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(fr)
    d.rounded_rectangle([0, 0, w, h], radius=22, fill=(46, 30, 20))
    d.rounded_rectangle([3, 3, w - 3, h - 3], radius=20, outline=(92, 62, 40), width=2)
    fr.alpha_composite(board_im, (pad, pad))
    return shadow_of(fr, blur=34, a=170, dy=26)


# ======================================================================= cinematic background
FAMOUS = [   # real positions (public domain games) used as the out-of-focus set behind the text
    "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
    "rnbqkb1r/pp2pppp/3p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R b KQkq - 2 5",
    "r2q1rk1/pp2bppp/2n1pn2/3p4/3P4/2NBPN2/PP3PPP/R2Q1RK1 w - - 0 10",
    "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7",
    "rnbqk2r/ppp1bppp/4pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R w KQkq - 2 5",
    "2r2rk1/pp1bqppp/2n1pn2/3p4/3P4/P1NBPN2/1PQ2PPP/R4RK1 w - - 3 13",
]
BGW, BGH = int(W * 1.18), int(H * 1.18)


def _perspective(im, out_w, out_h, tilt=0.62, squash=0.52):
    """Tilt a top-down board away from the camera (a real 3D look, done with a projective transform)."""
    w, h = im.size
    inset = w * tilt / 2
    # destination quad corners (where the board corners land): top edge narrower
    dst = [(inset, 0), (w - inset, 0), (w, h * squash), (0, h * squash)]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]; B += [u, v]
    coeffs = np.linalg.solve(np.array(A, float), np.array(B, float))
    out = im.transform((w, int(h * squash)), Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)
    return out.resize((out_w, int(out_w * out.height / out.width)), Image.LANCZOS)


def cinematic_bg(seed, mood="dark"):
    """A dark, shallow-depth-of-field shot of a real chess position under a warm key light (cached per seed)."""
    def mk():
        import chess
        rng = random.Random(seed)
        b = chess.Board(rng.choice(FAMOUS))
        top = board_img(b, size=1600, coords=False)
        persp = _perspective(top, int(BGW * 1.7), 0)
        bg = Image.new("RGBA", (BGW, BGH), (12, 11, 13, 255))
        # vertical gradient + warm glow (key light)
        g = np.linspace(0, 1, BGH)[:, None]
        base = np.zeros((BGH, BGW, 3), np.float32)
        c0, c1 = np.array([22, 18, 18]), np.array([8, 8, 10])
        base[:] = (c0 * (1 - g) + c1 * g)[:, None, :].reshape(BGH, 1, 3)
        bg = Image.fromarray(base.astype(np.uint8)).convert("RGBA")
        y = int(BGH * (0.54 if mood == "dark" else 0.58))
        bg.alpha_composite(persp, (int((BGW - persp.width) / 2 + rng.randint(-120, 120)), y))
        # depth of field: far part very blurred, near part a bit blurred
        far = bg.filter(ImageFilter.GaussianBlur(30)); near = bg.filter(ImageFilter.GaussianBlur(7))
        m = Image.fromarray((np.clip((np.linspace(0, 1, BGH) - 0.62) / 0.3, 0, 1)[:, None] * 255)
                            .repeat(BGW, 1).astype(np.uint8))
        bg = Image.composite(near, far, m)
        # darken for legibility, warm glow from the top-right, vignette
        arr = np.asarray(bg).astype(np.float32)
        yy, xx = np.mgrid[0:BGH, 0:BGW]
        glow = np.exp(-(((xx - BGW * 0.72) / (BGW * 0.55)) ** 2 + ((yy - BGH * 0.42) / (BGH * 0.35)) ** 2))
        vig = 1 - 0.55 * np.clip(((xx - BGW / 2) / (BGW * 0.62)) ** 2 + ((yy - BGH / 2) / (BGH * 0.62)) ** 2, 0, 1)
        light = 0.18 + 0.55 * np.exp(-(((xx - BGW * 0.6) / (BGW * 0.5)) ** 2 + ((yy - BGH * 0.78) / (BGH * 0.22)) ** 2))
        arr[..., :3] = arr[..., :3] * light[..., None] * vig[..., None] + glow[..., None] * np.array([60, 28, 6]) * 0.5
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    return cached(("cbg", seed, mood), mk)


def draw_bg(fr, seed, t, total, mood="dark"):
    """Slow push-in + drift over the whole reel (calm, cinematic)."""
    bg = cinematic_bg(seed, mood)
    k = ease_in_out(t / max(1.0, total))
    s = 1.0 - 0.07 * k
    cw, ch = int(BGW * s), int(BGH * s)
    ox = int((BGW - cw) * (0.35 + 0.3 * k)); oy = int((BGH - ch) * (0.6 - 0.2 * k))
    crop = bg.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.BILINEAR)
    fr.paste(crop, (0, 0))


# ======================================================================= type
def wrap(words, f, maxw):
    lines, cur = [], []
    for w in words:
        test = " ".join(x for x, _ in cur + [(w, 0)])
        if cur and f.getlength(test) > maxw:
            lines.append(cur); cur = []
        cur.append((w, 0))
    if cur:
        lines.append(cur)
    return [[w for w, _ in ln] for ln in lines]


def _norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def kinetic(fr, text, highlight, t, cy, size=84, maxw=W - 2 * MX, color=CREAM, f_path=F_BLACK, per_word=0.075,
            align="left", out_t=None, line_gap=1.12):
    """Words rise in one by one (staggered), highlighted words get an orange marker. Returns block height."""
    f = font(f_path, size)
    hl = {_norm(h) for x in (highlight or []) for h in str(x).split()}
    lines = wrap(str(text).split(), f, maxw)
    lh = int(size * line_gap)
    top = cy - len(lines) * lh / 2
    fade_out = 1.0 if out_t is None else clamp(1 - (t - out_t) / 0.25)
    k = 0
    d = ImageDraw.Draw(fr)
    for li, ln in enumerate(lines):
        widths = [f.getlength(w + " ") for w in ln]
        lw = sum(widths) - f.getlength(" ")
        x = MX if align == "left" else (W - lw) / 2
        y = top + li * lh
        for wi, w in enumerate(ln):
            lt = t - k * per_word; k += 1
            if lt <= 0:
                x += widths[wi]; continue
            e = ease_out(lt / 0.35); a = clamp(lt / 0.22) * fade_out
            dy = (1 - e) * size * 0.35
            on = _norm(w) in hl
            wim = cached(("w", w, size, f_path, on, color), lambda w=w, on=on: _word(w, f, on, color))
            fr.alpha_composite(alpha(wim, a), (int(x - 14), int(y + dy - 8)))
            x += widths[wi]
    return len(lines) * lh


def _word(w, f, on, color):
    tw = int(f.getlength(w)) + 28; th = int(f.size * 1.32) + 8
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if on:
        d.rounded_rectangle([4, int(th * 0.12), tw - 4, th - int(th * 0.08)], radius=12, fill=ORANGE + (255,))
        d.text((14, 6), w, font=f, fill=(255, 255, 255))
    else:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((14, 10), w, font=f, fill=(0, 0, 0, 170))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        ImageDraw.Draw(im).text((14, 6), w, font=f, fill=color)
    return im


def label(text, size=34, fg=ORANGE, f_path=F_UI, tracking=4):
    """Small caps label, letter-spaced (editorial)."""
    f = font(f_path, size)
    s = str(text).upper()
    w = int(sum(f.getlength(c) + tracking for c in s)) + 10
    im = Image.new("RGBA", (w, int(size * 1.4)), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 4
    for c in s:
        d.text((x, 2), c, font=f, fill=fg); x += f.getlength(c) + tracking
    return im


def brand_mark(fr, a=1.0, y=118):
    lg = cached("bm", lambda: _brand_mark())
    paste(fr, lg, W / 2, y, 1, a)


def _brand_mark():
    try:
        lg = brand.logo(300)
    except Exception:
        lg = label(brand.NAME, 30, CREAM)
    pad = 18
    im = Image.new("RGBA", (lg.width + 2 * pad, lg.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, im.width, im.height], radius=im.height // 2, fill=(255, 255, 255, 235))
    im.alpha_composite(lg, (pad, pad))
    return im


def progress(fr, t, total):
    d = ImageDraw.Draw(fr)
    x0, x1, y = MX, W - MX, 60
    d.rounded_rectangle([x0, y, x1, y + 6], radius=3, fill=(255, 255, 255, 50))
    d.rounded_rectangle([x0, y, x0 + (x1 - x0) * clamp(t / total), y + 6], radius=3, fill=ORANGE)


def button(text, size=54):
    f = font(F_BLACK, size)
    w, h = int(f.getlength(text)) + 110, int(size * 2.25)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=ORANGE)
    d.text((w / 2, h / 2 + 2), text, font=f, fill=(255, 255, 255), anchor="mm")
    return shadow_of(im, 22, 140, 12)


def cta_card(fr, t, seed, total, mode="keyword", line=None):
    """Closing card: one clear action. mode keyword -> 'Comment PLAN'."""
    draw_bg(fr, seed + 7, t + 30, total + 30)
    ov = Image.new("RGBA", (W, H), (8, 8, 10, 120)); fr.alpha_composite(ov)
    lg = cached("ctalogo", lambda: brand.logo_card(560))
    paste(fr, lg, W / 2, 560, 0.94 + 0.06 * back(t / 0.5), clamp(t / 0.3))
    title = line or "Want the training plan we use with our students?"
    kinetic(fr, title, ["plan"], t - 0.3, 900, size=70, align="center", per_word=0.05)
    if t > 1.0:
        kw = brand.KEYWORD
        b = cached(("btn", kw), lambda: button(f'Comment "{kw}"'))
        pulse = 1 + 0.02 * math.sin((t - 1.6) * 5) if t > 1.6 else 0.85 + 0.15 * back((t - 1.0) / 0.5)
        paste(fr, b, W / 2, 1160, pulse, clamp((t - 1.0) / 0.25))
    if t > 1.4:
        sub = cached("ctasub", lambda: _plain("We'll send you our free training video for parents", font(F_UI2, 40), MUTED))
        paste(fr, sub, W / 2, 1300, 1, clamp((t - 1.4) / 0.4))


def _plain(s, f, col):
    im = Image.new("RGBA", (int(f.getlength(s)) + 12, int(f.size * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((6, 0), s, font=f, fill=col)
    return im


# ======================================================================= music (real-sounding, tonal, mastered)
MUSIC_DIR = os.path.join(HERE, "assets", "music")
PROGS = [  # (root midi of each chord, chord type), bpm  - lofi / neo-soul voicings
    ([(53, "maj7"), (52, "m7"), (50, "m7"), (48, "maj7")], 78),
    ([(57, "m7"), (53, "maj7"), (48, "maj7"), (55, "7sus")], 84),
    ([(50, "m9"), (55, "9"), (48, "maj9"), (57, "m7")], 72),
    ([(48, "maj9"), (57, "m7"), (53, "maj7"), (55, "6")], 88),
    ([(52, "m7"), (57, "m9"), (50, "m7"), (55, "maj7")], 76),
]
CH = {"maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "m9": [0, 3, 7, 10, 14], "9": [0, 4, 7, 10, 14],
      "maj9": [0, 4, 7, 11, 14], "7sus": [0, 5, 7, 10], "6": [0, 4, 7, 9]}


def _hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def _piano(f, dur, vel=0.5):
    """Additive piano-ish tone: inharmonic partials, hammer attack, two-stage decay, slight detune chorus."""
    n = int(dur * SR); t = np.arange(n) / SR
    out = np.zeros(n)
    for k, amp in enumerate([1.0, 0.42, 0.22, 0.12, 0.06, 0.03], start=1):
        fk = f * k * math.sqrt(1 + 0.0004 * k * k)
        dec = np.exp(-t * (1.1 + 0.9 * k)) * 0.75 + np.exp(-t * (5 + 3 * k)) * 0.25
        out += amp * dec * (np.sin(2 * np.pi * fk * t) + 0.5 * np.sin(2 * np.pi * fk * 1.0016 * t + 0.3))
    att = np.clip(t / 0.004, 0, 1)
    rel = np.clip((dur - t) / 0.08, 0, 1)
    return out * att * rel * vel * 0.18


def _reverb(x, seconds=1.8, mix=0.22, seed=3):
    """Smooth hall reverb (sparse decaying taps, low-passed tail) via FFT convolution."""
    rng = np.random.RandomState(seed)
    n = int(seconds * SR)
    ir = np.zeros(n)
    taps = np.sort(rng.randint(int(0.012 * SR), n, 900))
    ir[taps] = rng.uniform(-1, 1, len(taps)) * np.exp(-taps / SR * (6.9 / seconds))
    k = int(SR / 3500)
    ir = np.convolve(ir, np.ones(k) / k, "same")                    # dark, smooth tail (no hiss)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    L = len(x) + n
    nfft = 1 << (L - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(x)]
    return x * (1 - mix) + wet * mix * 0.9


def synth_bed(total, seed=0, energy=0.6):
    """Warm lo-fi/neo-soul bed: piano chords + arpeggio, round sub bass, soft tonal kick. ~-18 dBFS."""
    rng = random.Random(seed)
    prog, bpm = PROGS[seed % len(PROGS)]
    beat = 60.0 / bpm; bar = beat * 4
    n = int((total + 2) * SR)
    mus = np.zeros(n); bass = np.zeros(n); drums = np.zeros(n)
    def put(buf, x, at):
        a = int(at * SR)
        if a >= n: return
        b = min(n, a + len(x)); buf[a:b] += x[:b - a]
    nb = int(total / bar) + 2
    for i in range(nb):
        root, kind = prog[i % len(prog)]
        t0 = i * bar
        notes = [root + 12 + iv for iv in CH[kind]]
        for j, m in enumerate(notes):                                 # soft strum
            put(mus, _piano(_hz(m), bar + 0.6, 0.42), t0 + j * 0.018)
        arp = notes[1:] + [notes[0] + 12]
        for k in range(8):                                            # gentle 8th-note arpeggio, humanised
            if rng.random() < 0.28:
                continue
            m = arp[(k * 3 + i) % len(arp)] + 12
            put(mus, _piano(_hz(m), beat * 1.4, 0.2 + 0.08 * rng.random()), t0 + k * beat / 2 + rng.uniform(0, 0.012))
        for k, ln in ((0, 1.5), (2.5, 1.5)):                          # round sub bass
            tt = np.arange(int(ln * beat * SR)) / SR
            env = np.clip(tt / 0.01, 0, 1) * np.exp(-tt * 1.8)
            put(bass, 0.16 * env * (np.sin(2 * np.pi * _hz(root - 12) * tt) + 0.25 * np.sin(4 * np.pi * _hz(root - 12) * tt)),
                t0 + k * beat)
        if energy > 0.3:
            for k in range(4):                                        # tonal kick on 1 and 3, soft click on 2 and 4
                tt = np.arange(int(0.35 * SR)) / SR
                if k % 2 == 0:
                    f = 48 + 70 * np.exp(-tt * 30)
                    put(drums, 0.30 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9), t0 + k * beat)
                else:
                    put(drums, 0.05 * np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt * 90), t0 + k * beat)
    mix = _reverb(mus, 2.2, 0.28) + bass + drums * energy
    k = int(SR / 9000)
    mix = np.convolve(mix, np.ones(k) / k, "same")                    # gentle high cut ("warm tape")
    mix = mix[:int(total * SR)]
    t = np.arange(len(mix)) / SR
    mix *= np.clip(t / 1.0, 0, 1) * np.clip((total - t) / 1.8, 0, 1)
    return (mix / (np.max(np.abs(mix)) + 1e-9) * 0.5).astype(np.float32)


def _decode(path, total):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).copy()
    if len(x) < SR * 4:
        return None
    need = int(total * SR)
    start = int(min(max(0, len(x) - need), len(x) * 0.12)) if len(x) > need else 0
    x = np.tile(x, int(np.ceil(need / len(x))) + 1)[start:start + need] if len(x) < need else x[start:start + need]
    t = np.arange(len(x)) / SR
    x = x * np.clip(t / 0.8, 0, 1) * np.clip((total - t) / 2.0, 0, 1)
    return (x / (np.max(np.abs(x)) + 1e-9) * 0.5).astype(np.float32)


def music(total, seed=0, energy=0.6):
    """Your own licensed tracks in assets/music/ (mp3/wav/m4a) when present (least recently used), else the synth."""
    files = sorted(glob.glob(os.path.join(MUSIC_DIR, "*.mp3")) + glob.glob(os.path.join(MUSIC_DIR, "*.wav")) +
                   glob.glob(os.path.join(MUSIC_DIR, "*.m4a")))
    if files:
        used = {r.get("music"): i for i, r in enumerate(recent(60)) if r.get("music")}
        f = min(files, key=lambda p: (used.get(os.path.basename(p), -1), random.Random(seed).random()))
        x = _decode(f, total)
        if x is not None:
            return x, os.path.basename(f)
    return synth_bed(total, seed, energy), f"synth-{seed % len(PROGS)}"


def vo_compress(a, thr_db=-20.0, ratio=3.0, att=0.008, rel=0.12, sr=None):
    """Gentle voice compressor: evens out loud and soft words so every word is clear over the music."""
    sr = sr or SR
    a = a.astype(np.float32)
    if len(a) < 100:
        return a
    x = np.abs(a).astype(np.float64)
    ka, kr = np.exp(-1.0 / (att * sr)), np.exp(-1.0 / (rel * sr))
    env = np.empty_like(x); e = 0.0
    for i in range(0, len(x), 64):
        blk = x[i:i + 64].max()
        e = ka * e + (1 - ka) * blk if blk > e else kr * e + (1 - kr) * blk
        env[i:i + 64] = e
    ref = np.max(x) + 1e-9
    db = 20 * np.log10(env / ref + 1e-9)
    over = np.maximum(0.0, db - thr_db)
    gain = 10 ** (-(over - over / ratio) / 20)
    k = max(1, int(0.005 * sr))
    gain = np.convolve(gain, np.ones(k) / k, "same")
    y = a * gain
    return (y / (np.max(np.abs(y)) + 1e-9) * 0.9).astype(np.float32)


def master(mix, speech_mask=None, target_db=-16.0, ceiling=0.89, sr=None):
    """Final master: DC/rumble removed, consistent loudness (~-14/-16 LUFS like the platforms), soft limiter."""
    sr = sr or SR
    m = mix.astype(np.float64)
    k = int(sr / 40)
    m = m - np.convolve(m, np.ones(k) / k, "same")
    sel = m[speech_mask] if speech_mask is not None and speech_mask.any() else m[np.abs(m) > 1e-4]
    rms = np.sqrt(np.mean(sel ** 2)) + 1e-9 if len(sel) else 1.0
    m = m * (10 ** (target_db / 20) / rms)
    knee = ceiling * 0.8
    a = np.abs(m); over = a > knee
    m[over] = np.sign(m[over]) * (knee + (ceiling - knee) * np.tanh((a[over] - knee) / (ceiling - knee)))
    return m.astype(np.float32)


def soft_tick(f=1500, vol=0.08):
    t = np.arange(int(0.07 * SR)) / SR
    return (vol * np.sin(2 * np.pi * f * t) * np.exp(-t * 70) * np.clip(t / 0.002, 0, 1)).astype(np.float32)


def bell(f=880, vol=0.12, dur=1.6):
    t = np.arange(int(dur * SR)) / SR
    s = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * d) for m, a, d in [(1, 1, 2.5), (2.01, .35, 4), (3.0, .12, 6)])
    return (vol * s * np.clip(t / 0.003, 0, 1)).astype(np.float32)


def swell(dur=0.7, vol=0.07):
    """Tonal riser into a transition (two gliding sines, no noise)."""
    n = int(dur * SR); t = np.arange(n) / SR
    f = 260 + 260 * (t / dur) ** 2
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    return (vol * s * (t / dur) ** 2 * np.clip((dur - t) / 0.05, 0, 1)).astype(np.float32)


# ======================================================================= encoding
def encode(frames, wav, out, w=W, h=H, fps=FPS):
    """frames: iterator of RGB(A) PIL images at w x h. High quality H.264 + AAC 192k (Instagram-friendly)."""
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-"] + (["-i", wav] if wav else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]) + [
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-crf", "19",
           "-maxrate", "8000k", "-bufsize", "12000k", "-g", str(fps * 2), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", "-use_editlist", "0", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames:
        p.stdin.write(fr.convert("RGB").tobytes())
    p.stdin.close(); p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg failed")
    return out


def write_wav(x, path):
    import soundfile as sf
    sf.write(path, np.clip(x, -1, 1), SR)
    return path


# ======================================================================= copy: topics, Gemini, honesty
def recent(n=40):
    try:
        return json.load(open(LOG))[-n:]
    except Exception:
        return []


def remember(entry):
    lg = recent(400) + [dict(entry, date=time.strftime("%Y-%m-%d"))]
    json.dump(lg[-400:], open(LOG, "w"), indent=0)


def topics():
    try:
        return json.load(open(TOPICS))["topics"]
    except Exception:
        return []


def pick_topic(fmt, seed=None):
    """Least recently used parent topic that suits this format (never the same topic within ~60 posts)."""
    ts = [t for t in topics() if fmt in t.get("formats", [fmt])] or topics()
    used = {r.get("topic"): i for i, r in enumerate(recent(400)) if r.get("topic")}
    rng = random.Random(seed)
    never = [t for t in ts if t["id"] not in used]
    if never:
        return rng.choice(never)
    return min(ts, key=lambda t: (used.get(t["id"], -1), rng.random()))


VOICE_RULES = """WRITING RULES (non-negotiable):
- Write like a calm, experienced coach texting an ambitious parent. Plain everyday English a parent who does NOT play
  chess understands immediately. No chess jargon, no notation, no method names, no acronyms, no "key #", no
  "deliberate practice", "bottleneck", "methodology", "high-performance", "unlock", "journey", "game changer".
- Specific, human moments beat abstractions: the car ride home, the tournament hall, homework time, the tablet at night.
- Short. Each line max 12 words. Contractions. No exclamation-mark hype. One emoji max in the caption, none on screen.
- Honest: no invented students, numbers, results or guarantees. Patterns coaches see, never promises."""


def ask_json(prompt, validate, temp=0.95, tries_per_model=2):
    """Gemini JSON with one repair round per model. validate(obj) -> obj or raises ValueError(reason)."""
    import make_story as MS
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set")
    last = None
    for model in MS.text_models(3):
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": temp}}
        for attempt in range(tries_per_model):
            txt = ""
            try:
                j = MS._post(model, body)
                txt = j["candidates"][0]["content"]["parts"][0]["text"]
                obj = json.loads(re.sub(r"^```(json)?|```$", "", txt.strip()))
                out = validate(obj)
                print(f"copy: {model}" + (" (repaired)" if attempt else ""), flush=True)
                return out
            except ValueError as e:
                last = e; print(f"copy: {model} rejected: {str(e)[:200]}", flush=True)
                body = {**body, "contents": body["contents"][:1] + [
                    {"role": "model", "parts": [{"text": txt or "{}"}]},
                    {"role": "user", "parts": [{"text": f"Rejected by our checks: {e}. Rewrite the whole JSON fixing "
                                                        "only that. Same schema."}]}]}
            except Exception as e:
                last = e; print(f"copy: {model}: {str(e)[:160]}", flush=True); break
    raise RuntimeError(f"copy failed: {last}")


JARGON = re.compile(r"\b(t-?t-?p|square\s*65|meta-?chess|key\s*#?\d+|bottleneck|methodology|deliberate practice|"
                    r"high-performance|unlock|game[- ]changer|journey|elo|fide|notation|tactic(s|al)? motif)\b", re.I)
SAN = re.compile(r"\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?)\b")


def check_text(texts, allow_san=False):
    """Honesty + plain-language checks for every on-screen/caption string. Raises ValueError."""
    import guard
    blob = " ".join(str(x) for x in texts)
    ok, bad = guard.claims_ok(re.sub(r"\b(?:age|aged|at|ages)\s+\d+\b", " ", blob))
    if not ok:
        raise ValueError(f"numbers that are not approved claims: {bad}")
    m = JARGON.search(blob)
    if m:
        raise ValueError(f"jargon a non-chess parent won't understand: '{m.group(0)}'")
    if not allow_san:
        s = [x for x in SAN.findall(blob) if re.search(r"[a-h][1-8]", x[0])]
        if s:
            raise ValueError(f"chess notation on screen: {s[0][0]}")


def caption(hook, body, cta_line=None, seed=0):
    rng = random.Random(seed)
    cta_line = cta_line or brand.cta("keyword")["caption"]
    return (f"{hook.strip()}\n\n{body.strip()}\n\n{cta_line}\n{brand.PARENT_LINE}\n\n" + " ".join(brand.hashtags(rng)))
