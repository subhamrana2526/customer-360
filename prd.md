# Elchemy Customer 360 + Market Intelligence — Project State & Handoff

> **Last updated:** 2026-04-27
> **Status:** Customer 360 fully working in production. Market Intelligence skeleton built — data ingestion is next.

---

## What Is Built

Two modules in a single FastAPI backend, isolated from each other:

| Module | Status |
|---|---|
| **Customer 360** | Fully working. Real HubSpot emails, real Elixir orders, live Google News, LLM brief generation. |
| **Market Intelligence** | Skeleton complete. Routes, formula engine, and signal UI all work — on **seed/fake price data**. Real ingestion (SunSirs, RBI FX) is the remaining work. |

---

## Running the Project

```bash
# From repo root
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`. Two tabs: **Customer 360** and **Market Intelligence**.

To regenerate briefs for all customers:
```bash
python -m scripts.pull_all      # fetch HubSpot + Elixir + News
python -m scripts.stage1_all    # summarize threads, aggregate orders, filter news
python -m scripts.stage2_all    # synthesize prep brief
```

---

## Folder Structure (current)

```
customer-360-backend/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI routes (Customer 360 + MI)
│   │   ├── config.py               # env vars, paths
│   │   ├── models.py               # Pydantic models (Customer 360 only)
│   │   ├── llm.py                  # OpenAI wrapper (JSON mode, retry)
│   │   ├── connectors/
│   │   │   ├── hubspot.py          # HubSpot CRM v3 (real)
│   │   │   ├── elixir.py           # Elixir orders API (real)
│   │   │   └── news.py             # Google News RSS via requests+feedparser (real)
│   │   ├── stage1/
│   │   │   ├── threads.py          # email thread summarizer (gpt-4o-mini)
│   │   │   ├── orders.py           # order aggregator (pure Python)
│   │   │   └── news_filter.py      # news relevance filter (gpt-4o-mini)
│   │   ├── stage2/
│   │   │   └── synthesize.py       # brief synthesis (gpt-4o)
│   │   ├── prompts/                # LLM prompt templates
│   │   └── mi/                     # Market Intelligence module (isolated)
│   │       ├── routes.py           # /api/mi/* endpoints
│   │       ├── store.py            # data layer (JSON-backed for now)
│   │       ├── formulas.py         # additive formula engine
│   │       ├── signals.py          # signal generation + C360 hook
│   │       └── ingest/             # ingestion stubs (to be implemented)
│   │           ├── sunsirs.py      # STUB — SunSirs chart OCR
│   │           ├── rbi.py          # STUB — RBI FX rates
│   │           └── freight.py      # STUB — freight matrix loader
│   ├── data/
│   │   ├── customers.json          # 2 real customers seeded
│   │   ├── product_catalog.json    # Elchemy product catalog
│   │   ├── macro_news.json         # macro news feed (manual JSON)
│   │   ├── cache/                  # per-customer JSON cache
│   │   │   └── {customer_id}/
│   │   │       ├── raw/            # hubspot.json, elixir.json, news.json
│   │   │       ├── stage1/         # stage1.json
│   │   │       └── brief.json
│   │   └── mi/                     # MI seed data
│   │       ├── factors.json        # 7 factors (toluene, NaOH, chlorine, LPG, FX, freight)
│   │       ├── products.json       # 5 toluene derivatives
│   │       ├── recipes.json        # cost structure per product (real chemistry weights)
│   │       ├── freight_matrix.json # manual freight rates (India → US East/West)
│   │       └── seed_prices.json    # FAKE — 60-day random walk prices (replace with real)
│   └── scripts/
│       ├── pull_all.py             # batch pull raw data
│       ├── stage1_all.py           # batch run Stage 1
│       ├── stage2_all.py           # batch run Stage 2
│       ├── mi_ingest_all.py        # TO BUILD — runs all MI ingestors
│       └── mi_compute_signals.py   # TO BUILD — recomputes signals from DB
├── frontend/
│   ├── index.html                  # homepage with tab strip
│   ├── customer.html               # C360 customer detail + brief
│   ├── stage1.html / stage1.js     # Stage 1 detail view
│   ├── app.js / style.css          # shared JS + CSS
│   └── mi/
│       ├── index.html              # MI dashboard (5 product cards)
│       ├── product.html            # MI product detail (charts + recipe)
│       ├── mi.js                   # MI frontend logic
│       └── mi.css                  # MI styles
├── intelligencePlatformPrd.md      # original MI PRD (architecture reference)
└── prd.md                          # this file
```

---

## Environment Variables (backend/.env)

```
OPENAI_API_KEY=...
OPENAI_MODEL_SYNTH=gpt-4o
OPENAI_MODEL_SUMM=gpt-4o-mini

HUBSPOT_TOKEN=...
HUBSPOT_WINDOW_DAYS=180

ELIXIR_BASE_URL=https://api-v2.elchemy.com
ELIXIR_TOKEN=...
ELIXIR_API_KEY=...

DATA_DIR=./data
CACHE_DIR=./data/cache

MI_DB_PATH=./data/mi.db         # for future SQLite migration
```

---

## Customer 360 — What's Real vs Stubbed

### Real and working
- **HubSpot connector** — pulls emails via CRM v3 API, grouped into threads. Cleans quoted reply chains and legal disclaimers from email bodies. Caps at 10 most recent threads to avoid token overflow.
- **Elixir connector** — pulls real sale orders via `GET /api/orders/sale-orders/` with Bearer + API key auth. Parses nested `deliveries → delivery_items → order_item` structure.
- **Google News connector** — fetches RSS via `requests` with browser User-Agent (important: bare `feedparser.parse(url)` is blocked by Google). Query uses full company name in exact-phrase form (`%22...%22`) with US locale.
- **Stage 1** — thread summarizer (gpt-4o-mini), order aggregator (pure Python), news relevance filter (gpt-4o-mini). All cached to JSON per customer.
- **Stage 2** — synthesis brief (gpt-4o). Cached to `brief.json`.
- **UI** — customer list, customer detail with Conversation Recap / Customer Snapshot / What's New / Market Context / Pitch Angles / Conversation Starters. Stage 1 detail page (`/customers/{id}/stage1`) with formatted thread cards, order stats, news items.

### Known limitations / decisions
- Thread summarizer caps at **10 threads** max and **1500 chars per email body** to avoid context overflow.
- `TL;DR` card was removed from the customer detail UI (intentional design decision).
- `DATA_DIR=./data` is relative to `backend/` — always run scripts from inside `backend/`.
- `relevant_products` field exists on the `Customer` model for MI integration but is empty for current customers.

---

## Market Intelligence — What's Real vs Fake

### Real (works correctly)
- **Formula engine** (`app/mi/formulas.py`) — additive weighted-sum: `ΔP = Σ(coef_i × pct_change_i)`. Uses recipe weights as default coefficients.
- **Signal generator** (`app/mi/signals.py`) — computes direction (up/down/flat), % change, top 3 drivers, one-line summary string.
- **Recipe data** (`data/mi/recipes.json`) — real chemistry cost structures for all 5 products (e.g. Benzyl Alcohol: 80% Toluene, 6% NaOH, 6% Chlorine, 5% LPG, 3% FX).
- **UI** — dashboard with 5 product cards showing direction arrow + % change + top driver. Product detail with Chart.js factor sparklines, recipe table with category badges.
- **API** — all `/api/mi/*` endpoints return computed data from the formula engine.

### Fake / seed data (replace with real ingestion)

| What | File | What to replace with |
|---|---|---|
| **Toluene + LPG prices** | `data/mi/seed_prices.json` | SunSirs chart OCR via GPT-4o vision (`app/mi/ingest/sunsirs.py`) |
| **NaOH + Chlorine prices** | `data/mi/seed_prices.json` | Same SunSirs OCR — but `sunsirs_id` not yet found for these two. Look up at `sunsirs.com/uk/prolist-1.html` |
| **USD/INR + USD/CNY** | `data/mi/seed_prices.json` | RBI API or `exchangerate.host` free API (`app/mi/ingest/rbi.py`) |
| **Freight rates** | `data/mi/freight_matrix.json` | Manual update — this is acceptable as "internal data" for the demo |
| **Data store** | JSON files + `lru_cache` in `store.py` | SQLite via SQLModel (`data/mi.db`) — interface is stable, one-file swap |

---

## Market Intelligence — Next Steps for Partner (Priority Order)

### Step A — FX rates via exchangerate.host (30 min)
**Why first:** No scraping, free API, no auth needed. Replaces two fake factors immediately.

Implement `backend/app/mi/ingest/rbi.py`:
```python
import httpx
from datetime import date, timedelta

async def fetch_fx_series(pair: str, days: int = 60) -> list[dict]:
    """pair: 'USD_INR' or 'USD_CNY'"""
    end = date.today()
    start = end - timedelta(days=days)
    url = f"https://api.exchangerate.host/timeframe?start_date={start}&end_date={end}&source=USD&currencies={pair.split('_')[1]}"
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
        r.raise_for_status()
        data = r.json()
    # data["quotes"] = {"2026-03-01": {"USDINR": 83.22}, ...}
    out = []
    for date_str, rates in sorted(data.get("quotes", {}).items()):
        price = list(rates.values())[0]
        out.append({"date": date_str, "price": price})
    return out
```

Write results into `data/mi/seed_prices.json` under keys `fx_usd_inr` and `fx_usd_cny`.

---

### Step B — Scout SunSirs chart access (30 min)
**Why first:** Validates whether httpx works before writing the full ingestor.

Run this script to test:
```python
import httpx

r = httpx.get(
    "https://graph.100ppi.com/?w=550&h=332&c=p&id=177&state=english",
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.sunsirs.com/uk/prodetail-177.html",
    },
    follow_redirects=True,
    timeout=15,
)
print(r.status_code, len(r.content), r.headers.get("content-type"))
open("test_toluene.png", "wb").write(r.content)
# If test_toluene.png opens as a real price chart → httpx path works
# If 403 or HTML → need Playwright fallback
```

Also find SunSirs IDs for NaOH and Chlorine:
- Browse `https://www.sunsirs.com/uk/prolist-1.html` (Chemical category)
- Update `backend/data/mi/factors.json` — set `sunsirs_id` for `naoh_cn` and `chlorine_cn`

---

### Step C — SunSirs OCR ingestor (2–3 hrs)
**File:** `backend/app/mi/ingest/sunsirs.py`

The chart URL pattern (from PRD):
```
https://graph.100ppi.com/?w=550&h=332&c=p&id={sunsirs_id}&state=english
```

Workflow:
1. For each factor with `source: "sunsirs"` and a `sunsirs_id`, fetch chart image via httpx (Step B confirms this works)
2. Send image bytes to GPT-4o vision with the prompt in `app/mi/prompts/chart_ocr.txt`
3. Parse response → list of `{"date": "YYYY-MM-DD", "price": float}`
4. Write results into `data/mi/seed_prices.json` (or upsert to `mi.db` if SQLite is set up)

The OCR prompt to create at `backend/app/mi/prompts/chart_ocr.txt`:
```
You are extracting time series data from a price chart image.

The chart shows a commodity price over time. The x-axis shows dates (format MM/DD),
the y-axis shows price (units stated in the chart title).

Extract every visible data point. Read the y-axis gridlines to calibrate values.
Use the date range in the title to assign full dates with year.

Return ONLY valid JSON:
{
  "commodity": "<as shown in title>",
  "unit": "<as shown in title>",
  "year": <integer>,
  "points": [{"date": "YYYY-MM-DD", "price": <number>}]
}

Rules:
- One point per visible inflection or roughly every 3-5 days.
- Round to the nearest y-axis gridline.
- Do not invent points outside the visible range.
- Do not include any text outside the JSON.
```

GPT-4o call with vision:
```python
import base64
from openai import OpenAI

client = OpenAI()

def ocr_chart(image_bytes: bytes) -> list[dict]:
    b64 = base64.b64encode(image_bytes).decode()
    prompt = open("app/mi/prompts/chart_ocr.txt").read()
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]
        }],
        response_format={"type": "json_object"},
    )
    import json
    data = json.loads(resp.choices[0].message.content)
    return data.get("points", [])
```

---

### Step D — SQLite migration (1 hr, optional for demo)
Replace `app/mi/store.py` JSON reads with SQLModel + SQLite. The function signatures are stable — `get_factor_series(factor_id)`, `price_on_or_before(factor_id, date)`, etc. Just change the internals.

Install: `pip install sqlmodel`

Models needed:
```python
class Factor(SQLModel, table=True): ...
class FactorPrice(SQLModel, table=True): ...
class Product(SQLModel, table=True): ...
class Recipe(SQLModel, table=True): ...
```
See `intelligencePlatformPrd.md` for full model definitions.

---

### Step E — Formula editor UI (2 hrs)
**File:** `frontend/mi/product.html` + `frontend/mi/mi.js`

Add to the product detail page below the recipe table:
- Coefficient number inputs (defaulted from recipe weights)
- "Evaluate" button → calls `POST /api/mi/formulas/{id}/evaluate`
- Result panel: direction badge, predicted % change, per-factor contribution bars

Backend endpoint to add in `app/mi/routes.py`:
```python
@router.post("/products/{product_id}/evaluate")
def evaluate(product_id: str, coefficients: dict[str, float]):
    result = formulas.evaluate_additive(coefficients)
    return result
```

---

### Step F — Stage 2 wiring (1 hr)
Wire MI signals into the Customer 360 prep brief so `market_context` mentions input cost pressure.

**1.** Add `relevant_products` to `data/customers.json` per customer:
```json
{"customer_id": "lr-ff-001", ..., "relevant_products": ["benzyl_alcohol", "benzaldehyde"]}
```

**2.** Update `backend/app/models.py` — add field to `Customer`:
```python
relevant_products: list[str] = []
```

**3.** Update `backend/app/stage2/synthesize.py` — add MI signals section:
```python
from app.mi.signals import get_for_customer

def synthesize(customer, stage1_out, product_catalog):
    try:
        mi_signals = get_for_customer(customer)
    except Exception as e:
        print(f"[mi] signal lookup failed: {e}")
        mi_signals = []

    mi_section = json.dumps(mi_signals, default=str) if mi_signals else "No MI signals available."
    # Add to the existing prompt template:
    prompt = prompt.replace("{mi_signals}", mi_section)
```

**4.** Update `backend/app/prompts/brief_synthesis.txt` — add new section and rule:
```
RELEVANT MARKET INTELLIGENCE SIGNALS:
{mi_signals}

# Add rule 9:
9. If MI signals are present, incorporate them into market_context with specifics.
   Example: "Benzyl Alcohol input costs estimated +9% over 30 days, driven by Toluene
   up 12% in China — your customer is likely feeling margin pressure right now."
   Do not invent signals not in the input.
```

---

## Architecture Decisions Made

| Decision | Choice | Reason |
|---|---|---|
| MI data store | JSON files now, SQLite later | Fastest for hackathon; interface is abstracted in `store.py` so swap is one file |
| Factor ingestion method | GPT-4o vision OCR on SunSirs chart images | SunSirs has anti-bot on their HTML pages; chart images served from `graph.100ppi.com` bypass this. OCR cost ~$0.01/chart. |
| FX source | exchangerate.host free API | RBI scraping is fragile; free API is reliable for demo |
| News fetch | `requests` + `feedparser` (NOT bare feedparser) | Google News blocks feedparser's default Python User-Agent. Must use `requests.get()` with browser UA, pass `resp.text` to feedparser. |
| Thread cap | Max 10 threads, 1500 chars/email body | Prevents 128k token overflow for customers with 100+ emails (hit in production) |
| MI ↔ C360 coupling | One-way only: C360 Stage 2 reads MI signals | MI never imports C360 code. MI failure is caught and returns empty list — cannot break brief generation. |
| Tab navigation | Server-side routes to separate HTML pages | Same pattern already used for `/customers/{id}` and `/customers/{id}/stage1`. No SPA complexity. |

---

## .gitignore Additions Needed

```
backend/data/mi/seed_prices.json   # will be regenerated by ingestor
backend/data/mi/mi.db              # SQLite, never commit
backend/.env
```

---

## Customers Currently Seeded

| ID | Company | Elixir ID | HubSpot ID | MI Products |
|---|---|---|---|---|
| `lr-ff-001` | L.R. Flavours & Fragrances Industries S.p.A. | `32d782e0-...` | `15453556810` | (empty — add benzyl_alcohol, benzaldehyde) |
| `lr-ff-002` | International Flavors & Fragrances Inc | (ask Subham) | (ask Subham) | (empty — add benzaldehyde, benzoic_acid) |
