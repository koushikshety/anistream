import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from youtube_validator import check_video

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
TARGET_COUNTRIES = ["IN"]  # Change to countries you serve, e.g. ["IN"]

# Official licensed channels from Section 3A (verify/add exact UC... IDs)
CHANNELS = [
    {"name": "Muse Asia", "id": "UCGbshtvS9t-8CW11W7TooQg", "min_minutes": 15},
    {"name": "Muse India", "id": "UCz4tgANd4yy8Oe0iXCdSWfA", "min_minutes": 15},
    {"name": "Ani-One Asia", "id": "UC0wNSTMWIL3qaorLx0jie6A", "min_minutes": 15},
]


def fetch_rss_video_ids(channel_id: str) -> list[str]:
    url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    ns = {"yt": "http://www.youtube.com/xml/schemas/2015"}
    return [el.text for el in root.findall(".//yt:videoId", ns) if el.text]


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
            ids = fetch_rss_video_ids(ch["id"])
            items = fetch_video_details(ids)
        except Exception as exc:
            print(f"[WARN] Failed channel {ch['name']}: {exc}")
            continue

        for item in items:
            vid = item["id"]
            title = item.get("snippet", {}).get("title", "")
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

            entry = {
                "video_id": vid,
                "channel": ch["name"],
                "title": title,
                "episode": result["episode"],
                "last_episode": result["last_episode"],
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
