"""Publish the same reel as a Facebook Reel on the academy's Page (Graph API, video_reels endpoint).

Uses the same IG_TOKEN (a Page token). Extra permission needed: pages_manage_posts (+ pages_read_engagement,
pages_show_list, which the Instagram setup already has). Never blocks the Instagram post.
"""
import os, time, requests
from publish_ig import GRAPH, API, _check, whoami


def publish_fb_reel(video_path, caption, token=None):
    token = token or os.environ["IG_TOKEN"]
    page_id = os.environ.get("FB_PAGE_ID") or whoami(token)["page_id"]
    start = _check(requests.post(f"{GRAPH}/{page_id}/video_reels",
                                 data={"upload_phase": "start", "access_token": token}, timeout=60))
    vid = start["video_id"]
    url = start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{API}/{vid}"
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(url, data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    _check(r)
    _check(requests.post(f"{GRAPH}/{page_id}/video_reels", data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": caption[:2200], "access_token": token}, timeout=60))
    status = None
    for _ in range(30):                                   # wait until Facebook finishes processing (max ~5 min)
        time.sleep(10)
        st = _check(requests.get(f"{GRAPH}/{vid}", params={"fields": "status", "access_token": token}, timeout=30))
        status = st.get("status", {})
        phase = (status.get("publishing_phase") or {}).get("status")
        if status.get("video_status") in ("ready", "published") or phase == "complete":
            break
        if status.get("video_status") == "error":
            raise RuntimeError(f"Facebook processing error: {status}")
    print("Facebook Reel:", vid, status and status.get("video_status"))
    return f"ok {vid}"
