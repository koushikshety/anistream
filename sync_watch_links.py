import json
import time
from datetime import datetime, timezone

import requests

ANILIST_URL = "https://graphql.anilist.co"

# Licensed platforms from Sections 3B & 3C of the plan
ALLOWED_PLATFORMS = {
    "Bilibili",
    "Bilibili TV",
    "iQIYI",
    "WeTV",
    "Tencent Video",
    "Rakuten Viki",
    "Viki",
    "Tubi TV",
    "Pluto TV",
    "RetroCrush",
    "Crunchyroll",
    "Netflix",
    "Hulu",
    "HIDIVE",
    "Amazon Prime Video",
    "YouTube",
}

QUERY = """
query ($page: Int, $perPage: Int, $country: CountryCode) {
  Page(page: $page, perPage: $perPage) {
    media(type: ANIME, countryOfOrigin: $country, status_in: [RELEASING, FINISHED], sort: POPULARITY_DESC) {
      id
      title {
        romaji
        english
        native
      }
      countryOfOrigin
      episodes
      nextAiringEpisode {
        episode
        airingAt
      }
      coverImage {
        large
      }
      externalLinks {
        site
        url
        type
        language
      }
    }
  }
}
"""


def fetch_catalog_links(country_code: str, pages: int = 2) -> list[dict]:
    results = []
    for page in range(1, pages + 1):
        resp = requests.post(
            ANILIST_URL,
            json={"query": QUERY, "variables": {"page": page, "perPage": 50, "country": country_code}},
            timeout=20,
        )
        resp.raise_for_status()
        media_list = resp.json().get("data", {}).get("Page", {}).get("media", [])

        for m in media_list:
            watch_links = [
                {
                    "platform": link["site"],
                    "url": link["url"],
                    "language": link.get("language") or "Sub/Original",
                }
                for link in m.get("externalLinks", [])
                if link.get("type") == "STREAMING" and link.get("site") in ALLOWED_PLATFORMS
            ]
            if not watch_links:
                continue

            results.append(
                {
                    "anilist_id": m["id"],
                    "category": "donghua" if m.get("countryOfOrigin") == "CN" else "anime",
                    "title": m["title"].get("english") or m["title"].get("romaji"),
                    "native_title": m["title"].get("native"),
                    "episodes": m.get("episodes"),
                    "next_airing": m.get("nextAiringEpisode"),
                    "cover": m.get("coverImage", {}).get("large"),
                    "where_to_watch": watch_links,
                }
            )
        # Respect AniList's 30 req/min rate limit from Section 4
        time.sleep(2.2)

    return results


def main() -> None:
    anime_links = fetch_catalog_links("JP", pages=2)
    donghua_links = fetch_catalog_links("CN", pages=2)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": anime_links + donghua_links,
    }
    with open("watch_links.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(payload['items'])} titles with official 'Where to watch' links.")


if __name__ == "__main__":
    main()
