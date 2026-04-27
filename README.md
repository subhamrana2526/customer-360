# Elchemy Customer 360

Generates a **Sales Prep Brief** for any customer before a call. Synthesizes HubSpot conversation history, Elixir order/inquiry data, and external news into a concise, actionable document for the sales rep.

## Project structure

```
customer-360-backend/
├── backend/                # FastAPI + Stage 1/2 pipeline + connectors
│   ├── app/
│   │   ├── connectors/     # HubSpot, Elixir, News
│   │   ├── stage1/         # thread summaries, order agg, news filter
│   │   ├── stage2/         # synthesis (PrepBrief)
│   │   ├── prompts/        # LLM prompt templates
│   │   ├── config.py
│   │   ├── llm.py
│   │   ├── main.py         # FastAPI routes
│   │   └── models.py
│   ├── scripts/            # batch runners (pull_all, stage1_all, stage2_all)
│   ├── data/               # seeded JSON + cache/
│   ├── requirements.txt
│   ├── .env
│   └── .env.example
├── frontend/               # static UI served by FastAPI at /static
│   ├── index.html
│   ├── customer.html
│   ├── stage1.html
│   ├── app.js
│   ├── stage1.js
│   ├── style.css
│   └── stage1.css
├── prd.md
└── README.md
```

## Quick start

```bash
# 1. From repo root, create venv and install backend deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Configure secrets
cp backend/.env.example backend/.env
# edit backend/.env

# 3. From inside backend/, pull data and run the pipeline
cd backend
python -m scripts.pull_all
python -m scripts.stage1_all
python -m scripts.stage2_all

# 4. Serve (still from backend/)
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>.

## Architecture

Two-stage pipeline:

- **Stage 1** — cheap, parallel, cached. Per-thread email summaries, order aggregation, news relevance filtering.
- **Stage 2** — one rich `gpt-4o` synthesis call per customer that produces the prep brief.

See [prd.md](prd.md) for full design.
