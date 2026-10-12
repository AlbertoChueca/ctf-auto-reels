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

WORDNUM = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
           "seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand")
_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                       "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}


def to_int(s):
    """'1,800+' -> 1800, 'eleven hundred' -> 1100, 'twenty three hundred' -> 2300, 'forty-four' -> 44."""
    s = str(s).lower().strip().rstrip(".,+")
    d = re.sub(r"[,+]", "", s)
    if re.fullmatch(r"\d+(\.\d+)?", d):
        return int(float(d))
    total = cur = 0; seen = False
    for w in re.split(r"[\s-]+", s):
        if w in _UNITS:
            cur += _UNITS[w]; seen = True
        elif w in _TENS:
            cur += _TENS[w]; seen = True
        elif w == "hundred":
            cur = (cur or 1) * 100; seen = True
        elif w == "thousand":
            total += (cur or 1) * 1000; cur = 0; seen = True
        elif w in ("and", "a"):
            continue
        else:
            return None
    return total + cur if seen else None


def allowed_numbers():
    """Every number we may state about results: approved claims, approved cases, and the gains between a case's
    'from X to Y' figures (1100 -> 1900 makes '800 points' a true statement)."""
    nums = {1}
    blobs = []
    for c in approved():
        nums |= {n for n in (to_int(x) for x in c.get("numbers", [])) if n is not None}
        blobs.append(c.get("text", ""))
    for c in cases():
        nums |= {n for n in (to_int(x) for x in c.get("numbers", [])) if n is not None}
        blobs.append(c.get("text", "") + " " + " ".join(c.get("facts", [])))
    for b in blobs:
        nums |= {to_int(x) for x in re.findall(r"\d[\d,]*", b)} - {None}
        for a, z in re.findall(r"from (\d[\d,]*)\+? to \+?(\d[\d,]*)", b, flags=re.I):
            a, z = to_int(a), to_int(z)
            if a and z and z > a:
                nums.add(z - a)
    return nums
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
    """Returns (ok, offending). Any number tied to results/students must be an approved number (digits or words)."""
    allowed = allowed_numbers()
    bad = []
    text = re.sub(r"\b(one|two|three) of (our|the|my|his|her|their|these|those)\b", " ", text or "", flags=re.I)
    # references to the book are not result claims: "Key 44", "Key forty-four", "Square 65", "65 keys"
    text = re.sub(rf"\bkeys?\s+(\d+|(?:{WORDNUM})(?:[\s-](?:{WORDNUM}))*)\b", " ", text, flags=re.I)
    text = re.sub(r"\bsquare\s+65\b|\b65\s+keys\b|\bof\s+65\b", " ", text, flags=re.I)
    for m in CLAIM_RE.finditer(text):
        n = to_int(m.group(1))
        if n is None or n not in allowed:
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


def anchored(sc):
    """Competitor test, deterministic part: does the script carry at least one of OUR anchors?"""
    import brand
    text = " ".join(f"{s.get('headline', '')} {s.get('narration', '')} {json.dumps(s.get('params', {}))}"
                    for s in sc.get("scenes", [])).lower()
    text += " " + (sc.get("caption_hook", "") + " " + sc.get("caption_body", "")).lower()
    hits = [t.strip() for t in brand.ANCHOR_TERMS if t in text]
    if any(s.get("block") in ("key_card", "before_after", "success_timeline") for s in sc.get("scenes", [])):
        hits.append("signature block")
    return hits
