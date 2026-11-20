import re
from typing import Any

import isodate  # pip install isodate

BAD = re.compile(
    r"\b(trailer|pv|teaser|reaction|review|amv|recap|preview|promo clip|fancap|shorts?)\b",
    re.I,
)
LOCKED = re.compile(
    r"\b(members?[- ]only|membership|ultra)\b",
    re.I,
)
EP = re.compile(
    r"\b(?:episodes?|ep\.?|e)\s*0*(\d{1,4})(?:\s*[-–—]\s*0*(\d{1,4}))?\b",
    re.I,
)


def check_video(
    video: dict[str, Any],
    countries: list[str] | tuple[str, ...],
    min_minutes: int = 15,
) -> dict[str, int | None] | None:
    """
    Validate a YouTube Data API v3 videos.list item (parts: snippet, contentDetails, status).
    Returns {'episode': int | None, 'last_episode': int | None} if valid, or None if rejected.
    """
    st = video.get("status", {})
    cd = video.get("contentDetails", {})
    sn = video.get("snippet", {})

    if st.get("privacyStatus") != "public" or not st.get("embeddable"):
        return None

    if st.get("uploadStatus") != "processed":
        return None

    if sn.get("liveBroadcastContent", "none") != "none":
        return None

    duration_str = cd.get("duration")
    if not duration_str:
        return None

    try:
        seconds = isodate.parse_duration(duration_str).total_seconds()
    except Exception:
        return None

    if seconds < min_minutes * 60:
        return None

    title = sn.get("title", "")
    desc_prefix = sn.get("description", "")[:300]
    text = f"{title} {desc_prefix}"

    if BAD.search(title) or LOCKED.search(text):
        return None

    rr = cd.get("regionRestriction", {})
    blocked = rr.get("blocked", ())
    allowed = rr.get("allowed")

    if any(c in blocked for c in countries):
        return None

    if allowed is not None and not all(c in allowed for c in countries):
        return None

    match = EP.search(title)
    if not match:
        # Unclear episode numbering -> send to manual review queue
        return {"episode": None, "last_episode": None}

    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    return {"episode": first, "last_episode": last}
