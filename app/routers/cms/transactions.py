"""
Transactions Router - Checkout, History, Approve/Reject Payment
Hybrid transaction system for all item types
"""
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, verify_pin_token, check_permission, get_branch_id, require_branch_id
from app.utils.helpers import verify_password

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
    user_id: Optional[int] = None  # Member ID (CMS staff checkout for registered member)
    customer_name: Optional[str] = None  # For walk-in customer
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    discount_type: Optional[str] = Field(None, pattern=r"^(percentage|fixed)$")
    discount_value: Optional[float] = Field(None, ge=0)
    promo_ids: Optional[List[int]] = None
    voucher_codes: Optional[List[str]] = None
    notes: Optional[str] = None


class RefundRequest(BaseModel):
    pin: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


# ============== Helper Functions ==============

MAX_PIN_ATTEMPTS = 3
PIN_LOCKOUT_DURATION_MINUTES = 15


def verify_pin_inline(cursor, conn, user_id: int, pin: str):
    """Verify PIN inline for sensitive operations. Raises HTTPException on failure."""
    cursor.execute(
        "SELECT pin, has_pin, failed_pin_attempts, pin_locked_until FROM users WHERE id = %s",
        (user_id,),
    )
    user = cursor.fetchone()
    if not user or not user["has_pin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "PIN_NOT_SET", "message": "PIN belum diatur"},
        )

    if user["pin_locked_until"] and datetime.now() < user["pin_locked_until"]:
        remaining = int((user["pin_locked_until"] - datetime.now()).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"error_code": "PIN_LOCKED", "message": f"PIN terkunci. Coba lagi dalam {remaining} menit."},
        )

    if not verify_password(pin, user["pin"]):
        failed = (user["failed_pin_attempts"] or 0) + 1
        if failed >= MAX_PIN_ATTEMPTS:
            locked_until = datetime.now() + timedelta(minutes=PIN_LOCKOUT_DURATION_MINUTES)
            cursor.execute(
                "UPDATE users SET failed_pin_attempts = %s, pin_locked_until = %s WHERE id = %s",
                (failed, locked_until, user_id),
            )
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={"error_code": "PIN_LOCKED", "message": f"Terlalu banyak percobaan. PIN terkunci selama {PIN_LOCKOUT_DURATION_MINUTES} menit."},
            )
        cursor.execute("UPDATE users SET failed_pin_attempts = %s WHERE id = %s", (failed, user_id))
        conn.commit()
        remaining = MAX_PIN_ATTEMPTS - failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_PIN", "message": f"PIN salah. Sisa percobaan: {remaining}"},
        )

    # Reset failed attempts on success
    cursor.execute("UPDATE users SET failed_pin_attempts = 0, pin_locked_until = NULL WHERE id = %s", (user_id,))


def generate_transaction_code(branch_code: str = ""):
    prefix = f"TRX-{branch_code}-" if branch_code else "TRX-"
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


def get_item_details(cursor, item_type: str, item_id: int, branch_id: int = None):
    """Get item details based on type"""
    if item_type == "membership":
        cursor.execute(
            "SELECT id, name, price, package_type, duration_days, visit_quota, class_quota FROM membership_packages WHERE id = %s AND is_active = 1",
            (item_id,),
        )
    elif item_type == "class_pass":
        cursor.execute(
            "SELECT id, name, price, class_count, valid_days FROM class_packages WHERE id = %s AND is_active = 1",
            (item_id,),
        )
    elif item_type == "pt_package":
        cursor.execute(
            "SELECT id, name, price, session_count, valid_days, trainer_id FROM pt_packages WHERE id = %s AND is_active = 1",
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


# Mapping item_type di cart ke applicable_to di promo/voucher
ITEM_TYPE_TO_APPLICABLE = {
    "product": "product",
    "rental": "product",
    "membership": "membership",
    "pt_package": "pt",
    "class_pass": "class",
}


def filter_applicable_items(transaction_items, applicable_to, applicable_items_json):
    """Filter transaction items yang sesuai dengan applicable_to dan applicable_items.
    Returns list of matching items."""
    import json

    if applicable_to == "all" and not applicable_items_json:
        return transaction_items

    matched = []
    applicable_item_ids = None
    if applicable_items_json:
        try:
            applicable_item_ids = json.loads(applicable_items_json) if isinstance(applicable_items_json, str) else applicable_items_json
        except (json.JSONDecodeError, TypeError):
            applicable_item_ids = None

    for item in transaction_items:
        item_applicable = ITEM_TYPE_TO_APPLICABLE.get(item["item_type"], item["item_type"])

        # Check applicable_to
        if applicable_to != "all" and item_applicable != applicable_to:
            continue

        # Check applicable_items (specific IDs)
        if applicable_item_ids and item["item_id"] not in applicable_item_ids:
            continue

        matched.append(item)

    return matched


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
        # Determine buyer and staff
        # 1. request.user_id → CMS staff checkout for registered member
        # 2. request.customer_name → walk-in customer
        # 3. neither → self-purchase (auth user is the buyer)
        if request.user_id:
            buyer_user_id = request.user_id
            staff_id = auth.get("user_id")
        elif request.customer_name:
            buyer_user_id = None
            staff_id = auth.get("user_id")
        else:
            buyer_user_id = auth.get("user_id")
            staff_id = None

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

        # Apply promos (multiple stacking)
        all_promo_ids = list(request.promo_ids) if request.promo_ids else []
        promo_discount = 0
        applied_promo_ids = []
        for pid in all_promo_ids:
            cursor.execute(
                """
                SELECT * FROM promos
                WHERE id = %s AND is_active = 1
                AND start_date <= NOW() AND end_date >= NOW()
                AND (usage_limit IS NULL OR usage_count < usage_limit)
                """,
                (pid,),
            )
            promo = cursor.fetchone()

            if promo:
                per_user_limit = promo.get("per_user_limit") or 0
                if per_user_limit > 0 and buyer_user_id:
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM discount_usages WHERE discount_type = 'promo' AND discount_id = %s AND user_id = %s",
                        (promo["id"], buyer_user_id),
                    )
                    if cursor.fetchone()["cnt"] >= per_user_limit:
                        promo = None

            if promo:
                promo_applicable = promo.get("applicable_to") or "all"
                matched_items = filter_applicable_items(
                    transaction_items, promo_applicable, promo.get("applicable_items")
                )

                if not matched_items and promo_applicable != "all":
                    continue

                if promo_applicable != "all" or promo.get("applicable_items"):
                    applicable_subtotal = sum(i["subtotal"] for i in matched_items)
                else:
                    applicable_subtotal = subtotal_after_discount

                min_purchase = float(promo.get("min_purchase") or 0)
                if min_purchase > 0 and applicable_subtotal < min_purchase:
                    continue

                this_discount = 0
                if promo["promo_type"] == "percentage":
                    this_discount = applicable_subtotal * (float(promo["discount_value"]) / 100)
                    if promo.get("max_discount"):
                        this_discount = min(this_discount, float(promo["max_discount"]))
                elif promo["promo_type"] == "fixed":
                    this_discount = min(float(promo["discount_value"]), applicable_subtotal)
                elif promo["promo_type"] == "free_item":
                    cheapest_price = min(i["unit_price"] for i in matched_items) if matched_items else 0
                    this_discount = min(cheapest_price, applicable_subtotal)

                this_discount = min(this_discount, subtotal_after_discount)
                promo_discount += this_discount
                subtotal_after_discount -= this_discount
                applied_promo_ids.append(promo["id"])

        # Apply vouchers (multiple stacking)
        all_voucher_codes = list(request.voucher_codes) if request.voucher_codes else []
        voucher_discount = 0
        applied_voucher_codes = []
        for vcode in all_voucher_codes:
            cursor.execute(
                """
                SELECT * FROM vouchers
                WHERE code = %s AND is_active = 1
                AND start_date <= NOW() AND end_date >= NOW()
                AND (usage_limit IS NULL OR usage_count < usage_limit)
                """,
                (vcode,),
            )
            voucher = cursor.fetchone()

            if voucher:
                if voucher.get("is_single_use") and buyer_user_id:
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM discount_usages WHERE discount_type = 'voucher' AND discount_id = %s AND user_id = %s",
                        (voucher["id"], buyer_user_id),
                    )
                    if cursor.fetchone()["cnt"] > 0:
                        voucher = None

            if not voucher:
                continue

            voucher_applicable = voucher.get("applicable_to") or "all"
            matched_items = filter_applicable_items(
                transaction_items, voucher_applicable, voucher.get("applicable_items")
            )

            if not matched_items and voucher_applicable != "all":
                continue

            if voucher_applicable != "all" or voucher.get("applicable_items"):
                applicable_subtotal = sum(i["subtotal"] for i in matched_items)
            else:
                applicable_subtotal = subtotal_after_discount

            this_discount = 0
            if voucher["voucher_type"] == "percentage":
                this_discount = applicable_subtotal * (float(voucher["discount_value"]) / 100)
                if voucher.get("max_discount"):
                    this_discount = min(this_discount, float(voucher["max_discount"]))
            elif voucher["voucher_type"] == "free_item":
                cheapest_price = min(i["unit_price"] for i in matched_items) if matched_items else 0
                this_discount = min(cheapest_price, applicable_subtotal)
            else:
                this_discount = min(float(voucher["discount_value"]), applicable_subtotal)

            this_discount = min(this_discount, subtotal_after_discount)
            voucher_discount += this_discount
            subtotal_after_discount -= this_discount
            applied_voucher_codes.append(voucher["code"])

        # Calculate tax and service charge
        tax_amount = subtotal_after_discount * (tax_percentage / 100) if tax_enabled else 0
        service_charge_amount = subtotal_after_discount * (service_charge_percentage / 100) if service_charge_enabled else 0

        grand_total = subtotal_after_discount + tax_amount + service_charge_amount

        # Create transaction
        transaction_code = generate_transaction_code(branch_code)
        promo_ids_json = json.dumps(applied_promo_ids) if applied_promo_ids else None
        voucher_codes_json = json.dumps(applied_voucher_codes) if applied_voucher_codes else None

        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, branch_id, user_id, staff_id, customer_name, customer_phone, customer_email,
             subtotal, discount_type, discount_value, discount_amount, subtotal_after_discount,
             tax_percentage, tax_amount, service_charge_percentage, service_charge_amount,
             grand_total, payment_method, payment_status, paid_amount, paid_at,
             promo_ids, promo_discount, voucher_codes, voucher_discount, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_code,
                branch_id,
                buyer_user_id,
                staff_id,
                request.customer_name,
                request.customer_phone,
                request.customer_email,
                subtotal,
                request.discount_type,
                request.discount_value or 0,
                transaction_discount_amount + promo_discount + voucher_discount,
                subtotal_after_discount,
                tax_percentage if tax_enabled else 0,
                tax_amount,
                service_charge_percentage if service_charge_enabled else 0,
                service_charge_amount,
                grand_total,
                request.payment_method,
                "pending",
                0,
                None,
                promo_ids_json,
                promo_discount,
                voucher_codes_json,
                voucher_discount,
                request.notes,
                datetime.now(),
            ),
        )
        transaction_id = cursor.lastrowid

        # Create transaction items and process each
        for item in transaction_items:
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

        # NOTE: Item processing (stock deduction, membership activation, etc.)
        # and discount usage logging are handled in approve-payment endpoint.
        # Checkout only creates the pending transaction + items.

        conn.commit()

        return {
            "success": True,
            "message": "Transaksi berhasil dibuat, menunggu persetujuan",
            "data": {
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "payment_status": "pending",
                "subtotal": subtotal,
                "discount_amount": transaction_discount_amount + promo_discount + voucher_discount,
                "promo_discount": promo_discount,
                "voucher_discount": voucher_discount,
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
            SELECT t.*, b.name as branch_name, b.code as branch_code,
                   approver.name as approved_by_name
            FROM transactions t
            LEFT JOIN branches b ON t.branch_id = b.id
            LEFT JOIN users approver ON t.approved_by = approver.id
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
        for key in ["subtotal", "discount_amount", "promo_discount", "voucher_discount", "subtotal_after_discount", "tax_amount", "service_charge_amount", "grand_total", "paid_amount"]:
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
):
    """Refund a transaction (requires PIN verification)"""
    check_permission(auth, "transaction.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verify PIN inline
        verify_pin_inline(cursor, conn, auth["user_id"], request.pin)

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

        # Cancel memberships created by this transaction
        cursor.execute(
            """
            UPDATE member_memberships
            SET status = 'cancelled', cancelled_at = %s, cancellation_reason = %s, updated_at = %s
            WHERE transaction_id = %s AND status = 'active'
            """,
            (datetime.now(), f"Refund: {request.reason}", datetime.now(), transaction_id),
        )

        # Cancel class passes created by this transaction
        cursor.execute(
            """
            UPDATE member_class_passes
            SET status = 'expired', updated_at = %s
            WHERE transaction_id = %s AND status = 'active'
            """,
            (datetime.now(), transaction_id),
        )

        # Cancel PT sessions created by this transaction
        cursor.execute(
            """
            UPDATE member_pt_sessions
            SET status = 'expired', updated_at = %s
            WHERE transaction_id = %s AND status = 'active'
            """,
            (datetime.now(), transaction_id),
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


# ============== Approve / Reject Payment ==============

class ApproveRejectRequest(BaseModel):
    pin: Optional[str] = None
    reason: Optional[str] = None


@router.post("/{transaction_id}/approve-payment")
def approve_payment(
    transaction_id: int,
    request: ApproveRejectRequest = ApproveRejectRequest(),
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Approve pending payment — activate items, deduct stock, mark as paid"""
    check_permission(auth, "transaction.update")

    if not request.pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "PIN_REQUIRED", "message": "PIN diperlukan untuk menyetujui pembayaran"},
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verify PIN inline
        verify_pin_inline(cursor, conn, auth["user_id"], request.pin)

        # Get transaction
        cursor.execute(
            "SELECT * FROM transactions WHERE id = %s AND payment_status = 'pending'",
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRANSACTION_NOT_FOUND", "message": "Transaksi pending tidak ditemukan"},
            )

        # Get transaction items
        cursor.execute(
            "SELECT * FROM transaction_items WHERE transaction_id = %s",
            (transaction_id,),
        )
        items = cursor.fetchall()

        target_user_id = transaction["user_id"]

        for item in items:
            metadata = json.loads(item["metadata"]) if item.get("metadata") else {}
            details = metadata.get("details", {})

            if item["item_type"] == "product":
                # Deduct stock from branch_product_stock
                cursor.execute(
                    "SELECT stock FROM branch_product_stock WHERE branch_id = %s AND product_id = %s",
                    (branch_id, item["item_id"]),
                )
                stock_row = cursor.fetchone()
                current_stock = stock_row["stock"] if stock_row else 0

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
                        current_stock,
                        current_stock - item["quantity"],
                        "transaction",
                        transaction_id,
                        auth["user_id"],
                        datetime.now(),
                    ),
                )

            elif item["item_type"] == "membership" and target_user_id:
                start_date_m = date.today()
                end_date_m = None
                visit_remaining = None

                if details.get("visit_quota"):
                    visit_remaining = details["visit_quota"]
                elif details.get("duration_days"):
                    end_date_m = start_date_m + timedelta(days=details["duration_days"])

                membership_code = f"MBR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                cursor.execute(
                    """
                    INSERT INTO member_memberships
                    (user_id, package_id, transaction_id, membership_code, start_date, end_date,
                     visit_remaining, class_remaining, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        target_user_id,
                        item["item_id"],
                        transaction_id,
                        membership_code,
                        start_date_m,
                        end_date_m,
                        visit_remaining,
                        details.get("class_quota"),
                        "active",
                        datetime.now(),
                    ),
                )

            elif item["item_type"] == "class_pass" and target_user_id:
                start_date_c = date.today()
                expire_date_c = start_date_c + timedelta(days=details.get("valid_days", 30))

                cursor.execute(
                    """
                    INSERT INTO member_class_passes
                    (user_id, class_package_id, transaction_id, total_classes, used_classes,
                     start_date, expire_date, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        target_user_id,
                        item["item_id"],
                        transaction_id,
                        details.get("class_count", 1),
                        0,
                        start_date_c,
                        expire_date_c,
                        "active",
                        datetime.now(),
                    ),
                )

            elif item["item_type"] == "pt_package" and target_user_id:
                start_date_p = date.today()
                expire_date_p = start_date_p + timedelta(days=details.get("valid_days", 90))
                trainer_id = metadata.get("trainer_id") or details.get("trainer_id")

                cursor.execute(
                    """
                    INSERT INTO member_pt_sessions
                    (user_id, pt_package_id, transaction_id, trainer_id, total_sessions, used_sessions,
                     start_date, expire_date, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        target_user_id,
                        item["item_id"],
                        transaction_id,
                        trainer_id,
                        details.get("session_count", 1),
                        0,
                        start_date_p,
                        expire_date_p,
                        "active",
                        datetime.now(),
                    ),
                )

        # Update promo usage_count (multiple via promo_ids JSON)
        promo_ids_to_log = []
        if transaction.get("promo_ids"):
            try:
                promo_ids_to_log = json.loads(transaction["promo_ids"])
            except (json.JSONDecodeError, TypeError):
                pass

        promo_discount_total = float(transaction.get("promo_discount") or 0)
        if promo_ids_to_log and promo_discount_total > 0:
            per_promo_discount = promo_discount_total / len(promo_ids_to_log)
            for pid in promo_ids_to_log:
                cursor.execute(
                    "UPDATE promos SET usage_count = usage_count + 1 WHERE id = %s",
                    (pid,),
                )
                cursor.execute(
                    """
                    INSERT INTO discount_usages (discount_type, discount_id, user_id, transaction_id, discount_amount, used_at)
                    VALUES ('promo', %s, %s, %s, %s, %s)
                    """,
                    (pid, target_user_id, transaction_id, per_promo_discount, datetime.now()),
                )

        # Update voucher usage_count (multiple via voucher_codes JSON)
        voucher_codes_to_log = []
        if transaction.get("voucher_codes"):
            try:
                voucher_codes_to_log = json.loads(transaction["voucher_codes"])
            except (json.JSONDecodeError, TypeError):
                pass

        voucher_discount_total = float(transaction.get("voucher_discount") or 0)
        if voucher_codes_to_log and voucher_discount_total > 0:
            per_voucher_discount = voucher_discount_total / len(voucher_codes_to_log)
            for vcode in voucher_codes_to_log:
                cursor.execute(
                    "SELECT id FROM vouchers WHERE code = %s",
                    (vcode,),
                )
                voucher_row = cursor.fetchone()
                if voucher_row:
                    cursor.execute(
                        "UPDATE vouchers SET usage_count = usage_count + 1 WHERE id = %s",
                        (voucher_row["id"],),
                    )
                    cursor.execute(
                        """
                        INSERT INTO discount_usages (discount_type, discount_id, user_id, transaction_id, discount_amount, used_at)
                        VALUES ('voucher', %s, %s, %s, %s, %s)
                        """,
                        (voucher_row["id"], target_user_id, transaction_id, per_voucher_discount, datetime.now()),
                    )

        # Mark transaction as paid
        now = datetime.now()
        cursor.execute(
            """
            UPDATE transactions
            SET payment_status = 'paid', paid_amount = grand_total, paid_at = %s,
                approved_by = %s, approved_at = %s, updated_at = %s,
                notes = CONCAT(IFNULL(notes, ''), %s)
            WHERE id = %s
            """,
            (
                now, auth["user_id"], now, now,
                f"\n[APPROVED] by staff #{auth['user_id']}" + (f" - {request.reason}" if request.reason else ""),
                transaction_id,
            ),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Pembayaran berhasil disetujui, item telah diaktifkan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error approving payment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "APPROVE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{transaction_id}/reject-payment")
def reject_payment(
    transaction_id: int,
    request: ApproveRejectRequest = ApproveRejectRequest(),
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Reject pending payment — mark as failed"""
    check_permission(auth, "transaction.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id, payment_status FROM transactions WHERE id = %s AND payment_status = 'pending'",
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRANSACTION_NOT_FOUND", "message": "Transaksi pending tidak ditemukan"},
            )

        reason_text = request.reason or "Pembayaran ditolak"
        cursor.execute(
            """
            UPDATE transactions
            SET payment_status = 'failed', updated_at = %s,
                notes = CONCAT(IFNULL(notes, ''), %s)
            WHERE id = %s
            """,
            (
                datetime.now(),
                f"\n[REJECTED] {reason_text}",
                transaction_id,
            ),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Pembayaran ditolak",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error rejecting payment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REJECT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
