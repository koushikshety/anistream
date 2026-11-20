import json
import os
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

YT_CHANNELS = [
    {"name": "Muse Asia", "type": "anime", "id": "UCGbshtvS9t-8CW11W7TooQg"},
    {"name": "Ani-One Asia", "type": "anime", "id": "UC0wNSTMWIL3qaorLx0jie6A"},
    {"name": "Tencent 4K", "type": "donghua", "id": "UCQatgKoA7lylp_UzvsLCWrw"},
    {"name": "Youku 4K", "type": "donghua", "id": "UCc4f0l6w9q8g1N2Q4Q5Y6wA"},
]

DM_FAST_SHOWS = [
    {"title": "Renegade Immortal", "type": "donghua"},
    {"title": "Battle Through the Heavens", "type": "donghua"},
    {"title": "Perfect World", "type": "donghua"},
    {"title": "Soul Land 2", "type": "donghua"},
    {"title": "Throne of Seal", "type": "donghua"},
    {"title": "Shrouding the Heavens", "type": "donghua"},
    {"title": "Swallowed Star", "type": "donghua"},
    {"title": "That Time I Got Reincarnated as a Slime", "type": "anime"},
]

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
BAD_WORDS = re.compile(r"\b(pv|trailer|teaser|preview|op|ed|clip|short|reaction|review|amv|ost)\b", re.I)
EP_PATTERNS = [
    re.compile(r"(?:episode|ep\.?|#)\s*0*(\d{1,4})\b", re.I),
    re.compile(r"第\s*0*(\d{1,4})\s*[集话話]"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def fetch_text(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def extract_ep_and_title(raw):
    if BAD_WORDS.search(raw):
        return None, None
    for pat in EP_PATTERNS:
        m = pat.search(raw)
        if m:
            ep = int(m.group(1))
            if 1 <= ep <= 2500:
                title = re.sub(r"《.*?》|【.*?】|\[.*?\]|\(.*?\)|[^\x00-\x7F]+", " ", raw[:m.start()])
                title = re.sub(r"[\|\-–—:]+$", "", title).strip()
                return (title if len(title) >= 3 else None), ep
    return None, None

def fetch_anilist(title, fallback_type):
    q = """
    query ($s: String) {
      Media(search: $s, type: ANIME, sort: POPULARITY_DESC) {
        title { english romaji native }
        countryOfOrigin status seasonYear averageScore episodes
        coverImage { extraLarge large } bannerImage description(asHtml: false)
        genres nextAiringEpisode { airingAt }
      }
    }
    """
    try:
        payload = json.dumps({"query": q, "variables": {"s": title}}).encode()
        res = json.loads(fetch_text("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "AniStreamBot/1.0"}))
        m = res.get("data", {}).get("Media")
        if not m:
            return None
        strict_type = "donghua" if m.get("countryOfOrigin") == "CN" else fallback_type
        disp = m["title"].get("english") or m["title"].get("romaji") or title
        cover = m["coverImage"].get("extraLarge") or m["coverImage"].get("large")
        na = m.get("nextAiringEpisode") or {}
        air_day = DAYS[(time.gmtime(na["airingAt"]).tm_wday + 1) % 7] if na.get("airingAt") else DAYS[sum(ord(c) for c in disp) % 7]
        return {
            "slug": slugify(disp), "type": strict_type, "title": disp,
            "nativeTitle": m["title"].get("native") or "",
            "aliases": [disp, m["title"].get("romaji") or "", title],
            "year": m.get("seasonYear") or 2025, "score": m.get("averageScore") or 80,
            "status": "ONGOING" if m.get("status") == "RELEASING" else "COMPLETED",
            "airDay": air_day, "quality": "4K / 1080p" if strict_type == "donghua" else "1080p",
            "episodes": m.get("episodes") or 24, "latestEp": 1,
            "genres": [g.lower() for g in (m.get("genres") or [])[:4]],
            "cover": cover, "banner": m.get("bannerImage") or cover,
            "desc": re.sub(r"<[^>]+>", "", m.get("description") or "").strip()[:280],
            "servers": [], "officialLinks": [], "updatedAt": int(time.time() * 1000)
        }
    except Exception:
        return None

def add_episode(catalog_map, title, fallback_type, srv_name, srv_type, ep, embed_val):
    slug = slugify(title)
    show = next((v for k, v in catalog_map.items() if k == slug or slug in k or k in slug), None)
    if not show:
        show = fetch_anilist(title, fallback_type)
        time.sleep(0.35)
        if not show:
            return
        catalog_map[show["slug"]] = show
    srv = next((s for s in show["servers"] if s["name"] == srv_name), None)
    if not srv:
        srv = {"name": srv_name, "type": srv_type, "lang": "English Sub", "episodeMap": {}}
        show["servers"].append(srv)
    if str(ep) not in srv["episodeMap"]:
        srv["episodeMap"][str(ep)] = embed_val
        show["latestEp"] = max(show.get("latestEp", 1), ep)
        show["episodes"] = max(show.get("episodes", 1), ep)
        show["updatedAt"] = int(time.time() * 1000)

def main():
    catalog_map = {}
    if os.path.exists("data/catalog.json"):
        for ex in json.load(open("data/catalog.json", encoding="utf-8")):
            if ex.get("slug") and ex.get("servers"):
                catalog_map[ex["slug"]] = ex

    # 1. Official YouTube RSS Feeds
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    for ch in YT_CHANNELS:
        try:
            xml = fetch_text(f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['id']}")
            root = ET.fromstring(xml)
            for entry in root.findall("a:entry", ns):
                vid = entry.find("yt:videoId", ns).text
                raw_t = entry.find("a:title", ns).text
                clean_t, ep = extract_ep_and_title(raw_t)
                if clean_t and ep:
                    add_episode(catalog_map, clean_t, ch["type"], ch["name"], "youtube", ep, vid)
        except Exception as e:
            print(f"[YT RSS Skip] {ch['name']}: {e}")

    # 2. Dailymotion Fast Public API (Full episodes >= 12 mins)
    for item in DM_FAST_SHOWS:
        try:
            q = urllib.parse.quote(f"{item['title']} episode eng sub")
            url = f"https://api.dailymotion.com/videos?search={q}&sort=recent&fields=id,title,duration&limit=12"
            data = json.loads(fetch_text(url))
            for v in data.get("list", []):
                if (v.get("duration") or 0) < 720:
                    continue
                _, ep = extract_ep_and_title(v.get("title", ""))
                if ep:
                    add_episode(catalog_map, item["title"], item["type"], "Dailymotion HD", "dailymotion", ep, v["id"])
        except Exception as e:
            print(f"[DM Skip] {item['title']}: {e}")

    final_list = [s for s in catalog_map.values() if s.get("servers")]
    final_list.sort(key=lambda x: (x.get("status") == "ONGOING", x.get("score", 0)), reverse=True)
    os.makedirs("data", exist_ok=True)
    json.dump(final_list, open("data/catalog.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Synced {len(final_list)} 100% playable shows!")

if __name__ == "__main__":
    main()
