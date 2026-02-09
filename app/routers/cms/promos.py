"""
CMS Promos Router - CRUD Promos & Vouchers
"""
import json
import logging
from datetime import datetime
from typing import Optional, List, Union

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/promos", tags=["CMS - Promos"])


# ============== Request Models ==============

class PromoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    promo_type: str = Field(..., pattern="^(percentage|fixed|free_item)$")
    discount_value: float = Field(0, ge=0)
    min_purchase: float = Field(0, ge=0)
    max_discount: Optional[float] = Field(None, ge=0)
    applicable_to: str = Field("all", pattern="^(all|membership|class|pt|product)$")
    applicable_items: Optional[Union[List[int], str]] = None
    start_date: str
    end_date: str
    usage_limit: Optional[int] = Field(None, ge=1)
    per_user_limit: int = Field(1, ge=1)
    new_member_only: bool = False
    member_only: bool = False
    is_active: bool = True


class PromoUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    promo_type: Optional[str] = Field(None, pattern="^(percentage|fixed|free_item)$")
    discount_value: Optional[float] = Field(None, ge=0)
    min_purchase: Optional[float] = Field(None, ge=0)
    max_discount: Optional[float] = None
    applicable_to: Optional[str] = Field(None, pattern="^(all|membership|class|pt|product)$")
    applicable_items: Optional[Union[List[int], str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = Field(None, ge=1)
    new_member_only: Optional[bool] = None
    member_only: Optional[bool] = None
    is_active: Optional[bool] = None


class VoucherCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    voucher_type: str = Field(..., pattern="^(percentage|fixed|free_item)$")
    discount_value: float = Field(0, ge=0)
    min_purchase: float = Field(0, ge=0)
    max_discount: Optional[float] = Field(None, ge=0)
    applicable_to: str = Field("all", pattern="^(all|membership|class|pt|product)$")
    applicable_items: Optional[Union[List[int], str]] = None
    start_date: str
    end_date: str
    usage_limit: int = Field(1, ge=1)
    is_single_use: bool = True
    is_active: bool = True


class VoucherUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    voucher_type: Optional[str] = Field(None, pattern="^(percentage|fixed|free_item)$")
    discount_value: Optional[float] = Field(None, ge=0)
    min_purchase: Optional[float] = Field(None, ge=0)
    max_discount: Optional[float] = None
    applicable_to: Optional[str] = Field(None, pattern="^(all|membership|class|pt|product)$")
    applicable_items: Optional[Union[List[int], str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    usage_limit: Optional[int] = None
    is_single_use: Optional[bool] = None
    is_active: Optional[bool] = None


# ============== Voucher Endpoints (must be before /{promo_id} routes) ==============

@router.get("/active")
def get_active_promos(
    applicable_to: Optional[str] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get active promos available for checkout"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = [
            "is_active = 1",
            "start_date <= NOW()",
            "end_date >= NOW()",
            "(usage_limit IS NULL OR usage_count < usage_limit)",
        ]
        params = []

        if applicable_to and applicable_to != "all":
            where_clauses.append("(applicable_to = %s OR applicable_to = 'all')")
            params.append(applicable_to)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT id, name, description, promo_type, discount_value, min_purchase, max_discount,
                   applicable_to, applicable_items, start_date, end_date, usage_limit, usage_count,
                   per_user_limit, new_member_only, member_only
            FROM promos{where_sql}
            ORDER BY discount_value DESC
            """,
            params,
        )
        promos = cursor.fetchall()

        for p in promos:
            p["discount_value"] = float(p["discount_value"]) if p.get("discount_value") else 0
            p["min_purchase"] = float(p["min_purchase"]) if p.get("min_purchase") else 0
            p["max_discount"] = float(p["max_discount"]) if p.get("max_discount") else None
            p["new_member_only"] = bool(p.get("new_member_only"))
            p["member_only"] = bool(p.get("member_only"))
            if p.get("applicable_items") and isinstance(p["applicable_items"], str):
                try:
                    p["applicable_items"] = json.loads(p["applicable_items"])
                except (json.JSONDecodeError, TypeError):
                    pass

        return {"success": True, "data": promos}

    except Exception as e:
        logger.error(f"Error getting active promos: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_ACTIVE_PROMOS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/vouchers/validate")
def validate_voucher(
    request: dict,
    auth: dict = Depends(verify_bearer_token),
):
    """Validate a voucher code and return discount info"""
    code = (request.get("code") or "").strip().upper()
    subtotal = float(request.get("subtotal", 0))

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CODE_REQUIRED", "message": "Kode voucher wajib diisi"},
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT v.*
            FROM vouchers v
            WHERE v.code = %s
            """,
            (code,),
        )
        voucher = cursor.fetchone()

        if not voucher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "VOUCHER_NOT_FOUND", "message": "Kode voucher tidak ditemukan"},
            )

        if not voucher.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "VOUCHER_INACTIVE", "message": "Voucher sudah tidak aktif"},
            )

        from datetime import datetime as dt
        now = dt.now()
        start = voucher.get("start_date")
        end = voucher.get("end_date")
        if start and now < dt.combine(start, dt.min.time()) if hasattr(start, 'year') else False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "VOUCHER_NOT_STARTED", "message": "Voucher belum berlaku"},
            )

        cursor.execute(
            "SELECT start_date, end_date, usage_limit, usage_count FROM vouchers WHERE code = %s AND is_active = 1 AND start_date <= NOW() AND end_date >= NOW() AND (usage_limit IS NULL OR usage_count < usage_limit)",
            (code,),
        )
        valid_row = cursor.fetchone()
        if not valid_row:
            # Check specific reason
            if voucher.get("usage_limit") and voucher.get("usage_count", 0) >= voucher["usage_limit"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "VOUCHER_EXHAUSTED", "message": "Voucher sudah mencapai batas penggunaan"},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "VOUCHER_EXPIRED", "message": "Voucher sudah expired atau belum berlaku"},
            )

        # Check min purchase
        min_purchase = float(voucher.get("min_purchase") or 0)
        if min_purchase > 0 and subtotal < min_purchase:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "MIN_PURCHASE_NOT_MET",
                    "message": f"Minimum pembelian Rp {min_purchase:,.0f}",
                },
            )

        # Calculate discount
        discount_value = float(voucher.get("discount_value") or 0)
        voucher_type = voucher.get("voucher_type", "fixed")
        discount_amount = 0

        if voucher_type == "percentage":
            discount_amount = subtotal * (discount_value / 100)
            max_discount = float(voucher["max_discount"]) if voucher.get("max_discount") else None
            if max_discount and discount_amount > max_discount:
                discount_amount = max_discount
        elif voucher_type == "fixed":
            discount_amount = min(discount_value, subtotal)

        # Parse applicable_items
        applicable_items_parsed = None
        if voucher.get("applicable_items"):
            ai = voucher["applicable_items"]
            if isinstance(ai, str):
                try:
                    applicable_items_parsed = json.loads(ai)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(ai, list):
                applicable_items_parsed = ai

        return {
            "success": True,
            "data": {
                "code": voucher["code"],
                "voucher_type": voucher_type,
                "discount_value": discount_value,
                "discount_amount": round(discount_amount, 2),
                "max_discount": float(voucher["max_discount"]) if voucher.get("max_discount") else None,
                "min_purchase": min_purchase,
                "applicable_to": voucher.get("applicable_to", "all"),
                "applicable_items": applicable_items_parsed,
                "usage_count": voucher.get("usage_count", 0),
                "usage_limit": voucher.get("usage_limit"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating voucher: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "VALIDATE_VOUCHER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/vouchers")
def get_vouchers(
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all vouchers with pagination"""
    check_permission(auth, "promo.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if is_active is not None:
            where_clauses.append("v.is_active = %s")
            params.append(1 if is_active else 0)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cursor.execute(f"SELECT COUNT(*) as total FROM vouchers v{where_sql}", params)
        total = cursor.fetchone()["total"]

        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT v.*
            FROM vouchers v
            {where_sql}
            ORDER BY v.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        vouchers = cursor.fetchall()

        for v in vouchers:
            v["discount_value"] = float(v["discount_value"]) if v.get("discount_value") else 0
            v["min_purchase"] = float(v["min_purchase"]) if v.get("min_purchase") else 0
            v["max_discount"] = float(v["max_discount"]) if v.get("max_discount") else None
            v["is_active"] = bool(v.get("is_active"))
            v["is_single_use"] = bool(v.get("is_single_use"))
            if v.get("applicable_items") and isinstance(v["applicable_items"], str):
                try:
                    v["applicable_items"] = json.loads(v["applicable_items"])
                except (json.JSONDecodeError, TypeError):
                    pass

        return {
            "success": True,
            "data": vouchers,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"Error getting vouchers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_VOUCHERS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/vouchers", status_code=status.HTTP_201_CREATED)
def create_voucher(request: VoucherCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new voucher"""
    check_permission(auth, "promo.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check code uniqueness
        cursor.execute("SELECT id FROM vouchers WHERE code = %s", (request.code.upper(),))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "CODE_EXISTS", "message": "Kode voucher sudah digunakan"},
            )

        # Convert applicable_items list to JSON string
        applicable_items_json = None
        if request.applicable_items:
            if isinstance(request.applicable_items, list):
                applicable_items_json = json.dumps(request.applicable_items)
            else:
                applicable_items_json = request.applicable_items

        cursor.execute(
            """
            INSERT INTO vouchers
            (code, voucher_type, discount_value, min_purchase, max_discount,
             applicable_to, applicable_items, start_date, end_date, usage_limit, is_single_use, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.code.upper(),
                request.voucher_type,
                request.discount_value,
                request.min_purchase,
                request.max_discount,
                request.applicable_to,
                applicable_items_json,
                request.start_date,
                request.end_date,
                request.usage_limit,
                1 if request.is_single_use else 0,
                1 if request.is_active else 0,
                datetime.now(),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Voucher berhasil dibuat",
            "data": {"id": cursor.lastrowid},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating voucher: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_VOUCHER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/vouchers/{voucher_id}")
def update_voucher(voucher_id: int, request: VoucherUpdate, auth: dict = Depends(verify_bearer_token)):
    """Update a voucher"""
    check_permission(auth, "promo.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM vouchers WHERE id = %s", (voucher_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "VOUCHER_NOT_FOUND", "message": "Voucher tidak ditemukan"},
            )

        # Check code uniqueness if changing
        if request.code:
            cursor.execute("SELECT id FROM vouchers WHERE code = %s AND id != %s", (request.code.upper(), voucher_id))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "CODE_EXISTS", "message": "Kode voucher sudah digunakan"},
                )

        update_fields = []
        params = []

        if request.code is not None:
            update_fields.append("`code` = %s")
            params.append(request.code.upper())

        for field in ["voucher_type", "applicable_to", "start_date", "end_date"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"`{field}` = %s")
                params.append(value)

        if request.applicable_items is not None:
            update_fields.append("`applicable_items` = %s")
            if isinstance(request.applicable_items, list):
                params.append(json.dumps(request.applicable_items) if request.applicable_items else None)
            else:
                params.append(request.applicable_items or None)

        for field in ["discount_value", "min_purchase", "max_discount", "usage_limit"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"`{field}` = %s")
                params.append(value)

        for field in ["is_single_use", "is_active"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"`{field}` = %s")
                params.append(1 if value else 0)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(voucher_id)

        cursor.execute(
            f"UPDATE vouchers SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {"success": True, "message": "Voucher berhasil diupdate"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating voucher: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_VOUCHER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/vouchers/{voucher_id}")
def delete_voucher(voucher_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete a voucher (soft delete)"""
    check_permission(auth, "promo.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM vouchers WHERE id = %s", (voucher_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "VOUCHER_NOT_FOUND", "message": "Voucher tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE vouchers SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), voucher_id),
        )
        conn.commit()

        return {"success": True, "message": "Voucher berhasil dihapus"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting voucher: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_VOUCHER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Promo Endpoints (after /vouchers to avoid route conflict) ==============

@router.get("")
def get_promos(
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all promos with pagination"""
    check_permission(auth, "promo.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if is_active is not None:
            where_clauses.append("is_active = %s")
            params.append(1 if is_active else 0)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cursor.execute(f"SELECT COUNT(*) as total FROM promos{where_sql}", params)
        total = cursor.fetchone()["total"]

        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT * FROM promos{where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        promos = cursor.fetchall()

        for p in promos:
            p["discount_value"] = float(p["discount_value"]) if p.get("discount_value") else 0
            p["min_purchase"] = float(p["min_purchase"]) if p.get("min_purchase") else 0
            p["max_discount"] = float(p["max_discount"]) if p.get("max_discount") else None
            p["is_active"] = bool(p.get("is_active"))
            p["new_member_only"] = bool(p.get("new_member_only"))
            p["member_only"] = bool(p.get("member_only"))
            if p.get("applicable_items") and isinstance(p["applicable_items"], str):
                try:
                    p["applicable_items"] = json.loads(p["applicable_items"])
                except (json.JSONDecodeError, TypeError):
                    pass

        return {
            "success": True,
            "data": promos,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"Error getting promos: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PROMOS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_promo(request: PromoCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new promo"""
    check_permission(auth, "promo.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Convert applicable_items list to JSON string
        applicable_items_json = None
        if request.applicable_items:
            if isinstance(request.applicable_items, list):
                applicable_items_json = json.dumps(request.applicable_items)
            else:
                applicable_items_json = request.applicable_items

        cursor.execute(
            """
            INSERT INTO promos
            (name, description, promo_type, discount_value, min_purchase, max_discount,
             applicable_to, applicable_items, start_date, end_date,
             usage_limit, per_user_limit, new_member_only, member_only, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.name,
                request.description,
                request.promo_type,
                request.discount_value,
                request.min_purchase,
                request.max_discount,
                request.applicable_to,
                applicable_items_json,
                request.start_date,
                request.end_date,
                request.usage_limit,
                request.per_user_limit,
                1 if request.new_member_only else 0,
                1 if request.member_only else 0,
                1 if request.is_active else 0,
                datetime.now(),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Promo berhasil dibuat",
            "data": {"id": cursor.lastrowid},
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating promo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_PROMO_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{promo_id}")
def get_promo(promo_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get a specific promo"""
    check_permission(auth, "promo.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM promos WHERE id = %s", (promo_id,))
        promo = cursor.fetchone()

        if not promo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PROMO_NOT_FOUND", "message": "Promo tidak ditemukan"},
            )

        promo["discount_value"] = float(promo["discount_value"]) if promo.get("discount_value") else 0
        promo["min_purchase"] = float(promo["min_purchase"]) if promo.get("min_purchase") else 0
        promo["max_discount"] = float(promo["max_discount"]) if promo.get("max_discount") else None
        promo["is_active"] = bool(promo.get("is_active"))
        promo["new_member_only"] = bool(promo.get("new_member_only"))
        promo["member_only"] = bool(promo.get("member_only"))
        if promo.get("applicable_items") and isinstance(promo["applicable_items"], str):
            try:
                promo["applicable_items"] = json.loads(promo["applicable_items"])
            except (json.JSONDecodeError, TypeError):
                pass

        return {"success": True, "data": promo}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting promo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PROMO_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{promo_id}")
def update_promo(promo_id: int, request: PromoUpdate, auth: dict = Depends(verify_bearer_token)):
    """Update a promo"""
    check_permission(auth, "promo.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM promos WHERE id = %s", (promo_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PROMO_NOT_FOUND", "message": "Promo tidak ditemukan"},
            )

        update_fields = []
        params = []

        for field in ["name", "description", "promo_type", "applicable_to",
                       "start_date", "end_date"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"`{field}` = %s")
                params.append(value)

        if request.applicable_items is not None:
            update_fields.append("`applicable_items` = %s")
            if isinstance(request.applicable_items, list):
                params.append(json.dumps(request.applicable_items) if request.applicable_items else None)
            else:
                params.append(request.applicable_items or None)

        for field in ["discount_value", "min_purchase", "max_discount",
                       "usage_limit", "per_user_limit"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"`{field}` = %s")
                params.append(value)

        for field in ["new_member_only", "member_only", "is_active"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"`{field}` = %s")
                params.append(1 if value else 0)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(promo_id)

        cursor.execute(
            f"UPDATE promos SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {"success": True, "message": "Promo berhasil diupdate"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating promo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_PROMO_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{promo_id}")
def delete_promo(promo_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete a promo (soft delete)"""
    check_permission(auth, "promo.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM promos WHERE id = %s", (promo_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PROMO_NOT_FOUND", "message": "Promo tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE promos SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), promo_id),
        )
        conn.commit()

        return {"success": True, "message": "Promo berhasil dihapus"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting promo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_PROMO_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
