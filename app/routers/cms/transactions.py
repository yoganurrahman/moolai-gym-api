"""
Transactions Router - Checkout, History
Hybrid transaction system for all item types
"""
import logging
import uuid
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, verify_pin_token, check_permission, get_branch_id, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["CMS - Transactions"])


# ============== Request/Response Models ==============

class TransactionItem(BaseModel):
    item_type: str = Field(..., pattern=r"^(membership|class_pass|pt_package|product|rental|service)$")
    item_id: int
    quantity: int = Field(1, ge=1)
    discount_type: Optional[str] = Field(None, pattern=r"^(percentage|fixed)$")
    discount_value: Optional[float] = Field(None, ge=0)


class CheckoutRequest(BaseModel):
    items: List[TransactionItem]
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet|other)$")
    customer_name: Optional[str] = None  # For walk-in customer
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    discount_type: Optional[str] = Field(None, pattern=r"^(percentage|fixed)$")
    discount_value: Optional[float] = Field(None, ge=0)
    voucher_code: Optional[str] = None
    notes: Optional[str] = None


class RefundRequest(BaseModel):
    reason: str = Field(..., min_length=1)


# ============== Helper Functions ==============

def generate_transaction_code(branch_code: str = ""):
    prefix = f"TRX-{branch_code}-" if branch_code else "TRX-"
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


def get_item_details(cursor, item_type: str, item_id: int, branch_id: int = None):
    """Get item details based on type"""
    if item_type == "membership":
        cursor.execute(
            "SELECT id, name, price, duration_days, visit_quota FROM membership_packages WHERE id = %s AND is_active = 1",
            (item_id,),
        )
    elif item_type == "class_pass":
        cursor.execute(
            "SELECT id, name, price, class_count FROM class_packages WHERE id = %s AND is_active = 1",
            (item_id,),
        )
    elif item_type == "pt_package":
        cursor.execute(
            "SELECT id, name, price, session_count FROM pt_packages WHERE id = %s AND is_active = 1",
            (item_id,),
        )
    elif item_type in ("product", "rental"):
        if branch_id:
            cursor.execute(
                """
                SELECT p.id, p.name, p.price, bps.stock, p.is_rental
                FROM products p
                LEFT JOIN branch_product_stock bps ON bps.product_id = p.id AND bps.branch_id = %s
                WHERE p.id = %s AND p.is_active = 1
                """,
                (branch_id, item_id),
            )
        else:
            cursor.execute(
                "SELECT id, name, price, stock, is_rental FROM products WHERE id = %s AND is_active = 1",
                (item_id,),
            )
    else:
        return None

    return cursor.fetchone()


# ============== Endpoints ==============

@router.post("/checkout")
def checkout(
    request: CheckoutRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """
    Create a new transaction with multiple items.
    Supports membership, class pass, PT package, products, rentals.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth.get("user_id")

        # Get branch code
        cursor.execute("SELECT code FROM branches WHERE id = %s", (branch_id,))
        branch_row = cursor.fetchone()
        if not branch_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BRANCH_NOT_FOUND", "message": "Branch tidak ditemukan"},
            )
        branch_code = branch_row["code"]

        # Get tax settings
        cursor.execute(
            "SELECT `key`, `value` FROM settings WHERE `key` IN ('tax_enabled', 'tax_percentage', 'service_charge_enabled', 'service_charge_percentage')"
        )
        settings = {row["key"]: row["value"] for row in cursor.fetchall()}
        tax_enabled = settings.get("tax_enabled", "false") == "true"
        tax_percentage = float(settings.get("tax_percentage", "0"))
        service_charge_enabled = settings.get("service_charge_enabled", "false") == "true"
        service_charge_percentage = float(settings.get("service_charge_percentage", "0"))

        # Process items
        transaction_items = []
        subtotal = 0

        for item in request.items:
            item_details = get_item_details(cursor, item.item_type, item.item_id, branch_id=branch_id)

            if not item_details:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error_code": "ITEM_NOT_FOUND",
                        "message": f"Item {item.item_type} dengan ID {item.item_id} tidak ditemukan",
                    },
                )

            # Check stock for products
            if item.item_type == "product" and not item_details.get("is_rental"):
                current_stock = item_details.get("stock") or 0
                if current_stock < item.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INSUFFICIENT_STOCK",
                            "message": f"Stok {item_details['name']} tidak mencukupi",
                        },
                    )

            # Calculate item pricing
            unit_price = float(item_details["price"])
            item_total = unit_price * item.quantity

            # Apply item discount
            item_discount_amount = 0
            if item.discount_type and item.discount_value:
                if item.discount_type == "percentage":
                    item_discount_amount = item_total * (item.discount_value / 100)
                else:
                    item_discount_amount = min(item.discount_value, item_total)

            item_subtotal = item_total - item_discount_amount
            subtotal += item_subtotal

            transaction_items.append({
                "item_type": item.item_type,
                "item_id": item.item_id,
                "item_name": item_details["name"],
                "quantity": item.quantity,
                "unit_price": unit_price,
                "discount_type": item.discount_type,
                "discount_value": item.discount_value or 0,
                "discount_amount": item_discount_amount,
                "subtotal": item_subtotal,
                "details": item_details,
            })

        # Apply transaction-level discount
        transaction_discount_amount = 0
        if request.discount_type and request.discount_value:
            if request.discount_type == "percentage":
                transaction_discount_amount = subtotal * (request.discount_value / 100)
            else:
                transaction_discount_amount = min(request.discount_value, subtotal)

        subtotal_after_discount = subtotal - transaction_discount_amount

        # Apply voucher if provided
        voucher_discount = 0
        if request.voucher_code:
            cursor.execute(
                """
                SELECT * FROM vouchers
                WHERE code = %s AND is_active = 1
                AND start_date <= NOW() AND end_date >= NOW()
                AND (usage_limit IS NULL OR usage_count < usage_limit)
                """,
                (request.voucher_code,),
            )
            voucher = cursor.fetchone()

            if voucher:
                if voucher["voucher_type"] == "percentage":
                    voucher_discount = subtotal_after_discount * (float(voucher["discount_value"]) / 100)
                    if voucher["max_discount"]:
                        voucher_discount = min(voucher_discount, float(voucher["max_discount"]))
                else:
                    voucher_discount = min(float(voucher["discount_value"]), subtotal_after_discount)

                subtotal_after_discount -= voucher_discount

                # Update voucher usage
                cursor.execute(
                    "UPDATE vouchers SET usage_count = usage_count + 1 WHERE id = %s",
                    (voucher["id"],),
                )

        # Calculate tax and service charge
        tax_amount = subtotal_after_discount * (tax_percentage / 100) if tax_enabled else 0
        service_charge_amount = subtotal_after_discount * (service_charge_percentage / 100) if service_charge_enabled else 0

        grand_total = subtotal_after_discount + tax_amount + service_charge_amount

        # Create transaction
        transaction_code = generate_transaction_code(branch_code)
        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, branch_id, user_id, staff_id, customer_name, customer_phone, customer_email,
             subtotal, discount_type, discount_value, discount_amount, subtotal_after_discount,
             tax_percentage, tax_amount, service_charge_percentage, service_charge_amount,
             grand_total, payment_method, payment_status, paid_amount, paid_at, voucher_code, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_code,
                branch_id,
                user_id if user_id and not request.customer_name else None,  # Member purchase
                auth["user_id"] if request.customer_name else None,  # Staff for walk-in
                request.customer_name,
                request.customer_phone,
                request.customer_email,
                subtotal,
                request.discount_type,
                request.discount_value or 0,
                transaction_discount_amount + voucher_discount,
                subtotal_after_discount,
                tax_percentage if tax_enabled else 0,
                tax_amount,
                service_charge_percentage if service_charge_enabled else 0,
                service_charge_amount,
                grand_total,
                request.payment_method,
                "paid",
                grand_total,
                datetime.now(),
                request.voucher_code,
                request.notes,
                datetime.now(),
            ),
        )
        transaction_id = cursor.lastrowid

        # Create transaction items and process each
        for item in transaction_items:
            import json
            metadata = {"details": {k: v for k, v in item["details"].items() if k not in ["price"]}}

            cursor.execute(
                """
                INSERT INTO transaction_items
                (transaction_id, item_type, item_id, item_name, quantity, unit_price,
                 discount_type, discount_value, discount_amount, subtotal, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    item["item_type"],
                    item["item_id"],
                    item["item_name"],
                    item["quantity"],
                    item["unit_price"],
                    item["discount_type"],
                    item["discount_value"],
                    item["discount_amount"],
                    item["subtotal"],
                    json.dumps(metadata),
                    datetime.now(),
                ),
            )

            # Process based on item type
            target_user_id = user_id if user_id and not request.customer_name else None

            if item["item_type"] == "product" and not item["details"].get("is_rental"):
                # Deduct stock from branch_product_stock
                cursor.execute(
                    "UPDATE branch_product_stock SET stock = stock - %s WHERE branch_id = %s AND product_id = %s AND stock >= %s",
                    (item["quantity"], branch_id, item["item_id"], item["quantity"]),
                )
                if cursor.rowcount == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INSUFFICIENT_STOCK",
                            "message": f"Stok {item['item_name']} tidak mencukupi di cabang ini",
                        },
                    )

                # Log stock change
                cursor.execute(
                    """
                    INSERT INTO product_stock_logs
                    (product_id, branch_id, type, quantity, stock_before, stock_after, reference_type, reference_id, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item["item_id"],
                        branch_id,
                        "out",
                        item["quantity"],
                        item["details"]["stock"],
                        item["details"]["stock"] - item["quantity"],
                        "transaction",
                        transaction_id,
                        auth["user_id"],
                        datetime.now(),
                    ),
                )

        conn.commit()

        return {
            "success": True,
            "message": "Transaksi berhasil",
            "data": {
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "subtotal": subtotal,
                "discount_amount": transaction_discount_amount + voucher_discount,
                "tax_amount": tax_amount,
                "service_charge_amount": service_charge_amount,
                "grand_total": grand_total,
                "items": [
                    {
                        "name": i["item_name"],
                        "quantity": i["quantity"],
                        "unit_price": i["unit_price"],
                        "subtotal": i["subtotal"],
                    }
                    for i in transaction_items
                ],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during checkout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKOUT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-history")
def get_my_transaction_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get transaction history for logged-in member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Count total
        cursor.execute(
            "SELECT COUNT(*) as total FROM transactions WHERE user_id = %s",
            (auth["user_id"],),
        )
        total = cursor.fetchone()["total"]

        # Get transactions
        offset = (page - 1) * limit
        cursor.execute(
            """
            SELECT * FROM transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (auth["user_id"], limit, offset),
        )
        transactions = cursor.fetchall()

        # Get items for each transaction
        for trx in transactions:
            cursor.execute(
                "SELECT * FROM transaction_items WHERE transaction_id = %s",
                (trx["id"],),
            )
            trx["items"] = cursor.fetchall()

            # Format decimals
            for key in ["subtotal", "discount_amount", "subtotal_after_discount", "tax_amount", "service_charge_amount", "grand_total", "paid_amount"]:
                if trx.get(key):
                    trx[key] = float(trx[key])

            for item in trx["items"]:
                for key in ["unit_price", "discount_value", "discount_amount", "subtotal"]:
                    if item.get(key):
                        item[key] = float(item[key])

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
        logger.error(f"Error getting transaction history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_HISTORY_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{transaction_id}")
def get_transaction(transaction_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get transaction detail"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get transaction
        cursor.execute(
            """
            SELECT t.*, b.name as branch_name, b.code as branch_code
            FROM transactions t
            LEFT JOIN branches b ON t.branch_id = b.id
            WHERE t.id = %s
            """,
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRANSACTION_NOT_FOUND", "message": "Transaksi tidak ditemukan"},
            )

        # Check permission - member can only view their own
        if transaction["user_id"] != auth["user_id"]:
            check_permission(auth, "transaction.view")

        # Get items
        cursor.execute(
            "SELECT * FROM transaction_items WHERE transaction_id = %s",
            (transaction_id,),
        )
        transaction["items"] = cursor.fetchall()

        # Get member/customer info
        if transaction["user_id"]:
            cursor.execute(
                "SELECT id, name, email, phone FROM users WHERE id = %s",
                (transaction["user_id"],),
            )
            transaction["member"] = cursor.fetchone()

        # Format decimals
        for key in ["subtotal", "discount_amount", "subtotal_after_discount", "tax_amount", "service_charge_amount", "grand_total", "paid_amount"]:
            if transaction.get(key):
                transaction[key] = float(transaction[key])

        for item in transaction["items"]:
            for key in ["unit_price", "discount_value", "discount_amount", "subtotal"]:
                if item.get(key):
                    item[key] = float(item[key])

        return {
            "success": True,
            "data": transaction,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TRANSACTION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("")
def get_all_transactions(
    user_id: Optional[int] = Query(None),
    payment_status: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get all transactions (CMS)"""
    check_permission(auth, "transaction.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if branch_id:
            where_clauses.append("t.branch_id = %s")
            params.append(branch_id)

        if user_id:
            where_clauses.append("t.user_id = %s")
            params.append(user_id)

        if payment_status:
            where_clauses.append("t.payment_status = %s")
            params.append(payment_status)

        if payment_method:
            where_clauses.append("t.payment_method = %s")
            params.append(payment_method)

        if date_from:
            where_clauses.append("DATE(t.created_at) >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("DATE(t.created_at) <= %s")
            params.append(date_to)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(f"SELECT COUNT(*) as total FROM transactions t{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get summary
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as total_transactions,
                SUM(grand_total) as total_revenue,
                SUM(CASE WHEN payment_status = 'paid' THEN grand_total ELSE 0 END) as paid_amount,
                SUM(CASE WHEN payment_status = 'refunded' THEN grand_total ELSE 0 END) as refunded_amount
            FROM transactions t
            {where_sql}
            """,
            params,
        )
        summary = cursor.fetchone()
        for key in ["total_revenue", "paid_amount", "refunded_amount"]:
            if summary.get(key):
                summary[key] = float(summary[key])

        # Get transactions
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT t.*, u.name as member_name, u.email as member_email,
                   s.name as staff_name,
                   b.name as branch_name, b.code as branch_code
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN users s ON t.staff_id = s.id
            LEFT JOIN branches b ON t.branch_id = b.id
            {where_sql}
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        transactions = cursor.fetchall()

        # Format decimals
        for trx in transactions:
            for key in ["subtotal", "discount_amount", "subtotal_after_discount", "tax_amount", "service_charge_amount", "grand_total", "paid_amount"]:
                if trx.get(key):
                    trx[key] = float(trx[key])

        return {
            "success": True,
            "data": transactions,
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
        logger.error(f"Error getting transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TRANSACTIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{transaction_id}/refund")
def refund_transaction(
    transaction_id: int,
    request: RefundRequest,
    auth: dict = Depends(verify_bearer_token),
    pin_auth: dict = Depends(verify_pin_token),
):
    """Refund a transaction (requires PIN verification)"""
    check_permission(auth, "transaction.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get transaction
        cursor.execute(
            "SELECT * FROM transactions WHERE id = %s AND payment_status = 'paid'",
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRANSACTION_NOT_FOUND", "message": "Transaksi tidak ditemukan atau sudah di-refund"},
            )

        # Update status
        cursor.execute(
            """
            UPDATE transactions
            SET payment_status = 'refunded', notes = CONCAT(IFNULL(notes, ''), %s), updated_at = %s
            WHERE id = %s
            """,
            (f"\n[REFUND] {request.reason}", datetime.now(), transaction_id),
        )

        # Restore stock for products to branch_product_stock
        cursor.execute(
            "SELECT * FROM transaction_items WHERE transaction_id = %s AND item_type = 'product'",
            (transaction_id,),
        )
        product_items = cursor.fetchall()

        for item in product_items:
            # Get current branch stock before restoring
            cursor.execute(
                "SELECT stock FROM branch_product_stock WHERE branch_id = %s AND product_id = %s",
                (transaction["branch_id"], item["item_id"]),
            )
            branch_row = cursor.fetchone()
            current_stock = branch_row["stock"] if branch_row else 0
            new_stock = current_stock + item["quantity"]

            if branch_row:
                cursor.execute(
                    "UPDATE branch_product_stock SET stock = %s WHERE branch_id = %s AND product_id = %s",
                    (new_stock, transaction["branch_id"], item["item_id"]),
                )
            else:
                cursor.execute(
                    "INSERT INTO branch_product_stock (branch_id, product_id, stock, min_stock) VALUES (%s, %s, %s, 0)",
                    (transaction["branch_id"], item["item_id"], new_stock),
                )

            # Log stock change
            cursor.execute(
                """
                INSERT INTO product_stock_logs
                (product_id, branch_id, type, quantity, stock_before, stock_after, reference_type, reference_id, notes, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item["item_id"],
                    transaction["branch_id"],
                    "in",
                    item["quantity"],
                    current_stock,
                    new_stock,
                    "transaction",
                    transaction_id,
                    f"Refund: {request.reason}",
                    auth["user_id"],
                    datetime.now(),
                ),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Transaksi berhasil di-refund",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error refunding transaction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REFUND_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
