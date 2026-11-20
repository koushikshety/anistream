import json
import os
import re
import time

CATALOG_PATH = "data/catalog.json"
EPISODES_PATH = "episodes.json"
WATCH_LINKS_PATH = "watch_links.json"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "show"


def clean_series_title(raw_title: str) -> str:
    t = raw_title or ""
    # Remove English and Chinese bracketed tags like [ENG SUB], 【会员抢先看】, 《仙逆》
    t = re.sub(r"\[.*?\]|\(.*?\)|【.*?】|《.*?》|「.*?」", " ", t)
    t = re.sub(r"\b(?:MULTI\s*SUB|ENG\s*SUB|FULL\s*EP(?:ISODE)?)\b", " ", t, flags=re.I)
    t = re.split(r"\s*[-–|:]\s*(?:episode|ep\.?)\s*\d+.*$", t, flags=re.I)[0]
    t = re.sub(r"\s*(?:episode|ep\.?)\s*\d+.*$", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -–|:")
    return t or raw_title.strip()


def normalize_key(text: str) -> str:
    s = clean_series_title(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    os.makedirs("data", exist_ok=True)
    catalog = load_json(CATALOG_PATH, [])
    yt_episodes = load_json(EPISODES_PATH, [])
    watch_data = load_json(WATCH_LINKS_PATH, {"items": []})
    now_ts = int(time.time())

    # Clean up any previously merged messy entries or year-as-episode bugs (> 1000)
    cleaned_catalog = []
    by_norm = {}
    for item in catalog:
        # Strip dead servers that have no mapped episodes and no playlistId
        item["servers"] = [
            s for s in item.get("servers", [])
            if (isinstance(s.get("episodeMap"), dict) and len(s["episodeMap"]) > 0)
            or s.get("playlistId")
            or (isinstance(s.get("videoIds"), list) and len(s["videoIds"]) > 0)
        ]
        # Remove false episode numbers > 1000 (like year 2025)
        for srv in item.get("servers", []):
            ep_map = srv.get("episodeMap", {})
            if isinstance(ep_map, dict):
                srv["episodeMap"] = {
                    k: v for k, v in ep_map.items() if k.isdigit() and int(k) < 1000
                }
        if int(item.get("episodes") or 1) >= 1000:
            all_eps = [
                int(k)
                for s in item.get("servers", [])
                for k in (s.get("episodeMap") or {}).keys()
                if k.isdigit()
            ]
            item["episodes"] = max(all_eps) if all_eps else 24
            item["latestEp"] = item["episodes"]

        item["title"] = clean_series_title(item.get("title", ""))
        key = normalize_key(item["title"])
        if key in by_norm:
            # Merge servers & officialLinks into existing entry instead of duplicating
            target = by_norm[key]
            for srv in item.get("servers", []):
                t_srv = next((s for s in target.setdefault("servers", []) if s.get("name") == srv.get("name")), None)
                if not t_srv:
                    target["servers"].append(srv)
                else:
                    t_srv.setdefault("episodeMap", {}).update(srv.get("episodeMap", {}))
            seen_sites = {x.get("site") for x in target.get("officialLinks", [])}
            for lk in item.get("officialLinks", []):
                if lk.get("site") not in seen_sites:
                    target.setdefault("officialLinks", []).append(lk)
                    seen_sites.add(lk.get("site"))
            continue

        by_norm[key] = item
        if item.get("nativeTitle"):
            by_norm[normalize_key(item["nativeTitle"])] = item
        cleaned_catalog.append(item)

    catalog = cleaned_catalog

    # 1. Merge official "Where to Watch" catalog entries
    for w in watch_data.get("items", []):
        raw_t = w.get("title") or w.get("native_title")
        if not raw_t:
            continue
        title = clean_series_title(raw_t)
        key = normalize_key(title)
        official_links = [
            {"site": lk.get("platform") or lk.get("site"), "url": lk["url"]}
            for lk in w.get("where_to_watch", [])
            if (lk.get("platform") or lk.get("site")) and lk.get("url")
        ]
        if not official_links:
            continue

        existing = by_norm.get(key) or (
            by_norm.get(normalize_key(w.get("native_title", ""))) if w.get("native_title") else None
        )
        if existing:
            seen_sites = {x.get("site") for x in existing.get("officialLinks", [])}
            for lk in official_links:
                if lk["site"] not in seen_sites:
                    existing.setdefault("officialLinks", []).append(lk)
                    seen_sites.add(lk["site"])
            if w.get("cover") and "ytimg.com" in existing.get("cover", ""):
                existing["cover"] = w["cover"]
                existing["banner"] = w["cover"]
            existing["updatedAt"] = now_ts
        else:
            total_eps = w.get("episodes") or (
                (w.get("next_airing") or {}).get("episode", 1) - 1
            ) or 12
            entry = {
                "slug": slugify(title),
                "type": w.get("category", "anime"),
                "title": title,
                "nativeTitle": w.get("native_title") or "",
                "aliases": [x for x in [title, w.get("native_title")] if x],
                "year": 2026,
                "score": 80,
                "status": "ONGOING" if w.get("next_airing") else "FINISHED",
                "airDay": "Daily",
                "quality": "1080p Official",
                "episodes": max(1, int(total_eps)),
                "latestEp": max(1, int(total_eps)),
                "genres": ["Action", "Adventure", "Fantasy"],
                "cover": w.get("cover") or "",
                "banner": w.get("cover") or "",
                "desc": f"Official licensed streams available on {', '.join(x['site'] for x in official_links)}.",
                "servers": [],
                "officialLinks": official_links,
                "updatedAt": now_ts,
            }
            catalog.append(entry)
            by_norm[key] = entry

    # 2. Merge validated official YouTube embed episodes into servers[]
    for ep in yt_episodes:
        series_title = clean_series_title(ep.get("title", ""))
        key = normalize_key(series_title)
        if not key:
            continue

        channel_name = ep.get("channel", "Official YouTube")
        vid = ep.get("video_id")
        ep_num = int(ep.get("episode") or 1)
        last_ep = int(ep.get("last_episode") or ep_num)
        if not vid or ep_num >= 1000:
            continue

        existing = by_norm.get(key)
        if not existing:
            existing = {
                "slug": slugify(series_title),
                "type": ep.get("category", "anime"),
                "title": series_title,
                "nativeTitle": "",
                "aliases": [series_title],
                "year": 2026,
                "score": 82,
                "status": "ONGOING",
                "airDay": "Daily",
                "quality": "1080p Official",
                "episodes": max(ep_num, last_ep),
                "latestEp": max(ep_num, last_ep),
                "genres": ["Action", "Fantasy"],
                "cover": ep.get("thumbnail") or "",
                "banner": ep.get("thumbnail") or "",
                "desc": f"Official full episodes streamed by {channel_name} on YouTube.",
                "servers": [],
                "officialLinks": [],
                "updatedAt": now_ts,
            }
            catalog.append(existing)
            by_norm[key] = existing

        srv = next(
            (s for s in existing.setdefault("servers", []) if s.get("name") == channel_name),
            None,
        )
        if not srv:
            srv = {
                "name": channel_name,
                "type": "youtube",
                "lang": "English Sub",
                "episodeMap": {},
            }
            existing["servers"].append(srv)

        for n in range(ep_num, last_ep + 1):
            srv["episodeMap"][str(n)] = vid

        existing["episodes"] = max(int(existing.get("episodes") or 1), last_ep)
        existing["latestEp"] = max(int(existing.get("latestEp") or 1), last_ep)
        existing["updatedAt"] = now_ts

    playable_catalog = [
        item for item in catalog
        if (item.get("servers") and len(item["servers"]) > 0)
        or (item.get("officialLinks") and len(item["officialLinks"]) > 0)
    ]

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(playable_catalog, f, ensure_ascii=False, indent=2)

    print(f"Merged catalog ready: {len(playable_catalog)} clean shows in {CATALOG_PATH}.")


if __name__ == "__main__":
    main()
