"""Drawing kit for the animated explainer reels ("neon figures" look, ChessTalentsFactory identity).

Everything is vector, drawn with cairo straight into the frame that goes to ffmpeg: glowing outlines, translucent
fills, faceless figures built from capsules (child = orange, parent = violet, coach = teal), chess props, panels,
word-by-word captions with boxed keywords and big neon labels. No image AI, no stock, no clip-art.

Coordinates: 1080 x 1920. Safe areas: captions y 250-400, label y 430-560, scene art y 600-1500.
"""
import io, math, os, random
import cairocffi as cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
FD = os.path.join(HERE, "fonts")
F_BLACK = os.path.join(FD, "Montserrat-Black.ttf")
F_XB = os.path.join(FD, "Montserrat-ExtraBold.ttf")
F_UI = os.path.join(FD, "Inter-Bold.ttf")
F_UI2 = os.path.join(FD, "Inter-SemiBold.ttf")

ORANGE = (245, 128, 32)
TEAL = (45, 226, 196)
PINK = (255, 72, 118)
VIOLET = (150, 124, 255)
GOLD = (255, 200, 80)
CREAM = (246, 240, 232)
MUTED = (150, 146, 164)
DIM = (92, 90, 110)
BG0, BG1 = (9, 9, 18), (19, 16, 32)
TONE = {"bad": PINK, "good": TEAL, "brand": ORANGE, "neutral": CREAM, "cool": VIOLET, "gold": GOLD}

TAU = math.tau


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in(t): t = clamp(t); return t ** 3
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def back(t, s=1.7): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2
def lerp(a, b, k): return a + (b - a) * k
def lerp2(p, q, k): return (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k)
def seg(t, a, b): return clamp((t - a) / max(1e-6, b - a))          # 0..1 progress of t inside [a, b]
def pulse(t, f=1.0): return 0.5 + 0.5 * math.sin(t * TAU * f)
def c01(c): return (c[0] / 255, c[1] / 255, c[2] / 255)
def mix(c, d, k): return tuple(c[i] + (d[i] - c[i]) * k for i in range(3))
def rot(v, a): return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))
def add(p, v): return (p[0] + v[0], p[1] + v[1])


def font(path, size, _c={}):
    k = (path, int(size))
    if k not in _c:
        _c[k] = ImageFont.truetype(path, int(size))
    return _c[k]


# ======================================================================= canvas
class K:
    """One frame. Thin helper over a cairo context with the neon vocabulary."""

    def __init__(self, surface=None):
        self.surface = surface or cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        self.c = cairo.Context(self.surface)
        self.c.set_line_cap(cairo.LINE_CAP_ROUND)
        self.c.set_line_join(cairo.LINE_JOIN_ROUND)

    # ---- state
    def push(self): self.c.save()
    def pop(self): self.c.restore()

    def camera(self, zoom=1.0, cx=W / 2, cy=H / 2, dx=0.0, dy=0.0, angle=0.0):
        """Zoom/pan/rotate everything drawn until pop()."""
        c = self.c
        c.translate(cx + dx, cy + dy); c.rotate(angle); c.scale(zoom, zoom); c.translate(-cx, -cy)

    # ---- paths
    def line(self, pts, closed=False):
        c = self.c
        c.new_path(); c.move_to(*pts[0])
        for p in pts[1:]:
            c.line_to(*p)
        if closed:
            c.close_path()

    def smooth(self, pts):
        """Catmull-Rom spline through pts."""
        c = self.c
        c.new_path(); c.move_to(*pts[0])
        P = [pts[0]] + list(pts) + [pts[-1]]
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
            c.curve_to(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                       p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1])

    def rrect(self, x, y, w, h, r):
        c = self.c
        r = min(r, w / 2, h / 2)
        c.new_path()
        c.arc(x + w - r, y + r, r, -TAU / 4, 0); c.arc(x + w - r, y + h - r, r, 0, TAU / 4)
        c.arc(x + r, y + h - r, r, TAU / 4, TAU / 2); c.arc(x + r, y + r, r, TAU / 2, TAU * 3 / 4)
        c.close_path()

    def circle(self, x, y, r):
        self.c.new_path(); self.c.arc(x, y, max(0.1, r), 0, TAU)

    def arc(self, x, y, r, a0, a1):
        self.c.new_path(); self.c.arc(x, y, max(0.1, r), a0, a1)

    # ---- ink
    def neon(self, color, w=6.0, a=1.0, glow=1.0, keep=False, hot=True):
        """Stroke the current path as a glowing tube."""
        c = self.c
        r, g, b = c01(color)
        if glow > 0:
            for m, al in ((7.5, 0.035), (4.6, 0.06), (2.6, 0.13)):
                c.set_source_rgba(r, g, b, al * a * glow); c.set_line_width(w * m); c.stroke_preserve()
        c.set_source_rgba(r, g, b, a); c.set_line_width(w); c.stroke_preserve()
        if hot and w >= 3:
            hr, hg, hb = c01(mix(color, (255, 255, 255), 0.65))
            c.set_source_rgba(hr, hg, hb, 0.55 * a); c.set_line_width(w * 0.3); c.stroke_preserve()
        if not keep:
            c.new_path()

    def stroke(self, color, w=3.0, a=1.0, keep=False, dash=None):
        c = self.c
        if dash:
            c.set_dash(dash)
        c.set_source_rgba(*c01(color), a); c.set_line_width(w)
        (c.stroke_preserve if keep else c.stroke)()
        if dash:
            c.set_dash([])

    def fill(self, color, a=1.0, keep=False):
        c = self.c
        c.set_source_rgba(*c01(color), a)
        (c.fill_preserve if keep else c.fill)()

    def glass(self, color, a=0.16, keep=True):
        """Translucent tinted fill (dark body with a hint of the outline colour)."""
        self.fill(mix(BG1, color, 0.22), 0.94, keep=True)
        self.fill(color, a * 0.25, keep=keep)

    def shape(self, color, w=5.0, a=1.0, fill_a=0.16, glow=1.0):
        """Fill + neon outline for the current path."""
        self.c.set_source_rgba(*c01(mix(BG1, color, 0.2)), 0.93 * a); self.c.fill_preserve()
        self.c.set_source_rgba(*c01(color), fill_a * 0.3 * a); self.c.fill_preserve()
        self.neon(color, w, a, glow)

    def glow_dot(self, x, y, r, color, a=1.0):
        c = self.c
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        cr = c01(color)
        g.add_color_stop_rgba(0, *cr, 0.55 * a); g.add_color_stop_rgba(0.4, *cr, 0.16 * a); g.add_color_stop_rgba(1, *cr, 0)
        c.set_source(g); c.new_path(); c.arc(x, y, r, 0, TAU); c.fill()

    def capsule(self, p, q, w, color, ow=4.5, a=1.0, glow=0.9, fill=None):
        """A limb: thick rounded segment with a neon outline."""
        c = self.c
        c.new_path(); c.move_to(*p); c.line_to(*q)
        r, g, b = c01(color)
        if glow > 0:
            for m, al in ((2.4, 0.05), (1.5, 0.10)):
                c.set_source_rgba(r, g, b, al * a * glow); c.set_line_width(w + ow * 2 * m * 1.6); c.stroke_preserve()
        c.set_source_rgba(r, g, b, a); c.set_line_width(w + ow * 2); c.stroke_preserve()
        c.set_source_rgba(*c01(fill or mix(BG1, color, 0.24)), 1.0 if a >= 1 else a); c.set_line_width(w); c.stroke()

    # ---- sprites (text and bitmaps rendered once with PIL, cached, then blitted)
    def sprite(self, spr, cx, cy, scale=1.0, a=1.0, angle=0.0, anchor="c"):
        if a <= 0.01 or spr is None:
            return
        c = self.c
        sw, sh = spr.get_width(), spr.get_height()
        c.save(); c.translate(cx, cy)
        if angle: c.rotate(angle)
        if scale != 1.0: c.scale(scale, scale)
        ox = {"c": -sw / 2, "l": 0, "r": -sw}[anchor]
        c.set_source_surface(spr, ox, -sh / 2)
        c.paint_with_alpha(clamp(a))
        c.restore()

    def text(self, s, cx, cy, size=44, color=CREAM, f=F_UI, a=1.0, scale=1.0, anchor="c", angle=0.0):
        self.sprite(text_sprite(str(s), size, color, f), cx, cy, scale, a, angle, anchor)

    def big(self, s, cx, cy, size=96, color=CREAM, a=1.0, scale=1.0, angle=0.0):
        self.sprite(neon_text(str(s), size, color), cx, cy, scale, a, angle)

    def bytes(self):
        self.surface.flush()
        return bytes(self.surface.get_data())

    def to_pil(self):
        self.surface.flush()
        arr = np.frombuffer(self.surface.get_data(), np.uint8).reshape(H, W, 4)
        return Image.fromarray(arr[..., [2, 1, 0]].copy())


# ======================================================================= sprites
_spr = {}


def _to_surface(im):
    """PIL RGBA -> cairo ARGB32 (premultiplied BGRA)."""
    arr = np.asarray(im.convert("RGBA")).astype(np.uint16)
    al = arr[..., 3:4]
    pre = (arr[..., :3] * al // 255).astype(np.uint8)
    out = np.dstack([pre[..., 2], pre[..., 1], pre[..., 0], arr[..., 3].astype(np.uint8)])
    buf = bytearray(out.tobytes())
    s = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, im.width, im.height, im.width * 4)
    s._keep = buf
    return s


def text_sprite(s, size, color=CREAM, f=F_UI):
    k = ("t", s, int(size), color, f)
    if k not in _spr:
        ft = font(f, size)
        w = int(ft.getlength(s)) + 16; h = int(size * 1.36) + 8
        im = Image.new("RGBA", (max(4, w), h), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((8, 4), s, font=ft, fill=tuple(int(v) for v in color) + (255,))
        _spr[k] = _to_surface(im)
    return _spr[k]


def text_w(s, size, f=F_UI):
    return font(f, size).getlength(s)


def neon_text(s, size, color=CREAM):
    """Big uppercase label: light core, coloured outline, soft glow (blurred once, cached)."""
    k = ("n", s, int(size), color)
    if k not in _spr:
        ft = font(F_BLACK, size)
        pad = int(size * 0.5)
        w = int(ft.getlength(s)) + 2 * pad; h = int(size * 1.3) + 2 * pad
        col = tuple(int(v) for v in color)
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((pad, pad), s, font=ft, fill=col + (255,), stroke_width=max(3, size // 14), stroke_fill=col + (255,))
        g1 = glow.filter(ImageFilter.GaussianBlur(size * 0.16))
        g2 = glow.filter(ImageFilter.GaussianBlur(size * 0.05))
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        g1.putalpha(g1.getchannel("A").point(lambda v: int(v * 0.55)))
        im.alpha_composite(g1); im.alpha_composite(g2)
        d = ImageDraw.Draw(im)
        d.text((pad, pad), s, font=ft, fill=tuple(int(v) for v in mix(BG0, color, 0.18)) + (255,),
               stroke_width=max(3, size // 15), stroke_fill=col + (255,))
        d.text((pad, pad), s, font=ft, fill=tuple(int(v) for v in mix(color, (255, 255, 255), 0.82)) + (255,))
        _spr[k] = _to_surface(im)
    return _spr[k]


def piece_sprite(symbol, size, color=CREAM):
    """Chess piece silhouette tinted with a neon colour (from the standard vector set)."""
    k = ("p", symbol, int(size), color)
    if k not in _spr:
        import chess, chess.svg, cairosvg
        svg = chess.svg.piece(chess.Piece.from_symbol(symbol.upper()), size=int(size))
        im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=int(size),
                                                    output_height=int(size)))).convert("RGBA")
        al = im.getchannel("A")
        lum = im.convert("L")
        edge = Image.eval(lum, lambda v: 255 - v)                       # dark lines of the drawing
        body = Image.new("RGBA", im.size, tuple(int(v) for v in mix(BG1, color, 0.3)) + (255,)); body.putalpha(al)
        line = Image.new("RGBA", im.size, tuple(int(v) for v in color) + (255,))
        line.putalpha(Image.composite(edge, Image.new("L", im.size, 0), al))
        pad = int(size * 0.25)
        out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
        gl = Image.new("RGBA", out.size, (0, 0, 0, 0)); gl.paste(line, (pad, pad), line)
        gl = gl.filter(ImageFilter.GaussianBlur(size * 0.06))
        out.alpha_composite(gl); out.alpha_composite(body, (pad, pad)); out.alpha_composite(line, (pad, pad))
        _spr[k] = _to_surface(out)
    return _spr[k]


def logo_sprite(width=210):
    k = ("logo", width)
    if k not in _spr:
        try:
            import brand
            lg = brand.logo(width)
            pad = 14
            im = Image.new("RGBA", (lg.width + 2 * pad, lg.height + 2 * pad), (0, 0, 0, 0))
            ImageDraw.Draw(im).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=im.height // 2, fill=(255, 255, 255, 235))
            im.alpha_composite(lg, (pad, pad))
            _spr[k] = _to_surface(im)
        except Exception:
            _spr[k] = text_sprite("ChessTalentsFactory", 30, CREAM)
    return _spr[k]


# ======================================================================= backgrounds (static layer per setting)
_bg = {}


def background(kind="lab", seed=0):
    """Static backdrop, drawn once per setting and reused for every frame of the scene."""
    key = (kind, seed)
    if key in _bg:
        return _bg[key]
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    k = K(s); c = k.c
    g = cairo.LinearGradient(0, 0, 0, H)
    top, bot = {"hall": ((10, 9, 22), (22, 14, 30)), "home": ((12, 10, 24), (26, 17, 28)),
                "road": ((7, 8, 20), (16, 12, 26)), "stage": ((12, 8, 20), (30, 16, 22))}.get(kind, (BG0, BG1))
    g.add_color_stop_rgb(0, *c01(top)); g.add_color_stop_rgb(1, *c01(bot))
    c.set_source(g); c.paint()
    rng = random.Random(seed * 131 + hash(kind) % 1000)
    if kind == "lab":                                   # dot grid, like graph paper under glass
        for y in range(40, H, 54):
            for x in range(27, W, 54):
                k.circle(x, y, 1.6); k.fill((255, 255, 255), 0.055)
    elif kind == "hall":                                # tournament hall: floor in perspective, rows of tables, banners
        hz = 930
        for i in range(-12, 13):
            k.line([(W / 2 + i * 30, hz), (W / 2 + i * 260, H)]); k.stroke(VIOLET, 2, 0.10)
        for j in range(9):
            y = hz + (H - hz) * (j / 9) ** 1.7
            k.line([(0, y), (W, y)]); k.stroke(VIOLET, 2, 0.10)
        for row in range(3):                            # distant tables with players (tiny silhouettes)
            y = hz - 20 - row * 62; sc = 1 - row * 0.2
            for i in range(-4, 5):
                x = W / 2 + i * 150 * sc + (row % 2) * 60
                k.rrect(x - 46 * sc, y, 92 * sc, 8 * sc, 3); k.fill(DIM, 0.55 - row * 0.12)
                for sx in (-34, 34):
                    k.circle(x + sx * sc, y - 26 * sc, 11 * sc); k.fill(DIM, 0.5 - row * 0.12)
                    k.rrect(x + sx * sc - 12 * sc, y - 15 * sc, 24 * sc, 22 * sc, 6); k.fill(DIM, 0.42 - row * 0.1)
        k.rrect(-20, 610, W + 40, 10, 5); k.fill(ORANGE, 0.25)
        for i in range(7):
            x = 40 + i * 150
            k.rrect(x, 628, 112, 34, 8); k.fill([ORANGE, VIOLET, TEAL][i % 3], 0.16)
        for x in (160, 540, 920):                       # ceiling lights
            k.glow_dot(x, 470, 330, mix(VIOLET, CREAM, 0.3), 0.20)
    elif kind == "home":                                # a room at night: window, shelf, lamp
        k.rrect(700, 560, 290, 330, 16); k.fill((20, 22, 48), 1); k.rrect(700, 560, 290, 330, 16); k.stroke(VIOLET, 4, 0.5)
        k.line([(845, 560), (845, 890)]); k.stroke(VIOLET, 3, 0.4); k.line([(700, 725), (990, 725)]); k.stroke(VIOLET, 3, 0.4)
        k.circle(920, 640, 30); k.fill(CREAM, 0.5); k.glow_dot(920, 640, 120, CREAM, 0.25)
        for sx, sy in ((740, 600), (790, 680), (760, 800), (960, 810), (880, 770)):
            k.circle(sx, sy, 2.5); k.fill(CREAM, 0.6)
        k.line([(70, 720), (430, 720)]); k.stroke(VIOLET, 5, 0.35)
        for i, hgt in enumerate((90, 120, 70, 110, 95, 60)):
            k.rrect(92 + i * 46, 720 - hgt, 34, hgt, 4); k.fill([VIOLET, ORANGE, TEAL, DIM][i % 4], 0.22)
        k.line([(0, 1500), (W, 1500)]); k.stroke(VIOLET, 3, 0.25)
        k.glow_dot(250, 1050, 520, ORANGE, 0.10)
    elif kind == "road":                                # night road: skyline, stars
        for i in range(60):
            k.circle(rng.uniform(0, W), rng.uniform(420, 900), rng.uniform(1, 2.6)); k.fill(CREAM, rng.uniform(0.2, 0.7))
        x = -20
        while x < W:
            bw = rng.uniform(70, 150); bh = rng.uniform(120, 330)
            k.rrect(x, 1130 - bh, bw, bh, 4); k.fill((24, 20, 44), 1)
            for wy in range(int(1130 - bh + 16), 1110, 34):
                for wx in range(int(x + 12), int(x + bw - 14), 26):
                    if rng.random() < 0.35:
                        k.rrect(wx, wy, 10, 14, 2); k.fill(GOLD, 0.35)
            x += bw + rng.uniform(6, 26)
        k.rrect(0, 1130, W, 420, 0); k.fill((14, 13, 26), 1)
        k.line([(0, 1130), (W, 1130)]); k.stroke(VIOLET, 4, 0.5)
    elif kind == "stage":
        for x, col in ((200, ORANGE), (880, VIOLET)):
            c.new_path(); c.move_to(x, 380); c.line_to(W / 2 - 330, 1500); c.line_to(W / 2 + 330, 1500); c.close_path()
            k.fill(col, 0.07)
        k.c.save(); k.c.scale(1, 0.22); k.circle(W / 2, 1480 / 0.22, 400); k.fill(ORANGE, 0.10); k.c.restore()
    # vignette
    v = cairo.RadialGradient(W / 2, H / 2, H * 0.32, W / 2, H / 2, H * 0.78)
    v.add_color_stop_rgba(0, 0, 0, 0, 0); v.add_color_stop_rgba(1, 0, 0, 0, 0.55)
    c.set_source(v); c.paint()
    s.flush()
    _bg[key] = s
    return s


def paint_bg(k, kind, seed=0):
    k.c.set_source_surface(background(kind, seed), 0, 0); k.c.paint()


def particles(k, t, seed=0, n=16, color=CREAM):
    """Slow floating dust that keeps still scenes alive."""
    rng = random.Random(seed)
    for _ in range(n):
        x0, y0 = rng.uniform(0, W), rng.uniform(450, 1650)
        sp, ph, r = rng.uniform(8, 26), rng.uniform(0, TAU), rng.uniform(2, 5)
        y = 450 + (y0 - sp * t - 450) % 1200
        x = x0 + math.sin(t * 0.6 + ph) * 22
        k.glow_dot(x, y, r * 5, color, 0.10 + 0.08 * math.sin(t + ph))


# ======================================================================= figures
PROFILE = {   # proportions in "units" (u = pixels per unit, given per figure)
    "child": dict(head=0.56, neck=0.10, torso=1.45, tw=0.74, ua=0.74, fa=0.70, th=0.86, sh=0.86, lw=0.30, aw=0.24),
    "adult": dict(head=0.47, neck=0.14, torso=1.95, tw=0.86, ua=0.98, fa=0.92, th=1.22, sh=1.24, lw=0.34, aw=0.27),
}


def _ik(S, Hn, a, b, bend=1):
    dx, dy = Hn[0] - S[0], Hn[1] - S[1]
    d = clamp(math.hypot(dx, dy), abs(a - b) + 1e-3, a + b - 1e-3)
    base = math.atan2(dy, dx)
    al = math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1))
    E = (S[0] + math.cos(base + bend * al) * a, S[1] + math.sin(base + bend * al) * a)
    Hc = (S[0] + math.cos(base) * d, S[1] + math.sin(base) * d)
    return E, Hc


class Person:
    """Side-view faceless figure. face=+1 looks right, -1 looks left."""

    def __init__(self, kind="child", color=ORANGE, u=78, face=1, accent=None):
        self.p = PROFILE[kind]; self.kind = kind; self.color = color; self.u = u; self.face = face
        self.accent = accent or (TEAL if color != TEAL else ORANGE)

    def pose(self, hip, seated=True, lean=0.0, head_tilt=0.0, hand=None, hand2=None, knee_up=0.0, stride=0.0):
        """Returns joints. lean/head_tilt in radians (positive = forward). hand = target of the front hand."""
        p, u, f = self.p, self.u, self.face
        J = {"hip": hip}
        up = rot((0, -1), lean * f)
        J["sho"] = add(hip, (up[0] * p["torso"] * u, up[1] * p["torso"] * u))
        hu = rot((0, -1), (lean + head_tilt) * f)
        J["head"] = add(J["sho"], (hu[0] * (p["neck"] + p["head"]) * u, hu[1] * (p["neck"] + p["head"]) * u))
        if seated:
            J["knee"] = add(hip, (f * p["th"] * u, -knee_up * u))
            J["foot"] = add(J["knee"], (f * 0.06 * u, p["sh"] * u))
            J["knee2"] = add(hip, (f * p["th"] * u * 0.94, 0.05 * u)); J["foot2"] = add(J["knee2"], (-f * 0.05 * u, p["sh"] * u))
        else:
            J["knee"] = add(hip, (f * stride * u * 0.5, p["th"] * u)); J["foot"] = add(J["knee"], (f * stride * u * 0.15, p["sh"] * u))
            J["knee2"] = add(hip, (-f * stride * u * 0.5 - f * 0.05 * u, p["th"] * u)); J["foot2"] = add(J["knee2"], (-f * stride * u * 0.3, p["sh"] * u))
        rest = add(J["sho"], (f * 0.12 * u, (p["ua"] + p["fa"]) * u * 0.96))
        for name, tgt, bend in (("", hand or rest, f), ("2", hand2 or add(rest, (-f * 0.2 * u, 0)), f)):   # elbows point down/back
            E, Hc = _ik(J["sho"], tgt, p["ua"] * u, p["fa"] * u, bend)
            J["elb" + name], J["hand" + name] = E, Hc
        return J

    def draw(self, k, J, a=1.0, glow=0.9, seated=True, hair=True):
        p, u, col = self.p, self.u, self.color
        lw, aw, tw = p["lw"] * u, p["aw"] * u, p["tw"] * u
        dark = mix(BG1, col, 0.16)
        # back arm + back leg (darker, behind)
        k.capsule(J["sho"], J["elb2"], aw, col, 3.5, a * 0.75, glow * 0.4, dark); k.capsule(J["elb2"], J["hand2"], aw * 0.92, col, 3.5, a * 0.75, glow * 0.4, dark)
        k.capsule(J["hip"], J["knee2"], lw, col, 3.5, a * 0.75, glow * 0.4, dark); k.capsule(J["knee2"], J["foot2"], lw * 0.9, col, 3.5, a * 0.75, glow * 0.4, dark)
        self._shoe(k, J["foot2"], a * 0.75, dark)
        # torso
        k.capsule(add(J["hip"], (0, -tw * 0.18)), add(J["sho"], (0, tw * 0.12)), tw, col, 4.5, a, glow)
        # front leg with sock bands
        k.capsule(J["hip"], J["knee"], lw, col, 4.5, a, glow); k.capsule(J["knee"], J["foot"], lw * 0.9, col, 4.5, a, glow)
        for q in (0.62, 0.78):
            m = lerp2(J["knee"], J["foot"], q)
            d = (J["foot"][0] - J["knee"][0], J["foot"][1] - J["knee"][1]); L = math.hypot(*d) or 1
            n = (-d[1] / L * lw * 0.42, d[0] / L * lw * 0.42)
            k.line([add(m, n), add(m, (-n[0], -n[1]))]); k.stroke(self.accent, max(3, u * 0.07), a)
        self._shoe(k, J["foot"], a)
        # head + neck
        k.capsule(J["sho"], lerp2(J["sho"], J["head"], 0.5), aw * 0.9, col, 4, a, glow * 0.5)
        r = p["head"] * u
        k.circle(J["head"][0], J["head"][1], r); k.shape(col, 5, a, 0.2, glow)
        if hair:
            f = self.face
            k.c.new_path(); k.c.arc(J["head"][0], J["head"][1], r * 0.99, TAU * 0.5 + (0.25 if f > 0 else -0.55), TAU + (0.55 if f > 0 else -0.25))
            k.c.close_path(); k.fill(col, 0.34 * a)
        # front arm (over everything)
        k.capsule(J["sho"], J["elb"], aw, col, 4.5, a, glow); k.capsule(J["elb"], J["hand"], aw * 0.92, col, 4.5, a, glow)
        k.circle(J["hand"][0], J["hand"][1], aw * 0.62); k.shape(col, 4, a, 0.3, glow * 0.6)

    def _shoe(self, k, foot, a=1.0, fill=None):
        u, f = self.u, self.face
        k.capsule(add(foot, (-f * 0.05 * u, 0.1 * u)), add(foot, (f * 0.36 * u, 0.1 * u)), 0.2 * u, self.accent, 3.5, a, 0.6,
                  fill or mix(BG1, self.accent, 0.3))


def chair(k, hip, u, face=1, color=DIM, a=0.8):
    x, y = hip
    k.line([(x - face * 0.55 * u, y - 1.25 * u), (x - face * 0.55 * u, y + 0.24 * u), (x + face * 0.6 * u, y + 0.24 * u)]); k.stroke(color, 9, a)
    for dx in (-0.5, 0.52):
        k.line([(x + face * dx * u, y + 0.24 * u), (x + face * dx * u, y + 1.0 * u)]); k.stroke(color, 7, a)


def table(k, x0, x1, y, floor, color=VIOLET, a=1.0):
    k.rrect(x0, y, x1 - x0, 16, 8); k.shape(color, 4, a, 0.3, 0.7)
    for x in (x0 + 34, x1 - 34):
        k.line([(x, y + 18), (x, floor)]); k.stroke(color, 8, a * 0.6)


def mini_piece(k, x, y, s, color, kind="pawn", a=1.0, tilt=0.0):
    """Tiny side-view piece standing at (x, y) = base centre."""
    c = k.c
    c.save(); c.translate(x, y); c.rotate(tilt)
    if kind == "pawn":
        k.line([(-s * 0.32, 0), (s * 0.32, 0), (s * 0.13, -s * 0.62), (-s * 0.13, -s * 0.62)], True); k.shape(color, 3, a, 0.35, 0.6)
        k.circle(0, -s * 0.82, s * 0.24); k.shape(color, 3, a, 0.35, 0.6)
    else:
        hh = {"king": 1.45, "queen": 1.3, "rook": 1.0, "knight": 1.05, "bishop": 1.2}.get(kind, 1.2) * s
        k.line([(-s * 0.36, 0), (s * 0.36, 0), (s * 0.18, -hh * 0.78), (-s * 0.18, -hh * 0.78)], True); k.shape(color, 3, a, 0.35, 0.6)
        if kind == "rook":
            k.rrect(-s * 0.3, -hh, s * 0.6, hh * 0.24, 3); k.shape(color, 3, a, 0.35, 0.6)
        else:
            k.circle(0, -hh * 0.86, s * 0.25); k.shape(color, 3, a, 0.35, 0.6)
        if kind == "king":
            k.line([(0, -hh * 1.08), (0, -hh * 1.36)]); k.stroke(color, 4, a); k.line([(-s * 0.13, -hh * 1.24), (s * 0.13, -hh * 1.24)]); k.stroke(color, 4, a)
        if kind == "queen":
            for dx in (-0.2, 0, 0.2):
                k.circle(dx * s, -hh * 1.12, s * 0.07); k.fill(color, a)
    c.restore()


def board_side(k, cx, y, w, a=1.0, fallen=0.0, t=0.0):
    """A board on a table seen from the side, with a few pieces. fallen 0..1 tips the orange king over."""
    k.rrect(cx - w / 2, y - 14, w, 14, 5); k.shape(GOLD, 3.5, a, 0.4, 0.6)
    s = w / 11
    for i, (dx, kind, col) in enumerate(((-0.40, "rook", CREAM), (-0.25, "pawn", CREAM), (-0.10, "king", ORANGE), (0.07, "pawn", MUTED),
                                         (0.22, "queen", MUTED), (0.38, "pawn", MUTED))):
        tilt = fallen * 1.45 if kind == "king" else 0.0
        mini_piece(k, cx + dx * w, y - 14, s, col, kind, a, tilt)


def chess_clock(k, cx, y, s, t, running=0, low=0.0, a=1.0):
    """Analog chess clock on a table. running = 0/1 side whose hand moves; low 0..1 turns it red."""
    col = mix(CREAM, PINK, low)
    k.rrect(cx - s, y - s * 0.95, 2 * s, s * 0.95, s * 0.16); k.shape(col, 3.5, a, 0.3, 0.6 + low)
    for i, dx in enumerate((-0.48, 0.48)):
        x = cx + dx * s; yy = y - s * 0.48
        k.circle(x, yy, s * 0.33); k.stroke(col, 3, a)
        ang = -TAU / 4 + (t * 2.2 if i == running else 0.6)
        k.line([(x, yy), (x + math.cos(ang) * s * 0.25, yy + math.sin(ang) * s * 0.25)]); k.stroke(col, 3, a)
        k.rrect(x - s * 0.12, y - s * (1.08 if i == running else 1.16), s * 0.24, s * 0.16, 3); k.fill(col, a)


def bubble(k, x, y, w, h, color, tail=(0, 0), a=1.0, scale=1.0, kind="speech"):
    """Speech / thought bubble centred at (x, y); tail = offset of the tip from the centre."""
    c = k.c
    c.save(); c.translate(x, y); c.scale(scale, scale); c.translate(-x, -y)
    if kind == "thought":
        tx, ty = x + tail[0], y + tail[1]
        for q, r in ((0.55, 16), (0.8, 10), (1.0, 6)):
            p = lerp2((x, y + h / 2), (tx, ty), q); k.circle(p[0], p[1], r); k.shape(color, 3.5, a, 0.3, 0.6)
    else:
        bx = x + clamp(tail[0], -w / 2 + 50, w / 2 - 50)
        by = y + (h / 2 if tail[1] > 0 else -h / 2)
        k.line([(bx - 26, by - (4 if tail[1] > 0 else -4)), (x + tail[0], y + tail[1]), (bx + 26, by - (4 if tail[1] > 0 else -4))]); k.shape(color, 4, a, 0.3, 0.7)
    k.rrect(x - w / 2, y - h / 2, w, h, min(h / 2, 46)); k.shape(color, 4.5, a, 0.3, 0.8)
    c.restore()


def bubble_text(k, s, x, y, color, tail=(0, 0), a=1.0, scale=1.0, size=46, maxw=520, kind="speech"):
    lines = wrap(s, size, maxw, F_UI)
    w = max(text_w(l, size) for l in lines) + 90; h = len(lines) * size * 1.3 + 56
    bubble(k, x, y, w, h, color, tail, a, scale, kind)
    k.c.save(); k.c.translate(x, y); k.c.scale(scale, scale); k.c.translate(-x, -y)
    for i, l in enumerate(lines):
        k.text(l, x, y + (i - (len(lines) - 1) / 2) * size * 1.3, size, CREAM, F_UI, a)
    k.c.restore()
    return w, h


def wrap(s, size, maxw, f=F_UI):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if cur and text_w(test, size, f) > maxw:
            lines.append(cur); cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or [""]


def panel(k, x, y, w, h, color=VIOLET, a=1.0, r=34):
    k.rrect(x, y, w, h, r); k.fill((16, 14, 30), 0.86 * a, keep=True); k.fill(color, 0.05 * a, keep=True); k.neon(color, 4, a * 0.9, 0.7)


def icon(k, name, x, y, s, color, a=1.0, t=0.0):
    """Small symbolic icons (all vector)."""
    c = k.c
    if name == "check":
        k.line([(x - s * 0.5, y), (x - s * 0.12, y + s * 0.38), (x + s * 0.55, y - s * 0.42)]); k.neon(color, s * 0.2, a)
    elif name == "cross":
        k.line([(x - s * 0.42, y - s * 0.42), (x + s * 0.42, y + s * 0.42)]); k.neon(color, s * 0.2, a)
        k.line([(x + s * 0.42, y - s * 0.42), (x - s * 0.42, y + s * 0.42)]); k.neon(color, s * 0.2, a)
    elif name == "heart":
        c.new_path(); c.move_to(x, y + s * 0.5)
        c.curve_to(x - s * 0.95, y - s * 0.1, x - s * 0.5, y - s * 0.75, x, y - s * 0.25)
        c.curve_to(x + s * 0.5, y - s * 0.75, x + s * 0.95, y - s * 0.1, x, y + s * 0.5); k.shape(color, s * 0.1, a, 0.5)
    elif name == "tear":
        c.new_path(); c.move_to(x, y - s * 0.6); c.curve_to(x + s * 0.5, y, x + s * 0.4, y + s * 0.5, x, y + s * 0.5)
        c.curve_to(x - s * 0.4, y + s * 0.5, x - s * 0.5, y, x, y - s * 0.6); k.shape(color, s * 0.1, a, 0.6)
    elif name == "question":
        k.big("?", x, y, s * 1.5, color, a)
    elif name == "bolt":
        k.line([(x + s * 0.15, y - s * 0.6), (x - s * 0.3, y + s * 0.05), (x + s * 0.02, y + s * 0.05), (x - s * 0.15, y + s * 0.6),
                (x + s * 0.32, y - s * 0.1), (x, y - s * 0.1)], True); k.shape(color, s * 0.08, a, 0.6)
    elif name == "trophy":
        c.new_path(); c.move_to(x - s * 0.42, y - s * 0.55); c.line_to(x + s * 0.42, y - s * 0.55)
        c.curve_to(x + s * 0.42, y + s * 0.1, x + s * 0.2, y + s * 0.2, x, y + s * 0.22)
        c.curve_to(x - s * 0.2, y + s * 0.2, x - s * 0.42, y + s * 0.1, x - s * 0.42, y - s * 0.55); c.close_path(); k.shape(color, s * 0.08, a, 0.5)
        for sg in (-1, 1):
            k.arc(x + sg * s * 0.46, y - s * 0.3, s * 0.2, -TAU / 4 if sg > 0 else TAU / 4, TAU / 4 if sg > 0 else TAU * 3 / 4); k.neon(color, s * 0.07, a)
        k.line([(x, y + s * 0.22), (x, y + s * 0.45)]); k.neon(color, s * 0.09, a)
        k.rrect(x - s * 0.3, y + s * 0.45, s * 0.6, s * 0.14, 4); k.shape(color, s * 0.07, a, 0.5)
    elif name == "play":
        k.line([(x - s * 0.3, y - s * 0.42), (x + s * 0.45, y), (x - s * 0.3, y + s * 0.42)], True); k.shape(color, s * 0.1, a, 0.5)
    elif name == "star":
        pts = []
        for i in range(10):
            r = s * (0.55 if i % 2 == 0 else 0.24); an = -TAU / 4 + i * TAU / 10
            pts.append((x + math.cos(an) * r, y + math.sin(an) * r))
        k.line(pts, True); k.shape(color, s * 0.07, a, 0.6)
    elif name == "clock":
        k.circle(x, y, s * 0.5); k.shape(color, s * 0.08, a, 0.3)
        k.line([(x, y), (x, y - s * 0.32)]); k.stroke(color, s * 0.08, a); k.line([(x, y), (x + s * 0.22, y + s * 0.1)]); k.stroke(color, s * 0.08, a)
    elif name == "pawn":
        mini_piece(k, x, y + s * 0.5, s * 0.9, color, "pawn", a)
    elif name == "king":
        mini_piece(k, x, y + s * 0.6, s * 0.75, color, "king", a)
    elif name == "arrow_up":
        k.line([(x, y + s * 0.5), (x, y - s * 0.4)]); k.neon(color, s * 0.16, a)
        k.line([(x - s * 0.3, y - s * 0.12), (x, y - s * 0.48), (x + s * 0.3, y - s * 0.12)]); k.neon(color, s * 0.16, a)
    elif name == "phone":
        k.rrect(x - s * 0.3, y - s * 0.55, s * 0.6, s * 1.1, s * 0.1); k.shape(color, s * 0.07, a, 0.3)


def sparks(k, x, y, t, color, n=8, r0=20, r1=90, a=1.0):
    """Radial burst lines at t in 0..1."""
    if t <= 0 or t >= 1:
        return
    e = ease_out(t)
    for i in range(n):
        an = i * TAU / n + 0.3
        p0 = (x + math.cos(an) * lerp(r0, r1 * 0.7, e), y + math.sin(an) * lerp(r0, r1 * 0.7, e))
        p1 = (x + math.cos(an) * lerp(r0 + 10, r1, e), y + math.sin(an) * lerp(r0 + 10, r1, e))
        k.line([p0, p1]); k.neon(color, 5, a * (1 - t))


def speed_lines(k, x, y, t, color, n=5, length=120, a=1.0, direction=-1):
    for i in range(n):
        yy = y + (i - n / 2) * 22
        ph = (t * 3 + i * 0.37) % 1
        x0 = x + direction * (40 + ph * 160)
        k.line([(x0, yy), (x0 + direction * length * (0.4 + 0.6 * ((i * 7) % 5) / 5), yy)]); k.stroke(color, 5, a * (1 - ph) * 0.8)


# ======================================================================= on-screen language
def label(k, s, t, tone="brand", y=500, size=None, hold=None, strike_at=None):
    """Big neon label: pops in, breathes. strike_at = local time when it gets crossed out (a 'wrong fix')."""
    if not s or t < 0:
        return
    s = str(s).upper()
    size = size or (112 if len(s) <= 10 else 96 if len(s) <= 14 else 80 if len(s) <= 19 else 66)
    while size > 48 and text_w(s, size, F_BLACK) > W - 150:
        size -= 4
    col = TONE.get(tone, ORANGE)
    sc = 0.7 + 0.3 * back(t / 0.28) + 0.012 * math.sin(t * 3)
    a = clamp(t / 0.12)
    if strike_at is not None and t > strike_at:
        a *= 0.55
    k.big(s, W / 2, y, size, col, a, sc)
    if t < 0.45:                                         # emphasis ticks at both ends of the word
        hw = text_w(s, size, F_BLACK) / 2 + 26; e = ease_out(t / 0.45)
        for sg in (-1, 1):
            for an in (-0.5, 0.0, 0.5):
                x0 = W / 2 + sg * (hw + 8 + 26 * e); x1 = W / 2 + sg * (hw + 34 + 46 * e)
                k.line([(x0, y + math.sin(an) * (20 + 30 * e)), (x1, y + math.sin(an) * (46 + 60 * e))]); k.neon(col, 5, (1 - t / 0.45) * 0.9)
    if strike_at is not None and t > strike_at:
        w = text_w(s, size, F_BLACK)
        e = ease_out((t - strike_at) / 0.25)
        k.line([(W / 2 - w / 2 - 20, y + 6), (W / 2 - w / 2 - 20 + (w + 40) * e, y - 4)]); k.neon(PINK, 12, 1.0)


def chunk_words(words, max_chars=20, max_words=4):
    """Group caption words into short lines: break on punctuation or when the line is full."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        txt = " ".join(words[j][1] for j in cur)
        nxt = words[i + 1][1] if i + 1 < len(words) else ""
        full = len(cur) >= max_words or len(txt) + 1 + len(nxt) > max_chars
        if w[1][-1:] in ".?!:;" or (full and not (len(nxt) <= 2 and len(txt) + 1 + len(nxt) <= max_chars + 3)) or \
                (w[1][-1:] == "," and len(cur) >= 2):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return chunks


def captions(k, words, chunks, t, highlight=(), y=322, size=60):
    """words: [(time, word)] for the whole reel; shows the chunk being spoken, word by word.
    Spoken words fade to grey, the current one is white; keywords get a glowing box."""
    if not words:
        return
    ci = None
    for i, ch in enumerate(chunks):
        if words[ch[0]][0] - 0.06 <= t:
            ci = i
        else:
            break
    if ci is None:
        return
    cur = chunks[ci]
    if ci + 1 >= len(chunks) and t > words[cur[-1]][0] + 1.5:
        return
    hl = {norm(h) for h in highlight}
    sp = text_w(" ", size, F_UI)

    def adv(j):
        return text_w(words[j][1], size, F_UI) + sp + (14 if norm(words[j][1]) in hl else 0)

    lines, width = [[]], 0
    for j in cur:                                         # layout of the full chunk so words never jump
        if lines[-1] and width + adv(j) > W - 190:
            lines.append([]); width = 0
        lines[-1].append(j); width += adv(j)
    for li, ln in enumerate(lines):
        x = W / 2 - (sum(adv(j) for j in ln) - sp) / 2
        yy = y + (li - (len(lines) - 1) / 2) * size * 1.34
        for j in ln:
            wd = words[j][1]; ww = text_w(wd, size, F_UI)
            key = norm(wd) in hl
            if words[j][0] - 0.06 <= t:
                is_cur = not (j + 1 < len(words) and words[j + 1][0] - 0.06 <= t and (j + 1) in cur)
                a = clamp((t - words[j][0] + 0.06) / 0.1)
                if key:
                    k.rrect(x - 7, yy - size * 0.66, ww + 28, size * 1.32, 12); k.fill(TEAL, 0.13 * a, keep=True)
                    k.neon(TEAL, 3, a * (1 if is_cur else 0.6), 0.8)
                    k.text(wd, x - 1, yy, size, CREAM if is_cur else mix(TEAL, MUTED, 0.35), F_UI, a, 1.0, "l")
                else:
                    k.text(wd, x - 8, yy, size, CREAM if is_cur else MUTED, F_UI, a * (1 if is_cur else 0.85), 1.0, "l")
            x += adv(j)


def norm(w):
    return "".join(ch for ch in str(w).lower() if ch.isalnum())


def watermark(k, a=0.9):
    k.sprite(logo_sprite(176), W / 2, 196, 1.0, a * 0.9)


def source_line(k, s, t, y=1490):
    if s:
        k.text(s, W / 2, y, 30, MUTED, F_UI2, clamp(t / 0.4) * 0.9)


def cut_flash(k, t, color=CREAM):
    """Two-frame light flash at a scene cut (a visual 'beat')."""
    if t < 0.1:
        k.c.set_source_rgba(*c01(color), 0.05 * (1 - t / 0.1)); k.c.paint()
