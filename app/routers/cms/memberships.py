"""
CMS Memberships Router - Admin management of memberships
"""
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memberships", tags=["CMS - Memberships"])


# ============== Request/Response Models ==============

class FreezeMembershipRequest(BaseModel):
    freeze_until: date
    reason: Optional[str] = None


class CreateMembershipRequest(BaseModel):
    user_id: int
    package_id: int
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")
    auto_renew: bool = False
    notes: Optional[str] = None


# ============== Helper Functions ==============

def generate_membership_code():
    """Generate unique membership code"""
    return f"MBR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_transaction_code(branch_code: str = ""):
    """Generate unique transaction code with branch code"""
    prefix = f"TRX-{branch_code}-" if branch_code else "TRX-"
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ============== Endpoints ==============

@router.get("")
def get_all_memberships(
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all memberships with filters"""
    check_permission(auth, "member.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if user_id:
            where_clauses.append("mm.user_id = %s")
            params.append(user_id)

        if status_filter:
            where_clauses.append("mm.status = %s")
            params.append(status_filter)

        if search:
            where_clauses.append("(u.name LIKE %s OR u.email LIKE %s OR mm.membership_code LIKE %s)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(
            f"""
            SELECT COUNT(*) as total
            FROM member_memberships mm
            JOIN users u ON mm.user_id = u.id
            {where_sql}
            """,
            params
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT mm.*, mp.name as package_name, mp.package_type, mp.price,
                   mp.include_classes, mp.class_quota,
                   u.name as member_name, u.email as member_email, u.phone as member_phone,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.membership_id = mm.id
                    AND cb.status IN ('booked', 'attended')) as classes_used
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            JOIN users u ON mm.user_id = u.id
            {where_sql}
            ORDER BY mm.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        memberships = cursor.fetchall()

        for m in memberships:
            m["price"] = float(m["price"]) if m.get("price") else 0
            # Calculate remaining days
            if m.get("end_date") and m["status"] == "active":
                remaining_days = (m["end_date"] - date.today()).days
                m["remaining_days"] = max(0, remaining_days)
            else:
                m["remaining_days"] = None

        return {
            "success": True,
            "data": memberships,
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
        logger.error(f"Error getting memberships: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_MEMBERSHIPS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{membership_id}")
def get_membership_detail(
    membership_id: int,
    auth: dict = Depends(verify_bearer_token),
):
    """Get membership detail"""
    check_permission(auth, "member.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT mm.*, mp.name as package_name, mp.package_type, mp.price,
                   mp.duration_days, mp.visit_quota, mp.include_classes, mp.facilities,
                   u.name as member_name, u.email as member_email, u.phone as member_phone
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            JOIN users u ON mm.user_id = u.id
            WHERE mm.id = %s
            """,
            (membership_id,),
        )
        membership = cursor.fetchone()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "MEMBERSHIP_NOT_FOUND", "message": "Membership tidak ditemukan"},
            )

        membership["price"] = float(membership["price"]) if membership.get("price") else 0

        if membership.get("facilities"):
            import json
            membership["facilities"] = json.loads(membership["facilities"]) if isinstance(membership["facilities"], str) else membership["facilities"]

        # Get transaction history
        cursor.execute(
            """
            SELECT t.id, t.transaction_code, t.grand_total, t.payment_method,
                   t.payment_status, t.created_at
            FROM transactions t
            JOIN transaction_items ti ON t.id = ti.transaction_id
            WHERE ti.item_type = 'membership' AND ti.item_id = %s
            ORDER BY t.created_at DESC
            """,
            (membership["package_id"],),
        )
        transactions = cursor.fetchall()
        for t in transactions:
            t["grand_total"] = float(t["grand_total"]) if t.get("grand_total") else 0

        membership["transactions"] = transactions

        return {
            "success": True,
            "data": membership,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting membership detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_MEMBERSHIP_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("")
def create_membership(
    request: CreateMembershipRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Create membership for a user (admin). Requires branch context for transaction."""
    check_permission(auth, "member.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check user exists
        cursor.execute("SELECT id, name FROM users WHERE id = %s AND is_active = 1", (request.user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Get package details
        cursor.execute(
            "SELECT * FROM membership_packages WHERE id = %s AND is_active = 1",
            (request.package_id,),
        )
        package = cursor.fetchone()

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PACKAGE_NOT_FOUND", "message": "Paket tidak ditemukan"},
            )

        # Check if user already has active membership
        cursor.execute(
            """
            SELECT id FROM member_memberships
            WHERE user_id = %s AND status = 'active'
            """,
            (request.user_id,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ACTIVE_MEMBERSHIP_EXISTS",
                    "message": "User sudah memiliki membership aktif",
                },
            )

        # Get tax settings
        cursor.execute("SELECT `key`, `value` FROM settings WHERE `key` IN ('tax_enabled', 'tax_percentage')")
        settings = {row["key"]: row["value"] for row in cursor.fetchall()}
        tax_enabled = settings.get("tax_enabled", "false") == "true"
        tax_percentage = float(settings.get("tax_percentage", "0"))

        # Calculate pricing
        subtotal = float(package["price"])
        tax_amount = subtotal * (tax_percentage / 100) if tax_enabled else 0
        grand_total = subtotal + tax_amount

        # Get branch code for transaction code
        cursor.execute("SELECT code FROM branches WHERE id = %s", (branch_id,))
        branch_row = cursor.fetchone()
        branch_code = branch_row["code"] if branch_row else ""

        # Create transaction
        transaction_code = generate_transaction_code(branch_code)
        cursor.execute(
            """
            INSERT INTO transactions
            (branch_id, transaction_code, user_id, staff_id, subtotal, subtotal_after_discount,
             tax_percentage, tax_amount, grand_total, payment_method, payment_status,
             paid_amount, paid_at, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
                transaction_code,
                request.user_id,
                auth["user_id"],  # staff
                subtotal,
                subtotal,
                tax_percentage if tax_enabled else 0,
                tax_amount,
                grand_total,
                request.payment_method,
                "paid",
                grand_total,
                datetime.now(),
                request.notes,
                datetime.now(),
            ),
        )
        transaction_id = cursor.lastrowid

        # Create transaction item
        cursor.execute(
            """
            INSERT INTO transaction_items
            (transaction_id, item_type, item_id, item_name, quantity, unit_price, subtotal, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_id,
                "membership",
                package["id"],
                package["name"],
                1,
                subtotal,
                subtotal,
                datetime.now(),
            ),
        )

        # Calculate dates
        start_date = date.today()
        end_date = None
        visit_remaining = None

        if package["package_type"] == "visit":
            visit_remaining = package["visit_quota"]
        else:
            end_date = start_date + timedelta(days=package["duration_days"])

        # Create membership
        membership_code = generate_membership_code()
        cursor.execute(
            """
            INSERT INTO member_memberships
            (user_id, package_id, transaction_id, membership_code, start_date, end_date,
             visit_remaining, class_remaining, status, auto_renew, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.user_id,
                package["id"],
                transaction_id,
                membership_code,
                start_date,
                end_date,
                visit_remaining,
                package["class_quota"],
                "active",
                1 if request.auto_renew else 0,
                datetime.now(),
            ),
        )
        membership_id = cursor.lastrowid

        conn.commit()

        return {
            "success": True,
            "message": f"Membership berhasil dibuat untuk {user['name']}",
            "data": {
                "membership_id": membership_id,
                "membership_code": membership_code,
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "package_name": package["name"],
                "start_date": str(start_date),
                "end_date": str(end_date) if end_date else None,
                "visit_remaining": visit_remaining,
                "total_paid": grand_total,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_MEMBERSHIP_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{membership_id}/freeze")
def freeze_membership(
    membership_id: int,
    request: FreezeMembershipRequest,
    auth: dict = Depends(verify_bearer_token)
):
    """Freeze a membership"""
    check_permission(auth, "member.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check membership
        cursor.execute(
            "SELECT * FROM member_memberships WHERE id = %s AND status = 'active'",
            (membership_id,),
        )
        membership = cursor.fetchone()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "MEMBERSHIP_NOT_FOUND", "message": "Membership aktif tidak ditemukan"},
            )

        # Freeze
        cursor.execute(
            """
            UPDATE member_memberships
            SET status = 'frozen', frozen_at = %s, frozen_until = %s, freeze_reason = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), request.freeze_until, request.reason, datetime.now(), membership_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Membership berhasil dibekukan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error freezing membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "FREEZE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{membership_id}/unfreeze")
def unfreeze_membership(membership_id: int, auth: dict = Depends(verify_bearer_token)):
    """Unfreeze a membership"""
    check_permission(auth, "member.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check membership
        cursor.execute(
            "SELECT * FROM member_memberships WHERE id = %s AND status = 'frozen'",
            (membership_id,),
        )
        membership = cursor.fetchone()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "MEMBERSHIP_NOT_FOUND", "message": "Membership frozen tidak ditemukan"},
            )

        # Calculate new end date (add frozen days back)
        frozen_days = 0
        if membership["frozen_at"] and membership["end_date"]:
            frozen_days = (date.today() - membership["frozen_at"].date()).days
            new_end_date = membership["end_date"] + timedelta(days=frozen_days)
        else:
            new_end_date = membership["end_date"]

        # Unfreeze
        cursor.execute(
            """
            UPDATE member_memberships
            SET status = 'active', end_date = %s, frozen_at = NULL, frozen_until = NULL,
                freeze_reason = NULL, updated_at = %s
            WHERE id = %s
            """,
            (new_end_date, datetime.now(), membership_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Membership berhasil diaktifkan kembali",
            "data": {
                "new_end_date": str(new_end_date) if new_end_date else None,
                "frozen_days_added": frozen_days,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error unfreezing membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UNFREEZE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{membership_id}/cancel")
def cancel_membership(membership_id: int, auth: dict = Depends(verify_bearer_token)):
    """Cancel a membership"""
    check_permission(auth, "member.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check membership
        cursor.execute(
            "SELECT * FROM member_memberships WHERE id = %s AND status IN ('active', 'frozen')",
            (membership_id,),
        )
        membership = cursor.fetchone()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "MEMBERSHIP_NOT_FOUND", "message": "Membership tidak ditemukan"},
            )

        # Cancel
        cursor.execute(
            """
            UPDATE member_memberships
            SET status = 'cancelled', cancelled_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), datetime.now(), membership_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Membership berhasil dibatalkan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error cancelling membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CANCEL_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
