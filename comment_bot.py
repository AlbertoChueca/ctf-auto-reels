"""Keyword bot: answers ONLY comments that contain the keyword (default PLAN). Everything else is left for the owner.

Runs every 2 hours from GitHub Actions. Uses only the official Instagram API on our own posts.
- A keyword comment gets a private reply (DM) with the link to the home page (free video + form), then a short
  public reply. If the DM cannot be sent, the public reply points to the link in bio instead of saying "sent".
- One DM per person per week at most (no spam).
- Remembers handled comments in handled_comments.json.
Env: IG_TOKEN. Optional: BOT_DRY_RUN=true (print only), HOME_URL (default chesstalentsfactory.com).
"""
import datetime, json, os, random, re, requests
import brand
from publish_ig import GRAPH, _check, whoami

TOKEN = os.environ.get("IG_TOKEN", "")
DRY = os.environ.get("BOT_DRY_RUN") == "true"
KW = re.compile(rf"(^|\W){re.escape(brand.KEYWORD)}(\W|$)", re.I)
HANDLED = "handled_comments.json"
HOME = brand.url_full((os.environ.get("HOME_URL") or "chesstalentsfactory.com").rstrip("/") + "/", "dm")

DM_KEYWORD = "Fill out the form of the video here 👉 " + HOME
PUBLIC_SENT = ["Sent! 📩 Check your DMs", "Done! Check your DMs 📩", "Just sent it to your inbox 📩"]
PUBLIC_ALREADY = ["It's already in your DMs 📩", "Check your DMs, we sent it to you 📩"]
PUBLIC_NO_DM = ["Thanks! 🙌 You'll find the free video and the form at the link in our bio"]


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def handle(c, uid, handled, now):
    """Processes one comment. Returns (public_sent, dm_sent). Non-keyword comments are ignored."""
    if not KW.search(c.get("text", "")):
        return 0, 0                                   # not the keyword: no reply, the owner answers if needed
    user = c.get("username", "")
    last_dm = handled["dm"].get(user)
    can_dm = not last_dm or (now - datetime.datetime.fromisoformat(last_dm)).days >= 7
    print(f"keyword comment {c['id']} -> dm={can_dm}")
    if DRY:
        return 0, 0
    dm_ok = False
    if can_dm:
        try:
            _check(requests.post(f"{GRAPH}/{uid}/messages", json={
                "recipient": {"comment_id": c["id"]}, "message": {"text": DM_KEYWORD}},
                headers={"Authorization": f"Bearer {TOKEN}"}))
            handled["dm"][user] = now.isoformat(); dm_ok = True
            handled["kw_dms"] = handled.get("kw_dms", 0) + 1
        except Exception as e:
            print("  private reply failed (check the instagram_manage_messages permission):", str(e)[:200])
    pub = random.choice(PUBLIC_SENT if dm_ok else PUBLIC_ALREADY if not can_dm else PUBLIC_NO_DM)
    try:
        _check(requests.post(f"{GRAPH}/{c['id']}/replies", data={"message": pub, "access_token": TOKEN}))
        return 1, int(dm_ok)
    except Exception as e:
        print("  public reply failed:", str(e)[:200])
        return 0, int(dm_ok)


def main():
    me = whoami(TOKEN); uid = me["user_id"]; myname = me["username"]
    handled = load(HANDLED, {"comments": [], "dm": {}})
    done = set(handled["comments"])
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
            p, d = handle(c, uid, handled, now)
            sent_pub += p; sent_dm += d
            done.add(c["id"])
    handled["comments"] = sorted(done)[-5000:]
    if not DRY:
        json.dump(handled, open(HANDLED, "w"), indent=0)
    print(f"Public replies: {sent_pub}, DMs: {sent_dm} (keyword DMs total: {handled.get('kw_dms', 0)})")


if __name__ == "__main__":
    main()
