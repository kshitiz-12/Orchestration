# 01 — Core data model

The entities every module shares. Modules (facilities, travel, supplies …) add their own tables, but always hang off
these. Every table carries `tenant_id`; every row is created, changed and read inside one tenant.

Notation: **bold** = new entity, *italic* = exists today and is extended, `code` = existing table name.

---

## 1. Tenant & organisation

### *Tenant* (`tenants`)
The customer company.
- `tenant_id`, `name`, `legal_name`, `region`, `status` (TRIAL / ACTIVE / SUSPENDED)
- `timezone` (default Asia/Kolkata), `currency` (INR), `locale`
- `inbound_addresses` — mail addresses that belong to this tenant (how inbound mail finds its company)
- `plan`, `limits` (seats, AI budget), `branding` (sender name, signature, logo)

### **OrgUnit**
One tree for the company's structure: business unit → department → sub-team. Separate from places, because a
department spans branches and a branch hosts many departments.
- `org_unit_id`, `tenant_id`, `parent_id`, `type` (BUSINESS_UNIT / DEPARTMENT / TEAM), `code`, `name`, `head_person_id`

### *Place* (today `locations` + `resources`)
One tree for physical space, any depth: region → city → branch → building → floor → zone → room / desk / parking slot.
- `place_id`, `tenant_id`, `parent_id`, `type` (REGION / CITY / BRANCH / BUILDING / FLOOR / ZONE / ROOM / DESK /
  PARKING / GUEST_HOUSE / STORE), `code`, `name`, `aliases[]`
- `address`, `geo` (lat/long, optional), `timezone` (inherits tenant)
- `capacity`, `facilities[]` (VC, projector, whiteboard …), `hours`, `is_bookable`, `status`
- `qr_code` (for QR-initiated requests later)

"Branch" is simply a Place with `type = BRANCH`. Everything that is "per branch" points at a Place and inherits down.

### *Person* (`persons`)
- `person_id`, `tenant_id`, `employee_code`, `email` (unique **per tenant**, not globally), `name`, `phone`
- `designation`, `grade`, `org_unit_id`, `manager_id`, `cost_centre_id`
- `home_place_id` (their branch), `seat_place_id` (desk), `employment_type` (EMPLOYEE / CONTRACTOR / INTERN)
- `joined_on`, `exit_on`, `status` (ACTIVE / ON_NOTICE / EXITED)
- `source` (IMPORT / API / CONNECTOR:keka …), `source_ref`, `synced_at`

### **PersonLocationOverride**
Where someone is *right now* when it differs from their home branch (travel, temporary posting, WFH).
- `person_id`, `place_id`, `from_date`, `to_date`, `reason` (TRAVEL / DEPUTATION / TEMPORARY), `source_case_id`

Created automatically from approved travel cases, or imported. The context engine uses it to answer "which branch is
this request for?" — e.g. Kapil (home: Pune) asks for a meeting room on a date he is in Delhi.

### **Role** and **RoleAssignment**
- Roles: EMPLOYEE, TEAM_MEMBER, BRANCH_ADMIN, REGIONAL_ADMIN, CENTRAL_ADMIN, APPROVER, FINANCE, AUDITOR, VENDOR, …
- `RoleAssignment(person_id, role, scope_place_id?, scope_org_unit_id?, valid_from, valid_to)`
- A scope means "this role for this part of the tree and everything below it". Delegation = a time-bound assignment.

---

## 2. Teams, services & vendors

### *Team* (today `departments`)
Who does the work. A team is either central or attached to a Place, and handles a set of services.
- `team_id`, `tenant_id`, `code`, `name`, `kind` (INTERNAL / VENDOR)
- `scope_place_id` (null = whole company), `org_unit_id` (optional)
- `inboxes[]` (primary + backups), `lead_person_id`
- `handover_info` (pickup instructions; exists today), `working_hours`

Routing: for a request at place P of service S, take the team for S at P; if none, walk up the Place tree; if still
none, the tenant's central team; if none, the branch admin.

### **ServiceType** (today `playbooks.py`, hard-coded)
The request catalogue, as data. A global default catalogue ships with the product; each tenant switches entries on,
renames them or adds its own.
- `code` (hvac, catering, travel …), `label`, `aliases[]`, `module` (FACILITIES / TRAVEL / SUPPLIES …)
- `required_fields[]` (each: key, aliases, question), `nice_to_have[]`
- `default_team_code`, `case_prefix`, `sla` (response / resolution hours by priority)
- `evidence_rule` (what proof closes it), `collectable` (requester picks something up)
- `workflow_id` (which workflow template runs it), `is_active`

### *Vendor* (`vendors`) and *Contract* (`contracts`)
- Vendor: services, branches served, contacts, licences (with expiry), compliance documents, rating
- Contract: vendor, services, places covered, rate card, SLA terms, start/end, notice period, renewal owner

### *SiteService* (`site_services`)
How a service is delivered at a place (included / contract / chargeable) and its rate. Keep as is; rename `site`
string to `place_id`.

---

## 3. Policy & authority

Detailed in doc 02. Entities:

- **Policy** — a named, versioned rule set (e.g. "Supplies entitlement 2026").
- **PolicyRule** — one rule: scope, applies-to, condition, effect (allow / limit / require approval / block / route).
- **ApprovalChain** — ordered or parallel approval steps, where each approver is a role ("branch admin of the case's
  branch", "requester's manager", "finance") rather than a named person.
- **Entitlement ledger** (see §5) — what each person has consumed against a limit.
- **Exception** — an approved one-off override of a rule, with who approved it and until when.

---

## 4. Work: cases, tasks, approvals, evidence

### *Case* (today `outcomes`)
The business objective. One per thing the requester wants achieved.
- `case_id`, `tenant_id`, `reference` (ITS-2026-0001), `service_type_code`, `title`, `summary`
- `requester_person_id`, `requester_email`, `on_behalf_of_person_id`
- `place_id` (where the work is), `cost_centre_id`, `org_unit_id`
- `priority`, `stage` (structured column; today hidden inside `facts.agent_stage`), `status`, `due_at`
- `details` (extracted fields), `context_snapshot` (who/where/policy at decision time — for audit)
- `workflow_id` + `workflow_version`, `policy_version`
- `outcome_criteria`, `verified_at`, `closure_type`, `closed_at`
- `source_channel` (EMAIL / WEB / WHATSAPP / QR / SCHEDULE / EVENT), `conversation_id`

Today a lot lives in `outcomes.facts` (JSON). The rule going forward: anything we filter, report or decide on gets a
real column; `details` stays JSON for service-specific fields.

### *Task* (`tasks`), *Approval* (`approvals`), *Evidence* (`evidence`), *Communication* (`communications`)
Keep. Changes:
- Task: `assignee_team_id`, `assignee_person_id`, `kind` (HUMAN / VENDOR / SYSTEM / APPROVAL), dependencies already exist.
- Approval: `chain_id`, `step`, `approver_role`, `resolved_approver_person_id`, `policy_rule_id` (why it was needed),
  `due_at`, `delegated_from`.
- Evidence: already right; add `kind` PHOTO / NOTE / SIGNATURE / DOCUMENT / GPS.

### **Event**
Anything that starts or changes work, from any source.
- `event_id`, `tenant_id`, `type` (EMAIL_RECEIVED, EMPLOYEE_JOINED, EMPLOYEE_EXITED, STOCK_BELOW_REORDER,
  COMPLIANCE_EXPIRING, ASSET_BREAKDOWN, INVOICE_RECEIVED, TRAVEL_APPROVED, SCHEDULE_DUE …)
- `payload`, `source`, `idempotency_key`, `received_at`, `processed_at`, `result_case_ids[]`

Today only email produces events (`raw_email_events`). The event table generalises it.

### **Schedule**
Recurring work: preventive maintenance, checklists, compliance checks, reports, morning briefing.
- `schedule_id`, `tenant_id`, `service_type_code` or `workflow_id`, `place_id`, `asset_id`, `rrule`, `next_run_at`

---

## 5. Things, stock & money

### *Asset* (`assets`)
- `asset_id`, `tag`, `qr_code`, `type`, `make`, `model`, `serial`, `place_id`, `custodian_person_id`
- `purchased_on`, `cost`, `warranty_until`, `amc_contract_id`, `criticality`, `status`, `health_score`

### **Item** and **StockLevel**
- Item: `sku`, `name`, `unit`, `category`, `approved_vendor_id`, `rate`
- StockLevel: `item_id`, `place_id` (store), `on_hand`, `min`, `max`, `reorder_point`

### **Entitlement ledger** (`EntitlementUsage`)
Every time something countable is given, a row is written: `person_id`, `entitlement_key` (e.g. `stapler`,
`laptop`, `catering_spend`), `quantity` or `amount`, `case_id`, `period_key` (2026, 2026-10), `at`.
The policy engine sums this to answer "has this person/department used their limit?". Works for any limit — items,
money, bookings — not just staplers.

### **Budget** and **SpendTransaction**
- Budget: `cost_centre_id` or `org_unit_id` or `place_id`, `period`, `category`, `amount`
- SpendTransaction: `case_id`, `vendor_id`, `amount`, `tax`, `category`, `cost_centre_id`, `place_id`, `org_unit_id`,
  `status` (COMMITTED / ACTUAL / REVERSED), `source` (APPROVAL / PO / INVOICE / IMPORT), `at`

This is what makes "what was IT's spend this month?" a query, not a guess.

### *PurchaseOrder*, *Receipt*, *Invoice* (exist)
Keep; link to SpendTransaction, Budget and Case.

### **ComplianceObligation**
- `place_id`, `kind` (FIRE_NOC, LIFT_LICENCE, DG_CONSENT, ELECTRICAL_INSPECTION, FSSAI, SHOPS_ESTABLISHMENT,
  INSURANCE, custom), `authority`, `document_ref`, `valid_from`, `valid_until`, `owner_person_id`,
  `reminder_days[]` (30/15/7)

---

## 6. Knowledge & learning (exist, keep)

- *KnowledgeEntry* — add `place_id` scope (branch-specific answers) and `version`.
- *LearningRecord* — keep; later add embeddings when knowledge outgrows the prompt.

---

## 7. Mapping from today's tables

| Today | Becomes | Change |
|---|---|---|
| `tenants` | Tenant | add timezone, inbound addresses, branding, plan |
| `locations` + `resources` | Place | merge into one tree; `resources` rows become ROOM / DESK / PARKING places |
| `persons` | Person | email unique per tenant; add grade, org unit, home place, cost centre, source |
| `departments` | Team | add scope place, multiple inboxes already exist |
| `playbooks.py` (code) | ServiceType | move to a table with a shipped default catalogue |
| `cost_centres` | CostCentre | keep; approver moves into ApprovalChain |
| `outcomes` | Case | promote stage, place, cost centre, workflow/policy versions to columns |
| `service_tickets` | — | fold into Case (duplicate of the same information today) |
| `site_services` | SiteService | `site` text → `place_id` |
| `business_rules`, `outcome_templates`, `services`, `notification_templates` | Policy / Workflow / ServiceType / Template | mostly unused today; replace rather than extend |
| `raw_email_events` | Event (EMAIL_RECEIVED) | keep as the email payload store; Event wraps it |
| `visitor_passes`, `room_bookings` | module tables | keep, add `place_id` |

## 8. Rules for every table

1. `tenant_id` on every row; every query filtered by it (later enforced by PostgreSQL Row-Level Security).
2. IDs stay random (`uuid4`-based) — no guessable sequences in URLs.
3. Anything used for routing, filtering, reporting or a decision is a column, not buried in JSON.
4. Every change to master data and every decision writes an audit row.
5. Imported rows keep `source` and `source_ref` so re-syncs update instead of duplicating.
