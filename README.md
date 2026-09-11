# Outcome Orchestration Platform (Prototype)

Email-first operational automation: unstructured email → governed business outcome with requirements, dependent tasks, exceptions, approvals, evidence, communications, and verified closure.

**Core rule:** AI interprets and recommends. Rules validate. Controlled services execute. Humans approve sensitive actions. Evidence verifies completion.

## Architecture

```
CloudMailin webhook → Intake Gateway → Raw Event Storage → Idempotency → Durable Queue
  → AI Interpretation → Schema Validation → Context Retrieval → Rules/Permissions
  → Outcome Engine → Tasks / Approvals / Exceptions
  → Controlled Connectors (mock ERP/vendor/access) → Evidence → Verification
  → CloudMailin SMTP reply (same email thread)
```

The outcome engine is **email-provider independent**. Prototype mail I/O uses `CloudMailinProvider`
(inbound webhook + SMTP). Outlook/Gmail adapters remain in the repo but are **not** the default.

## Stack

| Layer | Choice |
|-------|--------|
| Backend | Python + FastAPI |
| Frontend | Next.js + React |
| AI | `google-genai` / Gemini 2.5 Flash (Heuristic fallback if no key) |
| DB | Supabase PostgreSQL or local SQLite |
| ORM | SQLModel |
| Email | **CloudMailin** inbound webhook + SMTP (default). Outlook/Gmail optional. |
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
- `EMAIL_PROVIDER=cloudmailin` (prototype default)
- `CLOUDMAILIN_ADDRESS` / `CLOUDMAILIN_WEBHOOK_SECRET` / `CLOUDMAILIN_SMTP_URL`

## CloudMailin setup (PROTOTYPE — no Microsoft)

This prototype uses **CloudMailin only** for email. No Microsoft Graph, Entra app, or Gmail API required.

### 1. Create CloudMailin account
1. Sign up at [cloudmailin.com](https://www.cloudmailin.com/) (free inbound tier; no card for basic receive).
2. Copy your inbound address (e.g. `something@xxxx.cloudmailin.net`).

### 2. Configure webhook
1. Format: **JSON Normalized**
2. Target URL (public):  
   `https://<your-host>/api/v1/webhooks/cloudmailin?secret=YOUR_SECRET`  
   Local: expose FastAPI with [ngrok](https://ngrok.com/) → use the ngrok HTTPS URL.
3. Set in `backend/.env`:
```env
EMAIL_PROVIDER=cloudmailin
CLOUDMAILIN_ADDRESS=something@xxxx.cloudmailin.net
CLOUDMAILIN_WEBHOOK_SECRET=YOUR_SECRET
CLOUDMAILIN_FROM_EMAIL=noreply@your-verified-domain   # or CloudMailin outbound from
CLOUDMAILIN_SMTP_URL=smtp://USER:PASS@HOST:587        # from CloudMailin SMTP Accounts
```

### 3. Start stack
```bash
# API
cd backend && uvicorn app.main:app --reload --port 8000
# Worker (processes jobs; CloudMailin does not poll)
python -m app.workers.runner
# Frontend
cd frontend && npm run dev
```

Frontend `NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1`

### 4. Demo
1. Open **CloudMailin** in the UI — confirm address + SMTP status.
2. Email the CloudMailin address from Gmail/Outlook.
3. Watch Outcomes; incomplete requests send SMTP clarifications with `In-Reply-To` / `References` (same thread when SMTP is set).

**Inbound** works with webhook alone. **Live clarification emails** need SMTP (`CLOUDMAILIN_SMTP_URL`). Without SMTP, clarifications are still stored in the dashboard.

Outlook/Gmail code remains available if you later set `EMAIL_PROVIDER=outlook` or `gmail` — not needed for this prototype.

## Architecture (scalable by design)

See `backend/ARCHITECTURE.md`.

We intentionally keep **one backend stack**:
- FastAPI + SQLModel/SQLAlchemy + Alembic + Supabase Postgres
- Durable DB-backed job queue (worker process when needed)
- Replaceable AI (`LLMService`) and email (`EmailProvider`) adapters

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
  - `EMAIL_PROVIDER=cloudmailin` + `CLOUDMAILIN_*` (webhook secret, address, SMTP URL)
  - CloudMailin Target URL must point at `https://<your-api>/api/v1/webhooks/cloudmailin?secret=...`

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
  connectors/    CloudMailin + optional Outlook/Gmail + mock ERP/vendor/access
  core/          Config, DB, enums, security
  engine/        Outcome engine, scenarios, pipeline
  models/        SQLModel entities
  schemas/       Pydantic (incl. ExtractionResult)
  services/      Intake, queue, context, communications
  workers/       Durable job runner
frontend/        Next.js operations dashboard
```

## Security (prototype minimum)

- Webhook secret for CloudMailin; no mailbox passwords; SMTP credentials only in env
- Attachment allow-list + size limits
- Prompt-injection / safety scan on intake
- LLM never gets unrestricted DB/SQL/tool execution
- Financial, access-control, and vendor-sanction actions require human review
- Audit trail for status/approval/evidence/communication events

## Prototype boundaries

Out of scope: production HRMS/ERP/banking, live access control, BMS/CCTV, mobile apps, multi-country tax, public vendor marketplace.
