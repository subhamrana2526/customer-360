"""Group HubSpot emails into threads, summarize each via LLM."""
from collections import defaultdict
from datetime import date

from app.llm import call_json, load_prompt
from app.models import HubSpotRaw, ThreadSummary


def _format_email(e) -> str:
    ts = e.timestamp.isoformat() if e.timestamp else ""
    return (
        f"--- {ts} | {e.direction} | from {e.from_address} ---\n"
        f"Subject: {e.subject}\n\n{e.body_text}\n"
    )


def _truncate_thread(emails: list, max_keep: int = 20) -> list:
    if len(emails) <= max_keep:
        return emails
    head = 5
    tail = max_keep - head
    return emails[:head] + emails[-tail:]


def summarize_threads(raw: HubSpotRaw) -> list[ThreadSummary]:
    by_thread: dict[str, list] = defaultdict(list)
    for email in raw.emails:
        by_thread[email.thread_id].append(email)

    prompt_template = load_prompt("thread_summary.txt")
    summaries: list[ThreadSummary] = []

    for thread_id, emails in by_thread.items():
        emails.sort(key=lambda e: e.timestamp)
        kept = _truncate_thread(emails)
        thread_text = "\n".join(_format_email(e) for e in kept)
        prompt = prompt_template.replace("{thread_emails}", thread_text)

        result = call_json(prompt, purpose="summ")

        participants = sorted(
            {e.from_address for e in emails} | {a for e in emails for a in e.to_addresses}
        )
        date_start = min(e.timestamp.date() for e in emails) if emails else date.today()
        date_end = max(e.timestamp.date() for e in emails) if emails else date.today()

        summaries.append(
            ThreadSummary(
                thread_id=thread_id,
                date_start=date_start,
                date_end=date_end,
                participants=participants,
                summary=result.get("summary", ""),
                open_items=result.get("open_items", []),
                sentiment=result.get("sentiment", "neutral"),
                key_products_discussed=result.get("key_products_discussed", []),
            )
        )

    summaries.sort(key=lambda s: s.date_end, reverse=True)
    return summaries
