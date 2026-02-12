"""
CMS Packages Router - CRUD Membership Packages
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/packages", tags=["CMS - Packages"])


# ============== Request/Response Models ==============

class PackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    package_type: str = Field(..., pattern=r"^(daily|weekly|monthly|quarterly|yearly|visit)$")
    duration_days: Optional[int] = Field(None, ge=1)
    visit_quota: Optional[int] = Field(None, ge=1)
    price: float = Field(..., gt=0)
    include_classes: bool = False
    class_quota: Optional[int] = Field(None, ge=1)
    facilities: Optional[List[str]] = None
    is_active: bool = True
    sort_order: int = 0


class PackageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    package_type: Optional[str] = Field(None, pattern=r"^(daily|weekly|monthly|quarterly|yearly|visit)$")
    duration_days: Optional[int] = Field(None, ge=1)
    visit_quota: Optional[int] = Field(None, ge=1)
    price: Optional[float] = Field(None, gt=0)
    include_classes: Optional[bool] = None
    class_quota: Optional[int] = Field(None, ge=1)
    facilities: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ============== Endpoints ==============

@router.get("")
def get_packages(
    package_type: Optional[str] = Query(None, description="Filter by package type"),
    is_active: Optional[bool] = Query(True, description="Filter by active status (default: active only)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all membership packages with pagination"""
    check_permission(auth, "package.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Build query
        where_clauses = []
        params = []

        if package_type:
            where_clauses.append("package_type = %s")
            params.append(package_type)

        if is_active is not None:
            where_clauses.append("is_active = %s")
            params.append(1 if is_active else 0)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(f"SELECT COUNT(*) as total FROM membership_packages{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get data with pagination
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT * FROM membership_packages
            {where_sql}
            ORDER BY sort_order ASC, id ASC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        packages = cursor.fetchall()

        # Format response
        for pkg in packages:
            if pkg.get("facilities"):
                import json
                pkg["facilities"] = json.loads(pkg["facilities"]) if isinstance(pkg["facilities"], str) else pkg["facilities"]
            pkg["price"] = float(pkg["price"]) if pkg.get("price") else 0
            pkg["is_active"] = bool(pkg.get("is_active"))
            pkg["include_classes"] = bool(pkg.get("include_classes"))

        return {
            "success": True,
            "data": packages,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting packages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PACKAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_package(request: PackageCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new membership package"""
    check_permission(auth, "package.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        import json
        facilities_json = json.dumps(request.facilities) if request.facilities else None

        cursor.execute(
            """
            INSERT INTO membership_packages
            (name, description, package_type, duration_days, visit_quota, price,
             include_classes, class_quota, facilities, is_active, sort_order, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.name,
                request.description,
                request.package_type,
                request.duration_days,
                request.visit_quota,
                request.price,
                1 if request.include_classes else 0,
                request.class_quota,
                facilities_json,
                1 if request.is_active else 0,
                request.sort_order,
                datetime.now(),
            ),
        )
        conn.commit()
        package_id = cursor.lastrowid

        return {
            "success": True,
            "message": "Paket berhasil dibuat",
            "data": {"id": package_id},
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating package: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_PACKAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{package_id}")
def get_package(package_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get a specific membership package by ID"""
    check_permission(auth, "package.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM membership_packages WHERE id = %s", (package_id,))
        package = cursor.fetchone()

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PACKAGE_NOT_FOUND", "message": "Paket tidak ditemukan"},
            )

        # Format response
        if package.get("facilities"):
            import json
            package["facilities"] = json.loads(package["facilities"]) if isinstance(package["facilities"], str) else package["facilities"]
        package["price"] = float(package["price"]) if package.get("price") else 0
        package["is_active"] = bool(package.get("is_active"))
        package["include_classes"] = bool(package.get("include_classes"))

        return {
            "success": True,
            "data": package,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting package: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PACKAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{package_id}")
def update_package(
    package_id: int, request: PackageUpdate, auth: dict = Depends(verify_bearer_token)
):
    """Update a membership package"""
    check_permission(auth, "package.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if package exists
        cursor.execute("SELECT id FROM membership_packages WHERE id = %s", (package_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PACKAGE_NOT_FOUND", "message": "Paket tidak ditemukan"},
            )

        # Build update query dynamically
        update_fields = []
        params = []

        if request.name is not None:
            update_fields.append("name = %s")
            params.append(request.name)

        if request.description is not None:
            update_fields.append("description = %s")
            params.append(request.description)

        if request.package_type is not None:
            update_fields.append("package_type = %s")
            params.append(request.package_type)

        if request.duration_days is not None:
            update_fields.append("duration_days = %s")
            params.append(request.duration_days)

        if request.visit_quota is not None:
            update_fields.append("visit_quota = %s")
            params.append(request.visit_quota)

        if request.price is not None:
            update_fields.append("price = %s")
            params.append(request.price)

        if request.include_classes is not None:
            update_fields.append("include_classes = %s")
            params.append(1 if request.include_classes else 0)

        if request.class_quota is not None:
            update_fields.append("class_quota = %s")
            params.append(request.class_quota)

        if request.facilities is not None:
            import json
            update_fields.append("facilities = %s")
            params.append(json.dumps(request.facilities))

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if request.sort_order is not None:
            update_fields.append("sort_order = %s")
            params.append(request.sort_order)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(package_id)

        cursor.execute(
            f"UPDATE membership_packages SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Paket berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating package: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_PACKAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{package_id}")
def delete_package(package_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete a membership package (soft delete by setting is_active = false)"""
    check_permission(auth, "package.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if package exists
        cursor.execute("SELECT id FROM membership_packages WHERE id = %s", (package_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PACKAGE_NOT_FOUND", "message": "Paket tidak ditemukan"},
            )

        # Check if package is in use
        cursor.execute(
            "SELECT COUNT(*) as count FROM member_memberships WHERE package_id = %s AND status = 'active'",
            (package_id,),
        )
        if cursor.fetchone()["count"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PACKAGE_IN_USE",
                    "message": "Paket sedang digunakan oleh member aktif. Nonaktifkan paket saja.",
                },
            )

        # Soft delete
        cursor.execute(
            "UPDATE membership_packages SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), package_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Paket berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting package: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_PACKAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
