from fastapi import APIRouter

from app.api.routes import auth, gmail, intake, ops, outcomes, outlook, reviews, webhooks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(intake.router)
api_router.include_router(outcomes.router)
api_router.include_router(reviews.router)
api_router.include_router(ops.router)
api_router.include_router(gmail.router)
api_router.include_router(outlook.router)
api_router.include_router(webhooks.router)
