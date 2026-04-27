"""MI data store — JSON-backed for the skeleton phase.

Will be replaced by SQLite/SQLModel when ingestion lands. Keeping the function
signatures stable so the swap is a one-file change.
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.config import BACKEND_ROOT

MI_DATA_DIR = BACKEND_ROOT / "data" / "mi"


@lru_cache(maxsize=1)
def load_factors() -> list[dict]:
    return json.loads((MI_DATA_DIR / "factors.json").read_text())


@lru_cache(maxsize=1)
def load_products() -> list[dict]:
    return json.loads((MI_DATA_DIR / "products.json").read_text())


@lru_cache(maxsize=1)
def load_recipes() -> dict[str, list[dict]]:
    return json.loads((MI_DATA_DIR / "recipes.json").read_text())


@lru_cache(maxsize=1)
def _load_prices() -> dict[str, list[dict]]:
    p = MI_DATA_DIR / "seed_prices.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def get_product(product_id: str) -> dict | None:
    return next((p for p in load_products() if p["id"] == product_id), None)


def get_factor(factor_id: str) -> dict | None:
    return next((f for f in load_factors() if f["id"] == factor_id), None)


def get_recipe(product_id: str) -> list[dict]:
    return load_recipes().get(product_id, [])


def save_recipe(product_id: str, recipe: list[dict]) -> None:
    """Persist a recipe edit back to recipes.json and bust the cache."""
    recipes = load_recipes().copy()
    recipes[product_id] = recipe
    (MI_DATA_DIR / "recipes.json").write_text(json.dumps(recipes, indent=2))
    load_recipes.cache_clear()


def get_factor_series(factor_id: str) -> list[dict]:
    """Return [{date, price}] sorted ascending."""
    return _load_prices().get(factor_id, [])


def latest_price(factor_id: str) -> float | None:
    series = get_factor_series(factor_id)
    return series[-1]["price"] if series else None


def price_on_or_before(factor_id: str, target: date) -> float | None:
    series = get_factor_series(factor_id)
    for point in reversed(series):
        if date.fromisoformat(point["date"]) <= target:
            return point["price"]
    return None
