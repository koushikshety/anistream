import json
import os
from datetime import datetime, timezone

import requests
from youtube_validator import check_video

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
TARGET_COUNTRIES = ["IN"]  # Set to [] if you want all regions saved and filtered on frontend

# Section 3A: All Official Embeddable Anime & Donghua YouTube Channels
CHANNELS = [
    # --- Anime (Asia / India / Global) ---
    {"name": "Muse Asia", "id": "UCGbshtvS9t-8CW11W7TooQg", "type": "anime", "min_minutes": 15},
    {"name": "Muse India", "id": "UCz4tgANd4yy8Oe0iXCdSWfA", "type": "anime", "min_minutes": 15},
    {"name": "Ani-One Asia", "id": "UC0wNSTMWIL3qaorLx0jie6A", "type": "anime", "min_minutes": 15},
    {"name": "Crunchyroll", "id": "UC6pGDc4bFGD1_36IKv3FnYg", "type": "anime", "min_minutes": 15},
    {"name": "Crunchyroll Dubs", "id": "UCVi2lI40LetxLBKn-rtWC3A", "type": "anime", "min_minutes": 15},
    {"name": "Crunchyroll India", "id": "UC1dpwMXjjPe87utZQRrEr3Q", "type": "anime", "min_minutes": 15},
    {"name": "Anime! on TMS", "id": "UCzGf0DdUJVrsbcWL3e_tK1Q", "type": "anime", "min_minutes": 15},
    {"name": "GundamInfo", "id": "UCejtUitnpnf8Be-v5NuDSLw", "type": "anime", "min_minutes": 15},
    {"name": "VIZ Media", "id": "UCV1da9peoqEwqr45bpTJsbQ", "type": "anime", "min_minutes": 15},
    {"name": "Toei Animation", "id": "UCQYYekTKCb1y12sas08T6gQ", "type": "anime", "min_minutes": 15},

    # --- Donghua (Chinese Animation) ---
    {"name": "Made By Bilibili", "id": "UCQFyMGc6h30NMCd6HCk0ZPA", "type": "donghua", "min_minutes": 10},
    {"name": "Tencent Video - ANIMATION", "id": "UCdpiId0eJGnnIvfhpbJIM1w", "type": "donghua", "min_minutes": 10},
    {"name": "Ani-Mi Asia", "id": "UCqyqBNOAlZgJ3dQoDSCbCjQ", "type": "donghua", "min_minutes": 10},
]


def fetch_latest_upload_ids(channel_id: str, max_results: int = 50) -> list[str]:
    uploads_playlist_id = "UU" + channel_id[2:]
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return [
        item["contentDetails"]["videoId"]
        for item in resp.json().get("items", [])
        if item.get("contentDetails", {}).get("videoId")
    ]


def fetch_video_details(video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,contentDetails,status",
        "id": ",".join(video_ids[:50]),
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def is_oembed_playable(video_id: str) -> bool:
    url = "https://www.youtube.com/oembed"
    params = {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "format": "json",
    }
    resp = requests.get(url, params=params, timeout=10)
    return resp.status_code == 200


def main() -> None:
    if not YOUTUBE_API_KEY:
        raise RuntimeError("Missing YOUTUBE_API_KEY environment variable.")

    published = []
    manual_review = []

    for ch in CHANNELS:
        try:
            ids = fetch_latest_upload_ids(ch["id"], max_results=50)
            items = fetch_video_details(ids)
            print(f"[INFO] {ch['name']}: fetched {len(items)} recent uploads")
        except Exception as exc:
            print(f"[WARN] Failed channel {ch['name']}: {exc}")
            continue

        for item in items:
            vid = item["id"]
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            result = check_video(
                item,
                countries=TARGET_COUNTRIES,
                min_minutes=ch.get("min_minutes", 15),
            )
            if result is None:
                continue

            if not is_oembed_playable(vid):
                print(f"[HIDDEN] oEmbed failed for {vid}: {title}")
                continue

            rr = item.get("contentDetails", {}).get("regionRestriction", {})
            entry = {
                "video_id": vid,
                "channel": ch["name"],
                "category": ch["type"],
                "title": title,
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "episode": result["episode"],
                "last_episode": result["last_episode"],
                "allowed_countries": rr.get("allowed", []),
                "blocked_countries": rr.get("blocked", []),
                "embed_url": f"https://www.youtube.com/embed/{vid}",
                "watch_url": f"https://www.youtube.com/watch?v={vid}",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

            if result["episode"] is None:
                manual_review.append(entry)
            else:
                published.append(entry)

    with open("episodes.json", "w", encoding="utf-8") as f:
        json.dump(published, f, ensure_ascii=False, indent=2)

    with open("review_queue.json", "w", encoding="utf-8") as f:
        json.dump(manual_review, f, ensure_ascii=False, indent=2)

    print(f"Done: {len(published)} valid episodes, {len(manual_review)} sent to review.")


if __name__ == "__main__":
    main()
