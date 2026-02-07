"""
Member Products Router - Browse & purchase products
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, require_branch_id, get_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["Member - Products"])


# ============== Request Models ==============

class CartItem(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)


class PurchaseProductsRequest(BaseModel):
    items: List[CartItem] = Field(..., min_length=1)
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")


# ============== Helper Functions ==============

def generate_transaction_code():
    """Generate unique transaction code"""
    return f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ============== Endpoints ==============

@router.get("/categories")
def get_categories(auth: dict = Depends(verify_bearer_token)):
    """Get all active product categories with product count"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT pc.id, pc.name, pc.description, pc.image, pc.sort_order,
                   COUNT(p.id) as product_count
            FROM product_categories pc
            LEFT JOIN products p ON pc.id = p.category_id AND p.is_active = 1
            WHERE pc.is_active = 1
            GROUP BY pc.id
            ORDER BY pc.sort_order ASC, pc.name ASC
            """
        )
        categories = cursor.fetchall()

        return {
            "success": True,
            "data": categories,
        }

    except Exception as e:
        logger.error(f"Error getting categories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CATEGORIES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("")
def get_products(
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    include_images: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get active products. When branch_id is provided, includes per-branch stock info."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = ["p.is_active = 1"]
        params = []

        if category_id:
            where_clauses.append("p.category_id = %s")
            params.append(category_id)

        if search:
            where_clauses.append("(p.name LIKE %s OR p.description LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_sql = " WHERE " + " AND ".join(where_clauses)

        # Build branch JOIN clause
        branch_join = ""
        branch_select = ""
        if branch_id:
            branch_join = " LEFT JOIN branch_product_stock bps ON p.id = bps.product_id AND bps.branch_id = %s"
            branch_select = ", bps.stock AS branch_stock"

        # Count total
        count_params = ([branch_id] + params) if branch_id else list(params)
        cursor.execute(
            f"SELECT COUNT(*) as total FROM products p{branch_join}{where_sql}",
            count_params,
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        data_params = ([branch_id] + params + [limit, offset]) if branch_id else (params + [limit, offset])
        cursor.execute(
            f"""
            SELECT p.id, p.name, p.description, p.price, p.image,
                   p.is_rental, p.rental_duration,
                   pc.name as category_name{branch_select}
            FROM products p
            LEFT JOIN product_categories pc ON p.category_id = pc.id
            {branch_join}
            {where_sql}
            ORDER BY pc.sort_order ASC, p.name ASC
            LIMIT %s OFFSET %s
            """,
            data_params,
        )
        products = cursor.fetchall()

        # Get product IDs for images query
        product_ids = [p["id"] for p in products]

        # Load images from images table if requested
        product_images = {}
        if include_images and product_ids:
            placeholders = ",".join(["%s"] * len(product_ids))
            cursor.execute(
                f"""
                SELECT reference_id, file_path, title, sort_order
                FROM images
                WHERE category = 'product'
                  AND reference_id IN ({placeholders})
                  AND is_active = 1
                ORDER BY sort_order ASC, id ASC
                """,
                product_ids,
            )
            for img in cursor.fetchall():
                ref_id = img["reference_id"]
                if ref_id not in product_images:
                    product_images[ref_id] = []
                product_images[ref_id].append({
                    "file_path": img["file_path"],
                    "title": img["title"],
                })

        for p in products:
            p["price"] = float(p["price"]) if p.get("price") else 0
            p["is_rental"] = bool(p.get("is_rental"))
            if branch_id:
                b_stock = p.pop("branch_stock", None)
                p["branch_stock"] = b_stock if b_stock is not None else 0
            else:
                p["branch_stock"] = 0

            # Add images from images table
            if include_images:
                p["images"] = product_images.get(p["id"], [])

        return {
            "success": True,
            "data": products,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"Error getting products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PRODUCTS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/purchase")
def purchase_products(
    request: PurchaseProductsRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Purchase products from the shop"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Validate all products and check stock
        product_ids = [item.product_id for item in request.items]
        placeholders = ",".join(["%s"] * len(product_ids))
        cursor.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders}) AND is_active = 1",
            product_ids,
        )
        products_db = {p["id"]: p for p in cursor.fetchall()}

        # Check all products exist
        for item in request.items:
            if item.product_id not in products_db:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error_code": "PRODUCT_NOT_FOUND",
                        "message": f"Produk dengan id {item.product_id} tidak ditemukan",
                    },
                )

        # Check branch stock for non-rental products
        non_rental_ids = [
            item.product_id
            for item in request.items
            if not products_db[item.product_id]["is_rental"]
        ]
        branch_stocks = {}
        if non_rental_ids:
            placeholders2 = ",".join(["%s"] * len(non_rental_ids))
            cursor.execute(
                f"""
                SELECT product_id, stock FROM branch_product_stock
                WHERE branch_id = %s AND product_id IN ({placeholders2})
                """,
                [branch_id] + non_rental_ids,
            )
            branch_stocks = {row["product_id"]: row["stock"] for row in cursor.fetchall()}

        # Validate stock availability
        for item in request.items:
            product = products_db[item.product_id]
            if product["is_rental"]:
                continue
            available = branch_stocks.get(item.product_id, 0)
            if available < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "INSUFFICIENT_STOCK",
                        "message": f"Stok {product['name']} tidak mencukupi (tersedia: {available})",
                    },
                )

        # 2. Get tax settings
        cursor.execute(
            "SELECT `key`, `value` FROM settings WHERE `key` IN ('tax_enabled', 'tax_percentage')"
        )
        settings = {row["key"]: row["value"] for row in cursor.fetchall()}
        tax_enabled = settings.get("tax_enabled", "false") == "true"
        tax_percentage = float(settings.get("tax_percentage", "0"))

        # 3. Calculate pricing
        subtotal = 0.0
        item_details = []
        for item in request.items:
            product = products_db[item.product_id]
            unit_price = float(product["price"])
            item_subtotal = unit_price * item.quantity
            subtotal += item_subtotal
            item_details.append({
                "product": product,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "subtotal": item_subtotal,
            })

        tax_amount = subtotal * (tax_percentage / 100) if tax_enabled else 0
        grand_total = subtotal + tax_amount

        # 4. Create transaction
        transaction_code = generate_transaction_code()
        cursor.execute(
            """
            INSERT INTO transactions
            (transaction_code, user_id, branch_id, subtotal, subtotal_after_discount,
             tax_percentage, tax_amount, grand_total, payment_method, payment_status,
             paid_amount, paid_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_code,
                auth["user_id"],
                branch_id,
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

        # 5. Create transaction items and update stock
        response_items = []
        for detail in item_details:
            product = detail["product"]
            item_type = "rental" if product["is_rental"] else "product"

            cursor.execute(
                """
                INSERT INTO transaction_items
                (transaction_id, item_type, item_id, item_name, quantity,
                 unit_price, subtotal, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    item_type,
                    product["id"],
                    product["name"],
                    detail["quantity"],
                    detail["unit_price"],
                    detail["subtotal"],
                    datetime.now(),
                ),
            )

            # Reduce branch stock for non-rental products
            if not product["is_rental"]:
                old_stock = branch_stocks.get(product["id"], 0)
                new_stock = old_stock - detail["quantity"]

                cursor.execute(
                    """
                    UPDATE branch_product_stock
                    SET stock = %s, updated_at = %s
                    WHERE branch_id = %s AND product_id = %s
                    """,
                    (new_stock, datetime.now(), branch_id, product["id"]),
                )

                # Log stock change
                cursor.execute(
                    """
                    INSERT INTO product_stock_logs
                    (branch_id, product_id, type, quantity, stock_before, stock_after,
                     reference_type, reference_id, notes, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        branch_id,
                        product["id"],
                        "out",
                        detail["quantity"],
                        old_stock,
                        new_stock,
                        "purchase",
                        transaction_id,
                        f"Pembelian oleh member",
                        auth["user_id"],
                        datetime.now(),
                    ),
                )

            response_items.append({
                "product_name": product["name"],
                "quantity": detail["quantity"],
                "unit_price": detail["unit_price"],
                "subtotal": detail["subtotal"],
            })

        conn.commit()

        return {
            "success": True,
            "message": "Pembelian berhasil",
            "data": {
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "items": response_items,
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "grand_total": grand_total,
                "payment_method": request.payment_method,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error purchasing products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PURCHASE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
