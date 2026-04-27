"""MI signal generation — runs the default formula for each product and
returns a directional signal + headline driver."""
from typing import Any

from app.mi import formulas, store


def _summary_line(product_name: str, result: dict) -> str:
    if not result["factor_contributions"]:
        return f"{product_name}: no factor data available."
    top = result["factor_contributions"][0]
    direction_word = {"up": "up", "down": "down", "flat": "flat"}[result["direction"]]
    pct = abs(round(result["predicted_pct_change"] * 100, 1))
    top_pct = round(top["pct_change"] * 100, 1)
    top_dir = "up" if top_pct > 0 else "down"
    return (
        f"{top['factor_name']} {top_dir} {abs(top_pct)}% drove "
        f"{product_name} estimate {direction_word} {pct}%"
    )


def signal_for_product(product_id: str, window_days: int = 30) -> dict:
    product = store.get_product(product_id)
    if not product:
        return {}
    coefs = formulas.default_coefficients(product_id)
    result = formulas.evaluate_additive(coefs, window_days=window_days)
    return {
        "product_id": product_id,
        "product_name": product["name"],
        "family": product.get("family"),
        "direction": result["direction"],
        "pct_change": result["predicted_pct_change"],
        "window_days": result["window_days"],
        "end_date": result["end_date"],
        "top_drivers": result["factor_contributions"][:3],
        "summary_line": _summary_line(product["name"], result),
    }


def all_signals(window_days: int = 30) -> list[dict]:
    return [signal_for_product(p["id"], window_days) for p in store.load_products()]


def get_for_customer(customer: Any) -> list[dict]:
    """Customer 360 hook. Empty until customer→product mapping is wired."""
    relevant = getattr(customer, "relevant_products", None) or []
    return [signal_for_product(pid) for pid in relevant if store.get_product(pid)]
