"""Safety net for publishing without human review.

- claims: numeric claims in AI-written text must come from claims.json / cases.json (approved by the owner).
- qc(): hard technical checks on the final video (duration, real audio, video stream).
- pause / health: automatic brake. If recent reels collapse in views vs the 14-day baseline, or the run fails
  twice in a row, publishing pauses (paused.json) and the workflow fails so GitHub emails the owner.
"""
import datetime, json, os, re, statistics, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PAUSE = os.path.join(HERE, "paused.json")
FAILS = os.path.join(HERE, "failures.json")

WORDNUM = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|"
           "sixty|seventy|eighty|ninety|hundred|thousand")
CLAIM_RE = re.compile(rf"\b((?:\d[\d,.]*|(?:{WORDNUM})(?:[\s-](?:{WORDNUM}))*))\s*(?:%|percent|\+)?\s*"
                      r"(?:\w+\s){0,2}?(points?|elo|rating|percent|%|students?|kids|children|families|titles?|"
                      r"grandmasters?|masters?|champions?|wins|medals?)\b", re.I)


def approved():
    """List of approved claims (dicts with text and numbers)."""
    out = []
    try:
        out += [c for c in json.load(open(os.path.join(HERE, "claims.json"))) if c.get("approved")]
    except Exception:
        pass
    return out


def approved_text():
    a = approved()
    if not a:
        return "APPROVED CLAIMS: none -> do not state any number about results, students, titles or ratings gained."
    return "APPROVED CLAIMS (the ONLY result statements allowed, use them exactly):\n" + "\n".join(f"- {c['text']}" for c in a)


def cases():
    """Approved real student cases (website, the account's own reels, or added by hand)."""
    try:
        return [c for c in json.load(open(os.path.join(HERE, "cases.json"))) if c.get("approved")]
    except Exception:
        return []


def has(claim_id):
    return any(c.get("id") == claim_id for c in approved())


def claims_ok(text):
    """Returns (ok, offending). Any number tied to results/students must be an approved number."""
    allowed = set()
    for c in approved():
        allowed |= {str(n).lower() for n in c.get("numbers", [])}
    for c in cases():
        allowed |= set(re.findall(r"\d[\d,.]*", c.get("text", "") + " " + " ".join(c.get("facts", []))))
        allowed |= {str(n).lower() for n in c.get("numbers", [])}
    bad = []
    text = re.sub(r"\b(one|two|three) of (our|the|my|his|her|their|these|those)\b", " ", text or "", flags=re.I)
    for m in CLAIM_RE.finditer(text):
        num = m.group(1).lower().strip()
        if num not in allowed and num.replace(",", "") not in allowed:
            bad.append(m.group(0))
    return (not bad), bad


def qc(path, min_s=15, max_s=90):
    """Hard checks on the rendered file. Raises RuntimeError with the reason."""
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", path], capture_output=True, text=True)
    info = json.loads(p.stdout or "{}")
    dur = float(info.get("format", {}).get("duration", 0))
    kinds = {s.get("codec_type") for s in info.get("streams", [])}
    if "video" not in kinds or "audio" not in kinds:
        raise RuntimeError(f"qc: missing stream ({kinds})")
    if not (min_s <= dur <= max_s):
        raise RuntimeError(f"qc: duration {dur:.1f}s out of range")
    v = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", v)
    if not m or float(m.group(1)) < -40:
        raise RuntimeError(f"qc: audio too quiet or missing ({m and m.group(1)} dB)")
    return {"duration": round(dur, 1), "mean_volume_db": float(m.group(1))}


# ---------------------------------------------------------------- automatic brake
def paused():
    if os.path.exists(PAUSE):
        try:
            return json.load(open(PAUSE)).get("reason", "paused")
        except Exception:
            return "paused"
    return None


def pause(reason):
    json.dump({"reason": reason, "since": datetime.datetime.utcnow().isoformat()}, open(PAUSE, "w"), indent=1)


def record_run(ok, err=""):
    """Counts consecutive failed runs. Returns the count."""
    f = json.load(open(FAILS)) if os.path.exists(FAILS) else {"consecutive": 0}
    f["consecutive"] = 0 if ok else f.get("consecutive", 0) + 1
    if not ok:
        f["last_error"] = err[:500]
    json.dump(f, open(FAILS, "w"), indent=1)
    return f["consecutive"]


def health(drop=0.4, min_reels=20):
    """Views of the last 6 measured reels vs median of the 14 days before. Returns a reason string if the brake
    should engage, else None. Needs enough history (min_reels) to avoid false alarms at the start."""
    try:
        perf = json.load(open(os.path.join(HERE, "performance.json")))
    except Exception:
        return None
    rows = sorted((v for v in perf.values() if v.get("views") and v.get("date")), key=lambda v: v["date"])
    if len(rows) < min_reels:
        return None
    recent, base = rows[-6:], rows[-26:-6]
    med = statistics.median(r["views"] for r in base)
    now = statistics.mean(r["views"] for r in recent)
    if med > 0 and now < drop * med:
        return f"views of the last 6 reels ({now:.0f}) are under {int(drop * 100)}% of the 14-day median ({med:.0f})"
    return None
