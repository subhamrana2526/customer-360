"""Market Intelligence API.

Self-contained: only imports from app.mi.* and app.config. Does not depend on
Customer 360 connectors / stages / models.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.mi import signals, store


class RecipeItem(BaseModel):
    factor_id: str
    weight_pct: float
    notes: str | None = ""


class UpdateRecipeRequest(BaseModel):
    recipe: list[RecipeItem]

router = APIRouter(prefix="/api/mi", tags=["market-intelligence"])


@router.get("/health")
def health():
    return {"status": "ok", "module": "mi"}


@router.get("/factors")
def list_all_factors():
    """Full factor list — used by UI 'Add factor' dropdown."""
    return store.load_factors()


@router.get("/products")
def list_products():
    """Products with their latest 30-day signal."""
    return signals.all_signals()


@router.get("/products/{product_id}")
def get_product(product_id: str):
    product = store.get_product(product_id)
    if not product:
        raise HTTPException(404, f"Product {product_id} not found")
    recipe = store.get_recipe(product_id)
    enriched_recipe = []
    for r in recipe:
        f = store.get_factor(r["factor_id"]) or {}
        enriched_recipe.append({
            **r,
            "factor_name": f.get("name", r["factor_id"]),
            "category": f.get("category"),
            "unit": f.get("unit"),
        })
    return {
        **product,
        "recipe": enriched_recipe,
        "signal": signals.signal_for_product(product_id),
    }


@router.get("/products/{product_id}/factors")
def get_product_factors(product_id: str):
    """Factor price time series for charting."""
    if not store.get_product(product_id):
        raise HTTPException(404, f"Product {product_id} not found")
    out = []
    for r in store.get_recipe(product_id):
        factor = store.get_factor(r["factor_id"]) or {}
        out.append({
            "factor_id": r["factor_id"],
            "factor_name": factor.get("name", r["factor_id"]),
            "category": factor.get("category"),
            "unit": factor.get("unit"),
            "weight_pct": r["weight_pct"],
            "series": store.get_factor_series(r["factor_id"]),
        })
    return {"product_id": product_id, "factors": out}


@router.put("/products/{product_id}/recipe")
def update_recipe(product_id: str, req: UpdateRecipeRequest):
    """Persist a recipe edit. Validates each factor exists."""
    if not store.get_product(product_id):
        raise HTTPException(404, f"Product {product_id} not found")
    for item in req.recipe:
        if not store.get_factor(item.factor_id):
            raise HTTPException(400, f"Unknown factor: {item.factor_id}")
    store.save_recipe(product_id, [item.model_dump() for item in req.recipe])
    return {"status": "ok", "signal": signals.signal_for_product(product_id)}


@router.get("/factors/{factor_id}/series")
def get_factor_series(factor_id: str):
    """Time series for any factor — used when adding a factor to a recipe."""
    factor = store.get_factor(factor_id)
    if not factor:
        raise HTTPException(404, f"Factor {factor_id} not found")
    return {"factor_id": factor_id, "series": store.get_factor_series(factor_id)}


@router.get("/signals")
def list_signals():
    return signals.all_signals()


@router.post("/refresh")
def refresh():
    """Recompute signals. Ingestion stub — re-reads seed JSON."""
    store.load_factors.cache_clear()
    store.load_products.cache_clear()
    store.load_recipes.cache_clear()
    store._load_prices.cache_clear()
    return {"status": "ok", "signals": signals.all_signals()}
