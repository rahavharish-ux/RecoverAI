# RecoverAI

Agentic Revenue Recovery & Payment Failure Intelligence Platform.

## Structure

- `frontend/` — React + TypeScript + Vite + Tailwind CSS
- `backend/` — Python + FastAPI, with AI/ML (scikit-learn, pandas, NumPy) and agent orchestration under `app/ai/`

## Status

**Phases 1–3 are implemented.** The pipeline is Detect → Diagnose → Predict
→ Decide → Act → Measure → Learn → Audit. Detect/Diagnose/Act/Audit are
entirely deterministic (Phase 1) — a fixed decline-code taxonomy, a
rule-based policy engine (retry caps, cooldowns, fraud/hard-decline gates,
a kill switch), idempotent action execution against a clearly-labeled
simulated gateway, and an append-only audit trail. Predict (Phase 2) adds a
calibrated recovery-probability model, honestly evaluated on synthetic
data, that is purely advisory. Decide (Phase 3) adds an agent — a
Deterministic Decision Engine by default, or an LLM-backed one
(`ANTHROPIC_API_KEY`) — that reasons and selects only from the set the
policy engine already allowed; every write is independently re-validated
and executed through the unmodified Phase 1 action service, never
authorized by the agent's own reasoning. See the approved architecture
blueprint for the full design and the phased roadmap beyond this.

### Running the agent

No setup needed — the Deterministic Decision Engine works out of the box.
To use the LLM-backed agent instead, set `ANTHROPIC_API_KEY` in
`backend/.env`; if it's unset, empty, or the API call fails for any reason,
the system automatically falls back to the deterministic engine and keeps
working. Which one ran is always visible on the decision (`agent_mode`,
`mode_label`) — never conflated.

### Training the model

```bash
cd backend
python -m training.train   # generates synthetic data, trains, evaluates,
                            # calibrates, and registers the active model
```

Writes `ml_artifacts/<dataset_version>/{model.joblib,evaluation_report.json}`
(gitignored — regenerate locally) and registers the model in the
`model_versions` table the API reads from. Without this, `/api/v1/ml/*` and
every case's `prediction` field simply return nothing — the rest of the
system runs identically either way.

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

### API surface

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/payment-attempts` | Detect: record a gateway attempt (success or failure) — runs Diagnose, Predict, and Decide inline for failures |
| `GET /api/v1/cases` | Triage queue, filterable by status |
| `GET /api/v1/cases/{id}` | Case summary |
| `GET /api/v1/cases/{id}/events` | Full audit trail for the case |
| `GET /api/v1/cases/{id}/eligibility` | Fresh policy read: what's allowed right now, and why |
| `GET /api/v1/cases/{id}/prediction` | Most recent PREDICT-stage read: probability, confidence band, explanation, expected value per allowed action |
| `POST /api/v1/cases/{id}/predict` | Recompute a prediction for a case against current state |
| `GET /api/v1/cases/{id}/actions` | Action history for the case |
| `POST /api/v1/cases/{id}/actions` | Act: request execution of a recovery action |
| `GET /api/v1/policy` | Current policy version and thresholds |
| `GET /api/v1/ml/model` | Active model's metadata (algorithm, version, dataset/feature schema versions) |
| `GET /api/v1/ml/evaluation` | The active model's full, honestly-measured evaluation report |
| `POST /api/v1/cases/{id}/agent/decide` | DECIDE: the agent reasons over the policy-allowed action set and selects one |
| `POST /api/v1/cases/{id}/agent/execute` | EXECUTE: re-validates from scratch, then acts through the Phase 1 action service |
| `POST /api/v1/cases/{id}/agent/decisions/{decision_id}/approve` | Human approves a HUMAN_REVIEW decision — triggers execution |
| `POST /api/v1/cases/{id}/agent/decisions/{decision_id}/reject` | Human rejects a HUMAN_REVIEW decision — nothing executes |
| `GET /api/v1/cases/{id}/agent/trace` | Every decision for a case, each with its own tool-call log |
| `GET /api/v1/cases/{id}/decision` | The most recent agent decision for a case |

## Database

PostgreSQL, Supabase-compatible in production. Local dev/test defaults to a
SQLite file (`backend/recoverai_dev.db`, gitignored) for zero-friction
setup — the models avoid dialect-specific types, so pointing `DATABASE_URL`
at Postgres/Supabase is a config change, not a rewrite. Tables are created
automatically at startup in dev (`AUTO_CREATE_TABLES=true`); real
environments should use versioned migrations instead (planned, not yet
added).
