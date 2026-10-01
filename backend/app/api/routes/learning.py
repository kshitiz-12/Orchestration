"""AI learning & governance: accuracy, correction trends, suggested rules, knowledge drafts and the regression check."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.agent.ai_eval import prompt_version, run_eval
from app.agent.learning import accuracy_summary, apply_route_rule, automation_kpis, rule_suggestions
from app.api.deps import SessionDep, TenantDep, UserDep
from app.audit.service import AuditService
from app.models.company import KnowledgeEntry
from app.models.org import utcnow
from app.models.outcome import AuditLog

router = APIRouter(prefix="/learning", tags=["learning"])


class RouteRuleIn(BaseModel):
    category: str
    department: str


class KnowledgeApproveIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


def _last_eval(session, tenant_id: str) -> Optional[dict]:
    row = session.exec(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id, AuditLog.action == "AI_EVALUATION_RUN")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    return row.after if row else None


@router.get("/summary")
def learning_summary(session: SessionDep, tenant_id: TenantDep, _: UserDep):
    drafts = session.exec(
        select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id, KnowledgeEntry.section == "draft",
                                     KnowledgeEntry.is_active == False)  # noqa: E712
    ).all()
    return {
        "accuracy": accuracy_summary(session, tenant_id),
        "suggestions": rule_suggestions(session, tenant_id),
        "automation": automation_kpis(session, tenant_id),
        "knowledge_drafts": [
            {"entry_id": d.entry_id, "title": d.title, "content": d.content, "created_at": d.created_at} for d in drafts
        ],
        "last_eval": _last_eval(session, tenant_id),
        "prompt_version": prompt_version(),
    }


@router.post("/suggestions/apply")
def apply_suggestion(body: RouteRuleIn, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    try:
        result = apply_route_rule(session, tenant_id, body.category.strip().lower(), body.department.strip().upper(), user.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return {"ok": True, **result}


@router.post("/knowledge/{entry_id}/approve")
def approve_knowledge(entry_id: str, body: KnowledgeApproveIn, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    entry = session.get(KnowledgeEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    if body.title and body.title.strip():
        entry.title = body.title.strip()[:200]
    if body.content and body.content.strip():
        entry.content = body.content.strip()
    entry.section = "faq"
    entry.is_active = True
    entry.updated_at = utcnow()
    session.add(entry)
    AuditService(session).record(
        tenant_id=tenant_id, actor=user.email, action="KNOWLEDGE_APPROVED", entity_type="KnowledgeEntry",
        entity_id=entry.entry_id, after={"title": entry.title},
    )
    session.commit()
    return {"ok": True}


@router.post("/knowledge/{entry_id}/reject")
def reject_knowledge(entry_id: str, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    entry = session.get(KnowledgeEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    session.delete(entry)
    session.commit()
    return {"ok": True}


@router.post("/eval/run")
def run_evaluation(session: SessionDep, tenant_id: TenantDep, user: UserDep):
    from app.ai.service import LLMService

    result = run_eval(session, tenant_id, provider=LLMService().provider)
    stored = {**result, "failures": result["failures"][:30]}
    AuditService(session).record(
        tenant_id=tenant_id, actor=user.email, action="AI_EVALUATION_RUN", entity_type="AIEvaluation",
        entity_id=result["prompt_version"], after=stored,
    )
    session.commit()
    return result
