# 00 — Decisions while there is no customer

There is no customer yet, so these are defaults chosen to keep the product sellable to as many companies as possible.
Each one can be revisited; the reason is written down so it's clear what would change it.

## D1. Evolve the current system, don't rebuild

The email intake, AI understanding, case threads, evidence-based closure, SLA reminders and audit trail work and are
tested against real mail (275 tests). We extract them into shared engines step by step instead of starting over.

*Would change if:* the gap map (doc 03) showed most of the code had to be replaced anyway. It doesn't.

## D2. Hosted multi-tenant SaaS first

One deployment serves many companies, each strictly isolated (tenant on every row, enforced in the API and later by
PostgreSQL Row-Level Security). A dedicated deployment per customer stays possible because nothing depends on sharing.

*Would change if:* the first serious buyer is a bank that requires on-premise. The design keeps that door open.

## D3. Nothing company-specific in code

Branches, teams, request types, rules, approvers, limits, workflows, evidence and wording are data, configured per
company. Test for every feature: *could a new company set this up without a developer?*

## D4. First target market: multi-branch Indian corporate offices

500–5,000 employees, several branches, a real admin team and many vendors (IT services, BFSI back offices,
consulting, pharma head offices). Standard needs, so one product fits most of them. Factories, hospitals and colleges
come later as "industry packs" (blueprint phase 7).

## D5. V1 channels: email + web dashboard

Email already works and every company has it. WhatsApp and Teams come in a later phase (they need Meta approval and
cost per message). The design keeps channels behind one adapter so adding them doesn't touch the engines.

## D6. Data in through one standard import layer

No named HR/ERP connectors until a customer needs one. Three entry points feeding the same canonical tables:

1. Spreadsheet upload (works for every company on day one).
2. A documented REST API in our canonical format.
3. Named connectors (Keka, Darwinbox, Zoho People, SAP, Tally, Entra ID / Google Workspace) later — each is a thin
   translator into the canonical format.

## D7. The AI is never the system of record

AI interprets mail, extracts details, drafts messages and proposes plans. Rules, limits, approvals, balances, stock,
spend and case state live in the database and are decided by deterministic engines. Management answers come from
fixed, safe queries — the AI never writes database queries.

## D8. Any number of branches

A company can have 1 branch or 500. Nothing in the design may assume a fixed number of branches, cities, buildings or
admins:

- Places form a tree of any depth (region → city → branch → building → floor → room/desk); a company uses only the
  levels it needs.
- Every team, admin role, rule, SLA calendar and knowledge entry is attached to a place and applies to everything
  below it, so one setting can cover one desk or the whole company.
- If no team or admin exists at a branch, work falls back up the tree (building → branch → city → region → central),
  so a new branch works the moment it is added.
- Lists, dashboards and reports are filtered by place and paged; nothing loads "all branches" at once.

Pricing is out of scope for now.

## Open questions for the founder

- Is the first target market (D4) right, or is there a particular industry to start with?
- Should the compliance calendar be in V1? It is in the V1 plan (doc 04) because it is cheap and sells well in India.
