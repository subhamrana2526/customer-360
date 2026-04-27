"""LLM filter: keeps only news items materially relevant to the customer."""
import json
from datetime import date

from app.config import NEWS_CAP
from app.llm import call_json, load_prompt
from app.models import Customer, FilteredNewsItem, NewsItem, NewsRaw


def _cap_per_category(items: list[NewsItem], cap: int) -> list[NewsItem]:
    by_cat: dict[str, list[NewsItem]] = {"company": [], "macro": [], "industry": []}
    for it in items:
        by_cat.setdefault(it.category, []).append(it)
    out: list[NewsItem] = []
    for cat_items in by_cat.values():
        cat_items.sort(key=lambda i: i.date, reverse=True)
        out.extend(cat_items[:cap])
    return out


def filter_news(customer: Customer, raw: NewsRaw) -> list[FilteredNewsItem]:
    capped = _cap_per_category(raw.items, NEWS_CAP)
    if not capped:
        return []

    serializable = [
        {
            "title": it.title,
            "url": it.url,
            "date": it.date.isoformat(),
            "source": it.source,
            "snippet": it.snippet,
            "category": it.category,
        }
        for it in capped
    ]

    profile = customer.manufacturing_profile
    prompt = (
        load_prompt("news_filter.txt")
        .replace("{company_name}", customer.company_name)
        .replace("{industry}", customer.industry)
        .replace("{sub_industry}", ", ".join(customer.sub_industry or []))
        .replace("{geography}", customer.geography)
        .replace("{products_made}", ", ".join(profile.products_made))
        .replace("{likely_inputs}", ", ".join(profile.likely_inputs))
        .replace("{news_items_json}", json.dumps(serializable, indent=2))
    )

    result = call_json(prompt, purpose="summ")
    kept = result.get("kept", []) or []

    out: list[FilteredNewsItem] = []
    for k in kept:
        try:
            out.append(
                FilteredNewsItem(
                    title=k["title"],
                    url=k.get("url"),
                    date=date.fromisoformat(k["date"]) if isinstance(k.get("date"), str) else k.get("date"),
                    source=k.get("source", ""),
                    snippet=k.get("snippet", ""),
                    category=k.get("category", "company"),
                    why_it_matters=k.get("why_it_matters", ""),
                )
            )
        except Exception:
            continue
    return out
