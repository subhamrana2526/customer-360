import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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
from app.models import Customer, ElixirRaw, HubSpotRaw, NewsRaw, PrepBrief, Stage1Output
from app.stage1.news_filter import filter_news
from app.stage1.orders import aggregate
from app.stage1.threads import summarize_threads
from app.stage2.synthesize import synthesize

app = FastAPI(title="Elchemy Customer 360")


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


@app.post("/api/customers/{customer_id}/refresh")
def refresh(customer_id: str):
    customer = _load_customer(customer_id)
    ensure_customer_dirs(customer_id)

    hs = hubspot_conn.pull(customer.customer_id, customer.hubspot_company_id)
    el = elixir_conn.pull(customer.customer_id, customer.elixir_customer_id)
    nw = news_conn.pull(customer.customer_id, customer.company_name)

    rd = raw_dir(customer_id)
    (rd / "hubspot.json").write_text(hs.model_dump_json(indent=2))
    (rd / "elixir.json").write_text(el.model_dump_json(indent=2))
    (rd / "news.json").write_text(nw.model_dump_json(indent=2))

    thread_summaries = summarize_threads(hs)
    order_aggregate = aggregate(el)
    filtered = filter_news(customer, nw)

    stage1_out = Stage1Output(
        customer_id=customer_id,
        generated_at=datetime.now(timezone.utc),
        thread_summaries=thread_summaries,
        order_aggregate=order_aggregate,
        filtered_news=filtered,
    )
    (stage1_dir(customer_id) / "stage1.json").write_text(stage1_out.model_dump_json(indent=2))

    brief = synthesize(customer, stage1_out, _load_product_catalog())
    brief_path(customer_id).write_text(brief.model_dump_json(indent=2))
    return JSONResponse(content=json.loads(brief.model_dump_json()))


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/customers/{customer_id}")
def customer_page(customer_id: str):
    return FileResponse(STATIC_DIR / "customer.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
