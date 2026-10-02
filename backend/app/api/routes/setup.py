"""Company setup from the dashboard: department mailboxes, office knowledge and bulk data import.

The main admin mailbox stays in env (ADMIN_OPS_EMAIL); everything else lives here.
"""

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlmodel import func, select

from app.agent.company_seed import is_placeholder
from app.agent.importer import TEMPLATES, read_rows, run_import, template_csv
from app.api.deps import SessionDep, TenantDep, UserDep
from app.models.company import CostCentre, Department, KnowledgeEntry, ServiceTicket, SiteService, VisitorPass
from app.models.org import Person, Resource, Vendor, utcnow

router = APIRouter(prefix="/setup", tags=["setup"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class DepartmentIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    categories: Optional[list[str]] = None
    primary_email: Optional[str] = None
    backup_emails: Optional[list[str]] = None
    approver_email: Optional[str] = None
    sla_hours: Optional[int] = None
    spend_approval_limit: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    handover_info: Optional[str] = None


class KnowledgeIn(BaseModel):
    key: str
    title: str
    content: str
    section: str = "faq"
    is_active: bool = True


def _clean_email(value: Optional[str]) -> Optional[str]:
    v = (value or "").strip().lower()
    if not v:
        return None
    if "@" not in v or " " in v:
        raise HTTPException(status_code=422, detail=f"Invalid email: {value}")
    return v


def _dept_out(d: Department) -> dict:
    emails = [d.primary_email, *(d.backup_emails or [])]
    real = [e for e in emails if e and not is_placeholder(e)]
    return {
        "department_id": d.department_id,
        "code": d.code,
        "name": d.name,
        "categories": d.categories or [],
        "primary_email": d.primary_email,
        "backup_emails": d.backup_emails or [],
        "approver_email": d.approver_email,
        "sla_hours": d.sla_hours,
        "spend_approval_limit": d.spend_approval_limit,
        "is_active": d.is_active,
        "notes": d.notes,
        "handover_info": d.handover_info,
        "needs_setup": not real,
    }


@router.get("/status")
def setup_status(session: SessionDep, tenant_id: TenantDep, _: UserDep):
    from app.services.admin_ops import admin_ops_email

    depts = session.exec(select(Department).where(Department.tenant_id == tenant_id)).all()
    active = [d for d in depts if d.is_active]
    pending = [d.code for d in active if _dept_out(d)["needs_setup"]]

    def count(model, *where):
        return session.exec(select(func.count()).select_from(model).where(*where)).one()

    return {
        "admin_email": admin_ops_email(),
        "admin_email_source": "env (ADMIN_OPS_EMAIL)",
        "departments": len(active),
        "departments_needing_setup": pending,
        "employees": count(Person, Person.tenant_id == tenant_id),
        "resources": count(Resource, Resource.tenant_id == tenant_id),
        "vendors": count(Vendor, Vendor.tenant_id == tenant_id),
        "knowledge_entries": count(KnowledgeEntry, KnowledgeEntry.tenant_id == tenant_id),
        "open_tickets": count(
            ServiceTicket,
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.notin_(["RESOLVED", "CLOSED", "CANCELLED", "REJECTED"]),
        ),
    }


@router.get("/departments")
def list_departments(session: SessionDep, tenant_id: TenantDep, _: UserDep):
    rows = session.exec(select(Department).where(Department.tenant_id == tenant_id).order_by(Department.code)).all()
    return [_dept_out(d) for d in rows]


@router.post("/departments")
def create_department(body: DepartmentIn, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    code = (body.code or "").strip().upper().replace(" ", "_")
    if not code or not (body.name or "").strip():
        raise HTTPException(status_code=422, detail="code and name are required")
    exists = session.exec(select(Department).where(Department.tenant_id == tenant_id, Department.code == code)).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"Department {code} already exists")
    dept = Department(tenant_id=tenant_id, code=code, name=body.name.strip())
    _apply(dept, body)
    session.add(dept)
    session.commit()
    session.refresh(dept)
    return _dept_out(dept)


@router.patch("/departments/{department_id}")
def update_department(department_id: str, body: DepartmentIn, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    dept = session.get(Department, department_id)
    if not dept or dept.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Department not found")
    if body.name is not None and body.name.strip():
        dept.name = body.name.strip()
    _apply(dept, body)
    dept.updated_at = utcnow()
    session.add(dept)
    session.commit()
    session.refresh(dept)
    return _dept_out(dept)


@router.delete("/departments/{department_id}")
def deactivate_department(department_id: str, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    dept = session.get(Department, department_id)
    if not dept or dept.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Department not found")
    if dept.code == "ADMIN":
        raise HTTPException(status_code=400, detail="The ADMIN department is the fallback and can't be removed")
    dept.is_active = False
    session.add(dept)
    session.commit()
    return {"ok": True}


def _apply(dept: Department, body: DepartmentIn) -> None:
    if body.categories is not None:
        dept.categories = [c.strip().lower().replace(" ", "_") for c in body.categories if c.strip()]
    if body.primary_email is not None:
        dept.primary_email = _clean_email(body.primary_email)
    if body.backup_emails is not None:
        dept.backup_emails = [e for e in (_clean_email(x) for x in body.backup_emails) if e]
    if body.approver_email is not None:
        dept.approver_email = _clean_email(body.approver_email)
    if body.sla_hours is not None:
        dept.sla_hours = max(1, body.sla_hours)
    if body.spend_approval_limit is not None:
        dept.spend_approval_limit = max(0.0, body.spend_approval_limit)
    if body.is_active is not None:
        dept.is_active = body.is_active
    if body.notes is not None:
        dept.notes = body.notes
    if body.handover_info is not None:
        dept.handover_info = body.handover_info.strip() or None


@router.get("/knowledge")
def list_knowledge(session: SessionDep, tenant_id: TenantDep, _: UserDep):
    rows = session.exec(
        select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id).order_by(KnowledgeEntry.section, KnowledgeEntry.key)
    ).all()
    return [
        {"entry_id": r.entry_id, "key": r.key, "section": r.section, "title": r.title, "content": r.content, "is_active": r.is_active}
        for r in rows
    ]


@router.put("/knowledge")
def upsert_knowledge(body: KnowledgeIn, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    key = body.key.strip().lower().replace(" ", "_")
    if not key or not body.content.strip():
        raise HTTPException(status_code=422, detail="key and content are required")
    entry = session.exec(select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id, KnowledgeEntry.key == key)).first()
    entry = entry or KnowledgeEntry(tenant_id=tenant_id, key=key, title=body.title, content=body.content)
    entry.title = body.title.strip() or key
    entry.content = body.content.strip()
    entry.section = body.section.strip() or "faq"
    entry.is_active = body.is_active
    entry.updated_at = utcnow()
    session.add(entry)
    session.commit()
    return {"ok": True, "key": key}


@router.delete("/knowledge/{entry_id}")
def delete_knowledge(entry_id: str, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    entry = session.get(KnowledgeEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    session.delete(entry)
    session.commit()
    return {"ok": True}


DELIVERY_MODELS = {"INCLUDED", "CONTRACT", "SUBSIDISED", "CHARGEABLE", "OUTSOURCED"}


class SiteServiceIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    site: Optional[str] = None
    delivery_model: Optional[str] = None
    provider: Optional[str] = None
    owner_department: Optional[str] = None
    unit: Optional[str] = None
    rate: Optional[float] = None
    included_limit: Optional[float] = None
    premium_triggers: Optional[list[str]] = None
    premium_rate: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class CostCentreIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None
    approver_name: Optional[str] = None
    approver_email: Optional[str] = None
    is_active: Optional[bool] = None


def _service_out(s: SiteService) -> dict:
    return {
        k: getattr(s, k)
        for k in ("service_id", "site", "code", "name", "delivery_model", "provider", "owner_department", "unit",
                  "rate", "currency", "included_limit", "premium_triggers", "premium_rate", "is_active", "notes")
    }


@router.get("/site-services")
def list_site_services(session: SessionDep, tenant_id: TenantDep, _: UserDep):
    from app.services.site_services import ensure_site_services

    ensure_site_services(session, tenant_id)
    session.commit()
    rows = session.exec(
        select(SiteService).where(SiteService.tenant_id == tenant_id).order_by(SiteService.owner_department, SiteService.code)
    ).all()
    return [_service_out(s) for s in rows]


@router.put("/site-services")
def upsert_site_service(body: SiteServiceIn, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    code = (body.code or "").strip().lower().replace(" ", "_")
    if not code:
        raise HTTPException(status_code=422, detail="code is required")
    site = (body.site or "Corporate Office").strip()
    row = session.exec(
        select(SiteService).where(SiteService.tenant_id == tenant_id, SiteService.site == site, SiteService.code == code)
    ).first()
    if row is None:
        if not (body.name or "").strip():
            raise HTTPException(status_code=422, detail="name is required for a new service")
        row = SiteService(tenant_id=tenant_id, site=site, code=code, name=body.name.strip())
    if body.delivery_model is not None:
        model = body.delivery_model.strip().upper()
        if model not in DELIVERY_MODELS:
            raise HTTPException(status_code=422, detail=f"delivery_model must be one of {', '.join(sorted(DELIVERY_MODELS))}")
        row.delivery_model = model
    if body.name is not None and body.name.strip():
        row.name = body.name.strip()
    if body.unit is not None and body.unit.strip():
        row.unit = body.unit.strip()
    if body.provider is not None:
        row.provider = body.provider.strip() or None
    if body.notes is not None:
        row.notes = body.notes.strip() or None
    if body.owner_department is not None:
        row.owner_department = body.owner_department.strip().upper() or "ADMIN"
    for field in ("rate", "included_limit", "premium_rate"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, max(0.0, float(value)))
    if body.premium_triggers is not None:
        row.premium_triggers = [t.strip().lower() for t in body.premium_triggers if t.strip()]
    if body.is_active is not None:
        row.is_active = body.is_active
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _service_out(row)


@router.get("/cost-centres")
def list_cost_centres(session: SessionDep, tenant_id: TenantDep, _: UserDep):
    from app.services.site_services import ensure_site_services

    ensure_site_services(session, tenant_id)
    session.commit()
    rows = session.exec(select(CostCentre).where(CostCentre.tenant_id == tenant_id).order_by(CostCentre.code)).all()
    return [
        {
            "cost_centre_id": c.cost_centre_id, "code": c.code, "name": c.name, "department": c.department,
            "approver_name": c.approver_name, "approver_email": c.approver_email, "is_active": c.is_active,
            "needs_setup": not c.approver_email or is_placeholder(c.approver_email),
        }
        for c in rows
    ]


@router.put("/cost-centres")
def upsert_cost_centre(body: CostCentreIn, session: SessionDep, tenant_id: TenantDep, _: UserDep):
    code = (body.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=422, detail="code is required")
    row = session.exec(select(CostCentre).where(CostCentre.tenant_id == tenant_id, CostCentre.code == code)).first()
    if row is None:
        if not (body.name or "").strip():
            raise HTTPException(status_code=422, detail="name is required for a new cost centre")
        row = CostCentre(tenant_id=tenant_id, code=code, name=body.name.strip())
    if body.name is not None and body.name.strip():
        row.name = body.name.strip()
    if body.department is not None:
        row.department = body.department.strip() or None
    if body.approver_name is not None:
        row.approver_name = body.approver_name.strip() or None
    if body.approver_email is not None:
        row.approver_email = _clean_email(body.approver_email)
    if body.is_active is not None:
        row.is_active = body.is_active
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"ok": True, "code": row.code}


@router.get("/templates/{kind}", response_class=PlainTextResponse)
def download_template(kind: str, _: UserDep):
    if kind not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown type. Use one of: {', '.join(TEMPLATES)}")
    return PlainTextResponse(
        template_csv(kind),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{kind}_template.csv"'},
    )


@router.post("/import/{kind}")
async def import_data(
    kind: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: UserDep,
    file: UploadFile = File(...),
    commit: bool = Query(False, description="False = preview only, True = save"),
):
    if kind not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown type. Use one of: {', '.join(TEMPLATES)}")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    try:
        rows = read_rows(file.filename or "", content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read the file: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=422, detail="The file has no data rows")
    return run_import(session, tenant_id, kind, rows, commit=commit)


@router.get("/tickets")
def list_tickets(session: SessionDep, tenant_id: TenantDep, _: UserDep, limit: int = 100):
    rows = session.exec(
        select(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id).order_by(ServiceTicket.created_at.desc()).limit(limit)
    ).all()
    return [r.model_dump() for r in rows]


@router.get("/visitors")
def list_visitors(session: SessionDep, tenant_id: TenantDep, _: UserDep, limit: int = 100):
    rows = session.exec(
        select(VisitorPass).where(VisitorPass.tenant_id == tenant_id).order_by(VisitorPass.created_at.desc()).limit(limit)
    ).all()
    return [r.model_dump() for r in rows]
