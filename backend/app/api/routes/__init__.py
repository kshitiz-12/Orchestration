from fastapi import APIRouter

from app.api.routes import auth, intake, ops, outcomes, reviews

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(intake.router)
api_router.include_router(outcomes.router)
api_router.include_router(reviews.router)
api_router.include_router(ops.router)
