import json
import re
import urllib.request
import urllib.parse
import time

SEARCH_QUERIES = [
    {"q": "Muse India official full episodes playlist", "provider": "Muse India (Official)", "type": "anime", "quality": "1080p"},
    {"q": "Muse Asia official full episodes playlist", "provider": "Muse Asia (Official)", "type": "anime", "quality": "1080p"},
    {"q": "Ani-One India official full episodes playlist", "provider": "Ani-One India (Official)", "type": "anime", "quality": "1080p"},
    {"q": "Ani-One Asia official full episodes playlist", "provider": "Ani-One Asia (Official)", "type": "anime", "quality": "1080p"},
    {"q": "Tencent Video Animation donghua full episodes playlist", "provider": "Tencent Video (Official)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Youku Animation donghua full episodes playlist", "provider": "Youku Animation (Official)", "type": "donghua", "quality": "4K / 1080p"},
]

ALLOWED_CHANNELS = ("muse", "ani-one", "tencent", "youku", "bilibili", "crunchyroll")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_url(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def search_official_playlists(query):
    encoded = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded}&sp=EgIQAw%3D%3D"
    html = fetch_url(url)
    m = re.search(r"var ytInitialData = ({.*?});</script>", html)
    if not m:
        return []
    data = json.loads(m.group(1))
    results = []

    def walk(obj):
        if isinstance(obj, dict):
            if "playlistRenderer" in obj:
                pr = obj["playlistRenderer"]
                pid = pr.get("playlistId", "")
                title = pr.get("title", {}).get("simpleText", "")
                owner = "".join(r.get("text", "") for r in pr.get("shortBylineText", {}).get("runs", [])).lower()
                thumbs = pr.get("thumbnails", [{}])[0].get("thumbnails", [])
                thumb = thumbs[-1].get("url", "") if thumbs else ""
                ep_num = int(re.sub(r"\D", "", str(pr.get("videoCount", "12"))) or 12)
                if pid.startswith("PL") and any(k in owner for k in ALLOWED_CHANNELS):
                    results.append({"playlistId": pid, "rawTitle": title, "thumb": thumb, "episodes": ep_num})
            elif "lockupViewModel" in obj:
                lv = obj["lockupViewModel"]
                pid = lv.get("contentId", "")
                meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
                title = meta.get("title", {}).get("content", "")
                raw_blob = json.dumps(lv).lower()
                thumb_m = re.search(r'https://i\.ytimg\.com/vi/[^"]+\.jpg', json.dumps(lv))
                thumb = thumb_m.group(0) if thumb_m else ""
                if pid.startswith("PL") and title and any(k in raw_blob for k in ALLOWED_CHANNELS):
                    results.append({"playlistId": pid, "rawTitle": title, "thumb": thumb, "episodes": 24})
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return results

def clean_title(raw):
    t = re.sub(r"\[.*?\]|\(.*?\)|【.*?】", "", raw)
    t = re.sub(r"(?i)\b(hindi dub|english sub|multi sub|full episodes|all episodes|season \d+|ep\s*\d+.*|muse asia|muse india|ani-one|tencent|youku)\b", "", t)
    return re.sub(r"\s+", " ", t).strip(" -|:")

def fetch_anilist_meta(title):
    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
        title { english romaji }
        coverImage { extraLarge large }
        bannerImage
        description(asHtml: false)
        genres
        episodes
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"search": title}}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    try:
        res = json.loads(fetch_url("https://graphql.anilist.co", data=payload, headers=headers))
        return res.get("data", {}).get("Media")
    except Exception:
        return None

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def main():
    catalog_map = {}

    for item in SEARCH_QUERIES:
        print(f"Searching: {item['provider']}...")
        try:
            pls = search_official_playlists(item["q"])
            print(f"  Matched {len(pls)} official playlists")
        except Exception as e:
            print(f"  Error: {e}")
            continue

        for pl in pls[:15]:
            raw = pl["rawTitle"]
            is_hindi = bool(re.search(r"(?i)\bhindi\b", raw))
            track_label = "Hindi Dub" if is_hindi else ("Chinese (Eng Sub)" if item["type"] == "donghua" else "English Sub")
            base_name = clean_title(raw)
            if len(base_name) < 3:
                continue

            slug = slugify(base_name)
            if slug in catalog_map:
                catalog_map[slug]["tracks"][track_label] = pl["playlistId"]
                if is_hindi:
                    catalog_map[slug]["hasHindi"] = True
                    if "hindi" not in catalog_map[slug]["genres"]:
                        catalog_map[slug]["genres"].append("hindi")
                continue

            meta = fetch_anilist_meta(base_name)
            time.sleep(0.65)

            if meta and meta.get("coverImage", {}).get("large"):
                display_title = meta["title"].get("english") or meta["title"].get("romaji") or base_name
                cover = meta["coverImage"].get("extraLarge") or meta["coverImage"]["large"]
                banner = meta.get("bannerImage") or cover
                desc = re.sub(r"<[^>]+>", "", meta.get("description") or "").strip()
                ep_count = meta.get("episodes") or pl["episodes"]
                genres = [item["type"]] + [g.lower() for g in (meta.get("genres") or [])[:3]]
            else:
                if not pl["thumb"]:
                    continue
                display_title = base_name
                cover = pl["thumb"]
                banner = pl["thumb"]
                desc = f"Watch {base_name} officially licensed in HD from {item['provider']}."
                ep_count = pl["episodes"]
                genres = [item["type"], "action"]

            if is_hindi and "hindi" not in genres:
                genres.append("hindi")

            catalog_map[slug] = {
                "slug": slug,
                "type": item["type"],
                "title": display_title,
                "provider": item["provider"],
                "quality": item["quality"],
                "episodes": ep_count,
                "hasHindi": is_hindi,
                "genres": list(dict.fromkeys(genres)),
                "cover": cover,
                "banner": banner,
                "desc": desc[:260] + ("..." if len(desc) > 260 else ""),
                "tracks": {track_label: pl["playlistId"]},
            }
            print(f"  + Added: {display_title} ({track_label})")

    final_list = list(catalog_map.values())
    if final_list:
        with open("data/catalog.json", "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: Auto-synced {len(final_list)} verified Anime & Donghua shows!")
    else:
        print("WARNING: No playlists fetched; keeping existing catalog.json")

if __name__ == "__main__":
    main()
