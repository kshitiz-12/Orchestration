# AdminServices — Client Verification Pack

**Purpose of this document:** Give a client (business + IT) a single place to understand **what the system does**, **how it works technically**, and **how to verify each capability** with concrete examples and expected outcomes.

**Product shape:** One workplace operations system for a company (typically multi-branch BFSI / enterprise India). Day-to-day work runs over **email**. The **admin console** is for setup, requests visibility, approvals, and vendor lifecycle. There is **no separate vendor app** — vendors complete onboarding via an **invite email + secure registration link**.

---

## 1. Executive overview

| Question | Answer |
|----------|--------|
| What is it? | Email-first workplace desk: repairs, visitors, parking, supplies, travel, onboarding, meeting rooms, plus vendor onboarding and an operational ledger |
| Who uses it daily? | Employees (mail), facilities/IT/admin teams (mail), ops admin (mail + console), vendors (registration link only) |
| What is “done”? | Case opened → routed → (approval if needed) → work order → team completes → requester informed → ledger remembers spend/who/what |
| What is verified AI vs rules? | Classification can use Gemini; risk, approvals, ledger numbers, and vendor scores are **rules/deterministic** — spend answers never invent amounts |

---

## 2. Actors

| Actor | How they interact | Authority |
|-------|-------------------|-----------|
| **Employee** | Emails the workplace mailbox | Opens/updates their cases |
| **Team inbox** (Facilities, IT, …) | Replies on work-order threads | `on it`, `done`, `issue: …`, `assign to …` |
| **Ops / company admin** | Ops mailbox + console login | Approvals, vendor invite/activate, analytics questions, Setup |
| **Approver** | Approval mail or signed link | Approve/reject spend/sensitive requests |
| **Vendor** | Invite email → `/vendor-register/{token}` | Submit profile only; cannot see console |

---

## 3. First company onboarding (empty → live)

### 3.1 Technical boot

1. Configure environment: `DATABASE_URL`, strong `SECRET_KEY`, `ADMIN_OPS_EMAIL`, `ADMIN_EMAIL`, strong `ADMIN_PASSWORD`, mail provider secrets, `FRONTEND_PUBLIC_URL` (for vendor invite links), optional `GEMINI_API_KEY`.
2. Start API → creates schema → bootstraps empty company (tenant + admin login + department stubs) when `AUTO_SEED` is on.
3. Production refuses weak secrets / default `admin123` password.

**Verify:** Log into console with `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Overview loads.

### 3.2 Company data (console → Company data)

Upload or enter:

- Offices (place tree)
- Teams / departments (categories + inbox emails + SLA)
- Employees (known senders)
- Policies & FAQs (knowledge)
- Stock SKUs (optional)
- Rooms / resources (for meetings)

**Verify:** A test employee email is accepted (not ignored as unknown). A facilities department has a real inbox (not placeholder).

### 3.3 Mail channel

- CloudMailin webhook **or** Gmail/Outlook OAuth + poll/worker.
- Outbound replies go through the connected provider.

**Verify:** Send a test “Hi” from a known employee → polite help reply, no case (or empty-mail handling). Check Communications / Mail inbox status.

### 3.4 Vendors (console → Vendors)

Invite at least one HVAC/maintenance vendor, complete registration link, activate.

**Verify:** Vendor shows `ACTIVE` with a score/tier. Next AC case work order mentions preferred vendor when matching.

---

## 4. System architecture (technical)

```
Employee / Ops / Team email
        │
        ▼
IntakeService → RawEmailEvent (+ job queue)
        │
        ▼
ProcessingPipeline
  1. Ops/team reply on [CASE-REF]  → verify sender → desk/legacy command
  2. Ops analytics question        → verify sender → ledger answer (no new case)
  3. Unknown sender                → store only (policy)
  4. Requester mail                → AdminDesk (service) and/or ScenarioOrchestrator (meeting/invoice)
        │
        ├── Outcome + ServiceTicket + Communications
        ├── OpsLedgerEvent (append-only memory)
        ├── ResolutionAgent (facilities investigate / stalled)
        └── Vendor ACTIVE only for WO hints / stock reorder mail
```

**Key services**

| Layer | Module |
|-------|--------|
| Pipeline | `backend/app/engine/pipeline.py` |
| Desk | `backend/app/agent/desk.py` |
| SLA sweeps | `backend/app/agent/lifecycle.py` + `hold_sweeper.run_all_sweeps` (web + worker) |
| Ledger | `backend/app/services/ops_ledger.py` |
| Resolution | `backend/app/agent/resolution_agent.py` |
| Vendors | `backend/app/services/vendor_lifecycle.py` |
| Stock | `backend/app/services/stock.py` |
| APIs | `/api/v1/...` FastAPI |
| Console | Next.js `frontend/app/...` |

---

## 5. Capability catalogue — how to verify each function

For each capability: **what**, **trigger**, **technical path**, **verification example**, **expected result**.

---

### 5.1 Employee service request (facilities / HVAC)

**What:** Opens a case, routes to Facilities, sends work order, replies to employee.

**Trigger:** Employee emails e.g. “AC not working in 4th floor bay near pantry”.

**Technical path:** `AdminDesk._new_request` → `Outcome` + `ServiceTicket` → resolution `investigate` (facilities) → `_dispatch` → `Communication` WORK ORDER → ledger `CASE_OPENED`, `PLAN_PROPOSED`, `WORK_ORDER_SENT`.

**Verify:**

1. Mail from known employee with that subject/body.
2. Expect reply containing a case ref like `FAC-YYYY-####`.
3. Ops/Facilities inbox gets a work order with investigation notes if any.
4. Console → Requests shows the case `DISPATCHED` / `ASSIGNED`.

---

### 5.2 Duplicate facilities report (link existing)

**What:** Second similar open AC at same place is linked instead of a second full dispatch.

**Trigger:** Another mail describing the same open AC issue (new thread/requester).

**Technical path:** `investigate` → `link_case_ref` → new outcome `agent_stage=LINKED` → employee told the open case ref.

**Verify:** Two cases in DB; second is `LINKED` to first; reply cites first case number.

---

### 5.3 Missing information

**What:** Desk asks only what policy requires before acting (unless URGENT).

**Trigger:** Incomplete request (e.g. travel without dates).

**Expected:** Reply lists missing questions; case `AWAITING_INFO`; after employee answers, case progresses.

---

### 5.4 Approval (sensitive / over spend limit)

**What:** Ops must approve before dispatch.

**Trigger:** e.g. server-room access, or spend above department limit.

**Technical path:** `assess_risk` → `Approval` PENDING → OPS DECISION mail (+ signed links bound to approver email) → approve → dispatch.

**Verify:**

1. Case stage `AWAITING_APPROVAL`.
2. Ops replies `approve` on that thread (SPF/verification OK) **or** uses one-click link.
3. Employee gets “approved and assigned…”; stage `DISPATCHED`.

---

### 5.5 Team completion + spend on ledger

**What:** Team closes loop; amounts in the note become ledger spend.

**Trigger:** Facilities replies `done, compressor replaced, INR 12500`.

**Technical path:** `apply_team_reply` → `_resolve` → ledger `TEAM_DONE` + `SPEND_RECORDED` → requester update.

**Verify:** Case `RESOLVED`; requester mail “taken care of”; later ops spend question includes 12500.

---

### 5.6 Ops analytics over email (ledger Q&A)

**What:** Ops asks operational questions; answers come **only** from ledger (no invented totals).

**Examples:**

- “How much did FACILITIES spend in the last 30 days?”
- “What was repaired last 30 days?”
- “What needs replacing / low stock?”
- “Who did what on FAC-2026-0042?”

**Technical path:** `is_ops_authority` + `verify_ops_sender` + `answer_admin_question` → reply; **no new Outcome**.

**Verify:** With known spend rows, reply shows matching INR total and case lines. Spoofed From without SPF (strict mode) → **no** analytics reply.

---

### 5.7 Visitor pass / parking / supplies

| Request | Expected |
|---------|----------|
| Visitors with names/date | Pass codes issued; gate manifesto mail; case completed or dispatched |
| Visitor parking | Slot allotted or team asked to arrange |
| Supplies matching a SKU | Stock qty reduced; if below min → reorder case/mail; ledger stock events |

**Verify:** Check console case facts (`visitor_passes`, `parking`, `stock_issue`) and outbound mails.

---

### 5.8 Travel flight options

**What:** When travel asks for flights and keys are configured, schedule options attach to the case (fare confirmation remains Travel Desk).

**Verify:** With SerpAPI/Amadeus configured, travel case facts include `flight_options`; without keys, case still opens without live options.

---

### 5.9 SLA remind and escalate

**What:** Mid-SLA reminder to team; at due, escalate to ops (facilities get stalled investigation notes).

**Technical path:** Worker/web `run_all_sweeps` → `sweep_desk_cases`.

**Verify:** Advance clock in test or wait; facts get `sla_reminded_at` / `sla_escalated_at`; escalation mail to ops.

---

### 5.10 Vendor lifecycle (console + email only)

**Flow:**

1. **Ops** → Vendors → Invite (name, email, category) → system emails registration link.
2. **Vendor** opens `/vendor-register/{token}` → submits GST/PAN, coverage, compliance, docs flags, manpower/financial.
3. Status → `UNDER_REVIEW`; deterministic **score** + tier (`PREFERRED` / `APPROVED` / `CONDITIONAL`).
4. **Ops** opens vendor → Recompute score → **Activate** (optional contract row) → status `ACTIVE`.
5. Desk work orders prefer higher-score ACTIVE vendors for that category.
6. **Suspend / Blacklist** removes them from desk eligibility immediately.
7. **Scorecard** shows ledger-backed WO/spend counts (empty until work happens).

**APIs:**

- Ops: `POST /api/v1/vendors/invite`, `GET /vendors`, `POST /vendors/{id}/activate`, …
- Public: `GET/POST /api/v1/public/vendors/register/{token}`

**Verify (end-to-end):**

1. Invite “CoolAir HVAC” / cool@example.com / hvac.
2. Open registration URL from invite response or email.
3. Submit form → see “UNDER_REVIEW” and a provisional score.
4. In console Activate → status ACTIVE, tier set.
5. Raise an AC employee mail → work order “Preferred vendor” includes CoolAir when it is the best ACTIVE match.
6. Suspend CoolAir → new AC cases must not prefer it.

---

### 5.11 Unknown sender protection

**What:** With default `ACCEPT_REQUESTS_FROM=employees`, outsiders get no reply and no case.

**Verify:** Mail from random@gmail.com → stored event flagged ignored; no outbound reply.

---

### 5.12 Security controls (IT checklist)

| Control | Expected behaviour |
|---------|-------------------|
| Login RBAC | Non-ops roles cannot demo-reset / forge intake |
| Tenant | API uses logged-in user’s `tenant_id` |
| API email ingest | Cannot forge SPF/DKIM headers |
| Ops analytics | Requires sender verification like commands |
| Approval links | Bound to intended approver email (`for=` + HMAC) |
| OAuth callback | Invalid state rejected (no first-tenant fallback) |
| Vendor register | Expired/invalid token rejected |
| ACTIVE gate | Suspended vendors never appear in resolution vendor list |

---

## 6. Database tables that matter for verification

| Table | What you’ll see |
|-------|-----------------|
| `raw_email_events` | Every inbound mail |
| `outcomes` | Cases (`case_reference`, `facts`, status) |
| `service_tickets` | Desk ticket mirror |
| `communications` | Outbound emails |
| `approvals` | Pending/decided approvals |
| `ops_ledger_events` | Who/what/when/amount memory |
| `vendors` | Lifecycle status, score, token fields |
| `vendor_coverage` | State/city/office coverage |
| `contracts` | Created on vendor activate (optional) |
| `stock_skus` | Supplies inventory |
| `persons` / `departments` / `locations` | Org setup |
| `visitor_passes` | Issued visitor codes |

**Ledger event examples:** `CASE_OPENED`, `PLAN_PROPOSED`, `WORK_ORDER_SENT`, `TEAM_DONE`, `SPEND_RECORDED`, `CLOSED`, `VENDOR_INVITED`, `VENDOR_REGISTERED`, `VENDOR_ACTIVATED`, `STOCK_ISSUE`, `SLA_ESCALATED`.

---

## 7. End-to-end client runbooks (sign-off)

Use these as a demo script. Tick when observed.

### Runbook A — HVAC repair to spend Q&A

- [ ] Employee AC mail → case + WO
- [ ] Team `done … INR 12500` → resolved + requester update
- [ ] Ops “How much did FACILITIES spend…” → includes 12500
- [ ] Ledger rows exist for open / WO / done / spend

### Runbook B — Approval then dispatch

- [ ] Sensitive request waits for approval
- [ ] Ops approve → dispatched
- [ ] Unverified spoof cannot approve (strict mode)

### Runbook C — Vendor onboard to WO hint

- [ ] Invite → register link → UNDER_REVIEW + score
- [ ] Activate → ACTIVE
- [ ] Matching facilities WO shows preferred vendor
- [ ] Suspend → vendor no longer preferred

### Runbook D — Supplies reorder

- [ ] SKU below min after issue → reorder mail/case
- [ ] Ledger stock events present

### Runbook E — SLA

- [ ] Reminder and/or escalation mails fire when sweeper/worker runs

### Runbook F — Setup integrity

- [ ] Unknown sender ignored
- [ ] Known employee served
- [ ] Console Vendors + Company data usable by admin login

---

## 8. V3 production spine (added)

| Capability | How to verify |
|------------|---------------|
| Unified Outcome spine | Open a facilities case → DB has Requirement `FULFIL` + Task `WO`; meeting/invoice outcomes stamped `facts.unified_spine=true` |
| Legal entities | `GET /api/v1/entities` after bootstrap shows `DEFAULT` |
| Policies / budgets | `POST /api/v1/policies`, `POST /api/v1/budgets` then open a high-spend case |
| Assets / PM / incidents | `POST /api/v1/assets`, `/facilities/pm-schedules`, `/facilities/incidents` |
| AMC / projects | `POST /api/v1/amc/obligations`, `POST /api/v1/projects` |
| Mailroom / joiner / utilities | `POST /api/v1/admin-modules/mail`, `/lifecycle`, `/utilities` |
| Control tower | `GET /api/v1/control-tower/summary` |
| Failures console | Console → More → Failures |
| P2P | `POST /api/v1/p2p/purchase-requests`, `/purchase-orders`, `/grn`, `/ses` |
| Sourcing (RFQ) | `POST /api/v1/sourcing/requirements` → RFQ → quotes → award |
| Workplace | `POST /api/v1/workplace/seats/allocate`, visitor check-in/out |
| Fleet / travel | `POST /api/v1/fleet/trips`, `/travel/itineraries` |
| PM sweeper | Worker creates PM work orders when schedules are overdue |

Module status matrix: [V3_MODULE_GAP_MATRIX.md](V3_MODULE_GAP_MATRIX.md).  
Specs: [V3_ERD_AND_SOR.md](V3_ERD_AND_SOR.md), [V3_DR_AND_ACCEPTANCE.md](V3_DR_AND_ACCEPTANCE.md).

---

## 9. Honest scope notes (avoid surprises)

1. **Meeting booking runtime** still uses `ClientMeetingOrchestrator` for room holds/confirm; it now **shares** the Outcome→Requirement→Task spine with desk/invoice (`UNIFIED_OUTCOME_SPINE=true`).
2. **Vendor portal:** Not a separate product — invite link + admin Vendors page only.
3. **Scores:** Vendor scores are **deterministic from submitted fields**, not generative AI guesses. Performance scorecard is **ledger-only**.
4. **Flights:** Live options need API keys; otherwise travel cases still work without schedules.
5. **ERP/HRMS:** Production connectors are defined (`CertifiedStubERP` / `CertifiedStubHRMS` for CI). Live post/pay needs client credentials (Phase 9).
6. **Multi-entity:** `LegalEntity` + worker multi-tenant isolation landed; full ABAC field-level matrix and DR restore drill remain for go-live sign-off.

---

## 10. Client sign-off

| Area | Client initials | Date |
|------|-----------------|------|
| Onboarding / Setup | | |
| Employee request + WO loop | | |
| Approvals | | |
| Ledger / ops analytics | | |
| Vendor invite → activate → desk use | | |
| Security checks (unknown sender, verification) | | |
| SLA sweeps | | |

**Document version:** matches codebase after full vendor console+email workflow and security harden. Update this pack when folding meeting/invoice fully into the desk or adding new modules.
