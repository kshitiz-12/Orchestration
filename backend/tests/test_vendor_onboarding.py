"""Six-step vendor onboarding shared by company console and invite link."""

from sqlmodel import Session, select

from app.models.org import Tenant, Vendor
from app.services import vendor_lifecycle as vl


def _tid(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def test_company_and_vendor_onboarding_round_trip(session: Session):
    tid = _tid(session)
    vendor = vl.invite_vendor(
        session,
        tid,
        name="ABC Facilities Services Pvt. Ltd.",
        contact_email="abc.vendor@example.com",
        category="Facilities Management",
        contact_name="Ravi Kumar",
        service_areas=["Delhi", "Gurgaon"],
    )
    session.commit()

    company = vl.get_onboarding(session, tid, vendor.vendor_id)
    assert company["mode"] == "company"
    assert company["draft"]["current_step"] == 1
    assert company["draft"]["basic"]["legal_entity_name"]

    saved = vl.save_onboarding(
        session,
        tid,
        vendor.vendor_id,
        draft_patch={
            "current_step": 6,
            "basic": {
                "legal_entity_name": "ABC Facilities Services Pvt. Ltd.",
                "pan": "ABCDE1234F",
                "gstin": "07ABCDE1234F1Z5",
                "vendor_type": "Facilities Management",
            },
            "business": {
                "service_categories": ["HVAC / Air Conditioning"],
                "cities": ["Delhi", "Gurgaon"],
            },
            "compliance": {
                "documents": [{"type": "PAN Card", "status": "Valid"}],
            },
            "bank": {
                "beneficiary_name": "ABC Facilities Services Pvt. Ltd.",
                "account_number": "1234567890",
                "ifsc": "HDFC0001234",
                "bank_name": "HDFC Bank",
            },
            "review": {"truthful_declaration": True, "policy_declaration": True},
        },
        actor_email="admin@example.com",
    )
    assert saved["readiness"]["ready"] is True
    session.commit()

    public = vl.get_onboarding_by_token(session, vendor.invite_token or "")
    assert public["mode"] == "vendor"
    assert public["draft"]["basic"]["pan"] == "ABCDE1234F"

    result = vl.submit_onboarding_by_token(session, vendor.invite_token or "")
    session.commit()
    assert result["status"] == "submitted"
    refreshed = session.get(Vendor, vendor.vendor_id)
    assert refreshed is not None
    assert refreshed.status == "UNDER_REVIEW"
    assert refreshed.registration_submitted_at is not None
    assert refreshed.onboarding["review"]["submitted"] is True
