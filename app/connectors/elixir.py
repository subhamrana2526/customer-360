"""Elixir connector — pulls sale orders for a customer from the real API.

API: GET https://api-v2.elchemy.com/api/orders/sale-orders/
Auth: Authorization: Bearer <ELIXIR_TOKEN>  +  api-key: <ELIXIR_API_KEY>

Falls back to mock JSON in data/mocks/elixir/{customer_id}.json when
credentials are not configured.
"""
import json
from datetime import datetime, timezone

import httpx

from app.config import DATA_DIR, ELIXIR_API_KEY, ELIXIR_BASE_URL, ELIXIR_TOKEN
from app.models import ElixirRaw, Inquiry, Order

ORDERS_PATH = "/api/orders/sale-orders/"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {ELIXIR_TOKEN}",
        "api-key": ELIXIR_API_KEY,
        "Accept": "application/json",
    }


def _parse_order(raw: dict) -> Order:
    """Map one sale-order result from the API into our Order model."""
    # Collect all delivery items across all deliveries
    products: list[dict] = []
    total_value = 0.0
    currency = raw.get("unit_of_currency", "USD")

    for delivery in raw.get("deliveries", []):
        for di in delivery.get("delivery_items", []):
            oi = di.get("order_item", {})
            pg = oi.get("product_grade", {})
            name = oi.get("product_name", pg.get("display_name", ""))
            grade = oi.get("grade_name", "")
            qty = float(di.get("total_quantity") or 0)
            value = float(oi.get("total_amount_with_additional_charges") or 0)
            products.append({
                "name": name,
                "grade": grade,
                "qty": qty,
                "unit": raw.get("unit_of_weight", "MT"),
                "value": value,
            })
            total_value += value

    # Use created_at as the order date
    date_str = raw.get("created_at", "")[:10]
    try:
        from datetime import date
        order_date = date.fromisoformat(date_str)
    except Exception:
        order_date = datetime.now(timezone.utc).date()

    return Order(
        order_id=raw.get("display_id") or raw.get("id", ""),
        date=order_date,
        products=products,
        total_value=total_value or float(raw.get("total_amount") or 0),
        currency=currency,
        status=raw.get("status", ""),
    )


def _fetch_all_orders(elixir_customer_id: str) -> list[Order]:
    orders: list[Order] = []
    page = 1
    while True:
        params = {
            "customer_id_list": elixir_customer_id,
            "sort_by": "-created_at",
            "page_size": 50,
            "page": page,
        }
        resp = httpx.get(
            f"{ELIXIR_BASE_URL}{ORDERS_PATH}",
            headers=_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {})
        results = data.get("results", [])
        for r in results:
            orders.append(_parse_order(r))
        if page >= data.get("total_pages", 1):
            break
        page += 1
    return orders


def _mock_path(customer_id: str):
    return DATA_DIR / "mocks" / "elixir" / f"{customer_id}.json"


def _load_mock(customer_id: str, pulled_at: datetime) -> ElixirRaw:
    path = _mock_path(customer_id)
    if not path.exists():
        return ElixirRaw(customer_id=customer_id, pulled_at=pulled_at)
    data = json.loads(path.read_text())
    orders = [Order(**o) for o in data.get("orders", [])]
    inquiries = [Inquiry(**i) for i in data.get("inquiries", [])]
    return ElixirRaw(customer_id=customer_id, pulled_at=pulled_at, orders=orders, inquiries=inquiries)


def pull(customer_id: str, elixir_customer_id: str | None) -> ElixirRaw:
    now = datetime.now(timezone.utc)

    if not ELIXIR_TOKEN or not ELIXIR_API_KEY or not elixir_customer_id:
        return _load_mock(customer_id, now)

    try:
        orders = _fetch_all_orders(elixir_customer_id)
        # Inquiries endpoint not yet available — fall back to mock inquiries if present
        mock = _load_mock(customer_id, now)
        return ElixirRaw(
            customer_id=customer_id,
            pulled_at=now,
            orders=orders,
            inquiries=mock.inquiries,
        )
    except Exception as e:
        print(f"   [elixir] API error for {customer_id}: {e} — falling back to mock")
        return _load_mock(customer_id, now)
