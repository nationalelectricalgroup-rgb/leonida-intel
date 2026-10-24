#!/usr/bin/env python3
"""Daily public-source discovery engine for Leonida Intel.

Collects Google News RSS, YouTube Data API results, and matching items from
Google Trends' broad daily trending feed. Saves topic intelligence, a dedicated
ranked video list, and daily topic history.

This is a discovery and ranking tool, not a fact-checker. Labels are heuristic
and must never be presented as verified claims. Respect source terms, quotas,
rate limits, and access policies.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CURRENT_FILE = DATA / "trends.json"
HISTORY_FILE = DATA / "trend-history.json"

USER_AGENT = "LeonidaIntelTrendBot/1.0 (public-source discovery)"
MAX_ITEMS_PER_FEED = 40
ARCHIVE_AFTER_DAYS = 14
YOUTUBE_RESULTS_PER_QUERY = 10
REQUEST_PAUSE_SECONDS = 0.6

NEWS_QUERIES = [
    '"GTA 6" OR "Grand Theft Auto VI"',
    '"GTA 6" trailer OR gameplay OR map',
    '"GTA 6" leak OR rumour OR rumor OR theory',
    '"GTA 6" characters OR locations OR missions',
]

YOUTUBE_QUERIES = [
    "GTA 6 trailer",
    "GTA 6 news",
    "GTA 6 map",
    "GTA 6 gameplay theories",
]

TOPIC_ALIASES = {
    "release date": "GTA 6 release date",
    "release": "GTA 6 release date",
    "trailer": "GTA 6 trailer",
    "map": "GTA 6 map",
    "vice city": "GTA 6 Vice City",
    "leonida": "GTA 6 Leonida",
    "jason": "GTA 6 characters",
    "lucia": "GTA 6 characters",
    "characters": "GTA 6 characters",
    "gameplay": "GTA 6 gameplay",
    "online": "GTA 6 Online",
    "pc": "GTA 6 PC release",
    "mission": "GTA 6 missions",
    "missions": "GTA 6 missions",
    "vehicle": "GTA 6 vehicles",
    "vehicles": "GTA 6 vehicles",
    "soundtrack": "GTA 6 soundtrack",
    "leak": "GTA 6 rumours and leaks",
    "leaks": "GTA 6 rumours and leaks",
    "rumour": "GTA 6 rumours and leaks",
    "rumours": "GTA 6 rumours and leaks",
    "rumor": "GTA 6 rumours and leaks",
    "rumors": "GTA 6 rumours and leaks",
    "theory": "GTA 6 rumours and leaks",
    "theories": "GTA 6 rumours and leaks",
}

STOPWORDS = set("""
the and for with from this that have has are was were will would could should
about after before into over under what when where which who why how your you
they them their there here new latest official says said video videos watch
news update updates grand theft auto rockstar games game gaming gta trailer
gameplay more most some all any each not but its it's his her our today
yesterday explained reaction reacts review theory theories leak leaks rumour
rumours rumor rumors a an to of in on at by as is be it or if we i
""".split())


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_date(value: str) -> datetime | None:
    """Parse common RSS dates and ISO timestamps into an aware UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_text(parent, names) -> str:
    for name in names:
        element = parent.find(name)
        if element is not None and element.text:
            return element.text.strip()
    return ""


def fetch_rss(url: str) -> tuple[list[dict], str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(2_000_000)
        root = ET.fromstring(raw)
        results = []

        for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
            title = get_text(item, ["title"])
            link = get_text(item, ["link"])
            published = get_text(
                item,
                ["pubDate", "{http://purl.org/dc/elements/1.1/}date"],
            )
            if title and link:
                results.append({
                    "title": title,
                    "url": link,
                    "published": published,
                })

        # Atom fallback.
        if not results:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for item in root.findall(".//atom:entry", ns)[:MAX_ITEMS_PER_FEED]:
                title = get_text(item, ["{http://www.w3.org/2005/Atom}title"])
                link_element = item.find("atom:link", ns)
                link = link_element.get("href", "") if link_element is not None else ""
                published = get_text(
                    item,
                    [
                        "{http://www.w3.org/2005/Atom}published",
                        "{http://www.w3.org/2005/Atom}updated",
                    ],
                )
                if title and link:
                    results.append({
                        "title": title,
                        "url": link,
                        "published": published,
                    })
        return results, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def fetch_youtube_videos(query: str) -> tuple[list[dict], str | None]:
    """Fetch up to ten recent matching videos through the official YouTube API."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return [], "YOUTUBE_API_KEY secret is missing"

    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": YOUTUBE_RESULTS_PER_QUERY,
        "order": "date",
        "key": api_key,
    })
    url = "https://www.googleapis.com/youtube/v3/search?" + params
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8"))

        results = []
        for entry in data.get("items", []):
            snippet = entry.get("snippet", {})
            video_id = entry.get("id", {}).get("videoId")
            title = (snippet.get("title") or "").strip()
            if not video_id or not title:
                continue

            results.append({
                "title": title,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "video_id": video_id,
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "channel_name": snippet.get("channelTitle", ""),
                "published": snippet.get("publishedAt", ""),
                "source_type": "video",
                "source_name": "YouTube Data API",
                "query": query,
            })
        return results, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def canonical_topic(title: str) -> str | None:
    """Map genuinely GTA VI-related titles to a controlled topic taxonomy.

    Deliberately rejects titles that merely compare something to GTA 6 or use
    the game as a style reference. This is a relevance filter, not a fact-check.
    """
    lower = re.sub(r"[^a-z0-9\s]", " ", (title or "").lower())
    lower = re.sub(r"\s+", " ", lower).strip()
    game_terms = ("gta 6", "gta vi", "grand theft auto vi", "grand theft auto 6")
    if not any(term in lower for term in game_terms):
        return None

    # Common false positives where GTA is only a comparison, parody, or side mention.
    reject_phrases = (
        "gta 6 style", "gta style", "gta 6 inspired", "gta vi inspired",
        "gta 6 parody", "gta vi parody", "parody trailer", "meme coin",
        "shrek 2", "style trailer", "like gta 6", "gta 6 like",
        "gta 6 vs gta 5", "gta vi vs gta v", "games like gta 6",
        "gta 6 lookalike", "gta 6 clone", "gta 6 competitor",
    )
    if any(phrase in lower for phrase in reject_phrases):
        return None

    # Do not treat a passing comparison or a generic release/news phrase as GTA VI
    # coverage. Require a meaningful game-specific subject cue.
    context_terms = (
        "release", "launch", "trailer", "map", "vice city", "leonida",
        "jason", "lucia", "character", "gameplay", "mission", "story",
        "online", "pc", "platform", "vehicle", "car", "soundtrack",
        "music", "leak", "rumour", "rumor", "theory", "speculation",
        "rockstar", "edition", "preorder", "pre-order", "price", "delay",
        "date", "review", "hands-on", "preview", "feature", "mechanic",
        "world", "location", "weapon", "activity", "business", "wanted",
    )
    if not any(re.search(r"\b" + re.escape(term) + r"\b", lower) for term in context_terms):
        return None

    # Require a direct game-specific cue. Avoid generating categories from arbitrary
    # leftover title words such as “Taking Things” or “Almost Still”.
    aliases = sorted(TOPIC_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
    for needle, topic in aliases:
        if re.search(r"\b" + re.escape(needle) + r"\b", lower):
            return topic

    if any(term in lower for term in ("vice city", "leonida", "lucia", "jason", "rockstar")):
        if "vice city" in lower:
            return "GTA 6 Vice City"
        if "leonida" in lower:
            return "GTA 6 Leonida"
        return "GTA 6 characters"
    return "GTA 6 general discussion"


def classify_evidence(title: str, url: str) -> str:
    """Conservative topic/source heuristic, not a fact-check."""
    lower = title.lower()
    host = urllib.parse.urlparse(url).netloc.lower()
    if any(term in lower for term in (
        "debunked", "fake leak", "false rumour", "false rumor", "fact check",
        "rumour debunked", "rumor debunked", "not true", "hoax exposed",
    )):
        return "debunked"
    if any(term in lower for term in (
        "leak", "rumour", "rumor", "alleged", "unconfirmed",
        "theory", "speculation", "might", "could be"
    )):
        return "rumour_or_theory"
    if host == "rockstargames.com" or host.endswith(".rockstargames.com") or host == "take2games.com" or host.endswith(".take2games.com"):
        return "official_source_needs_review"
    return "reported_or_unverified"


def classify_video(title: str, url: str, channel_name: str = "") -> dict:
    """Return provisional display label and explanation; never claims verification."""
    lower = title.lower()
    host = urllib.parse.urlparse(url).netloc.lower()
    official_channel = any(term in (channel_name or "").lower() for term in (
        "rockstar games", "rockstar north"
    ))
    official_url = (
        host == "rockstargames.com" or host.endswith(".rockstargames.com")
        or host == "take2games.com" or host.endswith(".take2games.com")
    )

    if official_channel or official_url:
        label = "Official source — verify"
        kind = "official"
        note = "Source/channel appears official; verify the specific claim."
    elif any(term in lower for term in (
        "leak", "rumour", "rumor", "theory", "speculation", "what if",
        "fan theory", "prediction", "might", "could be"
    )):
        label = "Speculation / theory"
        kind = "speculation"
        note = "Title-based classification; not independently verified."
    elif any(term in lower for term in (
        "walkthrough", "guide", "tips", "mission", "ending", "secrets",
        "how to", "gameplay", "review", "analysis"
    )):
        label = "Gameplay / guide / analysis"
        kind = "gameplay"
        note = "Title-based classification; check whether this is actual gameplay or pre-release analysis."
    elif any(term in lower for term in (
        "report", "reported", "news", "confirms", "confirmed",
        "announces", "announced", "announcement", "update"
    )):
        label = "Reported news — verify"
        kind = "reported"
        note = "A report is not confirmation; check the linked sources."
    else:
        label = "Unverified video"
        kind = "unverified"
        note = "Not enough information in the title to classify confidently."

    return {
        "content_type": kind,
        "content_label": label,
        "classification_note": note,
    }


def stable_id(value: str) -> str:
    return hashlib.sha1(value.lower().encode("utf-8")).hexdigest()[:12]


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def video_rank_score(video: dict, topic_score: float) -> float:
    """Heuristic video score from topic relevance and freshness."""
    published = parse_date(video.get("published", ""))
    age_days = 30.0
    if published:
        age_days = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)
    freshness = max(0.0, 30.0 - min(age_days, 30.0)) / 30.0 * 20.0
    return round(float(topic_score) * 0.8 + freshness, 1)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    collected = []
    errors = []
    source_counts = Counter()

    # Google News RSS provides article discovery, not Google search volume.
    for query in NEWS_QUERIES:
        url = (
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(query)
            + "&hl=en-GB&gl=GB&ceid=GB:en"
        )
        items, error = fetch_rss(url)
        if error:
            errors.append({"source": "Google News RSS", "query": query, "error": error})
        for item in items:
            item["source_type"] = "news"
            item["source_name"] = "Google News RSS"
            item["query"] = query
            collected.append(item)
            source_counts["news"] += 1
        time.sleep(REQUEST_PAUSE_SECONDS)

    # Collect every returned YouTube result, not just the last item in each query.
    for query in YOUTUBE_QUERIES:
        items, error = fetch_youtube_videos(query)
        if error:
            errors.append({"source": "YouTube Data API", "query": query, "error": error})
        for item in items:
            collected.append(item)
            source_counts["video"] += 1
        time.sleep(REQUEST_PAUSE_SECONDS)

    # Broad daily trending feed; matching titles only, not GTA-specific volume.
    trends_url = "https://trends.google.com/trending/rss?geo=GB"
    items, error = fetch_rss(trends_url)
    if error:
        fallback_items, fallback_error = fetch_rss(
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB"
        )
        if not items:
            items = fallback_items
        if fallback_error and not items:
            errors.append({"source": "Google Trends RSS", "error": fallback_error})
    for item in items:
        if canonical_topic(item["title"]):
            item["source_type"] = "search_trend"
            item["source_name"] = "Google Trends daily trending searches"
            collected.append(item)
            source_counts["search_trend"] += 1

    # Deduplicate URLs while preserving video metadata. Prefer the richer/latest item.
    unique = {}
    for item in collected:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        existing = unique.get(url)
        if existing is None:
            unique[url] = item
        elif item.get("source_type") == "video":
            unique[url] = item
    collected = list(unique.values())

    # Apply relevance filtering before aggregation and video ranking. This prevents
    # unrelated parody/comparison stories from polluting topics and the video feed.
    rejected_count = 0
    relevant_items = []
    for item in collected:
        topic = canonical_topic(item.get("title", ""))
        if topic is None:
            rejected_count += 1
            continue
        item["topic"] = topic
        relevant_items.append(item)
    collected = relevant_items

    previous = load_json(CURRENT_FILE, {"topics": [], "videos": [], "updated_at": None})
    history_doc = load_json(HISTORY_FILE, {"days": []})
    previous_topics = {
        topic["id"]: topic for topic in previous.get("topics", []) if "id" in topic
    }

    observations = defaultdict(list)
    for item in collected:
        topic = canonical_topic(item.get("title", ""))
        if not topic:
            continue
        item["topic"] = topic
        item["evidence_status"] = classify_evidence(item["title"], item["url"])
        observations[topic].append(item)

    today = datetime.now(timezone.utc).date().isoformat()
    allowed_historical_topics = {
        "GTA 6 release date", "GTA 6 trailer", "GTA 6 map", "GTA 6 Vice City",
        "GTA 6 Leonida", "GTA 6 characters", "GTA 6 gameplay", "GTA 6 Online",
        "GTA 6 PC release", "GTA 6 missions", "GTA 6 vehicles",
        "GTA 6 soundtrack", "GTA 6 rumours and leaks", "GTA 6 general discussion",
    }
    all_topic_names = set(observations) | {
        topic.get("name", "") for topic in previous.get("topics", [])
        if topic.get("name", "") in allowed_historical_topics
    }
    topics = []

    for name in sorted(topic_name for topic_name in all_topic_names if topic_name):
        topic_id = stable_id(name)
        old = previous_topics.get(topic_id, {})
        obs = observations.get(name, [])
        source_types = sorted({item["source_type"] for item in obs})
        source_names = sorted({item["source_name"] for item in obs})
        distinct_domains = len({
            urllib.parse.urlparse(item["url"]).netloc.lower() for item in obs
        })
        mention_count = len(obs)

        # Transparent heuristic, not platform-wide popularity.
        # Diminishing returns stop one busy feed query from pushing everything to 100.
        # Distinct domains and independent signal types contribute, but are not proof
        # of truth or platform-wide popularity.
        momentum = min(
            90.0,
            10.0 * min(4, mention_count) ** 0.5
            + 5.0 * min(5, max(0, distinct_domains - 1))
            + 4.0 * min(2, len(source_types)),
        )
        old_score = float(old.get("trend_score", 0) or 0)
        if obs:
            trend_score = round(min(100.0, momentum * 0.8 + old_score * 0.2), 1)
        else:
            trend_score = round(old_score * 0.65, 1)

        previous_active_days = old.get("active_days", 0)
        active_days = (
            previous_active_days + 1
            if obs and old.get("last_seen") != today
            else previous_active_days
        )
        first_seen = old.get("first_seen", today)
        last_seen = today if obs else old.get("last_seen")

        inactive_days = 0
        if last_seen:
            try:
                inactive_days = max(
                    0,
                    (datetime.now(timezone.utc).date()
                     - datetime.fromisoformat(last_seen[:10]).date()).days,
                )
            except ValueError:
                inactive_days = 0

        if obs or inactive_days < 3:
            status = "active"
        elif inactive_days < ARCHIVE_AFTER_DAYS:
            status = "cooling"
        else:
            status = "archived"

        evidence_counts = Counter(item["evidence_status"] for item in obs)
        if not obs:
            evidence_status = "No new sources today — previous status not re-verified"
        elif evidence_counts.get("debunked", 0) == len(obs):
            evidence_status = "debunked — review sources"
        elif evidence_counts.get("official_source_needs_review", 0) == len(obs):
            evidence_status = "official source — verify claim"
        elif evidence_counts.get("rumour_or_theory", 0) == len(obs):
            evidence_status = "rumour / theory"
        elif evidence_counts.get("reported_or_unverified", 0) == len(obs):
            evidence_status = "reported / unverified"
        else:
            evidence_status = "mixed evidence — review sources"

        samples = sorted(
            obs,
            key=lambda item: parse_date(item.get("published", "")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:5]

        topics.append({
            "id": topic_id,
            "name": name,
            "status": status,
            "trend_score": trend_score,
            "evidence_status": evidence_status,
            "evidence_score": None,
            "evidence_score_note": "Not automatically scored; source classification is not fact verification.",
            "mentions_today": mention_count,
            "distinct_domains_today": distinct_domains,
            "signal_types_today": source_types,
            "source_names_today": source_names,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "active_days": active_days,
            "inactive_days": inactive_days,
            "samples": samples,
            "trend_score_method": "Heuristic with diminishing returns from matching feed items, distinct domains, signal types and a small prior-score component; not platform-wide search volume or truth confidence.",
        })

    order = {"active": 0, "cooling": 1, "archived": 2}
    topics.sort(key=lambda topic: (
        order.get(topic["status"], 3),
        -topic["trend_score"],
        topic["name"].lower(),
    ))

    topic_scores = {topic["name"]: topic["trend_score"] for topic in topics}

    # A dedicated video list, independent of the five samples shown per topic.
    videos = []
    seen_video_ids = set()
    for item in collected:
        if item.get("source_type") != "video" or not item.get("video_id"):
            continue
        video_id = item["video_id"]
        if video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)

        topic = item.get("topic") or canonical_topic(item.get("title", "")) or "GTA 6"
        classification = classify_video(
            item.get("title", ""),
            item.get("url", ""),
            item.get("channel_name", ""),
        )
        score = video_rank_score(item, topic_scores.get(topic, 0))
        videos.append({
            "video_id": video_id,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "thumbnail_url": item.get(
                "thumbnail_url",
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            ),
            "channel_name": item.get("channel_name", ""),
            "published": item.get("published", ""),
            "source_name": item.get("source_name", "YouTube Data API"),
            "source_type": "video",
            "topic": topic,
            "topic_trend_score": topic_scores.get(topic, 0),
            "video_rank_score": score,
            **classification,
            "classification_is_heuristic": True,
        })

    videos.sort(key=lambda video: (
        -video["video_rank_score"],
        video.get("published", ""),
        video.get("title", "").lower(),
    ))
    for rank, video in enumerate(videos, start=1):
        video["rank"] = rank

    current_doc = {
        "updated_at": now_iso(),
        "market": "GB",
        "collection_summary": {
            "unique_items": len(collected),
            "news_items": source_counts["news"],
            "video_items": source_counts["video"],
            "saved_unique_videos": len(videos),
            "google_trends_matches": source_counts["search_trend"],
            "irrelevant_items_filtered": rejected_count,
            "errors": errors,
            "notes": [
                "Google News RSS results are content-discovery signals, not Google search volume.",
                "Google Trends feed is a broad daily trending-search feed; only directly matching GTA 6 titles are included.",
                "Video ranks are heuristic scores based on topic score and freshness, not YouTube view counts or platform-wide popularity.",
                "Video classifications are title/source heuristics and are not fact verification.",
                "A relevance filter rejects obvious parody/comparison false positives; manual review is still needed.",
                "Topic evidence labels summarize title/source heuristics and do not verify claims.",
                "A topic with no new sources today is explicitly marked as not re-verified today.",
                "Trend scores use diminishing returns; high scores do not mean a claim is true.",
                "Official-looking channel labels should be checked; an official source does not automatically make every claim true.",
                "Only titles, URLs, thumbnail URLs, channel names and feed metadata are retained; no full article text or video is copied.",
            ],
        },
        "topics": topics,
        "videos": videos,
    }

    day_snapshot = {
        "date": today,
        "topics": [{
            "id": topic["id"],
            "name": topic["name"],
            "status": topic["status"],
            "trend_score": topic["trend_score"],
            "evidence_status": topic["evidence_status"],
            "mentions_today": topic["mentions_today"],
            "distinct_domains_today": topic["distinct_domains_today"],
            "signal_types_today": topic["signal_types_today"],
        } for topic in topics],
    }
    days = [
        day for day in history_doc.get("days", [])
        if day.get("date") != today
    ]
    days.append(day_snapshot)
    days.sort(key=lambda day: day.get("date", ""))
    history_doc = {"updated_at": now_iso(), "days": days[-365:]}

    CURRENT_FILE.write_text(
        json.dumps(current_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    HISTORY_FILE.write_text(
        json.dumps(history_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Updated {len(topics)} topics; collected {len(collected)} unique feed items; "
        f"saved {len(videos)} unique videos."
    )
    print(f"Filtered obvious irrelevant items: {rejected_count}")
    print(f"Feed errors: {len(errors)}")
    for error in errors:
        print(
            f"  ERROR [{error['source']}] "
            f"{error.get('query', '')}: {error['error']}"
        )
    print("Top 10 videos:")
    for video in videos[:10]:
        print(
            f"  #{video['rank']} score={video['video_rank_score']} "
            f"[{video['content_label']}] {video['title']}"
        )
    print("Top 15 topics:")
    for topic in topics[:15]:
        print(
            f"  {topic['status']:8} {topic['trend_score']:5} "
            f"{topic['name']} [{topic['evidence_status']}]"
        )


if __name__ == "__main__":
    main()
