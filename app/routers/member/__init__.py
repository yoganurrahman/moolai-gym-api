from fastapi import APIRouter

router = APIRouter(prefix="/api/member")

from . import memberships, checkins, classes, pt, transactions, profile

router.include_router(memberships.router)
router.include_router(checkins.router)
router.include_router(classes.router)
router.include_router(pt.router)
router.include_router(transactions.router)
router.include_router(profile.router)
