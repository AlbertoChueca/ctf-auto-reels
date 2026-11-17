"""Publish the reel on TikTok and YouTube Shorts through Zernio (zernio.com).

Secret:    ZERNIO_API_KEY
Variables: ZERNIO_TT_ACCOUNT / ZERNIO_YT_ACCOUNT  name (or id) of the academy's TikTok / YouTube account in Zernio.
                                                  Only needed when Zernio has several accounts of that platform.
           ZERNIO_PROFILE                         name (or id) of the Zernio profile of the academy (optional filter)
           TIKTOK=off / YOUTUBE=off               skip one platform
           TIKTOK_AI_LABEL=off                    do not mark the video as made with AI on TikTok (default: marked)

Safe by design: it never guesses. If the Zernio key sees several TikTok accounts (for example the academy's and
another project's) and none is selected, or the only one does not look like the academy's, nothing is posted there
and the run page says exactly which variable to set.

python publish_zernio.py     -> lists the connected accounts and which ones would be used (publishes nothing)
"""
import os, re, requests
import brand

API = "https://zernio.com/api/v1"
OURS = re.compile(r"talent|ctf|factory", re.I)          # what the academy's own accounts are called


def _h():
    return {"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}"}


def _check(r, what):
    if r.status_code >= 400:
        raise RuntimeError(f"Zernio {what} error {r.status_code}: {r.text[:400]}")
    try:
        return r.json() if r.content else {}
    except Exception:
        return {}


def _items(data, key):
    if isinstance(data, list):
        return data
    for k in (key, "data", "items"):
        if isinstance(data.get(k), list):
            return data[k]
    return []


def _name(a):
    return str(a.get("username") or a.get("displayName") or a.get("name") or a.get("handle") or "?")


def _id(a):
    return a.get("_id") or a.get("id")


def _profile_of(a):
    p = a.get("profileId") or a.get("profile")
    return (p.get("_id") or p.get("id"), p.get("name")) if isinstance(p, dict) else (p, None)


def accounts():
    accs = _items(_check(requests.get(f"{API}/accounts", headers=_h(), timeout=60), "accounts"), "accounts")
    want = (os.environ.get("ZERNIO_PROFILE") or "").strip().lower()
    if want:
        names = {}
        try:
            for p in _items(_check(requests.get(f"{API}/profiles", headers=_h(), timeout=60), "profiles"), "profiles"):
                names[_id(p)] = str(p.get("name") or "")
        except Exception as e:
            print("Zernio: could not read the profiles:", str(e)[:120], flush=True)
        def ok(a):
            pid, pname = _profile_of(a)
            return want in (str(pid).lower(), str(pname or names.get(pid) or "").lower())
        accs = [a for a in accs if ok(a)]
    return [a for a in accs if a.get("isActive", True) is not False]


def choose(accs, platform, wanted):
    """-> (account or None, message). Never guesses between several accounts."""
    mine = [a for a in accs if (a.get("platform") or "").lower() == platform]
    listing = ", ".join(f"@{_name(a)}" for a in mine) or "none"
    var = "ZERNIO_TT_ACCOUNT" if platform == "tiktok" else "ZERNIO_YT_ACCOUNT"
    if not mine:
        return None, f"{platform}: no account connected in Zernio"
    wanted = (wanted or "").strip().lstrip("@").lower()
    if wanted:
        hit = [a for a in mine if wanted in (str(_id(a)).lower(), _name(a).lstrip("@").lower())] or \
              [a for a in mine if wanted in _name(a).lower()]
        if len(hit) == 1:
            return hit[0], f"{platform}: @{_name(hit[0])}"
        return None, f"{platform}: the variable {var}='{wanted}' matches {len(hit)} accounts (connected: {listing})"
    ours = [a for a in mine if OURS.search(_name(a))]
    if len(ours) == 1:
        return ours[0], f"{platform}: @{_name(ours[0])}"
    return None, (f"{platform}: not posted. Connected in Zernio: {listing}. Set the variable {var} to the name of the "
                  f"academy's account (GitHub > Settings > Secrets and variables > Actions > Variables)")


def plan():
    """Which accounts would be used. -> ({platform: account}, [messages])"""
    accs = accounts()
    use, msgs = {}, []
    for platform, env, switch in (("tiktok", "ZERNIO_TT_ACCOUNT", "TIKTOK"), ("youtube", "ZERNIO_YT_ACCOUNT", "YOUTUBE")):
        if os.environ.get(switch, "on").lower() == "off":
            msgs.append(f"{platform}: off"); continue
        a, msg = choose(accs, platform, os.environ.get(env))
        msgs.append(msg)
        if a:
            use[platform] = a
    return use, msgs


def _tiktok_settings(acc_id):
    """Only what this TikTok account allows (privacy levels and interactions come from TikTok itself)."""
    st = {"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True, "allow_duet": True, "allow_stitch": True,
          "content_preview_confirmed": True, "express_consent_given": True}
    try:
        info = _check(requests.get(f"{API}/accounts/{acc_id}/tiktok/creator-info", headers=_h(), timeout=60), "creator info")
        levels = [l.get("value") for l in info.get("privacyLevels") or [] if l.get("value")]
        if levels and "PUBLIC_TO_EVERYONE" not in levels:
            st["privacy_level"] = levels[0]
            print(f"TikTok: this account cannot post publicly through the API yet; posting as {levels[0]}", flush=True)
        inter = (info.get("postingLimits") or {}).get("interactionSettings") or {}
        for k in ("allow_comment", "allow_duet", "allow_stitch"):
            if isinstance(inter.get(k), dict) and inter[k].get("enabled") is False:
                st[k] = False
        if (info.get("creator") or {}).get("canPostMore") is False:
            raise RuntimeError("TikTok says this account reached its posting limit for today")
    except RuntimeError as e:
        if "posting limit" in str(e):
            raise
        print("TikTok: creator info not available, using the defaults:", str(e)[:150], flush=True)
    return st


def _upload(video_path):
    pre = _check(requests.post(f"{API}/media/presign", headers=_h(), json={
        "filename": os.path.basename(video_path), "contentType": "video/mp4", "size": os.path.getsize(video_path)},
        timeout=60), "presign")
    with open(video_path, "rb") as f:
        up = requests.put(pre["uploadUrl"], data=f, headers={"Content-Type": "video/mp4"}, timeout=600)
    if up.status_code >= 400:
        raise RuntimeError(f"Zernio upload error {up.status_code}: {up.text[:300]}")
    return pre["publicUrl"]


def _post(body, key):
    r = requests.post(f"{API}/posts", headers={**_h(), "Idempotency-Key": key[:200]}, json=body, timeout=180)
    res = _check(r, "post")
    post = res.get("post", res) if isinstance(res, dict) else {}
    bad = [p for p in (post.get("platforms") or []) if str(p.get("status", "")).lower() in ("failed", "error")]
    if r.status_code == 207 or bad:
        raise RuntimeError(f"not published: {str((bad[0].get('errorMessage') or bad[0].get('error')) if bad else res)[:300]}")
    return post.get("_id") or post.get("id")


def crosspost(video_path, title, caption):
    """Posts the video on the academy's TikTok and YouTube. -> 'tiktok:ok,youtube:ok' (or the reason, per platform)."""
    use, msgs = plan()
    for m in msgs:
        print("Zernio ·", m, flush=True)
    if not use:
        return "; ".join(msgs)
    url = _upload(video_path)
    media = [{"type": "video", "url": url}]
    base = os.path.basename(video_path)
    out = [m for m in msgs if "not posted" in m or "no account" in m or "matches" in m]
    if "tiktok" in use:
        acc = _id(use["tiktok"])
        try:
            st = _tiktok_settings(acc)
            ai = os.environ.get("TIKTOK_AI_LABEL", "on").lower() != "off"
            body = {"content": caption[:2200], "mediaItems": media, "publishNow": True,
                    "platforms": [{"platform": "tiktok", "accountId": acc}]}
            try:
                _post(dict(body, tiktokSettings=dict(st, video_made_with_ai=True) if ai else st), f"{base}-tiktok")
            except RuntimeError as e:
                if not ai or " 400" not in str(e):
                    raise
                print("TikTok: retrying without the AI label field:", str(e)[:160], flush=True)
                _post(dict(body, tiktokSettings=st), f"{base}-tiktok-2")
            out.append("tiktok:ok")
        except Exception as e:
            out.append(f"tiktok:error {str(e)[:220]}")
    if "youtube" in use:
        try:
            link = brand.url_full(brand.CTA_URL, "shorts")
            desc = caption.replace("link on our profile.", link).replace("Link in bio.", link)
            clean = re.sub(r"[^\w\s,.'?!:\-]", "", title or "Chess parenting").strip()
            body = {"content": desc[:4900], "mediaItems": media, "publishNow": True, "tags": brand.YT_TAGS,
                    "platforms": [{"platform": "youtube", "accountId": _id(use["youtube"]), "platformSpecificData": {
                        "title": f"{clean[:88]} #shorts", "visibility": "public",
                        # addressed to parents -> not "made for kids" (keeps comments and the link in the description)
                        "madeForKids": os.environ.get("YT_MADE_FOR_KIDS", "false").lower() == "true", "categoryId": "27"}}]}
            _post(body, f"{base}-youtube")
            out.append("youtube:ok")
        except Exception as e:
            out.append(f"youtube:error {str(e)[:220]}")
    return ", ".join(out)


if __name__ == "__main__":
    for a in accounts():
        print(f"- {a.get('platform')}: @{_name(a)}  id {_id(a)}  profile {_profile_of(a)}")
    print("\n".join(plan()[1]))
