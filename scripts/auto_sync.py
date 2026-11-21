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
    {"name": "Tencent 4K", "type": "donghua", "id": "UCdpiId0eJGnnIvfhpbJIM1w"},
]

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
BAD_WORDS = re.compile(r"\b(pv|trailer|teaser|preview|op|ed|clip|short|reaction|review|amv|ost|explained|recap|vostfr|vf|sub[\s._-]?indo|indo|indonesian|sub[\s._-]?es|esp|espanol|pt[\s._-]?br|portugues|sub[\s._-]?th|thai|viet|vietsub|rus|arabic|预告|drama|cdrama|kdrama|asian movies|live action|movie)\b", re.I)
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

def build_show_obj(m, strict_type):
    disp = m["title"].get("english") or m["title"].get("romaji") or ""
    if not disp:
        return None
    cover = (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or ""
    if not cover:
        return None
    na = m.get("nextAiringEpisode") or {}
    air_day = DAYS[(time.gmtime(na["airingAt"]).tm_wday + 1) % 7] if na.get("airingAt") else DAYS[sum(ord(c) for c in disp) % 7]
    return {
        "slug": slugify(disp),
        "type": strict_type,
        "title": disp,
        "nativeTitle": m["title"].get("native") or "",
        "aliases": list(dict.fromkeys([disp, m["title"].get("romaji") or "", m["title"].get("native") or ""])),
        "year": m.get("seasonYear") or 2025,
        "score": m.get("averageScore") or 80,
        "status": "ONGOING" if m.get("status") == "RELEASING" else "COMPLETED",
        "airDay": air_day,
        "quality": "4K / 1080p" if strict_type == "donghua" else "1080p",
        "episodes": m.get("episodes") or 24,
        "latestEp": 1,
        "genres": [g.lower() for g in (m.get("genres") or [])[:4]],
        "cover": cover,
        "banner": m.get("bannerImage") or cover,
        "desc": re.sub(r"<[^>]+>", "", m.get("description") or "").strip()[:280],
        "servers": [],
        "officialLinks": [],
        "updatedAt": int(time.time() * 1000),
    }

def fetch_top_anilist(country, per_page=50):
    q = """
    query ($c: CountryCode, $n: Int) {
      Page(page: 1, perPage: $n) {
        media(type: ANIME, countryOfOrigin: $c, sort: [TRENDING_DESC, POPULARITY_DESC]) {
          title { english romaji native }
          countryOfOrigin status seasonYear averageScore episodes
          coverImage { extraLarge large } bannerImage description(asHtml: false)
          genres nextAiringEpisode { airingAt }
        }
      }
    }
    """
    payload = json.dumps({"query": q, "variables": {"c": country, "n": per_page}}).encode()
    res = json.loads(fetch_text(
        "https://graphql.anilist.co",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AniStreamBot/1.0"}
    ))
    return res.get("data", {}).get("Page", {}).get("media", [])

def attach_episode(show, srv_name, srv_type, ep, embed_val):
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

    # 1. Auto-discover Top 50 Anime (JP) + Top 50 Donghua (CN) from AniList
    discovered = []
    for country, s_type in [("JP", "anime"), ("CN", "donghua")]:
        try:
            for m in fetch_top_anilist(country, 50):
                obj = build_show_obj(m, s_type)
                if obj:
                    discovered.append(obj)
                    if obj["slug"] in catalog_map:
                        catalog_map[obj["slug"]]["type"] = s_type
                        catalog_map[obj["slug"]]["status"] = obj["status"]
                        catalog_map[obj["slug"]]["score"] = obj["score"]
        except Exception as e:
            print(f"[AniList Skip] {country}: {e}")

    # 2. Scan Official YouTube RSS Feeds
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    for ch in YT_CHANNELS:
        try:
            xml = fetch_text(f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['id']}")
            root = ET.fromstring(xml)
            for entry in root.findall("a:entry", ns):
                vid = entry.find("yt:videoId", ns).text
                raw_t = entry.find("a:title", ns).text
                clean_t, ep = extract_ep_and_title(raw_t)
                if not clean_t or not ep:
                    continue
                slug = slugify(clean_t)
                target = next((v for k, v in catalog_map.items() if k == slug or slug in k or k in slug), None)
                if not target:
                    target = next((d for d in discovered if d["slug"] == slug or slug in d["slug"]), None)
                    if target:
                        catalog_map[target["slug"]] = target
                if target:
                    attach_episode(target, ch["name"], "youtube", ep, vid)
        except Exception as e:
            print(f"[YT RSS Skip] {ch['name']}: {e}")

    # 3. Auto-sync Dailymotion HD for all 100 discovered Anime & Donghua
    for obj in discovered:
        try:
            q = urllib.parse.quote(f"{obj['title']} episode eng sub")
            url = f"https://api.dailymotion.com/videos?search={q}&sort=recent&fields=id,title,duration&limit=30"
            data = json.loads(fetch_text(url))
            found_any = False
            for v in data.get("list", []):
                if (v.get("duration") or 0) < 720:
                    continue
                v_title = v.get("title", "")
                vt_low = v_title.lower()
                matched_alias = False
                for alias in (obj.get("aliases") or [obj["title"]]):
                    if not alias:
                        continue
                    if alias.lower() in vt_low:
                        matched_alias = True
                        break
                    words = [w for w in re.findall(r"[a-z0-9]+", alias.lower()) if len(w) >= 3]
                    if words and sum(1 for w in words[:3] if w in vt_low) >= min(2, len(words)):
                        matched_alias = True
                        break
                if not matched_alias:
                    continue
                _, ep = extract_ep_and_title(v_title)
                if ep:
                    if obj["slug"] not in catalog_map:
                        catalog_map[obj["slug"]] = obj
                    attach_episode(catalog_map[obj["slug"]], "Dailymotion HD", "dailymotion", ep, v["id"])
                    found_any = True
            if found_any:
                time.sleep(0.15)
        except Exception:
            continue

    # Include newly discovered shows/seasons even if 0 episodes yet (marked upcoming)
    for obj in discovered:
        if obj["slug"] not in catalog_map:
            obj["upcoming"] = True
            obj["lastEpisodeAt"] = obj.get("lastEpisodeAt", 0)
            catalog_map[obj["slug"]] = obj

    for s in catalog_map.values():
        s["upcoming"] = not bool(s.get("servers"))
        if "lastEpisodeAt" not in s:
            s["lastEpisodeAt"] = 0

    # Strict chronological order: newest episodes jump to the front, older move back
    final_list = list(catalog_map.values())
    final_list.sort(
        key=lambda x: (
            int(x.get("lastEpisodeAt", 0)),
            not x.get("upcoming", False),
            x.get("status") == "ONGOING",
            int(x.get("score", 0))
        ),
        reverse=True
    )

    anime_list = [s for s in final_list if s.get("type") == "anime"]
    donghua_list = [s for s in final_list if s.get("type") == "donghua"]

    os.makedirs("data", exist_ok=True)
    with open("data/catalog.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)
    with open("data/anime_catalog.json", "w", encoding="utf-8") as f:
        json.dump(anime_list, f, indent=2, ensure_ascii=False)
    with open("data/donghua_catalog.json", "w", encoding="utf-8") as f:
        json.dump(donghua_list, f, indent=2, ensure_ascii=False)

    print(f"Synced {len(final_list)} total shows -> {len(anime_list)} Anime (JP), {len(donghua_list)} Donghua (CN)!")

if __name__ == "__main__":
    main()
