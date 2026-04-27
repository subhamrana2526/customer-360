"""Group HubSpot emails into threads, summarize each via LLM."""
import re
from collections import defaultdict
from datetime import date

from app.llm import call_json, load_prompt
from app.models import HubSpotRaw, ThreadSummary

# Matches the start of a quoted reply block in various email clients.
# Outlook: "Da: Name <email>\nInviato: ..."  /  "From: Name <email>\nSent: ..."
# Gmail:   "On Mon, 1 Jan 2024, Name <email> wrote:"
# Plain:   Lines starting with ">"
_QUOTE_PATTERNS = re.compile(
    r"(^>.*$"
    r"|^(-{2,}\s*Original Message\s*-{2,}).*"
    r"|^(Da|From)\s*:.+\n(Inviato|Sent)\s*:.*"
    r"|^On\s+.+wrote\s*:\s*$)",
    re.MULTILINE | re.IGNORECASE,
)

# Signature delimiter: standalone "--" line
_SIG_DELIMITER = re.compile(r"^\s*--\s*$", re.MULTILINE)

# Legal disclaimer marker common in Italian corporate email
_DISCLAIMER_MARKER = re.compile(
    r"(questo messaggio|this message has been sent|please consider your environmental)",
    re.IGNORECASE,
)


def _strip_body(body: str) -> str:
    """Remove quoted reply chains, signatures, and legal disclaimers."""
    # Cut at signature delimiter
    sig_match = _SIG_DELIMITER.search(body)
    if sig_match:
        body = body[: sig_match.start()]

    # Cut at legal disclaimer
    disc_match = _DISCLAIMER_MARKER.search(body)
    if disc_match:
        body = body[: disc_match.start()]

    # Remove lines that are part of a quoted block
    lines = body.splitlines()
    clean: list[str] = []
    in_quote_header = False
    for line in lines:
        stripped = line.strip()
        # Skip blank lines only if we're inside a quote block
        if _QUOTE_PATTERNS.match(line):
            in_quote_header = True
            continue
        if in_quote_header and not stripped:
            continue
        in_quote_header = False
        clean.append(line)

    return "\n".join(clean).strip()


_MAX_BODY_CHARS = 1500


def _format_email(e) -> str:
    ts = e.timestamp.isoformat() if e.timestamp else ""
    body = _strip_body(e.body_text)
    if len(body) > _MAX_BODY_CHARS:
        body = body[:_MAX_BODY_CHARS] + "\n[truncated]"
    return (
        f"--- {ts} | {e.direction} | from {e.from_address} ---\n"
        f"Subject: {e.subject}\n\n{body}\n"
    )


def _truncate_thread(emails: list, max_keep: int = 20) -> list:
    if len(emails) <= max_keep:
        return emails
    head = 5
    tail = max_keep - head
    return emails[:head] + emails[-tail:]


_MAX_THREADS = 10


def summarize_threads(raw: HubSpotRaw) -> list[ThreadSummary]:
    by_thread: dict[str, list] = defaultdict(list)
    for email in raw.emails:
        by_thread[email.thread_id].append(email)

    # Keep only the 10 most recent threads (by latest email in each thread)
    by_thread = dict(
        sorted(by_thread.items(), key=lambda kv: max(e.timestamp for e in kv[1]), reverse=True)[
            :_MAX_THREADS
        ]
    )

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
