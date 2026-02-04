"""
Member Transactions Router - Member's transaction history + self-checkout
"""
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Member - Transactions"])


# ============== Request Models ==============

class MemberCheckoutItem(BaseModel):
    item_type: str = Field(..., pattern=r"^(membership|class_pass|product|pt_package)$")
    item_id: int
    quantity: int = Field(1, ge=1)
    trainer_id: Optional[int] = None  # Required for pt_package


class MemberCheckoutRequest(BaseModel):
    items: List[MemberCheckoutItem]
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")
    auto_renew: bool = False


# ============== Helper Functions ==============

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
    elif item_type == "product":
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
    elif item_type == "pt_package":
        cursor.execute(
            "SELECT id, name, price, session_count, valid_days FROM pt_packages WHERE id = %s AND is_active = 1",
            (item_id,),
        )
    else:
        return None

    return cursor.fetchone()


# ============== Endpoints ==============

@router.post("/checkout")
def member_checkout(
    request: MemberCheckoutRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """
    Member self-checkout. Creates a transaction for the authenticated member.
    Supports membership, class_pass, and product items.
    """
    if not request.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "EMPTY_CART", "message": "Keranjang kosong"},
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        buyer_user_id = auth["user_id"]

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

            # Validate trainer_id for pt_package
            if item.item_type == "pt_package" and not item.trainer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "TRAINER_REQUIRED",
                        "message": "Trainer harus dipilih untuk paket PT",
                    },
                )

            # Calculate item pricing
            unit_price = float(item_details["price"])
            item_total = unit_price * item.quantity
            item_subtotal = item_total
            subtotal += item_subtotal

            transaction_items.append({
                "item_type": item.item_type,
                "item_id": item.item_id,
                "item_name": item_details["name"],
                "quantity": item.quantity,
                "unit_price": unit_price,
                "discount_amount": 0,
                "subtotal": item_subtotal,
                "details": item_details,
                "trainer_id": item.trainer_id,  # for pt_package
            })

        # Calculate tax and service charge
        tax_amount = subtotal * (tax_percentage / 100) if tax_enabled else 0
        service_charge_amount = subtotal * (service_charge_percentage / 100) if service_charge_enabled else 0
        grand_total = subtotal + tax_amount + service_charge_amount

        # Create transaction
        transaction_code = generate_transaction_code(branch_code)
        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, branch_id, user_id, staff_id, customer_name,
             subtotal, discount_type, discount_value, discount_amount, subtotal_after_discount,
             tax_percentage, tax_amount, service_charge_percentage, service_charge_amount,
             grand_total, payment_method, payment_status, paid_amount, paid_at, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_code,
                branch_id,
                buyer_user_id,
                None,  # no staff for self-checkout
                None,  # not a walk-in
                subtotal,
                None,  # no transaction discount
                0,
                0,
                subtotal,
                tax_percentage if tax_enabled else 0,
                tax_amount,
                service_charge_percentage if service_charge_enabled else 0,
                service_charge_amount,
                grand_total,
                request.payment_method,
                "paid",
                grand_total,
                datetime.now(),
                f"Self-checkout (auto_renew={request.auto_renew})" if request.auto_renew else "Self-checkout",
                datetime.now(),
            ),
        )
        transaction_id = cursor.lastrowid

        # Create transaction items and process each
        for item in transaction_items:
            metadata = {"details": {k: v for k, v in item["details"].items() if k not in ["price"]}}
            if item.get("trainer_id"):
                metadata["trainer_id"] = item["trainer_id"]

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
                    None,
                    0,
                    0,
                    item["subtotal"],
                    json.dumps(metadata),
                    datetime.now(),
                ),
            )

            # Process based on item type
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
                        buyer_user_id,
                        datetime.now(),
                    ),
                )

            elif item["item_type"] == "membership":
                # Activate membership for the member
                details = item["details"]
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
                     visit_remaining, class_remaining, status, auto_renew, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        buyer_user_id,
                        item["item_id"],
                        transaction_id,
                        membership_code,
                        start_date_m,
                        end_date_m,
                        visit_remaining,
                        details.get("class_quota"),
                        "active",
                        request.auto_renew,
                        datetime.now(),
                    ),
                )

            elif item["item_type"] == "class_pass":
                # Create class pass for the member
                details = item["details"]
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
                        buyer_user_id,
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

            elif item["item_type"] == "pt_package":
                # Create PT sessions for the member
                details = item["details"]
                trainer_id = item.get("trainer_id")
                start_date_pt = date.today()
                expire_date_pt = start_date_pt + timedelta(days=details.get("valid_days", 30))
                session_count = details.get("session_count", 1)

                # Insert one record per quantity purchased
                # Note: remaining_sessions is a generated column, so we don't insert it
                for _ in range(item["quantity"]):
                    cursor.execute(
                        """
                        INSERT INTO member_pt_sessions
                        (user_id, pt_package_id, trainer_id, transaction_id, total_sessions, used_sessions,
                         start_date, expire_date, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            buyer_user_id,
                            item["item_id"],
                            trainer_id,
                            transaction_id,
                            session_count,
                            0,  # used_sessions starts at 0
                            start_date_pt,
                            expire_date_pt,
                            "active",
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
                "discount_amount": 0,
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
        logger.error(f"Error during member checkout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKOUT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


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
