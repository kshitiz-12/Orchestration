# 04 — V1 roadmap

Goal of V1: a product we can install for a **new company in under a week, without code changes**, that handles the
everyday admin work of a multi-branch office over email + web.

Durations assume the current team pace and are rough; each phase ends with something demo-able.

## Phase 0 — Freeze & foundation (1–2 weeks)

- Push the current fixes; tag the working version as the "single-company baseline".
- Proper migrations (Alembic) instead of `ALTER` statements in `core/database.py`.
- Turn today's live scenarios into a fixed regression mail set (no live sending).
- **Done when:** baseline tagged, migrations run on a fresh DB, all tests pass.

## Phase 1 — Multi-tenant core (3–4 weeks)

- `tenant_id` resolved from the logged-in user / inbound address, not "first tenant".
- Postgres Row-Level Security on every tenant table; email unique per tenant.
- Per-tenant inbound address (`<tenant>@in.adminservices.in`) and settings (name, signature, sender, time zone).
- Real users and roles (Central Admin, Branch Admin, Team Member, Approver, Employee); Google/Microsoft sign-in.
- **Done when:** two demo companies run side by side; an automated test proves neither can see the other's data
  through the API, the dashboard or email.

## Phase 2 — Company structure & onboarding (3–4 weeks)

- Place tree (region → city → branch → building → floor → room/desk) replacing Location/Resource.
- People import from spreadsheet (CSV/XLSX) through the canonical import API; validation report; re-import updates.
- Teams scoped to places with fallback up the tree; service-to-team routing per place.
- Travel overrides (person temporarily at another branch).
- Onboarding wizard: company → places → people → teams → services → go live.
- **Done when:** a new company with 10 branches and 1,000 people is set up from spreadsheets in one sitting, and a
  request from a Pune employee is routed to the Pune team automatically.

## Phase 3 — Services & policy engine (4–5 weeks)

- ServiceType in the database (replaces `playbooks.py`), with a default catalogue of ~40 admin services.
- Policy engine (doc 02): rules, approval chains by role, entitlement ledger, budgets, exceptions, versioning.
- Replace the three approval paths and the hard-coded risk rules with the engine + default policy pack.
- Policy editor in Setup with "test a rule".
- **Done when:** stapler limit, travel class by grade, catering amount limit and after-hours access all work from
  rules the admin edited in the UI, and every approval shows its reasons.

## Phase 4 — SLA, evidence, reporting (2–3 weeks)

- One SLA engine (targets per service type and place; branch working hours and holidays; escalation through roles).
- Evidence required per service type before verified closure (already partly done — moves to data).
- Reports: volume, SLA met, ageing, cost by branch/cost centre, team performance; CSV export.
- Daily/weekly digest per role.
- **Done when:** a branch admin gets an escalation only for their branch, and a central admin sees an SLA report
  across all branches.

## Phase 5 — Employee portal & rooms (3 weeks)

- Simple web portal: raise a request, see status, reply, rate.
- Meeting rooms folded into the same case path (rooms are places; booking is a service type; meeting policy is rules).
- Remove the old meeting engine once parity tests pass.
- **Done when:** the same request works by email or portal with identical results.

## Phase 6 — Pilot readiness (2 weeks)

- Per-company usage counts (AI calls, cases, emails) for capacity monitoring.
- Backups, monitoring, error alerts, separate worker process.
- Security basics: encrypted mailbox tokens, audit export, data deletion on request (DPDP Act).
- Admin guide + onboarding checklist.
- **Done when:** a pilot company can be onboarded by someone other than the developers.

**V1 total: roughly 4–5 months.**

## After V1 (in blueprint order)

- WhatsApp / Teams channels.
- Named connectors: Darwinbox, Keka, Zoho People, SAP SuccessFactors (people); Tally, SAP, Zoho Books (finance).
- Vendor portal (vendors update jobs directly), purchase orders and invoice matching.
- Compliance calendar (licences, fire NOCs, AMCs, insurance renewals) with reminders and evidence.
- Asset lifecycle (issue, return, refresh, disposal), inventory and auto-reorder.
- Visitor management, transport rosters, guest house.
- Learning engine suggestions → draft rules for admin approval.

## Demo company (used for sales and tests)

**"Acme Financial Services"** — 1,200 employees, 3 regions, 8 cities, 12 branches (Mumbai HQ with 2 buildings,
Pune, Bengaluru ×2, Delhi, Gurugram, Noida, Chennai, Hyderabad, Kolkata, Ahmedabad), central admin team plus a branch
admin per branch, IT/HR/Facilities/Cafeteria teams with regional scope, 15 vendors with contracts.

## Demo scenarios (each must work end-to-end before a pilot)

1. **Routing by branch:** a Pune employee writes "AC not working on 3rd floor" → Pune facilities team gets the work
   order; Mumbai never sees it.
2. **Traveller:** a Delhi employee visiting Bengaluru for a week asks for a cab → Bengaluru transport team.
3. **Entitlement:** third stapler of the year → branch admin approval, with the two earlier deliveries shown.
4. **Grade policy:** L3 employee asks for a flight → economy set automatically, manager approves, travel desk books,
   reference returned to employee.
5. **Spend & budget:** ₹12,000 catering for a client visit → above limit → branch admin approves → cafeteria
   confirms → cost logged against the cost centre.
6. **Collection:** new laptop approved → IT says "collect from IT desk, 2nd floor, after 3pm" → employee told
   exactly that.
7. **One mail, two needs:** "need an access card and a parking slot" → two cases, two teams, separate threads,
   one combined reply to the employee.
8. **Escalation:** facilities ignores a job past SLA → reminder → branch admin → regional admin, each step logged.
9. **Sensitive:** request mentioning CCTV footage → approval required regardless of what the AI thinks.
10. **Isolation:** the same steps run for a second demo company; neither sees the other's data.

## V1 acceptance criteria

- A new company is live from spreadsheets and the wizard in ≤ 5 working days with no code change.
- Every approval and limit decision can be explained from stored rules and evidence.
- Branch admins see and act only on their branch; central admins see all.
- No case closes as verified without the evidence its service type requires.
- Tenant isolation test suite passes on every release.
- A company with 100+ branches works with the same setup steps as a company with one.
- All scenarios above pass in the regression set without live email.
