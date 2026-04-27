"""Freight matrix loader — reads freight_matrix.json → seed_prices.json."""
import json
from pathlib import Path

from app.config import BACKEND_ROOT

MI_DATA_DIR = BACKEND_ROOT / "data" / "mi"
SEED_PRICES_FILE = MI_DATA_DIR / "seed_prices.json"
FREIGHT_FILE = MI_DATA_DIR / "freight_matrix.json"


def update_seed_prices() -> None:
    if not FREIGHT_FILE.exists():
        print("[freight] freight_matrix.json not found, skipping")
        return

    matrix = json.loads(FREIGHT_FILE.read_text())
    existing: dict = {}
    if SEED_PRICES_FILE.exists():
        existing = json.loads(SEED_PRICES_FILE.read_text())

    for route_key, months in matrix.items():
        factor_id = route_key  # keys already include "freight_" prefix
        series = [
            {"date": f"{m['month']}-01", "price": m["price_usd_per_container"]}
            for m in months
        ]
        series.sort(key=lambda x: x["date"])
        existing[factor_id] = series
        print(f"[freight] {factor_id}: {len(series)} monthly points")

    SEED_PRICES_FILE.write_text(json.dumps(existing, indent=2))
    print(f"[freight] wrote {SEED_PRICES_FILE}")
