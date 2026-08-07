# Price Comparison AI Agent

A price-comparison tool that crawls live iPhone listings from **Amazon.sa** and **Noon.com**, stores them in a database, and uses **Claude** (and optionally a local **Ollama** model) to answer questions, compare prices across sites, and recommend the best deal based on your budget and preferences.

Built as an AI-track student project — the focus is on combining web scraping, a relational database, an LLM-backed API, and a simple frontend into one working system.

---

## Features

- **Amazon & Noon crawlers** — Playwright-based scrapers that collect product name, price, rating, review count, image, and URL (plus ASIN for Amazon).
- **FastAPI backend** — REST API with fast database-backed search, a background crawl trigger, and several AI-powered endpoints.
- **Claude integration** — structured, tool-enforced JSON responses (not freeform chat text) for asking questions, comparing prices, and getting recommendations.
- **Ollama integration** — a free, local-model alternative to Claude for the same Q&A feature.
- **Cross-site price comparison** — matches the *same* phone (same model, storage, color, and condition) across both sites and reports the price difference. Matching is double-checked in code, not just trusted from the AI, to avoid false matches (e.g. a refurbished unit being compared against a new one).
- **Budget-based recommendations** — hard filters (max price, min rating, storage, website) are applied in SQL first; the AI only picks and explains the best result among what already passed those filters, so it can never recommend something outside your stated budget.
- **Simple frontend** — a single self-contained HTML file (no build step) with tabs for Search, Compare, Ask AI, Recommend, and Crawl.

---

## Tech stack

| Layer | Technology |
|---|---|
| Crawling | Playwright (Python) |
| Backend | FastAPI + SQLAlchemy |
| Database | PostgreSQL |
| AI (cloud) | Claude API (`claude-sonnet-4-6`) via the `anthropic` Python SDK |
| AI (local) | Ollama (`llama3.2` by default) |
| Frontend | Plain HTML / CSS / JavaScript — no framework, no build tools |

---

## Project structure

```
price-comparison-ai-agent/
├── api/
│   └── main.py                # FastAPI app - all endpoints
├── crawlers/
│   ├── amazon/
│   │   └── crawler.py         # Amazon.sa crawler
│   └── noon/
│       └── crawler.py         # Noon.com crawler
├── database/
│   ├── database.py            # SQLAlchemy engine/session setup
│   ├── models.py               # ProductDB table definition
│   └── save_products.py       # Dedup + save logic
├── models/
│   └── products.py            # Product dataclass, shared by both crawlers
├── services/
│   ├── claude_service.py      # Claude integration - ask/compare/recommend
│   └── ollama_service.py      # Ollama integration - ask
├── index.html                 # Single-file frontend (opens directly in browser)
├── requirements.txt
├── .env                       # Not committed - see Setup below
└── .gitignore
```

The project also has `docs/` and `tests/` folders — add a note here about what's in them if you use them for anything specific.

> **Note on the `venv/` folder:** the project may have both `.venv/` and `venv/` present locally depending on setup history - only one is actually used (check which one your terminal prompt shows as active, e.g. `(.venv)`). Both are excluded from git either way, so this doesn't affect what gets pushed, but you can delete whichever one isn't your active environment to avoid confusion.

---

## Setup

### 1. Prerequisites

- Python 3.12+
- PostgreSQL running locally (or accessible remotely)
- [Ollama](https://ollama.com/download) installed, if you want the local-model features (optional — the app works without it, `/ask-local` will just return a clear error if it's not running)
- A Claude API key from the [Anthropic Console](https://console.anthropic.com/) if you want the Claude-backed features

### 2. Clone and set up a virtual environment

```powershell
git clone https://github.com/LeenQu/price-comparison-ai-agent.git
cd price-comparison-ai-agent
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt --break-system-packages
playwright install chromium
```
(`playwright install` downloads the actual browser Playwright drives — required once, separate from the pip package.)

### 4. Configure environment variables

Create a `.env` file in the project root (this file is gitignored — never commit it):

```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<database_name>
CLAUDE_API_KEY=your-anthropic-api-key-here
```

### 5. Set up the database

Create the database in PostgreSQL (via `psql` or pgAdmin), matching the name in `DATABASE_URL`. The `products` table is created automatically the first time the app runs (`database/database.py` calls `Base.metadata.create_all()` on import) — no manual migration needed.

### 6. Pull an Ollama model (optional, for `/ask-local`)

```powershell
ollama pull llama3.2
```

---

## Running it

### Start the API server

```powershell
uvicorn api.main:app --reload
```
Runs at `http://127.0.0.1:8000`. Interactive API docs (Swagger UI) are available at `http://127.0.0.1:8000/docs`.

### Open the frontend

Just double-click `index.html` in the project root — it opens directly in your browser, no server needed for the frontend itself. Make sure the "API base" field at the top matches where your server is running (defaults to `http://127.0.0.1:8000`).

### Run a crawler directly (for testing)

```powershell
python test_amazon.py
python test_noon.py
```

---

## API reference

All endpoints return JSON. Full interactive docs at `/docs` once the server is running.

### `GET /`
Health check. Returns `{"message": "Price Comparison API is running"}`.

### `GET /products`
Lists products already saved in the database.

| Param | Type | Default | Description |
|---|---|---|---|
| `website` | string, optional | — | Filter to `"Amazon"` or `"Noon"` |
| `limit` | int, optional | 100 | Max 500 |

### `GET /search`
Fast keyword search over saved products. Does **not** trigger a crawl.

| Param | Type | Default |
|---|---|---|
| `query` | string, required | — |
| `website` | string, optional | — |
| `limit` | int, optional | 50 |

### `POST /crawl`
Triggers a live crawl of both Amazon and Noon for a query, running as a background task (returns immediately; the actual crawl can take a few minutes). Check `/search` afterward.

| Param | Type | Required |
|---|---|---|
| `query` | string | yes |

### `GET /ask`
Answers a natural-language question about saved products, using Claude. Returns structured JSON (not freeform text): `summary`, `recommended_product`, `alternatives`, `caveats`.

| Param | Type | Required |
|---|---|---|
| `query` | string | yes — narrows which saved products to consider |
| `question` | string | yes — what you want to know |
| `limit` | int, optional | default 50 |

### `GET /ask-local`
Same as `/ask`, but answers using a local Ollama model instead of the Claude API. Requires Ollama running locally. Same response shape, plus a `"backend": "ollama"` field.

### `GET /compare`
Finds the same phone listed on both Amazon and Noon and reports the price difference for each match.

| Param | Type | Default |
|---|---|---|
| `query` | string, required | — |
| `limit_per_website` | int, optional | 30 — applies separately to each site so one site can't crowd out the other |

Returns `matches` (a list of `{model_description, amazon, noon, cheaper_website, price_difference}`) and `notes` (a list of short explanations for anything that *couldn't* be matched, e.g. a color or condition mismatch).

Matching is intentionally conservative: a listing is only counted as a match if storage, color, **and** condition (new vs. refurbished/renewed) all agree — this is double-checked in code after Claude's initial pass, not just trusted from the model.

### `GET /recommend`
Recommends the best product given structured filters. Filters run as SQL `WHERE` clauses first (hard constraints); Claude only picks and explains the best candidate among whatever already passed.

| Param | Type | Default |
|---|---|---|
| `category` | string, optional | `"iphone"` |
| `budget_max` | float, optional | — |
| `min_rating` | float, optional | — |
| `storage` | string, optional | substring match, e.g. `"128GB"` |
| `website` | string, optional | `"Amazon"` or `"Noon"` |
| `limit` | int, optional | 60 |

---

## Design notes / known limitations

- **Background crawl jobs are in-process** — `POST /crawl` uses FastAPI's `BackgroundTasks`, which runs in the same process as the API server. This is fine for local development and demoing, but if the server restarts mid-crawl, that job is simply lost (no retry, no queue). A proper task queue (Celery, RQ) would be the fix for production use.
- **Re-crawling doesn't update existing prices** — `save_products()` skips a product if it already exists (deduped by ASIN for Amazon, by URL for Noon) rather than updating its price. This means prices can go stale over time; there's no scheduled re-crawl yet.
- **AI matching is conservative by design** — the `/compare` endpoint would rather return zero matches than a wrong one. If you expected a match and didn't get one, check the `notes` field — it explains exactly what disqualified each candidate (mismatched color, storage, or new-vs-refurbished condition).
- **Ollama responses are generally lower quality than Claude's** on the same task, since local models are much smaller. `/ask-local` is included to demonstrate a local/free LLM integration, not as a production-quality substitute for `/ask`.
- **CORS is fully open** (`allow_origins=["*"]`) to let the locally-opened frontend file call the API. Fine for local development; would need to be restricted to a specific domain before any public deployment.

---

## Disclaimer

This is an independent student project for demonstrating web scraping, API design, and LLM integration. It is not affiliated with, endorsed by, or connected to Amazon or Noon in any way.
