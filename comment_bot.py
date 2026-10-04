"""Answer new comments on recent reels with a short public reply (optional private DM with the academy link).

Runs every hour from GitHub Actions. Uses only the official Instagram API on our own posts.
- Checks the correct first move (from log.jsonl) and congratulates people who got it.
- One DM per person per week at most (no spam), public replies are varied.
- Remembers handled comments in handled_comments.json.
Env: IG_TOKEN. Optional: BOT_DRY_RUN=true (print only).
"""
import datetime, json, os, random, re, requests
import brand
from publish_ig import GRAPH, _check, whoami

TOKEN = os.environ["IG_TOKEN"]
DRY = os.environ.get("BOT_DRY_RUN") == "true"
SEND_DMS = os.environ.get("BOT_SEND_DMS") == "true"   # DMs to every commenter: off (public replies only)
KEYWORD_DMS = os.environ.get("KEYWORD_DMS", "true") == "true"   # DM only to people who comment the keyword (opt-in)
KW = re.compile(rf"(^|\W){re.escape(brand.KEYWORD)}(\W|$)", re.I)
HANDLED = "handled_comments.json"
LINK = brand.url_full(brand.CTA_URL, "dm")

PUBLIC_CORRECT = [
    "Correct! {move} is the move 🎯 Great calculation!",
    "Spot on! {move} 💥 That's how strong juniors think",
    "Yes! {move} wins 👏 Well calculated",
    "Exactly, {move}! 🔥 Checks and captures first, always",
    "That's it! {move} ♟️ Tell your coach you found it",
    "Sharp eyes! {move} is the one 👀",
    "Nailed it! {move} 🎯 New challenge tomorrow",
    "Excellent! {move} is correct 💪 Parents: free training video in our bio",
]
PUBLIC_OTHER = [
    "Thanks for playing! ♟️ The full solution is at the end of the video",
    "Good try! Watch till the end for the answer 👀",
    "Love it! ♟️ New challenge every day",
    "Thanks for the comment! 🔥 Check every check and capture first",
    "Great to see you here! ♟️ Parents: our free training video is in the bio",
    "Keep calculating! 💪 Another one tomorrow",
]
PUBLIC_KEYWORD = [
    "Sent! 📩 Check your DMs",
    "Done! The free video is in your DMs 📩",
    "Just sent it to your inbox 📩",
    "Check your messages, it's there 📩",
]
DM_KEYWORD = ("Hi! Here's our free training video for parents: how kids gain rating points faster with the right "
              "structure 👉 " + LINK + "\nIf you'd like a plan for your child, you can book a call with our coaches "
              "from that page.")
DM_CORRECT = ("Great job finding {move}! 🎯 If you're a parent and want to see how kids gain rating points fast with "
              "the right training, here's our free video: " + LINK)
DM_OTHER = ("Thanks for playing! ♟️ If you're a parent, here's our free video on how kids improve their rating "
            "faster with structured training: " + LINK)


def norm(s):
    return re.sub(r"[x+#!?\s=.]", "", s).lower()


def got_it(text, first_move):
    """True when the comment contains the first solution move (SAN, ignoring x/+/#)."""
    if not first_move:
        return False
    target = norm(first_move)
    tokens = re.findall(r"[KQRBNkqrbn]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?", text)
    return any(norm(t) == target for t in tokens) and len(target) >= 2


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def main():
    me = whoami(TOKEN); uid = me["user_id"]; myname = me["username"]
    handled = load(HANDLED, {"comments": [], "dm": {}})
    done = set(handled["comments"])
    solutions = {}
    if os.path.exists("log.jsonl"):
        for line in open("log.jsonl"):
            e = json.loads(line)
            if e.get("media_id") and e.get("sans"):
                solutions[e["media_id"]] = e["sans"][0]

    now = datetime.datetime.now(datetime.timezone.utc)
    week_ago = now - datetime.timedelta(days=7)
    media = _check(requests.get(f"{GRAPH}/{uid}/media", params={
        "fields": "id,timestamp,media_product_type", "limit": 30, "access_token": TOKEN}))["data"]
    sent_pub = sent_dm = 0
    for m in media:
        ts = datetime.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        if ts < week_ago:          # private replies only allowed within 7 days
            continue
        comments = _check(requests.get(f"{GRAPH}/{m['id']}/comments", params={
            "fields": "id,text,username,timestamp", "limit": 50, "access_token": TOKEN})).get("data", [])
        for c in comments:
            if c["id"] in done or c.get("username") == myname:
                continue
            user = c.get("username", "")
            move = solutions.get(m["id"])
            ok = got_it(c.get("text", ""), move)
            kw = bool(KW.search(c.get("text", "")))
            pub = random.choice(PUBLIC_KEYWORD if kw else PUBLIC_CORRECT if ok else PUBLIC_OTHER).format(move=move)
            last_dm = handled["dm"].get(user)
            can_dm = not last_dm or (now - datetime.datetime.fromisoformat(last_dm)).days >= 7
            dm = DM_KEYWORD if kw else (DM_CORRECT if ok else DM_OTHER).format(move=move)
            want_dm = (kw and KEYWORD_DMS) or SEND_DMS
            print(f"@{user}: {c.get('text','')[:80]!r} -> keyword={kw} correct={ok} dm={can_dm and want_dm}")
            if not DRY:
                try:
                    _check(requests.post(f"{GRAPH}/{c['id']}/replies", data={"message": pub, "access_token": TOKEN}))
                    sent_pub += 1
                except Exception as e:
                    print("  public reply failed:", e)
                if can_dm and want_dm:
                    try:
                        _check(requests.post(f"{GRAPH}/{uid}/messages", json={
                            "recipient": {"comment_id": c["id"]}, "message": {"text": dm}},
                            headers={"Authorization": f"Bearer {TOKEN}"}))
                        handled["dm"][user] = now.isoformat(); sent_dm += 1
                        handled["kw_dms"] = handled.get("kw_dms", 0) + (1 if kw else 0)
                    except Exception as e:
                        print("  private reply failed:", e)
            done.add(c["id"])
    handled["comments"] = sorted(done)[-5000:]
    if not DRY:
        json.dump(handled, open(HANDLED, "w"), indent=0)
    print(f"Public replies: {sent_pub}, DMs: {sent_dm} (keyword DMs total: {handled.get('kw_dms', 0)})")


if __name__ == "__main__":
    main()
