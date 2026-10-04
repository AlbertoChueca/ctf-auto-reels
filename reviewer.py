"""Second agent: an AI producer that reviews and improves every reel before it is published.

Three checkpoints (all Gemini, a few cents per month in total):
  1. improve_script(): rewrites the script for a stronger hook for parents, a more useful insight, a clearer link to
     the puzzle and strict honesty (no invented results), using what performed best so far (performance.json).
  2. check_images(): looks at the 4 generated scenes (next to the mascot reference in mascot mode) and flags any that
     contain text/letters, broken anatomy, wrong chess boards, identifiable faces or anything unsafe -> redrawn once.
  3. review_video(): watches the finished reel (a small 480p copy), scores it, rewrites the first caption line
     and the comment prompt, and rejects the reel only if it is clearly broken (the pipeline then re-renders).
Every decision is logged to review_log.jsonl so you can read what the reviewer did.
Any reviewer error is ignored: the reel always continues with the original version.
"""
import base64, datetime, io, json, os, re, subprocess
import brand

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW_LOG = os.path.join(HERE, "review_log.jsonl")
PERF = os.path.join(HERE, "performance.json")
MIN_SCORE = float(os.environ.get("REVIEW_MIN_SCORE", "4"))   # below this the reel is re-rendered

PRODUCER = f"""You are a senior producer of short-form video ads and organic reels for {brand.NAME}, a premium online
chess academy (Instagram Reels, Facebook, TikTok, YouTube Shorts).
{brand.AUDIENCE}
{brand.ACADEMY}
{brand.HONESTY}
Your goals, in order: honest and safe; instantly clear; a scroll-stopping first 1.5 seconds for a busy parent; an
insight that makes the parent think "these people really know how kids improve"; a natural bridge to the puzzle for
their child; parents comment, share with other chess parents, visit our profile and follow."""


class RejectReel(RuntimeError):
    """The finished reel is clearly broken; the caller should render it again."""


def _log(kind, data):
    try:
        with open(REVIEW_LOG, "a") as f:
            f.write(json.dumps({"date": str(datetime.date.today()), "kind": kind, **data}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _ask(parts, temperature=0.6):
    """Gemini call returning parsed JSON."""
    import make_story as MS
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": temperature}}
    names = MS.TEXT_MODELS + [m for m in MS._available() if "flash" in m and not any(
        x in m for x in ("image", "tts", "live", "audio", "lite"))]
    last = None
    for model in dict.fromkeys(names):
        try:
            j = MS._post(model, body)
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.sub(r"^```(json)?|```$", "", txt.strip()))
        except Exception as e:
            last = e
            if " 404" not in str(e) and " 400" not in str(e):
                break
    raise last


def _jpeg_b64(im, size=512):
    im = im.copy(); im.thumbnail((size, size))
    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=80)
    return base64.b64encode(b.getvalue()).decode()


# ------------------------------------------------------------------ learnings from real performance
def learnings():
    """Short text with what worked / didn't on Instagram (empty until insights are available)."""
    try:
        perf = json.load(open(PERF))
    except Exception:
        perf = {}
    import strategy
    pb = strategy.playbook_text()
    rows = [r for r in perf.values() if r.get("views")]
    if len(rows) < 4:
        return pb
    rows.sort(key=lambda r: r["views"], reverse=True)
    avg = sum(r["views"] for r in rows) / len(rows)

    def line(r):
        eng = sum(r.get(k) or 0 for k in ("likes", "comments", "shares", "saved"))
        return (f'- "{r.get("story") or r.get("hook")}" ({r.get("level")}, {r.get("mode")}): {r["views"]} views, '
                f'{eng} interactions, avg watch {r.get("ig_reels_avg_watch_time", "?")} ms')
    top, low = rows[:3], rows[-3:]
    return (f"REAL INSTAGRAM RESULTS so far ({len(rows)} reels, average {avg:.0f} views):\nBest:\n"
            + "\n".join(map(line, top)) + "\nWorst:\n" + "\n".join(map(line, low))
            + "\nLean into what the best ones have in common; avoid what the worst ones did."
            + (("\n\n" + pb) if pb else ""))


# ------------------------------------------------------------------ 1. script
def _brief(arms):
    if not arms:
        return ""
    import strategy
    return (f"This reel is an A/B experiment: keep its opening hook style ({arms.get('hook_style')}) and theme "
            f"({arms.get('theme')}) and narration length {strategy.WORDS.get(arms.get('story_length'), '30-40')} words; "
            f"improve everything else.")


def improve_script(story, level, side, goal, episode, arms=None):
    """Returns an improved story (same schema). Falls back to the original on any problem."""
    try:
        res = _ask([{"text": f"""{PRODUCER}

{learnings()}

{_brief(arms)}
{brand.cases_text()}
{brand.narrator_text()}
Here is the draft script for reel {episode}. Puzzle that follows: {level} level, {side} to move, goal: {goal}.
DRAFT:
{json.dumps(story, ensure_ascii=False, indent=1)}

1) Score the draft 1-10 for: hook for a busy parent (first scene in 1.5 s), credibility/expertise, usefulness of the
   insight, link to the puzzle, the final invitation to test their child, voice-friendliness (short spoken sentences,
   numbers as words, no chess notation), honesty (no invented students/results, no guarantees).
2) Rewrite it to fix every weakness. Keep EXACTLY the same JSON schema and rules: 4 scenes, total narration 22-40
   words, max 11 words per sentence, last scene invites the parent to test their child with the puzzle, image prompts
   describe one vertical frame (no identifiable faces, no text/letters/logos in images), camera in
   [push_in, pull_out, pan_left, pan_right, tilt_up], sfx in [whoosh, boom, none], delivery = short acting direction.
   caption_hook: max 12 words, one emoji allowed, written for parents, invites a comment.
   Remove anything that breaks the honesty rules.
Return JSON: {{"scores": {{...}}, "overall": number, "changes": [str], "story": <the full improved story object>}}"""}])
        new = res.get("story") or {}
        sc = new.get("scenes") or []
        words = sum(len(s.get("narration", "").split()) for s in sc)
        ok = (len(sc) == 4 and all(s.get("narration") and s.get("image_prompt") for s in sc) and 18 <= words <= 48
              and not re.search(r"\b[a-h][1-8]\b|[KQRBN]x?[a-h][1-8]", " ".join(s["narration"] for s in sc)))
        _log("script", {"episode": episode, "overall": res.get("overall"), "scores": res.get("scores"),
                        "changes": res.get("changes"), "accepted": ok, "before": story.get("title"),
                        "after": new.get("title")})
        if not ok:
            print("reviewer: script rewrite rejected (format), keeping draft", flush=True)
            return story
        for k in ("title", "summary"):
            new.setdefault(k, story.get(k))
        print(f"reviewer: script {res.get('overall')}/10 -> improved ({'; '.join((res.get('changes') or [])[:3])})", flush=True)
        return new
    except Exception as e:
        print("reviewer: script review skipped:", str(e)[:200], flush=True)
        return story


# ------------------------------------------------------------------ 2. images
def check_images(imgs, scenes, mascot_ref=None):
    """Returns {scene_index: better_image_prompt} for scenes that should be redrawn."""
    try:
        from PIL import Image
        common = ("NO text, letters, numbers or logos anywhere; no broken anatomy (hands, faces) or melted shapes; chess "
                  "boards look like real 8x8 boards with real pieces; no close-up, identifiable child faces; looks premium "
                  "and trustworthy (fits an academy for ambitious parents); matches its prompt; readable on a phone; safe.")
        if mascot_ref:
            ref = Image.open(mascot_ref).convert("RGBA")
            bg = Image.new("RGB", ref.size, (255, 255, 255)); bg.paste(ref, (0, 0), ref)
            intro = (f"First image: the official academy mascot (reference). Then {len(imgs)} generated scenes, in order.\n"
                     f"For each scene check: the mascot is on-model when present; {common}")
            parts = [{"text": ""}, {"inline_data": {"mime_type": "image/jpeg", "data": _jpeg_b64(bg, 384)}}]
        else:
            intro = f"Below are {len(imgs)} generated illustrated scenes, in order. For each scene check: {common}"
            parts = [{"text": ""}]
        parts[0]["text"] = f"""{PRODUCER}
{intro}
Prompts: {json.dumps([s.get('image_prompt') for s in scenes], ensure_ascii=False)}
Return JSON: {{"scenes": [{{"index": 0, "ok": true, "problems": [str], "better_prompt": str}}]}}
Only mark ok=false for clear problems a viewer would notice."""
        for im in imgs:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _jpeg_b64(im)}})
        res = _ask(parts, 0.2)
        redo = {}
        for s in res.get("scenes", []):
            i = int(s.get("index", -1))
            if 0 <= i < len(imgs) and s.get("ok") is False:
                redo[i] = s.get("better_prompt") or scenes[i]["image_prompt"]
        _log("images", {"redo": {str(k): v for k, v in redo.items()},
                        "problems": {str(s.get("index")): s.get("problems") for s in res.get("scenes", []) if not s.get("ok", True)}})
        if redo:
            print(f"reviewer: redrawing scenes {[i + 1 for i in redo]}", flush=True)
        return redo
    except Exception as e:
        print("reviewer: image check skipped:", str(e)[:200], flush=True)
        return {}


# ------------------------------------------------------------------ 3. finished video
def review_video(path, story, caption, kind="puzzle"):
    """Watches the reel. Returns (new_caption, report). Raises RejectReel if the reel is clearly broken."""
    small = path.replace(".mp4", "_review.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "scale=360:640", "-r", "12",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "48k", small],
                       check=True)
        data = base64.b64encode(open(small, "rb").read()).decode()
        first, rest = (caption.split("\n", 1) + [""])[:2]
        res = _ask([{"text": f"""{PRODUCER}
Watch this finished reel ({'motion-graphics explainer for parents + call to action' if kind == 'explainer' else 'expert insight for parents + chess puzzle for their child + call to action'}).
Title: {story.get('title')}. Current Instagram caption first line: {first!r}

Check and score 1-10: hook for a parent in the first 1.5 s, clarity and credibility, pacing, subtitles readable and in
sync with the voice, voice natural and matching the words, {'animation and text easy to follow' if kind == 'explainer' else 'the chess board and moves easy to follow'}, visuals premium
and consistent, call to action clear, honesty (no invented results or guarantees), likelihood parents comment, share,
visit the profile and follow.
"critical" = true ONLY if the reel is clearly broken (silent, frozen/black, unreadable, wrong/garbled voice,
inappropriate or dishonest content). Then write a better FIRST caption line (max 12 words, one emoji max, written for
parents, makes them stop and comment) and a short comment prompt line (max 12 words, {'invites parents to comment' if kind == 'explainer' else 'invites the child’s answer'}).
Return JSON: {{"overall": number, "scores": {{...}}, "critical": bool, "issues": [str], "suggestions": [str],
"caption_first_line": str, "comment_prompt": str}}"""},
                    {"inline_data": {"mime_type": "video/mp4", "data": data}}], 0.4)
    except RejectReel:
        raise
    except Exception as e:
        print("reviewer: video review skipped:", str(e)[:200], flush=True)
        return caption, {}
    finally:
        if os.path.exists(small): os.remove(small)
    overall = float(res.get("overall") or 0)
    _log("video", {"story": story.get("title"), "overall": overall, "scores": res.get("scores"),
                   "critical": res.get("critical"), "issues": res.get("issues"), "suggestions": res.get("suggestions")})
    print(f"reviewer: reel scored {overall}/10" + (f" - issues: {'; '.join(res.get('issues', [])[:3])}" if res.get("issues") else ""), flush=True)
    if res.get("critical") and overall < MIN_SCORE:
        raise RejectReel(f"reviewer rejected the reel ({overall}/10): {'; '.join(res.get('issues', [])[:3])}")
    new_first = (res.get("caption_first_line") or "").strip()
    prompt = (res.get("comment_prompt") or "").strip()
    cap = caption
    if 3 <= len(new_first.split()) <= 14 and "#" not in new_first:
        cap = new_first + "\n" + rest
    if prompt and 3 <= len(prompt.split()) <= 14 and "#" not in prompt:
        cap = re.sub(r"Can your child find it\? Comment the move before the solution!|Comment your child's move and tag a chess parent!",
                     prompt, cap, count=1)
    return cap, {"overall": overall, "issues": res.get("issues"), "suggestions": res.get("suggestions")}
