"""Carousels for chess parents: the most saved and shared format on Instagram for advice content.

7 slides at 1080x1350 (cover, 5 points, closing CTA), same cinematic look as the reels. Every slide is published
as a short video slide (Instagram's API only uploads videos directly; image slides would need a public URL), with a
very slow push-in and the music bed, so it feels alive. If the carousel can't be published, run_daily turns the
same slides into a reel (slideshow) so the slot is never lost.

python make_carousel.py   -> renders out/test_carousel/ (evergreen content) + out/test_carousel_reel.mp4
"""
import json, os, random, sys
import numpy as np
from PIL import Image, ImageDraw

import brand
import formats as F

HERE = os.path.dirname(os.path.abspath(__file__))
EVERGREEN = os.path.join(HERE, "evergreen_faceless.json")
CW, CH = 1080, 1350
SLIDE_S = 5.0

PROMPT = """You write an Instagram CAROUSEL (7 slides) for {name}, for chess PARENTS.
{audience}
{honesty}
{rules}
TODAY'S PARENT TOPIC: {q}
WHAT A GOOD COACH WOULD HONESTLY SAY: {angle}
Recent posts (do not repeat): {recent}

Slide 1 (cover): "kicker" (2-3 words, e.g. "For chess parents", "Save this") and "title" (max 9 words, a list
promise like "5 signs...", "5 mistakes...", "What to say when...") with 1 "hl" word.
Slides 2-6: exactly 5 points. Each has "title" (max 7 words) and "body" (12-26 words: concrete, kind, practical).
"final": one line for the last slide (max 10 words), a takeaway.
"caption_hook" (max 12 words, one emoji max) and "caption_body" (2 short sentences, invite them to save or share).
Return JSON: {{"cover": {{"kicker": str, "title": str, "hl": [str]}}, "slides": [{{"title": str, "body": str}}],
"final": str, "caption_hook": str, "caption_body": str}}"""


def validate(sc):
    cv = sc.get("cover") or {}
    sl = [s for s in (sc.get("slides") or []) if str(s.get("title", "")).strip() and str(s.get("body", "")).strip()]
    if not cv.get("title") or len(sl) < 4:
        raise ValueError("need a cover title and 5 slides")
    sl = sl[:5]
    if len(cv["title"].split()) > 11:
        raise ValueError("cover title too long")
    for s in sl:
        if len(s["title"].split()) > 8 or len(s["body"].split()) > 30:
            raise ValueError(f"slide too long: {s['title'][:40]}")
    sc["slides"] = sl
    sc["final"] = str(sc.get("final") or "Small changes, big difference.")
    cv["kicker"] = " ".join(str(cv.get("kicker") or "For chess parents").split()[:3])
    F.check_text([cv["title"], cv["kicker"], sc["final"], sc.get("caption_hook", ""), sc.get("caption_body", "")] +
                 [s["title"] + " " + s["body"] for s in sl])
    return sc


def _bg(seed, k):
    big = F.cinematic_bg(seed)
    w = big.width; h = int(w * CH / CW)
    y = int((big.height - h) * 0.55)
    im = big.crop((0, y, w, y + h)).resize((CW, CH), Image.LANCZOS)
    im.alpha_composite(Image.new("RGBA", (CW, CH), (0, 0, 0, 70 if k else 30)))
    return im


def _footer(im, i, n):
    d = ImageDraw.Draw(im)
    f = F.font(F.F_UI2, 30)
    d.text((F.MX, CH - 92), "@" + brand.IG_HANDLE, font=f, fill=F.MUTED)
    for k in range(n):
        x = CW / 2 - (n - 1) * 13 + k * 26
        d.ellipse([x - 5, CH - 80, x + 5, CH - 70], fill=F.ORANGE if k == i else (110, 104, 100))
    if i < n - 1:
        s = "Swipe →"
        d.text((CW - F.MX - f.getlength(s), CH - 92), s, font=f, fill=F.CREAM)


def _text_block(im, text, f, x, y, maxw, color, hl=(), line=1.18):
    d = ImageDraw.Draw(im)
    hl = {F._norm(h) for x_ in hl for h in str(x_).split()}
    lines = F.wrap(str(text).split(), f, maxw)
    for li, ln in enumerate(lines):
        xx = x
        for w in ln:
            ww = f.getlength(w)
            if F._norm(w) in hl:
                d.rounded_rectangle([xx - 10, y + li * f.size * line + f.size * 0.08, xx + ww + 10,
                                     y + li * f.size * line + f.size * 1.18], radius=10, fill=F.ORANGE)
            d.text((xx, y + li * f.size * line), w, font=f, fill=(255, 255, 255) if F._norm(w) in hl else color)
            xx += ww + f.getlength(" ")
    return len(lines) * f.size * line


def slides(sc, seed):
    n = len(sc["slides"]) + 2
    out = []
    # cover
    im = _bg(seed, 0)
    F.paste(im, F.cached("bmc", F._brand_mark), CW / 2, 110)
    k = F.label(sc["cover"]["kicker"], 34)
    im.alpha_composite(k, (F.MX, 430))
    _text_block(im, sc["cover"]["title"], F.font(F.F_BLACK, 104), F.MX, 500, CW - 2 * F.MX, F.CREAM, sc["cover"].get("hl", []))
    _footer(im, 0, n); out.append(im)
    # points
    for i, s in enumerate(sc["slides"], start=1):
        im = _bg(seed + i, 1)
        num = f"{i:02d}"
        fnum = F.font(F.F_BLACK, 220)
        nim = Image.new("RGBA", (int(fnum.getlength(num)) + 20, 260), (0, 0, 0, 0))
        ImageDraw.Draw(nim).text((10, 0), num, font=fnum, fill=(0, 0, 0, 0), stroke_width=4, stroke_fill=F.ORANGE)
        im.alpha_composite(nim, (F.MX - 6, 170))
        h = _text_block(im, s["title"], F.font(F.F_BLACK, 78), F.MX, 470, CW - 2 * F.MX, F.CREAM)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([F.MX, 500 + h, F.MX + 90, 508 + h], radius=4, fill=F.ORANGE)
        _text_block(im, s["body"], F.font(F.F_UI2, 46), F.MX, 550 + h, CW - 2 * F.MX, (226, 220, 214), line=1.36)
        _footer(im, i, n); out.append(im)
    # closing CTA
    im = _bg(seed + 9, 1)
    lg = F.cached("ccl", lambda: brand.logo_card(500))
    F.paste(im, lg, CW / 2, 300)
    _text_block(im, sc["final"], F.font(F.F_BLACK, 76), F.MX, 470, CW - 2 * F.MX, F.CREAM)
    b = F.button(f'Comment "{brand.KEYWORD}"', 56)
    F.paste(im, b, CW / 2, 930)
    f = F.font(F.F_UI2, 40)
    s = "We'll send you our free training video for parents"
    ImageDraw.Draw(im).text(((CW - f.getlength(s)) / 2, 1040), s, font=f, fill=F.MUTED)
    _footer(im, n - 1, n); out.append(im)
    return out


def slide_videos(imgs, seed, folder):
    """Each slide -> a 5 s MP4 (slow push-in + its own slice of one continuous music bed)."""
    os.makedirs(folder, exist_ok=True)
    total = SLIDE_S * len(imgs)
    bed, track = F.music(total, seed, energy=0.5)
    bed = F.master(bed, target_db=-17.0)
    paths = []
    for i, im in enumerate(imgs):
        seg = bed[int(i * SLIDE_S * F.SR): int((i + 1) * SLIDE_S * F.SR)].copy()
        r = int(0.03 * F.SR); seg[:r] *= np.linspace(0, 1, r); seg[-r:] *= np.linspace(1, 0, r)
        wav = F.write_wav(seg, os.path.join(folder, f"s{i}.wav"))
        big = im.resize((int(CW * 1.04), int(CH * 1.04)), Image.LANCZOS)
        def frames(big=big):
            nfr = int(SLIDE_S * F.FPS)
            for fi in range(nfr):
                k = F.ease_in_out(fi / nfr); s = 1.04 - 0.04 * k
                w, h = int(CW * s), int(CH * s)
                x, y = (big.width - w) // 2, (big.height - h) // 2
                yield big.crop((x, y, x + w, y + h)).resize((CW, CH), Image.BILINEAR)
        p = os.path.join(folder, f"slide_{i + 1}.mp4")
        F.encode(frames(), wav, p, CW, CH)
        os.remove(wav)
        paths.append(p)
    return paths, track


def slideshow_reel(imgs, seed, out):
    """Fallback: the same slides as one vertical reel (each slide centred on the cinematic background)."""
    per = 3.6
    total = per * len(imgs) + 0.4
    def frames():
        for fi in range(int(total * F.FPS)):
            t = fi / F.FPS
            i = min(len(imgs) - 1, int(t / per)); lt = t - i * per
            fr = Image.new("RGBA", (F.W, F.H)); F.draw_bg(fr, seed, t, total)
            fr.alpha_composite(Image.new("RGBA", (F.W, F.H), (0, 0, 0, 120)))
            cur = imgs[i]
            a = F.clamp(lt / 0.3)
            if i > 0 and lt < 0.3:
                F.paste(fr, imgs[i - 1], F.W / 2, F.H / 2 - 40, 1.0, 1 - a)
            F.paste(fr, cur, F.W / 2, F.H / 2 - 40 + (1 - F.ease_out(lt / 0.4)) * 30, 1.0, a)
            F.progress(fr, t, total)
            yield fr
    bed, _ = F.music(total, seed, energy=0.5)
    n = int(total * F.SR); mix = bed[:n].copy()
    for i in range(1, len(imgs)):
        a = int(i * per * F.SR); x = F.soft_tick(1400, 0.05); mix[a:a + len(x)] += x[:max(0, n - a)]
    wav = F.write_wav(F.master(mix, target_db=-15.0), out.replace(".mp4", "_a.wav"))
    F.encode(frames(), wav, out)
    os.remove(wav)
    return out


def evergreen(seed):
    lib = [x for x in json.load(open(EVERGREEN)) if x["format"] == "carousel"]
    used = {r.get("evergreen"): i for i, r in enumerate(F.recent(400)) if r.get("evergreen")}
    return json.loads(json.dumps(min(lib, key=lambda x: (used.get(x["id"], -1), random.Random(seed).random()))))


def build(seed, out_dir, use_ai=True):
    topic, sc, used_ai, err = None, None, False, None
    if use_ai and os.environ.get("GEMINI_API_KEY"):
        try:
            topic = F.pick_topic("carousel", seed)
            rec = "; ".join(r.get("title") or "" for r in F.recent(15)) or "none"
            sc = F.ask_json(PROMPT.format(name=brand.NAME, audience=brand.AUDIENCE, honesty=brand.HONESTY,
                                          rules=F.VOICE_RULES, q=topic["q"], angle=topic["angle"], recent=rec), validate)
            used_ai = True
        except Exception as e:
            err = str(e)[:200]; print("carousel: AI copy failed, using evergreen:", err, flush=True)
    if sc is None:
        sc = evergreen(seed)
    imgs = slides(sc, seed)
    os.makedirs(out_dir, exist_ok=True)
    for i, im in enumerate(imgs):
        im.convert("RGB").save(os.path.join(out_dir, f"slide_{i + 1}.jpg"), quality=93)
    vids, track = slide_videos(imgs, seed, out_dir)
    reel = slideshow_reel(imgs, seed, out_dir.rstrip("/") + "_reel.mp4")
    cap = F.caption(sc.get("caption_hook") or sc["cover"]["title"], sc.get("caption_body", ""), seed=seed)
    open(reel.replace(".mp4", ".txt"), "w").write(cap)
    F.remember({"format": "carousel", "topic": topic and topic["id"], "evergreen": None if used_ai else sc.get("id"),
                "title": sc["cover"]["title"], "music": track})
    return {"format": "carousel", "engine": "ai" if used_ai else "evergreen", "topic": topic and topic["id"],
            "story": sc["cover"]["title"], "headline": sc["cover"]["title"], "hook": sc.get("caption_hook"),
            "slides": vids, "reel": reel, "caption": cap, "music": track, "cta": "keyword", "copy_error": err}


if __name__ == "__main__":
    print(build(int(sys.argv[1]) if len(sys.argv) > 1 else 5, "out/test_carousel", use_ai=False))
