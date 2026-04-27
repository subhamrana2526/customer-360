"""FX rate ingestor using frankfurter.app (free, no auth required).

Fetches USD/INR and USD/CNY daily rates and writes them into
data/mi/seed_prices.json alongside the other factor series.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import requests

from app.config import BACKEND_ROOT

MI_DATA_DIR = BACKEND_ROOT / "data" / "mi"
SEED_PRICES_FILE = MI_DATA_DIR / "seed_prices.json"

_BASE_URL = "https://api.frankfurter.app"
_HEADERS = {"User-Agent": "elchemy-mi/1.0"}

FACTOR_MAP = {
    "INR": "fx_usd_inr",
    "CNY": "fx_usd_cny",
}


def fetch_fx_series(days: int = 60) -> dict[str, list[dict]]:
    end = date.today()
    start = end - timedelta(days=days)
    url = f"{_BASE_URL}/{start}..{end}?from=USD&to=INR,CNY"
    r = requests.get(url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()

    series: dict[str, list[dict]] = {"fx_usd_inr": [], "fx_usd_cny": []}
    for date_str, rates in sorted(data.get("rates", {}).items()):
        for currency, factor_id in FACTOR_MAP.items():
            if currency in rates:
                series[factor_id].append({"date": date_str, "price": rates[currency]})
    return series


def update_seed_prices(days: int = 60) -> None:
    """Fetch real FX rates and upsert into seed_prices.json."""
    print(f"[rbi] fetching USD/INR and USD/CNY for last {days} days...")
    fx = fetch_fx_series(days=days)

    existing: dict = {}
    if SEED_PRICES_FILE.exists():
        existing = json.loads(SEED_PRICES_FILE.read_text())

    for factor_id, series in fx.items():
        existing[factor_id] = series
        print(f"[rbi] {factor_id}: {len(series)} data points "
              f"({series[0]['date']} → {series[-1]['date']})")

    SEED_PRICES_FILE.write_text(json.dumps(existing, indent=2))
    print(f"[rbi] wrote {SEED_PRICES_FILE}")


if __name__ == "__main__":
    update_seed_prices()
