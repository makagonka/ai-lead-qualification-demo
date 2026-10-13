# AI Lead Qualification Demo

**Independent portfolio project · FastAPI · Python · SQLite · optional OpenAI structured outputs · Docker · pytest**

A small, human-reviewed lead-processing service. It accepts **synthetic** incoming requests, handles repeated events, filters obvious noise, classifies possible client requests, stores structured decisions and drafts, and supports manual approval. **It never sends messages to people.**

> Independent demonstration based on general workflow concepts. This repository is **not** a copy of a deployed commercial service. It contains no proprietary rules, private source code, credentials, or customer data.

## Features

- Validated REST endpoints, Swagger UI at `/docs`, and `/health`
- SQLite persistence, idempotent `(source, external_id)` intake, normalized text deduplication
- Cheap rule-based prefilter before optional AI calls
- **Offline mode** (default): deterministic and free, no account or API key
- **OpenAI mode**: real Chat Completions API call using JSON Schema structured outputs; validated by Pydantic
- Human-in-the-loop review with an explicit `pending → approved/rejected` state
- Failure-safe handling: if an AI provider fails, the item goes to manual review
- Pytest integration and unit tests, GitHub Actions and localhost-only Docker Compose

## Flow

```mermaid
flowchart LR
  A[Incoming synthetic message] --> B[Idempotency + dedupe]
  B --> C[Rule-based prefilter]
  C --> D[Offline rules / OpenAI]
  D --> E[Validated classification + draft]
  E --> F[(SQLite)]
  F --> G[Human review]
```

## Run locally

Requires Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Or: `docker compose up --build`. Both start in **offline mode**.

## Try it

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"source":"synthetic-board","external_id":"case-001","text":"We need a website design for a product launch"}'

curl http://127.0.0.1:8000/v1/messages

# Replace 1 with the response ID. This only changes the review status.
curl -X POST http://127.0.0.1:8000/v1/messages/1/review \
  -H 'Content-Type: application/json' \
  -d '{"action":"approve"}'
```

More mock examples are in [examples/synthetic_messages.json](examples/synthetic_messages.json).

## Optional real LLM classification

Create a local `.env` based on `.env.example`, set `DEMO_MODE=openai` and `OPENAI_API_KEY` (never commit your key). Docker Compose loads `.env` automatically. For direct Python runs, export both environment variables. OpenAI calls cost money and transmit supplied message text to the provider — use synthetic examples only. The default offline mode is **not** a real LLM.

## Tests

```bash
python -m pytest -q
```

Read [architecture notes](docs/architecture.md) for limitations and production changes.

**Security:** API has no authentication and must not be exposed to the internet as-is. The sample source IDs and messages are fictional. Approval does not send anything. No third-party connectors are configured.

## My role / why this demo exists

This independently implemented work sample demonstrates a practical approach to **business requirements → deterministic rules → optional LLM decision → structured result → human approval → verification and tests**.
