# 03 — Current code: what to keep, extract, replace

We evolve the working system (decision D1). This maps today's code to the target engines and lists the gaps that
block selling to more than one company.

Legend: **Keep** = works, minor changes · **Extract** = good logic, move it into a shared engine · **Replace** =
rebuild on the new model · **Remove** = delete after migration.

## 1. Blockers for selling (must fix before a second customer)

| # | Gap | Where | Why it blocks |
|---|---|---|---|
| B1 | Single company. `get_tenant_id` returns the first tenant in the DB | `backend/app/api/deps.py` | Two customers would see each other's data |
| B2 | `Person.email` unique across the whole DB | `backend/app/models/org.py` | Same person/consultant can't exist in two customers; must be unique per tenant |
| B3 | No database-level isolation | all tables | One missed `tenant_id` filter = data leak. Needs Postgres Row-Level Security |
| B4 | Inbound mail not mapped to a tenant | `connectors/cloudmailin.py`, `services/intake.py` | One inbound address for everything. Need per-tenant address (`acme@in.adminservices.in`) or domain mapping |
| B5 | Prototype login (one admin, shared password) | `core/security.py`, `api/routes/auth.py` | Need real users, roles, SSO (Google/Microsoft), password reset |
| B6 | Services and rules hard-coded in Python | `agent/playbooks.py` (`PLAYBOOKS`, `assess_risk`, `_EVIDENCE`) | Every customer would need a code change |
| B7 | Company wording in code (signature, examples, seed data) | `core/config.py` mail signature, `agent/company_seed.py` | Must come from tenant settings |
| B8 | Secrets and mailbox credentials global | `.env`, `models/integrations.py` | Each tenant connects its own Gmail/Outlook; tokens stored encrypted per tenant |

## 2. Area by area

### Intake & channels
| File | Verdict | Note |
|---|---|---|
| `connectors/cloudmailin.py`, `gmail.py`, `outlook.py`, `services/email_poll.py`, `gmail_poll.py` | Keep | Add tenant resolution on the way in |
| `services/intake.py`, `models/intake.py` (idempotency) | Keep | Idempotency key must include tenant |
| `services/email_utils.py`, `thread_facts.py` | Keep | |

### AI
| File | Verdict | Note |
|---|---|---|
| `ai/admin_agent.py` (intake reading, team reply reading) | Keep | Prompt gets service catalogue and company facts from DB per tenant (mostly does already via directory) |
| `ai/gemini.py` (1,071 lines) | Extract | Split: provider client / prompts / parsers. Add per-tenant usage metering (cost control, pricing) |
| `ai/meeting_extract.py`, `messy_meeting_parse.py`, `admin_interpreter.py` | Extract | Fold into the single intake reader; one extraction path for all services |
| `ai/mail_writer.py` | Keep | Tone/language settings per tenant |

### The desk (case handling) — the core
| File | Verdict | Note |
|---|---|---|
| `agent/desk.py` (1,911 lines) | Extract | Holds intake, risk, approval, routing, work orders, team replies, closure. Split into: case service, approval (→ policy engine), work orders, team-reply handler, requester messaging. Behaviour and tests stay |
| `agent/playbooks.py` | Replace | Becomes `ServiceType` rows + default policy pack (see 02) + evidence requirement per service type |
| `agent/directory.py` | Extract | Becomes the routing part of the context engine: team by service + place, fallback up the place tree |
| `agent/lifecycle.py` | Extract | Merge into one SLA engine |
| `agent/priority.py` | Keep | Inputs move to policy (VIP, urgency rules) |
| `agent/learning.py`, `api/routes/learning.py` | Keep | Output becomes *draft* rules/knowledge needing admin approval |
| `agent/importer.py` | Extract | Becomes the standard import layer (spreadsheet → canonical API) for people, places, teams, assets |
| `agent/digest.py` | Keep | Per-tenant schedule and recipients |
| `agent/company_seed.py` | Replace | Becomes a "demo company" template + onboarding wizard |

### Approvals — currently in three places
| File | Verdict |
|---|---|
| `services/admin_ops.py` | Extract → policy engine |
| `agent/desk.py` approval branch | Extract → policy engine |
| `services/site_services.py` (`cost_centre_approver_emails`) | Extract → approval chain role `COST_CENTRE_OWNER` |
| `services/approval_actions.py`, `approval_links.py`, `api/routes/public_approvals.py` | Keep (channels) — all call the one engine |

### SLA & sweeps — currently in three places
| File | Verdict |
|---|---|
| `services/sla.py` (uses `load_meeting_policy`) | Extract → SLA engine, targets from ServiceType + policy |
| `agent/lifecycle.py` sweeper | Extract → SLA engine |
| `services/hold_sweeper.py`, `workers/runner.py` | Keep as the scheduler that *calls* the SLA engine; job per tenant |

Working hours and holidays must come from the place (branch) calendar, not fixed times.

### Meeting rooms — a separate engine today
| File | Verdict | Note |
|---|---|---|
| `engine/meeting_scenario.py` (2,254 lines), `services/meeting_room.py`, `room_booking.py`, `domain/meeting.py`, `policy/meeting_policy.py`, `services/catering.py`, `no_resource_flow.py` | Replace (gradually) | Rooms become `Place` (type room) + a booking service type. Meeting policy → rules in the policy engine. Keep it running until the desk path covers rooms, then remove |
| `engine/outcome_engine.py`, `outcome_reducer.py`, `outcome_pattern.py`, `pipeline.py`, `scenarios.py`, `event_services.py` | Review | Older pipeline; keep only what the desk path still uses |

### Data model
| Item | Verdict | Note |
|---|---|---|
| `models/outcome.py` (Outcome, Task, Approval, Evidence, Communication) | Keep → rename to Case over time | Promote stage, place, service type, requester, amount out of the `facts` JSON into real columns (indexes, reports) |
| `models/company.py` `service_tickets` | Remove | Duplicates `outcomes` |
| `models/company.py` Department | Replace | → Team with `scope_place` |
| `models/org.py` Location + Resource | Replace | → one Place tree |
| `OutcomeTemplate`, `BusinessRule`, `NotificationTemplate` | Replace | Exist but unused; superseded by ServiceType / PolicyRule / templates |
| `Asset`, `Vendor`, `Contract`, `PurchaseOrder`, `Receipt`, `Invoice` | Keep | Add tenant + place; wire into cases |
| `KnowledgeEntry` | Keep | Add place scope; fix the 6,000-character cut-off (see below) |
| `core/database.py` ad-hoc `ALTER` statements | Replace | Proper migrations (Alembic) — required before customers |

### Communication
| File | Verdict | Note |
|---|---|---|
| `services/communication.py` | Keep | Threading per case per recipient works. Sender address, signature, templates per tenant |
| `services/operator_inbox.py` | Keep | |

### Frontend
| Area | Verdict | Note |
|---|---|---|
| Dashboard, case views | Keep | Add place filter, role-based visibility (branch admin sees own branch) |
| `frontend/app/setup/page.tsx` | Extract | Becomes onboarding wizard + Setup sections: Places, People import, Teams, Services, Policies, Vendors |
| Login | Replace | Real auth + SSO |
| Missing | New | Employee self-service portal (raise/track requests without email), policy editor, reports |

### Audit, tests, ops
| Item | Verdict | Note |
|---|---|---|
| `audit/service.py` | Keep | Add tenant, actor, policy version on every decision |
| Test suite (275 passing) | Keep | Becomes the regression bank. Add a two-tenant isolation test suite |
| `evals/harness.py`, `agent/ai_eval.py` | Keep | Run per release on a fixed mail set |
| Render single service | Keep for pilots | Add separate worker, managed Postgres with backups, error monitoring |

## 3. Smaller known issues to fix along the way

- `directory.knowledge_text` joins all knowledge and cuts at 6,000 characters — large companies lose facts silently.
  Filter by service type and place first; add retrieval only if a tenant's knowledge outgrows that.
- `render.yaml` model name should match the chosen model (Gemini 3.5 Flash-Lite).
- Stage is stored inside `facts` JSON — hard to query, easy to get out of sync.
- Several regex-based rules (after-hours, travel) should become structured checks once the policy engine exists; keep
  the regexes only as AI-free fallbacks.

## 4. Order of work (feeds the roadmap)

1. B1–B3 tenant isolation + migrations (foundation; nothing else is safe without it).
2. Place tree + Person per tenant + import layer.
3. ServiceType in data + policy engine (replaces playbooks and the three approval paths).
4. One SLA engine.
5. Per-tenant channels, settings, auth.
6. Fold meeting rooms into the desk path.
