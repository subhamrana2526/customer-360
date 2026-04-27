"""HubSpot CRM v3 connector — pulls emails for a company."""
from datetime import datetime, timedelta, timezone

import httpx

from app.config import HUBSPOT_TOKEN, HUBSPOT_WINDOW_DAYS
from app.models import HubSpotCall, HubSpotEmail, HubSpotMeeting, HubSpotRaw, InquiredProduct

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


def _pull_deals(client: httpx.Client, company_id: str) -> list[InquiredProduct]:
    deal_ids = _fetch_association_ids(client, company_id, "deals")
    if not deal_ids:
        return []

    deals_raw = _batch_fetch_properties(
        client, "deals", deal_ids, ["dealname", "dealstage", "createdate", "hs_is_closed"]
    )
    deal_meta = {
        r["id"]: r["properties"] for r in deals_raw
    }

    # Collect all line item IDs across all deals, tracking which deal they belong to
    li_id_to_deal: dict[str, str] = {}
    for deal_id in deal_ids:
        resp = client.get(
            f"{BASE}/crm/v3/objects/deals/{deal_id}/associations/line_items",
            headers=_headers(),
        )
        resp.raise_for_status()
        for r in resp.json().get("results", []):
            li_id_to_deal[r["id"]] = deal_id

    if not li_id_to_deal:
        return []

    li_raw = _batch_fetch_properties(
        client, "line_items", list(li_id_to_deal.keys()), ["name", "quantity"]
    )

    # Deduplicate by product name — keep the entry from the most recent deal
    seen: dict[str, InquiredProduct] = {}
    for r in li_raw:
        name = (r["properties"].get("name") or "").strip()
        if not name:
            continue
        deal_id = li_id_to_deal[r["id"]]
        deal_props = deal_meta.get(deal_id, {})
        date_str = (deal_props.get("createdate") or "")[:10]
        try:
            from datetime import date as date_type
            deal_date = date_type.fromisoformat(date_str) if date_str else None
        except ValueError:
            deal_date = None

        qty_raw = r["properties"].get("quantity")
        qty = float(qty_raw) if qty_raw else None

        product = InquiredProduct(
            name=name,
            deal_name=deal_props.get("dealname") or "",
            deal_stage=deal_props.get("dealstage"),
            deal_date=deal_date,
            quantity=qty,
            is_open_deal=deal_props.get("hs_is_closed") != "true",
        )
        # Keep latest by date
        if name not in seen or (deal_date and (seen[name].deal_date is None or deal_date > seen[name].deal_date)):
            seen[name] = product

    return sorted(seen.values(), key=lambda p: p.deal_date or date_type.min, reverse=True)


def pull(customer_id: str, hubspot_company_id: str | None) -> HubSpotRaw:
    """Pull last HUBSPOT_WINDOW_DAYS of emails for a company."""
    now = datetime.now(timezone.utc)

    if not HUBSPOT_TOKEN or not hubspot_company_id:
        return HubSpotRaw(customer_id=customer_id, pulled_at=now)

    cutoff = now - timedelta(days=HUBSPOT_WINDOW_DAYS)

    with httpx.Client(timeout=30) as client:
        emails = _pull_emails(client, hubspot_company_id, cutoff)
        inquired_products = _pull_deals(client, hubspot_company_id)

    return HubSpotRaw(
        customer_id=customer_id,
        pulled_at=now,
        emails=emails,
        meetings=[],
        calls=[],
        inquired_products=inquired_products,
    )
