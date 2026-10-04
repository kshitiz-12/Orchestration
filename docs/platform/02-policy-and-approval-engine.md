# 02 — Policy & approval engine

One engine decides, for every case, what is allowed, what needs approval, who approves, and what limits apply.
Every module uses it; no module has its own approval or limit logic (blueprint non-negotiable).

## 1. What it answers

Given a case (who, where, what, how much, when), the engine returns a **decision**:

```json
{
  "outcome": "ALLOW | REQUIRE_APPROVAL | BLOCK | ASK",
  "reasons": [{"rule": "SUP-STAPLER-LIMIT", "text": "3rd stapler this year; limit is 2", "evidence": ["SUP-2026-0007 on 12 Feb", "SUP-2026-0031 on 3 Jul"]}],
  "approval_chain": [{"step": 1, "role": "BRANCH_ADMIN", "resolved": "neha@acme.com", "due_hours": 8}],
  "limits": [{"key": "stapler", "used": 2, "limit": 2, "period": "2026"}],
  "routing": {"team": "ADMIN@PUNE"},
  "policy_version": "2026.3",
  "inputs_snapshot": {"grade": "L3", "place": "Pune", "amount": 0}
}
```

The decision is deterministic: same inputs, same policy version → same answer. It is stored on the case, so anyone
can later see *why* something needed approval.

## 2. Inputs (the context engine builds these)

| Input | From |
|---|---|
| Requester: grade, org unit, manager, cost centre, home branch, current branch | Person, PersonLocationOverride |
| Service type and extracted details (quantity, amount, dates, items) | Case (AI extraction, then validated) |
| Place of the work (branch, building) | Case → Place tree |
| Amount: stated, or computed from rate card × quantity | details, SiteService, Contract, Item rate |
| Consumption so far | Entitlement ledger, SpendTransaction |
| Budget remaining | Budget − committed − actual |
| Time | request time vs working hours / holidays of that place |
| Risk signals from the AI | sensitive topic, unclear request, confidence |

The AI can **add** caution (flag something as sensitive). It can never remove a rule's requirement.

## 3. How a rule is written

Rules are rows, not code. Each rule has a scope, what it applies to, a condition and an effect.

```yaml
code: SUP-STAPLER-LIMIT
name: Stapler entitlement
scope: { place: "*", org_unit: "*" }          # company-wide; a branch can override
applies_to: { service: supplies, item: stapler }
condition:
  entitlement: { key: stapler, per: person, period: calendar_year }
  exceeds: 2
effect: REQUIRE_APPROVAL
approval_chain: SUPPLIES-EXCEPTION
message: "{requester} has already received {used} staplers this year (limit {limit})."
priority: 100
version: 2026.3
active_from: 2026-04-01
```

### Condition types (covers every case we know of)

| Type | Example |
|---|---|
| Entitlement / quota | 2 staplers per person per year; 1 laptop per 3 years; 4 guest-house nights per quarter |
| Amount threshold | catering above ₹5,000; any spend above the team's limit |
| Budget | category spend would exceed the cost centre's monthly budget |
| Grade / role | economy flights below L5, business class from L7; hotel cap by grade |
| Service type | access cards, visas, flights always need approval |
| Time / calendar | access after hours, weekends, holidays at that branch |
| Place | Delhi branch needs security sign-off for visitors |
| Content / risk | mentions salary, legal notice, CCTV footage, server room |
| Frequency | more than 3 room bookings a day by one person |
| Vendor / contract | non-contract vendor, price above contract rate |
| Confidence | AI unsure what is being asked |

### Effects

- `ALLOW` — go ahead.
- `REQUIRE_APPROVAL` — run the named approval chain first.
- `BLOCK` — refuse with a reason (e.g. item discontinued) and offer the alternative if configured.
- `ASK` — ask the requester for a specific missing fact before deciding (e.g. "for which Delhi branch?").
- `ROUTE` — send to a particular team (e.g. VIP visitor → front desk manager).
- `SET` — set a field (e.g. travel class = economy for grade < L5).

### Precedence

1. Most specific scope wins (desk/room > floor > building > branch > city > region > company).
2. Then `priority` (higher first).
3. `BLOCK` beats `REQUIRE_APPROVAL` beats `ALLOW` when two rules of equal weight conflict.
4. Approved **exceptions** (a one-off waiver with expiry) are checked before rules.

## 4. Approval chains and authority

Approvers are **roles resolved at decision time**, never hard-coded people. That way the system keeps working when
staff change.

```yaml
code: TRAVEL-STANDARD
steps:
  - { role: MANAGER_OF_REQUESTER, due_hours: 8 }
  - { role: BRANCH_ADMIN, of: case_place, when: "amount > 25000", due_hours: 8 }
  - { role: FINANCE, when: "amount > 100000", due_hours: 24 }
mode: sequential          # or parallel, or any_one_of
on_timeout: escalate      # escalate | auto_reject | remind_only
escalate_to: NEXT_LEVEL_IN_SCOPE
```

Resolution:
- `MANAGER_OF_REQUESTER` → `Person.manager_id`.
- `BRANCH_ADMIN of case_place` → RoleAssignment with that role whose scope contains the case's place (walk up the tree).
- If nobody holds the role → next level up → central admin. Never silently skip a required approval.
- Delegation: a time-bound RoleAssignment (on leave → deputy) is honoured automatically.
- Self-approval is not allowed: if the resolved approver is the requester, go one level up.

Approval channels stay as they are today: reply "approve"/"reject" by email, the dashboard, or a signed one-click link.
All three call the same engine method.

## 5. Entitlement ledger

Every fulfilled countable thing writes a ledger row (person, key, quantity/amount, period, case). Rules read sums.

- Written when the team marks the job **done** (not when requested), so cancelled requests don't count.
- Reversals (returns, cancellations after fulfilment) write a negative row.
- Works for items, money (catering per event, monthly travel spend) and bookings (guest-house nights).
- Admin can see and correct the ledger; corrections are audited.

## 6. Where the AI fits

1. AI reads the mail and proposes: service type, details (item: stapler, qty: 1), place, urgency, risk flags.
2. The context engine validates and fills from master data (requester's grade, branch, travel override).
3. **Policy engine decides.** The AI does not decide approvals or limits.
4. AI writes the message to the requester using the engine's reasons ("you've already received 2 staplers this year,
   so I've asked the admin to approve a third").
5. The admin's approval mail shows the engine's reasons and evidence.

## 7. Today's rules, carried over as the default policy pack

Every rule currently hard-coded in `backend/app/agent/playbooks.py` (`assess_risk`) and `services/admin_ops.py`
becomes a row in a default pack that ships with the product:

| Today (code) | Default rule |
|---|---|
| `sensitive=True` service types (access card, security, offboarding, purchase, vendor, HR query, payment, reimbursement) | `REQUIRE_APPROVAL`, chain `ADMIN-STANDARD` |
| No team handles the service | `REQUIRE_APPROVAL` by central admin |
| Non-returnable material gate pass | `REQUIRE_APPROVAL` |
| Sensitive words (salary, legal notice, CCTV footage, server room …) | `REQUIRE_APPROVAL` |
| After-hours / weekend / holiday access | `REQUIRE_APPROVAL` (uses the branch's working hours and holiday calendar instead of word matching) |
| Flight / train / hotel / visa booking | `REQUIRE_APPROVAL`, chain `TRAVEL-STANDARD` |
| Amount above team limit or service auto-limit (supplies ₹5,000, catering ₹5,000, printing ₹3,000) | `REQUIRE_APPROVAL` |
| Catering with no amount | `REQUIRE_APPROVAL` (cost sign-off) |
| AI confidence below 0.45 | `ASK` (clarify) or `REQUIRE_APPROVAL` |
| Meeting-room catering / external visitors / off-site (meeting policy) | rules in the same engine, not a separate policy file |

Plus new defaults that make sense for most companies (all editable): stationery entitlements, laptop refresh cycle,
travel class by grade, guest-house night cap, visitor rules.

## 8. Admin experience (Setup → Policies)

- A list of rules grouped by module, each in plain English: *"Staplers: 2 per employee per year. More needs Branch
  Admin approval."*
- Edit with simple forms (no YAML for customers): pick service, condition type, number, period, effect, chain.
- **Test a rule** box: "If Rohan (L3, Pune) asks for a stapler today, what happens?" → shows the decision.
- Versioning: edits create a new version with an effective date; old cases keep the version they were decided under.
- AI-suggested rules (blueprint "learning engine") arrive as drafts that an admin must approve before activation.

## 9. Audit

Each decision stores: inputs snapshot, policy version, matched rules, outcome, chain, resolved approvers. Each
approval stores who decided, when, through which channel and any reason. Nothing about a rule or decision changes
silently.

## 10. Acceptance tests (when built)

- Same input + same policy version → identical decision.
- Branch rule overrides company rule; desk rule overrides branch rule.
- Third stapler in a year → approval with the two earlier cases listed as evidence.
- Grade L3 flight → economy set automatically; L7 → business allowed.
- Approver on leave → deputy gets it; requester never approves their own case.
- Rule edited mid-year → earlier cases still show the old version.
- AI marks a request "not sensitive" but a rule says approval → approval still required.
