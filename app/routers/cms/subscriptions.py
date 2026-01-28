"""
Subscriptions Router - Manage Recurring Payments
"""
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["CMS - Subscriptions"])


# ============== Request Models ==============

class PauseSubscriptionRequest(BaseModel):
    pause_until: date
    reason: Optional[str] = None


class CancelSubscriptionRequest(BaseModel):
    reason: str = Field(..., min_length=1)


# ============== Member Endpoints ==============

@router.get("/my")
def get_my_subscriptions(
    status_filter: Optional[str] = Query(None, alias="status"),
    auth: dict = Depends(verify_bearer_token),
):
    """Get my subscriptions"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        where_clauses = ["s.user_id = %s"]
        params = [user_id]

        if status_filter:
            where_clauses.append("s.status = %s")
            params.append(status_filter)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT s.*, pm.type as payment_type, pm.masked_number, pm.provider
            FROM subscriptions s
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            {where_sql}
            ORDER BY s.created_at DESC
            """,
            params,
        )
        subscriptions = cursor.fetchall()

        for sub in subscriptions:
            sub["base_price"] = float(sub["base_price"]) if sub.get("base_price") else 0
            sub["discount_amount"] = float(sub["discount_amount"]) if sub.get("discount_amount") else 0
            sub["recurring_price"] = float(sub["recurring_price"]) if sub.get("recurring_price") else 0

            # Get recent invoices
            cursor.execute(
                """
                SELECT * FROM subscription_invoices
                WHERE subscription_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (sub["id"],),
            )
            sub["recent_invoices"] = cursor.fetchall()
            for inv in sub["recent_invoices"]:
                inv["amount"] = float(inv["amount"]) if inv.get("amount") else 0

        return {
            "success": True,
            "data": subscriptions,
        }

    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SUBSCRIPTIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{subscription_id}/pause")
def pause_subscription(
    subscription_id: int,
    request: PauseSubscriptionRequest,
    auth: dict = Depends(verify_bearer_token),
):
    """Pause a subscription"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get subscription
        cursor.execute(
            "SELECT * FROM subscriptions WHERE id = %s AND user_id = %s AND status = 'active'",
            (subscription_id, user_id),
        )
        subscription = cursor.fetchone()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SUBSCRIPTION_NOT_FOUND", "message": "Subscription tidak ditemukan"},
            )

        # Validate pause date
        if request.pause_until <= date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_DATE", "message": "Tanggal pause harus di masa depan"},
            )

        # Update subscription
        cursor.execute(
            """
            UPDATE subscriptions
            SET status = 'paused', paused_at = %s, paused_until = %s, pause_reason = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), request.pause_until, request.reason, datetime.now(), subscription_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": f"Subscription dibekukan sampai {request.pause_until}",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error pausing subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PAUSE_SUBSCRIPTION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{subscription_id}/resume")
def resume_subscription(subscription_id: int, auth: dict = Depends(verify_bearer_token)):
    """Resume a paused subscription"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get subscription
        cursor.execute(
            "SELECT * FROM subscriptions WHERE id = %s AND user_id = %s AND status = 'paused'",
            (subscription_id, user_id),
        )
        subscription = cursor.fetchone()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SUBSCRIPTION_NOT_FOUND", "message": "Subscription tidak ditemukan"},
            )

        # Calculate new billing date
        from datetime import timedelta
        if subscription["next_billing_date"] < date.today():
            # Set next billing to today + 1 day
            next_billing = date.today() + timedelta(days=1)
        else:
            next_billing = subscription["next_billing_date"]

        # Update subscription
        cursor.execute(
            """
            UPDATE subscriptions
            SET status = 'active', paused_at = NULL, paused_until = NULL, pause_reason = NULL,
                next_billing_date = %s, updated_at = %s
            WHERE id = %s
            """,
            (next_billing, datetime.now(), subscription_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Subscription berhasil diaktifkan kembali",
            "data": {
                "next_billing_date": str(next_billing),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error resuming subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "RESUME_SUBSCRIPTION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{subscription_id}/cancel")
def cancel_subscription(
    subscription_id: int,
    request: CancelSubscriptionRequest,
    auth: dict = Depends(verify_bearer_token),
):
    """Cancel a subscription"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get subscription
        cursor.execute(
            "SELECT * FROM subscriptions WHERE id = %s AND user_id = %s AND status IN ('active', 'paused')",
            (subscription_id, user_id),
        )
        subscription = cursor.fetchone()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SUBSCRIPTION_NOT_FOUND", "message": "Subscription tidak ditemukan"},
            )

        # Update subscription
        cursor.execute(
            """
            UPDATE subscriptions
            SET status = 'cancelled', cancelled_at = %s, cancellation_reason = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), request.reason, datetime.now(), subscription_id),
        )

        # Cancel pending invoices
        cursor.execute(
            """
            UPDATE subscription_invoices
            SET status = 'cancelled', updated_at = %s
            WHERE subscription_id = %s AND status = 'pending'
            """,
            (datetime.now(), subscription_id),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Subscription berhasil dibatalkan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error cancelling subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CANCEL_SUBSCRIPTION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== CMS Endpoints ==============

@router.get("")
def get_all_subscriptions(
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    billing_cycle: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all subscriptions (CMS)"""
    check_permission(auth, "transaction.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if user_id:
            where_clauses.append("s.user_id = %s")
            params.append(user_id)

        if status_filter:
            where_clauses.append("s.status = %s")
            params.append(status_filter)

        if billing_cycle:
            where_clauses.append("s.billing_cycle = %s")
            params.append(billing_cycle)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(f"SELECT COUNT(*) as total FROM subscriptions s{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get summary
        cursor.execute(
            f"""
            SELECT
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count,
                COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_count,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
                SUM(CASE WHEN status = 'active' THEN recurring_price ELSE 0 END) as monthly_recurring_revenue
            FROM subscriptions s
            {where_sql}
            """,
            params,
        )
        summary = cursor.fetchone()
        summary["monthly_recurring_revenue"] = float(summary["monthly_recurring_revenue"] or 0)

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT s.*, u.name as member_name, u.email as member_email,
                   pm.type as payment_type, pm.masked_number
            FROM subscriptions s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            {where_sql}
            ORDER BY s.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        subscriptions = cursor.fetchall()

        for sub in subscriptions:
            sub["base_price"] = float(sub["base_price"]) if sub.get("base_price") else 0
            sub["recurring_price"] = float(sub["recurring_price"]) if sub.get("recurring_price") else 0

        return {
            "success": True,
            "data": subscriptions,
            "summary": summary,
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
        logger.error(f"Error getting subscriptions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SUBSCRIPTIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/invoices")
def get_subscription_invoices(
    subscription_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    due_date_from: Optional[date] = Query(None),
    due_date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get subscription invoices (CMS)"""
    check_permission(auth, "transaction.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if subscription_id:
            where_clauses.append("si.subscription_id = %s")
            params.append(subscription_id)

        if status_filter:
            where_clauses.append("si.status = %s")
            params.append(status_filter)

        if due_date_from:
            where_clauses.append("si.due_date >= %s")
            params.append(due_date_from)

        if due_date_to:
            where_clauses.append("si.due_date <= %s")
            params.append(due_date_to)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(f"SELECT COUNT(*) as total FROM subscription_invoices si{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT si.*, s.item_name, s.billing_cycle,
                   u.name as member_name, u.email as member_email
            FROM subscription_invoices si
            JOIN subscriptions s ON si.subscription_id = s.id
            JOIN users u ON s.user_id = u.id
            {where_sql}
            ORDER BY si.due_date DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        invoices = cursor.fetchall()

        for inv in invoices:
            inv["amount"] = float(inv["amount"]) if inv.get("amount") else 0

        return {
            "success": True,
            "data": invoices,
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
        logger.error(f"Error getting invoices: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_INVOICES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
