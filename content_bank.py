"""Weekly: analyse the reels already published on the academy's Instagram (the editor's originals and the
automatic ones) and keep content_bank.json: topic, hook, key points, why it worked, and real student successes.

- run_daily's "remix" pillar re-explains the best ideas in a completely new way (new hook, new angle), never
  repeating the same idea within REMIX_COOLDOWN days.
- Student successes stated in the academy's own published reels are added to cases.json (source "instagram",
  first names removed by default) so the "success" pillar can use them. Set "approved": false to exclude one.
Free-tier friendly: at most MAX_NEW videos analysed per run (downscaled to 360p before sending to Gemini).
"""
import base64, datetime, json, os, re, subprocess, tempfile, requests

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "content_bank.json")
MAX_NEW = int(os.environ.get("BANK_MAX_NEW", "8"))
REMIX_COOLDOWN = int(os.environ.get("REMIX_COOLDOWN", "45"))

PROMPT = """You analyse a short vertical video published by ChessTalentsFactory, an online chess academy for kids
(audience: US parents). Caption: {caption!r}
Return JSON only:
{{"topic": str, "hook": str (what the first seconds say/show), "key_points": [max 5 short strings],
"why_it_works": str (one sentence), "pillar": "pain"|"faq"|"method"|"success"|"puzzle"|"other",
"reusable_idea": str (the core idea in one sentence, so it can be re-explained differently),
"student_success": {{"present": bool, "facts": [strings, ONLY facts explicitly stated in the video or caption:
ratings, titles, tournaments, time frames], "student_name": str or ""}},
"quality": 1-10 (how strong this idea is for parents)}}
Never invent facts. If something is not clearly stated, leave it out."""


def _media(token, uid):
    from publish_ig import GRAPH
    out, url = [], f"{GRAPH}/{uid}/media"
    params = {"fields": "id,caption,media_type,media_product_type,permalink,timestamp,media_url,like_count,comments_count",
              "limit": 50, "access_token": token}
    while url and len(out) < 500:
        r = requests.get(url, params=params, timeout=60).json()
        out += r.get("data", [])
        url, params = r.get("paging", {}).get("next"), None
    return out


def _views(token, mid):
    from publish_ig import GRAPH
    try:
        r = requests.get(f"{GRAPH}/{mid}/insights", params={"metric": "views,reach,shares,saved", "access_token": token}, timeout=30)
        return {d["name"]: (d.get("values") or [{}])[0].get("value") for d in r.json().get("data", [])}
    except Exception:
        return {}


def _analyse(video_url, caption):
    import make_story as MS
    with tempfile.TemporaryDirectory() as td:
        raw, small = os.path.join(td, "v.mp4"), os.path.join(td, "s.mp4")
        with requests.get(video_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(raw, "wb") as f:
                for ch in r.iter_content(1 << 20):
                    f.write(ch)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-t", "90", "-vf", "scale=360:-2", "-r", "10",
                        "-c:v", "libx264", "-crf", "32", "-preset", "veryfast", "-c:a", "aac", "-b:a", "48k", small], check=True)
        data = base64.b64encode(open(small, "rb").read()).decode()
    body = {"contents": [{"parts": [{"text": PROMPT.format(caption=(caption or "")[:1500])},
                                    {"inline_data": {"mime_type": "video/mp4", "data": data}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}}
    last = None
    for model in MS.text_models(3):
        try:
            j = MS._post(model, body)
            return json.loads(re.sub(r"^```(json)?|```$", "", j["candidates"][0]["content"]["parts"][0]["text"].strip()))
        except Exception as e:
            last = e
    raise RuntimeError(f"analysis failed: {last}")


def _auto_ids():
    ids = set()
    try:
        for line in open(os.path.join(HERE, "log.jsonl")):
            mid = json.loads(line).get("media_id")
            if mid:
                ids.add(mid)
    except Exception:
        pass
    return ids


def _add_case(item):
    s = (item.get("analysis") or {}).get("student_success") or {}
    facts = [f for f in s.get("facts", []) if isinstance(f, str) and 5 < len(f) < 160][:6]
    if not (s.get("present") and facts):
        return False
    import guard  # noqa: F401  (keeps the same file format as guard.cases)
    path = os.path.join(HERE, "cases.json")
    cases = json.load(open(path)) if os.path.exists(path) else []
    cid = f"ig-{item['id']}"
    if any(c.get("id") == cid for c in cases):
        return False
    nums = sorted(set(re.findall(r"\d[\d,]*", " ".join(facts))))
    cases.append({"id": cid, "approved": True, "source": "instagram", "name": "", "url": item.get("permalink"),
                  "text": "; ".join(facts)[:300], "facts": facts, "numbers": nums})
    json.dump(cases, open(path, "w"), indent=1, ensure_ascii=False)
    return True


def update():
    token = os.environ.get("IG_TOKEN")
    if not token or not os.environ.get("GEMINI_API_KEY"):
        return "content_bank: IG_TOKEN / GEMINI_API_KEY missing"
    from publish_ig import whoami
    uid = whoami(token)["user_id"]
    bank = json.load(open(BANK)) if os.path.exists(BANK) else {}
    auto = _auto_ids()
    new = done = cases = 0
    for m in _media(token, uid):
        if m.get("media_type") != "VIDEO":
            continue
        it = bank.get(m["id"]) or {"id": m["id"]}
        it.update(permalink=m.get("permalink"), date=(m.get("timestamp") or "")[:10], caption=(m.get("caption") or "")[:1500],
                  origin="auto" if m["id"] in auto else "original", likes=m.get("like_count"), comments=m.get("comments_count"))
        it.update(_views(token, m["id"]))
        if "analysis" not in it and new < MAX_NEW and m.get("media_url"):
            try:
                it["analysis"] = _analyse(m["media_url"], m.get("caption")); new += 1
                cases += _add_case(it)
            except Exception as e:
                print("analysis skipped", m["id"], str(e)[:150])
        bank[m["id"]] = it; done += 1
    json.dump(bank, open(BANK, "w"), indent=0, ensure_ascii=False)
    return f"content_bank: {done} videos indexed, {new} newly analysed, {cases} new student cases"


def score(it):
    a = it.get("analysis") or {}
    v = it.get("views") or 0
    eng = (it.get("likes") or 0) + 3 * (it.get("comments") or 0) + 4 * (it.get("shares") or 0) + 3 * (it.get("saved") or 0)
    import math
    return math.log1p(v) + 0.6 * math.log1p(eng) + 0.3 * float(a.get("quality") or 5)


def pick_remix():
    """Best analysed idea not remixed in the last REMIX_COOLDOWN days (originals get a small bonus)."""
    try:
        bank = json.load(open(BANK))
    except Exception:
        return None
    today = datetime.date.today()
    ok = []
    for it in bank.values():
        a = it.get("analysis")
        if not a or a.get("pillar") == "puzzle" or not a.get("reusable_idea"):
            continue
        last = it.get("remixed")
        if last and (today - datetime.date.fromisoformat(last)).days < REMIX_COOLDOWN:
            continue
        ok.append((score(it) + (0.5 if it.get("origin") == "original" else 0), it))
    if not ok:
        return None
    return max(ok, key=lambda x: x[0])[1]


def mark_remixed(mid):
    bank = json.load(open(BANK))
    if mid in bank:
        bank[mid]["remixed"] = datetime.date.today().isoformat()
        json.dump(bank, open(BANK, "w"), indent=0, ensure_ascii=False)


if __name__ == "__main__":
    print(update())
