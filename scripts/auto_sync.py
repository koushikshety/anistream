import json
import re
import urllib.request
import urllib.parse
import urllib.error
import time

# 1. Broad Official Channel Scans + 2. Targeted Famous Anime & Donghua Searches
SEARCH_QUERIES = [
    {"q": "Muse India official full episodes playlist", "server": "Server 1 (Muse India)", "type": "anime", "quality": "1080p"},
    {"q": "Muse Asia official full episodes playlist", "server": "Server 2 (Muse Asia)", "type": "anime", "quality": "1080p"},
    {"q": "Ani-One India official full episodes playlist", "server": "Server 1 (Ani-One India)", "type": "anime", "quality": "1080p"},
    {"q": "Ani-One Asia official full episodes playlist", "server": "Server 2 (Ani-One Asia)", "type": "anime", "quality": "1080p"},
    {"q": "Tencent Video Animation donghua full episodes playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Youku Animation donghua full episodes playlist", "server": "Server 2 (Youku 4K)", "type": "donghua", "quality": "4K / 1080p"},
    # Famous Anime & Donghua Direct Searches
    {"q": "That Time I Got Reincarnated as a Slime Muse Asia playlist", "server": "Server 1 (Muse Official)", "type": "anime", "quality": "1080p"},
    {"q": "Solo Leveling official playlist", "server": "Server 1 (Official)", "type": "anime", "quality": "1080p"},
    {"q": "Demon Slayer Kimetsu no Yaiba Muse Asia playlist", "server": "Server 1 (Muse Official)", "type": "anime", "quality": "1080p"},
    {"q": "Chainsaw Man Ani-One playlist", "server": "Server 1 (Ani-One Official)", "type": "anime", "quality": "1080p"},
    {"q": "Black Clover Muse Asia playlist", "server": "Server 1 (Muse Official)", "type": "anime", "quality": "1080p"},
    {"q": "Naruto Shippuden official episodes playlist", "server": "Server 1 (Official)", "type": "anime", "quality": "1080p"},
    {"q": "One Piece official episodes playlist", "server": "Server 1 (Official)", "type": "anime", "quality": "1080p"},
    {"q": "Tokyo Ghoul Muse Asia playlist", "server": "Server 1 (Muse Official)", "type": "anime", "quality": "1080p"},
    {"q": "No Game No Life Muse Asia playlist", "server": "Server 1 (Muse Official)", "type": "anime", "quality": "1080p"},
    {"q": "Assassination Classroom Muse Asia playlist", "server": "Server 1 (Muse Official)", "type": "anime", "quality": "1080p"},
    {"q": "Renegade Immortal Xian Ni Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Against the Gods Ni Tian Xie Shen donghua playlist", "server": "Server 1 (Official 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Battle Through the Heavens Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Swallowed Star Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Perfect World Wanmei Shijie Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "A Will Eternal Yi Nian Yong Heng Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Soul Land Douluo Dalu Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Throne of Seal Shen Yin Wangzuo Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Jade Dynasty Zhu Xian Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Tales of Demons and Gods Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "Martial Universe Wu Dong Qian Kun Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
    {"q": "The King's Avatar Quan Zhi Gao Shou Tencent Video playlist", "server": "Server 1 (Tencent 4K)", "type": "donghua", "quality": "4K / 1080p"},
]

ALLOWED_CHANNELS = ("muse", "ani-one", "tencent", "youku", "bilibili", "crunchyroll", "iqiyi", "wetv", "ani-mi", "anime")
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
        synonyms
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
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "AniStreamBot/1.0"}
    for _ in range(3):
        try:
            res = json.loads(fetch_url("https://graphql.anilist.co", data=payload, headers=headers))
            return res.get("data", {}).get("Media")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15)
            else:
                return None
        except Exception:
            time.sleep(2)
    return None

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def generate_sitemap(items):
    base = "https://anistream.aniguide-hub.workers.dev"
    urls = [f"  <url><loc>{base}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>"]
    for it in items:
        urls.append(f"  <url><loc>{base}/watch.html?id={it['slug']}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Generated sitemap.xml with {len(urls)} URLs", flush=True)

def main():
    catalog_map = {}
    try:
        with open("data/catalog.json", "r", encoding="utf-8") as f:
            for existing in json.load(f):
                if existing.get("slug") and existing.get("cover"):
                    catalog_map[existing["slug"]] = existing
    except Exception:
        pass

    for item in SEARCH_QUERIES:
        print(f"Scanning {item['q'][:42]}...", flush=True)
        try:
            pls = search_official_playlists(item["q"])
        except Exception as e:
            print(f"  Skipped: {e}", flush=True)
            continue

        limit = 16 if "official full episodes" in item["q"] else 3
        for pl in pls[:limit]:
            raw = pl["rawTitle"]
            is_hindi = bool(re.search(r"(?i)\bhindi\b", raw))
            clean_query = extract_english_search_name(raw)
            if len(clean_query) < 3:
                continue

            meta = fetch_anilist_meta(clean_query)
            time.sleep(1.1)

            if not meta or not meta.get("coverImage", {}).get("large"):
                continue

            eng_title = meta["title"].get("english") or meta["title"].get("romaji") or clean_query
            romaji_title = meta["title"].get("romaji") or ""
            native_title = meta["title"].get("native") or ""
            synonyms = meta.get("synonyms") or []
            year = meta.get("seasonYear") or 2024
            score = meta.get("averageScore") or 82
            slug = slugify(eng_title)

            aliases = list(dict.fromkeys([
                a.strip() for a in ([eng_title, romaji_title, native_title, clean_query] + synonyms) if a and len(a.strip()) >= 2
            ]))

            audio_type = "Hindi Dub" if is_hindi else ("Chinese (Eng Sub)" if item["type"] == "donghua" else "English Sub")
            server_entry = {
                "name": f"{item['server']} • {audio_type}",
                "playlistId": pl["playlistId"],
                "lang": audio_type
            }

            if slug in catalog_map:
                existing_ids = [s["playlistId"] for s in catalog_map[slug].get("servers", [])]
                if pl["playlistId"] not in existing_ids:
                    catalog_map[slug].setdefault("servers", []).append(server_entry)
                catalog_map[slug]["aliases"] = list(dict.fromkeys(catalog_map[slug].get("aliases", []) + aliases))
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
                "aliases": aliases,
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
            print(f"  + {eng_title} ({year}) [{audio_type}]", flush=True)

    final_list = list(catalog_map.values())
    if final_list:
        with open("data/catalog.json", "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)
        generate_sitemap(final_list)
        print(f"SUCCESS: Total {len(final_list)} Anime & Donghua shows synced!", flush=True)

if __name__ == "__main__":
    main()
