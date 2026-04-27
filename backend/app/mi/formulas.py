"""Formula engine — additive weighted-sum of factor % changes.

Multiplicative variant will land alongside the formula editor; the skeleton
only ships additive (the default the recipe generates)."""
from datetime import date, timedelta

from app.mi import store


def default_coefficients(product_id: str) -> dict[str, float]:
    """Coefficients = recipe weight_pct / 100."""
    return {r["factor_id"]: r["weight_pct"] / 100.0 for r in store.get_recipe(product_id)}


def evaluate_additive(
    coefficients: dict[str, float],
    window_days: int = 90,
    end_date: date | None = None,
) -> dict:
    """Σ (coef_i × pct_change_i)  over the window."""
    end_date = end_date or _latest_data_date()
    start_date = end_date - timedelta(days=window_days)

    contributions: list[dict] = []
    predicted = 0.0
    factors_with_data = 0

    for factor_id, coef in coefficients.items():
        start = store.price_on_or_before(factor_id, start_date)
        end = store.price_on_or_before(factor_id, end_date)
        if start is None or end is None or start == 0:
            continue
        pct_change = (end - start) / start
        weighted = coef * pct_change
        predicted += weighted
        factors_with_data += 1
        contributions.append({
            "factor_id": factor_id,
            "factor_name": (store.get_factor(factor_id) or {}).get("name", factor_id),
            "start_price": round(start, 4),
            "end_price": round(end, 4),
            "pct_change": round(pct_change, 4),
            "coefficient": coef,
            "weighted_contribution": round(weighted, 4),
        })

    contributions.sort(key=lambda c: abs(c["weighted_contribution"]), reverse=True)

    if abs(predicted) < 0.01:
        direction = "flat"
    elif predicted > 0:
        direction = "up"
    else:
        direction = "down"

    return {
        "window_days": window_days,
        "end_date": end_date.isoformat(),
        "factor_contributions": contributions,
        "predicted_pct_change": round(predicted, 4),
        "direction": direction,
        "confidence_note": f"Based on {factors_with_data} of {len(coefficients)} factors with fresh data",
    }


def _latest_data_date() -> date:
    """Latest date that exists in any seeded factor series."""
    latest: date | None = None
    for factor in store.load_factors():
        series = store.get_factor_series(factor["id"])
        if series:
            d = date.fromisoformat(series[-1]["date"])
            if latest is None or d > latest:
                latest = d
    return latest or date.today()
