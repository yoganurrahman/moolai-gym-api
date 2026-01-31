import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, EmailStr, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, require_permission
from app.utils.helpers import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["CMS - Users"])


# ============== Request Models ==============

class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role_id: int
    default_branch_id: Optional[int] = None
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    role_id: Optional[int] = None
    default_branch_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=100)


# ============== Endpoints ==============

@router.get("")
def list_users(
    search: Optional[str] = Query(None),
    role_id: Optional[int] = Query(None),
    role_ids: Optional[str] = Query(None, description="Comma-separated role IDs, e.g. 1,2,5"),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("user.view")),
):
    """
    List all users with pagination and filters.
    Requires: user.view permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Build query
        query = """
            SELECT u.id, u.name, u.email, u.phone, u.is_active, u.default_branch_id, u.created_at,
                   r.id as role_id, r.name as role_name,
                   b.name as default_branch_name, b.code as default_branch_code
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN branches b ON u.default_branch_id = b.id
            WHERE 1=1
        """
        count_query = "SELECT COUNT(*) as total FROM users u WHERE 1=1"
        params = []
        count_params = []

        if search:
            search_filter = " AND (u.name LIKE %s OR u.email LIKE %s)"
            query += search_filter
            count_query += search_filter
            params.extend([f"%{search}%", f"%{search}%"])
            count_params.extend([f"%{search}%", f"%{search}%"])

        if role_id is not None:
            role_filter = " AND u.role_id = %s"
            query += role_filter
            count_query += role_filter
            params.append(role_id)
            count_params.append(role_id)
        elif role_ids:
            ids = [int(x.strip()) for x in role_ids.split(",") if x.strip().isdigit()]
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                role_filter = f" AND u.role_id IN ({placeholders})"
                query += role_filter
                count_query += role_filter
                params.extend(ids)
                count_params.extend(ids)

        if is_active is not None:
            active_filter = " AND u.is_active = %s"
            query += active_filter
            count_query += active_filter
            params.append(1 if is_active else 0)
            count_params.append(1 if is_active else 0)

        # Get total count
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()["total"]

        # Add pagination
        offset = (page - 1) * limit
        query += " ORDER BY u.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        users = cursor.fetchall()

        # Format data
        for user in users:
            user["is_active"] = bool(user["is_active"])
            if user["created_at"]:
                user["created_at"] = user["created_at"].isoformat()
            user["role"] = {
                "id": user.pop("role_id"),
                "name": user.pop("role_name"),
            }
            branch_id = user.pop("default_branch_id", None)
            branch_name = user.pop("default_branch_name", None)
            branch_code = user.pop("default_branch_code", None)
            user["default_branch"] = {
                "id": branch_id,
                "name": branch_name,
                "code": branch_code,
            } if branch_id else None

        return {
            "success": True,
            "data": users,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LIST_USERS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{user_id}")
def get_user(
    user_id: int,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("user.view")),
):
    """
    Get a specific user by ID.
    Requires: user.view permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT u.id, u.name, u.email, u.phone, u.is_active, u.default_branch_id,
                   u.created_at, u.updated_at,
                   r.id as role_id, r.name as role_name,
                   b.name as default_branch_name, b.code as default_branch_code
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN branches b ON u.default_branch_id = b.id
            WHERE u.id = %s
            """,
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Format data
        user["is_active"] = bool(user["is_active"])
        if user["created_at"]:
            user["created_at"] = user["created_at"].isoformat()
        if user["updated_at"]:
            user["updated_at"] = user["updated_at"].isoformat()
        user["role"] = {
            "id": user.pop("role_id"),
            "name": user.pop("role_name"),
        }
        branch_id = user.pop("default_branch_id", None)
        branch_name = user.pop("default_branch_name", None)
        branch_code = user.pop("default_branch_code", None)
        user["default_branch"] = {
            "id": branch_id,
            "name": branch_name,
            "code": branch_code,
        } if branch_id else None

        return {"success": True, "data": user}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_USER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("")
def create_user(
    request: UserCreateRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("user.create")),
):
    """
    Create a new user (admin creates user).
    Requires: user.create permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "EMAIL_EXISTS", "message": "Email sudah terdaftar"},
            )

        # Check if role exists
        cursor.execute("SELECT id FROM roles WHERE id = %s", (request.role_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ROLE_NOT_FOUND", "message": "Role tidak ditemukan"},
            )

        # Validate default_branch_id if provided
        if request.default_branch_id is not None:
            cursor.execute(
                "SELECT id FROM branches WHERE id = %s AND is_active = 1",
                (request.default_branch_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "INVALID_BRANCH", "message": "Cabang tidak ditemukan atau tidak aktif"},
                )

        # Hash password
        hashed_password = hash_password(request.password)

        # Insert user
        cursor.execute(
            """
            INSERT INTO users (name, email, password, phone, role_id, default_branch_id, is_active, token_version, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.name,
                request.email,
                hashed_password,
                request.phone,
                request.role_id,
                request.default_branch_id,
                1 if request.is_active else 0,
                1,
                datetime.now(),
            ),
        )
        conn.commit()

        user_id = cursor.lastrowid

        return {
            "success": True,
            "message": "User berhasil dibuat",
            "data": {"id": user_id, "email": request.email, "name": request.name},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_USER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{user_id}")
def update_user(
    user_id: int,
    request: UserUpdateRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("user.update")),
):
    """
    Update a user.
    Requires: user.update permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if user exists
        cursor.execute("SELECT u.id, u.role_id FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Build update query
        update_fields = []
        params = []

        if request.name is not None:
            update_fields.append("name = %s")
            params.append(request.name)

        if request.email is not None:
            # Check if email conflicts
            cursor.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (request.email, user_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "EMAIL_EXISTS", "message": "Email sudah digunakan"},
                )
            update_fields.append("email = %s")
            params.append(request.email)

        if request.phone is not None:
            update_fields.append("phone = %s")
            params.append(request.phone)

        if request.role_id is not None:
            # Check if role exists
            cursor.execute("SELECT id FROM roles WHERE id = %s", (request.role_id,))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "ROLE_NOT_FOUND", "message": "Role tidak ditemukan"},
                )
            update_fields.append("role_id = %s")
            params.append(request.role_id)

        if request.default_branch_id is not None:
            # Validate branch
            cursor.execute(
                "SELECT id FROM branches WHERE id = %s AND is_active = 1",
                (request.default_branch_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "INVALID_BRANCH", "message": "Cabang tidak ditemukan atau tidak aktif"},
                )
            update_fields.append("default_branch_id = %s")
            params.append(request.default_branch_id)

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if update_fields:
            update_fields.append("updated_at = %s")
            params.append(datetime.now())
            params.append(user_id)

            cursor.execute(
                f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s",
                params,
            )
            conn.commit()

        return {
            "success": True,
            "message": "User berhasil diperbarui",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_USER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    request: UserResetPasswordRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("user.update")),
):
    """
    Reset a user's password (admin action).
    Requires: user.update permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Hash new password and update
        hashed_password = hash_password(request.new_password)
        cursor.execute(
            """
            UPDATE users
            SET password = %s, token_version = token_version + 1, updated_at = %s
            WHERE id = %s
            """,
            (hashed_password, datetime.now(), user_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Password berhasil direset",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error resetting password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "RESET_PASSWORD_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("user.delete")),
):
    """
    Delete a user.
    Requires: user.delete permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if user exists
        cursor.execute(
            """
            SELECT u.id, r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
            """,
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Prevent deleting superadmin
        if user["role_name"] and user["role_name"].lower() == "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "CANNOT_DELETE_SUPERADMIN", "message": "User superadmin tidak dapat dihapus"},
            )

        # Prevent self-deletion
        if user_id == auth["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "CANNOT_DELETE_SELF", "message": "Tidak dapat menghapus akun sendiri"},
            )

        # Delete user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()

        return {
            "success": True,
            "message": "User berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_USER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
