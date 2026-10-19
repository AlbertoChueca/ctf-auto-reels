"""One publishing slot for ChessTalentsFactory: ONE post a day, rotating formats made for parents.

python run_daily.py story [--dry-run]

Weekly calendar (New York date), override with FORMAT_OVERRIDE:
  Mon carousel  Tue chat  Wed challenge  Thu voice  Fri carousel  Sat kinetic  Sun challenge
  carousel   7-slide advice carousel (make_carousel)         - most saved/shared format
  chat       text conversation parent <-> coach (make_textreel) - no narrator
  kinetic    big confident text lines + music (make_textreel)   - no narrator
  challenge  "can your child find the winning move?" (make_challenge) - families answer in the comments
  voice      the narrated real-footage reel (make_broll), with a verified expressive voice
Every engine has an offline fallback (pre-written scripts / built-in puzzles), so a post always goes out.
Every post: Instagram (carousel or reel) + Story, Facebook Reel, YouTube/TikTok when configured.
"""
import datetime, json, os, random, sys, traceback
import brand, guard

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


# ---- weekly calendar (US date), Mon..Sun: 14 reels a week, success stories and remixes get the most slots
MIDDAY = {0: "pain", 1: "success", 2: "benefits", 3: "remix", 4: "faq", 5: "success", 6: "rating"}
EVENING = {0: "key", 1: "faq", 2: "key", 3: "success", 4: "key", 5: "remix", 6: "benefits"}   # key = a principle of our method
PILLARS = ("pain", "faq", "method", "proof", "success", "remix", "key", "benefits", "rating")
us_today = (now - datetime.timedelta(hours=5)).date()
wd = us_today.weekday()
pillar = os.environ.get("PILLAR_OVERRIDE", "auto")
if pillar not in PILLARS:
    pillar = MIDDAY[wd] if slot == "story" else EVENING[wd]
if pillar == "proof" and not (guard.has("avg_gain") or guard.has("fide_titles")):
    pillar = "method"
if pillar == "success" and not guard.cases():
    pillar = "pain"

CALENDAR = {0: "carousel", 1: "chat", 2: "challenge", 3: "voice", 4: "carousel", 5: "kinetic", 6: "challenge"}
FORMATS = ("carousel", "chat", "kinetic", "challenge", "voice")
fmt = os.environ.get("FORMAT_OVERRIDE", "auto")
if fmt not in FORMATS:
    fmt = CALENDAR[wd]
print("format:", fmt, flush=True)

why = guard.paused()
if why and not dry and os.environ.get("FORCE_PUBLISH") != "true":
    print(f"PAUSED: {why}. Delete paused.json (or run with force) to resume.")
    raise SystemExit(f"Publishing paused: {why}")

insights_msg = ""
try:                       # real Instagram results -> performance.json (the autopilot learns from them)
    import insights
    insights_msg = insights.update(); print(insights_msg, flush=True)
except Exception as e:
    insights_msg = f"insights skipped: {str(e)[:150]}"; print(insights_msg, flush=True)

# ---- autopilot experiment: choose today's creative options (learns from past results)
arms, strat_msg = {}, ""
try:
    import strategy
    fixed = {"cta": brand.CTA_MODE if brand.CTA_MODE in brand.CTA else "keyword"}   # one CTA everywhere: comment PLAN
    arms = strategy.choose(seed=f"{now:%Y-%m-%d-%H}-{slot}", fixed=fixed)
    if slot == "story":
        strat_msg = strategy.weekly_strategist()
    strategy.write_report()
    print("experiment:", {k: strategy.short(v) for k, v in arms.items()}, "|", strat_msg, flush=True)
except Exception as e:
    strat_msg = f"strategy skipped: {str(e)[:150]}"; print(strat_msg, flush=True)

# ---- the studio: 5 creators compete; they learn once a day from their own real results
agent, studio_msg = None, ""
try:
    if fmt != "voice" or os.environ.get("STUDIO", "off") != "on":
        raise RuntimeError("off (one consistent voice; turn on with STUDIO=on once real views are measured)")
    import studio
    studio_msg = studio.learn(); print(studio_msg, flush=True)
    recent_agents = []
    try:
        recent_agents = [x.get("agent") for x in json.load(open("explainer_log.json"))[-3:] if x.get("agent")]
    except Exception:
        pass
    agent = studio.pick(pillar, seed=f"{now:%Y-%m-%d-%H}-{slot}-agent", recent_agents=recent_agents)
    print("creator:", studio.CREATORS[agent]["name"], flush=True)
except Exception as e:
    studio_msg = f"studio skipped: {str(e)[:150]}"; print(studio_msg, flush=True)

out = f"out/{today}_{slot}_{now.hour:02d}.mp4"

# ---- render
ai = bool(os.environ.get("GEMINI_API_KEY"))
meta, engine, errors = None, None, []
slides = None
if fmt == "voice":
    arms.pop("format", None)
    chain = (["broll", "broll"] if ai else []) + ["evergreen_broll"]
    for eng in chain:
        try:
            import make_broll
            meta = make_broll.build(seed, out, pillar=pillar, arms=arms, evergreen=(eng == "evergreen_broll"), agent=agent)
            meta["qc"] = guard.qc(out)
            meta["arms"] = dict(meta.get("arms") or arms)
            if meta.get("shape"):
                meta["arms"]["shape"] = meta["shape"]
            engine = eng
            break
        except Exception as e:
            errors.append(f"{eng}: {str(e)[:300]}")
            print(f"[{eng}] failed:\n{traceback.format_exc()[-1500:]}", flush=True)
    if meta is None:                                   # narrated reel impossible today -> a text reel instead
        fmt = "kinetic"
if fmt in ("carousel", "chat", "kinetic", "challenge") and meta is None:
    tries = [(fmt, True), (fmt, False)] if fmt != "challenge" else [(fmt, True)]
    tries += [("kinetic", False)]                      # last resort: pre-written text reel, no AI, no download
    for f_, use_ai in tries:
        try:
            if f_ == "carousel":
                import make_carousel
                meta = make_carousel.build(seed, out.replace(".mp4", "_carousel"), use_ai=use_ai)
                slides = meta.pop("slides")
                os.replace(meta["reel"], out); os.replace(meta["reel"].replace(".mp4", ".txt"), out.replace(".mp4", ".txt"))
            elif f_ == "challenge":
                import make_challenge
                meta = make_challenge.build(seed, out)
            else:
                import make_textreel
                meta = make_textreel.build(seed, out, style=f_, use_ai=use_ai)
            meta["qc"] = guard.qc(out)
            fmt, engine = f_, meta.get("engine")
            break
        except Exception as e:
            meta = None
            errors.append(f"{f_}: {str(e)[:300]}")
            print(f"[{f_}] failed:\n{traceback.format_exc()[-1500:]}", flush=True)
if meta is None:
    n_fail = guard.record_run(False, "; ".join(errors))
    if n_fail >= 2:
        guard.pause(f"{n_fail} runs in a row failed: {errors[-1][:200]}")
    raise SystemExit("All render attempts failed")
guard.record_run(True)
pillar = meta.get("pillar", pillar)
print("engine:", engine, "| pillar:", pillar, flush=True)
try:
    import voice as _v
    voice_used = _v.ENGINE_USED
except Exception:
    voice_used = None
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:  # visible on the run page in GitHub
    with open(summary, "a") as f:
        f.write(f"## {fmt} · {'✅ AI copy' if engine in ('broll', 'ai', 'lichess') else '⚠️ fallback content'} · engine `{engine}`\n\n"
                + (f"- Topic: `{meta.get('topic')}` · music: `{meta.get('music')}`\n" if fmt != "voice" else "")
                + f"- Slot: `{slot}` · CTA: `{meta.get('cta')}` · voice: `{voice_used if fmt == 'voice' else 'none (music only)'}`\n"
                + (f"- Creator: **{studio.CREATORS[meta['agent']]['name']}** · {studio_msg}\n" if meta.get("agent") else f"- {studio_msg}\n")
                + (f"- Title: {meta.get('story')}\n" if meta.get("story") else "")
                + (f"- Format: **real footage** · shape `{meta.get('shape')}` · grade `{meta.get('grade')}` · clips: "
                   f"{sum(1 for x in (meta.get('footage') or []) if x)}/{len(meta.get('footage') or [])}\n" if fmt == "voice" else "")
                + (f"- Blocks: {', '.join(meta.get('blocks') or [])}\n" if meta.get("blocks") else "")
                + (f"- Student case: `{meta.get('case')}`\n" if meta.get("case") else "")
                + (f"- Remix of: `{meta.get('remix_of')}`\n" if meta.get("remix_of") else "")
                + (f"- Director: hooks considered: {' | '.join(meta['director'].get('hook_options') or [])}\n"
                   f"- Director: art scores {meta['director'].get('art_scores')} - {meta['director'].get('art_summary')}\n"
                   if meta.get("director") else "")
                + (f"- Brand guardian: distinctiveness {meta['brand_check'].get('distinctiveness')}/10, voice "
                   f"{meta['brand_check'].get('voice')}/10, anchors {meta['brand_check'].get('anchors')}"
                   f"{' (rewritten)' if meta['brand_check'].get('rewrote') else ''}\n" if meta.get("brand_check") else "")
                + (f"- Method principle: #{meta.get('key') or meta.get('anchor_key')}\n" if (meta.get("key") or meta.get("anchor_key")) else "")
                + (f"- Final video review: {meta.get('review_score')}/10\n" if meta.get("review_score") is not None else "")
                + f"- {insights_msg}\n"
                + (f"- Experiment: {', '.join(f'{k}={v.split(chr(58))[0]}' for k, v in arms.items())}\n" if arms else "")
                + (f"- {strat_msg}\n" if strat_msg else "")
                + "".join(f"- Error: `{e}`\n" for e in errors))
caption = open(out.replace(".mp4", ".txt")).read()
print(caption)

if dry:
    print("DRY RUN: not publishing")
    sys.exit(0)

from publish_ig import publish_reel, publish_story, publish_carousel
if loc: print("Location:", loc["name"])
media = None
if slides:
    try:
        media = publish_carousel(slides, caption, location_id=loc and loc["id"]); meta["published_as"] = "carousel"
    except Exception as e:
        print("Carousel failed, publishing the same slides as a reel:", str(e)[:300], flush=True)
        errors.append(f"carousel publish: {str(e)[:200]}")
if media is None:
    media = publish_reel(out, caption, location_id=loc and loc["id"]); meta["published_as"] = "reel"
meta.update(location=loc and loc["name"], permalink=media.get("permalink"), media_id=media.get("id"), engine=engine)

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
        meta["zernio"] = zernio_post(ig_safe(out), meta.get("hook") or meta.get("headline", ""), caption)
    except Exception as e:
        print("Zernio failed:", e); meta["zernio"] = f"error: {e}"

meta["voice"] = voice_used
brake = guard.health()
if brake:
    guard.pause(brake)
    print("BRAKE:", brake)
meta["format"] = fmt
log({k: meta.get(k) for k in ("engine", "format", "published_as", "topic", "puzzle", "music", "shape", "footage", "pillar", "voice", "review_score", "arms", "story", "hook", "headline", "location",
                              "permalink", "media_id", "story_share", "facebook", "zernio", "blocks", "cta", "qc",
                              "case", "remix_of", "director", "agent", "key",
                              "anchor_key", "brand_check")})
if brake:
    raise SystemExit(f"Published, then the automatic brake engaged: {brake}")
