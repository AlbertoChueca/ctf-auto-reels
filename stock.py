"""Real stock footage for the reels (free for commercial use, no attribution required): Pexels, then Pixabay.

get_clip(query, seconds, grade) -> local mp4, already vertical 1080x1920 @25fps, colour-graded, no audio.
- Prefers portrait HD files; landscape files are centre-cropped.
- Never reuses a clip within REUSE_DAYS (stock_used.json), so the feed keeps looking fresh.
- Tries the query, then simpler versions of it, then safe generic fallbacks.
Env: PIXABAY_API_KEY and/or PEXELS_API_KEY (both free). Also stock_library/ (your own clips, named by content).
STOCK_DIR=/some/folder (tests / offline): use local mp4 files from that folder instead of the APIs.
"""
import datetime, glob, hashlib, json, os, random, re, subprocess
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "out", "stock")
USED = os.path.join(HERE, "stock_used.json")
REUSE_DAYS = int(os.environ.get("STOCK_REUSE_DAYS", "60"))
W, H, FPS = 1080, 1920, 25

GRADES = {   # ffmpeg colour looks (subtle, premium); vignette added to all
    "warm": "eq=contrast=1.06:saturation=1.06:gamma=0.98,colorbalance=rs=.05:gs=.015:bs=-.05:rh=.02:bh=-.03",
    "cool": "eq=contrast=1.07:saturation=0.95,colorbalance=rs=-.03:gs=.0:bs=.04:rh=-.01:bh=.02",
    "punch": "eq=contrast=1.14:saturation=1.12:gamma=0.96",
    "soft": "eq=contrast=0.98:saturation=0.96:gamma=1.03,colorbalance=rs=.03:bs=-.02",
    "mono": "eq=saturation=0.25:contrast=1.12:gamma=0.97",
}
FALLBACKS = ["child playing chess", "chess pieces close up", "kid studying at desk", "family at home evening",
             "chess board hands", "child thinking", "parent and child talking", "school classroom children",
             "tournament hall people", "kid using laptop"]


class StockError(RuntimeError):
    pass


def _used():
    try:
        return json.load(open(USED))
    except Exception:
        return {}


def _mark(uid):
    u = _used(); u[uid] = str(datetime.date.today())
    if len(u) > 3000:
        u = dict(sorted(u.items(), key=lambda kv: kv[1])[-3000:])
    json.dump(u, open(USED, "w"), indent=0)


def _fresh(uid):
    d = _used().get(uid)
    return not d or (datetime.date.today() - datetime.date.fromisoformat(d)).days >= REUSE_DAYS


def _pexels(query, min_s):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    out = []
    for orient in ("portrait", None):
        params = {"query": query, "per_page": 30, "size": "medium"}
        if orient:
            params["orientation"] = orient
        try:
            r = requests.get("https://api.pexels.com/videos/search", params=params, headers={"Authorization": key}, timeout=30)
            vids = r.json().get("videos", []) if r.status_code == 200 else []
        except Exception:
            vids = []
        for v in vids:
            if (v.get("duration") or 0) < min_s:
                continue
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
            portrait = [f for f in files if f["height"] >= f["width"] and f["height"] >= 1280]
            pool = portrait or [f for f in files if f["height"] >= 720]
            if not pool:
                continue
            f = min(pool, key=lambda f: abs(f["height"] - 1920))
            out.append({"uid": f"pexels-{v['id']}", "url": f["link"], "w": f["width"], "h": f["height"],
                        "dur": v.get("duration"), "portrait": f["height"] >= f["width"], "thumb": v.get("image"),
                        "tags": " ".join(re.findall(r"[a-z]+", (v.get("url") or "").lower().split("/video/")[-1])),
                        "pop": 0})
        if len([o for o in out if o["portrait"]]) >= 6:
            break
    return out


def _pixabay(query, min_s):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    try:
        r = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": query, "per_page": 50,
                                                                   "safesearch": "true", "video_type": "film"},
                         timeout=30)
        hits = r.json().get("hits", []) if r.status_code == 200 else []
    except Exception:
        hits = []
    out = []
    for h in hits:
        if (h.get("duration") or 0) < min_s:
            continue
        v = (h.get("videos") or {})
        f = v.get("large") if (v.get("large") or {}).get("url") else v.get("medium")
        if not f or not f.get("url") or h.get("type", "film") != "film":
            continue                                   # no animation / CGI
        thumb = next((x.get("thumbnail") for x in (v.get("small"), v.get("medium"), v.get("tiny"), f)
                      if x and x.get("thumbnail")), None)
        out.append({"uid": f"pixabay-{h['id']}", "url": f["url"], "w": f.get("width", 1920), "h": f.get("height", 1080),
                    "dur": h.get("duration"), "portrait": f.get("height", 0) >= f.get("width", 1), "thumb": thumb,
                    "tags": (h.get("tags") or "").lower(), "pop": (h.get("downloads") or 0) + 20 * (h.get("likes") or 0)})
    return out


LIBRARY = os.path.join(HERE, "stock_library")      # your own clips: name them by content, e.g. "kid-chess-home-1.mp4"


def _local(query, min_s):
    d = os.environ.get("STOCK_DIR")
    if not d:
        return []
    files = sorted(glob.glob(os.path.join(d, "*.mp4")))
    return [{"uid": "local-" + os.path.basename(p), "url": p, "w": W, "h": H, "dur": 30, "portrait": True} for p in files]


def _library(query, min_s):
    """Clips in stock_library/ whose file name shares words with the query (best matches first)."""
    words = set(re.findall(r"[a-z]+", query.lower())) - {"a", "an", "the", "of", "with", "and", "at", "in", "on"}
    out = []
    for p in glob.glob(os.path.join(LIBRARY, "**", "*.mp4"), recursive=True):
        name = set(re.findall(r"[a-z]+", os.path.relpath(p, LIBRARY).lower()))
        hit = len(words & name)
        if hit:
            out.append((hit, {"uid": "lib-" + os.path.relpath(p, LIBRARY), "url": p, "w": W, "h": H, "dur": 30,
                              "portrait": True}))
    return [c for _, c in sorted(out, key=lambda x: -x[0])]


STOP = {"a", "an", "the", "of", "with", "and", "at", "in", "on", "to", "for", "close", "up", "shot", "video"}


OFF_TOPIC = {"dog", "dogs", "puppy", "cat", "cats", "kitten", "pet", "pets", "animal", "animals", "bird", "horse",
             "food", "eating", "bowl", "cooking", "snow", "winter", "christmas", "xmas", "santa", "baby", "babies",
             "toddler", "infant", "newborn", "wedding", "bride", "sky", "stars", "starry", "space", "galaxy", "night",
             "animation", "cartoon", "3d", "cgi", "render", "green", "screen", "chroma", "abstract", "background",
             "particles", "fractal", "loop", "beach", "bikini", "party", "beer", "wine", "alcohol", "smoking",
             "gun", "war", "halloween", "zombie", "fire", "explosion", "drone", "aerial", "city", "traffic"}


def on_topic(c):
    """False for clips whose tags show they are about something unrelated (pets, food, sky, babies, CGI...)."""
    tags = set(re.findall(r"[a-z0-9]+", (c.get("tags") or "").lower()))
    return not (tags & OFF_TOPIC)


def _keywords(q):
    w = set(re.findall(r"[a-z]+", q.lower())) - STOP
    syn = {"kid": "child", "kids": "children", "son": "boy", "daughter": "girl", "mom": "mother", "dad": "father"}
    return w | {syn[x] for x in w if x in syn}


def _simplify(q):
    words = [w for w in re.findall(r"[a-zA-Z]+", q.lower()) if w not in ("a", "an", "the", "of", "with", "and", "at", "in")]
    out = []
    if len(words) > 3:
        out.append(" ".join(words[:3]))
    if len(words) > 2:
        out.append(" ".join(words[-2:]))
    return out


def candidates(query, min_s=5, seed=None, fresh_only=True):
    rng = random.Random(seed or query)
    for q in [query] + _simplify(query):
        found = _local(q, min_s) or (_pexels(q, min_s) + _pixabay(q, min_s) + _library(q, min_s))
        fresh = [c for c in found if (not fresh_only or c["uid"].startswith("local-") or _fresh(c["uid"])) and on_topic(c)]
        if fresh:
            want = _keywords(query)
            def score(c):
                tags = set(re.findall(r"[a-z]+", c.get("tags") or ""))
                return (len(want & tags) * 3 + (1 if c.get("portrait") else 0)
                        + min(2.0, (c.get("pop") or 0) / 20000.0) + rng.random() * 0.8)
            pool = sorted(fresh, key=score, reverse=True)[:12]
            return pool, q
    return [], None


def _download(c):
    os.makedirs(CACHE, exist_ok=True)
    if os.path.exists(c["url"]):
        return c["url"]
    path = os.path.join(CACHE, hashlib.md5(c["url"].encode()).hexdigest()[:16] + "_raw.mp4")
    if not os.path.exists(path):
        with requests.get(c["url"], stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for ch in r.iter_content(1 << 20):
                    f.write(ch)
    return path


def _prepare(raw, seconds, grade, out):
    """Vertical 1080x1920 crop (+6% margin for the slow camera move), 25 fps, graded, vignette, no audio."""
    dur = _probe(raw)
    start = max(0.0, min(dur - seconds - 0.2, dur * 0.15)) if dur > seconds + 1 else 0.0
    bw, bh = int(W * 1.06) // 2 * 2, int(H * 1.06) // 2 * 2
    vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},fps={FPS},"
          f"{GRADES.get(grade, GRADES['warm'])},vignette=PI/5")
    loop = ["-stream_loop", "-1"] if dur and dur < seconds else []
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + loop + ["-ss", f"{start:.2f}", "-i", raw, "-t", f"{seconds:.2f}",
                    "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "17", "-pix_fmt", "yuv420p", out],
                   check=True)
    return out


def _probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def relevance(c, query):
    """How many of the query's key words appear in the clip's tags (local/library clips count as relevant)."""
    if c["uid"].startswith(("local-", "lib-")):
        return 1
    return len(_keywords(query) & set(re.findall(r"[a-z]+", c.get("tags") or "")))


def search(query, seconds, seed=None, exclude=(), n=6):
    """Up to n candidate clips for a query (fresh first; generic fallbacks only if the query finds nothing)."""
    min_s = max(3, int(seconds * 0.6))
    for q, fresh_only in [(query, True), (query, False)]:
        cands, used_q = candidates(q, min_s, seed, fresh_only)
        cands = [dict(c, query=used_q) for c in cands if c["uid"] not in exclude]
        if cands:
            return cands[:n]
    return []


def thumbnail(c):
    """Small preview image of a candidate (PIL), or None."""
    from PIL import Image
    import io
    try:
        if c.get("thumb"):
            r = requests.get(c["thumb"], timeout=20); r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "1.5", "-i", c["url"], "-frames:v", "1", "-vf",
                            "scale=480:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=60)
        return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None
    except Exception:
        return None


def fetch(c, seconds, grade="warm"):
    """Download + prepare one chosen candidate -> local path."""
    raw = _download(c)
    out = os.path.join(CACHE, f"{c['uid']}_{grade}_{int(seconds * 10)}.mp4")
    if not os.path.exists(out):
        _prepare(raw, seconds + 0.5, grade, out)
    _mark(c["uid"])
    return out


def get_clip(query, seconds, grade="warm", seed=None, exclude=()):
    """Returns (path_to_prepared_clip, info). Raises StockError if nothing at all can be found."""
    tried = []
    for q, fresh_only in [(x, True) for x in [query] + FALLBACKS] + [(query, False), (FALLBACKS[0], False)]:
        cands, used_q = candidates(q, max(3, int(seconds * 0.6)), seed, fresh_only)
        cands = [c for c in cands if c["uid"] not in exclude]
        for c in cands[:3]:
            try:
                raw = _download(c)
                out = os.path.join(CACHE, f"{c['uid']}_{grade}_{int(seconds * 10)}.mp4")
                if not os.path.exists(out):
                    _prepare(raw, seconds + 0.5, grade, out)
                _mark(c["uid"])
                return out, {"uid": c["uid"], "query": used_q, "asked": query}
            except Exception as e:
                tried.append(f"{c['uid']}: {str(e)[:80]}")
        if q == query and not cands:
            print(f"stock: nothing fresh for {query!r}, trying fallbacks", flush=True)
    raise StockError(f"no stock footage available ({'; '.join(tried[-3:]) or 'no API key / no results'})")


def available():
    return bool(os.environ.get("PEXELS_API_KEY") or os.environ.get("PIXABAY_API_KEY") or os.environ.get("STOCK_DIR")
                or len(glob.glob(os.path.join(LIBRARY, "**", "*.mp4"), recursive=True)) >= 12)
