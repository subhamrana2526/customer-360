"""HubSpot CRM v3 connector — pulls emails, meetings, calls for a company.

Stub: returns empty/seeded data when HUBSPOT_TOKEN is unset. Wire real
endpoints during Block 1 when token is available.
"""
from datetime import datetime, timezone

import httpx

from app.config import HUBSPOT_TOKEN, HUBSPOT_WINDOW_DAYS
from app.models import HubSpotCall, HubSpotEmail, HubSpotMeeting, HubSpotRaw

BASE = "https://api.hubapi.com"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}


def pull(customer_id: str, hubspot_company_id: str | None) -> HubSpotRaw:
    """Pull last HUBSPOT_WINDOW_DAYS of emails/meetings/calls for a company.

    TODO(block-1): implement real fetch. For now, returns empty raw envelope
    so the rest of the pipeline can run end-to-end.
    """
    now = datetime.now(timezone.utc)
    if not HUBSPOT_TOKEN or not hubspot_company_id:
        return HubSpotRaw(customer_id=customer_id, pulled_at=now)

    emails: list[HubSpotEmail] = []
    meetings: list[HubSpotMeeting] = []
    calls: list[HubSpotCall] = []

    # TODO: implement
    # 1. GET /crm/v3/objects/companies/{id}/associations/emails
    # 2. Batch fetch emails via /crm/v3/objects/emails/batch/read with hs_email_text
    # 3. Same for meetings and calls
    # 4. Filter to last HUBSPOT_WINDOW_DAYS
    _ = (httpx, HUBSPOT_WINDOW_DAYS, BASE, _headers)

    return HubSpotRaw(
        customer_id=customer_id,
        pulled_at=now,
        emails=emails,
        meetings=meetings,
        calls=calls,
    )
