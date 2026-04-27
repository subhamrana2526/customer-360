import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import (
    CUSTOMERS_FILE,
    PRODUCT_CATALOG_FILE,
    STATIC_DIR,
    brief_path,
    ensure_customer_dirs,
    raw_dir,
    stage1_dir,
)
from app.connectors import elixir as elixir_conn
from app.connectors import hubspot as hubspot_conn
from app.connectors import news as news_conn
from app.llm import call_json
from app.mi.routes import router as mi_router
from app.models import Customer, ElixirRaw, HubSpotRaw, ManufacturingProfile, NewsRaw, PrepBrief, Stage1Output
from app.stage1.news_filter import filter_news
from app.stage1.orders import aggregate
from app.stage1.threads import summarize_threads
from app.stage2.synthesize import synthesize

app = FastAPI(title="Elchemy Customer 360")
app.include_router(mi_router)


def _load_customers() -> list[Customer]:
    if not CUSTOMERS_FILE.exists():
        return []
    return [Customer(**c) for c in json.loads(CUSTOMERS_FILE.read_text())]


def _load_customer(customer_id: str) -> Customer:
    for c in _load_customers():
        if c.customer_id == customer_id:
            return c
    raise HTTPException(404, f"Customer {customer_id} not found")


def _load_product_catalog() -> list[dict]:
    if not PRODUCT_CATALOG_FILE.exists():
        return []
    return json.loads(PRODUCT_CATALOG_FILE.read_text())


class AddCustomerRequest(BaseModel):
    company_name: str
    hubspot_company_id: str = ""
    elixir_customer_id: str = ""


def _infer_customer_profile(company_name: str) -> dict:
    """Use LLM to infer industry, geography, and manufacturing profile from company name."""
    prompt = f"""You are a B2B specialty chemicals industry expert.
Given only the company name below, infer the most likely profile.

Company: {company_name}

Return ONLY valid JSON:
{{
  "industry": "<one of: F&F, Personal Care, Food, Home Care, Pharma, Industrial, Other>",
  "sub_industry": ["<specific sub-categories, 1-3 items>"],
  "segment": "<one of: end_user, distributor>",
  "geography": "<country or region, e.g. Italy, India, USA, Europe>",
  "manufacturing_profile": {{
    "products_made": ["<what this company likely manufactures, 2-4 items>"],
    "scale": "<one of: Small, Mid-size, Large, Enterprise>",
    "likely_inputs": ["<raw material inputs they likely buy, 3-5 items>"]
  }}
}}

Be specific but conservative — only infer what the company name clearly suggests."""
    result = call_json(prompt, purpose="summ")
    return result


def _save_customer(customer: Customer) -> None:
    customers = []
    if CUSTOMERS_FILE.exists():
        customers = json.loads(CUSTOMERS_FILE.read_text())
    # Replace if exists, otherwise append
    customers = [c for c in customers if c["customer_id"] != customer.customer_id]
    customers.append(json.loads(customer.model_dump_json()))
    CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2))


def _run_pipeline(customer: Customer) -> PrepBrief:
    ensure_customer_dirs(customer.customer_id)

    hs = hubspot_conn.pull(customer.customer_id, customer.hubspot_company_id)
    el = elixir_conn.pull(customer.customer_id, customer.elixir_customer_id)
    nw = news_conn.pull(customer.customer_id, customer.company_name)

    rd = raw_dir(customer.customer_id)
    (rd / "hubspot.json").write_text(hs.model_dump_json(indent=2))
    (rd / "elixir.json").write_text(el.model_dump_json(indent=2))
    (rd / "news.json").write_text(nw.model_dump_json(indent=2))

    thread_summaries = summarize_threads(hs)
    order_aggregate = aggregate(el)
    filtered = filter_news(customer, nw)

    stage1_out = Stage1Output(
        customer_id=customer.customer_id,
        generated_at=datetime.now(timezone.utc),
        thread_summaries=thread_summaries,
        order_aggregate=order_aggregate,
        filtered_news=filtered,
        inquired_products=hs.inquired_products,
    )
    (stage1_dir(customer.customer_id) / "stage1.json").write_text(stage1_out.model_dump_json(indent=2))

    brief = synthesize(customer, stage1_out)
    brief_path(customer.customer_id).write_text(brief.model_dump_json(indent=2))
    return brief


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/customers")
def list_customers():
    return [c.model_dump(mode="json") for c in _load_customers()]


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    return _load_customer(customer_id).model_dump(mode="json")


@app.get("/api/customers/{customer_id}/brief")
def get_brief(customer_id: str):
    _load_customer(customer_id)
    path = brief_path(customer_id)
    if not path.exists():
        raise HTTPException(404, "Brief not generated yet. POST /refresh first.")
    return JSONResponse(content=json.loads(path.read_text()))


@app.get("/api/customers/{customer_id}/raw")
def get_raw(customer_id: str):
    _load_customer(customer_id)
    out: dict = {}
    rd = raw_dir(customer_id)
    for name in ("hubspot", "elixir", "news"):
        p = rd / f"{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text())
    return out


@app.get("/api/customers/{customer_id}/stage1")
def get_stage1(customer_id: str):
    _load_customer(customer_id)
    p = stage1_dir(customer_id) / "stage1.json"
    if not p.exists():
        raise HTTPException(404, "Stage1 not generated yet.")
    return json.loads(p.read_text())


@app.post("/api/customers")
def add_customer(req: AddCustomerRequest):
    """Create a new customer by inferring profile via LLM, then run the full pipeline."""
    # Generate a stable ID from the company name
    slug = re.sub(r"[^a-z0-9]+", "-", req.company_name.lower()).strip("-")[:30]
    customer_id = f"{slug}-{uuid.uuid4().hex[:6]}"

    # LLM-infer profile fields from company name
    try:
        inferred = _infer_customer_profile(req.company_name)
    except Exception as e:
        print(f"[add_customer] profile inference failed: {e}, using defaults")
        inferred = {}

    mfg = inferred.get("manufacturing_profile", {})
    customer = Customer(
        customer_id=customer_id,
        company_name=req.company_name,
        industry=inferred.get("industry", "Other"),
        sub_industry=inferred.get("sub_industry"),
        segment=inferred.get("segment", "end_user"),
        geography=inferred.get("geography", "Unknown"),
        hubspot_company_id=req.hubspot_company_id or None,
        elixir_customer_id=req.elixir_customer_id or None,
        manufacturing_profile=ManufacturingProfile(
            products_made=mfg.get("products_made", []),
            scale=mfg.get("scale", ""),
            likely_inputs=mfg.get("likely_inputs", []),
        ),
    )

    _save_customer(customer)

    try:
        brief = _run_pipeline(customer)
        return JSONResponse(content={
            "customer_id": customer_id,
            "customer": json.loads(customer.model_dump_json()),
            "brief": json.loads(brief.model_dump_json()),
        })
    except Exception as e:
        # Customer is saved even if pipeline fails — can refresh later
        raise HTTPException(500, f"Customer saved but pipeline failed: {e}")


@app.post("/api/customers/{customer_id}/refresh")
def refresh(customer_id: str):
    customer = _load_customer(customer_id)
    brief = _run_pipeline(customer)
    return JSONResponse(content=json.loads(brief.model_dump_json()))


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/customers/{customer_id}")
def customer_page(customer_id: str):
    return FileResponse(STATIC_DIR / "customer.html")


@app.get("/customers/{customer_id}/stage1")
def stage1_page(customer_id: str):
    return FileResponse(STATIC_DIR / "stage1.html")


@app.get("/mi")
def mi_index_page():
    return FileResponse(STATIC_DIR / "mi" / "index.html")


@app.get("/mi/products/{product_id}")
def mi_product_page(product_id: str):
    return FileResponse(STATIC_DIR / "mi" / "product.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
