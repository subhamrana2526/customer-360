"""Elixir connector — pulls orders and inquiries for a customer.

Falls back to mock JSON in data/mocks/elixir/{customer_id}.json when the
real API is not configured. Lets the rest of the pipeline run end-to-end.
"""
import json
from datetime import datetime, timezone

from app.config import DATA_DIR, ELIXIR_BASE_URL, ELIXIR_TOKEN
from app.models import ElixirRaw, Inquiry, Order


def _mock_path(customer_id: str):
    return DATA_DIR / "mocks" / "elixir" / f"{customer_id}.json"


def pull(customer_id: str, elixir_customer_id: str | None) -> ElixirRaw:
    now = datetime.now(timezone.utc)

    if not ELIXIR_BASE_URL or not ELIXIR_TOKEN or not elixir_customer_id:
        return _load_mock(customer_id, now)

    # TODO(block-1): real Elixir API calls once Mehul provides specs.
    # GET {ELIXIR_BASE_URL}/customers/{id}/orders
    # GET {ELIXIR_BASE_URL}/customers/{id}/inquiries
    return _load_mock(customer_id, now)


def _load_mock(customer_id: str, pulled_at: datetime) -> ElixirRaw:
    path = _mock_path(customer_id)
    if not path.exists():
        return ElixirRaw(customer_id=customer_id, pulled_at=pulled_at)
    data = json.loads(path.read_text())
    orders = [Order(**o) for o in data.get("orders", [])]
    inquiries = [Inquiry(**i) for i in data.get("inquiries", [])]
    return ElixirRaw(
        customer_id=customer_id,
        pulled_at=pulled_at,
        orders=orders,
        inquiries=inquiries,
    )
