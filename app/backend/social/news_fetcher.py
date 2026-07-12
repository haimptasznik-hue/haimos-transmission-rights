"""
news_fetcher.py — Fetches renewable energy news from RSS feeds.
Covers: Australia (NEM), New Zealand, USA, Hydrogen, EV, Global clean energy.
"""

import feedparser
import time
from datetime import datetime, timezone
from typing import List, Dict

# ── RSS Feed Sources ──────────────────────────────────────────────────────────
FEEDS = [
    # Australia / NEM
    {"label": "RenewEconomy",       "url": "https://reneweconomy.com.au/feed/",          "region": "Australia"},
    {"label": "PV Magazine AU",     "url": "https://www.pv-magazine-australia.com/feed/", "region": "Australia"},
    {"label": "Energy Monitor AU",  "url": "https://www.energymonitor.ai/feed/",          "region": "Global"},
    {"label": "AEMO News",          "url": "https://aemo.com.au/newsroom/feed",            "region": "NEM"},

    # New Zealand
    {"label": "Good Electricity NZ","url": "https://www.goodelectricity.co.nz/feed/",     "region": "New Zealand"},
    {"label": "Stuff NZ Energy",    "url": "https://www.stuff.co.nz/environment/rss",     "region": "New Zealand"},

    # USA
    {"label": "CleanTechnica",      "url": "https://cleantechnica.com/feed/",             "region": "USA"},
    {"label": "Electrek",           "url": "https://electrek.co/feed/",                   "region": "USA"},
    {"label": "Utility Dive",       "url": "https://www.utilitydive.com/feeds/news/",     "region": "USA"},
    {"label": "PV Magazine USA",    "url": "https://www.pv-magazine-usa.com/feed/",       "region": "USA"},

    # Hydrogen
    {"label": "H2 View",            "url": "https://www.h2-view.com/feed/",               "region": "Hydrogen"},
    {"label": "Hydrogen Insight",   "url": "https://hydrogeninsight.com/feed/",           "region": "Hydrogen"},

    # EV
    {"label": "InsideEVs",          "url": "https://insideevs.com/feed/",                 "region": "EV"},
    {"label": "EV Adoption",        "url": "https://evadoption.com/feed/",                "region": "EV"},

    # Global
    {"label": "Bloomberg NEF",      "url": "https://about.bnef.com/blog/feed/",           "region": "Global"},
    {"label": "Carbon Brief",       "url": "https://www.carbonbrief.org/feed",             "region": "Global"},
]

KEYWORDS = [
    "solar", "wind", "battery", "storage", "hydrogen", "renewable", "clean energy",
    "EV", "electric vehicle", "grid", "BESS", "VPP", "NEM", "AEMO", "offshore",
    "onshore", "lithium", "green energy", "net zero", "decarbonisation", "decarbonization",
    "power purchase", "PPA", "curtailment", "frequency", "firming", "capacity",
    "interconnector", "rooftop solar", "community battery", "microgrid"
]


def _is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def fetch_news(max_per_feed: int = 5) -> List[Dict]:
    """Fetch and return relevant articles from all RSS feeds."""
    articles = []

    for feed_cfg in FEEDS:
        try:
            parsed = feedparser.parse(feed_cfg["url"])
            count = 0
            for entry in parsed.entries:
                if count >= max_per_feed:
                    break
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                link    = entry.get("link", "")

                # Parse published date
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                    except Exception:
                        published = None

                if not title or not link:
                    continue
                if not _is_relevant(title, summary):
                    continue

                articles.append({
                    "title":     title,
                    "summary":   summary[:500],
                    "link":      link,
                    "source":    feed_cfg["label"],
                    "region":    feed_cfg["region"],
                    "published": published or datetime.now(timezone.utc).isoformat(),
                })
                count += 1
        except Exception:
            # Silently skip failed feeds — don't crash the pipeline
            continue

    # Sort by newest first (best effort)
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles


if __name__ == "__main__":
    items = fetch_news()
    print(f"Fetched {len(items)} relevant articles")
    for a in items[:5]:
        print(f"[{a['region']}] {a['source']}: {a['title']}")
