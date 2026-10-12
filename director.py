"""Creative director: a second AI agent that reviews COPY and DESIGN before anything is published.

1. copy_chief(): senior direct-response copywriter for parent audiences. Writes 5 alternative hooks, scores them
   (scroll-stop, clarity, curiosity, relevance, credibility), keeps the best, then tightens every scene so the reel
   flows pain -> insight -> proof -> invitation, and the last scene bridges naturally into the call to action.
2. art_director(): looks at a STORYBOARD (one key frame per scene + the end card, rendered from the real design
   system in about a second) and checks legibility, overlaps, hierarchy, empty space, consistency and whether each
   image matches what the voice says. It returns concrete fixes (shorter headline, other highlight words, another
   block from the same slot, shorter list items) which are applied and checked again, up to 2 rounds.
3. brand_guardian(): the competitor test. Scores how unmistakably ChessTalentsFactory the script is (could another
   academy post it word for word?) and how well it follows the brand bible (voice, vocabulary, banned words). Below
   8/10, or with no anchor of ours at all (deterministic check), it rewrites the script around our method anchor.
Every fix goes through make_explainer.validate(), so the agent can never break the honesty rules or the layout.
"""
import json, os
from PIL import Image, ImageDraw

import brand, guard
import design as D

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_log.jsonl")


def _ask(parts, temp=0.5):
    import reviewer
    return reviewer._ask(parts, temp)


def _jpeg_b64(im, w=1080):
    import reviewer
    return reviewer._jpeg_b64(im, w)


def _log(entry):
    import datetime
    with open(LOG, "a") as f:
        f.write(json.dumps({"date": str(datetime.date.today()), **entry}, ensure_ascii=False) + "\n")


ROLE = f"""You are the creative director of {brand.NAME}'s short-form video (Instagram Reels, Facebook, Shorts).
{brand.bible()}
{brand.AUDIENCE}
{brand.ACADEMY}
{brand.HONESTY}
Standards: premium, calm confidence, zero hype, zero cliches. Every reel must (1) stop a busy parent's scroll in the
first 1.5 seconds, (2) teach or show something specific and credible, (3) make them think "these people really know
how kids improve", (4) end with a natural bridge into the call to action, so they comment, follow or visit the profile."""


def brand_guardian(sc, pillar, context, slots_text):
    hits = guard.anchored(sc)
    res = _ask([{"text": f"""You are the BRAND GUARDIAN of {brand.NAME}. Your only job: protect a premium, distinctive brand.
BRAND BIBLE:
{brand.bible()}
{brand.HONESTY}
{guard.approved_text()}
{context}

SCRIPT TO JUDGE (pillar: {pillar}):
{json.dumps(sc, ensure_ascii=False)}
Our anchors found automatically: {hits or 'NONE'}

1) Score 1-10 "distinctiveness": 10 = only ChessTalentsFactory could have made this (our method, our concepts by name,
   our cases, our coaches); 1 = any academy or freelance coach could post it word for word.
2) Score 1-10 "voice": matches the brand bible voice and vocabulary, no banned words, premium and calm.
3) If either score is below 8, rewrite the script so it passes: weave in the METHOD ANCHOR / today's key / case
   above by name, use our vocabulary, remove anything generic or off-voice. Keep the hook if it is strong, keep the
   same scenes and blocks (allowed per slot: {slots_text}), keep the JSON schema, keep it honest.
Return JSON: {{"distinctiveness": number, "voice": number, "issues": [str], "script": <full script JSON or null>}}"""}], 0.5)
    return res, hits


def copy_chief(sc, pillar, context, slots_text):
    res = _ask([{"text": f"""{ROLE}
{guard.approved_text()}
{context}
FACTS you may use: {'; '.join(brand.FACTS)}

DRAFT SCRIPT (pillar: {pillar}):
{json.dumps(sc, ensure_ascii=False)}

Allowed blocks per scene (keep each scene inside its slot):
{slots_text}

Step 1. Write 5 alternative HOOKS for scene 1 (headline max 6 words + first narration sentence). Use different
angles: a sharp question, a counter-intuitive claim, a specific moment parents recognise, a mistake, a promise of
insight. Score each 1-10 for scroll-stop, clarity, curiosity, relevance to this pillar and credibility. Pick the best.
Step 2. Rewrite the whole script around the chosen hook: one idea per scene, concrete words parents use, narration
8-20 words per scene, total 75-110 words, headlines max 6 words with 1-2 highlight words, narration matching what
each block shows, last scene ends with a line that leads into the call to action ("{brand.cta('keyword')['say'][:40]}...").
Keep the JSON schema, the same number of scenes, and params valid for each block.
Return JSON: {{"hooks": [{{"headline": str, "line": str, "score": number}}], "chosen": int,
"script": <the full improved script JSON>, "notes": str}}"""}], 0.7)
    out = res.get("script") or {}
    for k in ("caption_hook", "caption_body", "title", "summary"):
        out.setdefault(k, sc.get(k))
    return out, {"hooks": res.get("hooks", [])[:5], "chosen": res.get("chosen"), "notes": (res.get("notes") or "")[:300]}


# ----------------------------------------------------------------------- storyboard
def est_durations(sc):
    return [max(2.6, len(s["narration"].split()) / 2.6 + 0.6) for s in sc["scenes"]]


def frame(sc, i, t, kind="keyword"):
    fr = Image.new("RGBA", (D.W, D.H), (0, 0, 0, 255))
    durs = est_durations(sc)
    if i < len(sc["scenes"]):
        s = dict(sc["scenes"][i]); s["_first"] = i == 0
        off = 1.2 if i == 0 else 0.0                      # the first scene opens fully composed (cover = hook)
        D.DRAW[s["block"]](fr, t + off, durs[i] + off, s)
        dark = s["block"] in D.DARK_BLOCKS
        D.brand_bar(fr, sum(durs[:i]) + t, sum(durs) + 5, dark)
        words = s["narration"].split()
        D.captions(fr, [(k * 0.38, w) for k, w in enumerate(words)], t)
    else:
        D.end_card(fr, t, 5.0, kind)
        D.brand_bar(fr, sum(durs) + t, sum(durs) + 5, True)
    return fr


def storyboard(sc, kind="keyword"):
    durs = est_durations(sc)
    shots = [(0, 0.0)] + [(i, durs[i] * 0.85) for i in range(len(sc["scenes"]))] + [(len(sc["scenes"]), 3.2)]
    tw, th, cols = 360, 640, 4
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 16, rows * (th + 56) + 16), (235, 235, 238))
    d = ImageDraw.Draw(sheet)
    for k, (i, t) in enumerate(shots):
        im = frame(sc, i, t, kind).convert("RGB").resize((tw, th))
        x, y = 16 + (k % cols) * (tw + 16), 16 + (k // cols) * (th + 56)
        sheet.paste(im, (x, y + 40))
        label = "FIRST FRAME (cover)" if k == 0 else ("END CARD" if i >= len(sc["scenes"]) else f"SCENE {i + 1}: {sc['scenes'][i]['block']}")
        d.text((x, y + 8), label, font=D.font(D.F_UI, 22), fill=(30, 30, 30))
    return sheet


def art_director(sc, pillar, slots_text, kind):
    sheet = storyboard(sc, kind)
    res = _ask([{"text": f"""{ROLE}
You are now the ART DIRECTOR. Below is the storyboard of a reel: the first frame (also the cover), one key frame per
scene (in order) and the end card. Script: {json.dumps(sc['scenes'], ensure_ascii=False)}

Check every frame like a top motion designer: text fully readable on a phone, nothing cut off or overlapping (text vs
characters vs cards vs captions), clear hierarchy (one focal point), balanced composition (no awkward empty areas or
crowding), consistent premium look, highlight words that really matter, the image supports what the voice says,
the first frame works as a cover that makes parents stop.
You may only fix things with these actions (per scene index starting at 0):
- "headline": a shorter/clearer headline (max 6 words), "highlight": 1-2 words of it
- "block": another block from the same slot (see below)
- "params": shorter list items / different numbers ONLY if allowed
Slots: {slots_text}
Return JSON: {{"score": 1-10, "critical": bool, "summary": str, "fixes": [{{"scene": int, "headline": str?,
"highlight": [str]?, "block": str?, "params": {{}}?, "why": str}}]}}. If it is already excellent, return no fixes."""},
                {"inline_data": {"mime_type": "image/jpeg", "data": _jpeg_b64(sheet, 1500)}}], 0.3)
    return res


def apply_fixes(sc, fixes):
    sc = json.loads(json.dumps(sc))
    for f in fixes or []:
        try:
            i = int(f.get("scene"))
        except Exception:
            continue
        if not 0 <= i < len(sc["scenes"]):
            continue
        s = sc["scenes"][i]
        if f.get("headline"):
            s["headline"] = str(f["headline"])
        if isinstance(f.get("highlight"), list):
            s["highlight"] = f["highlight"]
        if f.get("block"):
            s["block"] = f["block"]
        if isinstance(f.get("params"), dict):
            s["params"] = {**(s.get("params") or {}), **f["params"]}
    return sc


def direct(sc, pillar, context, slots_text, validate, kind, agent=None):
    """Full creative review. Always returns a valid script (the best version that passed validation).
    The director polishes but keeps the creator's voice and angle, so creators stay distinct."""
    report = {"pillar": pillar, "agent_id": agent}
    if agent:
        import studio
        context = (context + f"\nThis script was written by {studio.CREATORS[agent]['name']} "
                   f"({studio.CREATORS[agent]['persona'][:160]}...). Keep its voice and angle; improve, don't flatten.")
    try:
        new, info = copy_chief(sc, pillar, context, slots_text)
        if sc.get("_key"):
            new["_key"] = sc["_key"]
        sc = validate(new, pillar)
        report["copy"] = info
        print("director/copy: hook =", sc["scenes"][0]["headline"], "|", info.get("notes", "")[:120], flush=True)
    except Exception as e:
        report["copy_error"] = str(e)[:200]; print("director/copy skipped:", str(e)[:200], flush=True)
    try:                                              # brand guardian: the competitor test
        res, hits = brand_guardian(sc, pillar, context, slots_text)
        dist, voice = float(res.get("distinctiveness") or 0), float(res.get("voice") or 0)
        rewrote = False
        if (dist < 8 or voice < 8 or not hits) and isinstance(res.get("script"), dict):
            new = res["script"]
            for k in ("caption_hook", "caption_body", "title", "summary", "_key"):
                if sc.get(k) is not None:
                    new.setdefault(k, sc.get(k))
            new = validate(new, pillar)
            if guard.anchored(new):
                sc, rewrote = new, True
        report["brand"] = {"distinctiveness": dist, "voice": voice, "anchors": guard.anchored(sc),
                           "issues": (res.get("issues") or [])[:4], "rewrote": rewrote}
        print(f"director/brand: distinctiveness {dist}/10, voice {voice}/10, anchors {guard.anchored(sc)}"
              + (" -> rewritten" if rewrote else ""), flush=True)
    except Exception as e:
        report["brand_error"] = str(e)[:200]; print("director/brand skipped:", str(e)[:200], flush=True)
    report["art"] = []
    for rnd in range(2):
        try:
            res = art_director(sc, pillar, slots_text, kind)
        except Exception as e:
            report["art_error"] = str(e)[:200]; print("director/art skipped:", str(e)[:200], flush=True); break
        score = float(res.get("score") or 0)
        report["art"].append({"round": rnd + 1, "score": score, "summary": (res.get("summary") or "")[:300],
                              "fixes": res.get("fixes", [])[:8]})
        print(f"director/art round {rnd + 1}: {score}/10 - {res.get('summary', '')[:150]}", flush=True)
        if (score >= 8 and not res.get("critical")) or not res.get("fixes"):
            break
        try:
            sc = validate(apply_fixes(sc, res["fixes"]), pillar)
        except Exception as e:
            print("director/art fixes rejected by validation:", str(e)[:150], flush=True); break
    _log({"agent": "director", **report})
    return sc, report
