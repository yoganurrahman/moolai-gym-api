"""
Member Transactions Router - Member's transaction history + self-checkout
"""
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List

import os

from fastapi import APIRouter, HTTPException, status, Depends, Query, File, Form, UploadFile
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
    promo_id: Optional[int] = None
    voucher_code: Optional[str] = None


# ============== Helper Functions ==============

# Mapping item_type di cart ke applicable_to di promo/voucher
ITEM_TYPE_TO_APPLICABLE = {
    "product": "product",
    "rental": "product",
    "membership": "membership",
    "pt_package": "pt",
    "class_pass": "class",
}


def filter_applicable_items(transaction_items, applicable_to, applicable_items_json):
    """Filter transaction items yang sesuai dengan applicable_to dan applicable_items."""
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
        if applicable_to != "all" and item_applicable != applicable_to:
            continue
        if applicable_item_ids and item["item_id"] not in applicable_item_ids:
            continue
        matched.append(item)

    return matched


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

        subtotal_after_discount = subtotal

        # Apply promo if provided
        promo_discount = 0
        if request.promo_id:
            cursor.execute(
                """
                SELECT * FROM promos
                WHERE id = %s AND is_active = 1
                AND start_date <= NOW() AND end_date >= NOW()
                AND (usage_limit IS NULL OR usage_count < usage_limit)
                """,
                (request.promo_id,),
            )
            promo = cursor.fetchone()

            if promo:
                # Check per_user_limit
                per_user_limit = promo.get("per_user_limit") or 0
                if per_user_limit > 0:
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
                    pass
                else:
                    if promo_applicable != "all" or promo.get("applicable_items"):
                        applicable_subtotal = sum(i["subtotal"] for i in matched_items)
                    else:
                        applicable_subtotal = subtotal_after_discount

                    min_purchase = float(promo.get("min_purchase") or 0)
                    if min_purchase <= 0 or applicable_subtotal >= min_purchase:
                        if promo["promo_type"] == "percentage":
                            promo_discount = applicable_subtotal * (float(promo["discount_value"]) / 100)
                            if promo.get("max_discount"):
                                promo_discount = min(promo_discount, float(promo["max_discount"]))
                        elif promo["promo_type"] == "fixed":
                            promo_discount = min(float(promo["discount_value"]), applicable_subtotal)
                        elif promo["promo_type"] == "free_item":
                            cheapest_price = min(i["unit_price"] for i in matched_items) if matched_items else 0
                            promo_discount = min(cheapest_price, applicable_subtotal)

                        promo_discount = min(promo_discount, subtotal_after_discount)
                        subtotal_after_discount -= promo_discount

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
                if voucher.get("is_single_use"):
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM discount_usages WHERE discount_type = 'voucher' AND discount_id = %s AND user_id = %s",
                        (voucher["id"], buyer_user_id),
                    )
                    if cursor.fetchone()["cnt"] > 0:
                        voucher = None

            if voucher:
                voucher_applicable = voucher.get("applicable_to") or "all"
                matched_items = filter_applicable_items(
                    transaction_items, voucher_applicable, voucher.get("applicable_items")
                )

                if not matched_items and voucher_applicable != "all":
                    pass
                else:
                    if voucher_applicable != "all" or voucher.get("applicable_items"):
                        applicable_subtotal = sum(i["subtotal"] for i in matched_items)
                    else:
                        applicable_subtotal = subtotal_after_discount

                    if voucher["voucher_type"] == "percentage":
                        voucher_discount = applicable_subtotal * (float(voucher["discount_value"]) / 100)
                        if voucher.get("max_discount"):
                            voucher_discount = min(voucher_discount, float(voucher["max_discount"]))
                    elif voucher["voucher_type"] == "free_item":
                        cheapest_price = min(i["unit_price"] for i in matched_items) if matched_items else 0
                        voucher_discount = min(cheapest_price, applicable_subtotal)
                    else:
                        voucher_discount = min(float(voucher["discount_value"]), applicable_subtotal)

                    voucher_discount = min(voucher_discount, subtotal_after_discount)
                    subtotal_after_discount -= voucher_discount

        # Calculate tax and service charge
        tax_amount = subtotal_after_discount * (tax_percentage / 100) if tax_enabled else 0
        service_charge_amount = subtotal_after_discount * (service_charge_percentage / 100) if service_charge_enabled else 0
        grand_total = subtotal_after_discount + tax_amount + service_charge_amount

        # Create transaction
        transaction_code = generate_transaction_code(branch_code)
        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, branch_id, user_id, staff_id, customer_name,
             subtotal, discount_type, discount_value, discount_amount, subtotal_after_discount,
             tax_percentage, tax_amount, service_charge_percentage, service_charge_amount,
             grand_total, payment_method, payment_status, paid_amount, paid_at,
             promo_id, promo_discount, voucher_code, voucher_discount, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                promo_discount + voucher_discount,
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
                request.promo_id,
                promo_discount,
                request.voucher_code,
                voucher_discount,
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

            # Item activation (stock deduct, membership, class pass, PT) happens on CMS approval

        conn.commit()

        return {
            "success": True,
            "message": "Checkout berhasil, silakan lakukan pembayaran",
            "data": {
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "subtotal": subtotal,
                "discount_amount": promo_discount + voucher_discount,
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
        logger.error(f"Error during member checkout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKOUT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/submit-payment")
def submit_payment(
    transaction_id: int = Form(...),
    file: Optional[UploadFile] = File(None),
    auth: dict = Depends(verify_bearer_token),
):
    """
    Submit payment for pending transaction.
    For cash: must upload payment proof image.
    For other methods: can submit without proof.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get pending transaction owned by this user
        cursor.execute(
            "SELECT * FROM transactions WHERE id = %s AND user_id = %s AND payment_status = 'pending'",
            (transaction_id, auth["user_id"]),
        )
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRANSACTION_NOT_FOUND", "message": "Transaksi tidak ditemukan atau sudah diproses"},
            )

        # Cash payment requires proof
        if transaction["payment_method"] == "cash" and file is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PROOF_REQUIRED", "message": "Pembayaran tunai memerlukan bukti pembayaran"},
            )

        payment_proof_path = None

        if file:
            # Validate file type
            allowed_types = ["image/jpeg", "image/png", "image/webp"]
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "INVALID_FILE_TYPE", "message": "Format file harus JPG, PNG, atau WebP"},
                )

            file_content = file.file.read()

            # Validate file size (5MB max)
            if len(file_content) > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "FILE_TOO_LARGE", "message": "Ukuran file maksimal 5MB"},
                )

            # Save file
            upload_dir = os.environ.get("UPLOAD_DIR", "uploads/images")
            proof_dir = os.path.join(upload_dir, "payment_proof")
            os.makedirs(proof_dir, exist_ok=True)

            ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            unique_name = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(proof_dir, unique_name)

            with open(file_path, "wb") as f:
                f.write(file_content)

            payment_proof_path = f"uploads/images/payment_proof/{unique_name}"

        # Update transaction with payment proof
        if payment_proof_path:
            cursor.execute(
                "UPDATE transactions SET payment_proof = %s, updated_at = %s WHERE id = %s",
                (payment_proof_path, datetime.now(), transaction_id),
            )
        else:
            cursor.execute(
                "UPDATE transactions SET updated_at = %s WHERE id = %s",
                (datetime.now(), transaction_id),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Pembayaran berhasil disubmit, menunggu persetujuan admin",
            "data": {
                "transaction_id": transaction_id,
                "payment_proof": payment_proof_path,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error submitting payment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SUBMIT_PAYMENT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/active-promos")
def get_active_promos_for_member(
    auth: dict = Depends(verify_bearer_token),
):
    """Get active promos available for member checkout"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, name, description, promo_type, discount_value, min_purchase, max_discount,
                   applicable_to, start_date, end_date, usage_limit, usage_count, per_user_limit
            FROM promos
            WHERE is_active = 1 AND start_date <= NOW() AND end_date >= NOW()
            AND (usage_limit IS NULL OR usage_count < usage_limit)
            AND (member_only = 1 OR new_member_only = 0)
            ORDER BY created_at DESC
            """
        )
        promos = cursor.fetchall()

        # Convert decimals
        for p in promos:
            for key in ["discount_value", "min_purchase", "max_discount"]:
                if p.get(key) is not None:
                    p[key] = float(p[key])

        return {"success": True, "data": promos}

    except Exception as e:
        logger.error(f"Error loading active promos: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LOAD_PROMOS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/active-vouchers")
def get_active_vouchers_for_member(
    auth: dict = Depends(verify_bearer_token),
):
    """Get active vouchers available for member checkout"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, code, voucher_type, discount_value, min_purchase, max_discount,
                   applicable_to, start_date, end_date, usage_limit, usage_count, is_single_use
            FROM vouchers
            WHERE is_active = 1 AND start_date <= NOW() AND end_date >= NOW()
            AND (usage_limit IS NULL OR usage_count < usage_limit)
            ORDER BY created_at DESC
            """
        )
        vouchers = cursor.fetchall()

        for v in vouchers:
            for key in ["discount_value", "min_purchase", "max_discount"]:
                if v.get(key) is not None:
                    v[key] = float(v[key])

        return {"success": True, "data": vouchers}

    except Exception as e:
        logger.error(f"Error loading active vouchers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LOAD_VOUCHERS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/validate-voucher")
def validate_voucher_for_member(
    request: dict,
    auth: dict = Depends(verify_bearer_token),
):
    """Validate a voucher code for member checkout"""
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
            SELECT * FROM vouchers
            WHERE code = %s AND is_active = 1
            AND start_date <= NOW() AND end_date >= NOW()
            AND (usage_limit IS NULL OR usage_count < usage_limit)
            """,
            (code,),
        )
        voucher = cursor.fetchone()

        if not voucher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "VOUCHER_NOT_FOUND", "message": "Voucher tidak ditemukan atau sudah tidak berlaku"},
            )

        # Check is_single_use
        if voucher.get("is_single_use"):
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM discount_usages WHERE discount_type = 'voucher' AND discount_id = %s AND user_id = %s",
                (voucher["id"], auth["user_id"]),
            )
            if cursor.fetchone()["cnt"] > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "ALREADY_USED", "message": "Voucher ini sudah pernah digunakan"},
                )

        # Check min_purchase
        min_purchase = float(voucher.get("min_purchase") or 0)
        if min_purchase > 0 and subtotal < min_purchase:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "MIN_PURCHASE_NOT_MET",
                    "message": f"Minimum pembelian Rp {min_purchase:,.0f} untuk voucher ini",
                },
            )

        # Calculate discount
        discount_amount = 0
        if voucher["voucher_type"] == "percentage":
            discount_amount = subtotal * (float(voucher["discount_value"]) / 100)
            if voucher.get("max_discount"):
                discount_amount = min(discount_amount, float(voucher["max_discount"]))
        elif voucher["voucher_type"] == "fixed":
            discount_amount = min(float(voucher["discount_value"]), subtotal)

        # Convert decimals
        for key in ["discount_value", "min_purchase", "max_discount"]:
            if voucher.get(key) is not None:
                voucher[key] = float(voucher[key])

        voucher["discount_amount"] = discount_amount

        return {"success": True, "data": voucher}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating voucher: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "VALIDATE_FAILED", "message": str(e)},
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
            SELECT t.id, t.transaction_code, t.subtotal, t.discount_amount,
                   t.promo_id, t.promo_discount, t.voucher_code, t.voucher_discount,
                   t.tax_amount, t.grand_total,
                   t.payment_method, t.payment_status, t.payment_proof,
                   t.paid_at, t.created_at,
                   b.name as branch_name, b.code as branch_code,
                   p.name as promo_name
            FROM transactions t
            LEFT JOIN branches b ON t.branch_id = b.id
            LEFT JOIN promos p ON t.promo_id = p.id
            WHERE t.user_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (auth["user_id"], limit, offset),
        )
        transactions = cursor.fetchall()

        for t in transactions:
            for key in ["subtotal", "discount_amount", "promo_discount", "voucher_discount", "tax_amount", "grand_total"]:
                t[key] = float(t[key]) if t.get(key) else 0

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
            SELECT t.*, b.name as branch_name, b.code as branch_code,
                   p.name as promo_name, p.promo_type, p.discount_value as promo_discount_value
            FROM transactions t
            LEFT JOIN branches b ON t.branch_id = b.id
            LEFT JOIN promos p ON t.promo_id = p.id
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
        for key in ["subtotal", "discount_amount", "promo_discount", "voucher_discount", "subtotal_after_discount", "tax_amount", "service_charge_amount", "grand_total", "paid_amount", "promo_discount_value"]:
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
