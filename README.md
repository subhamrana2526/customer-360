# Elchemy Customer 360

Generates a **Sales Prep Brief** for any customer before a call. Synthesizes HubSpot conversation history, Elixir order/inquiry data, and external news into a concise, actionable document for the sales rep.

## Quick start

```bash
# 1. Create venv and install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Copy env and fill in keys
cp .env.example .env
# edit .env

# 3. Pull raw data, run pipelines (once customers.json is seeded)
python -m scripts.pull_all
python -m scripts.stage1_all
python -m scripts.stage2_all

# 4. Serve
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`.

## Architecture

Two-stage pipeline:

- **Stage 1** — cheap, parallel, cached. Per-thread email summaries, order aggregation, news relevance filtering.
- **Stage 2** — one rich `gpt-4o` synthesis call per customer that produces the prep brief.

See `prd.md` for full design.
