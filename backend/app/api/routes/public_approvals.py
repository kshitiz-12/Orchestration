"""One-click approve / reject from the approval mail. The HMAC signature in the link is the auth.

GET only shows a confirmation page (mail scanners prefetch links); the decision is applied on POST.
"""

from __future__ import annotations

import html
from typing import Optional

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse

from app.api.deps import SessionDep
from app.models.outcome import Approval, Outcome
from app.services.approval_actions import apply_decision, approval_pretty
from app.services.approval_links import verify
from app.services.site_services import cost_plan_text

router = APIRouter(prefix="/public/approvals", tags=["public"])

_STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f5f6f8;margin:0;padding:32px;color:#1c2330}
.card{max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,.06)}
h1{font-size:20px;margin:0 0 12px} pre{white-space:pre-wrap;background:#f7f8fa;border-radius:8px;padding:12px;font-size:14px}
button{border:0;border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer;color:#fff}
.approve{background:#1f8f4e}.reject{background:#c0392b} textarea{width:100%;min-height:70px;margin:8px 0 14px;border-radius:8px;border:1px solid #d5d9e0;padding:8px}
.muted{color:#6b7385;font-size:13px}
"""


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head><body><div class='card'>{body}</div></body></html>",
        status_code=status,
    )


def _load(session, approval_id: str, decision: str, exp: int, sig: str) -> tuple[Optional[Approval], Optional[HTMLResponse]]:
    if not verify(approval_id, decision, exp, sig):
        return None, _page("Link not valid", "<h1>This link is not valid or has expired</h1>"
                           "<p>Reply to the approval mail with \"approve\" or \"reject\" instead.</p>", 403)
    approval = session.get(Approval, approval_id)
    if approval is None:
        return None, _page("Not found", "<h1>Approval not found</h1>", 404)
    if approval.decision != "PENDING":
        return None, _page(
            "Already decided",
            f"<h1>Already {html.escape(approval.decision.lower())}</h1><p class='muted'>Nothing was changed.</p>",
        )
    return approval, None


@router.get("/{approval_id}/{decision}", response_class=HTMLResponse)
def confirm_page(approval_id: str, decision: str, session: SessionDep, exp: int = Query(0), sig: str = Query("")):
    approval, error = _load(session, approval_id, decision, exp, sig)
    if error:
        return error
    outcome = session.get(Outcome, approval.outcome_id) if approval.outcome_id else None
    facts = dict(outcome.facts or {}) if outcome else {}
    plan = (approval.payload or {}).get("cost_plan") or facts.get("cost_plan")
    detail = cost_plan_text(plan) if plan else ""
    what = html.escape(approval_pretty(approval.approval_type, facts))
    case = html.escape(outcome.case_reference if outcome else "")
    summary = html.escape((outcome.summary or "") if outcome else "")
    action = f"?exp={exp}&sig={html.escape(sig)}"
    if decision == "approve":
        form = (f"<form method='post' action='{action}'><button class='approve' type='submit'>Approve</button></form>")
    else:
        form = (f"<form method='post' action='{action}'><label>Reason (optional)</label>"
                "<textarea name='reason'></textarea><button class='reject' type='submit'>Reject</button></form>")
    body = (
        f"<h1>{'Approve' if decision == 'approve' else 'Reject'}: {what}</h1>"
        f"<p><b>{case}</b> {summary}</p>"
        + (f"<pre>{html.escape(detail)}</pre>" if detail else "")
        + form
        + "<p class='muted'>Only the chargeable part needs approval; the no-cost services go ahead either way.</p>"
    )
    return _page("Approval", body)


@router.post("/{approval_id}/{decision}", response_class=HTMLResponse)
def apply_link_decision(
    approval_id: str,
    decision: str,
    session: SessionDep,
    exp: int = Query(0),
    sig: str = Query(""),
    reason: str = Form(""),
):
    approval, error = _load(session, approval_id, decision, exp, sig)
    if error:
        return error
    approved = decision == "approve"
    apply_decision(
        session,
        approval.tenant_id,
        approval,
        approved=approved,
        actor="approver:signed_link",
        note=(reason or "").strip()[:500],
        via="signed_link",
    )
    session.commit()
    return _page(
        "Done",
        f"<h1>{'Approved' if approved else 'Rejected'} — thank you</h1>"
        "<p>The requester and the admin team have been updated.</p>",
    )
