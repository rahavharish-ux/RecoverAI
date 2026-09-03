# RecoverAI

Agentic Revenue Recovery & Payment Failure Intelligence Platform.

> RecoverAI combines calibrated ML prediction, deterministic financial
> safety policies, constrained agent reasoning, controlled recovery
> execution, and complete auditability to recover revenue safely.

## Status

**Phases 1–4 are implemented.** Pipeline: Detect → Diagnose → Predict →
Decide → Act → Measure → Learn → Audit, plus an executive dashboard and a
polished Case Intelligence view over the same data. Not production-ready —
see [Synthetic Data Disclaimer](#synthetic-data-disclaimer) and
[Known Limitations](#known-limitations-and-honest-caveats).

## Problem

Recurring-revenue businesses lose money to failed payments — expired
cards, insufficient funds, processor errors, fraud holds. Naive retry
schedules recover some of it, but retry hopeless charges at real cost,
ignore card-network retry-abuse penalties, and give finance no way to see
*why* revenue was lost or *why* any given action was taken.

## Solution

For every failed payment, RecoverAI runs a governed pipeline that
combines a deterministic policy engine, a calibrated ML model, and a
constrained reasoning agent to choose the highest-expected-value recovery
action, execute it against a simulated gateway, and record enough
evidence that any case can be replayed and explained after the fact.

## Architecture

```
DETECT → DIAGNOSE → PREDICT → DECIDE → ACT → MEASURE → LEARN → AUDIT
```

- **Detect/Diagnose** (`backend/app/domain/decline_taxonomy.py`) — a fixed,
  deterministic decline-code taxonomy. No ML, no LLM.
- **Predict** (`backend/app/ml/`, `backend/training/`) — a calibrated
  logistic-regression/random-forest model, trained and honestly evaluated
  on synthetic data. Purely advisory.
- **Decide** (`backend/app/domain/policy.py`, `backend/app/agent/`) — a
  deterministic policy engine computes the *allowed* action set; an agent
  (deterministic by default, LLM-backed if configured) reasons and selects
  only from that set.
- **Act** (`backend/app/services/action_service.py`) — idempotent
  execution against a labeled payment simulator, independently
  re-validated at execution time regardless of what any decision record
  says.
- **Measure/Audit** (`backend/app/services/dashboard_service.py`,
  `case_events`) — an append-only audit trail every case's story is
  rendered from directly, plus read-only dashboard aggregation over the
  same tables.

Frontend: React + TypeScript + Vite + Tailwind, a small set of views
(Dashboard, Cases, Case Intelligence, Agent Activity, Model Intelligence,
Demo Center) navigated with local component state — no router library,
deliberately kept minimal.

## AI/ML

- **Target**: P(a retry attempt on this failed payment would succeed).
- **Dataset**: synthetic, chronologically generated (`training/synthetic_data.py`)
  with a hidden, noisy ground-truth process kept separate from the
  training pipeline (`training/train.py`) — see the disclaimer below.
- **Models compared honestly**: logistic regression (baseline) vs. random
  forest (candidate), selected by validation PR-AUC, both reported on the
  same held-out test set.
- **Calibration**: isotonic regression, verified to improve Brier score
  before being trusted.
- **Explainability**: exact coefficient contributions for logistic
  regression; native feature importances plus a labeled direction proxy
  for random forest. No SHAP, no invented explanations.

Train it: `python -m training.train` from `backend/`.

## Agentic Architecture

```
ML Prediction  →  Deterministic Policy  →  Agent Decision  →  Server Re-validation  →  Execute
```

The agent (`backend/app/agent/`) reasons **only** over actions the policy
engine already allowed — it cannot see, let alone select, a prohibited
one. Two providers behind one `AgentProvider` interface:

- **Deterministic Decision Engine** — default, no network, no API key.
  Picks the highest-expected-value allowed action.
- **Agentic AI Decision Engine** — Anthropic-backed, a genuine tool-use
  loop over raw HTTP (no SDK dependency), gated on `ANTHROPIC_API_KEY`.
  Falls back to the deterministic engine on any failure or malformed
  response.

Which one ran is always labeled verbatim (`agent_mode`, `mode_label`) —
a deterministic decision is never styled or worded to look like LLM
output.

13 tools with strict Pydantic schemas (8 read, 5 write) are the agent's
only interface to case data — it never queries the database directly.

## Safety Model

- **The agent never authorizes its own writes.** EXECUTE independently
  re-fetches case state, re-runs policy, and re-checks idempotency by
  calling the same `action_service.request_action` a human clicking
  "retry" in the API goes through — proven by a test that tampers an
  `AgentDecision.selected_action` directly in the database and confirms
  execution still rejects it.
- **Deterministic risk flags can only strengthen human-review
  requirements**, never weaken a provider's own judgment (fraud, high
  value, low confidence, repeated failures, conflicting signals).
- **Idempotency** — every write carries a caller-derived or
  caller-supplied key; duplicate requests never double-execute.
- **Hard caps** — a per-decision tool-call limit and a per-case decision
  limit make an infinite agent loop structurally impossible.

## Demo Scenarios

The **Demo Center** (in the app) runs five scenarios through the real
API — nothing is scripted UI text:

| | Scenario | What it shows |
|---|---|---|
| A | Successful Recovery | High-probability transient failure → agent retries → recovered |
| B | Fraud → Human Review | Fraud signal → agent can only escalate → requires human approval |
| C | Expired Card → Method Update | Retry never offered by policy → agent requests a method update |
| D | Retry & Cooldown Protection | A second retry this soon is blocked by cooldown → agent adapts |
| E | High Value → Human Review | Crosses the review threshold even though retry looks safe |

## Evaluation

Model metrics are computed once, honestly, on a held-out test set, and
surfaced via `GET /api/v1/ml/evaluation` and the Model Intelligence view
— never hand-typed into the UI. See that endpoint for the actual current
numbers; this README does not restate a point-in-time snapshot that would
go stale.

## Synthetic Data Disclaimer

**Every number in this system comes from a simulated sandbox.** Customers,
payment methods, transactions, decline outcomes, and recovery results are
all synthetically generated or simulated. Nothing here is:

- real payment processing,
- real customer data,
- a measurement of real-world recovery uplift or ROI,
- a production-grade LLM evaluation (the LLM path is implemented and
  unit-tested against a mocked transport; it has not been exercised
  against a live Anthropic API key in this environment).

Every screen that shows model or economics figures labels them as
sandbox/synthetic explicitly (e.g. "Synthetic Sandbox Evaluation",
the Economics panel's note field).

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic, scikit-learn, pandas,
  numpy, httpx, pytest.
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, Vitest.
- **Database**: SQLite for local dev/test (zero setup); PostgreSQL/Supabase
  in production — the models avoid dialect-specific types, so this is a
  config change, not a rewrite.
- No Kubernetes, no microservices, no message queue, no vector database —
  deliberately.

## How to Run

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate                  # Windows
pip install -r requirements-dev.txt
cp .env.example .env                   # optional — sensible defaults work out of the box
python -m training.train               # trains and registers the active model
python -m scripts.seed_demo_data       # a few synthetic customers/invoices to explore with
uvicorn app.main:app --reload          # http://localhost:8000
pytest                                  # backend tests
```

To enable the LLM-backed agent instead of the deterministic engine, set
`ANTHROPIC_API_KEY` in `backend/.env` — everything else works identically
either way.

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173 — proxies /api to :8000
npm run test       # Vitest
npm run lint        # oxlint
npm run build       # typecheck + production build
```

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/payment-attempts` | Detect: record a gateway attempt — runs Diagnose, Predict, and Decide inline for failures |
| `GET /api/v1/cases` | Triage queue, filterable by status |
| `GET /api/v1/cases/{id}` | Case summary |
| `GET /api/v1/cases/{id}/events` | Full audit trail for the case |
| `GET /api/v1/cases/{id}/eligibility` | Fresh policy read: what's allowed right now, and why |
| `GET /api/v1/cases/{id}/prediction` · `POST .../predict` | Most recent / recomputed PREDICT-stage read |
| `GET /api/v1/cases/{id}/actions` · `POST .../actions` | Action history / request execution directly |
| `GET /api/v1/policy` | Current policy version, thresholds, and action costs |
| `GET /api/v1/ml/model` · `GET /api/v1/ml/evaluation` | Active model metadata / full evaluation report |
| `POST /api/v1/cases/{id}/agent/decide` | DECIDE: agent reasons over the policy-allowed set |
| `POST /api/v1/cases/{id}/agent/execute` | EXECUTE: re-validates from scratch, then acts |
| `POST .../agent/decisions/{id}/approve` · `.../reject` | Human review transitions |
| `GET /api/v1/cases/{id}/agent/trace` · `GET .../decision` | Full agent trace / latest decision |
| `GET /api/v1/dashboard/summary` | Top-line KPIs |
| `GET /api/v1/dashboard/funnel` | Detect → Recovered stage counts |
| `GET /api/v1/dashboard/failures` | Cases grouped by decline code |
| `GET /api/v1/dashboard/decisions` | Recent agent decisions across all cases |
| `GET /api/v1/dashboard/priority-cases` | Open cases ranked by amount at risk |
| `GET /api/v1/dashboard/economics` | Sandbox recovery economics |

## Screenshots

*(placeholder — add screenshots of the Dashboard, Case Intelligence, and
Demo Center views here before final submission)*

## Future Work

- Wire the LLM agent path against a real Anthropic key in a controlled
  environment and capture actual latency/cost/behavior.
- Formalize the policy engine as a versioned, diffable module.
- Date-range filtering and cohort views on the dashboard.
- Versioned migrations (Alembic) in place of `create_all()`.

## Known Limitations and Honest Caveats

- SQLite is the dev/test database; Postgres is supported but not the
  default here.
- No authentication/authorization layer yet — this is a sandbox, not a
  multi-tenant product.
- The LLM agent path is implemented and tested against a mocked HTTP
  transport only.
- `recovery_probability` is retry-specific; risk-flagging still applies
  it as a general confidence signal even when the selected action isn't
  retry (conservatively over-triggers human review, never under-triggers).
- `generate_payment_link`/`create_recovery_message` reuse the existing
  `REQUEST_METHOD_UPDATE` action type rather than introducing new ones.

## Database

PostgreSQL, Supabase-compatible in production. Local dev/test defaults to
a SQLite file (`backend/recoverai_dev.db`, gitignored). Tables are
created automatically at startup in dev (`AUTO_CREATE_TABLES=true`); real
environments should use versioned migrations instead (planned, not yet
added).
