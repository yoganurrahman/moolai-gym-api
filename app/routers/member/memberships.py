"""
Member Memberships Router - Member's membership endpoints
"""
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memberships", tags=["Member - Memberships"])


# ============== Request/Response Models ==============

class PurchaseMembershipRequest(BaseModel):
    package_id: int
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")
    auto_renew: bool = False
    notes: Optional[str] = None


class RenewMembershipRequest(BaseModel):
    membership_id: int
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")


# ============== Helper Functions ==============

def generate_membership_code():
    """Generate unique membership code"""
    return f"MBR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_transaction_code():
    """Generate unique transaction code"""
    return f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ============== Endpoints ==============

@router.get("/my")
def get_my_membership(auth: dict = Depends(verify_bearer_token)):
    """Get current active membership for logged-in member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT mm.*, mp.name as package_name, mp.package_type,
                   mp.include_classes, mp.facilities
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.user_id = %s AND mm.status = 'active'
            ORDER BY mm.created_at DESC
            LIMIT 1
            """,
            (auth["user_id"],),
        )
        membership = cursor.fetchone()

        if not membership:
            return {
                "success": True,
                "data": None,
                "message": "Anda belum memiliki membership aktif",
            }

        # Format response
        if membership.get("facilities"):
            import json
            membership["facilities"] = json.loads(membership["facilities"]) if isinstance(membership["facilities"], str) else membership["facilities"]

        # Calculate remaining days
        if membership.get("end_date"):
            remaining_days = (membership["end_date"] - date.today()).days
            membership["remaining_days"] = max(0, remaining_days)
        else:
            membership["remaining_days"] = None

        return {
            "success": True,
            "data": membership,
        }

    except Exception as e:
        logger.error(f"Error getting membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_MEMBERSHIP_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/history")
def get_membership_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get membership history for logged-in member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Count total
        cursor.execute(
            "SELECT COUNT(*) as total FROM member_memberships WHERE user_id = %s",
            (auth["user_id"],),
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            """
            SELECT mm.*, mp.name as package_name, mp.package_type, mp.price
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.user_id = %s
            ORDER BY mm.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (auth["user_id"], limit, offset),
        )
        memberships = cursor.fetchall()

        for m in memberships:
            m["price"] = float(m["price"]) if m.get("price") else 0

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

    except Exception as e:
        logger.error(f"Error getting membership history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_HISTORY_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/packages")
def get_available_packages(auth: dict = Depends(verify_bearer_token)):
    """Get available membership packages for purchase"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, name, description, package_type, duration_days, visit_quota,
                   price, include_classes, class_quota, facilities
            FROM membership_packages
            WHERE is_active = 1
            ORDER BY sort_order ASC, price ASC
            """
        )
        packages = cursor.fetchall()

        for pkg in packages:
            if pkg.get("facilities"):
                import json
                pkg["facilities"] = json.loads(pkg["facilities"]) if isinstance(pkg["facilities"], str) else pkg["facilities"]
            pkg["price"] = float(pkg["price"]) if pkg.get("price") else 0
            pkg["include_classes"] = bool(pkg.get("include_classes"))

        return {
            "success": True,
            "data": packages,
        }

    except Exception as e:
        logger.error(f"Error getting packages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PACKAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/purchase")
def purchase_membership(
    request: PurchaseMembershipRequest, auth: dict = Depends(verify_bearer_token)
):
    """Purchase a new membership"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
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
            (auth["user_id"],),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ACTIVE_MEMBERSHIP_EXISTS",
                    "message": "Anda sudah memiliki membership aktif. Gunakan perpanjang untuk memperpanjang.",
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

        # Create transaction
        transaction_code = generate_transaction_code()
        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, user_id, subtotal, subtotal_after_discount,
             tax_percentage, tax_amount, grand_total, payment_method, payment_status,
             paid_amount, paid_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_code,
                auth["user_id"],
                subtotal,
                subtotal,
                tax_percentage if tax_enabled else 0,
                tax_amount,
                grand_total,
                request.payment_method,
                "paid",
                grand_total,
                datetime.now(),
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
                auth["user_id"],
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
            "message": "Membership berhasil dibeli",
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
        logger.error(f"Error purchasing membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PURCHASE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/renew")
def renew_membership(
    request: RenewMembershipRequest, auth: dict = Depends(verify_bearer_token)
):
    """Renew an existing membership"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get existing membership
        cursor.execute(
            """
            SELECT mm.*, mp.name as package_name, mp.package_type, mp.duration_days,
                   mp.visit_quota, mp.price, mp.class_quota
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.id = %s AND mm.user_id = %s
            """,
            (request.membership_id, auth["user_id"]),
        )
        membership = cursor.fetchone()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "MEMBERSHIP_NOT_FOUND", "message": "Membership tidak ditemukan"},
            )

        # Get tax settings
        cursor.execute("SELECT `key`, `value` FROM settings WHERE `key` IN ('tax_enabled', 'tax_percentage')")
        settings = {row["key"]: row["value"] for row in cursor.fetchall()}
        tax_enabled = settings.get("tax_enabled", "false") == "true"
        tax_percentage = float(settings.get("tax_percentage", "0"))

        # Calculate pricing
        subtotal = float(membership["price"])
        tax_amount = subtotal * (tax_percentage / 100) if tax_enabled else 0
        grand_total = subtotal + tax_amount

        # Create transaction
        transaction_code = generate_transaction_code()
        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, user_id, subtotal, subtotal_after_discount,
             tax_percentage, tax_amount, grand_total, payment_method, payment_status,
             paid_amount, paid_at, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_code,
                auth["user_id"],
                subtotal,
                subtotal,
                tax_percentage if tax_enabled else 0,
                tax_amount,
                grand_total,
                request.payment_method,
                "paid",
                grand_total,
                datetime.now(),
                f"Perpanjangan membership {membership['membership_code']}",
                datetime.now(),
            ),
        )
        transaction_id = cursor.lastrowid

        # Create transaction item
        cursor.execute(
            """
            INSERT INTO transaction_items
            (transaction_id, item_type, item_id, item_name, item_description,
             quantity, unit_price, subtotal, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_id,
                "membership",
                membership["package_id"],
                membership["package_name"],
                "Perpanjangan",
                1,
                subtotal,
                subtotal,
                datetime.now(),
            ),
        )

        # Calculate new dates
        if membership["package_type"] == "visit":
            # Add visit quota
            new_visit_remaining = (membership["visit_remaining"] or 0) + membership["visit_quota"]
            cursor.execute(
                """
                UPDATE member_memberships
                SET visit_remaining = %s, status = 'active', updated_at = %s
                WHERE id = %s
                """,
                (new_visit_remaining, datetime.now(), membership["id"]),
            )
            new_end_date = None
        else:
            # Extend end date
            current_end = membership["end_date"] or date.today()
            if current_end < date.today():
                current_end = date.today()
            new_end_date = current_end + timedelta(days=membership["duration_days"])

            cursor.execute(
                """
                UPDATE member_memberships
                SET end_date = %s, status = 'active', updated_at = %s
                WHERE id = %s
                """,
                (new_end_date, datetime.now(), membership["id"]),
            )
            new_visit_remaining = None

        conn.commit()

        return {
            "success": True,
            "message": "Membership berhasil diperpanjang",
            "data": {
                "membership_id": membership["id"],
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "new_end_date": str(new_end_date) if new_end_date else None,
                "new_visit_remaining": new_visit_remaining,
                "total_paid": grand_total,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error renewing membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "RENEW_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
