"""One publishing slot for ChessTalentsFactory. TWO posts a day: midday and evening (New York time).

python run_daily.py story|storytag [--dry-run]        (story = midday slot, storytag = evening slot)

Every post is an animated explainer (make_animated). SEVEN kinds, about 80 % education / 20 % the academy:
              midday      evening
  Mon         problem     METHOD
  Tue         myth        howto
  Wed         science     problem
  Thu         question    RESULTS
  Fri         problem     myth
  Sat         howto       science
  Sun         question    METHOD / RESULTS (alternating weeks)
  problem / myth / science / howto / question  = useful for any chess parent, no selling
  METHOD  = how we train      RESULTS = a real student's progress + proven numbers (claims.json, cases.json)
Override by hand: KIND_OVERRIDE (one of the seven), TOPIC_OVERRIDE (free text), FORMAT_OVERRIDE (carousel, chat,
kinetic, challenge, voice: the older formats).
Every engine has an offline fallback (pre-written scripts), so a post always goes out.
Every post: Instagram reel with its cover frame + first comment + Story, Facebook Reel, and TikTok / YouTube Shorts
when Zernio is configured. Reels that end with "comment PLAN" (the Instagram DM bot) get a second cut ending with
"link on our profile" for the other platforms.
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

FORMATS = ("animated", "carousel", "chat", "kinetic", "challenge", "voice")
fmt = os.environ.get("FORMAT_OVERRIDE", "auto")
if fmt not in FORMATS:
    fmt = "animated"

# ---- the seven kinds of animated reel: 11 educational + 3 about the academy every week (about 80 / 20)
KIND_MIDDAY = {0: "problem", 1: "myth", 2: "science", 3: "question", 4: "problem", 5: "howto", 6: "question"}
KIND_EVENING = {0: "method", 1: "howto", 2: "problem", 3: "results", 4: "myth", 5: "science",
                6: "method" if us_today.isocalendar()[1] % 2 else "results"}
ALL_KINDS = ("problem", "myth", "science", "howto", "question", "method", "results")
kind = os.environ.get("KIND_OVERRIDE", "auto")
if kind not in ALL_KINDS:
    kind = "problem" if (os.environ.get("TOPIC_OVERRIDE") or "").strip() else (KIND_MIDDAY if slot == "story" else KIND_EVENING)[wd]
print("format:", fmt, "| kind:", kind if fmt == "animated" else "-", flush=True)

if not dry and os.environ.get("IG_TOKEN"):      # check the token BEFORE spending minutes and AI calls on a reel
    try:
        import publish_ig
        print("Instagram token OK: @" + str(publish_ig.whoami(os.environ["IG_TOKEN"]).get("username")), flush=True)
    except publish_ig.TokenError as e:
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(f"## ❌ Nothing was published: the Instagram token must be renewed\n\n{e}\n")
        raise SystemExit(f"NOT PUBLISHED. {e}")
    except Exception as e:
        print("token check skipped:", str(e)[:200], flush=True)

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
if fmt in ("animated", "carousel", "chat", "kinetic", "challenge") and meta is None:
    tries = [(fmt, True), (fmt, False)] if fmt != "challenge" else [(fmt, True)]
    tries += [("animated", False)] if fmt != "animated" else [("kinetic", False)]   # last resort: pre-written, no AI
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
            elif f_ == "animated":
                import make_animated
                meta = make_animated.build(seed, out, kind=kind, use_ai=use_ai)
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
                + (f"- Kind: **{meta.get('kind')}** ({meta.get('pillar')}) · cut for TikTok/YouTube/Facebook: "
                   f"{'own ending (link on profile)' if meta.get('alt_video') else 'same video'}\n" if fmt == "animated" else "")
                + (f"- Animated: {meta.get('duration')}s · scenes: {', '.join(meta.get('blocks') or [])} · research: "
                   f"`{meta.get('evidence')}` · narration: `{meta.get('voice_engine')}` · hooks tried: "
                   f"{' | '.join(meta.get('hook_options') or []) or '-'}\n" if fmt == "animated" else "")
                + f"- Slot: `{slot}` · CTA: `{meta.get('cta')}` · voice: `{voice_used if fmt in ('voice', 'animated') else 'none (music only)'}`\n"
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
# Facebook, TikTok and YouTube have no "comment PLAN" DM bot: they get the cut and the caption that point to the profile link
out_x = meta.get("alt_video") if meta.get("alt_video") and os.path.exists(meta["alt_video"]) else out
caption_x = meta.get("caption_alt") or caption

if dry:
    if os.environ.get("ZERNIO_API_KEY"):            # a dry run also tells where TikTok / YouTube would be posted
        try:
            import publish_zernio
            zmsg = publish_zernio.plan()[1]
        except Exception as e:
            zmsg = [f"Zernio: {str(e)[:200]}"]
        print("\n".join(zmsg), flush=True)
        if summary:
            open(summary, "a").write("".join(f"- Zernio · {m}\n" for m in zmsg))
    elif summary:
        open(summary, "a").write("- TikTok / YouTube: sin configurar (falta el secreto `ZERNIO_API_KEY`)\n")
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
    media = publish_reel(out, caption, location_id=loc and loc["id"], thumb_offset_ms=meta.get("thumb_offset_ms"))
    meta["published_as"] = "reel"
meta.update(location=loc and loc["name"], permalink=media.get("permalink"), media_id=media.get("id"), engine=engine)

if meta.get("comment_prompt") and os.environ.get("FIRST_COMMENT", "on") != "off":   # a question that invites answers
    try:
        from publish_ig import comment as _comment
        _comment(media["id"], meta["comment_prompt"]); meta["first_comment"] = "ok"
    except Exception as e:
        print("First comment failed:", str(e)[:200]); meta["first_comment"] = f"error: {str(e)[:120]}"

try:  # also share it as a Story (never blocks the reel)
    publish_story(out); meta["story_share"] = "ok"
except Exception as e:
    print("Story failed:", e); meta["story_share"] = f"error: {e}"

if os.environ.get("FB_REELS", "on") != "off":  # Facebook Reels on the academy Page (never blocks Instagram)
    try:
        from publish_fb import publish_fb_reel
        from publish_ig import ig_safe
        meta["facebook"] = publish_fb_reel(ig_safe(out_x), caption_x)
    except Exception as e:
        print("Facebook failed:", e); meta["facebook"] = f"error: {str(e)[:200]}"

if os.environ.get("ZERNIO_API_KEY"):  # TikTok + YouTube Shorts via Zernio (never blocks Instagram)
    try:
        from publish_zernio import crosspost as zernio_post
        from publish_ig import ig_safe
        meta["zernio"] = zernio_post(ig_safe(out_x), meta.get("story") or meta.get("headline", ""), caption_x)
    except Exception as e:
        print("Zernio failed:", e); meta["zernio"] = f"error: {str(e)[:300]}"
else:
    meta["zernio"] = "not configured"
    print("TikTok / YouTube: not configured (add the ZERNIO_API_KEY secret, see LEEME.md)", flush=True)
if summary:
    with open(summary, "a") as f:
        f.write(f"- Publicado: Instagram ✅ · Story `{meta.get('story_share')}` · Facebook `{meta.get('facebook')}` · "
                f"TikTok/YouTube `{meta.get('zernio')}`\n")

meta["voice"] = voice_used
brake = guard.health()
if brake:
    guard.pause(brake)
    print("BRAKE:", brake)
meta["format"] = fmt
log({k: meta.get(k) for k in ("engine", "format", "published_as", "topic", "puzzle", "music", "evidence", "voice_engine",
                              "duration", "first_comment", "hook_options", "shape", "footage", "pillar", "voice", "review_score", "arms", "story", "hook", "headline", "location",
                              "permalink", "media_id", "story_share", "facebook", "zernio", "blocks", "cta", "qc",
                              "case", "remix_of", "director", "agent", "key", "kind",
                              "anchor_key", "brand_check")})
if brake:
    raise SystemExit(f"Published, then the automatic brake engaged: {brake}")
