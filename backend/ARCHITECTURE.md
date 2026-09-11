"""
Architecture decision — schema & data access

We deliberately do NOT use Prisma for this product.

Why:
- The runtime is Python + FastAPI. Prisma is a Node ORM and would force a second
  language, dual clients, and split ownership of the same tables.
- Scalability comes from one clear write path: FastAPI services → SQLModel/
  SQLAlchemy → Postgres (Supabase), with Alembic migrations as schema truth.
- The Outcome Engine, AI gateway, and connectors stay independent of the ORM.

Schema ownership:
- Models live in `app/models/` (SQLModel)
- Migrations live in `alembic/` (Alembic)
- Runtime never invents schema in production if `SCHEMA_AUTO_CREATE=false`;
  use `alembic upgrade head` (also runnable on boot via `RUN_MIGRATIONS_ON_STARTUP`).

Future scale path (without rewrite):
- Read replicas / separate worker service
- Redis/Celery only when queue volume requires it (DB queue is enough for prototype)
- Entra ID auth, object storage for attachments
- Channel adapters (Outlook.com / M365 via Graph, optional Gmail) behind `EmailProvider`
- Least-privilege Graph: `User.Read` `Mail.Read` `Mail.Send` (processed IDs in DB; no Mail.ReadWrite)

Email channel:
- `app/connectors/base.py` — `EmailProvider` (fetch / reply / mark processed)
- `app/connectors/outlook.py` — Microsoft Graph for Outlook.com / work accounts
- `app/connectors/gmail.py` — optional legacy Gmail
- `app/connectors/factory.py` — `EMAIL_PROVIDER` selection
- Outcome engine never imports Graph or Gmail SDKs directly
"""
