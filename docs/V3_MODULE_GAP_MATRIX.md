# V3 Module gap matrix (living)

Updated after production-gap closing pass. Status reflects **runtime behaviour**, not docs alone.

| ID | Module | Status | Notes |
|----|--------|--------|-------|
| M01 | Helpdesk | Partial→Advanced | Desk + spine + AMC/evidence gates |
| M02 | Space/Seating | Partial→Advanced | Seat allocate/release API + desk seating path |
| M03 | Asset lifecycle | Partial | CRUD + status; custody/disposal still thin |
| M04 | AMC | Partial→Advanced | Obligations + dispatch coverage hint |
| M05 | Corrective | Partial→Advanced | Desk + AMC gate + resolution |
| M06 | Preventive | Partial→Advanced | PM sweeper → WO in `run_all_sweeps` |
| M07 | Soft services | Partial | Round log API; no roster/SES loop |
| M08 | Safety/Access | Partial | Incidents + sensitive WOs |
| M09 | Visitors/Parking | Partial→Advanced | Pass + check-in/out + expiry sweep |
| M10 | Meetings | Partial→Advanced | Shared spine + booking orchestrator |
| M11 | Travel | Partial→Advanced | Itinerary + duty_of_care record |
| M12 | Transport/Fleet | Partial→Advanced | Vehicles + trips |
| M13 | Cafeteria | Partial | Catering helpers |
| M14 | Mailroom | Partial→Advanced | MailItem API |
| M15 | Inventory | Partial→Advanced | Reserve + GRN→stock post |
| M16 | Sourcing | **Was Missing → Advanced** | RFQ/quote/compare/award |
| M17 | Vendor onboard | Advanced | Invite→activate |
| M18 | Contracts/perf | Partial | Contract + scorecard + AMC |
| M19 | PR/PO | Partial→Advanced | `/p2p` PR/PO |
| M20 | GRN/SES | Partial→Advanced | `/p2p/grn` `/p2p/ses` |
| M21 | Invoice | Partial→Advanced | Match engine + stub ERP post |
| M22 | Incidents/BCP | Partial | Raise/close; fan-out thin |
| M23 | Utilities/ESG | Partial | Utility readings |
| M24 | Employee lifecycle | Partial | Checklist API + desk fan_out (not fully unified) |
| M25 | Projects | Partial→Advanced | Project CRUD |
| M26 | Control tower | Partial→Advanced | Live summary counts |

**Still not 100% production Done:** live ERP/HRMS/IdP, full soft-service/SES loop, emergency fan-out, ABAC field matrix, DR restore drill evidence, client UAT on 14 criteria.
