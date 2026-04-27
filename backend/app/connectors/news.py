"""News connector — Google News RSS per-company + macro feed loader."""
import json
from datetime import date, datetime, timezone
from urllib.parse import quote

import feedparser
import requests

from app.config import MACRO_NEWS_FILE
from app.models import NewsItem, NewsRaw

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _google_news_url(company_name: str) -> str:
    return (
        f"https://news.google.com/rss/search?q=%22{quote(company_name)}%22"
        f"&hl=en-US&gl=US&ceid=US:en"
    )


def _parse_pubdate(entry) -> date:
    try:
        if entry.get("published_parsed"):
            t = entry.published_parsed
            return date(t.tm_year, t.tm_mon, t.tm_mday)
    except Exception:
        pass
    return date.today()


def fetch_company_news(company_name: str, limit: int = 30) -> list[NewsItem]:
    url = _google_news_url(company_name)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as exc:
        print(f"[news] fetch failed for {company_name!r}: {exc}")
        return []

    items: list[NewsItem] = []
    for entry in feed.entries[:limit]:
        items.append(
            NewsItem(
                title=entry.get("title", ""),
                url=entry.get("link"),
                date=_parse_pubdate(entry),
                source=entry.get("source", {}).get("title", "Google News")
                if isinstance(entry.get("source"), dict)
                else "Google News",
                snippet=entry.get("summary", "")[:500],
                category="company",
            )
        )
    return items


def load_macro_news() -> list[NewsItem]:
    if not MACRO_NEWS_FILE.exists():
        return []
    payload = json.loads(MACRO_NEWS_FILE.read_text())
    items: list[NewsItem] = []
    for day in payload:
        d = date.fromisoformat(day["date"])
        source = day.get("source", "")
        for it in day.get("items", []):
            items.append(
                NewsItem(
                    title=it.get("title", ""),
                    url=it.get("url"),
                    date=d,
                    source=source,
                    snippet=it.get("summary", ""),
                    category=it.get("category", "macro"),
                )
            )
    return items


def pull(customer_id: str, company_name: str) -> NewsRaw:
    company = fetch_company_news(company_name)
    macro = load_macro_news()
    return NewsRaw(
        customer_id=customer_id,
        pulled_at=datetime.now(timezone.utc),
        items=company + macro,
    )
