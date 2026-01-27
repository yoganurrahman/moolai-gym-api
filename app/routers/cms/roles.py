import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roles", tags=["CMS - Roles"])


# ============== Request Models ==============

class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    permission_ids: List[int] = []


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    permission_ids: Optional[List[int]] = None


# ============== Endpoints ==============

@router.get("")
def list_roles(
    is_active: Optional[bool] = Query(None),
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("role.view")),
):
    """
    List all roles with their permissions.
    Requires: role.view permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = "SELECT id, name, description, is_active, created_at FROM roles WHERE 1=1"
        params = []

        if is_active is not None:
            query += " AND is_active = %s"
            params.append(1 if is_active else 0)

        query += " ORDER BY id ASC"
        cursor.execute(query, params)
        roles = cursor.fetchall()

        # Get permissions for each role
        for role in roles:
            cursor.execute(
                """
                SELECT p.id, p.name, p.description
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id = %s
                ORDER BY p.name
                """,
                (role["id"],),
            )
            role["permissions"] = cursor.fetchall()
            role["is_active"] = bool(role["is_active"])
            if role["created_at"]:
                role["created_at"] = role["created_at"].isoformat()

        return {"success": True, "data": roles}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing roles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LIST_ROLES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{role_id}")
def get_role(
    role_id: int,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("role.view")),
):
    """
    Get a specific role by ID with its permissions.
    Requires: role.view permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id, name, description, is_active, created_at FROM roles WHERE id = %s",
            (role_id,),
        )
        role = cursor.fetchone()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ROLE_NOT_FOUND", "message": "Role tidak ditemukan"},
            )

        # Get permissions
        cursor.execute(
            """
            SELECT p.id, p.name, p.description
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id = %s
            ORDER BY p.name
            """,
            (role_id,),
        )
        role["permissions"] = cursor.fetchall()
        role["is_active"] = bool(role["is_active"])
        if role["created_at"]:
            role["created_at"] = role["created_at"].isoformat()

        return {"success": True, "data": role}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_ROLE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("")
def create_role(
    request: RoleCreateRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("role.create")),
):
    """
    Create a new role with permissions.
    Requires: role.create permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if role name already exists
        cursor.execute("SELECT id FROM roles WHERE name = %s", (request.name,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ROLE_EXISTS", "message": "Nama role sudah ada"},
            )

        # Insert role
        cursor.execute(
            """
            INSERT INTO roles (name, description, is_active, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (request.name, request.description, 1 if request.is_active else 0, datetime.now()),
        )
        role_id = cursor.lastrowid

        # Insert permissions
        if request.permission_ids:
            for permission_id in request.permission_ids:
                cursor.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                    (role_id, permission_id),
                )

        conn.commit()

        return {
            "success": True,
            "message": "Role berhasil dibuat",
            "data": {"id": role_id, "name": request.name},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_ROLE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{role_id}")
def update_role(
    role_id: int,
    request: RoleUpdateRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("role.update")),
):
    """
    Update a role and its permissions.
    Requires: role.update permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if role exists
        cursor.execute("SELECT id, name FROM roles WHERE id = %s", (role_id,))
        role = cursor.fetchone()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ROLE_NOT_FOUND", "message": "Role tidak ditemukan"},
            )

        # Prevent updating superadmin role
        if role["name"].lower() == "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "CANNOT_UPDATE_SUPERADMIN", "message": "Role superadmin tidak dapat diubah"},
            )

        # Build update query dynamically
        update_fields = []
        params = []

        if request.name is not None:
            # Check if new name conflicts
            cursor.execute(
                "SELECT id FROM roles WHERE name = %s AND id != %s",
                (request.name, role_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "ROLE_EXISTS", "message": "Nama role sudah ada"},
                )
            update_fields.append("name = %s")
            params.append(request.name)

        if request.description is not None:
            update_fields.append("description = %s")
            params.append(request.description)

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if update_fields:
            update_fields.append("updated_at = %s")
            params.append(datetime.now())
            params.append(role_id)

            cursor.execute(
                f"UPDATE roles SET {', '.join(update_fields)} WHERE id = %s",
                params,
            )

        # Update permissions if provided
        if request.permission_ids is not None:
            # Delete existing permissions
            cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))

            # Insert new permissions
            for permission_id in request.permission_ids:
                cursor.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                    (role_id, permission_id),
                )

        conn.commit()

        return {
            "success": True,
            "message": "Role berhasil diperbarui",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_ROLE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("role.delete")),
):
    """
    Delete a role.
    Requires: role.delete permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if role exists
        cursor.execute("SELECT id, name FROM roles WHERE id = %s", (role_id,))
        role = cursor.fetchone()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ROLE_NOT_FOUND", "message": "Role tidak ditemukan"},
            )

        # Prevent deleting superadmin role
        if role["name"].lower() == "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "CANNOT_DELETE_SUPERADMIN", "message": "Role superadmin tidak dapat dihapus"},
            )

        # Check if role is in use
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role_id = %s", (role_id,))
        result = cursor.fetchone()
        if result["count"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ROLE_IN_USE",
                    "message": f"Role sedang digunakan oleh {result['count']} user",
                },
            )

        # Delete role permissions first
        cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))

        # Delete role
        cursor.execute("DELETE FROM roles WHERE id = %s", (role_id,))
        conn.commit()

        return {
            "success": True,
            "message": "Role berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_ROLE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
