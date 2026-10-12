"""Story reel for ChessTalentsFactory: a unique ~12s illustrated opening for PARENTS (expert insight + challenge for
their child; script + scenes generated with Google Gemini), followed by the puzzle segment from make_hype.

python make_story.py puzzle.json seed out.mp4          (needs GEMINI_API_KEY)
STORY_MOCK=1 python make_story.py ...                   (offline test with placeholder scenes)
"""
import base64, io, json, math, os, random, re, subprocess, sys, time
import numpy as np
import requests
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import make_reel as R
import make_hype as HY
import brand

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 25, 24000
API = "https://generativelanguage.googleapis.com/v1beta/models"
TEXT_MODELS = [m for m in os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash").split(",") if m]
IMAGE_MODELS = [m for m in os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image,gemini-2.5-flash-image").split(",") if m]


def _available():
    """Model names this API key can call with generateContent (used as a fallback when names change)."""
    try:
        r = requests.get(f"{API}?pageSize=200", headers={"x-goog-api-key": _key()}, timeout=60)
        return [m["name"].split("/")[-1] for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:
        return []
STORY_LOG = os.path.join(HERE, "story_log.json")
MASCOT_DIR = os.path.join(HERE, "assets", "mascot")
MASCOT_MODE = brand.FORMAT == "mascot"
REFS = sorted(p for p in os.listdir(MASCOT_DIR) if p.lower().endswith(".png"))[:4] if MASCOT_MODE and os.path.isdir(MASCOT_DIR) else []

STYLE = ("Premium flat 2D editorial illustration with soft cinematic lighting and warm black-and-orange accents, clean "
         "shapes, rich but calm colours, like a high-end explainer video for parents. People are stylised illustrated "
         "characters (not photorealistic), generic, not resembling any real person. Chess boards are drawn correctly "
         "(8x8, light square at each player's bottom right) with recognisable pieces.")

if MASCOT_MODE:
    _ct = os.path.join(MASCOT_DIR, "character.txt")
    CHARACTER = (open(_ct).read().strip() if os.path.exists(_ct) else
                 "THE MASCOT: the academy mascot exactly as in the reference images.") + "\n" + STYLE
    CHAR_RULE = ('Always say "the mascot from the reference images" for the mascot; other characters are generic '
                 "illustrated people in the same style.")
else:
    CHARACTER = STYLE
    CHAR_RULE = ("Children appear as generic illustrated kids (7-14), seen from the side, from behind or at mid distance, "
                 "never a close-up of a face, never identifiable. Parents and coaches are generic illustrated adults.")

STORY_PROMPT = """You write the 10-15 second opening of vertical chess reels for {name}, a premium online chess academy.
{audience}
{academy}
{narrator}
{honesty}
{cases}

This is reel number {episode}. Recent reels (do not repeat their ideas):
{recent}

{playbook}

Write ONE new script: hook -> an insight the parent did not know -> what actually works -> a challenge for their child.
TODAY'S CREATIVE BRIEF (an A/B experiment, follow it): hook style = {hook_style}; theme = {theme}.
The challenge at the end IS the chess puzzle that follows: {level} level, {side} to move, goal: {goal}.
Rules:
- Exactly 4 scenes. Total narration {words} words. Spoken English, expert-to-parent: specific, credible, zero hype,
  no cliches ("unlock their potential", "game changer"), never condescending.
- Scene 1 must stop a parent's scroll in 1.5 seconds: a sharp claim, a question or a surprising fact about how kids
  actually improve at chess.
- Scenes 2-3: one concrete, useful insight they can act on today and why it matters for the child's rating.
- Scene 4: invite the parent to test their child with the puzzle that follows, e.g. "Show this to your child. Can they
  find the winning move?" (vary the wording every reel).
- Write numbers as words. Short sentences (max 11 words), contractions, commas for breaths. No hashtags, emojis,
  abbreviations or chess notation in narration. No prices, no guarantees, no competitors.
- Do NOT reuse any of these previous ideas: {avoid}
- image_prompt: describe ONE vertical 9:16 frame: action, setting (home study desk, tournament hall, online lesson on a
  laptop, car ride to a tournament, kitchen table with a board, a coach analysing a game...), camera framing, lighting,
  mood. {char_rule} No text, letters, numbers, logos or readable screens in the image.
- camera: one of push_in, pull_out, pan_left, pan_right, tilt_up.
- sfx: one of whoosh, boom, none (use boom at most once).
- delivery: 3-8 word acting direction for the voice actor, calm-confident register, varied across scenes (e.g.
  "direct, slightly surprised", "warm and reassuring", "serious, then a small smile", "curious, leaning in").
- summary: one sentence describing the idea of this reel (for continuity).
- caption_hook: Instagram first line for parents (max 12 words, one emoji allowed) that makes them stop and comment.
Return JSON: {{"title": str, "summary": str, "scenes": [{{"narration": str, "image_prompt": str, "camera": str, "sfx": str, "delivery": str}}], "caption_hook": str}}"""


# ----------------------------------------------------------------- Gemini
def _key():
    return os.environ["GEMINI_API_KEY"]


DEAD = set()          # models that do not exist / are retired / have no daily quota left: skipped for the whole run
_AVAIL = None


class QuotaError(RuntimeError):
    pass


def _retry_delay(r):
    """Seconds Google asks us to wait (RetryInfo), and whether the exhausted quota is a DAILY one."""
    try:
        err = r.json().get("error", {})
        delay, daily = None, False
        for d in err.get("details", []):
            if d.get("retryDelay"):
                delay = float(str(d["retryDelay"]).rstrip("s") or 0)
            for v in d.get("violations", []) or []:
                if "PerDay" in (v.get("quotaId") or "") or "per_day" in (v.get("quotaMetric") or "").lower():
                    daily = True
        return delay, daily
    except Exception:
        return None, False


def _post(model, body, tries=3):
    """One model. Honours Google's retry delay; gives up fast on daily quota, retired models and long outages."""
    if model in DEAD:
        raise QuotaError(f"Gemini {model}: skipped (unavailable earlier in this run)")
    last = ""
    for k in range(tries):
        try:
            r = requests.post(f"{API}/{model}:generateContent", json=body, timeout=150,
                              headers={"x-goog-api-key": _key(), "Content-Type": "application/json"})
        except requests.RequestException as e:
            last = f"network: {str(e)[:120]}"; time.sleep(5 * (k + 1)); continue
        if r.status_code == 200:
            return r.json()
        last = f"{r.status_code}: {r.text[:300]}"
        if r.status_code == 429:
            delay, daily = _retry_delay(r)
            if daily or (delay and delay > 70):
                DEAD.add(model)
                raise QuotaError(f"Gemini {model} 429 quota exhausted ({'daily' if daily else f'retry in {delay:.0f}s'})")
            time.sleep(min(delay or 20, 60) + 1); continue
        if r.status_code >= 500:
            time.sleep(8 * (k + 1)); continue
        if r.status_code in (400, 403, 404):
            DEAD.add(model)
        raise RuntimeError(f"Gemini {model} {last}")
    raise RuntimeError(f"Gemini {model}: still failing after {tries} tries ({last[:160]})")


def text_models(limit=None):
    """Preferred text models first, then any other available flash model; dead ones removed. Cached per run."""
    global _AVAIL
    if _AVAIL is None:
        _AVAIL = _available()
    extra = [m for m in _AVAIL if "flash" in m and not any(x in m for x in ("image", "tts", "live", "audio", "lite", "omni"))]
    extra.sort(key=lambda m: [-int(x) if x.isdigit() else 0 for x in re.findall(r"\d+", m)])  # newest first
    names = [m for m in dict.fromkeys(TEXT_MODELS + extra) if m not in DEAD and (not _AVAIL or m in _AVAIL or m in TEXT_MODELS)]
    return names[:limit] if limit else names


def write_story(level, side, goal, avoid, episode=1, recent=(), arms=None):
    import strategy
    arms = arms or {}
    pb = strategy.playbook_text()
    body = {"contents": [{"parts": [{"text": STORY_PROMPT.format(
                name=brand.NAME, audience=brand.AUDIENCE, academy=brand.ACADEMY, narrator=brand.narrator_text(),
                honesty=brand.HONESTY, cases=brand.cases_text(), char_rule=CHAR_RULE,
                level=level, side=side, goal=goal, episode=episode,
                playbook=("WHAT WORKS FOR OUR AUDIENCE (from real results):\n" + pb) if pb else "",
                hook_style=arms.get("hook_style", "your best idea"), theme=arms.get("theme", "your best idea"),
                words=strategy.WORDS.get(arms.get("story_length"), "30-40"),
                recent="\n".join(f"- {r}" for r in recent) or "- (this is the first reel)",
                avoid="; ".join(avoid[-40:]) or "none")}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 1.1}}
    names = TEXT_MODELS + [m for m in _available() if "flash" in m and not any(x in m for x in ("image", "tts", "live", "audio", "lite"))]
    j, last = None, None
    for model in dict.fromkeys(names):
        try:
            j = _post(model, body); print("text model:", model, flush=True); break
        except RuntimeError as e:
            last = e
            if " 404" not in str(e) and " 400" not in str(e): raise
    if j is None: raise last
    txt = j["candidates"][0]["content"]["parts"][0]["text"]
    story = json.loads(txt)
    assert len(story["scenes"]) >= 3
    return story


def gen_image(prompt, refs):
    if refs:
        txt = (f"{CHARACTER}\n\nCreate this scene with exactly the same mascot as the reference images (same shapes, "
               f"colours and outline style). Vertical 9:16 composition, no text.\n\nScene: {prompt}")
    else:
        txt = f"{CHARACTER}\n\nCreate this scene. Vertical 9:16 composition, no text, letters or logos.\n\nScene: {prompt}"
    parts = [{"text": txt}]
    for p in refs:
        parts.append({"inline_data": {"mime_type": "image/png",
                                      "data": base64.b64encode(open(os.path.join(MASCOT_DIR, p), "rb").read()).decode()}})
    last = None
    for model in dict.fromkeys(IMAGE_MODELS + [m for m in _available() if "image" in m]):
        try:
            j = _post(model, {"contents": [{"parts": parts}],
                              "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}})
            for part in j["candidates"][0]["content"]["parts"]:
                d = part.get("inlineData") or part.get("inline_data")
                if d:
                    print("image model:", model, flush=True)
                    return Image.open(io.BytesIO(base64.b64decode(d["data"]))).convert("RGB")
            last = RuntimeError(f"{model}: no image in response")
            continue
        except Exception as e:
            last = e
    raise last


def mock_story(rng):
    return {"title": "Mock reel", "summary": "Mock", "caption_hook": "Most kids lose rating points for this reason 👇",
            "scenes": [{"narration": t, "image_prompt": str(i), "camera": c, "sfx": x, "delivery": dl}
                       for i, (t, c, x, dl) in enumerate([
                           ("Most kids don't lose games to bad openings.", "push_in", "none", "direct, slightly surprised"),
                           ("They lose because they move too fast.", "pan_left", "whoosh", "serious, then a small smile"),
                           ("Strong kids check every check and capture first.", "pull_out", "none", "warm and reassuring"),
                           ("Show this to your child. Can they find it?", "push_in", "boom", "curious, leaning in")])]}


def mock_image(prompt, i):
    bgc = [(30, 24, 22), (70, 36, 14), (20, 30, 40), (90, 50, 10)][i % 4]
    im = Image.new("RGB", (900, 1600), bgc); d = ImageDraw.Draw(im)
    for k in range(12):
        d.ellipse([k * 90 - 100, 1100 + 30 * math.sin(k), k * 90 + 200, 1700], fill=tuple(min(255, c + 25) for c in bgc))
    import chess
    for r in range(8):
        for f in range(8):
            d.rectangle([90 + f * 90, 420 + r * 90, 180 + f * 90, 510 + r * 90],
                        fill=(240, 217, 181) if (r + f) % 2 == 0 else (181, 136, 99))
    pc = R.piece_img(chess.Piece(chess.KNIGHT, chess.WHITE), 300)
    im.paste(pc, (300, 560), pc)
    return im


# ----------------------------------------------------------------- animation
def cover(im, scale):
    w, h = int(W * scale), int(H * scale)
    r = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def grade(im):
    im = ImageEnhance.Contrast(im).enhance(1.08); im = ImageEnhance.Color(im).enhance(1.12)
    v = Image.new("L", (W, H), 0); ImageDraw.Draw(v).ellipse([-W * 0.35, -H * 0.2, W * 1.35, H * 1.2], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGB", (W, H), (8, 6, 14))
    return Image.composite(im, dark, v.point(lambda p: 90 + p * 165 // 255))


def frame_for(big, cam, p, t):
    """big: pre-scaled (1.18x) image; p: 0..1 progress within the scene."""
    e = HY.eio(p)
    bw, bh = big.size
    z = {"push_in": 1.0 + 0.16 * e, "pull_out": 1.16 - 0.16 * e}.get(cam, 1.08)
    vw, vh = bw / 1.18 / z * 1.0, bh / 1.18 / z
    cx, cy = bw / 2, bh / 2
    if cam == "pan_left": cx = bw / 2 + (bw - vw) * 0.45 * (0.5 - e)
    if cam == "pan_right": cx = bw / 2 - (bw - vw) * 0.45 * (0.5 - e)
    if cam == "tilt_up": cy = bh / 2 + (bh - vh) * 0.45 * (0.5 - e)
    if cam == "shake":
        cx += 14 * math.sin(t * 53) * (1 - p); cy += 10 * math.cos(t * 47) * (1 - p)
    x0 = min(max(cx - vw / 2, 0), bw - vw); y0 = min(max(cy - vh / 2, 0), bh - vh)
    return big.crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh))).resize((W, H), Image.BILINEAR)


def build(P, seed, out, mode="level", arms=None):
    arms = arms or {}
    rng = random.Random(f"{P.get('id')}-{seed}-story")
    import chess
    LV = R.LEVELS[P["level"]]
    if "fen" in P:
        b = chess.Board(P["fen"]); b.push(chess.Move.from_uci(P["moves"].split()[0])); sol = P["moves"].split()[1:]
    else:
        b = chess.Board()
        for m in P["pgn"].split(): b.push_san(m)
        sol = P["sol"]
    side = "Black" if b.turn == chess.BLACK else "White"
    b2 = b.copy()
    for u in sol: b2.push(chess.Move.from_uci(u))
    mate_n = (len(sol) + 1) // 2 if b2.is_checkmate() else None
    goal = f"mate in {mate_n}" if mate_n else "win material"

    # preflight: fail fast (before paying for images) if a required file is missing
    need = [HY.F900]
    missing = [p for p in need if not os.path.exists(p)]
    if missing:
        raise SystemExit("Missing files in the repository: " + ", ".join(os.path.relpath(p, HERE) for p in missing))
    if MASCOT_MODE and not REFS:
        raise SystemExit("REEL_FORMAT=mascot but assets/mascot/ has no PNG reference images")
    mock = os.environ.get("STORY_MOCK") == "1"
    log = json.load(open(STORY_LOG)) if os.path.exists(STORY_LOG) else []
    episode = len(log) + 1
    recent = [f"{s.get('title')}: {s.get('summary', '')}" for s in log[-3:]]
    story = mock_story(rng) if mock else write_story(LV["name"].title(), side, goal, [s["title"] for s in log],
                                                     episode, recent, arms)
    review_on = not mock and os.environ.get("REVIEWER", "on") != "off"
    if review_on:                                   # 2nd agent: producer review of the script
        import reviewer
        story = reviewer.improve_script(story, LV["name"].title(), side, goal, episode, arms)
    scenes = story["scenes"][:4]
    print("Story:", story["title"], flush=True)
    def one_image(i):
        for attempt in range(2):
            try:
                return mock_image(scenes[i]["image_prompt"], i) if mock else gen_image(scenes[i]["image_prompt"], REFS)
            except Exception as e:
                print(f"scene {i + 1} image failed ({attempt + 1}/2): {str(e)[:200]}", flush=True)
        return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as ex:                     # the 4 scenes are drawn at the same time
        got = list(ex.map(one_image, range(len(scenes))))
    if review_on and any(g is not None for g in got):     # 2nd agent: redraw off-model / broken scenes once
        redo = reviewer.check_images([g if g is not None else next(x for x in got if x is not None) for g in got],
                                     scenes, os.path.join(MASCOT_DIR, REFS[0]) if REFS else None)
        if redo:
            def redraw(i):
                try:
                    return i, gen_image(redo[i], REFS)
                except Exception as e:
                    print(f"scene {i + 1} redraw failed: {str(e)[:150]}", flush=True); return i, None
            with ThreadPoolExecutor(4) as ex:
                for i, im in ex.map(redraw, list(redo)):
                    if im is not None: got[i] = im
    imgs = []
    for i, im in enumerate(got):
        if im is None:
            others = [g for g in got if g is not None]
            if not others: raise RuntimeError("could not generate any scene image")
            im = imgs[-1] if imgs else others[0]           # keep the reel alive: reuse a neighbouring scene
        imgs.append(im)
        print(f"scene {i + 1} image ready", flush=True)

    # voice: story narration + puzzle segment are recorded with the SAME engine/voice.
    # The puzzle segment is rendered first; if the voice fails half way, both parts are redone with the next engine.
    import voice
    voice.reset()
    puzzle_mp4 = out.replace(".mp4", "_puzzle.mp4")
    for attempt in range(3):
        try:
            A = voice.say_many([sc["narration"] for sc in scenes], speed=1.08,
                               styles=[sc.get("delivery") for sc in scenes], one_take=True)
            meta = HY.build(P, seed, puzzle_mp4, mode=mode, skip_hook=True, backdrop=imgs[-1], keep_voice=True,
                             cta_kind=arms.get("cta"),
                             think_factor=__import__("strategy").THINK_FACTOR.get(arms.get("think_time"), 1.0))
            break
        except voice.VoiceError as e:
            nxt = voice.next_engine()
            print(f"voice changed during the reel ({e}); redoing story + puzzle with: {nxt}", flush=True)
            voice.reset(nxt)
    else:
        raise RuntimeError("could not record a consistent voice")
    durs = [max(len(a) / SR + 0.35, 2.0) for a in A]
    starts = np.cumsum([0] + durs[:-1]); total = float(sum(durs)) + 0.3

    n = int(SR * (total + 0.5)); vo = np.zeros(n, np.float32); fx = np.zeros(n, np.float32)
    def put(buf, a, at, g=1.0):
        i = int(at * SR)
        if i < 0: a = a[-i:]; i = 0
        if i >= n: return
        j = min(n, i + len(a)); buf[i:j] += a[: j - i] * g
    for i, a in enumerate(A):
        put(vo, a, starts[i] + 0.12)
        s = scenes[i].get("sfx", "none")
        if i:                                   # soft, musical scene change
            put(fx, R.whoosh(0.6, seed=i), starts[i] - 0.35, 0.55)
            put(fx, R.shimmer([659.3, 784.0, 880.0, 587.3][i % 4]), starts[i] - 0.05, 0.8)
        if s == "boom": put(fx, R.soft_hit(), starts[i] + 0.02, 0.6)
    put(fx, HY.riser(1.6), total - 1.6, 0.9)
    tb = np.arange(n) / SR      # calm, warm pad under the voice (parents' register: no hype beat here)
    pad = sum(np.sin(2 * np.pi * f * tb) for f in (110, 164.8, 220)) * 0.045 * np.clip(tb / 1.5, 0, 1)
    mix = np.tanh((vo * 1.15 + fx + pad.astype(np.float32)) * 1.1) * 0.92
    wav = out.replace(".mp4", "_s.wav"); sf.write(wav, mix, SR)
    hop = SR // FPS

    words = []
    for i, sc in enumerate(scenes):            # timings from what the voice actually says
        for ts, w in voice.align(A[i], sc["narration"]):
            words.append((i, starts[i] + 0.12 + ts, w))

    bigs = [cover(grade(cover(im, 1.0)), 1.18) for im in imgs]
    LEAK = [None]
    story_mp4 = out.replace(".mp4", "_story.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + HY.enc_args(story_mp4),
                            stdin=subprocess.PIPE)
    for fi in range(int(total * FPS)):
        t = fi / FPS
        i = int(np.searchsorted(starts, t, side="right") - 1)
        p = (t - starts[i]) / durs[i]
        fr = frame_for(bigs[i], scenes[i].get("camera", "push_in"), min(p, 1), t).convert("RGBA")
        lt = t - starts[i]
        if i and lt < 0.35:   # warm light-leak flash between scenes
            k = 1 - lt / 0.35
            if LEAK[0] is None:                       # blurred once, then only its opacity changes
                leak = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(leak)
                ld.ellipse([-W * 0.4, -H * 0.2, W * 0.9, H * 0.6], fill=(255, 170, 70, 170))
                LEAK[0] = leak.filter(ImageFilter.GaussianBlur(120))
            lk = LEAK[0].copy(); lk.putalpha(LEAK[0].getchannel("A").point(lambda v, k=k: int(v * k)))
            fr.alpha_composite(lk)
            if lt < 0.08: fr = Image.blend(fr, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.5 * (1 - lt / 0.08))
        cur = [(ts, w) for si, ts, w in words if si == i and ts <= t]
        if cur:
            idx = len(cur) - 1; st = (idx // 3) * 3
            ph = HY.phrase_img([w for _, w in cur[st:idx + 1]], t - cur[-1][0], 86)
            R.paste_center(fr, HY.band_img(ph.height + 80), W / 2, 1520)
            R.paste_center(fr, ph, W / 2, 1520)
        if i == 0 and lt < 2.5:   # top label
            tag = R.pill(f"{brand.NAME.upper()} · TIP #{episode}", 34, brand.INK, fg=brand.ORANGE, padx=30, pady=12)
            R.paste_center(fr, tag, W / 2, 170, HY.eob(lt / 0.3))
        proc.stdin.write(HY.grain(fr, fi))
    proc.stdin.close(); proc.wait(); os.remove(wav)

    # join story + puzzle segment (rendered above; the story is the hook)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", story_mp4, "-i", puzzle_mp4, "-filter_complex",
                    "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]"]
                   + HY.enc_args(out, scale=False), check=True)
    cap_old = open(puzzle_mp4.replace(".mp4", ".txt")).read().split("\n", 1)[1]
    caption = f"{story.get('caption_hook', story['title'])}\n{cap_old}"
    review = {}
    if review_on:                                   # 2nd agent: watch the finished reel, polish the caption
        caption, review = reviewer.review_video(out, story, caption)   # raises RejectReel if clearly broken
    open(out.replace(".mp4", ".txt"), "w").write(caption)
    for f in (story_mp4, puzzle_mp4, puzzle_mp4.replace(".mp4", ".txt")):
        if os.path.exists(f): os.remove(f)
    if not mock:
        log.append({"title": story["title"], "summary": story.get("summary", ""), "puzzle": P.get("id")})
        json.dump(log[-200:], open(STORY_LOG, "w"), indent=0)
        for k, im in enumerate(imgs):
            im.save(out.replace(".mp4", f"_scene{k + 1}.jpg"), quality=88)
    meta.update(story=story["title"], hook=story.get("caption_hook", story["title"]), arms=arms,
                review_score=review.get("overall"))
    return meta


if __name__ == "__main__":
    P = json.load(open(sys.argv[1]))
    print(json.dumps(build(P, int(sys.argv[2]), sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "level"), indent=1))
