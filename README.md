# RecoverAI

Agentic Revenue Recovery & Payment Failure Intelligence Platform.

## Structure

- `frontend/` — React + TypeScript + Vite + Tailwind CSS
- `backend/` — Python + FastAPI, with AI/ML (scikit-learn, pandas, NumPy) and agent orchestration under `app/ai/`

## Getting started

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173
npm run test       # Vitest
```

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt
cp .env.example .env           # then fill in DATABASE_URL / SUPABASE_URL / SUPABASE_KEY
uvicorn app.main:app --reload  # http://localhost:8000
pytest                          # backend tests
```

The frontend dev server proxies `/api` requests to `http://localhost:8000`.

## Database

PostgreSQL, Supabase-compatible. Set `DATABASE_URL` (direct Postgres connection) and/or
`SUPABASE_URL` / `SUPABASE_KEY` in `backend/.env`.
