from fastapi import APIRouter

router = APIRouter(prefix="/api/trainer")

from . import dashboard, pt, profile

router.include_router(dashboard.router)
router.include_router(pt.router)
router.include_router(profile.router)
