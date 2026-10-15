"""Motion-graphics explainer reels for ChessTalentsFactory (style of the "Stuck in chess?" video).

The AI only writes: it picks scene BLOCKS from a fixed catalog and writes headlines + narration. Every block is
designed and animated in code with the academy's characters (assets/kit/*.png), so visual quality never depends
on an image model. Pillars (what the reel is about) come from the weekly calendar in run_daily.py:

  pain    rating stuck -> wrong way -> mentor/roadmap -> method/authority -> (proof) -> CTA
  faq     a parent's question -> honest answer -> method/authority -> CTA
  method  the roadmap: what each level needs -> steps -> authority -> CTA
  proof   only with approved claims (claims.json): mentor -> rating up / trophy -> CTA

Replace the character cut-outs in assets/kit/ with the designer's source art (same file names, transparent PNG)
and every reel improves automatically.
"""
import io, json, math, os, random, re, subprocess, time
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import brand, guard
import make_reel as R
import make_hype as HY

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 25, 24000
KIT = os.path.join(HERE, "assets", "kit")
F_HEAD = os.path.join(HERE, "fonts", "Arvo-Bold.ttf")
F_UI = os.path.join(HERE, "fonts", "Poppins-Bold.ttf")
INK = (24, 22, 28)
ORANGE = brand.ORANGE
ORANGE_D = (214, 86, 24)
BG_LIGHT = (250, 245, 242)
LOG = os.path.join(HERE, "explainer_log.json")


def font(path, size, _c={}):
    k = (path, size)
    if k not in _c:
        _c[k] = ImageFont.truetype(path, size)
    return _c[k]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_out(t): t = clamp(t); return t * t * (3 - 2 * t)
def back(t, s=1.6): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2


# ======================================================================= catalog (what the AI may use)
BLOCKS = {
    "pain":         "a frustrated child sitting on the chess floor, thought bubble. params: {\"pose\": \"sad\"|\"thinking\"}",
    "rating_drop":  "the child + a rating card that drops (illustrative). params: {\"from\": int 600-2000, \"to\": int lower}",
    "wrong_way":    "dark scene, up to 3 cards of what does NOT work, crossed out. params: {\"items\": [max 3 phrases, max 3 words each]}",
    "mentor":       "the coach walks in and stands next to the child. params: {}",
    "roadmap":      "a roadmap card whose steps light up as stars, ending in a trophy, child beside it. params: {}",
    "method_steps": "3 numbered steps appear one by one next to the coach. params: {\"steps\": [3 phrases, max 4 words each]}",
    "authority":    "coach and child hand in hand, 2-3 badges pop in. params: {\"badges\": [2-3 items copied EXACTLY from FACTS]}",
    "faq_question": "a big question card with the thinking child. params: {\"question\": max 8 words}",
    "faq_answer":   "up to 3 answer points tick in next to the coach. params: {\"points\": [max 3 phrases, max 5 words each]}",
    "progress":     "the child stands up and an upward progress line grows (no numbers). params: {}",
    "rating_up":    "rating gain counter (ONLY with an approved claim). params: {}",
    "trophy":       "the child lifts a trophy, confetti. params: {}",
    "limited":      "calendar with spots filling (ONLY with the approved limited_spots claim). params: {}",
    "before_after": "REAL student rating progress counter. params: {\"from\": int, \"to\": int, \"label\": \"in 13 months\"} - numbers ONLY from TODAY'S STUDENT CASE",
    "success_timeline": "REAL student milestones appear one by one with medals. params: {\"milestones\": [2-4 items, max 7 words each, ONLY from TODAY'S STUDENT CASE]}",
    "key_card": "signature card 'SQUARE 65 - KEY n/65' with the key's title, by IM Alberto Chueca. params: {\"key\": n} (n = TODAY'S KEY)",
}

PILLARS = {
    "pain": [["pain", "rating_drop"], ["wrong_way"], ["mentor", "roadmap"], ["method_steps", "authority"],
             ["progress", "trophy"]],
    "faq": [["faq_question"], ["faq_answer"], ["method_steps", "mentor", "roadmap"], ["authority"]],
    "method": [["pain", "rating_drop"], ["roadmap"], ["method_steps"], ["authority"], ["progress", "trophy"]],
    "proof": [["pain", "rating_drop"], ["mentor"], ["rating_up", "progress"], ["trophy"], ["authority"]],
    "success": [["pain", "rating_drop"], ["before_after", "success_timeline"], ["success_timeline", "method_steps"],
                ["trophy", "authority"]],
    "remix": [["pain", "rating_drop", "faq_question"], ["wrong_way", "faq_answer", "mentor"],
              ["roadmap", "method_steps"], ["authority", "progress", "trophy"]],
    "benefits": [["pain", "faq_question"], ["wrong_way", "faq_answer"], ["method_steps", "roadmap"],
                 ["authority", "progress", "trophy"]],
    "rating": [["faq_question", "pain"], ["roadmap"], ["method_steps", "faq_answer"], ["authority", "progress"]],
    "key": [["pain", "faq_question", "rating_drop", "wrong_way"], ["key_card"], ["method_steps", "faq_answer", "roadmap"],
            ["authority", "progress", "trophy"]],
}

PILLAR_BRIEF = {
    "pain": "Name a painful, specific situation chess parents live (rating stuck, losing in tournaments, endless blitz "
            "without progress, child losing motivation), why the usual fixes fail, and what structured training with "
            "a real coach changes.",
    "faq": "Answer ONE real question parents ask before hiring a chess academy (groups vs private, online vs in "
           "person, how much time per week, when to start tournaments, why not cheaper freelance coaches, what age, "
           "how fast progress shows). Be honest and specific.",
    "method": "Explain how structured training works: a level-based roadmap, what a child at a given level must "
              "master next, why order matters, assignments between lessons.",
    "proof": "Show credibility using ONLY the approved claims and facts: what changes when a child trains with the "
             "right method.",
    "success": "Tell the REAL story of TODAY'S STUDENT CASE below: where the child started, what changed with structured "
               "training, the milestones reached. Use ONLY its facts, exactly. Then connect it to the parent watching "
               "(it is a pattern, not a promise).",
    "benefits": "Show a parent what chess training really gives their child beyond the board: focus, patience, "
                "handling frustration, confidence, school habits, less passive screen time. Concrete everyday moments, "
                "no exaggerated science claims.",
    "rating": "Explain to a parent who has never played chess what a chess rating is (like a school grade or a race "
              "time that goes up as skills grow), what our 6 Learning Path levels mean, and what really moves a child "
              "from one level to the next.",
    "key": "Teach TODAY'S KEY from Square 65, the book by IM Alberto Chueca that condenses our method into 65 keys. "
           "Scene 1: the problem this key solves, as a parent sees it. Scene 2: the key_card (name it: 'Key n of Square "
           "65'). Scene 3: what to actually do, in concrete steps taken from the key. Scene 4: how we apply it with our "
           "students. Faithful to the book; never invent what the key says.",
    "remix": "Re-explain the IDEA TO REMIX below in a completely new way: a new hook, a new angle, a new example or "
             "analogy. Do not copy its wording or structure. It must feel like a fresh reel to someone who saw the original.",
}


def allowed_blocks():
    out = set(BLOCKS)
    if not guard.has("avg_gain"):
        out.discard("rating_up")
    if not guard.has("limited_spots"):
        out.discard("limited")
    if not guard.cases():
        out -= {"before_after", "success_timeline"}
    if not os.path.exists(os.path.join(HERE, "method_bank.json")):
        out.discard("key_card")
    return out                      # a trophy is a symbol of goals: allowed without any number


PROMPT = """{creator}

You write a {secs}-second vertical motion-graphics reel for {name}.
{bible}
{audience}
{academy}
{narrator}
{honesty}
{claims}
{cases}
FACTS you may use freely: {facts}

PILLAR: {pillar}. {brief}
{context}
TODAY'S CREATIVE BRIEF (A/B experiment, follow it): hook style = {hook_style}; theme = {theme}.
{playbook}
Recent reels (do NOT repeat their idea or headlines): {recent}

Build exactly {n} scenes. Scene k must use one block from SLOT k:
{slots}
Block catalog: {catalog}

Rules:
- Scene 1 stops a busy parent's scroll in 1.5 seconds: headline of 2-5 words that names their pain or question.
- headline: max 6 words, title style, punchy; "highlight": 1-2 words of the headline shown in orange.
- narration per scene: 8-20 spoken words, short sentences, contractions, numbers as words, expert-to-parent tone,
  no hype, no cliches, no chess notation. Total narration {words} words. The narration of each scene must match
  what its block shows.
- delivery: 3-8 word acting direction for the voice (calm, confident, warm; vary it).
- No prices. No guarantees. No competitors. Never state a number about results, students or titles unless it is
  in APPROVED CLAIMS. Rating numbers are allowed ONLY inside a rating_drop block as an illustrative example.
- PARENT TEST: the viewer is a parent who has NEVER played chess; their child loves it. No chess jargon or
  notation. If a chess idea is needed, translate it into everyday words (school, sports, music practice).
- COMPETITOR TEST: if another academy or a freelance coach could post this reel word for word, it fails. Carry at
  least one of OUR anchors (Square 65 key, Learning Path level, T-T-P or another signature concept, a real approved
  case, a coach credential) and use our vocabulary from the brand bible.
- caption_hook: Instagram first line for parents, max 12 words, one emoji allowed.
- caption_body: 1-2 short sentences that add value for the parent (no hashtags).
Return JSON: {{"title": str, "summary": str, "caption_hook": str, "caption_body": str,
"scenes": [{{"block": str, "headline": str, "highlight": [str], "narration": str, "delivery": str, "params": {{}}}}]}}"""


def _slots_text(pillar, allowed):
    lines = []
    for i, opts in enumerate(PILLARS[pillar]):
        ok = [b for b in opts if b in allowed] or ["mentor"]
        lines.append(f"  SLOT {i + 1}: {' | '.join(ok)}")
    return "\n".join(lines)


def _recent(n=12):
    try:
        return json.load(open(LOG))[-n:]
    except Exception:
        return []


NAMES = os.environ.get("STUDENT_NAMES", "none").lower()     # none | first


def pick_case():
    """Least recently featured approved case."""
    cases = guard.cases()
    if not cases:
        return None
    used = {}
    for i, r in enumerate(_recent(200)):
        if r.get("case"):
            used[r["case"]] = i
    return min(cases, key=lambda c: used.get(c["id"], -1))


def case_text(c):
    who = (c.get("name") or "one of our students") if NAMES == "first" else "one of our students"
    return (f"TODAY'S STUDENT CASE (real, published by the academy; refer to the child as \"{who}\", never any other "
            f"name, never invent anything): {c['text']} | Facts: " + "; ".join(c.get("facts", [])))


def method_bank():
    try:
        return json.load(open(os.path.join(HERE, "method_bank.json")))
    except Exception:
        return []


def _used_keys():
    used = {}
    for i, r in enumerate(_recent(400)):
        for k in (r.get("key"), r.get("anchor_key")):
            if k:
                used[int(k)] = i
    return used


def pick_key(pillar=None, rng=None):
    """Least recently used key. pillar=None -> any key (key pillar); otherwise keys relevant to that pillar."""
    bank = method_bank()
    if not bank:
        return None
    rng = rng or random.Random()
    if os.environ.get("PARENT_KEYS_ONLY", "true") == "true":     # our audience: parents who don't play chess
        bank = [k for k in bank if k.get("parent_friendly", True)] or bank
    pool = [k for k in bank if pillar is None or pillar in k.get("pillars", [])] or bank
    used = _used_keys()
    never = [k for k in pool if k["n"] not in used]
    if never:                                        # spread chapters: random among the never-used ones
        return rng.choice(never)
    return min(pool, key=lambda k: used.get(k["n"], -1))


def key_text(k, full=True):
    body = k["text"][:2200] if full else k["summary"]
    return (f"TODAY'S KEY: Square 65, Key {k['n']} of 65 - \"{k['title']}\" (chapter: {k['chapter']}). "
            f"What the book says (stay faithful, do not copy long sentences, do not invent):\n{body}")


def context_for(pillar):
    rng = random.Random()
    if pillar == "key":
        k = pick_key(None, rng)
        if k:
            return key_text(k), {"key": k["n"]}
    ctx, extra = _context_main(pillar)
    if pillar in ("success", "remix") and not ctx:
        return ctx, extra
    k = pick_key(pillar if pillar in ("pain", "faq", "method", "benefits") else None, rng)
    if k:                                            # every reel carries our method (competitor test)
        ctx += ("\n\nMETHOD ANCHOR (weave it in naturally, at least one sentence; e.g. 'In Square 65, IM Alberto "
                "Chueca calls this...' or 'It's Key " + str(k["n"]) + " of our method'):\n" + key_text(k, full=False))
        extra["anchor_key"] = k["n"]
    return ctx, extra


def _context_main(pillar):
    if pillar == "success":
        c = pick_case()
        if c:
            return case_text(c), {"case": c["id"]}
    if pillar == "remix":
        try:
            import content_bank
            it = content_bank.pick_remix()
        except Exception:
            it = None
        if it:
            a = it["analysis"]
            return (f"IDEA TO REMIX (from one of our past reels; re-explain it, do not copy): {a.get('reusable_idea')} | "
                    f"Key points: {'; '.join(a.get('key_points', []))} | Why it worked: {a.get('why_it_works')}"), {"remix_of": it["id"]}
    return "", {}


def write_script(pillar, arms=None, context="", agent=None, key=None):
    import make_story as MS, strategy
    arms = arms or {}
    allowed = allowed_blocks()
    n = len(PILLARS[pillar])
    recent = _recent()
    import studio
    body = {"contents": [{"role": "user", "parts": [{"text": PROMPT.format(
        creator=studio.brief(agent) if agent in studio.CREATORS else "", secs="35-50", bible=brand.bible(), name=brand.NAME, audience=brand.AUDIENCE, academy=brand.ACADEMY, narrator=brand.narrator_text(),
        honesty=brand.HONESTY, claims=guard.approved_text(), cases=brand.cases_text(), facts="; ".join(brand.FACTS),
        pillar=pillar, brief=PILLAR_BRIEF[pillar], hook_style=arms.get("hook_style", "your best idea"),
        theme=arms.get("theme", "your best idea"),
        playbook=("WHAT WORKS FOR OUR AUDIENCE (from real results):\n" + strategy.playbook_text()) if strategy.playbook_text() else "",
        recent="; ".join(f"{r.get('agent') or '-'}/{r.get('pillar')}: {r.get('title')} ({r.get('headline')})" for r in recent) or "none",
        n=n, slots=_slots_text(pillar, allowed), catalog=json.dumps({k: v for k, v in BLOCKS.items() if k in allowed}),
        words="75-110", context=context)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}}
    body0 = body
    last = None
    for model in MS.text_models(3):
        body = body0
        for attempt in range(2):                  # 2nd attempt = repair: same model, told exactly what to fix
            try:
                j = MS._post(model, body)
                txt = j["candidates"][0]["content"]["parts"][0]["text"]
                sc = json.loads(re.sub(r"^```(json)?|```$", "", txt.strip()))
                if key:
                    sc["_key"] = key
                    for x in sc.get("scenes", []):
                        if x.get("block") == "key_card":
                            x.setdefault("params", {})["key"] = key
                out = validate(sc, pillar)
                print(f"explainer script: {model}" + (" (repaired)" if attempt else ""), flush=True)
                return out
            except ValueError as e:               # script broke a rule -> ask the same model to fix it
                last = e; print(f"explainer script: {model} rejected: {str(e)[:160]}", flush=True)
                body = {**body, "contents": body["contents"][:1] + [
                    {"role": "model", "parts": [{"text": txt}]},
                    {"role": "user", "parts": [{"text": f"Your script was rejected by our checks: {e}. Rewrite the whole "
                     "script fixing ONLY that. Any number about students, ratings or results must be one of the "
                     "APPROVED CLAIMS or the REAL CASE facts exactly (you may write it in words). Same JSON schema."}]}]}
            except Exception as e:
                last = e; print(f"explainer script: {str(e)[:160]}", flush=True)
                break                              # API problem -> next model
    raise RuntimeError(f"explainer script failed: {last}")


def validate(sc, pillar):
    """Hard rules the AI cannot break: block per slot, lengths, params, approved claims only."""
    allowed = allowed_blocks()
    scenes = sc.get("scenes") or []
    slots = PILLARS[pillar]
    if len(scenes) < len(slots):
        raise ValueError("too few scenes")
    scenes = scenes[:len(slots)]
    for i, s in enumerate(scenes):
        opts = [b for b in slots[i] if b in allowed] or ["mentor"]
        if s.get("block") not in opts:
            s["block"] = opts[0]
        s["headline"] = " ".join(str(s.get("headline", "")).split()[:6]) or "Chess parents"
        s["narration"] = " ".join(str(s.get("narration", "")).split()[:26])
        s["highlight"] = [h for h in (s.get("highlight") or []) if isinstance(h, str)][:2]
        p = s.get("params") or {}
        if s["block"] == "authority":
            facts = {f.lower(): f for f in brand.FACTS}
            b = [facts[x.lower()] for x in p.get("badges", []) if isinstance(x, str) and x.lower() in facts][:3]
            p["badges"] = b or ["International Masters", "Small groups of 2-6", "Level-based roadmap"]
        if s["block"] == "rating_drop":
            a = int(clamp(float(p.get("from") or 1400), 500, 2200)); b = int(clamp(float(p.get("to") or a - 150), 300, a - 30))
            p["from"], p["to"] = a, b
        for key, k, nw in (("items", 3, 3), ("steps", 3, 4), ("points", 3, 5)):
            if key in p:
                p[key] = [" ".join(str(x).split()[:nw]) for x in p[key] if str(x).strip()][:k]
        if s["block"] == "before_after":
            try:
                a, b = int(p.get("from")), int(p.get("to"))
                ok_n, _ = guard.claims_ok(f"{a} rating {b} rating")
                if not ok_n or b <= a:
                    raise ValueError
                p["from"], p["to"] = a, b
                p["label"] = " ".join(str(p.get("label", "")).split()[:4])
            except Exception:
                s["block"] = "success_timeline" if "success_timeline" in allowed else "progress"
        if s["block"] == "success_timeline":
            p["milestones"] = [" ".join(str(x).split()[:7]) for x in p.get("milestones", []) if str(x).strip()][:4] or ["Real progress"]
        if s["block"] == "key_card":
            bank = {k["n"]: k for k in method_bank()}
            try:
                n = int(p.get("key"))
            except Exception:
                n = sc.get("_key")
            if n not in bank:
                n = sc.get("_key") if sc.get("_key") in bank else None
            if n is None:
                s["block"] = next((b for b in slots[i] if b != "key_card" and b in allowed), "roadmap")
            else:
                p["key"] = n; p["title"] = bank[n]["title"]; p["chapter"] = bank[n]["chapter"]
        if s["block"] == "faq_question":
            p["question"] = " ".join(str(p.get("question") or s["headline"]).split()[:8])
        s["params"] = p
    text = " ".join(f"{s['headline']} {s['narration']} {json.dumps(s['params'])}" for s in scenes if s["block"] != "rating_drop")
    text += " " + sc.get("caption_hook", "") + " " + sc.get("caption_body", "")
    text = re.sub(r"\b(?:age|aged|at)\s+\d+\b", " ", text)       # ages are not result claims
    hard, _soft = guard.jargon({"scenes": scenes})
    if hard:
        raise ValueError(f"chess jargon a non-playing parent cannot follow: {hard[:4]}")
    ok, bad = guard.claims_ok(text)
    if not ok:
        raise ValueError(f"unapproved claims: {bad}")
    words = sum(len(s["narration"].split()) for s in scenes)
    if not 45 <= words <= 140:
        raise ValueError(f"narration length {words}")
    sc["scenes"] = scenes
    return sc


def mock_script(pillar):
    return {
        "title": "Mock explainer", "summary": "mock", "caption_hook": "Is your child's rating stuck? 👇",
        "caption_body": "Most plateaus aren't about talent. They're about structure.",
        "scenes": [
            {"block": "pain", "headline": "Stuck in chess?", "highlight": ["Stuck"], "params": {"pose": "sad"},
             "narration": "Watching your talented child stay stuck at the same rating is tough.", "delivery": "warm"},
            {"block": "wrong_way", "headline": "More games won't fix it", "highlight": ["won't"],
             "params": {"items": ["Random YouTube", "Endless blitz", "No clear plan"]},
             "narration": "Random videos and endless blitz feel like practice, but they aren't a strategy.", "delivery": "direct"},
            {"block": "roadmap", "headline": "Kids need a roadmap", "highlight": ["roadmap"], "params": {},
             "narration": "Strong kids follow a roadmap, one skill at a time, in the right order.", "delivery": "calm"},
            {"block": "authority", "headline": "Train with International Masters", "highlight": ["International", "Masters"],
             "params": {"badges": ["International Masters", "Small groups of 2-6", "Level-based roadmap"]},
             "narration": "Our students train with International Masters, in small groups of kids at their level.", "delivery": "warm"},
            {"block": "progress", "headline": "Structure beats talent", "highlight": ["Structure"], "params": {},
             "narration": "With structure, progress stops being luck and becomes a plan.", "delivery": "confident"},
        ]}


import design as D
DRAW = D.DRAW


# ======================================================================= build
def evergreen_script(pillar):
    """Pre-written fallback (real facts only), least recently used; same pillar if possible."""
    lib = json.load(open(os.path.join(HERE, "evergreen.json")))
    cases = {c["id"] for c in guard.cases()}
    lib = [x for x in lib if not x.get("case") or x["case"] in cases]
    used = {r.get("evergreen"): i for i, r in enumerate(_recent(200)) if r.get("evergreen")}
    same = [x for x in lib if x["pillar"] == pillar] or lib
    sc = json.loads(json.dumps(min(same, key=lambda x: used.get(x["id"], -1))))
    extra = {"evergreen": sc["id"], **({"case": sc["case"]} if sc.get("case") else {})}
    for k in ("key", "anchor_key"):
        if sc.get(k):
            extra[k] = sc[k]
    return validate(sc, sc["pillar"]), sc["pillar"], extra


def build(seed, out, pillar="pain", arms=None, mock=None, evergreen=False, agent=None):
    import voice, studio
    arms = arms or {}
    if agent in studio.CREATORS:
        studio.apply_look(agent)                           # each creator has its own on-brand visual look
    mock = os.environ.get("STORY_MOCK") == "1" if mock is None else mock
    rng = random.Random(seed)
    kind = arms.get("cta") if arms.get("cta") in brand.CTA else (brand.CTA_MODE if brand.CTA_MODE in brand.CTA else "keyword")
    director_report = None
    if evergreen:
        sc, pillar, extra = evergreen_script(pillar)
    else:
        ctx, extra = ("", {}) if mock else context_for(pillar)
        if pillar in ("success", "remix") and not ctx:
            pillar = "pain"                                # nothing to feature yet -> a pain reel instead
        sc = mock_script(pillar) if mock else write_script(pillar, arms, ctx, agent, extra.get("key"))
        if not mock and os.environ.get("REVIEWER", "on") != "off":
            import director                                # 2nd agent: copy chief + art director
            sc, director_report = director.direct(sc, pillar, ctx, _slots_text(pillar, allowed_blocks()), validate, kind,
                                                  agent=agent)
    scenes = [dict(x) for x in sc["scenes"]]
    scenes[0]["_first"] = False
    CT = brand.cta(kind)
    # ---- voice: one continuous performance (natural, consistent), split per scene; falls back to line by line
    voice.reset()
    texts = [x["narration"] for x in scenes] + [CT["say"]]
    A = voice.say_many(texts, speed=1.0, styles=[x.get("delivery") for x in scenes] + ["warm, confident, inviting"],
                       one_take=True)
    LEAD, PAD = 0.25, 0.45
    durs = [max(2.6, LEAD + len(a) / SR + PAD) for a in A[:-1]] + [max(4.6, LEAD + len(A[-1]) / SR + 1.6)]
    starts = np.cumsum([0.0] + durs[:-1]); total = float(sum(durs))
    words = []
    for i, a in enumerate(A):
        for ts, w in voice.align(a, texts[i]):
            words.append((starts[i] + LEAD + ts, w))
    # ---- audio: voice + tonal transitions + soft ticks + chime + ducked music bed (no noise-based effects)
    n = int(total * SR) + SR
    mix = np.zeros(n, np.float32)
    def put(x, at, g=1.0):
        a0 = max(0, int(at * SR)); b0 = min(n, a0 + len(x)); mix[a0:b0] += g * x[:b0 - a0]
    for i, a in enumerate(A):
        put(a.astype(np.float32), starts[i] + LEAD, 1.0)
    for i in range(1, len(durs)):
        put(D.swell(0.55), starts[i] - 0.3, 0.8)
    for i in range(len(scenes)):
        put(D.tick(), starts[i] + 0.12, 0.6)
    put(D.chime(), starts[-1] + 1.4, 0.7)
    bed = D.music(n / SR)
    duck = np.ones(n, np.float32)
    for i, a in enumerate(A):
        s0 = int((starts[i] + LEAD - 0.1) * SR); duck[max(0, s0):s0 + len(a) + int(0.2 * SR)] = 0.45
    duck = np.convolve(duck, np.ones(int(0.12 * SR)) / int(0.12 * SR), "same").astype(np.float32)   # smooth ducking
    mix += bed[:n] * duck
    mix /= max(1.0, float(np.abs(mix).max()) / 0.92)
    wav = out.replace(".mp4", "_x.wav"); sf.write(wav, mix[:int(total * SR)], SR)
    # ---- video
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + HY.enc_args(out), stdin=subprocess.PIPE)
    TR = 0.4
    prev_last = None
    nf = int(total * FPS)
    for fi in range(nf):
        tg = fi / FPS
        i = int(np.searchsorted(starts, tg, side="right") - 1)
        lt = tg - starts[i]
        fr = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        if i < len(scenes):
            sc_i = dict(scenes[i]); sc_i["_first"] = (i == 0)            # frame 0 already shows the full hook (cover)
            DRAW[sc_i["block"]](fr, lt + (1.2 if i == 0 else 0.0), durs[i] + (1.2 if i == 0 else 0.0), sc_i)
            dark = sc_i["block"] in D.DARK_BLOCKS
            D.brand_bar(fr, tg, total, dark)
            D.captions(fr, [(ts, w) for ts, w in words if starts[i] - 0.01 <= ts < starts[i] + durs[i]], tg)
        else:
            D.end_card(fr, lt, durs[i], kind)
            D.brand_bar(fr, tg, total, True)
        if i > 0 and lt < TR and prev_last is not None:             # crossfade + gentle scale
            k = D.ease_in_out(lt / TR)
            sc_in = 1.04 - 0.04 * k
            inc = fr.resize((int(W * sc_in), int(H * sc_in)), Image.BILINEAR).crop(
                (int((W * sc_in - W) / 2), int((H * sc_in - H) / 2), int((W * sc_in - W) / 2) + W, int((H * sc_in - H) / 2) + H))
            fr = Image.blend(prev_last, inc, k)
        if int(np.searchsorted(starts, (fi + 1) / FPS, side="right") - 1) != i:
            prev_last = fr.copy()
        proc.stdin.write(fr.convert("RGB").tobytes())
    proc.stdin.close(); proc.wait(); os.remove(wav)
    # ---- caption
    cap = (f"{sc.get('caption_hook', scenes[0]['headline'])}\n{sc.get('caption_body', '')}\n\n{CT['caption']}\n"
           f"{brand.PARENT_LINE}\n\n" + " ".join(brand.hashtags(rng)))
    open(out.replace(".mp4", ".txt"), "w").write(cap)
    meta = dict(mode="explainer", pillar=pillar, story=sc.get("title"), hook=sc.get("caption_hook"),
                headline=scenes[0]["headline"], blocks=[x["block"] for x in scenes], duration=round(total, 1),
                cta=kind, arms=arms, review_score=None, agent=agent if not evergreen else None)
    if director_report:
        arts = director_report.get("art") or []
        meta["brand_check"] = director_report.get("brand")
        meta["director"] = {"hook_options": [h.get("headline") for h in (director_report.get("copy") or {}).get("hooks", [])],
                            "art_scores": [r["score"] for r in arts], "art_summary": arts[-1]["summary"] if arts else None}
    if not mock and not evergreen and os.environ.get("REVIEWER", "on") != "off":
        try:
            import reviewer
            new_cap, rep = reviewer.review_video(out, {"title": sc.get("title")}, cap, kind="explainer")
            if new_cap:
                open(out.replace(".mp4", ".txt"), "w").write(new_cap)
            meta["review_score"] = rep.get("overall")
        except reviewer.RejectReel:
            raise
        except Exception as e:
            print("explainer review skipped:", e)
    log = _recent(200) + [{"pillar": pillar, "title": sc.get("title"), "headline": scenes[0]["headline"],
                           "date": time.strftime("%Y-%m-%d"), "agent": agent, **extra}]
    if extra.get("remix_of"):
        try:
            import content_bank; content_bank.mark_remixed(extra["remix_of"])
        except Exception as e:
            print("mark_remixed:", e)
    meta.update(extra)
    json.dump(log[-200:], open(LOG, "w"), indent=0)
    return meta


def review_script(sc, pillar):
    """2nd agent: makes the script sharper for parents, then the same hard validation runs again."""
    try:
        import reviewer
        res = reviewer._ask([{"text": f"""{reviewer.PRODUCER}
{guard.approved_text()}
FACTS: {'; '.join(brand.FACTS)}
Improve this motion-graphics reel script (pillar: {pillar}). Keep the same number of scenes and the SAME block in each
scene, keep the JSON schema. Make scene 1 stop a parent's scroll, make every narration concrete and credible, match
narration to what each block shows, remove anything that breaks the honesty rules. Headlines max 6 words.
SCRIPT: {json.dumps(sc, ensure_ascii=False)}
Return the improved script JSON only."""}], 0.6)
        return validate(res, pillar)
    except Exception as e:
        print("explainer script review skipped:", str(e)[:200], flush=True)
        return sc
