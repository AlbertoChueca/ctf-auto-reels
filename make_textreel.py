"""Faceless reels without a narrator: no synthetic voice, so nothing sounds like AI.

Two styles, both on the cinematic chess background with a real music bed:
  kinetic  big, confident lines that rise in word by word (POV, "nobody tells chess parents...", myth vs truth)
  chat     a text conversation between a parent and our coach, typing dots and all (very relatable)

python make_textreel.py kinetic|chat   -> renders out/test_<style>.mp4 (uses the evergreen script without a key)
"""
import json, math, os, random, re, sys
import numpy as np
from PIL import Image, ImageDraw

import brand
import formats as F

HERE = os.path.dirname(os.path.abspath(__file__))
EVERGREEN = os.path.join(HERE, "evergreen_faceless.json")
W, H, FPS, SR = F.W, F.H, F.FPS, F.SR

KINETIC_SHAPES = {
    "pov": "starts with 'POV:' and a specific moment the parent lives (second person), then what is really going on, "
           "then what helps",
    "nobody_tells": "'Nobody tells chess parents this:' then the honest truth in short beats",
    "myth_truth": "a belief many parents hold, then 'The truth:' and why, then what to do instead",
    "if_you": "'If your child ...' (a recognisable situation), then 3 short beats of what it means and what to do",
    "quiet_truth": "a calm, slightly surprising statement from a coach, then the reasoning in short beats",
}

PROMPT_KINETIC = """You write a short on-screen-text reel (no voice-over) for {name}, for chess PARENTS on Instagram.
{audience}
{honesty}
{rules}
TODAY'S PARENT TOPIC: {q}
WHAT A GOOD COACH WOULD HONESTLY SAY: {angle}
SHAPE: {shape} - {shape_desc}
Recent reels (do not repeat): {recent}

Write:
- "hook": the first screen, max 10 words, stops a parent's scroll (specific moment or surprising truth).
- "beats": 4 or 5 screens, each 6-14 words, one idea each, building to a useful insight a parent can act on tonight.
- "close": one line (max 12 words) that leads naturally into: "Want the training plan we use with our students?"
- "hl": for the hook and each beat, 1 word from that text to highlight.
- "caption_hook": first caption line, max 12 words, can include one emoji. "caption_body": 2 short sentences that
  add value (no hashtags).
Return JSON: {{"hook": str, "hook_hl": str, "beats": [{{"text": str, "hl": str}}], "close": str,
"caption_hook": str, "caption_body": str}}"""

PROMPT_CHAT = """You write a short reel shown as a TEXT CONVERSATION between a parent and our coach at {name}.
{audience}
{honesty}
{rules}
TODAY'S PARENT TOPIC: {q}
WHAT A GOOD COACH WOULD HONESTLY SAY: {angle}
Recent reels (do not repeat): {recent}

Write 6-8 messages. The parent writes like a real busy parent texting (casual, short, maybe a typo-free lowercase
start, no emojis or one at most). The coach replies warm, direct and specific, never salesy, max 18 words per
message. Start with the parent describing a real moment or asking. End with the coach giving one concrete thing to
try, and the parent reacting briefly ("ok that makes sense" style).
Also "header": a 2-4 word label for the top of the screen (e.g. "A parent asked us").
Return JSON: {{"header": str, "messages": [{{"from": "parent"|"coach", "text": str}}],
"caption_hook": str (max 12 words, one emoji max), "caption_body": str (2 short sentences)}}"""


# ----------------------------------------------------------------------- validation
def _words(s): return len(str(s).split())


def validate_kinetic(sc):
    if not sc.get("hook") or not isinstance(sc.get("beats"), list):
        raise ValueError("missing hook or beats")
    beats = [b for b in sc["beats"] if str(b.get("text", "")).strip()][:5]
    if len(beats) < 3:
        raise ValueError("need 4-5 beats")
    if _words(sc["hook"]) > 12:
        raise ValueError("hook longer than 12 words")
    for b in beats:
        if _words(b["text"]) > 16:
            raise ValueError(f"beat too long: {b['text'][:60]}")
    sc["beats"] = beats
    sc["close"] = str(sc.get("close") or "Every child can learn this.").strip()
    F.check_text([sc["hook"], sc["close"], sc.get("caption_hook", ""), sc.get("caption_body", "")] +
                 [b["text"] for b in beats])
    return sc


def validate_chat(sc):
    msgs = [m for m in (sc.get("messages") or []) if m.get("from") in ("parent", "coach") and str(m.get("text", "")).strip()]
    if not 5 <= len(msgs) <= 9:
        raise ValueError("need 6-8 messages")
    if msgs[0]["from"] != "parent":
        raise ValueError("the parent must write first")
    for m in msgs:
        if _words(m["text"]) > 22:
            raise ValueError(f"message too long: {m['text'][:60]}")
    sc["messages"] = msgs
    sc["header"] = " ".join(str(sc.get("header") or "A parent asked us").split()[:4])
    F.check_text([m["text"] for m in msgs] + [sc["header"], sc.get("caption_hook", ""), sc.get("caption_body", "")])
    return sc


def evergreen(style, seed):
    lib = [x for x in json.load(open(EVERGREEN)) if x["format"] == style]
    used = {r.get("evergreen"): i for i, r in enumerate(F.recent(400)) if r.get("evergreen")}
    sc = min(lib, key=lambda x: (used.get(x["id"], -1), random.Random(seed).random()))
    return json.loads(json.dumps(sc))


def write(style, topic, seed):
    rec = "; ".join(r.get("title") or r.get("topic", "") for r in F.recent(15)) or "none"
    common = dict(name=brand.NAME, audience=brand.AUDIENCE, honesty=brand.HONESTY, rules=F.VOICE_RULES,
                  q=topic["q"], angle=topic["angle"], recent=rec)
    if style == "chat":
        return F.ask_json(PROMPT_CHAT.format(**common), validate_chat)
    shape = random.Random(seed).choice(list(KINETIC_SHAPES))
    sc = F.ask_json(PROMPT_KINETIC.format(shape=shape, shape_desc=KINETIC_SHAPES[shape], **common), validate_kinetic)
    sc["shape"] = shape
    return sc


# ----------------------------------------------------------------------- kinetic render
def _beat_len(text, first=False):
    return max(2.6 if first else 2.4, 1.15 + 0.3 * _words(text))


def render_kinetic(sc, seed, out):
    screens = [(sc["hook"], [sc.get("hook_hl", "")], True)] + [(b["text"], [b.get("hl", "")], False) for b in sc["beats"]] \
              + [(sc["close"], [], False)]
    durs = [_beat_len(t, f) for t, _, f in screens]
    CTA = 4.8
    starts = np.cumsum([0] + durs)
    total = float(starts[-1] + CTA)
    kicker = sc.get("kicker") or {"pov": "POV", "nobody_tells": "For chess parents", "myth_truth": "Myth vs truth",
                                  "if_you": "For chess parents", "quiet_truth": "From our coaches"}.get(sc.get("shape"), "For chess parents")
    kim = F.label(kicker, 32)

    def frames():
        for fi in range(int(total * FPS)):
            t = fi / FPS
            fr = Image.new("RGBA", (W, H))
            i = int(np.searchsorted(starts, t, side="right") - 1)
            if i < len(screens):
                F.draw_bg(fr, seed, t, total)
                ov = Image.new("RGBA", (W, H), (0, 0, 0, 40)); fr.alpha_composite(ov)
                lt = t - starts[i]
                text, hl, first = screens[i]
                size = 104 if first else (88 if _words(text) <= 9 else 78)
                cy = 860
                h = F.kinetic(fr, text, hl, lt, cy, size=size, out_t=durs[i] - 0.28, per_word=0.07 if first else 0.06)
                if i == 0 or (lt < durs[i] - 0.28):
                    a = F.clamp(lt / 0.3) * (1 if lt < durs[i] - 0.28 else F.clamp(1 - (lt - durs[i] + 0.28) / 0.25))
                    if i == 0:
                        F.paste(fr, kim, F.MX + kim.width / 2, cy - h / 2 - 70, 1, a)
                    else:
                        num = F.cached(("n", i, len(screens)), lambda i=i: F.label(f"{i:02d} / {len(screens) - 1:02d}", 28, F.MUTED))
                        F.paste(fr, num, F.MX + num.width / 2, cy - h / 2 - 64, 1, a * 0.9)
                F.brand_mark(fr, 0.95)
                F.progress(fr, t, total)
            else:
                F.cta_card(fr, t - starts[-1], seed, total)
            yield fr

    n = int(total * SR)
    bed, track = F.music(total, seed, energy=0.65)
    mix = bed[:n].astype(np.float32) * 1.0
    def put(x, at, g=1.0):
        a = int(at * SR); b = min(n, a + len(x))
        if a < n: mix[a:b] += g * x[:b - a]
    for k, s in enumerate(starts[1:-1], start=1):
        put(F.soft_tick(1320 if k % 2 else 1480, 0.05), s + 0.02)
    put(F.swell(0.8, 0.05), starts[-1] - 0.8)
    put(F.bell(784, 0.1), starts[-1] + 1.0)
    wav = F.write_wav(F.master(mix, target_db=-15.0), out.replace(".mp4", "_a.wav"))
    F.encode(frames(), wav, out)
    os.remove(wav)
    return total, track


# ----------------------------------------------------------------------- chat render
BUB_F = 50
COACH_BG, PARENT_BG = (38, 36, 42, 250), (245, 128, 32, 255)


def bubble(text, who):
    f = F.font(F.F_UI2, BUB_F)
    maxw = 780
    lines = F.wrap(text.split(), f, maxw - 64)
    tw = max(f.getlength(" ".join(l)) for l in lines)
    w, h = int(tw + 64), int(len(lines) * BUB_F * 1.32 + 44)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=38, fill=COACH_BG if who == "coach" else PARENT_BG)
    for li, l in enumerate(lines):
        d.text((32, 20 + li * BUB_F * 1.32), " ".join(l), font=f, fill=(255, 255, 255) if who == "parent" else F.CREAM)
    return im


def typing_dots(t):
    im = Image.new("RGBA", (150, 84), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 150, 84], radius=38, fill=COACH_BG)
    for k in range(3):
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 9 - k * 0.9))
        c = tuple(int(v * a) for v in (230, 225, 220)) + (255,)
        d.ellipse([34 + k * 30, 34, 50 + k * 30, 50], fill=c)
    return im


def chat_header(header):
    im = Image.new("RGBA", (W - 2 * 60, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width, im.height], radius=40, fill=(24, 23, 27, 235))
    try:
        lg = brand.logo(150)
        av = Image.new("RGBA", (104, 104), (0, 0, 0, 0)); ImageDraw.Draw(av).ellipse([0, 0, 104, 104], fill=(255, 255, 255))
        lg.thumbnail((84, 84)); av.alpha_composite(lg, ((104 - lg.width) // 2, (104 - lg.height) // 2))
        im.alpha_composite(av, (26, 23))
    except Exception:
        pass
    d.text((152, 30), "Coach · ChessTalentsFactory", font=F.font(F.F_UI, 40), fill=F.CREAM)
    d.ellipse([152, 96, 168, 112], fill=(60, 200, 110))
    d.text((180, 86), "online", font=F.font(F.F_UI2, 32), fill=F.MUTED)
    return im


def render_chat(sc, seed, out):
    msgs = sc["messages"]
    t = 1.6                                             # header + title first
    timeline = []
    for m in msgs:
        typing = 0.9 if m["from"] == "coach" else 0.35
        appear = t + typing
        timeline.append((t, appear, m))
        t = appear + 0.8 + 0.2 * _words(m["text"])
    talk_end = t + 0.8
    CTA = 4.8
    total = talk_end + CTA
    bubs = [bubble(m["text"], m["from"]) for m in msgs]
    gap = 26
    area_top, area_bot = 450, 1500
    hdr = chat_header(sc["header"])
    title = F.label(sc["header"], 34)

    def frames():
        for fi in range(int(total * FPS)):
            tt = fi / FPS
            fr = Image.new("RGBA", (W, H))
            if tt < talk_end:
                F.draw_bg(fr, seed, tt, total)
                fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 110)))
                shown = [k for k, (ts, ap, m) in enumerate(timeline) if tt >= ap]
                typing_k = next((k for k, (ts, ap, m) in enumerate(timeline) if ts <= tt < ap and m["from"] == "coach"), None)
                heights = [bubs[k].height + gap for k in shown] + ([84 + gap] if typing_k is not None else [])
                over = max(0.0, sum(heights) - (area_bot - area_top))
                y = area_top - over
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                for k in shown:
                    b = bubs[k]; age = tt - timeline[k][1]
                    e = F.ease_out(age / 0.28)
                    x = 64 if timeline[k][2]["from"] == "coach" else W - 64 - b.width
                    layer.alpha_composite(F.alpha(b, F.clamp(e)), (int(x), int(y + (1 - e) * 30)))
                    y += b.height + gap
                if typing_k is not None:
                    layer.alpha_composite(typing_dots(tt), (64, int(y)))
                mask = F.cached("chatmask", lambda: Image.fromarray(
                    (np.clip((np.arange(H)[:, None] - (area_top - 40)) / 70.0, 0, 1) * 255).repeat(W, 1).astype(np.uint8)))
                layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer.getchannel("A")), np.asarray(mask))))
                fr.alpha_composite(layer)
                F.paste(fr, title, W / 2, 215, 1, F.clamp(tt / 0.4))
                F.paste(fr, hdr, W / 2, 340, 1, F.clamp((tt - 0.2) / 0.4))
                F.progress(fr, tt, total)
            else:
                F.cta_card(fr, tt - talk_end, seed, total)
            yield fr

    n = int(total * SR)
    bed, track = F.music(total, seed, energy=0.45)
    mix = bed[:n] * 0.85
    def put(x, at, g=1.0):
        a = int(at * SR); b = min(n, a + len(x))
        if a < n: mix[a:b] += g * x[:b - a]
    for ts, ap, m in timeline:
        put(F.soft_tick(1180 if m["from"] == "coach" else 1560, 0.07), ap)
    put(F.swell(0.8, 0.05), talk_end - 0.8)
    put(F.bell(784, 0.1), talk_end + 1.0)
    wav = F.write_wav(F.master(mix, target_db=-15.0), out.replace(".mp4", "_a.wav"))
    F.encode(frames(), wav, out)
    os.remove(wav)
    return total, track


# ----------------------------------------------------------------------- build
def build(seed, out, style="kinetic", use_ai=True):
    topic, sc, used_ai, err = None, None, False, None
    if use_ai and os.environ.get("GEMINI_API_KEY"):
        try:
            topic = F.pick_topic(style, seed)
            sc = write(style, topic, seed); used_ai = True
        except Exception as e:
            err = str(e)[:200]; print("textreel: AI copy failed, using evergreen:", err, flush=True)
    if sc is None:
        sc = evergreen(style, seed)
    total, track = (render_chat if style == "chat" else render_kinetic)(sc, seed, out)
    hook = sc.get("caption_hook") or (sc.get("hook") if style == "kinetic" else sc["messages"][0]["text"])
    cap = F.caption(hook, sc.get("caption_body", ""), seed=seed)
    open(out.replace(".mp4", ".txt"), "w").write(cap)
    title = sc.get("hook") or sc.get("header")
    F.remember({"format": style, "topic": topic and topic["id"], "evergreen": None if used_ai else sc.get("id"),
                "title": title, "music": track})
    return {"format": style, "engine": "ai" if used_ai else "evergreen", "topic": topic and topic["id"],
            "story": title, "hook": hook, "headline": title, "shape": sc.get("shape"), "duration": round(total, 1),
            "music": track, "cta": "keyword", "copy_error": err}


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "kinetic"
    os.makedirs("out", exist_ok=True)
    print(build(int(sys.argv[2]) if len(sys.argv) > 2 else 7, f"out/test_{st}.mp4", st, use_ai=False))
