# Kairos

WhatsApp order agent for small businesses in Pakistan. Customers message a
business on WhatsApp (English, Urdu or Roman Urdu); Kairos turns the chat into a
structured, priced order, stores it in Postgres, and replies. The full spec is
`ARCHITECTURE.md`. We are in **Phase 1** (see section 10): webhook + dedupe, one
LLM extraction, draft order in Postgres, templated reply.

## Core rule

**The LLM understands, the code decides.** The model only extracts intent and
fields from messages (and, from Phase 2, writes reply text). Prices, totals,
catalog matching, validation and order status changes are always decided in plain
Python in `kairos/domain/`. The model never invents a price, never sees a total it
could alter, and never confirms an order on its own.

## Business-agnostic by design

Kairos is for *any* business that takes product orders on WhatsApp, not one kind
of product.

- No product names, product types or business names in code or prompts.
- Each business's catalog lives in the `catalog_items` table. Load one with a
  seed YAML (`seeds/demo_business.yaml` is the generic example).
- Business-specific text (name, greeting, currency label, delivery rules) comes
  from `businesses.settings`.
- Domain functions (`catalog.py`, `pricing.py`) take the catalog as an argument
  and never touch the database.
- Every table is tenant scoped with `business_id`.

## Other rules

- Postgres is the source of truth. Money is integer units of currency; times are
  stored in UTC.
- All order status changes go through `kairos.domain.orders.transition`, which
  validates the move and records an `order_events` row.
- Every inbound message is stored before processing, deduped on `wa_message_id`.
- Secrets live only in `.env` (see `.env.example`), never in code.
- Ask before adding any dependency not already in `pyproject.toml` or the spec.
- Don't build later-phase features early.

## Tech stack

Python 3.12, FastAPI + uvicorn, arq + Redis (job queue), Postgres + async
SQLAlchemy (asyncpg) + Alembic, Anthropic SDK (Claude, via `LLM_*` env vars),
httpx (WhatsApp Cloud API), pydantic-settings, PyYAML (seed files), pytest. LangGraph and Google
Sheets arrive in Phase 2.

## Layout

```
kairos/
  api/webhook.py          GET/POST /webhook
  agent/schemas.py        Extraction schema (LLM structured output)
  agent/decide.py         Phase 1: Extraction + catalog -> decision (pure Python)
  agent/replies.py        Phase 1 templated replies (en / Roman Urdu)
  agent/prompts/          prompt text (no product types; catalog injected at runtime)
  domain/                 catalog.py, pricing.py, orders.py  (pure Python)
  integrations/           llm.py, whatsapp.py
  jobs/worker.py          arq worker: process_message
  db/                     models.py, session.py
  config.py               settings from env
  seed.py                 load a business + catalog from YAML
migrations/               Alembic
seeds/                    business YAML files
tests/unit/               domain tests (no DB, no LLM)
```

## Running

```bash
cp .env.example .env                 # fill in secrets; POSTGRES_* must match DATABASE_URL
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m kairos.seed seeds/demo_business.yaml
docker compose up api worker         # API on http://localhost:8000
ngrok http 8000                      # point the Meta webhook at <ngrok-url>/webhook
```

Local without Docker for the app itself:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn kairos.api.main:app --reload
arq kairos.jobs.worker.WorkerSettings
```

## Testing

```bash
pytest                    # unit tests: state machine, pricing, catalog matching
```

Unit tests use their own sample catalogs (at least two unrelated kinds of
business) and never need Postgres, Redis, WhatsApp or the LLM.
