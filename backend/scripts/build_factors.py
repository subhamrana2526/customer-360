"""Generate data/mi/factors.json from data/sunsirs_products.json.

Run once (or whenever sunsirs_products.json changes):
    python scripts/build_factors.py
"""
import json
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
SUNSIRS_FILE = BACKEND_ROOT / "data" / "sunsirs_products.json"
OUT_FILE = BACKEND_ROOT / "data" / "mi" / "factors.json"

# Non-sunsirs factors to append (FX + freight)
EXTRA_FACTORS = [
    {
        "id": "fx_usd_inr",
        "name": "USD/INR",
        "category": "fx",
        "source": "rbi",
        "source_url": "https://api.frankfurter.app",
        "sunsirs_id": None,
        "unit": "INR per USD",
    },
    {
        "id": "fx_usd_cny",
        "name": "USD/CNY",
        "category": "fx",
        "source": "rbi",
        "source_url": "https://api.frankfurter.app",
        "sunsirs_id": None,
        "unit": "CNY per USD",
    },
    {
        "id": "freight_in_us_east",
        "name": "Freight India → US East",
        "category": "freight",
        "source": "internal",
        "source_url": None,
        "sunsirs_id": None,
        "unit": "USD/container",
    },
]

CATEGORY_MAP = {
    "Energy": "energy",
    "Chemical": "raw_material",
}


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def extract_sunsirs_id(url: str) -> int | None:
    m = re.search(r"prodetail-(\d+)", url)
    return int(m.group(1)) if m else None


def main():
    products = json.loads(SUNSIRS_FILE.read_text())

    factors = []
    seen_ids: set[str] = set()

    for p in products:
        fid = slugify(p["name"])
        # Deduplicate (shouldn't happen but be safe)
        base = fid
        n = 1
        while fid in seen_ids:
            fid = f"{base}_{n}"
            n += 1
        seen_ids.add(fid)

        sid = extract_sunsirs_id(p["url"])
        factors.append({
            "id": fid,
            "name": p["name"],
            "category": CATEGORY_MAP.get(p["category"], "raw_material"),
            "source": "sunsirs",
            "source_url": p["url"],
            "sunsirs_id": sid,
            "unit": "RMB/ton",
        })

    factors.extend(EXTRA_FACTORS)

    OUT_FILE.write_text(json.dumps(factors, indent=2))
    sunsirs_count = len([f for f in factors if f["source"] == "sunsirs"])
    print(f"Wrote {len(factors)} factors ({sunsirs_count} SunSirs + {len(EXTRA_FACTORS)} extra) → {OUT_FILE}")

    # Print mapping for recipe updates
    print("\nKey factor IDs for recipes.json:")
    for name in ["Toluene", "Caustic soda", "Hydrochloric acid", "LPG"]:
        match = next((f for f in factors if f["name"].lower() == name.lower()), None)
        if match:
            print(f"  {name} → {match['id']}")


if __name__ == "__main__":
    main()
