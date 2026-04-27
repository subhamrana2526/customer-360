# Customer 360 — Hackathon Build Plan

## What We're Building

A tool that generates a **Sales Prep Brief** for any customer before a call. The brief synthesizes HubSpot conversation history, Elixir order/inquiry data, and external context (news, market signals) into a concise, actionable document for the sales rep.

**Core value:** Things HubSpot's UI cannot give you. Synthesized intelligence, not raw data.

**Demo target:** 5–6 real customers, live brief generation in front of judges.

---

## Architecture

Two-stage pipeline. Stage 1 is cheap, parallel, and cached. Stage 2 is one rich call per customer.

```
┌─────────────────────────────────────────────────────────────┐
│                      RAW DATA SOURCES                        │
│   HubSpot API   |   Elixir API   |   Google News   |  Macro │
│   (emails,         (orders,         (per company)     news  │
│   meetings,        inquiries)                          feed │
│   calls)                                                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 1 — SUMMARIZE (cached)                │
│   Thread        |    Order         |    News                 │
│   summarizer    |    aggregator    |    relevance filter     │
│   (LLM)         |    (no LLM)      |    (LLM)                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              STAGE 2 — SYNTHESIZE PREP BRIEF                 │
│   One LLM call. Reasons over Stage 1 output + customer       │
│   profile + product catalog. Returns structured brief.       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                       FastAPI serves
                       to simple web UI
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| LLM | OpenAI (`gpt-4o` for synthesis, `gpt-4o-mini` for summarization) |
| Frontend | Static HTML + vanilla JS, served by FastAPI. `marked.js` for markdown rendering |
| Data store | JSON files on disk (no DB needed for hackathon) |
| Env management | `python-dotenv` |
| HTTP | `httpx` |

LLM client abstracted in `app/llm.py` so we can swap to Gemini/Claude with a config flag.

---

## File Structure

```
elchemy-customer-360/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── customers.json              # seeded customer profiles (manual)
│   ├── product_catalog.json        # Elchemy product catalog
│   ├── macro_news.json             # daily macro news feed
│   └── cache/
│       └── {customer_id}/
│           ├── raw/
│           │   ├── hubspot.json
│           │   ├── elixir.json
│           │   └── news.json
│           ├── stage1/
│           │   ├── threads.json
│           │   ├── orders.json
│           │   └── news.json
│           └── brief.json
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app + routes
│   ├── config.py                   # env vars, paths
│   ├── models.py                   # Pydantic schemas
│   ├── llm.py                      # OpenAI client wrapper
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── hubspot.py              # pull emails, meetings, calls
│   │   ├── elixir.py               # pull orders, inquiries
│   │   └── news.py                 # Google News RSS + macro feed loader
│   ├── stage1/
│   │   ├── __init__.py
│   │   ├── threads.py              # summarize email threads
│   │   ├── orders.py               # aggregate order history
│   │   └── news_filter.py          # filter news for relevance
│   ├── stage2/
│   │   ├── __init__.py
│   │   └── synthesize.py           # generate prep brief
│   └── prompts/
│       ├── thread_summary.txt
│       ├── news_filter.txt
│       └── brief_synthesis.txt
├── static/
│   ├── index.html                  # customer list page
│   ├── customer.html               # customer detail / brief page
│   ├── app.js
│   └── style.css
└── scripts/
    ├── pull_all.py                 # batch pull raw data for all customers
    ├── stage1_all.py               # batch run Stage 1
    └── stage2_all.py               # batch run Stage 2
```

---

## Data Models

All Pydantic models live in `app/models.py`.

### Customer Profile (seeded manually in `data/customers.json`)

```python
class ManufacturingProfile(BaseModel):
    products_made: list[str]                  # e.g. ["shampoos", "face washes"]
    scale: str                                # e.g. "Mid-size (50-200 cr revenue)"
    likely_inputs: list[str]                  # e.g. ["SLES", "CAPB", "preservatives"]

class Customer(BaseModel):
    customer_id: str
    company_name: str
    website: str | None
    industry: str                             # "Personal Care", "F&F", "Food", "Home Care"
    sub_industry: list[str] | None
    segment: Literal["end_user", "distributor"]
    geography: str
    hubspot_company_id: str | None
    elixir_customer_id: str | None
    manufacturing_profile: ManufacturingProfile
    historical_context: str | None            # 1-paragraph summary of the overall relationship
                                              # written manually for long-standing customers (e.g. LR F&F)
                                              # used as context in Stage 2 even when email window is 6 months
    notes: str | None
```

### Raw HubSpot Data

```python
class HubSpotEmail(BaseModel):
    id: str
    thread_id: str
    timestamp: datetime
    direction: Literal["incoming", "outgoing"]
    from_address: str
    to_addresses: list[str]
    subject: str
    body_text: str                            # plain text only

class HubSpotMeeting(BaseModel):
    id: str
    timestamp: datetime
    attendees: list[str]
    title: str
    notes: str | None

class HubSpotCall(BaseModel):
    id: str
    timestamp: datetime
    duration_seconds: int
    transcript: str | None
    notes: str | None

class HubSpotRaw(BaseModel):
    customer_id: str
    pulled_at: datetime
    emails: list[HubSpotEmail]
    meetings: list[HubSpotMeeting]
    calls: list[HubSpotCall]
```

### Raw Elixir Data

```python
class Order(BaseModel):
    order_id: str
    date: date
    products: list[dict]                      # [{name, grade, qty, unit, value}]
    total_value: float
    currency: str
    status: str

class Inquiry(BaseModel):
    inquiry_id: str
    date: date
    products_requested: list[str]
    status: str
    converted_to_order: bool

class ElixirRaw(BaseModel):
    customer_id: str
    pulled_at: datetime
    orders: list[Order]
    inquiries: list[Inquiry]
```

### Raw News Data

```python
class NewsItem(BaseModel):
    title: str
    url: str | None
    date: date
    source: str
    snippet: str
    category: Literal["company", "macro", "industry"]
```

### Stage 1 Outputs

```python
class ThreadSummary(BaseModel):
    thread_id: str
    date_start: date
    date_end: date
    participants: list[str]
    summary: str                              # 2-3 lines
    open_items: list[str]                     # commitments still pending
    sentiment: Literal["positive", "neutral", "cooling", "cold"]
    key_products_discussed: list[str]

class OrderAggregate(BaseModel):
    customer_id: str
    total_orders: int
    total_value_ytd: float
    last_order_date: date | None
    days_since_last_order: int | None
    top_products: list[dict]                  # [{name, qty, value, last_ordered}]
    inquiry_count: int
    inquiry_to_order_rate: float
    products_inquired_not_ordered: list[str]  # gaps to mine

class FilteredNewsItem(NewsItem):
    why_it_matters: str                       # 1-line, customer-specific

class Stage1Output(BaseModel):
    customer_id: str
    generated_at: datetime
    thread_summaries: list[ThreadSummary]
    order_aggregate: OrderAggregate
    filtered_news: list[FilteredNewsItem]
```

### Final Prep Brief

```python
class PitchAngle(BaseModel):
    product_name: str
    rationale: str                            # connects to a fact

class PrepBrief(BaseModel):
    customer_id: str
    company_name: str
    generated_at: datetime
    last_touchpoint: date | None
    days_since_touchpoint: int | None
    
    tldr: str                                 # 3 lines max
    conversation_recap: str                   # where things stand
    customer_snapshot: str                    # what they make + buy
    whats_new: str                            # company-specific news
    market_context: str                       # relevant macro/industry
    pitch_angles: list[PitchAngle]
    conversation_starters: list[str]          # 3-5 specific items
```

---

## Stage 1 Details

### 1a. Thread Summarizer (`app/stage1/threads.py`)

**Input:** `HubSpotRaw` for a customer.
**Logic:**
1. Group emails by `thread_id`
2. Sort each thread chronologically
3. Concatenate emails into one block per thread
4. Call LLM (gpt-4o-mini) per thread with `prompts/thread_summary.txt`
5. Parse JSON response into `ThreadSummary`
6. Cache results

**Prompt draft (`prompts/thread_summary.txt`):**
```
You are processing an email thread between Elchemy (a specialty chemicals 
distributor) and a customer. Your output will be used to prep a sales rep 
for an upcoming call.

Extract the following from the thread below. Return ONLY valid JSON 
matching this exact schema:

{
  "summary": "<2-3 sentences: what was discussed, what was decided>",
  "open_items": ["<commitment or pending action, one per item>"],
  "sentiment": "<one of: positive, neutral, cooling, cold>",
  "key_products_discussed": ["<product or chemical names mentioned>"]
}

Rules:
- Be specific. Reference actual products, prices, dates if mentioned.
- "open_items" includes promises from EITHER side that are not yet closed.
- "sentiment" reflects the most recent message tone, not the average.
- If thread is short (1-2 messages), still return the schema.

THREAD:
{thread_emails}
```

**Tip:** If a thread has > 30 emails, truncate to first 5 and last 15. Keeps tokens reasonable.

### 1b. Order Aggregator (`app/stage1/orders.py`)

**No LLM.** Pure aggregation logic over `ElixirRaw`.

Compute:
- Total orders count
- Total value YTD
- Last order date and days_since
- Top 5 products by value
- Inquiry to order conversion rate
- Products inquired about but never ordered (the gap to mine)

### 1c. News Filter (`app/stage1/news_filter.py`)

**Input:** Customer profile + raw news items (company-specific + macro + industry).
**Logic:** Single LLM call returns filtered list with relevance reasoning.

**news_cap config:** Before calling the LLM, truncate the raw news input to the most recent `NEWS_CAP` items (default: 15, configurable via env var). This prevents token blowout for large public companies like P&G where Google News returns hundreds of items. Cap applies per category (company / macro / industry) independently so macro news does not crowd out company-specific items.

**Prompt draft (`prompts/news_filter.txt`):**
```
You are filtering news items for relevance to a specific specialty 
chemicals customer of Elchemy. Keep only items that affect the customer 
in a tangible way.

Customer profile:
- Company: {company_name}
- Industry: {industry}
- Sub-industries: {sub_industry}
- Geography: {geography}
- What they make: {products_made}
- Likely raw material inputs: {likely_inputs}

For each news item, decide if it affects the customer through ONE OF:
(a) Their input costs (raw materials, energy, freight, FX)
(b) Their end-market demand
(c) Regulatory environment in their geography or category
(d) Direct mention of the company or close competitors
(e) Relevant supply chain disruption

For items kept, write a 1-line "why_it_matters" tied SPECIFICALLY to 
this customer (not generic).

Return ONLY valid JSON:
{
  "kept": [
    {
      "title": "<original title>",
      "url": "<original url>",
      "date": "<YYYY-MM-DD>",
      "source": "<original source>",
      "category": "<company|macro|industry>",
      "why_it_matters": "<1 line, customer-specific>"
    }
  ]
}

Drop generic items. Be ruthless. 3-5 kept items is ideal. Zero is acceptable.

NEWS ITEMS:
{news_items_json}
```

---

## Stage 2 Details

### Synthesis (`app/stage2/synthesize.py`)

**Input:** Customer profile + Stage 1 output + product catalog.
**Output:** `PrepBrief`.
**Model:** `gpt-4o`.

**Prompt draft (`prompts/brief_synthesis.txt`):**
```
You are preparing a sales rep at Elchemy (a B2B specialty chemicals 
distributor headquartered in Mumbai) for an upcoming call with a customer. 
Your output is the entire prep brief the rep will read.

CUSTOMER PROFILE:
{customer_profile}

RELATIONSHIP HISTORY (pre-window context, for long-standing customers):
{historical_context}

WHAT WE'VE DISCUSSED RECENTLY (thread summaries, most recent first):
{thread_summaries}

THEIR ORDER & INQUIRY HISTORY WITH US:
{order_aggregate}

RECENT NEWS RELEVANT TO THEM:
{filtered_news}

ELCHEMY PRODUCTS THAT POTENTIALLY FIT THEIR PROFILE:
{filtered_product_catalog}

Generate a structured prep brief. Return ONLY valid JSON matching this schema:

{
  "tldr": "<3 lines max. State: last touchpoint timing, the single most 
    important thing to address on this call, and the strongest pitch 
    opportunity.>",
  "conversation_recap": "<2-4 sentences. Where do things stand with this 
    account? Are there open commitments? What did the last conversation 
    leave unresolved? Be specific about products, prices, dates.>",
  "customer_snapshot": "<2-3 sentences. What they make, what they've 
    bought from us, where the relationship is in terms of share of wallet.>",
  "whats_new": "<2-3 sentences. Anything noteworthy about the company itself 
    in recent news. If nothing, say 'No company-specific news in the period.' 
    Do not invent.>",
  "market_context": "<2-4 sentences. Macro or industry factors affecting 
    THEIR inputs or end-market right now. Tie back to specific raw materials 
    or product categories where possible.>",
  "pitch_angles": [
    {
      "product_name": "<specific Elchemy product>",
      "rationale": "<2 sentences connecting to a concrete fact: a past 
        inquiry, a market move, a manufacturing input gap, a recent 
        conversation>"
    }
  ],
  "conversation_starters": [
    "<specific, non-generic opener tied to recent context. Something the 
      rep would not have on hand without this brief.>"
  ]
}

CRITICAL RULES:
1. Be specific. Use names, dates, products, numbers from the input.
2. Do not invent facts. If the data does not support a claim, omit it.
3. "pitch_angles" must reference something concrete from the data above 
   (an inquiry, a recent purchase, a market move, a stated need).
4. "conversation_starters" must be things the rep could not easily get from 
   HubSpot UI alone. Synthesis, not summary.
5. Aim for 3-5 pitch angles and 3-5 conversation starters.
6. No filler language. No "It is important to note." No "In conclusion."
7. No em dashes.
8. If a section has thin or missing input data, say so plainly in that 
   section. Do not pad with generic content. For example: if conversation 
   history is sparse, "conversation_recap" should say "Limited interaction 
   history on file. Relationship appears to be early-stage." For a large 
   public company with rich news but thin internal history, lean into 
   market_context and whats_new and keep conversation_recap honest about 
   the thin history.
```

---

## Data Source Implementation Notes

### HubSpot Connector (`app/connectors/hubspot.py`)

Use HubSpot's CRM API v3.

| Need | Endpoint |
|---|---|
| Get company by ID | `GET /crm/v3/objects/companies/{id}` |
| Get associated emails | `GET /crm/v3/objects/companies/{id}/associations/emails` then batch fetch |
| Get associated meetings | Similar pattern with `/meetings` |
| Get associated calls | Similar pattern with `/calls` |
| Pull email body | Property `hs_email_text` (plain) — prefer over `hs_email_html` |

Auth: Private App access token in `HUBSPOT_TOKEN` env var.

Time window: pull last 6 months by default (configurable).

### Elixir Connector (`app/connectors/elixir.py`)

Stub initially — Mehul to provide endpoint specs. Expected:
- Customer-by-ID lookup
- Orders list filtered by customer + date range
- Inquiries list filtered by customer + date range

Auth via `ELIXIR_TOKEN` env var.

If Elixir API is not ready by Block 1, **mock with seeded JSON** in `data/mocks/elixir/` so the rest of the pipeline isn't blocked. Real API can be wired in later.

### News Connector (`app/connectors/news.py`)

**Per-customer Google News:**
```python
url = f"https://news.google.com/rss/search?q=%22{quote(company_name)}%22&hl=en-IN&gl=IN&ceid=IN:en"
```
Parse with `feedparser`. Cache for 6 hours.

**Macro news:** Read from `data/macro_news.json`. Format expected:
```json
[
  {
    "date": "2026-04-27",
    "source": "Kotak Daily",
    "items": [
      {"title": "...", "summary": "...", "category": "macro"}
    ]
  }
]
```
Mehul will paste/automate population of this file.

**Industry RSS (optional, time-permitting):**
- Happi: `https://www.happi.com/rss/`
- Cosmetics Design: `https://www.cosmeticsdesign.com/rss`
- Perfumer & Flavorist: `https://www.perfumerflavorist.com/rss`

---

## API Endpoints (`app/main.py`)

```
GET  /                                  → serve static/index.html
GET  /customers/{id}                    → serve static/customer.html
GET  /api/customers                     → list all customers (from data/customers.json)
GET  /api/customers/{id}                → customer profile
GET  /api/customers/{id}/brief          → cached PrepBrief (404 if not generated)
POST /api/customers/{id}/refresh        → trigger raw pull → stage1 → stage2; 
                                          returns brief
GET  /api/customers/{id}/raw            → debug: raw data
GET  /api/customers/{id}/stage1         → debug: stage1 output
GET  /api/health                        → simple OK
```

The refresh endpoint is the demo magic moment. Should complete in 20–40 seconds.

For the demo, run scripts in advance to pre-cache. Refresh button proves it works live.

---

## Frontend (Minimal)

Two pages, both vanilla HTML + JS.

### `static/index.html` — Customer List
- Fetch `/api/customers`
- Render as a table or card grid: company name, industry, last touchpoint
- Click → navigate to `/customers/{id}`

### `static/customer.html` — Customer Detail
- Fetch `/api/customers/{id}` and `/api/customers/{id}/brief`
- Layout:
  - **Top:** Company name, industry, segment, geography, last touchpoint badge
  - **Main panel:** the Prep Brief, rendered from markdown sections via `marked.js`
  - **Right rail / tabs:** raw data inspectors (collapsible) — useful for the demo to show "look, this came from real data"
  - **Sticky button:** "Refresh Brief" → POST refresh, show spinner, re-render

Brand: use Elchemy red `#ef4136` for accents, slate brown `#2a2522` for text, light grey `#f1f2f2` for backgrounds.

---

## Build Sequence

Roughly 12–14 hours, parallelizable across 2–3 people.

### Block 1 — Plumbing (3 hrs)
- [ ] Repo scaffold, FastAPI hello-world running
- [ ] `customers.json` seeded with 5–6 real customers (manual entry)
- [ ] `product_catalog.json` populated with Elchemy products + tags by industry
- [ ] HubSpot connector: pull emails for one test customer, save to `cache/{id}/raw/hubspot.json`
- [ ] Elixir connector: real or mocked, save to `cache/{id}/raw/elixir.json`
- [ ] News connector: Google News RSS for company name + macro feed loader

### Block 2 — Stage 1 (3 hrs)
- [ ] `app/llm.py` OpenAI wrapper with retry + JSON-mode parsing
- [ ] Thread summarizer: working end-to-end on one customer
- [ ] Order aggregator: pure Python, well-tested
- [ ] News filter: working end-to-end on one customer
- [ ] `scripts/stage1_all.py` runs Stage 1 for all 6 customers, caches output

### Block 3 — Stage 2 (3 hrs)
- [ ] Master prompt drafted in `prompts/brief_synthesis.txt`
- [ ] `synthesize.py` calls gpt-4o, parses JSON, validates against `PrepBrief` schema
- [ ] Iterate on prompt against the 6 customers until briefs are sharp and specific
- [ ] `scripts/stage2_all.py` batch-generates briefs

### Block 4 — UI (2 hrs)
- [ ] List page rendering customers
- [ ] Detail page rendering brief
- [ ] Refresh button wired to POST endpoint
- [ ] Branded styling pass

### Block 5 — Demo Polish (2 hrs)
- [ ] Pick the strongest customer for the headline demo
- [ ] Identify 2–3 specific "wow" moments in their brief to call out
- [ ] Rehearse the narrative: "Here is what HubSpot shows. Here is what our brief tells you."
- [ ] Have a backup pre-rendered brief in case live refresh fails

### Buffer (1–2 hrs)
HubSpot rate limits, schema mismatches, OpenAI timeouts, the usual.

---

## Setup Checklist

`requirements.txt`:
```
fastapi
uvicorn[standard]
httpx
pydantic
python-dotenv
openai
feedparser
beautifulsoup4
python-dateutil
```

`.env.example`:
```
OPENAI_API_KEY=
OPENAI_MODEL_SYNTH=gpt-4o
OPENAI_MODEL_SUMM=gpt-4o-mini

HUBSPOT_TOKEN=
ELIXIR_BASE_URL=
ELIXIR_TOKEN=

DATA_DIR=./data
CACHE_DIR=./data/cache
```

Run commands:
```bash
# install
pip install -r requirements.txt

# pull raw data for everyone
python -m scripts.pull_all

# stage 1
python -m scripts.stage1_all

# stage 2
python -m scripts.stage2_all

# serve
uvicorn app.main:app --reload --port 8000
```

---

## Decisions Still to Confirm

1. **Elixir API** — is there a Postman collection or doc I (Claude Code) can reference? If not, mock for now and Mehul will provide endpoints during Block 1.
2. **Macro news feed** — current format: pasted text in chat. For the build, define a simple JSON format (shown above) and Mehul updates it manually for the demo. Automation later.
3. **HubSpot field for industry** — confirm the property name on Company records (`industry` is HubSpot default but customers may use a custom property).
4. **Customer selection** — Mehul to pick the 5–6 demo customers and provide their HubSpot company IDs and Elixir customer IDs.
5. **Trade publication RSS feeds** — included as nice-to-have. Skip if Block 1 runs over.