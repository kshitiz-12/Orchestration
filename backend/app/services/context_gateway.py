"""Enterprise Context Gateway — authorised facts only for AI (V3 §9).

Every fact includes source system, record ID, freshness, version, permission scope,
and unavailable fields. AI must not invent missing masters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.org import Location, Person, ServiceCatalog, Vendor, utcnow


@dataclass
class ContextFact:
    key: str
    value: Any
    source_system: str
    record_id: Optional[str]
    freshness: str  # CURRENT | STALE | UNKNOWN
    version: Optional[str] = None
    permission_scope: str = "tenant"
    retrieved_at: str = field(default_factory=lambda: utcnow().isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source_system": self.source_system,
            "record_id": self.record_id,
            "freshness": self.freshness,
            "version": self.version,
            "permission_scope": self.permission_scope,
            "retrieved_at": self.retrieved_at,
        }


@dataclass
class ContextBundle:
    facts: list[ContextFact] = field(default_factory=list)
    unavailable: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "facts": [f.as_dict() for f in self.facts],
            "unavailable": self.unavailable,
        }


class ContextGateway:
    def __init__(self, session: Session, tenant_id: str, *, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def _mark_unavailable(self, bundle: ContextBundle, field: str, reason: str) -> None:
        bundle.unavailable.append({"field": field, "reason": reason})

    def for_requester(self, email: Optional[str]) -> ContextBundle:
        bundle = ContextBundle()
        if not email:
            self._mark_unavailable(bundle, "requester", "email_not_provided")
            return bundle
        person = self.session.exec(
            select(Person).where(Person.tenant_id == self.tenant_id, Person.email == email.strip().lower())
        ).first()
        if not person:
            self._mark_unavailable(bundle, "requester", "not_in_directory")
            return bundle
        bundle.facts.append(
            ContextFact(
                key="requester",
                value={
                    "person_id": person.person_id,
                    "email": person.email,
                    "name": person.name,
                    "role": person.role,
                    "department": person.department,
                    "site_id": person.site_id,
                    "entity_id": person.entity_id,
                    "is_active": person.is_active,
                },
                source_system="AdminServices.Person",
                record_id=person.person_id,
                freshness="CURRENT",
                permission_scope="tenant",
            )
        )
        return bundle

    def vendors_for_category(self, category: Optional[str], *, location_id: Optional[str] = None) -> ContextBundle:
        bundle = ContextBundle()
        if not category:
            self._mark_unavailable(bundle, "vendors", "category_not_provided")
            return bundle
        stmt = (
            select(Vendor)
            .where(Vendor.tenant_id == self.tenant_id)
            .where(Vendor.status == "ACTIVE")
        )
        if self.entity_id:
            # Entity-scoped vendors when tagged; untagged remain visible
            stmt = stmt.where((Vendor.entity_id == self.entity_id) | (Vendor.entity_id == None))  # noqa: E711
        rows = self.session.exec(stmt).all()
        matched = []
        for v in rows:
            cats = {str(c).upper() for c in (v.approved_services or [])}
            cats.add((v.category or "").upper())
            if category.upper() not in cats and category.upper() not in (v.category or "").upper():
                # soft match on category string
                if category.lower() not in (v.category or "").lower():
                    continue
            if location_id and v.coverage_location_ids and location_id not in (v.coverage_location_ids or []):
                continue
            matched.append(
                {
                    "vendor_id": v.vendor_id,
                    "name": v.name,
                    "category": v.category,
                    "score": v.score,
                    "vendor_tier": v.vendor_tier,
                    "contact_email": v.contact_email,
                }
            )
        if not matched:
            self._mark_unavailable(bundle, "vendors", "no_active_vendor_for_category")
            return bundle
        bundle.facts.append(
            ContextFact(
                key="active_vendors",
                value=matched,
                source_system="AdminServices.Vendor",
                record_id=None,
                freshness="CURRENT",
                permission_scope="tenant",
            )
        )
        return bundle

    def location_by_id(self, location_id: Optional[str]) -> ContextBundle:
        bundle = ContextBundle()
        if not location_id:
            self._mark_unavailable(bundle, "location", "location_id_not_provided")
            return bundle
        loc = self.session.get(Location, location_id)
        if not loc or loc.tenant_id != self.tenant_id:
            self._mark_unavailable(bundle, "location", "not_found")
            return bundle
        bundle.facts.append(
            ContextFact(
                key="location",
                value={
                    "location_id": loc.location_id,
                    "type": loc.type,
                    "name": loc.name,
                    "code": loc.code,
                    "parent_id": loc.parent_id,
                    "site_id": loc.site_id,
                },
                source_system="AdminServices.Location",
                record_id=loc.location_id,
                freshness="CURRENT",
            )
        )
        return bundle

    def service_catalogue(self, category: Optional[str] = None) -> ContextBundle:
        bundle = ContextBundle()
        stmt = select(ServiceCatalog).where(ServiceCatalog.tenant_id == self.tenant_id)
        if category:
            stmt = stmt.where(ServiceCatalog.category == category)
        rows = self.session.exec(stmt).all()
        if not rows:
            self._mark_unavailable(bundle, "services", "none_configured")
            return bundle
        bundle.facts.append(
            ContextFact(
                key="services",
                value=[
                    {
                        "service_id": s.service_id,
                        "category": s.category,
                        "name": s.name,
                        "sla_hours": s.sla_hours,
                        "owner_role": s.owner_role,
                    }
                    for s in rows
                ],
                source_system="AdminServices.ServiceCatalog",
                record_id=None,
                freshness="CURRENT",
            )
        )
        return bundle

    def resolve_location(self, text: Optional[str] = None, *, location_id: Optional[str] = None) -> ContextBundle:
        """V3 tool: resolve_location — by id or fuzzy name/code/alias."""
        if location_id:
            return self.location_by_id(location_id)
        bundle = ContextBundle()
        needle = (text or "").strip().lower()
        if not needle:
            self._mark_unavailable(bundle, "location", "text_not_provided")
            return bundle
        rows = self.session.exec(select(Location).where(Location.tenant_id == self.tenant_id)).all()
        hit = None
        for loc in rows:
            blob = " ".join(
                x for x in [loc.name or "", loc.code or "", loc.alias or "", loc.type or ""] if x
            ).lower()
            if needle in blob or (loc.code and loc.code.lower() == needle):
                hit = loc
                break
        if not hit:
            self._mark_unavailable(bundle, "location", "unresolved")
            return bundle
        return self.location_by_id(hit.location_id)

    def get_site_services(self, site: Optional[str] = None, *, category: Optional[str] = None) -> ContextBundle:
        """V3 tool: get_site_services — SiteService catalogue for a site."""
        from app.models.company import SiteService

        bundle = ContextBundle()
        stmt = select(SiteService).where(SiteService.tenant_id == self.tenant_id, SiteService.is_active == True)  # noqa: E712
        if site:
            stmt = stmt.where(SiteService.site == site)
        rows = list(self.session.exec(stmt).all())
        if category:
            rows = [r for r in rows if category.lower() in (r.code or "").lower() or category.lower() in (r.name or "").lower()]
        if not rows:
            self._mark_unavailable(bundle, "site_services", "none_configured")
            return bundle
        bundle.facts.append(
            ContextFact(
                key="site_services",
                value=[
                    {
                        "service_id": r.service_id,
                        "code": r.code,
                        "name": r.name,
                        "site": r.site,
                        "delivery_model": r.delivery_model,
                        "rate": r.rate,
                        "sla_response_hours": r.sla_response_hours,
                        "sla_resolution_hours": r.sla_resolution_hours,
                        "chargeback_rule_code": r.chargeback_rule_code,
                    }
                    for r in rows
                ],
                source_system="AdminServices.SiteService",
                record_id=None,
                freshness="CURRENT",
            )
        )
        return bundle

    def check_amc(self, *, category: Optional[str] = None, asset_id: Optional[str] = None, location_id: Optional[str] = None) -> ContextBundle:
        """V3 tool: check_amc — AMC coverage before buy/dispatch."""
        from app.services.amc_gate import amc_coverage_hint

        bundle = ContextBundle()
        hint = amc_coverage_hint(
            self.session,
            self.tenant_id,
            category=category or "maintenance",
            asset_id=asset_id,
            location_id=location_id,
        )
        bundle.facts.append(
            ContextFact(
                key="amc_coverage",
                value=hint,
                source_system="AdminServices.AmcObligation",
                record_id=(hint.get("obligations") or [{}])[0].get("obligation_id") if hint.get("obligations") else None,
                freshness="CURRENT",
            )
        )
        if not hint.get("has_coverage"):
            self._mark_unavailable(bundle, "amc_vendor", hint.get("guidance") or "no_coverage")
        return bundle

    def get_budget(self, *, period: Optional[str] = None, category: str = "OPEX", cost_centre: Optional[str] = None) -> ContextBundle:
        """V3 tool: get_budget — operational budget availability (not ERP books)."""
        from datetime import date

        from app.engines.budget import BudgetEngine

        bundle = ContextBundle()
        period = period or date.today().isoformat()[:7]
        eng = BudgetEngine(self.session, self.tenant_id, entity_id=self.entity_id)
        check = eng.check(amount=0.0, period=period, category=category, cost_centre=cost_centre)
        if not check.budget_id:
            self._mark_unavailable(bundle, "budget", check.reason or "no_budget_row")
            return bundle
        from app.models.org import Budget

        row = self.session.get(Budget, check.budget_id)
        bundle.facts.append(
            ContextFact(
                key="budget",
                value={
                    "budget_id": check.budget_id,
                    "period": period,
                    "category": category,
                    "cost_centre": cost_centre,
                    "available": check.available,
                    "reserved": row.reserved_amount if row else None,
                    "committed": row.committed_amount if row else None,
                    "actual": row.actual_amount if row else None,
                    "accrued": getattr(row, "accrued_amount", 0) if row else None,
                },
                source_system="AdminServices.Budget",
                record_id=check.budget_id,
                freshness="CURRENT",
            )
        )
        return bundle

    def get_rate(self, *, vendor_id: Optional[str] = None, service_code: Optional[str] = None, category: Optional[str] = None) -> ContextBundle:
        """V3 tool: get_rate — contract / site service rate."""
        from app.models.company import SiteService
        from app.models.org import Contract

        bundle = ContextBundle()
        if vendor_id:
            contract = self.session.exec(
                select(Contract).where(
                    Contract.tenant_id == self.tenant_id,
                    Contract.vendor_id == vendor_id,
                    Contract.status == "ACTIVE",
                )
            ).first()
            if contract:
                bundle.facts.append(
                    ContextFact(
                        key="rate_card",
                        value={"contract_id": contract.contract_id, "rate_card": contract.rate_card, "vendor_id": vendor_id},
                        source_system="AdminServices.Contract",
                        record_id=contract.contract_id,
                        freshness="CURRENT",
                    )
                )
                return bundle
        if service_code:
            svc = self.session.exec(
                select(SiteService).where(
                    SiteService.tenant_id == self.tenant_id,
                    SiteService.code == service_code.strip().upper(),
                    SiteService.is_active == True,  # noqa: E712
                )
            ).first()
            if svc:
                bundle.facts.append(
                    ContextFact(
                        key="service_rate",
                        value={"code": svc.code, "rate": svc.rate, "currency": svc.currency, "unit": svc.unit},
                        source_system="AdminServices.SiteService",
                        record_id=svc.service_id,
                        freshness="CURRENT",
                    )
                )
                return bundle
        # Fall back to service catalogue
        cat = self.service_catalogue(category=category)
        if cat.facts:
            return cat
        self._mark_unavailable(bundle, "rate", "no_rate_found")
        return bundle

    def for_interpretation(
        self,
        *,
        requester_email: Optional[str] = None,
        category: Optional[str] = None,
        location_text: Optional[str] = None,
        location_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        period: Optional[str] = None,
    ) -> ContextBundle:
        """Compose authorised facts for AI — V3 §9 controlled tool calling bundle."""
        return self.merge(
            self.for_requester(requester_email),
            self.resolve_location(location_text, location_id=location_id),
            self.get_site_services(category=category),
            self.check_amc(category=category, asset_id=asset_id, location_id=location_id),
            self.get_budget(period=period, category="OPEX"),
            self.vendors_for_category(category, location_id=location_id),
            self.get_rate(category=category),
        )

    def merge(self, *bundles: ContextBundle) -> ContextBundle:
        out = ContextBundle()
        for b in bundles:
            out.facts.extend(b.facts)
            out.unavailable.extend(b.unavailable)
        return out
