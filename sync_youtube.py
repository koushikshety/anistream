import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

# 100% Whitelisted Official Rights-Holder Channels (JP Anime + CN Donghua)
OFFICIAL_CHANNELS = [
    # Japanese Anime (JP)
    {"name": "Muse Asia", "handle": "@MuseAsia", "region": "JP"},
    {"name": "Muse India", "handle": "@MuseIndia", "region": "JP"},
    {"name": "Ani-One Asia", "handle": "@AniOneAsia", "region": "JP"},
    {"name": "Ani-One India", "handle": "@AniOneIndia", "region": "JP"},
    {"name": "Crunchyroll", "handle": "@crunchyroll", "region": "JP"},
    # Chinese Donghua (CN)
    {"name": "Tencent Video - ANIMATION", "handle": "@TencentVideoAnimation", "region": "CN"},
    {"name": "YOUKU ANIMATION", "handle": "@YOUKUANIMATION", "region": "CN"},
    {"name": "MadeByBilibili", "handle": "@MadeByBilibili", "region": "CN"},
    {"name": "iQIYI Anime", "handle": "@iQIYIAnime", "region": "CN"},
]

IGNORE_RE = re.compile(
    r"\b(pv|teaser|trailer|preview|highlight|clip|clips|shorts|ost|opening|ending|op|ed|mv|amv|behind the scenes|interview|recap|special|compilation)\b",
    re.I,
)
EP_RE = re.compile(r"(?:ep(?:isode)?|#|第)\s*0*(\d{1,4})\b", re.I)

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def fetch_text(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def resolve_channel_id(handle):
    html = fetch_text(f"https://www.youtube.com/{handle}")
    m = re.search(r'"externalId":"(UC[\w-]+)"', html) or re.search(
        r'"channelId":"(UC[\w-]+)"', html
    )
    return m.group(1) if m else None


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def clean_series_title(video_title):
    # Strip brackets like [Multi-Sub], (ENG SUB), and everything from Episode/EP onwards
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】", " ", video_title)
    t = re.split(r"\b(?:ep(?:isode)?|#|第)\s*0*\d+", t, maxsplit=1, flags=re.I)[0]
    t = re.sub(r"[\|\-–—:]+$", "", t).strip()
    return re.sub(r"\s+", " ", t)



def load_catalog_index():
    index = {}
    for path in ["data/catalog.json", "catalog.json"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item in items:
                    slug = item.get("slug", "")
                    title = item.get("title", "")
                    if slug and title:
                        norm = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
                        index[norm] = slug
            except Exception:
                pass
    return index

def match_catalog_slug(series_name, catalog_index):
    norm = re.sub(r"[^a-z0-9]+", " ", series_name.lower()).strip()
    if norm in catalog_index:
        return catalog_index[norm]
    for cat_norm, cat_slug in catalog_index.items():
        if len(cat_norm) >= 5 and (cat_norm in norm or norm in cat_norm):
            return cat_slug
    return slugify(series_name)

def main():
    ep_file = "episodes.json"
    data = {}
    if os.path.exists(ep_file):
        try:
            with open(ep_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    catalog_index = load_catalog_index()
    added = 0
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    for ch in OFFICIAL_CHANNELS:
        try:
            cid = resolve_channel_id(ch["handle"])
            if not cid:
                print(f"[Skip] Could not resolve {ch['name']}")
                continue

            xml_text = fetch_text(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
            root = ET.fromstring(xml_text)

            for entry in root.findall("atom:entry", ns):
                title = (entry.findtext("atom:title", "", ns) or "").strip()
                vid = (entry.findtext("yt:videoId", "", ns) or "").strip()
                if not title or not vid or IGNORE_RE.search(title):
                    continue

                m = EP_RE.search(title)
                if not m:
                    continue

                ep_num = str(int(m.group(1)))
                series_name = clean_series_title(title)
                if len(series_name) < 3:
                    continue

                slug = match_catalog_slug(series_name, catalog_index)
                embed_url = f"https://www.youtube.com/embed/{vid}"

                if slug not in data or not isinstance(data[slug], dict):
                    data[slug] = {}

                if ep_num not in data[slug]:
                    data[slug][ep_num] = {
                        "url": embed_url,
                        "source": ch["name"],
                        "region": ch["region"],
                        "title": title,
                    }
                    added += 1

            print(f"[OK] {ch['name']} ({ch['region']})")
        except Exception as e:
            print(f"[Err] {ch['name']}: {e}")

    with open(ep_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done! Added {added} new official YouTube episodes to {ep_file}.")


if __name__ == "__main__":
    main()
