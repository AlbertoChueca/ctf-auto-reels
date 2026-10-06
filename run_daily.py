"""One publishing slot.

python run_daily.py <story|storytag|basic|intermediate|advanced|tagfriend> [--dry-run]

ChessTalentsFactory (academy) version.
story / storytag (default daily slots): unique AI opening for parents + puzzle for their child (make_story).
storytag = "send this to another chess parent" challenge.
If anything in the story pipeline fails (Gemini down, quota, network...), the slot automatically falls back to the
puzzle-only reel (make_hype), so a post always goes out. Every post: random US location, 3-5 chess hashtags,
Story share and YouTube Shorts/TikTok cross-post when configured.
"""
import datetime, json, os, random, sys, traceback
from pick_puzzles import pick, mark_used
import brand

slot = sys.argv[1]
dry = "--dry-run" in sys.argv or os.environ.get("DRY_RUN") == "true"
now = datetime.datetime.utcnow()
today = now.date()
seed = today.toordinal() * 24 + now.hour
os.makedirs("out", exist_ok=True)

locs = [l for l in json.load(open("locations.json")) if l.get("id")] if os.path.exists("locations.json") else []
loc = random.Random(f"{now:%Y-%m-%d-%H}-{slot}-loc").choice(locs) if locs else None


def log(entry):
    with open("log.jsonl", "a") as f:
        f.write(json.dumps({"date": str(today), "slot": slot, **entry}) + "\n")


# ---- choose level / mode
LEVELS = ["basic", "intermediate", "advanced"]
if slot == "story":
    level, mode = LEVELS[today.toordinal() % 3], "level"          # rotates every day
elif slot == "storytag":
    level, mode = random.Random(f"{today}-tag").choice(["basic", "intermediate"]), "tagfriend"
elif slot == "tagfriend":
    level, mode = random.Random(f"{now:%Y-%m-%d-%H}-tag").choice(["basic", "basic", "intermediate"]), "tagfriend"
else:
    level, mode = slot, "level"

if os.environ.get("LEVEL_OVERRIDE", "auto") in LEVELS:      # manual run with a chosen difficulty
    level = os.environ["LEVEL_OVERRIDE"]

# ---- weekly calendar (US date): the midday slot is the conversion reel, the evening slot is the puzzle challenge
import guard
# Mon..Sun. Midday = conversion reel, evening = more variety (puzzles + other formats). 14 different reels a week.
MIDDAY = {0: "pain", 1: "success", 2: "faq", 3: "remix", 4: "method", 5: "success", 6: "remix"}
EVENING = {0: "puzzle", 1: "remix", 2: "puzzle", 3: "faq", 4: "puzzle", 5: "pain", 6: "puzzle"}
us_today = (now - datetime.timedelta(hours=5)).date()
wd = us_today.weekday()
pillar = os.environ.get("PILLAR_OVERRIDE", "auto")
if pillar not in ("pain", "faq", "method", "proof", "success", "remix", "puzzle", "story"):
    pillar = MIDDAY[wd] if slot == "story" else EVENING[wd]
if pillar == "story":
    pillar = "puzzle"
if pillar == "puzzle" and slot == "storytag":
    mode = "tagfriend" if wd == 6 else "level"
if pillar == "proof" and not (guard.has("avg_gain") or guard.has("fide_titles")):
    pillar = "method"
if pillar == "success" and not guard.cases():
    pillar = "pain"
IMAGE_GEN = os.environ.get("IMAGE_GEN", "off") == "on"   # off = free mode: no AI image generation
why = guard.paused()
if why and not dry and os.environ.get("FORCE_PUBLISH") != "true":
    print(f"PAUSED: {why}. Delete paused.json (or run with force) to resume.")
    raise SystemExit(f"Publishing paused: {why}")
insights_msg = ""
try:                       # real Instagram results -> performance.json (the reviewer learns from them)
    import insights
    insights_msg = insights.update(); print(insights_msg, flush=True)
except Exception as e:
    insights_msg = f"insights skipped: {str(e)[:150]}"; print(insights_msg, flush=True)

# ---- autopilot experiment: choose today's creative options (learns from past results)
arms, strat_msg = {}, ""
try:
    import strategy
    fixed = {}
    if os.environ.get("LEVEL_OVERRIDE", "auto") in LEVELS or slot not in ("story",):
        fixed["difficulty"] = level                       # manual choice / tag-a-friend keep their level
    if brand.CTA_MODE in brand.CTA:
        fixed["cta"] = brand.CTA_MODE                     # CTA chosen by the owner (variable CTA_MODE), not tested
    arms = strategy.choose(seed=f"{now:%Y-%m-%d-%H}-{slot}", fixed=fixed)
    level = arms.get("difficulty", level)
    if slot == "story":
        strat_msg = strategy.weekly_strategist()
    strategy.write_report()
    print("experiment:", {k: strategy.short(v) for k, v in arms.items()}, "|", strat_msg, flush=True)
except Exception as e:
    strat_msg = f"strategy skipped: {str(e)[:150]}"; print(strat_msg, flush=True)

P = pick(level, seed=f"{today}-{slot}-{now.hour}")
out = f"out/{today}_{slot}_{now.hour:02d}.mp4"

# ---- render with fallbacks
meta, engine = None, None
# Every slot gets the premium story reel (same as "Story reel test"). If the story pipeline has a transient
# problem it is retried once; only then does it fall back so a post always goes out.
if pillar != "puzzle":
    chain = ["explainer", "explainer", "hype"]
else:
    chain = ["story", "story", "hype", "hype"] if IMAGE_GEN else ["hype", "hype"]
errors = []
for eng in chain:
    try:
        if eng == "explainer":
            if not os.environ.get("GEMINI_API_KEY") and os.environ.get("STORY_MOCK") != "1":
                raise RuntimeError("GEMINI_API_KEY not set")
            from make_explainer import build as b
            meta = b(seed, out, pillar=pillar, arms=arms)
        elif eng == "story":
            if not os.environ.get("GEMINI_API_KEY"):
                raise RuntimeError("GEMINI_API_KEY not set")
            from make_story import build as b
            meta = b(P, seed, out, mode=mode, arms=arms)
        else:
            from make_hype import build as b
            meta = b(P, seed, out, mode=mode, cta_kind=arms.get("cta"))
        meta["qc"] = guard.qc(out)                  # hard checks: streams, duration, real audio
        engine = eng
        break
    except Exception as e:
        errors.append(f"{eng}: {str(e)[:300]}")
        print(f"[{eng}] failed, trying next engine:\n{traceback.format_exc()[-1500:]}", flush=True)
if meta is None:
    n_fail = guard.record_run(False, "; ".join(errors))
    if n_fail >= 2:
        guard.pause(f"{n_fail} runs in a row failed: {errors[-1][:200]}")
    raise SystemExit("All render engines failed")
guard.record_run(True)
print("engine:", engine, flush=True)
try:
    import voice as _v
    voice_used = _v.ENGINE_USED
except Exception:
    voice_used = None
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:  # visible on the run page in GitHub
    with open(summary, "a") as f:
        ok = engine == "story"
        ok = (engine == "explainer" and pillar != "puzzle") or (pillar == "puzzle" and engine in ("story", "hype"))
        f.write(f"## {'✅ Premium reel' if ok else '⚠️ Fallback reel'} · pillar `{pillar}` · engine `{engine}`\n\n"
                f"- Slot: `{slot}` · level: `{level}` · mode: `{mode}` · CTA: `{arms.get('cta', brand.CTA_MODE)}`\n"
                f"- Engine: `{engine}` · voice: `{voice_used}` · format: `{brand.FORMAT}` · narrator: `{brand.NARRATOR}`\n"
                + (f"- Story: {meta.get('story')}\n" if meta.get("story") else "")
                + (f"- Reviewer score: {meta.get('review_score')}/10\n" if meta.get("review_score") is not None else "")
                + f"- {insights_msg}\n"
                + (f"- Experiment: {', '.join(f'{k}={v.split(chr(58))[0]}' for k, v in arms.items())}\n" if arms else "")
                + (f"- {strat_msg}\n" if strat_msg else "")
                + "".join(f"- Error: `{e}`\n" for e in errors))
caption = open(out.replace(".mp4", ".txt")).read()
print(caption)

if dry:
    print("DRY RUN: not publishing")
    sys.exit(0)

from publish_ig import publish_reel, publish_story
if loc: print("Location:", loc["name"])
media = publish_reel(out, caption, location_id=loc and loc["id"])
meta.update(location=loc and loc["name"], permalink=media.get("permalink"), media_id=media.get("id"), engine=engine)
mark_used(P["id"])

try:  # also share it as a Story (never blocks the reel)
    publish_story(out); meta["story_share"] = "ok"
except Exception as e:
    print("Story failed:", e); meta["story_share"] = f"error: {e}"

if os.environ.get("FB_REELS", "on") != "off":  # Facebook Reels on the academy Page (never blocks Instagram)
    try:
        from publish_fb import publish_fb_reel
        from publish_ig import ig_safe
        meta["facebook"] = publish_fb_reel(ig_safe(out), caption)
    except Exception as e:
        print("Facebook failed:", e); meta["facebook"] = f"error: {str(e)[:200]}"

if os.environ.get("ZERNIO_API_KEY"):  # YouTube Shorts + TikTok via Zernio (never blocks Instagram)
    try:
        from publish_zernio import crosspost as zernio_post
        from publish_ig import ig_safe
        meta["zernio"] = zernio_post(ig_safe(out), meta["hook"], caption)
    except Exception as e:
        print("Zernio failed:", e); meta["zernio"] = f"error: {e}"

meta["voice"] = voice_used
meta["pillar"] = pillar
brake = guard.health()
if brake:
    guard.pause(brake)
    print("BRAKE:", brake)
meta["arms"] = arms if engine in ("story", "explainer") else ({"cta": arms["cta"]} if arms.get("cta") else {})
log({k: meta.get(k) for k in ("engine", "pillar", "voice", "review_score", "arms", "mode", "puzzle", "level", "rating", "story",
                              "hook", "location", "permalink", "media_id", "sans", "story_share", "facebook", "zernio",
                              "blocks", "cta", "qc")})
if brake:
    raise SystemExit(f"Published, then the automatic brake engaged: {brake}")
