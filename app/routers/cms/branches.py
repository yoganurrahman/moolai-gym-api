"""
Branches Router - CRUD Management Cabang/Lokasi Gym
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/branches", tags=["CMS - Branches"])


# ============== Request Models ==============

class BranchCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: str = "Asia/Jakarta"
    opening_time: str = "06:00:00"
    closing_time: str = "22:00:00"
    sort_order: int = 0


class BranchUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class AssignTrainerRequest(BaseModel):
    trainer_id: int
    is_primary: bool = False


class UpdateBranchStockRequest(BaseModel):
    stock: int = Field(..., ge=0)
    min_stock: int = Field(5, ge=0)


# ============== Endpoints ==============

@router.get("")
def get_branches(
    is_active: Optional[bool] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all branches"""
    check_permission(auth, "branch.view")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if is_active is not None:
            where_clauses.append("is_active = %s")
            params.append(1 if is_active else 0)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cursor.execute(
            f"SELECT * FROM branches{where_sql} ORDER BY sort_order ASC, name ASC",
            params,
        )
        branches = cursor.fetchall()

        for b in branches:
            if b.get("opening_time"):
                b["opening_time"] = str(b["opening_time"])
            if b.get("closing_time"):
                b["closing_time"] = str(b["closing_time"])

        return {
            "success": True,
            "data": branches,
            "total": len(branches),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branches: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_BRANCHES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{branch_id}")
def get_branch(branch_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get branch detail"""
    check_permission(auth, "branch.view")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()

        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan"},
            )

        if branch.get("opening_time"):
            branch["opening_time"] = str(branch["opening_time"])
        if branch.get("closing_time"):
            branch["closing_time"] = str(branch["closing_time"])

        # Get trainer count
        cursor.execute(
            "SELECT COUNT(*) as total FROM trainer_branches WHERE branch_id = %s",
            (branch_id,),
        )
        branch["trainer_count"] = cursor.fetchone()["total"]

        return {"success": True, "data": branch}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_BRANCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_branch(
    request: BranchCreate,
    auth: dict = Depends(verify_bearer_token),
):
    """Create a new branch"""
    check_permission(auth, "branch.create")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check code uniqueness
        cursor.execute("SELECT id FROM branches WHERE code = %s", (request.code.upper(),))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "BRANCH_CODE_EXISTS", "message": f"Kode cabang '{request.code}' sudah digunakan"},
            )

        cursor.execute(
            """
            INSERT INTO branches (code, name, address, city, province, phone, email,
                                  timezone, opening_time, closing_time, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.code.upper(),
                request.name,
                request.address,
                request.city,
                request.province,
                request.phone,
                request.email,
                request.timezone,
                request.opening_time,
                request.closing_time,
                request.sort_order,
            ),
        )
        conn.commit()
        branch_id = cursor.lastrowid

        return {
            "success": True,
            "message": f"Cabang '{request.name}' berhasil dibuat",
            "data": {"id": branch_id, "code": request.code.upper()},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating branch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_BRANCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{branch_id}")
def update_branch(
    branch_id: int,
    request: BranchUpdate,
    auth: dict = Depends(verify_bearer_token),
):
    """Update a branch"""
    check_permission(auth, "branch.update")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM branches WHERE id = %s", (branch_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan"},
            )

        update_fields = []
        params = []

        if request.code is not None:
            # Check uniqueness
            cursor.execute(
                "SELECT id FROM branches WHERE code = %s AND id != %s",
                (request.code.upper(), branch_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error_code": "BRANCH_CODE_EXISTS", "message": f"Kode cabang '{request.code}' sudah digunakan"},
                )
            update_fields.append("code = %s")
            params.append(request.code.upper())

        for field in ["name", "address", "city", "province", "phone", "email", "timezone", "opening_time", "closing_time", "sort_order"]:
            value = getattr(request, field, None)
            if value is not None:
                update_fields.append(f"{field} = %s")
                params.append(value)

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        params.append(branch_id)
        cursor.execute(
            f"UPDATE branches SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {"success": True, "message": "Cabang berhasil diupdate"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating branch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_BRANCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{branch_id}")
def delete_branch(branch_id: int, auth: dict = Depends(verify_bearer_token)):
    """Soft-delete a branch (set is_active=0)"""
    check_permission(auth, "branch.delete")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE branches SET is_active = 0 WHERE id = %s", (branch_id,)
        )
        conn.commit()

        return {"success": True, "message": f"Cabang '{branch['name']}' berhasil dinonaktifkan"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting branch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_BRANCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Trainer Assignment ==============

@router.get("/{branch_id}/trainers")
def get_branch_trainers(branch_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get trainers assigned to a branch"""
    check_permission(auth, "branch.view")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM branches WHERE id = %s", (branch_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan"},
            )

        cursor.execute(
            """
            SELECT t.id as trainer_id, t.specialization, t.is_active,
                   u.name, u.email, u.phone, u.avatar,
                   tb.is_primary, tb.created_at as assigned_at
            FROM trainer_branches tb
            JOIN trainers t ON tb.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
            WHERE tb.branch_id = %s
            ORDER BY tb.is_primary DESC, u.name ASC
            """,
            (branch_id,),
        )
        trainers = cursor.fetchall()

        return {"success": True, "data": trainers, "total": len(trainers)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branch trainers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_BRANCH_TRAINERS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{branch_id}/trainers", status_code=status.HTTP_201_CREATED)
def assign_trainer_to_branch(
    branch_id: int,
    request: AssignTrainerRequest,
    auth: dict = Depends(verify_bearer_token),
):
    """Assign a trainer to a branch"""
    check_permission(auth, "branch.update")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate branch
        cursor.execute("SELECT id FROM branches WHERE id = %s AND is_active = 1", (branch_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan"},
            )

        # Validate trainer
        cursor.execute("SELECT id FROM trainers WHERE id = %s AND is_active = 1", (request.trainer_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        # Check if already assigned
        cursor.execute(
            "SELECT id FROM trainer_branches WHERE trainer_id = %s AND branch_id = %s",
            (request.trainer_id, branch_id),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "ALREADY_ASSIGNED", "message": "Trainer sudah di-assign ke cabang ini"},
            )

        # If setting as primary, unset other primaries for this trainer
        if request.is_primary:
            cursor.execute(
                "UPDATE trainer_branches SET is_primary = 0 WHERE trainer_id = %s",
                (request.trainer_id,),
            )

        cursor.execute(
            "INSERT INTO trainer_branches (trainer_id, branch_id, is_primary) VALUES (%s, %s, %s)",
            (request.trainer_id, branch_id, 1 if request.is_primary else 0),
        )
        conn.commit()

        return {"success": True, "message": "Trainer berhasil di-assign ke cabang"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error assigning trainer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ASSIGN_TRAINER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{branch_id}/trainers/{trainer_id}")
def remove_trainer_from_branch(
    branch_id: int,
    trainer_id: int,
    auth: dict = Depends(verify_bearer_token),
):
    """Remove a trainer from a branch"""
    check_permission(auth, "branch.update")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id FROM trainer_branches WHERE trainer_id = %s AND branch_id = %s",
            (trainer_id, branch_id),
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ASSIGNMENT_NOT_FOUND", "message": "Trainer tidak di-assign ke cabang ini"},
            )

        cursor.execute(
            "DELETE FROM trainer_branches WHERE trainer_id = %s AND branch_id = %s",
            (trainer_id, branch_id),
        )
        conn.commit()

        return {"success": True, "message": "Trainer berhasil di-remove dari cabang"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error removing trainer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REMOVE_TRAINER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Branch Stock ==============

@router.get("/{branch_id}/stock")
def get_branch_stock(branch_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get product stock at a specific branch"""
    check_permission(auth, "branch.view")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM branches WHERE id = %s", (branch_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan"},
            )

        cursor.execute(
            """
            SELECT bps.id, bps.stock, bps.min_stock,
                   p.id as product_id, p.sku, p.name, p.price, p.is_active,
                   pc.name as category_name
            FROM branch_product_stock bps
            JOIN products p ON bps.product_id = p.id
            LEFT JOIN product_categories pc ON p.category_id = pc.id
            WHERE bps.branch_id = %s
            ORDER BY pc.sort_order ASC, p.name ASC
            """,
            (branch_id,),
        )
        stock = cursor.fetchall()

        for s in stock:
            s["price"] = float(s["price"]) if s.get("price") else 0
            s["low_stock"] = s["stock"] <= s["min_stock"]

        return {"success": True, "data": stock, "total": len(stock)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branch stock: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_BRANCH_STOCK_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{branch_id}/stock/{product_id}")
def update_branch_stock(
    branch_id: int,
    product_id: int,
    request: UpdateBranchStockRequest,
    auth: dict = Depends(verify_bearer_token),
):
    """Update product stock at a specific branch"""
    check_permission(auth, "branch.update")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if stock record exists
        cursor.execute(
            "SELECT id, stock FROM branch_product_stock WHERE branch_id = %s AND product_id = %s",
            (branch_id, product_id),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE branch_product_stock SET stock = %s, min_stock = %s WHERE id = %s",
                (request.stock, request.min_stock, existing["id"]),
            )
        else:
            cursor.execute(
                "INSERT INTO branch_product_stock (branch_id, product_id, stock, min_stock) VALUES (%s, %s, %s, %s)",
                (branch_id, product_id, request.stock, request.min_stock),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Stock berhasil diupdate",
            "data": {"branch_id": branch_id, "product_id": product_id, "stock": request.stock},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating branch stock: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_BRANCH_STOCK_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
