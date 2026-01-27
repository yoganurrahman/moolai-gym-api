from fastapi import APIRouter

router = APIRouter(prefix="/api/cms")

from . import users, roles, permissions

router.include_router(users.router)
router.include_router(roles.router)
router.include_router(permissions.router)
