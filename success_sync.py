"""Weekly: read the student pages on chesstalentsfactory.com and keep cases.json up to date.

Only what the academy itself publishes on its website is used (approved automatically, source "website").
Entries added by hand or from Instagram are never touched. Set "approved": false on any case to exclude it.
"""
import html, json, os, re, requests

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://chesstalentsfactory.com"
UA = {"User-Agent": "Mozilla/5.0 (ctf-auto-reels)"}


def _text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", h, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))


def student_links():
    h = requests.get(f"{BASE}/our-students/", headers=UA, timeout=30).text
    links = sorted(set(re.findall(r'href="(https://chesstalentsfactory\.com/our-students/[a-z0-9-]+/)"', h)))
    return [l for l in links if l.rstrip("/") != f"{BASE}/our-students"]


def parse(url):
    h = requests.get(url, headers=UA, timeout=30).text
    name = html.unescape(re.search(r"<title>(.*?)[-–|]", h, re.S).group(1)).replace("\xa0", " ").strip()
    desc = re.search(r'<meta name="description" content="([^"]*)"', h)
    lines = [re.sub(r"\s+", " ", l).strip() for l in _text(h).split("\n")]
    lines = [l for l in lines if l]
    facts, i = [], 0
    for k, l in enumerate(lines):                       # timeline: a year line followed by the achievement
        if re.fullmatch(r"(19|20)\d\d(,\s*(19|20)\d\d)*( \(Age \d+\))?", l) and k + 1 < len(lines):
            nxt = lines[k + 1]
            if 8 < len(nxt) < 140 and "Privacy" not in nxt:
                facts.append(f"{l}: {nxt}")
    headline = html.unescape(desc.group(1)).strip() if desc else ""
    if not headline and not facts:
        return None
    first = name.split()[0].title()
    nums = sorted(set(re.findall(r"\d[\d,]*", headline + " " + " ".join(facts))))
    return {"id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "approved": True, "source": "website",
            "name": first, "url": url, "text": headline[:300], "facts": (facts[:8] or [headline])[:8], "numbers": nums}


def main():
    path = os.path.join(HERE, "cases.json")
    cases = json.load(open(path)) if os.path.exists(path) else []
    by_id = {c["id"]: c for c in cases}
    n = 0
    for url in student_links():
        try:
            c = parse(url)
        except Exception as e:
            print("skip", url, e); continue
        if not c:
            continue
        old = by_id.get(c["id"]) or next((x for x in cases if x.get("url") == url), None)
        if old and old.get("source") != "website":
            continue                                    # hand-edited entry: never overwrite
        if old:
            c["approved"] = old.get("approved", True)   # keep the owner's decision
            cases[cases.index(old)] = c
        else:
            cases.append(c)
        n += 1
    json.dump(cases, open(path, "w"), indent=1, ensure_ascii=False)
    print(f"success_sync: {n} student pages read, {len([c for c in cases if c.get('approved')])} approved cases")


if __name__ == "__main__":
    main()
