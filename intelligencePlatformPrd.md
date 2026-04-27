# MI Tracker — Hackathon Build Plan

## What We're Building

A market intelligence platform where sales reps track **input factor prices** (raw materials, energy, FX, freight) for chemical products, and combine them via **rep-built formulas** to infer where the output product's price is heading.

**Core framing:** This is not a price prediction engine. It's an intelligence-feeding tool. The system provides clean factor data and a flexible formula layer; the rep brings the chemistry knowledge and decides the weights.

**Demo target:** 5 toluene derivatives (Benzyl Alcohol, Benzaldehyde, Benzyl Chloride, Benzoic Acid, Toluene Diisocyanate) with live factor charts, editable formulas, and a derived directional signal (up / down / flat + % change).

**Integration:** MI signals feed into the Customer 360 prep brief.

---

## Architecture

Three layers. Factor ingestion is the hardest part; everything else is straightforward CRUD.

```
┌───────────────────────────────────────────────────────────────┐
│                    FACTOR INGESTION (cron + on-demand)         │
│   SunSirs charts          |  RBI FX  |  Freight matrix         │
│   (raw materials + LPG)      (API)      (manual JSON)          │
│   via chart OCR                                                │
└──────────────────────────────┬────────────────────────────────┘
                               │  writes daily price points
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                  TIME SERIES STORE (SQLite)                    │
│   factor_prices: factor_id, date, price, currency, unit        │
│   product_recipes: product_id, factor_id, weight_pct           │
│   formulas: product_id, owner, type, coefficients              │
└──────────────────────────────┬────────────────────────────────┘
                               │
              ┌────────────────┴─────────────────┐
              ▼                                  ▼
┌────────────────────────────┐   ┌──────────────────────────────┐
│       FORMULA ENGINE       │   │       MI SIGNAL GENERATOR    │
│   Evaluates rep formulas   │   │   Per-product: directional   │
│   against latest factor    │   │   signal + % change. Pushed  │
│   data. Daily, weekly,     │   │   into Customer 360 brief    │
│   monthly windows.         │   │   for relevant customers.    │
└────────────┬───────────────┘   └──────────────────────────────┘
             │
             ▼
        FastAPI + UI
        (charts, formula editor, signal cards)
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI (same project root as Customer 360 — shared `app/`) |
| OCR | **GPT-4o vision** as primary — proven on chart images, returns clean structured data |
| Scraping | `httpx` + `BeautifulSoup` for HTML; `Playwright` only if we hit JS-rendered pages |
| Storage | SQLite via `sqlmodel` (one file: `data/mi.db`) |
| Frontend | Static HTML + vanilla JS, `Chart.js` for line charts |
| Cron | Simple Python script triggered manually for hackathon; APScheduler later |

**Why GPT-4o for OCR:** Tesseract fails on line charts (it reads text, not pixels-as-data). Specialized vision models are overkill. GPT-4o vision can be prompted to extract data points from a chart with date/value pairs, and it handles the SunSirs chart layout reliably. Cost: ~$0.01 per chart. We re-run only on cron, not per page load, so cost is trivial.

---

## File Structure

Sharing root with Customer 360. New additions:

```
elchemy-hackathon/
├── app/
│   ├── mi/
│   │   ├── __init__.py
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── sunsirs.py            # chart OCR for raw materials + LPG energy
│   │   │   ├── rbi.py                # FX rates
│   │   │   └── freight.py            # freight matrix loader
│   │   ├── store.py                  # SQLite read/write
│   │   ├── formulas.py               # formula engine
│   │   ├── signals.py                # directional signal generation
│   │   └── routes.py                 # FastAPI router for /api/mi/*
│   └── prompts/
│       └── chart_ocr.txt             # prompt for GPT-4o vision
├── data/
│   ├── mi.db                         # SQLite
│   ├── factors.json                  # seed: factor definitions
│   ├── products.json                 # seed: 5 toluene derivatives
│   ├── recipes.json                  # seed: cost structure per product
│   └── freight_matrix.json           # seed: route × month → USD/container
├── static/
│   ├── mi/
│   │   ├── index.html                # product list + signals dashboard
│   │   ├── product.html              # detail page: charts + formula editor
│   │   └── mi.js
└── scripts/
    ├── mi_ingest_all.py              # run all ingestors, populate DB
    └── mi_compute_signals.py         # recompute all formulas + signals
```

---

## Data Model (SQLite via SQLModel)

```python
class Factor(SQLModel, table=True):
    id: str = Field(primary_key=True)         # "toluene_cn", "naoh_cn", "natgas_in", "fx_usd_inr", "freight_in_us_east"
    name: str                                  # "Toluene (China)"
    category: Literal["raw_material", "energy", "fx", "freight"]
    source: str                                # "sunsirs", "igx", "rbi", "internal"
    source_url: str | None
    unit: str                                  # "RMB/ton", "INR/MMBtu", "USD/INR", "USD/container"
    sector: str | None                         # "Chemical" — from SunSirs

class FactorPrice(SQLModel, table=True):
    id: int = Field(primary_key=True)
    factor_id: str = Field(foreign_key="factor.id")
    date: date
    price: float
    ingested_at: datetime
    source_artifact: str | None                # path to chart image we OCR'd, for audit

class Product(SQLModel, table=True):
    id: str = Field(primary_key=True)         # "benzyl_alcohol"
    name: str                                  # "Benzyl Alcohol"
    family: str                                # "toluene_derivative"
    description: str | None

class Recipe(SQLModel, table=True):
    """Cost structure: which factors drive a product's cost, and at what weight."""
    id: int = Field(primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    factor_id: str = Field(foreign_key="factor.id")
    weight_pct: float                          # 0-100
    notes: str | None
    updated_at: datetime
    updated_by: str | None                     # so reps can edit

class Formula(SQLModel, table=True):
    id: int = Field(primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    name: str                                  # "Default" or "Mehul's tweak"
    type: Literal["additive", "multiplicative"]
    coefficients_json: str                     # {"toluene_cn": 0.78, "naoh_cn": 0.06, ...}
    is_default: bool
    created_by: str | None
    created_at: datetime
```

### Seed Data (committed in repo)

`data/factors.json`:
```json
[
  {"id": "toluene_cn",       "name": "Toluene (China)",      "category": "raw_material", "source": "sunsirs", "source_url": "https://www.sunsirs.com/uk/prodetail-177.html", "sunsirs_id": 177, "unit": "RMB/ton"},
  {"id": "naoh_cn",          "name": "Caustic Soda (China)", "category": "raw_material", "source": "sunsirs", "source_url": "<find via SunSirs Chemical category>",          "sunsirs_id": null, "unit": "RMB/ton"},
  {"id": "chlorine_cn",      "name": "Chlorine (China)",     "category": "raw_material", "source": "sunsirs", "source_url": "<find via SunSirs Chemical category>",          "sunsirs_id": null, "unit": "RMB/ton"},
  {"id": "lpg_cn",           "name": "LPG (China)",          "category": "energy",       "source": "sunsirs", "source_url": "https://www.sunsirs.com/uk/prodetail-158.html", "sunsirs_id": 158, "unit": "RMB/ton"},
  {"id": "fx_usd_inr",       "name": "USD/INR",              "category": "fx",           "source": "rbi",     "source_url": "https://www.rbi.org.in/...",                    "sunsirs_id": null, "unit": "INR per USD"},
  {"id": "fx_usd_cny",       "name": "USD/CNY",              "category": "fx",           "source": "rbi",     "source_url": "...",                                           "sunsirs_id": null, "unit": "CNY per USD"},
  {"id": "freight_in_us_east","name": "Freight India → US East","category": "freight",   "source": "internal","source_url": null,                                            "sunsirs_id": null, "unit": "USD/container"}
]
```

**Note on energy factor:** We use **LPG (China)** as the energy proxy, sourced from SunSirs (`prodetail-158.html`). LPG is more relevant than natural gas for many of these chemical processes and keeps the energy ingestion on the same source as the raw materials. This removes the IGX dependency entirely for the demo.

**Find the IDs for NaOH and Chlorine:** SunSirs lists these under the Chemical category at `https://www.sunsirs.com/uk/prolist-1.html` (or similar). 5-minute task in Block 1 to grab the exact `prodetail-XXX.html` IDs. Once found, drop the integers into `sunsirs_id` above.

`data/products.json`:
```json
[
  {"id": "benzyl_alcohol",   "name": "Benzyl Alcohol",   "family": "toluene_derivative"},
  {"id": "benzaldehyde",     "name": "Benzaldehyde",     "family": "toluene_derivative"},
  {"id": "benzyl_chloride",  "name": "Benzyl Chloride",  "family": "toluene_derivative"},
  {"id": "benzoic_acid",     "name": "Benzoic Acid",     "family": "toluene_derivative"},
  {"id": "tdi",              "name": "Toluene Diisocyanate", "family": "toluene_derivative"}
]
```

`data/recipes.json` — seeded recipe per product. Editable from UI later. Example for Benzyl Alcohol:
```json
{
  "benzyl_alcohol": [
    {"factor_id": "toluene_cn",   "weight_pct": 80, "notes": "Primary feedstock"},
    {"factor_id": "naoh_cn",      "weight_pct": 6,  "notes": "Reagent"},
    {"factor_id": "chlorine_cn",  "weight_pct": 6,  "notes": "Reagent"},
    {"factor_id": "lpg_cn",       "weight_pct": 5,  "notes": "Energy proxy"},
    {"factor_id": "fx_usd_cny",   "weight_pct": 3,  "notes": "FX exposure"}
  ]
}
```

---

## Factor Ingestion Details

### A. SunSirs Chart OCR (`app/mi/ingest/sunsirs.py`)

**Key finding:** SunSirs charts are served as direct images from a CDN host (`graph.100ppi.com`), not embedded in the protected HTML page. URL pattern:

```
https://graph.100ppi.com/?w=550&h=332&c=p&id={sunsirs_id}&state=english
```

This means we can fetch the chart image directly without scraping the protected `sunsirs.com/uk/prodetail-XXX.html` page at all. Examples:
- Toluene: `https://graph.100ppi.com/?w=550&h=332&c=p&id=177&state=english`
- LPG: `https://graph.100ppi.com/?w=550&h=332&c=p&id=158&state=english`

**Caveat:** The main `sunsirs.com` site has anti-bot protection. The `graph.100ppi.com` host appears not to share it, but this needs to be verified at runtime. See "Scout task" below.

**Workflow:**
1. For each factor with `source: "sunsirs"` and a `sunsirs_id`, build the chart image URL from the pattern above.
2. Fetch the image via `httpx` with a real-browser User-Agent and `Referer` header set to the parent SunSirs product page.
3. If the fetch fails (403, anti-bot, timeout), fall back to Playwright headless: open the parent page, wait for the chart image to load, save the rendered image bytes.
4. Send image bytes to GPT-4o vision with structured extraction prompt.
5. Parse response → list of `{date, price}` points.
6. Upsert into `factor_price` table (skip dates already present).

**httpx fetch helper:**
```python
SUNSIRS_GRAPH_URL = "https://graph.100ppi.com/?w=550&h=332&c=p&id={id}&state=english"

async def fetch_sunsirs_chart(sunsirs_id: int) -> bytes:
    url = SUNSIRS_GRAPH_URL.format(id=sunsirs_id)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"https://www.sunsirs.com/uk/prodetail-{sunsirs_id}.html",
        "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.get(url, headers=headers)
        r.raise_for_status()
        return r.content
```

**Prompt (`prompts/chart_ocr.txt`):**
```
You are extracting time series data from a price chart image.

The chart shows a commodity price over time. The x-axis shows dates 
(format MM/DD), the y-axis shows price (units stated in the chart title).

Extract every visible data point you can identify. Read the y-axis 
gridlines to calibrate price values. Use the date range in the title 
to assign full dates (with year).

Return ONLY valid JSON in this exact schema:
{
  "commodity": "<as shown in title>",
  "unit": "<as shown in title>",
  "year": <integer, inferred from date range>,
  "points": [
    {"date": "YYYY-MM-DD", "price": <number>}
  ]
}

Rules:
- One point per visible inflection or roughly every 3-5 days, whichever 
  is denser.
- Round prices to the nearest unit on the y-axis gridline scale.
- If a value is ambiguous (line crosses near a gridline), pick the 
  closer one.
- Do not invent points outside the visible range.
- Do not include any text outside the JSON.
```

**Practical notes:**
- SunSirs charts span 3 months by default. Daily granularity is approximate but good enough for trend signal.
- Re-run weekly during the hackathon; once-a-day in production.
- **For the actual go-live**, switch from chart OCR to scraping their last-6-days price table (more reliable). Stub a `sunsirs_table.py` ingestor — even if not used in the demo, having the path mapped out shows judges we know the production answer.

**Failure handling:** If GPT-4o returns malformed JSON or fewer than 5 points, fall back to a cached previous extraction and log the failure.

**Scout task (first 30 minutes of Block 2):** Before writing the full ingestor, validate the access path:
```python
import httpx
r = httpx.get(
    "https://graph.100ppi.com/?w=550&h=332&c=p&id=177&state=english",
    headers={
        "User-Agent": "Mozilla/5.0 ...",
        "Referer": "https://www.sunsirs.com/uk/prodetail-177.html",
    },
    follow_redirects=True,
    timeout=15,
)
print(r.status_code, len(r.content), r.headers.get("content-type"))
# Save: open("test.png", "wb").write(r.content)
```
- If `200` and `image/png` and the saved file opens as a real chart → use the httpx path.
- If `403` / anti-bot HTML / empty body → switch to Playwright fallback. Pre-install with `pip install playwright && playwright install chromium` so this fallback is ready.

**Find the missing SunSirs IDs (also Block 2 first 30 minutes):** Confirm the product IDs for Caustic Soda and Chlorine by browsing `https://www.sunsirs.com/uk/prolist-1.html`. Update `factors.json` with the integer IDs.

### B. RBI FX (`app/mi/ingest/rbi.py`)

RBI publishes daily reference rates at `https://www.rbi.org.in/Scripts/ReferenceRateArchive.aspx` (CSV-style table). For real-time/historical FX:
- USD/INR, USD/CNY available
- Pull last 90 days on first run, then daily delta

Alternative for hackathon if RBI scraping is finicky: free `exchangerate.host` API. Keep `rbi.py` as the goal, mock-fall-back to API.

### C. Freight Matrix (`app/mi/ingest/freight.py`)

Manual JSON for the demo. Format:
```json
{
  "in_us_east": [
    {"month": "2026-01", "price_usd_per_container": 2400},
    {"month": "2026-02", "price_usd_per_container": 2350},
    ...
  ],
  "in_us_west": [...]
}
```
Loader reads file → upserts into `factor_price` with `factor_id="freight_in_us_east"` etc., using the 1st of each month as date.

---

## Formula Engine (`app/mi/formulas.py`)

### Two formula types

**Additive** — straightforward weighted sum of % changes:
```
ΔP_predicted = Σ (coefficient_i × ΔP_factor_i)
```
where each ΔP_factor_i is the % change of that factor over the chosen window.

**Multiplicative** — compound effect:
```
P_new / P_old = Π (1 + coefficient_i × δP_factor_i)
ΔP_predicted = (P_new / P_old) - 1
```

### Inputs to evaluation

```python
def evaluate_formula(
    formula: Formula,
    window_days: int = 30,
    end_date: date = today,
) -> FormulaResult:
    ...
```

For each factor in the formula coefficients:
1. Fetch start_price (closest available on or before `end_date - window_days`)
2. Fetch end_price (closest available on or before `end_date`)
3. Compute pct_change_factor = (end - start) / start
4. Apply formula

### Output

```python
class FormulaResult(BaseModel):
    formula_id: int
    product_id: str
    window_days: int
    end_date: date
    factor_contributions: list[dict]   # [{factor_id, pct_change, weighted_contribution}]
    predicted_pct_change: float
    direction: Literal["up", "down", "flat"]   # flat if |change| < 1%
    confidence_note: str                        # e.g. "Based on 4 of 5 factors with fresh data"
```

### Default formula auto-generation

For each product, if no `is_default=True` formula exists, generate one from the recipe:
```python
default_coefficients = {
    factor_id: weight_pct / 100
    for factor_id, weight_pct in recipe_for_product
}
```

This is what loads when a rep first opens a product. They can clone, tweak, and save their own.

---

## Signal Generator (`app/mi/signals.py`)

Per-product MI signal — the thing that gets surfaced in dashboards and Customer 360 briefs.

```python
class MISignal(BaseModel):
    product_id: str
    product_name: str
    direction: Literal["up", "down", "flat"]
    pct_change: float                       # signed
    window_days: int                        # 30 by default
    top_drivers: list[dict]                 # [{factor_name, contribution_pct}], top 2-3
    summary_line: str                       # "Toluene up 12% drove BA estimate +9%"
    generated_at: datetime
```

`summary_line` is generated from the formula result, no LLM needed — just template:
```
"{top_factor} {top_factor_direction} {top_factor_pct}% drove {product} 
estimate {product_direction} {product_pct}%"
```

Run on every refresh; cache in DB.

---

## Customer 360 Integration

**Plug-in point:** Stage 2 synthesis prompt in Customer 360 takes a new input section.

In `app/stage2/synthesize.py`:
```python
def get_mi_signals_for_customer(customer: Customer) -> list[MISignal]:
    """Return MI signals for products the customer manufactures or has 
    inquired about / ordered."""
    relevant_product_ids = (
        infer_from_manufacturing_profile(customer)
        + infer_from_order_history(customer)
        + infer_from_inquiry_history(customer)
    )
    return [load_signal(pid) for pid in set(relevant_product_ids)]
```

The synthesis prompt gets a new section:
```
RELEVANT MARKET INTELLIGENCE SIGNALS:
{mi_signals_json}
```

And a rule:
```
9. If MI signals are present, use them in "market_context" with specifics: 
   "{product} input costs estimated +9% over last 30 days, driven primarily 
   by Toluene up 12% in China." Do not invent signals not in the input.
```

This is the magic moment for the demo: a customer brief that says "Hey, your customer makes Benzyl Alcohol and Toluene is up 12% — they're feeling input cost pressure right now, here's the conversation angle."

**Mapping inference:** For the demo, hand-map the 5-6 customers to the 5 toluene derivatives in `customers.json` via a `relevant_products: ["benzyl_alcohol", ...]` field. Smart inference is a v2 feature.

---

## API Endpoints

```
GET  /api/mi/products                          → list 5 products with latest signal
GET  /api/mi/products/{id}                     → product detail + recipe + factors
GET  /api/mi/products/{id}/factors             → factor price time series for charting
PUT  /api/mi/products/{id}/recipe              → edit cost structure (weights)

GET  /api/mi/formulas?product_id=...           → list formulas for product
POST /api/mi/formulas                          → create formula
PUT  /api/mi/formulas/{id}                     → edit coefficients
POST /api/mi/formulas/{id}/evaluate            → run formula → FormulaResult

GET  /api/mi/signals                           → all latest MI signals
POST /api/mi/refresh                           → trigger ingest + recompute
```

---

## UI

### `static/mi/index.html` — Dashboard
Card grid, one per product:
- Product name
- Big colored arrow: ↑ up / ↓ down / → flat
- Predicted % change (e.g. "+9.2% over 30d")
- Top driver line ("Toluene +12% in China")
- Sparkline of estimated price trend
- Click → product detail

### `static/mi/product.html` — Product Detail
Three sections, top to bottom:

**1. Factor Charts (Chart.js)**
One panel per factor in the recipe:
- Toluene (RMB/ton, last 90d)
- Caustic Soda
- Chlorine
- LPG (energy proxy)
- USD/CNY FX
Each panel shows: latest price, % change over 30d, line chart.

**2. Recipe + Formula Editor**
- Editable table: factor | weight % | notes (saves to DB on blur)
- Formula type toggle: Additive / Multiplicative
- Coefficient sliders or number inputs (defaulted from recipe weights)
- "Evaluate" button → shows FormulaResult panel:
  - Direction badge
  - Predicted % change, large
  - Per-factor contribution waterfall (small bar chart)
  - "Save formula as..." input

**3. Formula Library**
Saved formulas for this product, with last-evaluated direction/% next to each.

Brand: Elchemy red `#ef4136` for accents, slate brown `#2a2522` for text. Up = green `#99cc33`, down = red `#ef4136`, flat = gold `#ef7f18`.

---

## Build Sequence

12-14 hours, parallel where possible. Two people ideal.

### Block 1 — Plumbing & Seed (2.5 hrs)
- [ ] SQLModel models, DB init, alembic-skip-just-create-all
- [ ] Seed `factors.json`, `products.json`, `recipes.json`, `freight_matrix.json`
- [ ] FastAPI router skeleton with all endpoints stubbed returning fake data
- [ ] Test one OCR call against a saved SunSirs chart image to validate prompt

### Block 2 — Ingestion (3.5 hrs, parallel)
- [ ] **Scout task (first 30 min, blocks Person A):** verify `graph.100ppi.com` chart fetch works with httpx; confirm SunSirs IDs for NaOH and Chlorine. Update `factors.json`.
- [ ] Person A: SunSirs OCR ingestor → working for Toluene + NaOH + Chlorine + LPG (all 4 from same source)
- [ ] Person B: RBI FX scraper (or fallback `exchangerate.host` API) + freight matrix loader
- [ ] `scripts/mi_ingest_all.py` runs all three ingestors, populates DB end-to-end

### Block 3 — Formula Engine + Signals (2 hrs)
- [ ] Formula evaluation logic (additive + multiplicative)
- [ ] Default formula generator from recipe
- [ ] Signal generator with template summary line
- [ ] `scripts/mi_compute_signals.py` populates signal cache for all products

### Block 4 — UI (3 hrs)
- [ ] Dashboard with 5 product cards + signals
- [ ] Product detail page with Chart.js factor panels
- [ ] Formula editor with sliders + Evaluate button
- [ ] Recipe editor (inline edit, save on blur)

### Block 5 — Customer 360 Integration (1 hr)
- [ ] Add `relevant_products` field to seeded customers
- [ ] Wire MI signals into Stage 2 synthesis prompt
- [ ] Regenerate briefs, verify market_context section now has crisp MI lines

### Block 6 — Polish + Demo Prep (1.5 hrs)
- [ ] Refresh button on dashboard runs full pipeline live (target < 60s)
- [ ] Pre-cache before demo so live refresh is the show, not the dependency
- [ ] Verify a "wow" moment per product: one strongly up, one strongly down, one flat
- [ ] Have backup screenshots in case ingest fails on demo day

### Buffer (1-2 hrs)
SunSirs blocking the request (Playwright fallback), RBI page format change, GPT-4o JSON drift.

---

## Setup Additions

`requirements.txt` additions:
```
sqlmodel
pillow                      # for image handling
playwright                  # fallback for SunSirs if httpx is blocked; pre-install with `playwright install chromium`
chart.js                    # via CDN, no install needed
```

`.env` additions:
```
MI_DB_PATH=./data/mi.db
SUNSIRS_GRAPH_BASE=https://graph.100ppi.com
SUNSIRS_PRODUCT_BASE=https://www.sunsirs.com/uk
GPT_VISION_MODEL=gpt-4o
```

---

## Decisions Still to Confirm

1. **SunSirs chart image fetch.** Pattern is `https://graph.100ppi.com/?w=550&h=332&c=p&id={sunsirs_id}&state=english`. Need to verify in the Block 2 scout task whether httpx with proper headers gets through, or whether Playwright fallback is required. Pre-install Playwright either way.
2. **SunSirs IDs for NaOH and Chlorine.** Toluene = 177, LPG = 158 are confirmed. The other two need a 5-minute lookup on SunSirs Chemical category. Block 2 scout task.
3. **Recipe accuracy.** The 80/6/6/5/3 split for Benzyl Alcohol is the example. Mehul to validate the splits for all 5 products before Block 3, or briefs will recommend nonsense.
4. **Customer-to-product mapping.** For the demo, which of LR Flavors & Fragrances and P&G should map to which toluene derivatives? F&F uses Benzaldehyde and Benzyl Alcohol heavily — natural fit for LR. P&G touches multiple — tie to the most newsworthy mover for a clean demo line.
5. **OCR demo or pre-cached?** Best to ingest once before demo, run signals live. Live OCR demo is risky and slow (~15s per chart × 4 = 60s of nothing on screen). Cache and let the "Refresh" button re-run signals (fast) without re-OCR'ing (slow).