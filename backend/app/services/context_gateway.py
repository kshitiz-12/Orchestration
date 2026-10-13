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

    def merge(self, *bundles: ContextBundle) -> ContextBundle:
        out = ContextBundle()
        for b in bundles:
            out.facts.extend(b.facts)
            out.unavailable.extend(b.unavailable)
        return out
