#!/usr/bin/env python3
"""Low-cost daily trend discovery for Leonida Intel.

Uses public RSS endpoints only. It does not scrape full articles, bypass access
controls, or infer that a popular topic is factually true.
"""
from __future__ import annotations
import json
import re
import time
import os
import hashlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CURRENT_FILE = DATA / "trends.json"
HISTORY_FILE = DATA / "trend-history.json"
USER_AGENT = "LeonidaIntelTrendBot/1.0 (public RSS trend discovery)"
MAX_ITEMS_PER_FEED = 40
ARCHIVE_AFTER_DAYS = 14

# RSS endpoints are used for discovery and metadata only. Respect each site's
# terms, rate limits, robots guidance and any changes to access policies.
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
SEED_TOPICS = [
    "GTA 6 release date", "GTA 6 trailer", "GTA 6 map",
    "GTA 6 characters", "GTA 6 gameplay", "GTA 6 PC release",
    "GTA 6 online", "GTA 6 rumours and leaks", "GTA 6 story",
    "GTA 6 missions", "GTA 6 vehicles", "GTA 6 soundtrack",
    "GTA 6 Vice City", "GTA 6 Leonida",
]
STOPWORDS = set("""
the and for with from this that have has are was were will would could should
about after before into over under what when where which who why how your you
they them their there here new latest official says said video videos watch
news update updates grand theft auto rockstar games game gaming gta grand
trailer gameplay more most some all any each not but its it's his her our
today yesterday explained reaction reacts review theory theories leak leaks
rumour rumours rumor rumors a an to of in on at by as is be it or if we i
""".split())
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

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def get_text(parent, names):
    for name in names:
        el = parent.find(name)
        if el is not None and el.text:
            return el.text.strip()
    return ""

def fetch_rss(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(2_000_000)
        root = ET.fromstring(raw)
        results = []
        for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
            title = get_text(item, ["title"])
            link = get_text(item, ["link"])
            pubdate = get_text(item, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])
            if title and link:
                results.append({"title": title, "url": link, "published": pubdate})
        # Atom fallback
        if not results:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for item in root.findall(".//atom:entry", ns)[:MAX_ITEMS_PER_FEED]:
                title = get_text(item, ["{http://www.w3.org/2005/Atom}title"])
                link_el = item.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                published = get_text(item, ["{http://www.w3.org/2005/Atom}published",
                                            "{http://www.w3.org/2005/Atom}updated"])
                if title and link:
                    results.append({"title": title, "url": link, "published": published})
        return results, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
        
def fetch_youtube_videos(query):
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return [], "YOUTUBE_API_KEY secret is missing"

    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 10,
        "order": "date",
        "key": api_key,
    })
    url = "https://www.googleapis.com/youtube/v3/search?" + params
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8"))

        results = []
        for entry in data.get("items", []):
            snippet = entry.get("snippet", {})
            video_id = entry.get("id", {}).get("videoId")
            title = snippet.get("title", "")

            if not video_id or not title:
                continue

            results.append({
                "title": title,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "published": snippet.get("publishedAt", ""),
            })

        return results, None

    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

def canonical_topic(title):
    lower = re.sub(r"[^a-z0-9\s]", " ", title.lower())
    lower = re.sub(r"\s+", " ", lower).strip()
    if not any(x in lower for x in ("gta 6", "gta vi", "grand theft auto vi", "grand theft auto 6")):
        return None
    # Prefer explicit subject aliases that appear in title.
    for needle, topic in sorted(TOPIC_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if needle in lower:
            return topic
    words = [w for w in lower.split() if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
    if not words:
        return "GTA 6 general discussion"
    # A stable broad bucket avoids creating a new topic for every headline.
    return "GTA 6 " + " ".join(words[:2]).title()

def classify_evidence(title, url):
    lower = title.lower()
    host = urllib.parse.urlparse(url).netloc.lower()
    if any(x in lower for x in ("debunked", "fake leak", "false rumour", "false rumor")):
        return "debunked"
    if any(x in lower for x in ("leak", "rumour", "rumor", "alleged", "unconfirmed", "theory", "speculation")):
        return "rumour_or_theory"
    if any(x in host for x in ("rockstargames.com", "take2games.com")):
        return "official_source_needs_review"
    return "reported_or_unverified"

def stable_id(topic):
    return hashlib.sha1(topic.lower().encode("utf-8")).hexdigest()[:12]

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    collected = []
    errors = []
    source_counts = Counter()

    # Google News RSS search results are a news-discovery signal, NOT raw Google
    # search volume. Google Trends' public daily feed is a separate, broad signal.
    for query in NEWS_QUERIES:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-GB&gl=GB&ceid=GB:en"
        items, err = fetch_rss(url)
        if err: errors.append({"source": "Google News RSS", "error": err})
        for item in items:
            item["source_type"] = "news"
            item["source_name"] = "Google News RSS"
            collected.append(item)
            source_counts["news"] += 1
        time.sleep(0.6)

    for query in YOUTUBE_QUERIES:
        url = "https://www.youtube.com/feeds/videos.xml?search_query=" + urllib.parse.quote(query)
        items, err = fetch_rss(url)
        if err: errors.append({"source": "YouTube RSS", "error": err})
        for item in items:
            item["source_type"] = "video"
            item["source_name"] = "YouTube RSS"
            collected.append(item)
            source_counts["video"] += 1
        time.sleep(0.6)

    # Broad Google Trends daily trending searches feed. It only contributes when
    # the trending title itself clearly mentions GTA 6; it is not keyword-level
    # search volume and may legitimately produce no matching items.
    trends_url = "https://trends.google.com/trending/rss?geo=GB"
    items, err = fetch_rss(trends_url)
    if err:
        # Legacy endpoint fallback
        items2, err2 = fetch_rss("https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB")
        items = items or items2
        if err2 and not items:
            errors.append({"source": "Google Trends RSS", "error": err2})
    for item in items:
        if canonical_topic(item["title"]):
            item["source_type"] = "search_trend"
            item["source_name"] = "Google Trends daily trending searches"
            collected.append(item)
            source_counts["search_trend"] += 1

    # Deduplicate by canonical URL and collect topic observations.
    unique = {}
    for item in collected:
        url = item.get("url", "").strip()
        if url:
            unique[url] = item
    collected = list(unique.values())

    previous = load_json(CURRENT_FILE, {"topics": [], "updated_at": None})
    history_doc = load_json(HISTORY_FILE, {"days": []})
    previous_topics = {x["id"]: x for x in previous.get("topics", []) if "id" in x}
    observations = defaultdict(list)
    for item in collected:
        topic = canonical_topic(item["title"])
        if not topic:
            continue
        item["topic"] = topic
        item["evidence_status"] = classify_evidence(item["title"], item["url"])
        observations[topic].append(item)

    today = datetime.now(timezone.utc).date().isoformat()
    all_topic_names = set(observations) | {x.get("name", "") for x in previous.get("topics", [])}
    topics = []
    for name in sorted(n for n in all_topic_names if n):
        tid = stable_id(name)
        old = previous_topics.get(tid, {})
        obs = observations.get(name, [])
        source_types = sorted({x["source_type"] for x in obs})
        source_names = sorted({x["source_name"] for x in obs})
        unique_sources = len({urllib.parse.urlparse(x["url"]).netloc.lower() for x in obs})
        item_count = len(obs)
        # Transparent heuristic score, not a claim of platform-wide popularity.
        momentum = min(100, item_count * 12 + max(0, unique_sources - 1) * 8 + len(source_types) * 5)
        old_score = old.get("trend_score", 0)
        trend_score = round(min(100, momentum * 0.7 + old_score * 0.3), 1) if obs else round(old_score * 0.72, 1)
        prior_days = old.get("active_days", 0)
        active_days = prior_days + 1 if obs and old.get("last_seen") != today else prior_days
        first_seen = old.get("first_seen", today)
        last_seen = today if obs else old.get("last_seen")
        inactive_days = 0
        if last_seen:
            try:
                inactive_days = max(0, (datetime.now(timezone.utc).date() - datetime.fromisoformat(last_seen[:10]).date()).days)
            except ValueError:
                inactive_days = 0
        status = "active" if obs or inactive_days < 3 else ("cooling" if inactive_days < ARCHIVE_AFTER_DAYS else "archived")
        evidence = Counter(x["evidence_status"] for x in obs)
        if evidence.get("debunked"):
            evidence_status = "debunked"
        elif evidence.get("official_source_needs_review"):
            evidence_status = "official source — verify claim"
        elif evidence.get("rumour_or_theory"):
            evidence_status = "rumour / theory"
        elif obs:
            evidence_status = "reported / unverified"
        else:
            evidence_status = old.get("evidence_status", "unverified")
        samples = sorted(obs, key=lambda x: x.get("published", ""), reverse=True)[:5]
        topics.append({
            "id": tid, "name": name, "status": status,
            "trend_score": trend_score,
            "evidence_status": evidence_status,
            "evidence_score": None,
            "evidence_score_note": "Not automatically scored; source classification is not fact verification.",
            "mentions_today": item_count,
            "distinct_domains_today": unique_sources,
            "signal_types_today": source_types,
            "source_names_today": source_names,
            "first_seen": first_seen, "last_seen": last_seen,
            "active_days": active_days, "inactive_days": inactive_days,
            "samples": samples,
            "trend_score_method": "Heuristic from matching feed items, distinct domains, signal types, and prior score; not platform-wide search volume."
        })

    # Sort active topics first by score. Keep archived records for historical retrieval.
    order = {"active": 0, "cooling": 1, "archived": 2}
    topics.sort(key=lambda x: (order.get(x["status"], 3), -x["trend_score"], x["name"].lower()))
    current_doc = {
        "updated_at": now_iso(),
        "market": "GB",
        "collection_summary": {
            "unique_items": len(collected),
            "news_items": source_counts["news"],
            "video_items": source_counts["video"],
            "google_trends_matches": source_counts["search_trend"],
            "errors": errors,
            "notes": [
                "Google News RSS results are content-discovery signals, not Google search volume.",
                "Google Trends feed is a broad daily trending-search feed; only directly matching GTA 6 titles are included.",
                "No factual claims are automatically verified. Evidence status is a cautious title/source heuristic.",
                "No full article text or video is copied; only title, URL and feed metadata are retained."
            ]
        },
        "topics": topics
    }
    day_snapshot = {
        "date": today,
        "topics": [{
            "id": t["id"], "name": t["name"], "status": t["status"],
            "trend_score": t["trend_score"], "evidence_status": t["evidence_status"],
            "mentions_today": t["mentions_today"],
            "distinct_domains_today": t["distinct_domains_today"],
            "signal_types_today": t["signal_types_today"]
        } for t in topics]
    }
    days = [d for d in history_doc.get("days", []) if d.get("date") != today]
    days.append(day_snapshot)
    days.sort(key=lambda d: d.get("date", ""))
    history_doc = {"updated_at": now_iso(), "days": days[-365:]}

    CURRENT_FILE.write_text(json.dumps(current_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    HISTORY_FILE.write_text(json.dumps(history_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Updated {len(topics)} topics; collected {len(collected)} unique feed items.")
    print(f"Feed errors: {len(errors)}")
    for error in errors:
        print(f"  ERROR [{error['source']}]: {error['error']}")
    for topic in topics[:15]:
        print(f"{topic['status']:8} {topic['trend_score']:5} {topic['name']} [{topic['evidence_status']}]")

if __name__ == "__main__":
    main()
