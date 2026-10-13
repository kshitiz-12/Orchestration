# Facilities.docx gap matrix (scoped)

**Source:** `facilities.docx` Parts I §§2–11 (+ acceptance §13.2 relevant items)  
**Product exclusions (explicit):**

1. Real estate / lease commercial masters (rent, landlord, lease ID, deposits)
2. Mobile field apps / IoT sensors / GPS telemetry

**Verdict:** **100% of in-scope facilities.docx capabilities** are implemented in code (models + services + APIs + tests). Live ERP/HRMS connectivity and org-specific UAT remain environment concerns, not blueprint gaps.

| Section | Topic | Status | Evidence |
|--------|--------|--------|----------|
| 2 | Org / location hierarchy | Done | `Location` typology + parent hierarchy; `attributes` profile |
| 2.3 | Location master mandatory data | Done | `PUT /facilities/locations/{id}/profile` — address, CC, owner, criticality, service bundle (lease keys stripped) |
| 3.1–3.2 | Building / engineering infra | Done | Captured via `SpaceUnit` zones (HVAC/fire) + asset/engineering masters; no lease |
| 3.3 | Space master | Done | `SpaceUnit` — type, room type, capacity, amenities, accessibility |
| 4.1 | Service catalogue fields | Done | `EnterpriseServiceItem` + `/facilities/catalogue` |
| 5.1–5.2 | Asset classification / master | Done | `Asset` + enrich/completeness (make/model/serial/warranty/criticality) |
| 5.3 | AMC contract model | Done | `AmcObligation` + `/facilities/amc/vendor-call` |
| 5.4 | PM schedule / job plans | Done | `PreventiveSchedule` + `PmJobPlan` |
| 6.1–6.2 | Inventory / item master | Done | Extended `StockSku` + entitlements |
| 6.3 | Replenishment / controls | Done | Reorder, cycle count, expiry batches, issue entitlement checks |
| 7.1–7.3 | Budget lifecycle | Done | Reserve → commit → accrue → actual; available formula includes accruals |
| 7.5 | Chargeback | Done | `ChargebackRule` methods DIRECT/AREA/HEADCOUNT/METERED/… + allocate |
| 8 | Procurement / vendors / billing | Done (prior) | P2P, RFQ, contracts, SES, invoice match — unchanged |
| 9.1–9.3 | Request / WO / incident | Done | `WorkOrder` spine + duplicate detect + AMC gate; incident emergency fan-out |
| 9.4 | Projects / branch lifecycle | Done (prior) | `ProjectRecord` + workplace lifecycle |
| 10.2 | Compliance register | Done | `ComplianceRequirement` + due/overdue sweeper |
| 10.3 | Risk register | Done | `RiskRegisterItem` |
| 10.4 | BCP / emergency readiness | Done | `BcpPlan` + `EmergencyDrill` (no mobile/sensor) |
| 10.x | ESG metrics | Done | `EsgMetric` (manual/integration readings, not IoT) |
| 11 | Dashboards / data model | Done | `/facilities/dashboard` + ERD tables above |
| Soft services | Schedule → round → SES | Done | `SoftServiceSchedule` → generate → `complete-ses` |
| §13.2 | Acceptance (in-scope) | Done | Completeness APIs, AMC gate, SES link, SoD (prior), SLA clocks (prior), compliance alerts |

## Intentionally not built

| Topic | Reason |
|-------|--------|
| Lease / rent / landlord / deposit | User exclusion: real estate |
| Mobile offline WO / QR field app | User exclusion: mobile field |
| Sensor / BMS / GPS auto-tickets | User exclusion: IoT / mobile field |

## Tests

`backend/tests/test_facilities_enterprise.py` — location/space, catalogue/WO, asset/AMC, inventory, budget/chargeback, compliance/BCP/incident/soft-SES, PM job plans.
