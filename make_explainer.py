"""Motion-graphics explainer reels for ChessTalentsFactory (style of the "Stuck in chess?" video).

The AI only writes: it picks scene BLOCKS from a fixed catalog and writes headlines + narration. Every block is
designed and animated in code with the academy's characters (assets/kit/*.png), so visual quality never depends
on an image model. Pillars (what the reel is about) come from the weekly calendar in run_daily.py:

  pain    rating stuck -> wrong way -> mentor/roadmap -> method/authority -> (proof) -> CTA
  faq     a parent's question -> honest answer -> method/authority -> CTA
  method  the roadmap: what each level needs -> steps -> authority -> CTA
  proof   only with approved claims (claims.json): mentor -> rating up / trophy -> CTA

Replace the character cut-outs in assets/kit/ with the designer's source art (same file names, transparent PNG)
and every reel improves automatically.
"""
import io, json, math, os, random, re, subprocess, time
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import brand, guard
import make_reel as R
import make_hype as HY

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 25, 24000
KIT = os.path.join(HERE, "assets", "kit")
F_HEAD = os.path.join(HERE, "fonts", "Arvo-Bold.ttf")
F_UI = os.path.join(HERE, "fonts", "Poppins-Bold.ttf")
INK = (24, 22, 28)
ORANGE = brand.ORANGE
ORANGE_D = (214, 86, 24)
BG_LIGHT = (250, 245, 242)
LOG = os.path.join(HERE, "explainer_log.json")


def font(path, size, _c={}):
    k = (path, size)
    if k not in _c:
        _c[k] = ImageFont.truetype(path, size)
    return _c[k]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_out(t): t = clamp(t); return t * t * (3 - 2 * t)
def back(t, s=1.6): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2


# ======================================================================= catalog (what the AI may use)
BLOCKS = {
    "pain":         "a frustrated child sitting on the chess floor, thought bubble. params: {\"pose\": \"sad\"|\"thinking\"}",
    "rating_drop":  "the child + a rating card that drops (illustrative). params: {\"from\": int 600-2000, \"to\": int lower}",
    "wrong_way":    "dark scene, up to 3 cards of what does NOT work, crossed out. params: {\"items\": [max 3 phrases, max 3 words each]}",
    "mentor":       "the coach walks in and stands next to the child. params: {}",
    "roadmap":      "a roadmap card whose steps light up as stars, ending in a trophy, child beside it. params: {}",
    "method_steps": "3 numbered steps appear one by one next to the coach. params: {\"steps\": [3 phrases, max 4 words each]}",
    "authority":    "coach and child hand in hand, 2-3 badges pop in. params: {\"badges\": [2-3 items copied EXACTLY from FACTS]}",
    "faq_question": "a big question card with the thinking child. params: {\"question\": max 8 words}",
    "faq_answer":   "up to 3 answer points tick in next to the coach. params: {\"points\": [max 3 phrases, max 5 words each]}",
    "progress":     "the child stands up and an upward progress line grows (no numbers). params: {}",
    "rating_up":    "rating gain counter (ONLY with an approved claim). params: {}",
    "trophy":       "the child lifts a trophy, confetti. params: {}",
    "limited":      "calendar with spots filling (ONLY with the approved limited_spots claim). params: {}",
}

PILLARS = {
    "pain": [["pain", "rating_drop"], ["wrong_way"], ["mentor", "roadmap"], ["method_steps", "authority"],
             ["progress", "trophy"]],
    "faq": [["faq_question"], ["faq_answer"], ["method_steps", "mentor", "roadmap"], ["authority"]],
    "method": [["pain", "rating_drop"], ["roadmap"], ["method_steps"], ["authority"], ["progress", "trophy"]],
    "proof": [["pain", "rating_drop"], ["mentor"], ["rating_up", "progress"], ["trophy"], ["authority"]],
}

PILLAR_BRIEF = {
    "pain": "Name a painful, specific situation chess parents live (rating stuck, losing in tournaments, endless blitz "
            "without progress, child losing motivation), why the usual fixes fail, and what structured training with "
            "a real coach changes.",
    "faq": "Answer ONE real question parents ask before hiring a chess academy (groups vs private, online vs in "
           "person, how much time per week, when to start tournaments, why not cheaper freelance coaches, what age, "
           "how fast progress shows). Be honest and specific.",
    "method": "Explain how structured training works: a level-based roadmap, what a child at a given level must "
              "master next, why order matters, assignments between lessons.",
    "proof": "Show credibility using ONLY the approved claims and facts: what changes when a child trains with the "
             "right method.",
}


def allowed_blocks():
    out = set(BLOCKS)
    if not guard.has("avg_gain"):
        out.discard("rating_up")
    if not guard.has("limited_spots"):
        out.discard("limited")
    return out                      # a trophy is a symbol of goals: allowed without any number


PROMPT = """You write a {secs}-second vertical motion-graphics reel for {name}.
{audience}
{academy}
{narrator}
{honesty}
{claims}
{cases}
FACTS you may use freely: {facts}

PILLAR: {pillar}. {brief}
TODAY'S CREATIVE BRIEF (A/B experiment, follow it): hook style = {hook_style}; theme = {theme}.
{playbook}
Recent reels (do NOT repeat their idea or headlines): {recent}

Build exactly {n} scenes. Scene k must use one block from SLOT k:
{slots}
Block catalog: {catalog}

Rules:
- Scene 1 stops a busy parent's scroll in 1.5 seconds: headline of 2-5 words that names their pain or question.
- headline: max 6 words, title style, punchy; "highlight": 1-2 words of the headline shown in orange.
- narration per scene: 8-20 spoken words, short sentences, contractions, numbers as words, expert-to-parent tone,
  no hype, no cliches, no chess notation. Total narration {words} words. The narration of each scene must match
  what its block shows.
- delivery: 3-8 word acting direction for the voice (calm, confident, warm; vary it).
- No prices. No guarantees. No competitors. Never state a number about results, students or titles unless it is
  in APPROVED CLAIMS. Rating numbers are allowed ONLY inside a rating_drop block as an illustrative example.
- caption_hook: Instagram first line for parents, max 12 words, one emoji allowed.
- caption_body: 1-2 short sentences that add value for the parent (no hashtags).
Return JSON: {{"title": str, "summary": str, "caption_hook": str, "caption_body": str,
"scenes": [{{"block": str, "headline": str, "highlight": [str], "narration": str, "delivery": str, "params": {{}}}}]}}"""


def _slots_text(pillar, allowed):
    lines = []
    for i, opts in enumerate(PILLARS[pillar]):
        ok = [b for b in opts if b in allowed] or ["mentor"]
        lines.append(f"  SLOT {i + 1}: {' | '.join(ok)}")
    return "\n".join(lines)


def _recent(n=12):
    try:
        return json.load(open(LOG))[-n:]
    except Exception:
        return []


def write_script(pillar, arms=None):
    import make_story as MS, strategy
    arms = arms or {}
    allowed = allowed_blocks()
    n = len(PILLARS[pillar])
    recent = _recent()
    body = {"contents": [{"parts": [{"text": PROMPT.format(
        secs="35-50", name=brand.NAME, audience=brand.AUDIENCE, academy=brand.ACADEMY, narrator=brand.narrator_text(),
        honesty=brand.HONESTY, claims=guard.approved_text(), cases=brand.cases_text(), facts="; ".join(brand.FACTS),
        pillar=pillar, brief=PILLAR_BRIEF[pillar], hook_style=arms.get("hook_style", "your best idea"),
        theme=arms.get("theme", "your best idea"),
        playbook=("WHAT WORKS FOR OUR AUDIENCE (from real results):\n" + strategy.playbook_text()) if strategy.playbook_text() else "",
        recent="; ".join(f"{r.get('pillar')}: {r.get('title')} ({r.get('headline')})" for r in recent) or "none",
        n=n, slots=_slots_text(pillar, allowed), catalog=json.dumps({k: v for k, v in BLOCKS.items() if k in allowed}),
        words="75-110")}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}}
    names = MS.TEXT_MODELS + [m for m in MS._available() if "flash" in m and not any(
        x in m for x in ("image", "tts", "live", "audio", "lite"))]
    last = None
    for model in dict.fromkeys(names):
        try:
            j = MS._post(model, body)
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            return validate(json.loads(re.sub(r"^```(json)?|```$", "", txt.strip())), pillar)
        except Exception as e:
            last = e; print("explainer script:", model, str(e)[:200], flush=True)
    raise RuntimeError(f"explainer script failed: {last}")


def validate(sc, pillar):
    """Hard rules the AI cannot break: block per slot, lengths, params, approved claims only."""
    allowed = allowed_blocks()
    scenes = sc.get("scenes") or []
    slots = PILLARS[pillar]
    if len(scenes) < len(slots):
        raise ValueError("too few scenes")
    scenes = scenes[:len(slots)]
    for i, s in enumerate(scenes):
        opts = [b for b in slots[i] if b in allowed] or ["mentor"]
        if s.get("block") not in opts:
            s["block"] = opts[0]
        s["headline"] = " ".join(str(s.get("headline", "")).split()[:6]) or "Chess parents"
        s["narration"] = " ".join(str(s.get("narration", "")).split()[:26])
        s["highlight"] = [h for h in (s.get("highlight") or []) if isinstance(h, str)][:2]
        p = s.get("params") or {}
        if s["block"] == "authority":
            facts = {f.lower(): f for f in brand.FACTS}
            b = [facts[x.lower()] for x in p.get("badges", []) if isinstance(x, str) and x.lower() in facts][:3]
            p["badges"] = b or ["International Masters", "Small groups of 2-6", "Level-based roadmap"]
        if s["block"] == "rating_drop":
            a = int(clamp(float(p.get("from") or 1400), 500, 2200)); b = int(clamp(float(p.get("to") or a - 150), 300, a - 30))
            p["from"], p["to"] = a, b
        for key, k, nw in (("items", 3, 3), ("steps", 3, 4), ("points", 3, 5)):
            if key in p:
                p[key] = [" ".join(str(x).split()[:nw]) for x in p[key] if str(x).strip()][:k]
        if s["block"] == "faq_question":
            p["question"] = " ".join(str(p.get("question") or s["headline"]).split()[:8])
        s["params"] = p
    text = " ".join(f"{s['headline']} {s['narration']} {json.dumps(s['params'])}" for s in scenes if s["block"] != "rating_drop")
    text += " " + sc.get("caption_hook", "") + " " + sc.get("caption_body", "")
    ok, bad = guard.claims_ok(text)
    if not ok:
        raise ValueError(f"unapproved claims: {bad}")
    words = sum(len(s["narration"].split()) for s in scenes)
    if not 45 <= words <= 140:
        raise ValueError(f"narration length {words}")
    sc["scenes"] = scenes
    return sc


def mock_script(pillar):
    return {
        "title": "Mock explainer", "summary": "mock", "caption_hook": "Is your child's rating stuck? 👇",
        "caption_body": "Most plateaus aren't about talent. They're about structure.",
        "scenes": [
            {"block": "pain", "headline": "Stuck in chess?", "highlight": ["Stuck"], "params": {"pose": "sad"},
             "narration": "Watching your talented child stay stuck at the same rating is tough.", "delivery": "warm"},
            {"block": "wrong_way", "headline": "More games won't fix it", "highlight": ["won't"],
             "params": {"items": ["Random YouTube", "Endless blitz", "No clear plan"]},
             "narration": "Random videos and endless blitz feel like practice, but they aren't a strategy.", "delivery": "direct"},
            {"block": "roadmap", "headline": "Kids need a roadmap", "highlight": ["roadmap"], "params": {},
             "narration": "Strong kids follow a roadmap, one skill at a time, in the right order.", "delivery": "calm"},
            {"block": "authority", "headline": "Train with International Masters", "highlight": ["International", "Masters"],
             "params": {"badges": ["International Masters", "Small groups of 2-6", "Level-based roadmap"]},
             "narration": "Our students train with International Masters, in small groups of kids at their level.", "delivery": "warm"},
            {"block": "progress", "headline": "Structure beats talent", "highlight": ["Structure"], "params": {},
             "narration": "With structure, progress stops being luck and becomes a plan.", "delivery": "confident"},
        ]}


# ======================================================================= drawing primitives
_cache = {}


def cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def kit(name, height):
    def mk():
        im = Image.open(os.path.join(KIT, name + ".png")).convert("RGBA")
        return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)
    return cached(("kit", name, height), mk)


def floor_light():
    """Light wall + perspective black/white chess floor, like the reference video."""
    def mk():
        im = Image.new("RGB", (W, H), BG_LIGHT)
        d = ImageDraw.Draw(im)
        for y in range(H):                                     # soft vertical gradient
            k = y / H
            d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip((252, 248, 246), (240, 233, 229))))
        hz = 1240                                             # floor top (horizon of the floor plane)
        d.rectangle([0, hz - 80, W, hz], fill=(226, 230, 235))  # skirting band
        zn, zf, S, vx = 1.0, 6.0, 230.0, W / 2               # true perspective: depth z, tile width S at z=1
        def Y(z): return hz + (H - hz) * (1 / z - 1 / zf) / (1 / zn - 1 / zf)
        def X(u, z): return vx + u * S / z
        rows = 12
        zs = [zf - (zf - zn) * (j / rows) ** 0.75 for j in range(rows + 1)]
        for j in range(rows):
            z0, z1 = zs[j], zs[j + 1]
            for u in range(-14, 14):
                pts = [(X(u, z0), Y(z0)), (X(u + 1, z0), Y(z0)), (X(u + 1, z1), Y(z1)), (X(u, z1), Y(z1))]
                d.polygon(pts, fill=(22, 22, 26) if (j + u) % 2 else (247, 247, 249))
        fog = Image.new("L", (W, H), 0); fd = ImageDraw.Draw(fog)
        for y in range(hz, H):                                 # soft fog near the horizon, like a studio floor
            fd.line([(0, y), (W, y)], fill=int(150 * clamp(1 - (y - hz) / 260)))
        im.paste((236, 236, 240), (0, 0), fog)
        im = im.filter(ImageFilter.GaussianBlur(0.7))
        return im.convert("RGBA")
    return cached("floor_light", mk)


def bg_dark():
    def mk():
        im = Image.new("RGB", (W, H), (22, 21, 26)); d = ImageDraw.Draw(im)
        for y in range(0, H, 60):
            for x in range(0, W, 60):
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(40, 39, 46))
        v = Image.new("L", (W, H), 0)
        ImageDraw.Draw(v).ellipse([-300, 200, W + 300, H - 200], fill=255)
        dark = Image.new("RGB", (W, H), (10, 10, 12))
        return Image.composite(im, dark, v.filter(ImageFilter.GaussianBlur(180))).convert("RGBA")
    return cached("bg_dark", mk)


def bg_orange():
    def mk():
        im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
        for y in range(H):
            k = ease_in_out(clamp((y - 500) / 1300))
            d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip((252, 247, 244), (240, 120, 40))))
        return im.convert("RGBA")
    return cached("bg_orange", mk)


def bg_cta():
    def mk():
        import chess
        im = Image.new("RGBA", (W, H), (222, 226, 232, 255))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for (x, y, s, p) in [(-80, 80, 520, chess.PAWN), (720, -60, 460, chess.KING), (760, 1380, 620, chess.PAWN),
                             (-120, 1500, 480, chess.KNIGHT), (420, 1640, 360, chess.PAWN)]:
            pc = R.piece_img(chess.Piece(p, chess.BLACK), s)
            layer.alpha_composite(pc, (x, y))
        im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(5)))
        return im
    return cached("bg_cta", mk)


def shadow(fr, cx, y, w, a=70):
    sh = cached(("sh", w, a), lambda: _mk_shadow(w, a))
    fr.alpha_composite(sh, (int(cx - sh.width / 2), int(y - sh.height / 2)))


def _mk_shadow(w, a):
    im = Image.new("RGBA", (w + 80, w // 4 + 80), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([40, 40, 40 + w, 40 + w // 4], fill=(0, 0, 0, a))
    return im.filter(ImageFilter.GaussianBlur(16))


def paste(fr, im, cx, cy, scale=1.0, alpha=1.0, anchor="center"):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.004:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    x = int(cx - im.width / 2)
    y = int(cy - im.height / 2) if anchor == "center" else int(cy - im.height)
    fr.alpha_composite(im, (x, y)) if 0 <= x and 0 <= y and x + im.width <= W and y + im.height <= H else _safe(fr, im, x, y)


def _safe(fr, im, x, y):
    tmp = Image.new("RGBA", fr.size, (0, 0, 0, 0)); tmp.paste(im, (x, y)); fr.alpha_composite(tmp)


def character(fr, name, cx, feet_y, height, t, enter=0.0, slide_from=None):
    """Puppet-lite animation: pop/slide entrance, breathing and a gentle bob."""
    lt = t - enter
    if lt < 0:
        return
    im = kit(name, height)
    k = ease_out(lt / 0.55)
    x = cx if slide_from is None else slide_from + (cx - slide_from) * k
    sc = 1.0 if slide_from is not None else 0.85 + 0.15 * back(lt / 0.5)
    breath = 1 + 0.012 * math.sin(2 * math.pi * lt / 2.6)
    bob = 5 * math.sin(2 * math.pi * lt / 2.6 + 0.6)
    shadow(fr, x, feet_y - 6, int(im.width * 0.7), int(70 * min(1, lt / 0.4)))
    s = sc * breath
    if abs(s - 1) > 0.004:
        im = im.resize((int(im.width * sc), int(im.height * s)), Image.BILINEAR)
    al = min(1, lt / 0.25)
    if al < 1:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * al)))
    _safe(fr, im, int(x - im.width / 2), int(feet_y - im.height + bob))


def text_img(txt, path, size, fill, maxw=None):
    k = ("txt", txt, path, size, fill, maxw)
    def mk():
        f = font(path, size)
        words, lines, cur = txt.split(), [], ""
        for w in words:
            t2 = (cur + " " + w).strip()
            if maxw and f.getlength(t2) > maxw and cur:
                lines.append(cur); cur = w
            else:
                cur = t2
        lines.append(cur)
        lh = int(size * 1.22)
        wd = int(max(f.getlength(l) for l in lines)) + 8
        im = Image.new("RGBA", (wd, lh * len(lines) + 10), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for i, l in enumerate(lines):
            d.text(((wd - f.getlength(l)) / 2, i * lh), l, font=f, fill=fill)
        return im
    return cached(k, mk)


def headline(fr, text, highlight, t, y=170, size=96, dark=False, maxw=960):
    """Word-by-word slam-in headline, orange highlight words."""
    f = font(F_HEAD, size)
    words = text.split()
    hl = {h.lower().strip(".,!?") for hh in highlight for h in hh.split()}
    lines, cur = [], []
    for w in words:
        if cur and f.getlength(" ".join(cur + [w])) > maxw:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    if len(lines) > 3:
        size = int(size * 0.82); return headline(fr, text, highlight, t, y, size, dark, maxw)
    lh = int(size * 1.18); i = 0
    for li, line in enumerate(lines):
        total = f.getlength(" ".join(line)); x = (W - total) / 2
        for w in line:
            lt = t - 0.08 * i - 0.05
            col = ORANGE if w.lower().strip(".,!?") in hl else ((250, 250, 250) if dark else INK)
            if lt > 0:
                wi = text_img(w, F_HEAD, size, col)
                s = 1.0 + 0.35 * (1 - back(lt / 0.32, 2.2))
                a = min(1, lt / 0.12)
                paste(fr, wi, x + f.getlength(w) / 2 + 4, y + li * lh + size * 0.6, s, a)
            x += f.getlength(w + " "); i += 1


def subtitle(fr, words, t):
    """Pill subtitle at the bottom (like the reference): the current phrase, spoken word in white."""
    if not words:
        return
    idx = max([i for i, (ts, _) in enumerate(words) if ts <= t] or [0])
    start = (idx // 6) * 6
    chunk = words[start:start + 6]
    f = font(F_UI, 40)
    txt = " ".join(w for _, w in chunk)
    tw = f.getlength(txt)
    pw, ph = min(980, tw + 70), 92
    key = ("subbg", int(pw))
    bgp = cached(key, lambda: _pill_bg(int(pw), ph))
    x0, y0 = (W - bgp.width) / 2, 1660
    fr.alpha_composite(bgp, (int(x0), y0))
    d = ImageDraw.Draw(fr)
    x = (W - tw) / 2
    for i, (ts, w) in enumerate(chunk):
        cur = start + i == idx
        d.text((x, y0 + 20), w, font=f, fill=(255, 255, 255) if cur or ts <= t else (255, 225, 205))
        x += f.getlength(w + " ")


def _pill_bg(w, h):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=(205, 92, 52, 225))
    return im


def card(w, h, border=ORANGE, radius=26, bw=10, fill=(255, 255, 255)):
    def mk():
        im = Image.new("RGBA", (w + 40, h + 50), (0, 0, 0, 0))
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([20, 34, 20 + w, 34 + h], radius=radius, fill=(0, 0, 0, 70))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
        ImageDraw.Draw(im).rounded_rectangle([20, 20, 20 + w, 20 + h], radius=radius, fill=fill,
                                             outline=border, width=bw)
        return im
    return cached(("card", w, h, border, radius, bw, fill), mk)


def rating_card(fr, value, cx, cy, t, enter=0.0, color=INK):
    lt = t - enter
    if lt < 0:
        return
    c = card(380, 210).copy(); d = ImageDraw.Draw(c)
    d.text((60, 42), "Rating", font=font(F_HEAD, 46), fill=ORANGE)
    d.text((60, 92), str(int(value)), font=font(F_HEAD, 118), fill=color)
    paste(fr, c, cx, cy, 0.7 + 0.3 * back(lt / 0.45), min(1, lt / 0.15))


def bubble(fr, cx, cy, t, enter=0.0):
    lt = t - enter
    if lt < 0:
        return
    def mk():
        im = Image.new("RGBA", (300, 240), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for (x, y, r) in [(150, 95, 80), (95, 105, 55), (210, 105, 58), (125, 60, 50), (185, 62, 52)]:
            d.ellipse([x - r, y - r, x + r, y + r], fill=(214, 220, 228))
        d.ellipse([60, 185, 90, 215], fill=(214, 220, 228)); d.ellipse([35, 220, 52, 237], fill=(214, 220, 228))
        return im
    im = cached("bubble", mk).copy(); d = ImageDraw.Draw(im)
    for i in range(3):
        a = 0.5 + 0.5 * math.sin(lt * 6 - i * 0.9)
        d.ellipse([105 + i * 45 - 13, 92 - 13 - 6 * a, 105 + i * 45 + 13, 92 + 13 - 6 * a], fill=(255, 255, 255))
    paste(fr, im, cx, cy, back(lt / 0.4), 1)


def chip(text, size=40, fg=INK, bg=(255, 255, 255), border=ORANGE, icon=None):
    def mk():
        f = font(F_UI, size); tw = f.getlength(text)
        pad = 34; iw = 70 if icon else 0
        w, h = int(tw + 2 * pad + iw), int(size * 2.1)
        im = Image.new("RGBA", (w + 30, h + 40), (0, 0, 0, 0))
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([15, 26, 15 + w, 26 + h], radius=h // 2, fill=(0, 0, 0, 60))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([15, 15, 15 + w, 15 + h], radius=h // 2, fill=bg, outline=border, width=5)
        if icon:
            cx, cy, r = 15 + pad + 24, 15 + h / 2, 24
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ORANGE)
            if icon == "check":
                d.line([(cx - 11, cy + 1), (cx - 3, cy + 9), (cx + 12, cy - 9)], fill=(255, 255, 255), width=6)
            elif icon == "x":
                d.line([(cx - 9, cy - 9), (cx + 9, cy + 9)], fill=(255, 255, 255), width=6)
                d.line([(cx - 9, cy + 9), (cx + 9, cy - 9)], fill=(255, 255, 255), width=6)
            else:
                d.text((cx, cy), icon, font=font(F_UI, 30), fill=(255, 255, 255), anchor="mm")
        d.text((15 + pad + iw, 15 + h / 2), text, font=f, fill=fg, anchor="lm")
        return im
    return cached(("chip", text, size, fg, bg, border, icon), mk)


def trophy_icon(size):
    def mk():
        s = size; im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        gold, dark = (247, 190, 40), (205, 140, 20)
        d.ellipse([s * .1, s * .15, s * .32, s * .45], outline=gold, width=max(3, s // 22))
        d.ellipse([s * .68, s * .15, s * .9, s * .45], outline=gold, width=max(3, s // 22))
        d.pieslice([s * .22, -s * .25, s * .78, s * .62], 0, 180, fill=gold)
        d.rectangle([s * .45, s * .6, s * .55, s * .76], fill=dark)
        d.rounded_rectangle([s * .3, s * .76, s * .7, s * .9], radius=s // 30, fill=(120, 70, 40))
        return im
    return cached(("trophy", size), mk)


def star(size, fill):
    def mk():
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        c, r1, r2 = size / 2, size / 2 - 2, size / 4.6
        pts = [(c + (r1 if i % 2 == 0 else r2) * math.sin(i * math.pi / 5), c - (r1 if i % 2 == 0 else r2) * math.cos(i * math.pi / 5)) for i in range(10)]
        d.polygon(pts, fill=fill)
        return im
    return cached(("star", size, fill), mk)


# ======================================================================= blocks: draw(fr, t, dur, scene)
def b_pain(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    pose = "girl_thinking" if s["params"].get("pose") == "thinking" else "girl_sad"
    character(fr, pose, W / 2, 1520, 820, t, 0.05)
    bubble(fr, W / 2 + 290, 640, t, 0.7)
    headline(fr, s["headline"], s["highlight"], t)


def b_rating_drop(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    character(fr, "girl_thinking", W / 2, 1540, 800, t, 0.0)
    a, b = s["params"]["from"], s["params"]["to"]
    k = ease_in_out((t - 0.6) / max(0.8, dur - 1.6))
    val = a + (b - a) * k
    red = (200, 40, 40) if k > 0.05 else INK
    rating_card(fr, val, W / 2 + 230, 560, t, 0.25, red)
    headline(fr, s["headline"], s["highlight"], t)


def b_wrong_way(fr, t, dur, s):
    fr.alpha_composite(bg_dark())
    items = s["params"].get("items") or ["Random videos", "Endless blitz", "No plan"]
    icons = ["play", "bolt", "dice"]
    for i, it in enumerate(items[:3]):
        enter = 0.45 + i * max(0.55, (dur - 1.6) / 3)
        lt = t - enter
        if lt < 0:
            continue
        c = card(800, 230, border=ORANGE, bw=12).copy(); d = ImageDraw.Draw(c)
        cx, cy = 140, 135
        d.ellipse([cx - 56, cy - 56, cx + 56, cy + 56], fill=ORANGE)
        ic = icons[i % 3]
        if ic == "play":
            d.polygon([(cx - 18, cy - 28), (cx - 18, cy + 28), (cx + 30, cy)], fill=(255, 255, 255))
        elif ic == "bolt":
            d.polygon([(cx + 6, cy - 36), (cx - 22, cy + 6), (cx - 2, cy + 6), (cx - 8, cy + 36), (cx + 22, cy - 8), (cx + 2, cy - 8)], fill=(255, 255, 255))
        else:
            d.rounded_rectangle([cx - 28, cy - 28, cx + 28, cy + 28], radius=10, outline=(255, 255, 255), width=6)
            for dx, dy in [(-12, -12), (12, 12), (0, 0)]:
                d.ellipse([cx + dx - 5, cy + dy - 5, cx + dx + 5, cy + dy + 5], fill=(255, 255, 255))
        f = font(F_HEAD, 58 if len(it) < 16 else 48)
        d.text((230, cy), it, font=f, fill=INK, anchor="lm")
        strike = clamp((lt - 0.45) / 0.3)
        if strike > 0:
            d.line([(210, cy + 4), (210 + (f.getlength(it) + 40) * strike, cy + 4)], fill=(215, 45, 45), width=10)
        y = 690 + i * 290
        paste(fr, c, W / 2 + (1 - ease_out(lt / 0.4)) * 700, y, 1, min(1, lt / 0.2))
    headline(fr, s["headline"], s["highlight"], t, dark=True)


def b_mentor(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    character(fr, "girl_standing", W / 2 - 200, 1560, 640, t, 0.0)
    character(fr, "coach_standing", W / 2 + 190, 1560, 900, t, 0.35, slide_from=W + 300)
    headline(fr, s["headline"], s["highlight"], t)


def b_roadmap(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    lt = t - 0.2
    c = card(560, 640, border=(225, 232, 245), bw=6, fill=(245, 249, 255)).copy(); d = ImageDraw.Draw(c)
    d.text((300, 90), "Roadmap", font=font(F_HEAD, 64), fill=(28, 40, 80), anchor="mm")
    n_on = int(clamp((t - 0.8) / max(0.6, dur - 2.0)) * 11)
    for i in range(12):
        r, col = divmod(i, 3)
        cx, cy = 140 + col * 160, 210 + r * 120
        if i == 11:
            c.alpha_composite(trophy_icon(110), (int(cx - 55), int(cy - 58)))
        elif i < n_on:
            c.alpha_composite(star(80, (110, 170, 245)), (int(cx - 40), int(cy - 40)))
        else:
            d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(196, 216, 245))
    if lt > 0:
        paste(fr, c, W / 2 - 150, 820, 0.8 + 0.2 * back(lt / 0.5), min(1, lt / 0.2))
    character(fr, "girl_standing", W / 2 + 290, 1580, 600, t, 0.5)
    headline(fr, s["headline"], s["highlight"], t)


def b_method_steps(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    character(fr, "coach_standing", W - 170, 1640, 860, t, 0.0)
    steps = s["params"].get("steps") or ["Find the gaps", "Train in order", "Review every game"]
    for i, st in enumerate(steps[:3]):
        enter = 0.6 + i * max(0.6, (dur - 1.8) / 3)
        lt = t - enter
        if lt < 0:
            continue
        ch = chip(st, 52, icon=str(i + 1))
        paste(fr, ch, 40 + ch.width / 2 + (1 - ease_out(lt / 0.4)) * -500, 620 + i * 210, 1, min(1, lt / 0.2))
    headline(fr, s["headline"], s["highlight"], t)


def b_authority(fr, t, dur, s):
    fr.alpha_composite(bg_orange())
    character(fr, "pair_hands", W / 2, 1640, 700, t, 0.0)
    nb = len((s["params"].get("badges") or [])[:3])
    for i, bdg in enumerate((s["params"].get("badges") or [])[:3]):
        lt = t - (0.5 + i * min(0.55, max(0.3, (dur - 1.4) / max(1, nb))))
        if lt < 0:
            continue
        ch = chip(bdg, 40, icon="check")
        pos = [(W / 2, 600), (W / 2, 720), (W / 2, 840)][i]
        paste(fr, ch, pos[0], pos[1], 0.6 + 0.4 * back(lt / 0.4), min(1, lt / 0.15))
    headline(fr, s["headline"], s["highlight"], t)


def b_faq_question(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    character(fr, "girl_thinking", W / 2, 1560, 760, t, 0.4)
    q = s["params"].get("question") or s["headline"]
    lt = t - 0.1
    c = card(900, 360, border=ORANGE, bw=12).copy(); d = ImageDraw.Draw(c)
    ti = text_img(q, F_HEAD, 66 if len(q) < 34 else 56, INK, maxw=760)
    c.alpha_composite(ti, (int(470 - ti.width / 2), int(200 - ti.height / 2)))
    qm = text_img("?", F_HEAD, 140, (255, 255, 255))
    badge = Image.new("RGBA", (170, 170), (0, 0, 0, 0)); ImageDraw.Draw(badge).ellipse([0, 0, 169, 169], fill=ORANGE)
    badge.alpha_composite(qm, (int(85 - qm.width / 2), int(78 - qm.height / 2)))
    if lt > 0:
        paste(fr, c, W / 2, 470, 0.8 + 0.2 * back(lt / 0.45), min(1, lt / 0.15))
        paste(fr, badge, W / 2 + 400, 300, back((lt - 0.3) / 0.4), 1 if lt > 0.3 else 0)


def b_faq_answer(fr, t, dur, s):
    fr.alpha_composite(floor_light())
    character(fr, "coach_standing", W - 170, 1640, 860, t, 0.0)
    pts = s["params"].get("points") or ["Small groups", "Same level", "Clear plan"]
    for i, p in enumerate(pts[:3]):
        lt = t - (0.6 + i * max(0.6, (dur - 1.8) / 3))
        if lt < 0:
            continue
        ch = chip(p, 50, icon="check")
        paste(fr, ch, 40 + ch.width / 2 + (1 - ease_out(lt / 0.4)) * -500, 620 + i * 210, 1, min(1, lt / 0.2))
    headline(fr, s["headline"], s["highlight"], t)


def b_progress(fr, t, dur, s):
    fr.alpha_composite(bg_orange())
    k = ease_in_out((t - 0.4) / max(1.0, dur - 1.2))
    d = ImageDraw.Draw(fr)
    pts = [(140 + i * 80, 1180 - (i * 50 + 60 * math.sin(i * 1.3)) * 1.0) for i in range(11)]
    n = max(2, int(2 + k * (len(pts) - 2)))
    d.line(pts[:n], fill=(255, 255, 255), width=16, joint="curve")
    for p in pts[:n]:
        d.ellipse([p[0] - 14, p[1] - 14, p[0] + 14, p[1] + 14], fill=ORANGE_D, outline=(255, 255, 255), width=5)
    tip = pts[n - 1]
    d.polygon([(tip[0] + 10, tip[1] - 60), (tip[0] + 60, tip[1] - 10), (tip[0] - 10, tip[1] - 10)], fill=(255, 255, 255))
    character(fr, "girl_standing", W / 2 + 230, 1640, 620, t, 0.2)
    headline(fr, s["headline"], s["highlight"], t)


def b_rating_up(fr, t, dur, s):
    fr.alpha_composite(bg_orange())
    character(fr, "pair_hands", W / 2, 1660, 900, t, 0.0)
    gain = 300
    for c in guard.approved():
        if c.get("id") == "avg_gain":
            nums = [int(n) for n in c.get("numbers", []) if str(n).isdigit()]
            gain = nums[0] if nums else gain
    k = ease_out((t - 0.6) / max(1.0, dur - 1.6))
    lt = t - 0.3
    if lt > 0:
        c = card(520, 230).copy(); d = ImageDraw.Draw(c)
        d.text((60, 40), "Avg. rating gain", font=font(F_HEAD, 40), fill=ORANGE)
        d.text((60, 92), f"+{int(gain * k)}", font=font(F_HEAD, 120), fill=INK)
        paste(fr, c, W / 2, 600, 0.7 + 0.3 * back(lt / 0.45), min(1, lt / 0.15))
    headline(fr, s["headline"], s["highlight"], t)


def b_trophy(fr, t, dur, s):
    fr.alpha_composite(bg_orange())
    rng = random.Random(7)
    d = ImageDraw.Draw(fr)
    for i in range(70):
        x0 = rng.uniform(0, W); sp = rng.uniform(260, 520); ph = rng.uniform(0, 3)
        y = (rng.uniform(-400, 0) + (t - 0.3) * sp) % (H + 200) - 100
        if t < 0.3:
            continue
        col = rng.choice([(255, 255, 255), (255, 214, 80), (230, 90, 30), (40, 40, 48)])
        x = x0 + 30 * math.sin(t * 3 + ph)
        d.rectangle([x, y, x + 14, y + 22], fill=col)
    character(fr, "girl_trophy", W / 2, 1700, 1150, t, 0.0)
    headline(fr, s["headline"], s["highlight"], t)


def b_limited(fr, t, dur, s):
    fr.alpha_composite(bg_dark())
    c = card(640, 560, border=(255, 255, 255), bw=4).copy(); d = ImageDraw.Draw(c)
    d.rectangle([20, 20, 660, 130], fill=(240, 240, 244))
    for i in range(8):
        d.rounded_rectangle([90 + i * 70, 0, 106 + i * 70, 60], radius=6, fill=(60, 60, 70))
    filled = int(clamp((t - 0.6) / max(0.8, dur - 1.6)) * 20)
    for i in range(28):
        r, col = divmod(i, 7)
        x, y = 70 + col * 80, 170 + r * 95
        d.rounded_rectangle([x, y, x + 60, y + 60], radius=10, fill=(230, 80, 40) if i < filled else (222, 226, 232))
    paste(fr, c, W / 2, 900, 0.8 + 0.2 * back((t - 0.2) / 0.45), min(1, max(0, t - 0.2) / 0.15))
    headline(fr, s["headline"], s["highlight"], t, dark=True)


DRAW = {"pain": b_pain, "rating_drop": b_rating_drop, "wrong_way": b_wrong_way, "mentor": b_mentor,
        "roadmap": b_roadmap, "method_steps": b_method_steps, "authority": b_authority,
        "faq_question": b_faq_question, "faq_answer": b_faq_answer, "progress": b_progress,
        "rating_up": b_rating_up, "trophy": b_trophy, "limited": b_limited}


def b_cta(fr, t, dur, kind):
    fr.alpha_composite(bg_cta())
    lg = brand.logo(760)
    paste(fr, lg, W / 2, 760, 0.85 + 0.15 * back(t / 0.5), min(1, t / 0.2))
    CT = brand.cta(kind)
    label = {"keyword": f'COMMENT "{brand.KEYWORD}"', "vsl": "WATCH FREE VIDEO", "call": "BOOK CALL",
             "comment": "FOLLOW"}.get(kind, "BOOK CALL")
    lt = t - 0.5
    if lt > 0:
        press = 1 - 0.06 * math.exp(-((t - 1.35) * 9) ** 2)
        b = chip(label, 64, fg=ORANGE_D, border=(255, 255, 255))
        paste(fr, b, W / 2, 1010, (0.7 + 0.3 * back(lt / 0.45)) * press, min(1, lt / 0.15))
        sub = text_img(CT["pills"][1] if kind != "keyword" else CT["pills"][1], F_UI, 40, INK)
        paste(fr, sub, W / 2, 1170, 1, clamp((lt - 0.3) / 0.3))
        url = text_img("@" + brand.IG_HANDLE if kind == "keyword" else CT["url"](), F_UI, 44, ORANGE_D)
        paste(fr, url, W / 2, 1250, 1, clamp((lt - 0.5) / 0.3))
    # cursor that taps the button
    ct = clamp((t - 0.7) / 0.65)
    if t > 0.7:
        cx = W / 2 + 260 - 150 * ease_out(ct); cy = 1140 - 100 * ease_out(ct)
        d = ImageDraw.Draw(fr)
        d.polygon([(cx, cy), (cx, cy + 62), (cx + 16, cy + 48), (cx + 30, cy + 76), (cx + 42, cy + 70),
                   (cx + 28, cy + 44), (cx + 48, cy + 42)], fill=(20, 20, 24), outline=(255, 255, 255))


# ======================================================================= audio
def music(total):
    """Calm, warm corporate bed: soft pad + gentle plucked arpeggio, 96 bpm."""
    n = int(total * SR); t = np.arange(n) / SR
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 329.63)]
    out = np.zeros(n, np.float32)
    bar = 60 / 96 * 4
    for i in range(int(total / bar) + 1):
        a, b = int(i * bar * SR), min(n, int((i + 1) * bar * SR))
        if a >= n:
            break
        tt = t[a:b] - t[a]
        for f in chords[i % 4]:
            out[a:b] += 0.022 * np.sin(2 * np.pi * f / 2 * tt) * np.clip(tt / 0.5, 0, 1)
        for k in range(8):
            s0 = a + int(k * bar / 8 * SR)
            if s0 >= n:
                break
            f = chords[i % 4][k % 3] * (2 if k % 4 == 3 else 1)
            ln = min(int(0.5 * SR), n - s0); tk = np.arange(ln) / SR
            out[s0:s0 + ln] += 0.035 * np.sin(2 * np.pi * f * tk) * np.exp(-tk * 7)
    fade = np.clip(t / 1.0, 0, 1) * np.clip((total - t) / 1.2, 0, 1)
    return out * fade


# ======================================================================= build
def build(seed, out, pillar="pain", arms=None, mock=None):
    import voice
    arms = arms or {}
    mock = os.environ.get("STORY_MOCK") == "1" if mock is None else mock
    rng = random.Random(seed)
    sc = mock_script(pillar) if mock else write_script(pillar, arms)
    if not mock and os.environ.get("REVIEWER", "on") != "off":
        sc = review_script(sc, pillar)
    scenes = sc["scenes"]
    kind = arms.get("cta") if arms.get("cta") in brand.CTA else (brand.CTA_MODE if brand.CTA_MODE in brand.CTA else "keyword")
    CT = brand.cta(kind)
    voice.reset()
    texts = [s["narration"] for s in scenes] + [CT["say"]]
    A = voice.say_many(texts, speed=1.04, styles=[s.get("delivery") for s in scenes] + ["warm, confident, inviting"],
                       one_take=False)
    PAD = 0.35
    durs = [max(2.4, len(a) / SR + PAD) for a in A[:-1]] + [max(4.2, len(A[-1]) / SR + 1.4)]
    starts = np.cumsum([0.0] + durs[:-1]); total = float(sum(durs))
    words = []
    for i, a in enumerate(A):
        for ts, w in voice.align(a, texts[i]):
            words.append((starts[i] + 0.15 + ts, w))
    # ---- audio mix
    n = int(total * SR) + SR
    mix = np.zeros(n, np.float32)
    def put(x, at, g=1.0):
        a = int(at * SR); b = min(n, a + len(x)); mix[a:b] += g * x[:b - a]
    for i, a in enumerate(A):
        put(a.astype(np.float32), starts[i] + 0.15, 1.0)
    for i in range(1, len(durs)):
        put(R.whoosh(0.35, seed=i).astype(np.float32), starts[i] - 0.12, 0.45)
    for i, s in enumerate(scenes):
        put(R.pop().astype(np.float32), starts[i] + 0.1, 0.25)
    put(R.ding().astype(np.float32), starts[-1] + 1.3, 0.35)
    bed = music(n / SR)
    env = np.ones(n, np.float32)                          # duck the music under the voice
    for i, a in enumerate(A):
        s0 = int((starts[i] + 0.1) * SR); env[s0:s0 + len(a) + int(0.1 * SR)] = 0.55
    mix += bed[:n] * env
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    wav = out.replace(".mp4", "_x.wav"); sf.write(wav, mix[:int(total * SR)], SR)
    # ---- video
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + HY.enc_args(out), stdin=subprocess.PIPE)
    prev_last = None
    nf = int(total * FPS)
    for fi in range(nf):
        tg = fi / FPS
        i = int(np.searchsorted(starts, tg, side="right") - 1)
        lt = tg - starts[i]
        fr = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        if i < len(scenes):
            DRAW[scenes[i]["block"]](fr, lt, durs[i], scenes[i])
        else:
            b_cta(fr, lt, durs[i], kind)
        if tg >= 0.15:
            subtitle(fr, [(ts, w) for ts, w in words if starts[i] - 0.01 <= ts < starts[i] + durs[i]], tg)
        if i > 0 and lt < 0.32 and prev_last is not None:      # push transition
            k = ease_in_out(lt / 0.32)
            base = Image.new("RGBA", (W, H))
            base.paste(prev_last, (int(-W * k), 0)); base.paste(fr, (int(W * (1 - k)), 0))
            fr = base
        if int(np.searchsorted(starts, (fi + 1) / FPS, side="right") - 1) != i:
            prev_last = fr.copy()                              # last frame of this scene -> next push transition
        proc.stdin.write(fr.convert("RGB").tobytes())
    proc.stdin.close(); proc.wait(); os.remove(wav)
    # ---- caption
    cap = (f"{sc.get('caption_hook', scenes[0]['headline'])}\n{sc.get('caption_body', '')}\n\n{CT['caption']}\n"
           f"{brand.PARENT_LINE}\n\n" + " ".join(brand.hashtags(rng)))
    open(out.replace(".mp4", ".txt"), "w").write(cap)
    meta = dict(mode="explainer", pillar=pillar, story=sc.get("title"), hook=sc.get("caption_hook"),
                headline=scenes[0]["headline"], blocks=[s["block"] for s in scenes], duration=round(total, 1),
                cta=kind, arms=arms, review_score=None)
    if not mock and os.environ.get("REVIEWER", "on") != "off":
        try:
            import reviewer
            new_cap, rep = reviewer.review_video(out, {"title": sc.get("title")}, cap, kind="explainer")
            if new_cap:
                open(out.replace(".mp4", ".txt"), "w").write(new_cap)
            meta["review_score"] = rep.get("overall")
        except reviewer.RejectReel:
            raise
        except Exception as e:
            print("explainer review skipped:", e)
    log = _recent(200) + [{"pillar": pillar, "title": sc.get("title"), "headline": scenes[0]["headline"],
                           "date": time.strftime("%Y-%m-%d")}]
    json.dump(log[-200:], open(LOG, "w"), indent=0)
    return meta


def review_script(sc, pillar):
    """2nd agent: makes the script sharper for parents, then the same hard validation runs again."""
    try:
        import reviewer
        res = reviewer._ask([{"text": f"""{reviewer.PRODUCER}
{guard.approved_text()}
FACTS: {'; '.join(brand.FACTS)}
Improve this motion-graphics reel script (pillar: {pillar}). Keep the same number of scenes and the SAME block in each
scene, keep the JSON schema. Make scene 1 stop a parent's scroll, make every narration concrete and credible, match
narration to what each block shows, remove anything that breaks the honesty rules. Headlines max 6 words.
SCRIPT: {json.dumps(sc, ensure_ascii=False)}
Return the improved script JSON only."""}], 0.6)
        return validate(res, pillar)
    except Exception as e:
        print("explainer script review skipped:", str(e)[:200], flush=True)
        return sc
