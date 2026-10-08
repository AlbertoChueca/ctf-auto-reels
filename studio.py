"""The creative studio: 5 AI creators that compete and improve every day.

Each creator has
- a persona (how it thinks, its kind of hooks and angles),
- the pillars it is best at (pain, faq, method, success, remix, proof),
- its own visual LOOK (background family + highlight style), so the feed looks varied but on-brand,
- a NOTEBOOK (agents/<id>.md) it rewrites once a day from its own real results: best/worst reels, audience
  comments, and what the creative director corrected. The notebook is injected into every script it writes.

Every day each slot picks a creator with Thompson sampling on its real results (profile visits, follows, shares,
saves, views) among the creators that cover today's pillar, plus 20 % exploration, so better creators get more
turns but nobody stops experimenting. Weekly, the studio head writes shared lessons (agents/_studio.md) from the
winning creator so the others learn from it, and retires each creator's weakest habit.

All scripts still go through validate() + the creative director (copy chief + art director) + final video review,
so a creator can be daring with ideas but never break the honesty rules or the design system.
"""
import datetime, json, math, os, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "agents")
PERF = os.path.join(HERE, "performance.json")
EXPLORE = float(os.environ.get("STUDIO_EXPLORE", "0.2"))

CREATORS = {
    "analyst": dict(
        name="The Analyst",
        persona=("A calm International-Master-level coach who explains chess improvement like an engineer: precise, "
                 "structured, one clear framework per reel (3 steps, 1 rule, before/after). Hooks are specific and "
                 "intriguing ('The 3 skills between 1200 and 1500'). Speaks to analytical, high-achieving parents."),
        pillars=["method", "faq", "proof"],
        look={"light": "paper", "marker": "underline"}),
    "storyteller": dict(
        name="The Storyteller",
        persona=("A warm documentary narrator. Turns real student journeys into short emotional arcs: the moment of "
                 "doubt, the turning point, the result. Hooks open on a vivid moment ('He was stuck at 1100 for a "
                 "year'). Uses ONLY real, approved facts. Makes parents picture their own child."),
        pillars=["success", "remix", "pain"],
        look={"light": "warm", "marker": "fill"}),
    "mythbuster": dict(
        name="The Myth Buster",
        persona=("A bold, contrarian expert who opens by breaking a belief parents hold ('More games won't fix it', "
                 "'Openings aren't the problem'). Pattern-interrupt hooks, short punchy lines, then a clear, credible "
                 "alternative. Never rude, never hype."),
        pillars=["pain", "method", "remix"],
        look={"light": "studio", "marker": "fill"}),
    "parent_whisperer": dict(
        name="The Parent Whisperer",
        persona=("Speaks from the parent's side of the table: the drive to the tournament, the tears after a loss, "
                 "the doubt about which coach to trust. Empathetic first sentence, then honest, practical answers to "
                 "the questions parents ask before hiring an academy. Builds trust and handles objections."),
        pillars=["faq", "pain", "success"],
        look={"light": "paper", "marker": "fill"}),
    "trend_scout": dict(
        name="The Trend Scout",
        persona=("A creative short-form strategist obsessed with what makes people stop scrolling: curiosity gaps, "
                 "unexpected comparisons, 'POV' and 'nobody tells parents this' formats, numbered reveals. Re-invents "
                 "the account's best past ideas in fresh formats. Always original, never gimmicky."),
        pillars=["remix", "pain", "faq", "method"],
        look={"light": "warm", "marker": "underline"}),
}


# ----------------------------------------------------------------------- notebooks
def notebook(cid):
    try:
        return open(os.path.join(DIR, f"{cid}.md")).read().strip()
    except Exception:
        return ""


def studio_notes():
    try:
        return open(os.path.join(DIR, "_studio.md")).read().strip()
    except Exception:
        return ""


def brief(cid):
    """Text injected into the script prompt for this creator."""
    c = CREATORS[cid]
    nb, sn = notebook(cid), studio_notes()
    return (f"YOU ARE {c['name'].upper()}, one of 5 competing creators in our studio. Your reels are measured by real "
            f"profile visits, follows, shares and saves, and the best creator gets more reels.\n{c['persona']}\n"
            + (f"YOUR NOTEBOOK (what you learned from your own results; apply it):\n{nb}\n" if nb else "")
            + (f"STUDIO LESSONS (shared by the best creator; apply them):\n{sn}\n" if sn else "")
            + "Be original: a hook you have never used, an angle the other creators have not used recently.")


# ----------------------------------------------------------------------- choice (Thompson sampling)
def _rows():
    try:
        perf = json.load(open(PERF))
    except Exception:
        return []
    import strategy
    out = []
    for r in perf.values():
        if r.get("agent") in CREATORS:
            rw = strategy.reward(r)
            if rw is not None:
                out.append((r["agent"], rw, r))
    return out


def standings():
    rows = _rows()
    vals = [rw for _, rw, _ in rows]
    mu = sum(vals) / len(vals) if vals else 0.0
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 if len(vals) > 1 else 1.0
    st = {c: [0, 0.0] for c in CREATORS}
    for a, rw, _ in rows:
        st[a][0] += 1; st[a][1] += rw
    return {c: (n, s / n if n else None) for c, (n, s) in st.items()}, mu, max(sd, 0.3)


def pick(pillar, seed=None, recent_agents=()):
    forced = os.environ.get("AGENT_OVERRIDE", "auto")
    if forced in CREATORS:
        return forced
    rng = random.Random(seed)
    cands = [c for c, v in CREATORS.items() if pillar in v["pillars"]] or list(CREATORS)
    if len(cands) > 1 and recent_agents:                    # variety: avoid the creator of the previous reel
        cands = [c for c in cands if c != recent_agents[-1]] or cands
    st, mu, sd = standings()
    if rng.random() < EXPLORE or sum(st[c][0] for c in cands) < 6:
        return min(cands, key=lambda c: (st[c][0], rng.random()))     # early on: give everyone turns
    best, bv = None, -1e9
    for c in cands:
        n, m = st[c]
        v = rng.gauss(((m if m is not None else mu) * n + mu) / (n + 1), sd / math.sqrt(n + 1))
        if v > bv:
            best, bv = c, v
    return best


def apply_look(cid):
    import design as D
    D.set_look(**CREATORS[cid]["look"])


# ----------------------------------------------------------------------- daily learning
def _comments(media_id, token, n=15):
    if not (media_id and token):
        return []
    try:
        import requests
        from publish_ig import GRAPH
        r = requests.get(f"{GRAPH}/{media_id}/comments", params={"fields": "text", "limit": n, "access_token": token},
                         timeout=30).json()
        return [c.get("text", "")[:160] for c in r.get("data", []) if c.get("text")]   # no usernames (privacy)
    except Exception:
        return []


def _director_notes(cid, n=6):
    out = []
    try:
        for line in open(os.path.join(HERE, "review_log.jsonl")):
            e = json.loads(line)
            if e.get("agent_id") == cid:
                for a in e.get("art", []):
                    out.append(a.get("summary", ""))
                if (e.get("copy") or {}).get("notes"):
                    out.append(e["copy"]["notes"])
    except Exception:
        pass
    return [x for x in out if x][-n:]


def _ask(text):
    import reviewer
    return reviewer._ask([{"text": text}], 0.6)


def learn(force=False):
    """Once a day: every creator with measured reels rewrites its notebook. Mondays: studio lessons."""
    os.makedirs(DIR, exist_ok=True)
    stamp = os.path.join(DIR, ".last_learn")
    today = str(datetime.date.today())
    if not force and os.path.exists(stamp) and open(stamp).read().strip() == today:
        return "studio: already learned today"
    if not os.environ.get("GEMINI_API_KEY"):
        return "studio: no GEMINI_API_KEY"
    rows = _rows(); token = os.environ.get("IG_TOKEN")
    st, mu, _ = standings()
    done = []
    for cid, c in CREATORS.items():
        mine = sorted([r for a, _, r in rows if a == cid], key=lambda r: r.get("date", ""))[-20:]
        if not mine:
            continue
        import strategy
        ranked = sorted(mine, key=strategy.reward, reverse=True)
        def line(r):
            return (f"- {r.get('date')} [{r.get('pillar')}] hook: {r.get('headline') or r.get('hook')!r} | views "
                    f"{r.get('views')} | profile visits {r.get('profile_visits')} | follows {r.get('follows')} | "
                    f"shares {r.get('shares')} | saves {r.get('saved')} | avg watch "
                    f"{round((r.get('ig_reels_avg_watch_time') or 0) / 1000, 1)}s")
        best, worst = ranked[:3], ranked[-3:][::-1]
        comments = []
        for r in best[:2] + worst[:1]:
            comments += _comments(r.get("media_id"), token, 8)
        try:
            res = _ask(f"""You are {c['name']}, a creator of short reels for a premium online chess academy for kids
(audience: busy, ambitious US parents). Persona: {c['persona']}
Your average score: {st[cid][1] if st[cid][1] is not None else 'n/a'} vs studio average {round(mu, 2)} ({st[cid][0]} reels).
YOUR BEST REELS:
{chr(10).join(map(line, best))}
YOUR WORST REELS:
{chr(10).join(map(line, worst))}
WHAT PARENTS COMMENTED (anonymous): {json.dumps(comments[:20], ensure_ascii=False)}
WHAT THE CREATIVE DIRECTOR CORRECTED IN YOUR SCRIPTS: {json.dumps(_director_notes(cid), ensure_ascii=False)}
YOUR CURRENT NOTEBOOK:
{notebook(cid) or '(empty)'}

Rewrite your notebook (max 180 words, bullet points, plain English) for your next reels:
- KEEP: hooks, angles, words and structures that brought profile visits, follows, shares and saves.
- STOP: what failed or the director kept fixing.
- TRY NEXT: 3 specific, original experiments (new hook formats or angles) that fit your persona.
Be concrete (quote hook patterns). Never invent facts about students or results.
Return JSON: {{"notebook": str}}""")
            nb = (res.get("notebook") or "").strip()
            if nb:
                open(os.path.join(DIR, f"{cid}.md"), "w").write(f"# {c['name']} - notebook ({today})\n\n{nb}\n")
                done.append(cid)
        except Exception as e:
            print("studio learn", cid, str(e)[:150], flush=True)
    msg = f"studio: notebooks updated for {', '.join(done) or 'nobody yet (no measured reels)'}"
    if datetime.date.today().weekday() == 0 or force:
        ranked = sorted([(c, m) for c, (n, m) in st.items() if n >= 3 and m is not None], key=lambda x: -x[1])
        if ranked:
            top = ranked[0][0]
            try:
                res = _ask(f"""You are the head of a 5-creator reel studio for a premium chess academy (audience: US
parents). The best creator this period is {CREATORS[top]['name']} (score {round(ranked[0][1], 2)}; ranking:
{', '.join(f"{CREATORS[c]['name']} {round(m, 2)}" for c, m in ranked)}).
Its notebook:
{notebook(top)}
Write STUDIO LESSONS for all creators (max 120 words, bullets): the 3-5 transferable principles behind the winner's
results (hooks, pacing, CTA, structure), phrased so each creator can apply them in its own style. Return JSON:
{{"lessons": str}}""")
                if res.get("lessons"):
                    open(os.path.join(DIR, "_studio.md"), "w").write(f"# Studio lessons ({today}) - leader: "
                                                                      f"{CREATORS[top]['name']}\n\n{res['lessons']}\n")
                    msg += f"; studio lessons from {CREATORS[top]['name']}"
            except Exception as e:
                print("studio lessons", str(e)[:150], flush=True)
    open(stamp, "w").write(today)
    return msg


def leaderboard_md():
    st, mu, _ = standings()
    rows = sorted(CREATORS, key=lambda c: -(st[c][1] if st[c][1] is not None else -99))
    out = ["| Creador | Reels medidos | Puntuación media |", "|---|---|---|"]
    for c in rows:
        n, m = st[c]
        out.append(f"| {CREATORS[c]['name']} | {n} | {round(m, 2) if m is not None else '-'} |")
    return "\n".join(out)
