from fastapi import APIRouter

router = APIRouter(prefix="/api/cms")

from . import (
    users, roles, permissions, packages, products,
    memberships, checkins, classes, trainers, pt,
    transactions, subscriptions, reports, branches, settings, promos
)

router.include_router(branches.router)
router.include_router(users.router)
router.include_router(roles.router)
router.include_router(permissions.router)
router.include_router(packages.router)
router.include_router(products.router)
router.include_router(memberships.router)
router.include_router(checkins.router)
router.include_router(classes.router)
router.include_router(trainers.router)
router.include_router(pt.router)
router.include_router(transactions.router)
router.include_router(subscriptions.router)
router.include_router(reports.router)
router.include_router(settings.router)
router.include_router(promos.router)
