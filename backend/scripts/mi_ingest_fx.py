"""Refresh FX rates in seed_prices.json from frankfurter.app."""
import sys
sys.path.insert(0, ".")

from app.mi.ingest.rbi import update_seed_prices

if __name__ == "__main__":
    update_seed_prices(days=60)
