# RecoverAI

Agentic Revenue Recovery & Payment Failure Intelligence Platform.

## Structure

- `frontend/` — React + TypeScript + Vite + Tailwind CSS
- `backend/` — Python + FastAPI, with AI/ML (scikit-learn, pandas, NumPy) and agent orchestration under `app/ai/`

## Status

**Phase 1 (deterministic core) is implemented.** The full Detect → Diagnose →
Decide → Act → Measure → Audit loop runs without any ML or LLM: a fixed
decline-code taxonomy, a rule-based policy engine (retry caps, cooldowns,
fraud/hard-decline gates, a kill switch), idempotent action execution
against a clearly-labeled simulated payment gateway, and an append-only
audit trail. See the approved architecture blueprint for the full design
and the phased roadmap beyond this.

## Getting started

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173
npm run test       # Vitest
npm run build      # typecheck + production build
```

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt
cp .env.example .env           # optional — sensible defaults work out of the box
python -m scripts.seed_demo_data  # a few synthetic customers/invoices to explore with
uvicorn app.main:app --reload  # http://localhost:8000
pytest                          # backend tests
```

The frontend dev server proxies `/api` requests to `http://localhost:8000`.

### API surface (Phase 1)

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/payment-attempts` | Detect: record a gateway attempt (success or failure) |
| `GET /api/v1/cases` | Triage queue, filterable by status |
| `GET /api/v1/cases/{id}` | Case summary |
| `GET /api/v1/cases/{id}/events` | Full audit trail for the case |
| `GET /api/v1/cases/{id}/eligibility` | Fresh policy read: what's allowed right now, and why |
| `GET /api/v1/cases/{id}/actions` | Action history for the case |
| `POST /api/v1/cases/{id}/actions` | Act: request execution of a recovery action |
| `GET /api/v1/policy` | Current policy version and thresholds |

## Database

PostgreSQL, Supabase-compatible in production. Local dev/test defaults to a
SQLite file (`backend/recoverai_dev.db`, gitignored) for zero-friction
setup — the models avoid dialect-specific types, so pointing `DATABASE_URL`
at Postgres/Supabase is a config change, not a rewrite. Tables are created
automatically at startup in dev (`AUTO_CREATE_TABLES=true`); real
environments should use versioned migrations instead (planned, not yet
added).
