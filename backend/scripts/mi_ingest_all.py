"""Run all MI ingestors and populate data/mi/seed_prices.json.

Usage:
    python -m scripts.mi_ingest_all
"""
import json
from pathlib import Path

from app.config import BACKEND_ROOT
from app.mi.ingest import freight, rbi, sunsirs
from app.mi.store import load_factors

MI_DATA_DIR = BACKEND_ROOT / "data" / "mi"
SEED_PRICES_FILE = MI_DATA_DIR / "seed_prices.json"


def upsert(existing: dict, new_data: dict) -> dict:
    """Merge new_data into existing without clobbering unrelated keys."""
    return {**existing, **new_data}


def main() -> None:
    factors = load_factors()

    # Load existing prices (preserve any hand-edited data)
    existing: dict = {}
    if SEED_PRICES_FILE.exists():
        existing = json.loads(SEED_PRICES_FILE.read_text())

    # 1. SunSirs — OCR all 45 charts
    print("=" * 50)
    print("STEP 1: SunSirs chart OCR")
    print("=" * 50)
    sunsirs_data = sunsirs.ingest_all(factors)
    existing = upsert(existing, sunsirs_data)
    SEED_PRICES_FILE.write_text(json.dumps(existing, indent=2))
    print(f"-> SunSirs: {len(sunsirs_data)} factors ingested\n")

    # 2. FX rates
    print("=" * 50)
    print("STEP 2: FX rates (frankfurter.app)")
    print("=" * 50)
    rbi.update_seed_prices(days=90)
    existing = json.loads(SEED_PRICES_FILE.read_text())
    print()

    # 3. Freight
    print("=" * 50)
    print("STEP 3: Freight matrix")
    print("=" * 50)
    freight.update_seed_prices()
    existing = json.loads(SEED_PRICES_FILE.read_text())
    print()

    # Summary
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    total_points = sum(len(v) for v in existing.values())
    print(f"Total factors with data: {len(existing)}")
    print(f"Total price points: {total_points}")
    for fid, series in sorted(existing.items()):
        if series:
            print(f"  {fid:<35} {len(series):>4} pts  ({series[0]['date']} → {series[-1]['date']})")


if __name__ == "__main__":
    main()
