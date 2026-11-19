import json
import re
import urllib.request
import urllib.parse
import time

SEARCH_QUERIES = [
    {"q": "Muse India official full episodes playlist", "server": "Server 1 (Muse India)", "type": "anime", "quality": "1080p"},
    {"q": "Muse Asia official full episodes playlist", "server": "Server 2 (Muse Asia)", "type": "anime", "quality": "1080p"},
    {"q": "Ani-One India official full episodes playlist", "server": "Server 1 (Ani-One India)", "type": "anime", "quality": "1080p"},
    {"q": "Ani-One Asia official full episodes playlist", "server": "Server 2 (Ani-One Asia)", "type": "anime", "quality": "1080p"},
    {"q": "Tencent Video Animation donghua full episodes playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Youku Animation donghua full episodes playlist", "server": "Server 2 (Youku 4K)", "type": "donghua", "quality": "4K / 1080p"},
]

ALLOWED_CHANNELS = ("muse", "ani-one", "tencent", "youku", "bilibili", "crunchyroll")
SPAM_WORDS = ("membership", "join animation", "download wetv", "wetv.vip", "completed series", "animasi anichin", "donghua 3d", "preview", "trailer", "pv ")

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
                ep_num = int(re.sub(r"\D", "", str(pr.get("videoCount", "12"))) or 12)
                if pid.startswith("PL") and any(k in owner for k in ALLOWED_CHANNELS):
                    results.append({"playlistId": pid, "rawTitle": title, "episodes": ep_num})
            elif "lockupViewModel" in obj:
                lv = obj["lockupViewModel"]
                pid = lv.get("contentId", "")
                meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
                title = meta.get("title", {}).get("content", "")
                raw_blob = json.dumps(lv).lower()
                if pid.startswith("PL") and title and any(k in raw_blob for k in ALLOWED_CHANNELS):
                    results.append({"playlistId": pid, "rawTitle": title, "episodes": 24})
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return results

def extract_english_search_name(raw):
    if any(s in raw.lower() for s in SPAM_WORDS):
        return ""
    # Remove CJK brackets & non-ASCII characters so AniList gets pure English/Romaji
    t = re.sub(r"《.*?》|【.*?】|\[.*?\]|\(.*?\)", " ", raw)
    t = re.sub(r"[^\x00-\x7F]+", " ", t)
    t = re.sub(r"(?i)\b(hindi dub|english sub|eng sub|multisub|multi sub|full episodes|all episodes|full ep|season \d+|ep\s*\d+.*|muse asia|muse india|muse in|ani-one|tencent|youku|animation|free)\b", " ", t)
    t = re.sub(r"[|★☆•:：\-–—]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def fetch_anilist_meta(title):
    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
        title { english romaji native }
        seasonYear
        averageScore
        coverImage { extraLarge large }
        bannerImage
        description(asHtml: false)
        genres
        episodes
        externalLinks { site url }
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
        print(f"Scanning {item['server']}...")
        try:
            pls = search_official_playlists(item["q"])
        except Exception as e:
            print(f"  Skipped: {e}")
            continue

        for pl in pls[:20]:
            raw = pl["rawTitle"]
            is_hindi = bool(re.search(r"(?i)\bhindi\b", raw))
            clean_query = extract_english_search_name(raw)
            if len(clean_query) < 3:
                continue

            meta = fetch_anilist_meta(clean_query)
            time.sleep(0.65)

            # Require true vertical 2:3 AniList poster so zero cropped/landscape images ever appear!
            if not meta or not meta.get("coverImage", {}).get("large"):
                continue

            eng_title = meta["title"].get("english") or meta["title"].get("romaji") or clean_query
            native_title = meta["title"].get("native") or meta["title"].get("romaji") or ""
            year = meta.get("seasonYear") or 2024
            score = meta.get("averageScore") or 82
            slug = slugify(eng_title)

            audio_type = "Hindi Dub" if is_hindi else ("Chinese (Eng Sub)" if item["type"] == "donghua" else "English Sub")
            server_entry = {
                "name": f"{item['server']} • {audio_type}",
                "playlistId": pl["playlistId"],
                "lang": audio_type
            }

            if slug in catalog_map:
                # Merge additional server/language onto existing show
                existing_ids = [s["playlistId"] for s in catalog_map[slug]["servers"]]
                if pl["playlistId"] not in existing_ids:
                    catalog_map[slug]["servers"].append(server_entry)
                if is_hindi:
                    catalog_map[slug]["hasHindi"] = True
                    if "hindi" not in catalog_map[slug]["genres"]:
                        catalog_map[slug]["genres"].append("hindi")
                continue

            cover = meta["coverImage"].get("extraLarge") or meta["coverImage"]["large"]
            banner = meta.get("bannerImage") or cover
            desc = re.sub(r"<[^>]+>", "", meta.get("description") or "").strip()
            ep_count = meta.get("episodes") or pl["episodes"]

            raw_genres = [g.lower() for g in (meta.get("genres") or [])]
            genres = [item["type"]] + raw_genres[:4]
            if any(g in raw_genres for g in ("fantasy", "adventure", "action")):
                genres.append("isekai")
            if is_hindi:
                genres.append("hindi")

            official_links = [
                {"site": l["site"], "url": l["url"]}
                for l in (meta.get("externalLinks") or [])
                if l.get("site") in ("Crunchyroll", "Netflix", "Amazon Prime Video", "Bilibili", "YouTube")
            ][:3]

            catalog_map[slug] = {
                "slug": slug,
                "type": item["type"],
                "title": eng_title,
                "nativeTitle": native_title,
                "year": year,
                "score": score,
                "provider": item["server"],
                "quality": item["quality"],
                "episodes": ep_count,
                "hasHindi": is_hindi,
                "genres": list(dict.fromkeys(genres)),
                "cover": cover,
                "banner": banner,
                "desc": desc[:280] + ("..." if len(desc) > 280 else ""),
                "servers": [server_entry],
                "officialLinks": official_links,
            }
            print(f"  + {eng_title} ({year}) [{audio_type}]")

    final_list = list(catalog_map.values())
    if final_list:
        with open("data/catalog.json", "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)
        print(f"SUCCESS: Synced {len(final_list)} clean English-titled shows with 2:3 posters!")

if __name__ == "__main__":
    main()
