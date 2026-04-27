"""Pure-Python aggregator over Elixir order/inquiry history."""
from collections import defaultdict
from datetime import date

from app.models import ElixirRaw, OrderAggregate


def aggregate(raw: ElixirRaw) -> OrderAggregate:
    today = date.today()
    orders = raw.orders
    inquiries = raw.inquiries

    total_orders = len(orders)
    total_value_ytd = sum(o.total_value for o in orders if o.date.year == today.year)
    last_order_date = max((o.date for o in orders), default=None)
    days_since = (today - last_order_date).days if last_order_date else None

    product_totals: dict[str, dict] = defaultdict(
        lambda: {"qty": 0.0, "value": 0.0, "last_ordered": None}
    )
    for o in orders:
        for p in o.products:
            name = p.get("name") or p.get("grade") or "unknown"
            product_totals[name]["qty"] += float(p.get("qty", 0) or 0)
            product_totals[name]["value"] += float(p.get("value", 0) or 0)
            prev = product_totals[name]["last_ordered"]
            product_totals[name]["last_ordered"] = (
                o.date if prev is None or o.date > prev else prev
            )

    top_products = sorted(
        (
            {
                "name": name,
                "qty": v["qty"],
                "value": v["value"],
                "last_ordered": v["last_ordered"].isoformat() if v["last_ordered"] else None,
            }
            for name, v in product_totals.items()
        ),
        key=lambda x: x["value"],
        reverse=True,
    )[:5]

    inquiry_count = len(inquiries)
    converted = sum(1 for i in inquiries if i.converted_to_order)
    rate = (converted / inquiry_count) if inquiry_count else 0.0

    ordered_products = {p.get("name") for o in orders for p in o.products if p.get("name")}
    inquired = {p for i in inquiries for p in i.products_requested}
    gaps = sorted(inquired - ordered_products)

    _closed_statuses = {"delivered", "completed", "cancelled", "closed", "rejected"}
    open_order_products = sorted({
        p.get("name")
        for o in orders
        if o.status.lower() not in _closed_statuses
        for p in o.products
        if p.get("name")
    })

    return OrderAggregate(
        customer_id=raw.customer_id,
        total_orders=total_orders,
        total_value_ytd=total_value_ytd,
        last_order_date=last_order_date,
        days_since_last_order=days_since,
        top_products=top_products,
        inquiry_count=inquiry_count,
        inquiry_to_order_rate=rate,
        products_inquired_not_ordered=gaps,
        open_order_products=open_order_products,
    )
