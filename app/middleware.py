import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

from app.db import get_db_connection

load_dotenv()

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", 24))
PIN_TOKEN_EXPIRE_HOURS = int(os.getenv("PIN_TOKEN_EXPIRE_HOURS", 1))

security = HTTPBearer()
pin_security = HTTPBearer(auto_error=False)


def get_user_permissions(user_id: int) -> List[str]:
    """
    Get REAL-TIME user permissions from database.

    Args:
        user_id: The user ID

    Returns:
        List of permission names for the user.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT p.name
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            JOIN users u ON u.role_id = rp.role_id
            WHERE u.id = %s
            """,
            (user_id,),
        )
        permissions = [row["name"] for row in cursor.fetchall()]
        return permissions
    except Exception as e:
        logger.error(f"Error getting permissions for user {user_id}: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Verify JWT Bearer token from Authorization header.
    Permissions are fetched REAL-TIME from database, not from token.

    Returns user context dict with: user_id, email, role_id, role_name, permission
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check token type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_TOKEN_TYPE",
                    "message": "Token tidak valid",
                },
            )

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "TOKEN_EXPIRED",
                    "message": "Sesi Anda telah habis. Silakan login kembali.",
                },
            )

        user_id = payload.get("user_id")
        token_version = payload.get("token_version")

        # Verify token_version against database (for multi-device logout)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT u.token_version, u.is_active, r.name as role_name
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            user = cursor.fetchone()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "USER_NOT_FOUND",
                        "message": "User tidak ditemukan",
                    },
                )

            if not user["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "USER_INACTIVE",
                        "message": "Akun Anda tidak aktif. Hubungi administrator.",
                    },
                )

            if user["token_version"] != token_version:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "TOKEN_REVOKED",
                        "message": "Sesi Anda telah berakhir. Silakan login kembali.",
                    },
                )

            # Get role_name from database (more accurate than token)
            role_name = user["role_name"] or payload.get("role_name", "member")

        finally:
            cursor.close()
            conn.close()

        # Get permissions REAL-TIME from database
        permissions = get_user_permissions(user_id)

        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role_id": payload.get("role_id"),
            "role_name": role_name,
            "permission": permissions,  # Real-time from database
            "token_version": payload.get("token_version"),
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "TOKEN_EXPIRED",
                "message": "Sesi Anda telah habis. Silakan login kembali.",
            },
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_TOKEN",
                "message": "Token tidak valid",
            },
        )


def create_access_token(data: dict, expires_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    """
    Create JWT access token with minimal user data.
    Permissions are NOT stored in token - they are checked real-time from database.

    Args:
        data: dict containing user_id, email, role_id, role_name, token_version
        expires_hours: token expiration time in hours (default 24)

    Returns:
        JWT token string
    """
    # Only include essential data in token (NOT permissions)
    to_encode = {
        "user_id": data.get("user_id"),
        "email": data.get("email"),
        "role_id": data.get("role_id"),
        "role_name": data.get("role_name"),
        "token_version": data.get("token_version"),
    }

    expire = datetime.utcnow() + timedelta(hours=expires_hours)
    to_encode.update({
        "exp": expire,
        "type": "access",
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_pin_token(user_id: int, pin_version: int, expires_hours: int = PIN_TOKEN_EXPIRE_HOURS) -> str:
    """
    Create JWT PIN token for sensitive operations (transactions).

    Args:
        user_id: User ID
        pin_version: PIN version for invalidation
        expires_hours: token expiration time in hours (default 1)

    Returns:
        JWT PIN token string
    """
    expire = datetime.utcnow() + timedelta(hours=expires_hours)
    to_encode = {
        "user_id": user_id,
        "pin_version": pin_version,
        "exp": expire,
        "type": "pin",
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_pin_token(
    credentials: HTTPAuthorizationCredentials = Depends(pin_security),
) -> dict:
    """
    Verify PIN token from X-Pin-Token header.
    Used for sensitive operations like transactions.

    Returns user context dict with: user_id, pin_version
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "PIN_TOKEN_REQUIRED",
                "message": "PIN token diperlukan untuk operasi ini. Silakan verifikasi PIN terlebih dahulu.",
            },
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check token type
        if payload.get("type") != "pin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_PIN_TOKEN",
                    "message": "PIN token tidak valid",
                },
            )

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "PIN_TOKEN_EXPIRED",
                    "message": "PIN token telah kadaluarsa. Silakan verifikasi PIN kembali.",
                },
            )

        user_id = payload.get("user_id")
        pin_version = payload.get("pin_version")

        # Verify pin_version against database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT pin_version, has_pin FROM users WHERE id = %s",
                (user_id,),
            )
            user = cursor.fetchone()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "USER_NOT_FOUND",
                        "message": "User tidak ditemukan",
                    },
                )

            if not user["has_pin"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "PIN_NOT_SET",
                        "message": "PIN belum diatur. Silakan atur PIN terlebih dahulu.",
                    },
                )

            if user["pin_version"] != pin_version:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "PIN_TOKEN_REVOKED",
                        "message": "PIN token tidak valid. Silakan verifikasi PIN kembali.",
                    },
                )

        finally:
            cursor.close()
            conn.close()

        return {
            "user_id": user_id,
            "pin_version": pin_version,
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "PIN_TOKEN_EXPIRED",
                "message": "PIN token telah kadaluarsa. Silakan verifikasi PIN kembali.",
            },
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid PIN token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_PIN_TOKEN",
                "message": "PIN token tidak valid",
            },
        )


def require_permission(permission_name: str):
    """
    Dependency to check if user has specific permission.
    Superadmin bypasses all permission checks.
    Permissions are checked REAL-TIME from database.

    Usage:
        @router.get("/")
        def list_items(
            auth: dict = Depends(verify_bearer_token),
            _: None = Depends(require_permission("item.view"))
        ):
    """
    def permission_checker(auth: dict = Depends(verify_bearer_token)) -> None:
        role_name = auth.get("role_name", "")

        # Superadmin bypass
        if role_name.lower() == "superadmin":
            return None

        # Check permission (already real-time from verify_bearer_token)
        user_permissions = auth.get("permission", [])
        if permission_name in user_permissions:
            return None

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PERMISSION_DENIED",
                "message": f"Anda tidak memiliki akses untuk operasi ini",
            },
        )

    return permission_checker


def require_any_permission(*permission_names: str):
    """
    Dependency to check if user has ANY of the specified permissions (OR logic).
    Permissions are checked REAL-TIME from database.

    Usage:
        @router.get("/")
        def list_items(
            auth: dict = Depends(verify_bearer_token),
            _: None = Depends(require_any_permission("item.view", "item.manage"))
        ):
    """
    def permission_checker(auth: dict = Depends(verify_bearer_token)) -> None:
        role_name = auth.get("role_name", "")

        # Superadmin bypass
        if role_name.lower() == "superadmin":
            return None

        # Check permission (already real-time from verify_bearer_token)
        user_permissions = auth.get("permission", [])
        for perm in permission_names:
            if perm in user_permissions:
                return None

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PERMISSION_DENIED",
                "message": f"Anda tidak memiliki akses untuk operasi ini",
            },
        )

    return permission_checker


def require_all_permissions(*permission_names: str):
    """
    Dependency to check if user has ALL of the specified permissions (AND logic).
    Permissions are checked REAL-TIME from database.

    Usage:
        @router.get("/")
        def sensitive_operation(
            auth: dict = Depends(verify_bearer_token),
            _: None = Depends(require_all_permissions("item.view", "item.delete"))
        ):
    """
    def permission_checker(auth: dict = Depends(verify_bearer_token)) -> None:
        role_name = auth.get("role_name", "")

        # Superadmin bypass
        if role_name.lower() == "superadmin":
            return None

        # Check permission (already real-time from verify_bearer_token)
        user_permissions = auth.get("permission", [])
        has_all = all(perm in user_permissions for perm in permission_names)
        if has_all:
            return None

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PERMISSION_DENIED",
                "message": f"Anda tidak memiliki akses untuk operasi ini",
            },
        )

    return permission_checker


def check_permission(auth: dict, permission_name: str) -> None:
    """
    Check if user has specific permission. Raises HTTPException if not.
    Superadmin bypasses all permission checks.
    Permissions are already REAL-TIME from auth context.

    Usage:
        @router.get("/")
        def list_items(auth: dict = Depends(verify_bearer_token)):
            check_permission(auth, "item.view")
            # ... rest of the code
    """
    role_name = auth.get("role_name", "")

    # Superadmin bypass
    if role_name.lower() == "superadmin":
        return None

    # Check permission (already real-time from verify_bearer_token)
    user_permissions = auth.get("permission", [])
    if permission_name in user_permissions:
        return None

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": "PERMISSION_DENIED",
            "message": f"Anda tidak memiliki akses untuk operasi ini",
        },
    )
