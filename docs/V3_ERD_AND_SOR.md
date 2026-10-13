# AdminServices V3 — Executable SRS (Gate G0)

**Status:** Approved build baseline for 100% production delivery  
**Source:** `AdminServices_Enterprise_Blueprint_V3_Complete_Detailed.docx` (V3, 12 Oct 2026)  
**Principle:** Preserve working email desk / ledger / vendor / approvals; migrate into one spine. No demo leftovers at Gate G8.

---

## 1. Glossary (minimum)

| Term | Meaning |
|------|---------|
| Tenant | Customer isolation boundary |
| LegalEntity | Books / tax / approval scope inside a tenant |
| Outcome | One parent business result across modules |
| Requirement | Satisfiable need under an outcome |
| Task | Executable work unit with owner, SLA, evidence |
| Context Gateway | Only authorised facts AI may use (IDs, freshness, unavailable fields) |
| Control engine | Effective-dated Approval / SLA / Rate / Budget / Resource / Matching / Evidence |
| Ops ledger | Operational spend/events — **not** financial truth |
| Cost / Invoice / ERP status | Commercial and accounting states, kept separate |

---

## 2. System-of-record matrix

| Domain | System of record | AdminServices role |
|--------|------------------|--------------------|
| Employee identity / hierarchy | HRMS / IdP | Sync + entitlement cache |
| Cost centres / GL / payment | ERP / Finance | Reference + post status; no direct pay |
| Vendor commercial master (bank) | ERP / Procurement | Onboard + verify refs; bank change maker-checker |
| Location / space / seat | AdminServices | Own |
| Asset / AMC / PM | AdminServices (CMMS) | Own; ERP asset link optional |
| Service / SiteService catalogue | AdminServices | Own |
| Contract / SLA obligations | AdminServices + Legal | Own operational copy |
| Policy / approval / rate / budget rules | AdminServices | Own (effective-dated) |
| Outcome / task / evidence / comms | AdminServices | Own |
| PO / GRN / SES / invoice match | AdminServices + ERP | Match here; post/pay in ERP |
| Mail thread | Mail provider | Store + correlate |

---

## 3. Target ERD (canonical objects)

```
Tenant 1──* LegalEntity 1──* OrgUnit
Tenant 1──* Person (entity_id?, site_id, roles)
Tenant 1──* Location (hierarchy site→seat)
Tenant 1──* ServiceCatalog / SiteService
Tenant 1──* Asset / StockItem
Tenant 1──* Vendor / VendorCoverage / Contract / RateCard
Tenant 1──* PolicyRule (versioned) / Budget
Tenant 1──* Outcome 1──* Requirement / Task / Approval / Evidence
Tenant 1──* CostRequirement / PurchaseOrder / Receipt|SES / Invoice
Tenant 1──* OpsLedgerEvent (ops only)
Tenant 1──* OutboxEvent / AuditEvent
```

Implementation lands additively via schema sync; dual spines removed in Phase 4.

---

## 4. Module backlog M01–M26

| ID | Module | Phase | Gate |
|----|--------|-------|------|
| M01 | Service Request and Helpdesk | 4–5 | G4/G5 |
| M02 | Workplace, Space and Seating | 5 | G5 |
| M03 | Asset Lifecycle | 5 | G5 |
| M04 | AMC and Contract Maintenance | 5 | G5 |
| M05 | Corrective Maintenance | 5 | G5 |
| M06 | Preventive/Predictive Maintenance | 5 | G5 |
| M07 | Housekeeping / Soft Services | 5 | G5 |
| M08 | Safety, Security, Access | 5 | G5 |
| M09 | Visitors, Reception, Parking | 7 | G7 |
| M10 | Meetings, Events | 4+7 | G4 |
| M11 | Travel / Accommodation | 7 | — |
| M12 | Transport / Cab / Fleet | 7 | — |
| M13 | Cafeteria / Pantry | 7 | — |
| M14 | Mailroom / Courier | 7 | — |
| M15 | Inventory / Stores | 5 | G5 |
| M16 | Vendor Sourcing | 6 | G6 |
| M17 | Vendor Due Diligence / Onboarding | 6 | G6 |
| M18 | Contracts / Performance | 6 | G6 |
| M19 | Procurement / PR / PO | 6 | G6 |
| M20 | GRN / SES | 6 | G6 |
| M21 | Invoice / Matching / Settlement | 6 | G6 |
| M22 | Incidents / BCP | 8 | G8 |
| M23 | Utilities / ESG | 8 | — |
| M24 | Employee Lifecycle Workplace | 7 | — |
| M25 | Projects / Property / Insurance | 8 | — |
| M26 | Analytics / Control Tower / AI Learning | 8 | G8 |

---

## 5. NFR (production)

- Isolation: tenant, legal entity, site, department, field; vendor external boundary  
- Idempotency on writes; duplicate-safe mail/job processing  
- Retry + DLQ + reconciliation for integrations  
- Observability: correlation IDs, failure console, sweep health  
- DR: backup/restore runbook; RPO/RTO evidenced in Phase 9  
- AI: structured output, confidence gate, no inventing masters  

---

## 6. Security baseline

- JWT + role matrix; SoD (requester ≠ approver ≠ buyer ≠ receiver ≠ payer where configured)  
- No AI approval of vendors, invoices, payments, employment, legal  
- Approval links: HMAC + intended approver; single-use where required  
- Secrets in env/vault; weak defaults blocked  
- Append-only audit for AI, human, system, vendor actions  

---

## 7. Gate G0 checklist

| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | Scope = full V3 TARGET | This doc + DOCX |
| 2 | Glossary + SoR agreed | §§1–2 |
| 3 | ERD target defined | §3 |
| 4 | Module backlog phased | §4 |
| 5 | NFR + security stated | §§5–6 |
| 6 | Dual-spine retirement planned | Phase 4 |
| 7 | Completeness = 14 DOCX criteria | Phase 9 sign-off |

**G0 status:** Complete for build start.

---

## 7b. Build progress (living)

| Phase | Status | Landed in repo |
|-------|--------|----------------|
| 0 SRS | Done | This document |
| 1 Foundation | Done | `LegalEntity`, `OutboxEvent`, multi-tenant worker, SoD/site helpers, `/entities`, Failures nav |
| 2 Masters | Done (core) | `PolicyRule`, `Budget`, `/budgets`, `/policies` |
| 3 Engines | Done (core) | Approval/SLA/Budget/Evidence/Matching/Rate/Resource |
| 4 Orchestration | Advanced | Unified spine ON (`unified_outcome_spine`): meeting/invoice materialize + desk Requirement/Task + MatchingEngine cross-check; booking runtime still ClientMeetingOrchestrator |
| 5 Facilities | Advanced | `/assets`, `/facilities`, `/amc`, stock reserve/bin/batch fields |
| 6 P2P | Advanced | CostRequirement/SES/ErpHandoff, MatchingEngine wired into invoice scenario |
| 7 Admin | Advanced | `/admin-modules` mailroom, joiner/leaver, utilities; HRMS stub |
| 8 Extended | Advanced | Incidents, `/control-tower`, `/projects`, utility readings |
| 9 Production | Scaffolded | [V3_DR_AND_ACCEPTANCE.md](V3_DR_AND_ACCEPTANCE.md) — live ERP/IdP + UAT/DR drills remaining |

---

## 8. Immediate refactor priorities (§29) → phases

1. Dual spine → Phase 4  
2. Outcome/Requirement/Task/Evidence SoR → Phase 4  
3. Context Gateway → Phase 4  
4. Canonical masters → Phase 2  
5. Ledger ≠ finance → Phase 6  
6. Approval/SLA engines → Phase 3  
7. Vendor DD upgrade → Phase 6  
8. AI governance → Phase 4  
9. Tenant/entity/site isolation → Phase 1  
10. Failure console + acceptance → Phase 1 + 9  
