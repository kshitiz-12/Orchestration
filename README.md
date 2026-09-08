# Outcome Orchestration Platform (Prototype)

Email-first operational automation: unstructured email → governed business outcome with requirements, dependent tasks, exceptions, approvals, evidence, communications, and verified closure.

**Core rule:** AI interprets and recommends. Rules validate. Controlled services execute. Humans approve sensitive actions. Evidence verifies completion.

## Architecture

```
Gmail/API → Intake Gateway → Raw Event Storage → Idempotency → Durable Queue
  → AI Interpretation → Schema Validation → Context Retrieval → Rules/Permissions
  → Outcome Engine → Tasks / Approvals / Exceptions
  → Controlled Connectors (mock ERP/vendor/access) → Evidence → Verification → Email
```

The outcome engine is independent of Gmail and Gemini.

## Stack

| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI |
| Frontend | Next.js + React |
| AI | `google-genai` / Gemini 2.5 Flash (Heuristic fallback if no key) |
| DB | Supabase PostgreSQL or local SQLite |
| ORM | SQLModel |
| Email | Gmail API + OAuth (or API ingest for demo) |
| Jobs | Database-backed durable queue + worker |

## Quick start (local SQLite demo)

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or use the provided .env

python -m scripts.seed
python -m scripts.load_demo_emails
uvicorn app.main:app --reload --port 8000
```

Optional durable worker (separate terminal):

```bash
python -m app.workers.runner
```

API docs: http://localhost:8000/docs  
Health: http://localhost:8000/health  
Admin login: `admin@prototype.local` / `admin123`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: http://localhost:3000

### Tests

```bash
cd backend
pytest -q
```

## Environment

See `backend/.env.example`.

- `DATABASE_URL` — Supabase Postgres or `sqlite:///./orchestration.db`
- `GEMINI_API_KEY` — enables Gemini; empty uses deterministic heuristic provider
- `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` — dedicated prototype inbox OAuth

## Architecture (scalable by design)

See `backend/ARCHITECTURE.md`.

We intentionally keep **one backend stack**:
- FastAPI + SQLModel/SQLAlchemy + Alembic + Supabase Postgres
- Durable DB-backed job queue (worker process when needed)
- Replaceable AI (`LLMService`) and email (`EmailChannel`) adapters

**Not using Prisma** — it would split schema ownership across Node and Python and reduce scalability for this product.

Schema path:
- Models: `app/models/`
- Migrations: `alembic/` (`alembic upgrade head`)
- Boot: `SCHEMA_AUTO_CREATE` (prototype) or `RUN_MIGRATIONS_ON_STARTUP` (production)

Health:
- `GET /health` — liveness
- `GET /ready` — database readiness

## Deploy backend on Render (database = Supabase)

1. In Supabase → **Project Settings → Database → Connection string → URI**
   - Use **Session pooler** (host `*.pooler.supabase.com`, port `5432`)
   - Do **not** use Direct `db.*.supabase.co` from Render (often IPv6-only → deploy crash)
   - Avoid Transaction pooler (`6543`) for this FastAPI app
2. On Render Web Service (`rootDir: backend`):
   - Build: `pip install -r requirements.txt`
   - Start: `bash start.sh`
   - Health: `/health` (also available: `/ready`)
3. Set env vars:
   - `PYTHON_VERSION=3.12.8` (**required** — do not use 3.14)
   - `DATABASE_URL` = Session pooler URI (ssl is auto-added)
   - `SECRET_KEY`, `ADMIN_PASSWORD`
   - `CORS_ORIGINS` = your frontend URL(s)
   - `APP_ENV=production`, `DEBUG=false`, `AUTO_SEED=true`
   - optional `GEMINI_API_KEY`

Build must show `Using Python version 3.12.8`, not 3.14.
If deploy loops on startup, check logs for `Database connection failed` and switch to the Session pooler URI.

On first boot the API creates tables in Supabase and seeds `admin@prototype.local`.

Optional worker: `python -m app.workers.runner` (same `DATABASE_URL`). On free tier you can call `POST /api/v1/intake/worker/tick` instead.

## Demo scenarios covered

- **A** New employee workplace readiness with no permanent seat (independent tasks continue)
- **B** Parking occupied / chair missing
- **C** Vendor quality escalation (multi-issue, allegations UNVERIFIED)
- **D** Invoice settlement with three-way match (no autonomous payment)

## Project layout

```
backend/app/
  api/           FastAPI routes
  ai/            LLMService + GeminiProvider (replaceable)
  audit/         Append-only audit
  connectors/    Gmail + mock ERP/vendor/access
  core/          Config, DB, enums, security
  engine/        Outcome engine, scenarios, pipeline
  models/        SQLModel entities
  schemas/       Pydantic (incl. ExtractionResult)
  services/      Intake, queue, context, communications
  workers/       Durable job runner
frontend/        Next.js operations dashboard
```

## Security (prototype minimum)

- No Gmail passwords stored (OAuth only)
- Attachment allow-list + size limits
- Prompt-injection / safety scan on intake
- LLM never gets unrestricted DB/SQL/tool execution
- Financial, access-control, and vendor-sanction actions require human review
- Audit trail for status/approval/evidence/communication events

## Prototype boundaries

Out of scope: production HRMS/ERP/banking, live access control, BMS/CCTV, mobile apps, multi-country tax, public vendor marketplace.
