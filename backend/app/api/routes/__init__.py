from fastapi import APIRouter

from app.api.routes import (
    admin_modules,
    amc_projects,
    assets,
    auth,
    budgets,
    control_tower,
    enterprise_v3,
    entities,
    facilities,
    fleet_travel,
    gmail,
    intake,
    learning,
    ops,
    outcomes,
    outlook,
    p2p,
    policies,
    public_approvals,
    public_vendors,
    reviews,
    setup,
    sourcing,
    vendors,
    webhooks,
    workplace,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(intake.router)
api_router.include_router(outcomes.router)
api_router.include_router(reviews.router)
api_router.include_router(ops.router)
api_router.include_router(entities.router)
api_router.include_router(budgets.router)
api_router.include_router(policies.router)
api_router.include_router(assets.router)
api_router.include_router(facilities.router)
api_router.include_router(admin_modules.router)
api_router.include_router(amc_projects.router)
api_router.include_router(p2p.router)
api_router.include_router(sourcing.router)
api_router.include_router(workplace.router)
api_router.include_router(fleet_travel.router)
api_router.include_router(control_tower.router)
api_router.include_router(enterprise_v3.router)
api_router.include_router(vendors.router)
api_router.include_router(gmail.router)
api_router.include_router(outlook.router)
api_router.include_router(webhooks.router)
api_router.include_router(setup.router)
api_router.include_router(learning.router)
api_router.include_router(public_approvals.router)
api_router.include_router(public_vendors.router)
