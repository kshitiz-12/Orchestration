# AdminServices Orchestra — platform planning

Planning documents for turning the current email desk into a configurable admin platform that can be sold to many
companies. They follow `AdminServices_Developer_Master_Blueprint_Orchestra_V1.docx` and are written against the code
as it exists today.

| # | Document | What it settles |
|---|---|---|
| 00 | [Decisions](00-decisions.md) | Product decisions taken while there is no customer yet, and why |
| 01 | [Data model](01-data-model.md) | The core entities every module shares, and how they map to today's tables |
| 02 | [Policy & approval engine](02-policy-and-approval-engine.md) | How company rules, limits and approvers are configured and evaluated |
| 03 | [Current code gap map](03-current-code-gap-map.md) | What to keep, extract into an engine, or replace |
| 04 | [V1 roadmap](04-v1-roadmap.md) | Build phases, V1 scope, demo company and acceptance criteria |

Status: draft for review.

Built so far:
- **Any number of branches (D8).** Places form a tree of any depth (`backend/app/agent/places.py`). Teams cover a place
  and everything below it (`Department.location_id`, blank = whole company). Each request is tied to a place: one named
  in the request first, else the requester's home branch, else one mentioned in the mail. It goes to the nearest team
  above that place, and falls back up the tree to the company-wide team. An `ADMIN_<branch>` team is that branch's
  admin and gets its unhandled work, approvals and alerts. Places, teams and employees can be imported with a branch
  column. The team list given to the AI stays the same size however many branches there are.
