# V3 DR + Acceptance gates (Phase 9 scaffolding)

## Disaster recovery

| Item | Target | Evidence to capture |
|------|--------|---------------------|
| RPO | ≤ 15 minutes (DB continuous backup / PITR) | Backup job logs |
| RTO | ≤ 4 hours for core email desk | Restore drill report |
| Worker crash | Jobs reclaimable; no duplicate external sends (idempotency keys) | Replay test |
| Mail provider outage | Queue intake; human fallback mailbox | Outage runbook |
| AI outage | Deterministic classification / human review | `AI_EMERGENCY_STOP` drill |

Restore drill checklist:

1. Snapshot/backup restore to non-prod  
2. Run `init_db` / schema sync  
3. Smoke: login, ingest test mail, vendor list, approval link  
4. Confirm no duplicate `ProcessingJob` side-effects after replay  

## Gate evidence matrix (G0–G8)

| Gate | Status | Evidence location |
|------|--------|-------------------|
| G0 Specification | Done | [V3_ERD_AND_SOR.md](V3_ERD_AND_SOR.md) |
| G1 Foundation | In progress | LegalEntity, Outbox, worker multi-tenant, SoD helpers |
| G2 Engines | In progress | `backend/app/engines/*` + `/policies` `/budgets` |
| G3 AI/Core | In progress | ContextGateway + AIGovernance |
| G4 Outcome | Advanced | Unified spine ON for desk + meeting/invoice materialize; booking runtime shared |
| G5 Facilities | Advanced | `/assets` `/facilities` `/amc` + stock reservations |
| G6 P2P | Advanced | MatchingEngine wired into invoice scenario + CertifiedStubERP |
| G7 Failure/Security | Partial | Failures UI; SoD helpers; approval `for=` bound; DR drill pending |
| G8 Learning/Handover | Partial | Control tower + verification pack updated; live UAT pending |

## 14 completeness criteria

Track owners at UAT; none are claimed complete until Phase 9 sign-off with behavioural evidence.
