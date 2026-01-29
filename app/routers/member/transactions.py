"""
Member Transactions Router - Member's transaction history
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Member - Transactions"])


# ============== Endpoints ==============

@router.get("/history")
def get_my_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get my transaction history"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Count total
        cursor.execute(
            "SELECT COUNT(*) as total FROM transactions WHERE user_id = %s",
            (auth["user_id"],),
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            """
            SELECT t.id, t.transaction_code, t.subtotal, t.discount_amount, t.tax_amount, t.grand_total,
                   t.payment_method, t.payment_status, t.paid_at, t.created_at,
                   b.name as branch_name, b.code as branch_code
            FROM transactions t
            LEFT JOIN branches b ON t.branch_id = b.id
            WHERE t.user_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (auth["user_id"], limit, offset),
        )
        transactions = cursor.fetchall()

        for t in transactions:
            t["subtotal"] = float(t["subtotal"]) if t.get("subtotal") else 0
            t["discount_amount"] = float(t["discount_amount"]) if t.get("discount_amount") else 0
            t["tax_amount"] = float(t["tax_amount"]) if t.get("tax_amount") else 0
            t["grand_total"] = float(t["grand_total"]) if t.get("grand_total") else 0

        return {
            "success": True,
            "data": transactions,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"Error getting transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TRANSACTIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{transaction_id}")
def get_transaction_detail(transaction_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get transaction detail"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT t.*, b.name as branch_name, b.code as branch_code
            FROM transactions t
            LEFT JOIN branches b ON t.branch_id = b.id
            WHERE t.id = %s AND t.user_id = %s
            """,
            (transaction_id, auth["user_id"]),
        )
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRANSACTION_NOT_FOUND", "message": "Transaksi tidak ditemukan"},
            )

        # Format decimals
        for key in ["subtotal", "discount_amount", "subtotal_after_discount", "tax_amount", "service_charge", "grand_total", "paid_amount"]:
            if transaction.get(key):
                transaction[key] = float(transaction[key])

        # Get items
        cursor.execute(
            """
            SELECT item_type, item_id, item_name, item_description, quantity, unit_price,
                   discount_type, discount_value, discount_amount, subtotal
            FROM transaction_items
            WHERE transaction_id = %s
            """,
            (transaction_id,),
        )
        items = cursor.fetchall()

        for item in items:
            item["unit_price"] = float(item["unit_price"]) if item.get("unit_price") else 0
            item["discount_amount"] = float(item["discount_amount"]) if item.get("discount_amount") else 0
            item["subtotal"] = float(item["subtotal"]) if item.get("subtotal") else 0

        transaction["items"] = items

        return {
            "success": True,
            "data": transaction,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TRANSACTION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
