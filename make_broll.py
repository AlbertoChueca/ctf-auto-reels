"""Premium real-footage reels for chess PARENTS (who often don't play chess themselves).

Every reel = real stock footage (Pexels/Pixabay, graded per creator) + voice + kinetic text in varied layouts +
optional glass overlays (real progress chart, the 6-level ladder, a Square 65 key, an approved stat, a checklist).
Structure ("shape") varies per reel: story, listicle, myth vs fact, POV, letter to parents, Q&A, before/after.
The AI writes; hard rules (validate_broll) + the creative director (copy chief, brand guardian with the parent test,
art director on a real storyboard) keep it honest, on-brand and readable.
"""
import json, os, random, re, subprocess, time
import numpy as np
import soundfile as sf
from PIL import Image

import brand, guard, stock
import design as D
import broll_design as B
import make_explainer as E
import make_hype as HY

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = D.W, D.H, D.FPS, D.SR
BW, BH = int(W * 1.06) // 2 * 2, int(H * 1.06) // 2 * 2
LOG = E.LOG

SHAPES = {
    "story": "a short, true-to-life moment between a parent and child -> what is really happening -> what helps -> invitation",
    "listicle": "'3 signs...', '3 mistakes...' or '3 things...': hook, then exactly 3 numbered scenes (layout 'number'), then close",
    "myth_fact": "open with a belief many parents hold (the myth) -> the truth -> why -> what to do instead",
    "pov": "'POV: your child just...' first scene in second person, emotional and specific, then reframe with our insight",
    "letter": "a calm, direct message from an experienced coach to the parent ('Dear chess parent...')",
    "qa": "a real question parents ask before hiring a coach -> an honest answer in 3 beats",
    "before_after": "before structured training vs after (habits, mindset, confidence, results)",
}
GRADE_BY_AGENT = {"analyst": "cool", "storyteller": "warm", "mythbuster": "punch", "parent_whisperer": "soft",
                  "trend_scout": "punch"}
OVERLAYS = ["none", "chart", "ladder", "key_card", "stat", "list"]
SAFE_SUCCESS_BROLL = ["hands moving chess piece close up", "chess board close up wooden", "trophy on table",
                      "tournament hall people", "chess clock close up", "notebook pen study desk"]
CHILD_WORDS = re.compile(r"\b(boy|girl|child|children|kid|kids|son|daughter|teen|face|portrait|student)\b", re.I)


# ----------------------------------------------------------------------- context
def case_progress(case):
    blob = (case.get("text", "") + " " + " ".join(case.get("facts", [])))
    m = re.search(r"from (\d[\d,]*)\+? to \+?(\d[\d,]*)\+?(?: rating)?(?: in (?:only |just )?(\d+) (months?|years?))?", blob, re.I)
    if not m:
        return None
    a, b = guard.to_int(m.group(1)), guard.to_int(m.group(2))
    if not (a and b and b > a):
        return None
    period = f"{m.group(3)} {m.group(4)}" if m.group(3) else ""
    return {"from": a, "to": b, "period": period}


def context(pillar):
    ctx, extra = E.context_for(pillar)
    info = {}
    if extra.get("case"):
        c = next((c for c in guard.cases() if c["id"] == extra["case"]), None)
        if c:
            info["progress"] = case_progress(c)
    if extra.get("key") or extra.get("anchor_key"):
        n = extra.get("key") or extra.get("anchor_key")
        k = next((k for k in E.method_bank() if k["n"] == n), None)
        if k:
            info["key"] = k
    return ctx, extra, info


# ----------------------------------------------------------------------- script
PROMPT = """{creator}

You write a 30-45 second vertical REAL-FOOTAGE reel for {name}.
{bible}
{audience}
{narrator}
{honesty}
{claims}
{cases}
FACTS you may use freely: {facts}

THE VIEWER: a parent who has NEVER played chess; their child loves chess. Talk about THEIR child and THEIR life:
the drive to tournaments, tears after a loss, screens vs focus, school, confidence, money and time well spent,
choosing the right coach. Chess terms only if translated into everyday words (school grades, sports, music practice).

PILLAR: {pillar}. {brief}
{context}
REEL SHAPE (follow it): {shape} = {shape_desc}
TODAY'S CREATIVE BRIEF (A/B experiment): hook style = {hook_style}; theme = {theme}.
{playbook}
Recent reels (do NOT repeat their idea, shape or headlines): {recent}

Write 5 or 6 scenes. Each scene:
- "headline": the ON-SCREEN text, 2-7 words, punchy; scene 1 = the hook that stops a parent's scroll in 1 second.
- "highlight": 1-2 words of the headline in orange.
- "narration": 8-22 spoken words, short sentences, warm expert-to-parent voice, numbers as words. Total {words} words.
- "delivery": 3-8 word acting direction (calm, warm, confident; vary).
- "layout": one of top | center | lower | question | number | quote.
  center = one big statement; question = a parent's question card; number = item n of a numbered list (listicles);
  quote = ONLY for a sentence from TODAY'S KEY, exactly as the book says it.
- "broll": 2-4 SIMPLE English words a stock-video site really has (subject + action), matching what the voice says:
  e.g. "boy playing chess", "girl doing homework", "mother hugging son", "family car trip", "chess pieces closeup",
  "child using tablet", "chess clock", "trophy", "classroom children", "father son talking". Children aged 7-14,
  never babies or toddlers. Every scene a DIFFERENT shot. No brands, no text, no celebrities.{success_rule}
- "overlay": none | chart | ladder | key_card | stat | list. {overlay_rule}
- "params": for number {{"n": i, "total": 3}}; ladder {{"from_level": 0-5, "to_level": 0-5}}; stat {{"value": "250+",
  "label": "students trained"}} (approved numbers only); list {{"items": [max 3, max 5 words]}}; key_card {{}};
  quote {{"source": "Square 65, Key n"}}.
Rules: max 2 overlays per reel; NO call to action inside the scenes (no "comment", "link in bio", "book a call",
"follow"): the end card adds the only one, so the last scene just leads naturally into it; no prices, no guarantees,
no competitors; never a number about results unless it is in APPROVED CLAIMS or the REAL CASE.
- caption_hook: Instagram first line for parents, max 12 words, one emoji allowed. caption_body: 1-2 useful sentences.
Return JSON: {{"title": str, "summary": str, "shape": str, "caption_hook": str, "caption_body": str,
"scenes": [{{"headline": str, "highlight": [str], "narration": str, "delivery": str, "layout": str, "broll": str,
"overlay": str, "params": {{}}}}]}}"""


def overlay_rule(pillar, info):
    r = []
    if pillar == "success" and info.get("progress"):
        r.append("Use 'chart' (the real progress of TODAY'S STUDENT CASE) in exactly one scene.")
    if pillar == "rating":
        r.append("Use 'ladder' in one scene to show our 6 levels.")
    if info.get("key"):
        r.append("You may use 'key_card' once to show TODAY'S KEY / METHOD ANCHOR.")
    if pillar not in ("success",):
        r.append("Do not use 'chart'.")
    return " ".join(r)


def write_script(pillar, arms, ctx, info, agent):
    import make_story as MS, strategy, studio
    recent = E._recent(40)
    last_shapes = [r.get("shape") for r in recent[-3:]]
    shape = arms.get("shape") if arms.get("shape") in SHAPES else None
    if shape is None or shape in last_shapes:          # never the same structure as the last 3 reels
        shape = random.choice([x for x in SHAPES if x not in last_shapes] or list(SHAPES))
    body0 = {"contents": [{"role": "user", "parts": [{"text": PROMPT.format(
        creator=studio.brief(agent) if agent in studio.CREATORS else "", name=brand.NAME, bible=brand.bible(),
        audience=brand.AUDIENCE, narrator=brand.narrator_text(), honesty=brand.HONESTY, claims=guard.approved_text(),
        cases=brand.cases_text(), facts="; ".join(brand.FACTS), pillar=pillar, brief=E.PILLAR_BRIEF.get(pillar, ""),
        context=ctx, shape=shape, shape_desc=SHAPES[shape], hook_style=arms.get("hook_style", "your best idea"),
        theme=arms.get("theme", "your best idea"),
        playbook=("WHAT WORKS FOR OUR AUDIENCE:\n" + strategy.playbook_text()) if strategy.playbook_text() else "",
        recent="; ".join(f"{r.get('format', 'motion')}/{r.get('shape', '-')}/{r.get('pillar')}: {r.get('headline')}" for r in recent[-15:]) or "none",
        words="75-115",
        success_rule=(" For this real student story use NON-IDENTIFYING footage only (hands, board, clock, trophy, "
                      "tournament hall, silhouettes from behind): the footage illustrates, it is not the student.")
        if pillar == "success" else "",
        overlay_rule=overlay_rule(pillar, info))}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.05}}
    last = None
    for model in MS.text_models(3):
        body = body0
        for attempt in range(2):
            txt = ""
            try:
                j = MS._post(model, body)
                txt = j["candidates"][0]["content"]["parts"][0]["text"]
                sc = json.loads(re.sub(r"^```(json)?|```$", "", txt.strip()))
                sc["shape"] = shape
                out = validate(sc, pillar, info)
                novelty(out, recent)
                print(f"broll script: {model}" + (" (repaired)" if attempt else ""), flush=True)
                return out
            except ValueError as e:
                last = e; print(f"broll script: {model} rejected: {str(e)[:160]}", flush=True)
                body = {**body0, "contents": body0["contents"] + [
                    {"role": "model", "parts": [{"text": txt or "{}"}]},
                    {"role": "user", "parts": [{"text": f"Rejected by our checks: {e}. Rewrite the whole script fixing "
                                                        "ONLY that. Same JSON schema."}]}]}
            except Exception as e:
                last = e; print(f"broll script: {str(e)[:160]}", flush=True); break
    raise RuntimeError(f"broll script failed: {last}")


def _tok(t):
    return set(re.findall(r"[a-z']{3,}", str(t or "").lower())) - {"your", "the", "and", "you", "for", "this", "that",
                                                                 "with", "child", "chess", "kid", "kids"}


def novelty(sc, recent):
    """Every reel must be new: hook and idea may not repeat any of the last 40 reels."""
    h = _tok(sc["scenes"][0]["headline"]) | _tok(sc.get("caption_hook"))
    t = _tok(sc.get("title"))
    for r in recent[-40:]:
        rh = _tok(r.get("headline")) | _tok(r.get("hook"))
        if h and rh and len(h & rh) / len(h | rh) > 0.45:
            raise ValueError(f"hook too similar to a recent reel ({r.get('headline')!r}); write a completely new hook and angle")
        rt = _tok(r.get("title"))
        if t and rt and len(t & rt) / len(t | rt) > 0.6:
            raise ValueError(f"idea too similar to a recent reel ({r.get('title')!r}); choose a different idea")


def _words(x, n):
    return " ".join(str(x or "").split()[:n])


def validate(sc, pillar, info=None):
    """Hard rules the AI cannot break."""
    info = info if info is not None else (sc.get("_info") or {})
    scenes = (sc.get("scenes") or [])[:6]
    if len(scenes) < 4:
        raise ValueError("needs 4-6 scenes")
    n_over, num_i = 0, 0
    nums = sum(1 for s in scenes if s.get("layout") == "number")
    key = info.get("key")
    for i, s in enumerate(scenes):
        s["headline"] = _words(s.get("headline"), 7) or "Chess parents"
        s["narration"] = _words(s.get("narration"), 26)
        s["highlight"] = [h for h in (s.get("highlight") or []) if isinstance(h, str)][:2]
        s["delivery"] = _words(s.get("delivery"), 8) or "warm, confident"
        lay = s.get("layout") if s.get("layout") in B.LAYOUTS else "top"
        p = s.get("params") if isinstance(s.get("params"), dict) else {}
        ov = s.get("overlay") if s.get("overlay") in OVERLAYS else "none"
        if ov != "none":
            n_over += 1
            if n_over > 2:
                ov = "none"
        if ov == "chart" and not info.get("progress"):
            ov = "none"
        if ov == "ladder":
            try:
                a, b = int(p.get("from_level", 1)), int(p.get("to_level", 3))
                p["from_level"], p["to_level"] = max(0, min(5, a)), max(0, min(5, b))
            except Exception:
                p["from_level"], p["to_level"] = 1, 3
        if ov == "key_card":
            if key:
                p["key"], p["title"] = key["n"], key["title"]
            else:
                ov = "none"
        if ov == "stat":
            val, lab = _words(p.get("value"), 2), _words(p.get("label"), 5)
            ok, _ = guard.claims_ok(f"{val} {lab}") if val else (False, None)
            num = guard.to_int(re.sub(r"[^0-9,]", "", val)) if val else None
            if not ok or num is None or num not in guard.allowed_numbers():
                ov = "none"
            else:
                p["value"], p["label"] = val, lab
        if ov == "list":
            p["items"] = [_words(x, 5) for x in (p.get("items") or []) if str(x).strip()][:3]
            if not p["items"]:
                ov = "none"
        if lay == "number":
            num_i += 1
            p["n"], p["total"] = num_i, max(nums, 1)
        if lay == "quote":
            src_ok = False
            if key:
                kt = set(re.findall(r"[a-z']+", key["text"].lower()))
                hw = re.findall(r"[a-z']+", s["headline"].lower())
                src_ok = bool(hw) and sum(w in kt for w in hw) / len(hw) >= 0.8
            if src_ok:
                p["source"] = f"Square 65, Key {key['n']}"
                s["headline"] = _words(s["headline"], 9)
            else:
                lay = "center"; p.pop("source", None)
        if ov != "none" and lay not in ("top", "number", "question"):
            lay = "top"                                   # never stack big text over a card
        br = _words(re.sub(r"[^a-zA-Z ]", " ", str(s.get("broll") or "")), 5).lower() or "child playing chess"
        if pillar == "success" and CHILD_WORDS.search(br):
            br = SAFE_SUCCESS_BROLL[i % len(SAFE_SUCCESS_BROLL)]
        s.update(layout=lay, overlay=ov, params=p, broll=br)
    words = sum(len(s["narration"].split()) for s in scenes)
    if not 55 <= words <= 140:
        raise ValueError(f"narration length {words} words (needs 75-115)")
    cta_txt = " ".join(f"{s['headline']} {s['narration']}" for s in scenes).lower()
    m = re.search(r"\b(comment|link in (?:the )?bio|book (?:a|your) (?:free )?call|dm us|send us a|click|sign up|"
                  r"follow (?:us|for)|subscribe|tap the|watch (?:the|our) (?:free )?(?:video|training))\b", cta_txt)
    if m:
        raise ValueError(f"the scenes contain a call to action ({m.group(0)!r}); remove it, the end card adds the "
                         "only call to action")
    hard, soft = guard.jargon({"scenes": scenes})
    if hard:
        raise ValueError(f"chess jargon a non-playing parent cannot follow: {hard[:4]}")
    if len(soft) > 2:
        raise ValueError(f"too much chess vocabulary for parents ({soft}); use everyday words")
    text = " ".join(f"{s['headline']} {s['narration']} {json.dumps(s['params'])}" for s in scenes)
    text += " " + str(sc.get("caption_hook", "")) + " " + str(sc.get("caption_body", ""))
    text = re.sub(r"\b(?:age|aged|at)\s+\d+\b", " ", text)
    ok, bad = guard.claims_ok(text)
    if not ok:
        raise ValueError(f"unapproved claims: {bad}")
    sc["scenes"] = scenes
    sc["_info"] = info
    if sc.get("shape") not in SHAPES:
        sc["shape"] = "story"
    return sc


def slots_text():
    return ("Each scene has: headline (on-screen text), highlight, narration, delivery, layout (top|center|lower|"
            "question|number|quote), broll (stock footage search), overlay (none|chart|ladder|key_card|stat|list), "
            "params. Keep the scene count, the shape and the overlays; you may change headline, highlight, layout, "
            "broll and narration.")


# ----------------------------------------------------------------------- footage
class Clip:
    """Streams frames of a prepared clip (BWxBH); loops if the scene is longer than the clip.
    path=None -> no footage available: a premium dark brand background (the camera move still animates it)."""
    def __init__(self, path):
        self.path = path; self.p = None; self.still = None
        if path is None:
            self.still = D.cached("broll_still", lambda: D.bg_dark().convert("RGB").resize((BW, BH), Image.LANCZOS))
        else:
            self._open()

    def _open(self):
        if self.p:
            self.p.kill()
        self.p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", self.path, "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-s", f"{BW}x{BH}", "-"], stdout=subprocess.PIPE)

    def frame(self):
        if self.still is not None:
            return self.still
        n = BW * BH * 3
        buf = self.p.stdout.read(n)
        if len(buf) < n:
            self._open(); buf = self.p.stdout.read(n)
        return Image.frombytes("RGB", (BW, BH), buf)

    def close(self):
        if self.p:
            self.p.kill()


def camera(img, t, dur, move):
    """Slow, premium camera move inside the 6 % margin: push, drift left/right, rise."""
    k = D.ease_in_out(t / max(dur, 0.1))
    mx, my = BW - W, BH - H
    if move == "push":
        z = 1 + 0.05 * k
        cw, ch = int(BW / z), int(BH / z)
        x, y = (BW - cw) // 2, (BH - ch) // 2
        return img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)
    if move == "left":
        x, y = int(mx * (1 - k)), my // 2
    elif move == "right":
        x, y = int(mx * k), my // 2
    else:  # rise
        x, y = mx // 2, int(my * (1 - k))
    return img.crop((x, y, x + W, y + H))


SAFE_BROLL = ["boy playing chess", "girl playing chess", "chess pieces closeup", "chess board", "child studying",
              "chess clock", "children classroom", "family home", "hands chess"]


def _sheet(rows):
    """rows: [(label, [PIL thumbs])] -> one contact sheet for the footage judge."""
    from PIL import ImageDraw
    cw, ch, lab, cols = 256, 144, 34, 6
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, len(rows) * (ch + lab + 10) + 8), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    f = D.font(D.F_UI, 18)
    for r, (label, ims) in enumerate(rows):
        y = 8 + r * (ch + lab + 10)
        d.text((8, y + 4), label[:150], font=f, fill=(20, 20, 20))
        for k, im in enumerate(ims[:cols]):
            x = 8 + k * (cw + 8)
            if im is None:
                d.rectangle([x, y + lab, x + cw, y + lab + ch], fill=(200, 200, 200)); continue
            t = im.copy(); t.thumbnail((cw, ch))
            sheet.paste(t, (x + (cw - t.width) // 2, y + lab + (ch - t.height) // 2))
            d.rectangle([x, y + lab, x + 30, y + lab + 24], fill=(0, 0, 0)); d.text((x + 8, y + lab + 2), str(k), font=f, fill=(255, 255, 255))
    return sheet


def judge_footage(scenes, need, cands, pillar):
    """Gemini looks at the real thumbnails and picks, per scene, the clip that matches the voice (or none)."""
    import reviewer
    rows, idx = [], []
    for i in need:
        ims = [stock.thumbnail(c) for c in cands[i]]
        rows.append((f"SCENE {i} (searched: {cands[i][0].get('query', '')}): voice says: {scenes[i]['narration'][:80]}", ims)); idx.append(i)
    if not rows:
        return {}
    sheet = _sheet(rows)
    rule = ("This is a REAL student's story: reject any clip where a child's face is clearly identifiable; prefer hands, "
            "boards, clocks, trophies, halls, silhouettes. " if pillar == "success" else "")
    res = reviewer._ask([{"text": f"""You are the footage editor of a premium chess academy's Instagram reels for US
parents. Each row is one scene (what the voice says) with numbered candidate stock clips (thumbnails).
For each scene pick the ONE candidate that best illustrates what the voice says, looks premium and real.
REJECT: animation, 3D/CGI, cartoons, green screen, text or watermarks, starry skies/abstract backgrounds, empty
furniture, babies or toddlers, snow/holiday scenes unrelated to the message, adults alone when the scene is about a
child, anything unrelated to children, families, school or chess, low quality. {rule}
If no candidate is good, pick -1 and give a better 2-4 word stock-video search (simple subject + action).
Rows (scene numbers): {idx}
Return JSON: {{"scenes": [{{"scene": int, "pick": int, "better_query": str}}]}}"""},
                         {"inline_data": {"mime_type": "image/jpeg", "data": reviewer._jpeg_b64(sheet, 1600)}}], 0.2)
    out = {}
    for r in res.get("scenes", []):
        try:
            out[int(r["scene"])] = (int(r.get("pick", -1)), (r.get("better_query") or "").strip())
        except Exception:
            pass
    return out


def fetch_clips(scenes, durs, grade, seed, pillar="pain", judge=True, only=None, used=None):
    """Search -> AI footage judge on real thumbnails (2 rounds, better queries) -> download + grade.
    Returns a list of paths (None = designed background)."""
    n = len(scenes)
    only = list(range(n)) if only is None else list(only)
    used = set(used or ())
    judge = judge and bool(os.environ.get("GEMINI_API_KEY")) and os.environ.get("FOOTAGE_JUDGE", "on") != "off"
    queries = {i: scenes[i]["broll"] for i in only}
    chosen = {}
    for rnd in range(3):
        need = [i for i in only if i not in chosen]
        if not need:
            break
        cands = {}
        for i in need:
            excl = used | {c["uid"] for c in chosen.values()}
            cands[i] = stock.search(queries[i], durs[i] + 0.6, seed=f"{seed}-{i}-{rnd}", exclude=excl)
        if not judge or rnd == 2:      # no AI eyes: only a clip whose tags clearly match (else designed background)
            taken = {c["uid"] for c in chosen.values()}
            for i in need:
                ok = [c for c in cands[i] if c["uid"] not in taken and stock.relevance(c, queries[i]) >= 2
                      or (c["uid"].startswith(("local-", "lib-")) and c["uid"] not in taken)]
                if ok:
                    chosen[i] = ok[0]; taken.add(ok[0]["uid"])
            break
        try:
            verdict = judge_footage(scenes, [i for i in need if cands[i]], cands, pillar)
        except Exception as e:
            print("footage judge skipped:", str(e)[:150], flush=True)
            judge = False                              # fall back to strict tag matching
            continue
        taken = {c["uid"] for c in chosen.values()}
        for i in need:
            pick, better = verdict.get(i, (-1, ""))
            if cands[i] and 0 <= pick < len(cands[i]) and cands[i][pick]["uid"] not in taken:
                chosen[i] = cands[i][pick]; taken.add(chosen[i]["uid"])
                print(f"footage scene {i}: '{queries[i]}' -> {chosen[i]['uid']}", flush=True)
            else:
                nq = better or SAFE_BROLL[(i + rnd) % len(SAFE_BROLL)]
                if pillar == "success" and CHILD_WORDS.search(nq):
                    nq = SAFE_SUCCESS_BROLL[(i + rnd) % len(SAFE_SUCCESS_BROLL)]
                print(f"footage scene {i}: rejected '{queries[i]}' -> trying '{nq}'", flush=True)
                queries[i] = nq
    paths = [None] * n
    for i in only:
        c = chosen.get(i)
        s = scenes[i]
        if c:
            try:
                paths[i] = stock.fetch(c, durs[i] + 0.6, grade)
                s["_clip"] = {"uid": c["uid"], "query": queries[i], "asked": s["broll"]}
                s["broll"] = queries[i]
                continue
            except Exception as e:
                print("stock download:", str(e)[:150], flush=True)
        print(f"footage scene {i}: no good clip -> designed background", flush=True)
        s["_clip"] = {"uid": None, "query": None, "asked": s["broll"]}
    return paths


def first_frame(path):
    c = Clip(path); im = c.frame(); c.close()
    return camera(im, 0, 1, "push")


def scene_frame(base, s, t, dur, info, kind_first=False):
    fr = base.convert("RGBA")
    B.scrim(fr, s["layout"])
    B.overlay(fr, s, t, dur, info)
    B.on_screen(fr, s, t, dur)
    return fr


def storyboard_fn(paths, info, refetch=None):
    def make(sc, kind):
        if refetch:
            refetch(sc)
        tw, th, cols = 300, 533, 4
        shots = [(i, 0.0 if i == 0 else 3.0) for i in range(len(sc["scenes"]))]
        sheet = Image.new("RGB", (cols * (tw + 14) + 14, ((len(shots) + cols - 1) // cols) * (th + 50) + 14), (235, 235, 238))
        from PIL import ImageDraw
        d = ImageDraw.Draw(sheet)
        for k, (i, t) in enumerate(shots):
            s = dict(sc["scenes"][i]); s["_first"] = (i == 0)
            fr = scene_frame(first_frame(paths[i]), s, t + (1.5 if i == 0 else 0), 4.0, info)
            D.brand_bar(fr, i, len(shots), True)
            D.captions(fr, [(q * .3, w) for q, w in enumerate(s["narration"].split())], 1.0)
            x, y = 14 + (k % cols) * (tw + 14), 14 + (k // cols) * (th + 50)
            sheet.paste(fr.convert("RGB").resize((tw, th)), (x, y + 36))
            d.text((x, y + 6), f"SCENE {i + 1}: {s['layout']}/{s['overlay']} - footage: {s['broll']}"[:52],
                   font=D.font(D.F_UI, 18), fill=(30, 30, 30))
        return sheet
    return make


# ----------------------------------------------------------------------- build
def evergreen_script(pillar):
    lib = json.load(open(os.path.join(HERE, "evergreen_broll.json")))
    cases = {c["id"] for c in guard.cases()}
    lib = [x for x in lib if not x.get("case") or x["case"] in cases]
    used = {r.get("evergreen"): i for i, r in enumerate(E._recent(200)) if r.get("evergreen")}
    same = [x for x in lib if x["pillar"] == pillar] or lib
    sc = json.loads(json.dumps(min(same, key=lambda x: used.get(x["id"], -1))))
    info = {}
    if sc.get("case"):
        c = next((c for c in guard.cases() if c["id"] == sc["case"]), None)
        info["progress"] = case_progress(c) if c else None
    if sc.get("key"):
        info["key"] = next((k for k in E.method_bank() if k["n"] == sc["key"]), None)
    extra = {"evergreen": sc["id"], **{k: sc[k] for k in ("case", "key") if sc.get(k)}}
    return validate(sc, sc["pillar"], info), sc["pillar"], extra, info


def build(seed, out, pillar="pain", arms=None, agent=None, evergreen=False, mock=False):
    import voice, studio
    arms = arms or {}
    if agent in studio.CREATORS:
        studio.apply_look(agent)
    grade = GRADE_BY_AGENT.get(agent, random.Random(seed).choice(list(stock.GRADES)[:4]))
    kind = arms.get("cta") if arms.get("cta") in brand.CTA else (brand.CTA_MODE if brand.CTA_MODE in brand.CTA else "keyword")
    report = {}
    if evergreen or mock:
        sc, pillar, extra, info = evergreen_script(pillar)
    else:
        ctx, extra, info = context(pillar)
        if pillar in ("success", "remix") and not ctx:
            pillar = "pain"; ctx, extra, info = context(pillar)
        sc = write_script(pillar, arms, ctx, info, agent)
        if os.environ.get("REVIEWER", "on") != "off":
            import director
            shape_w = sc.get("shape")
            sc, report = director.direct(sc, pillar, ctx, slots_text(),
                                         lambda x, p: validate({**x, "shape": x.get("shape") or shape_w}, p, info), kind,
                                         agent=agent, art=False)
    scenes = sc["scenes"]
    shape0 = sc.get("shape")
    CT = brand.cta(kind)
    # ---- voice first: exact scene lengths
    voice.reset()
    texts = [s["narration"] for s in scenes] + [CT["say"]]
    A = voice.say_many(texts, speed=1.0, styles=[s.get("delivery") for s in scenes] + ["warm, confident, inviting"],
                       one_take=True)
    LEAD, PAD = 0.2, 0.4
    durs = [max(2.6, LEAD + len(a) / SR + PAD) for a in A[:-1]] + [max(4.6, LEAD + len(A[-1]) / SR + 1.6)]
    # ---- footage + art direction on a real storyboard
    paths = fetch_clips(scenes, durs, grade, seed, pillar)
    fetched = [s["broll"] for s in scenes]
    clips_meta = [s.get("_clip") for s in scenes]

    def refetch(sc_now):                               # the art director asked for other footage -> get it now,
        changed = [i for i, s in enumerate(sc_now["scenes"])   # so its next look sees the new clips
                   if i < len(fetched) and s["broll"] != fetched[i]]
        for i, s in enumerate(sc_now["scenes"]):
            if i < len(fetched) and i not in changed:
                s["_clip"] = clips_meta[i]; s["broll"] = fetched[i]
        if changed:
            used = {(c or {}).get("uid") for k, c in enumerate(clips_meta) if k not in changed}
            new = fetch_clips(sc_now["scenes"], durs, grade, f"{seed}-art", pillar, only=changed, used=used)
            for i in changed:
                paths[i] = new[i]; fetched[i] = sc_now["scenes"][i]["broll"]; clips_meta[i] = sc_now["scenes"][i]["_clip"]

    if not (evergreen or mock) and os.environ.get("REVIEWER", "on") != "off":
        import director
        sc = director.art_loop(sc, pillar, slots_text(), lambda x, p: validate({**x, "shape": x.get("shape") or shape0}, p, info),
                               kind, report, storyboard_fn=storyboard_fn(paths, info, refetch))
        refetch(sc)
        scenes = sc["scenes"]
    starts = np.cumsum([0.0] + durs[:-1]); total = float(sum(durs))
    words = []
    for i, a in enumerate(A):
        for ts, w in voice.align(a, texts[i]):
            words.append((starts[i] + LEAD + ts, w))
    # ---- audio
    rng = random.Random(seed)
    n = int(total * SR) + SR
    mix = np.zeros(n, np.float32)
    def put(x, at, g=1.0):
        a0 = max(0, int(at * SR)); b0 = min(n, a0 + len(x)); mix[a0:b0] += g * x[:b0 - a0]
    for i, a in enumerate(A):
        put(a.astype(np.float32), starts[i] + LEAD, 1.0)
    for i in range(1, len(durs)):
        put(D.swell(0.5), starts[i] - 0.28, 0.55)
    put(D.chime(), starts[-1] + 1.4, 0.6)
    bed = D.music(n / SR, variant=rng.randrange(len(D.PROGRESSIONS)))
    duck = np.ones(n, np.float32)
    for i, a in enumerate(A):
        s0 = int((starts[i] + LEAD - 0.1) * SR); duck[max(0, s0):s0 + len(a) + int(0.2 * SR)] = 0.42
    duck = np.convolve(duck, np.ones(int(0.12 * SR)) / int(0.12 * SR), "same").astype(np.float32)
    mix += bed[:n] * duck * 1.15
    mix /= max(1.0, float(np.abs(mix).max()) / 0.92)
    wav = out.replace(".mp4", "_b.wav"); sf.write(wav, mix[:int(total * SR)], SR)
    # ---- video
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + HY.enc_args(out), stdin=subprocess.PIPE)
    moves = [rng.choice(["push", "left", "right", "rise"]) for _ in scenes]
    trans = [rng.choice(["fade", "cut", "fade"]) for _ in durs]
    clips = [Clip(p) for p in paths]
    illus = pillar in ("success", "proof")
    TR, prev_last = 0.28, None
    for fi in range(int(total * FPS)):
        tg = fi / FPS
        i = int(np.searchsorted(starts, tg, side="right") - 1)
        lt = tg - starts[i]
        if i < len(scenes):
            s = dict(scenes[i]); s["_first"] = (i == 0)
            base = camera(clips[i].frame(), lt, durs[i], moves[i])
            fr = scene_frame(base, s, lt + (1.5 if i == 0 else 0), durs[i] + (1.5 if i == 0 else 0), info)
            D.brand_bar(fr, tg, total, True)
            D.captions(fr, [(ts, w) for ts, w in words if starts[i] - 0.01 <= ts < starts[i] + durs[i]], tg)
            if illus:
                tag = D.cached("illus", lambda: D._txt("Illustrative footage", D.font(D.F_UI2, 22), (225, 222, 228)))
                fr.alpha_composite(tag, (W - D.MX - tag.width, H - 290))
        else:
            fr = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            D.end_card(fr, lt, durs[i], kind)
            D.brand_bar(fr, tg, total, True)
        if i > 0 and lt < TR and prev_last is not None and trans[i] == "fade":
            fr = Image.blend(prev_last, fr, D.ease_in_out(lt / TR))
        if int(np.searchsorted(starts, (fi + 1) / FPS, side="right") - 1) != i:
            prev_last = fr.copy()
        proc.stdin.write(fr.convert("RGB").tobytes())
    for c in clips:
        c.close()
    proc.stdin.close(); proc.wait(); os.remove(wav)
    # ---- caption + metadata
    cap = (f"{sc.get('caption_hook') or scenes[0]['headline']}\n{sc.get('caption_body', '')}\n\n{CT['caption']}\n"
           f"{brand.PARENT_LINE}\n" + ("Images: illustrative stock footage.\n" if illus else "") + "\n"
           + " ".join(brand.hashtags(rng)))
    open(out.replace(".mp4", ".txt"), "w").write(cap)
    meta = dict(mode="broll", format="broll", pillar=pillar, shape=sc.get("shape"), story=sc.get("title"),
                hook=sc.get("caption_hook"), headline=scenes[0]["headline"], blocks=[f"{s['layout']}/{s['overlay']}" for s in scenes],
                footage=[(s.get("_clip") or {}).get("uid") for s in scenes], duration=round(total, 1), cta=kind,
                arms=arms, review_score=None, agent=agent if not (evergreen or mock) else None, grade=grade)
    if report:
        arts = report.get("art") or []
        meta["director"] = {"hook_options": [h.get("headline") for h in (report.get("copy") or {}).get("hooks", [])],
                            "art_scores": [r["score"] for r in arts], "art_summary": arts[-1]["summary"] if arts else None}
        meta["brand_check"] = report.get("brand")
    if not mock and os.environ.get("REVIEWER", "on") != "off" and os.environ.get("GEMINI_API_KEY"):
        try:
            import reviewer
            new_cap, rep = reviewer.review_video(out, {"title": sc.get("title")}, cap, kind="broll")
            if new_cap:
                open(out.replace(".mp4", ".txt"), "w").write(new_cap)
            meta["review_score"] = rep.get("overall")
        except reviewer.RejectReel:
            raise
        except Exception as e:
            print("broll review skipped:", e)
    log = E._recent(200) + [{"pillar": pillar, "format": "broll", "shape": sc.get("shape"), "title": sc.get("title"),
                             "headline": scenes[0]["headline"], "hook": sc.get("caption_hook"), "date": time.strftime("%Y-%m-%d"), "agent": agent, **extra}]
    if extra.get("remix_of"):
        try:
            import content_bank; content_bank.mark_remixed(extra["remix_of"])
        except Exception as e:
            print("mark_remixed:", e)
    meta.update(extra)
    json.dump(log[-200:], open(LOG, "w"), indent=0)
    return meta
