import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permissions", tags=["CMS - Permissions"])


# ============== Request Models ==============

class PermissionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class PermissionUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


# ============== Endpoints ==============

@router.get("")
def list_permissions(
    search: Optional[str] = Query(None),
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("permission.view")),
):
    """
    List all permissions.
    Requires: permission.view permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = "SELECT id, name, description, created_at FROM permissions WHERE 1=1"
        params = []

        if search:
            query += " AND (name LIKE %s OR description LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY name ASC"
        cursor.execute(query, params)
        permissions = cursor.fetchall()

        for perm in permissions:
            if perm["created_at"]:
                perm["created_at"] = perm["created_at"].isoformat()

        return {"success": True, "data": permissions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing permissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LIST_PERMISSIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("")
def create_permission(
    request: PermissionCreateRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("permission.create")),
):
    """
    Create a new permission.
    Requires: permission.create permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if permission name already exists
        cursor.execute("SELECT id FROM permissions WHERE name = %s", (request.name,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PERMISSION_EXISTS", "message": "Nama permission sudah ada"},
            )

        # Insert permission
        cursor.execute(
            """
            INSERT INTO permissions (name, description, created_at)
            VALUES (%s, %s, %s)
            """,
            (request.name, request.description, datetime.now()),
        )
        conn.commit()

        permission_id = cursor.lastrowid

        return {
            "success": True,
            "message": "Permission berhasil dibuat",
            "data": {"id": permission_id, "name": request.name},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_PERMISSION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{permission_id}")
def update_permission(
    permission_id: int,
    request: PermissionUpdateRequest,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("permission.update")),
):
    """
    Update a permission.
    Requires: permission.update permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if permission exists
        cursor.execute("SELECT id FROM permissions WHERE id = %s", (permission_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PERMISSION_NOT_FOUND", "message": "Permission tidak ditemukan"},
            )

        # Build update query
        update_fields = []
        params = []

        if request.name is not None:
            # Check if new name conflicts
            cursor.execute(
                "SELECT id FROM permissions WHERE name = %s AND id != %s",
                (request.name, permission_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "PERMISSION_EXISTS", "message": "Nama permission sudah ada"},
                )
            update_fields.append("name = %s")
            params.append(request.name)

        if request.description is not None:
            update_fields.append("description = %s")
            params.append(request.description)

        if update_fields:
            update_fields.append("updated_at = %s")
            params.append(datetime.now())
            params.append(permission_id)

            cursor.execute(
                f"UPDATE permissions SET {', '.join(update_fields)} WHERE id = %s",
                params,
            )
            conn.commit()

        return {
            "success": True,
            "message": "Permission berhasil diperbarui",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_PERMISSION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{permission_id}")
def delete_permission(
    permission_id: int,
    auth: dict = Depends(verify_bearer_token),
    _: None = Depends(require_permission("permission.delete")),
):
    """
    Delete a permission.
    Requires: permission.delete permission
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if permission exists
        cursor.execute("SELECT id FROM permissions WHERE id = %s", (permission_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PERMISSION_NOT_FOUND", "message": "Permission tidak ditemukan"},
            )

        # Check if permission is in use
        cursor.execute(
            "SELECT COUNT(*) as count FROM role_permissions WHERE permission_id = %s",
            (permission_id,),
        )
        result = cursor.fetchone()
        if result["count"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PERMISSION_IN_USE",
                    "message": f"Permission sedang digunakan oleh {result['count']} role",
                },
            )

        # Delete permission
        cursor.execute("DELETE FROM permissions WHERE id = %s", (permission_id,))
        conn.commit()

        return {
            "success": True,
            "message": "Permission berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_PERMISSION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
