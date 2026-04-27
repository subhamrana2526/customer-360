"""HubSpot CRM v3 connector — pulls emails for a company."""
from datetime import datetime, timedelta, timezone

import httpx

from app.config import HUBSPOT_TOKEN, HUBSPOT_WINDOW_DAYS
from app.models import HubSpotCall, HubSpotEmail, HubSpotMeeting, HubSpotRaw

BASE = "https://api.hubapi.com"
BATCH_SIZE = 100

_DIRECTION_MAP = {
    "EMAIL": "outgoing",
    "FORWARDED_EMAIL": "outgoing",
    "INCOMING_EMAIL": "incoming",
    "REPLY_TO": "incoming",
}


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}


def _fetch_association_ids(client: httpx.Client, company_id: str, object_type: str) -> list[str]:
    ids: list[str] = []
    url = f"{BASE}/crm/v3/objects/companies/{company_id}/associations/{object_type}"
    params: dict = {"limit": BATCH_SIZE}

    while True:
        resp = client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        ids.extend(r["id"] for r in data.get("results", []))
        next_page = data.get("paging", {}).get("next", {})
        if not next_page:
            break
        params = {"limit": BATCH_SIZE, "after": next_page["after"]}

    return ids


def _batch_fetch_properties(
    client: httpx.Client, object_type: str, ids: list[str], properties: list[str]
) -> list[dict]:
    results: list[dict] = []
    for i in range(0, len(ids), BATCH_SIZE):
        chunk = ids[i : i + BATCH_SIZE]
        resp = client.post(
            f"{BASE}/crm/v3/objects/{object_type}/batch/read",
            headers=_headers(),
            json={"properties": properties, "inputs": [{"id": id_} for id_ in chunk]},
        )
        resp.raise_for_status()
        results.extend(resp.json().get("results", []))
    return results


def _pull_emails(client: httpx.Client, company_id: str, cutoff: datetime) -> list[HubSpotEmail]:
    ids = _fetch_association_ids(client, company_id, "emails")
    if not ids:
        return []

    raw = _batch_fetch_properties(
        client,
        "emails",
        ids,
        [
            "hs_email_text",
            "hs_email_subject",
            "hs_timestamp",
            "hs_email_direction",
            "hs_email_from_email",
            "hs_email_to_email",
            "hs_email_thread_id",
        ],
    )

    emails: list[HubSpotEmail] = []
    for r in raw:
        p = r["properties"]
        ts_str = p.get("hs_timestamp") or p.get("hs_createdate", "")
        if not ts_str:
            continue
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts < cutoff:
            continue

        direction = _DIRECTION_MAP.get(p.get("hs_email_direction", "EMAIL"), "outgoing")
        to_raw = p.get("hs_email_to_email") or ""
        to_addresses = [a.strip() for a in to_raw.split(";") if a.strip()]

        emails.append(
            HubSpotEmail(
                id=r["id"],
                thread_id=p.get("hs_email_thread_id") or r["id"],
                timestamp=ts,
                direction=direction,
                from_address=p.get("hs_email_from_email") or "",
                to_addresses=to_addresses,
                subject=p.get("hs_email_subject") or "",
                body_text=p.get("hs_email_text") or "",
            )
        )

    return sorted(emails, key=lambda e: e.timestamp)


def pull(customer_id: str, hubspot_company_id: str | None) -> HubSpotRaw:
    """Pull last HUBSPOT_WINDOW_DAYS of emails for a company."""
    now = datetime.now(timezone.utc)

    if not HUBSPOT_TOKEN or not hubspot_company_id:
        return HubSpotRaw(customer_id=customer_id, pulled_at=now)

    cutoff = now - timedelta(days=HUBSPOT_WINDOW_DAYS)

    with httpx.Client(timeout=30) as client:
        emails = _pull_emails(client, hubspot_company_id, cutoff)

    return HubSpotRaw(
        customer_id=customer_id,
        pulled_at=now,
        emails=emails,
        meetings=[],
        calls=[],
    )
