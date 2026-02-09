"""
CMS Products Router - CRUD Products & Inventory
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission, get_branch_id, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["CMS - Products"])


# ============== Request Models ==============

class ProductCreate(BaseModel):
    category_id: Optional[int] = None
    sku: Optional[str] = Field(None, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    cost_price: Optional[float] = Field(None, ge=0)
    stock: int = Field(0, ge=0)
    min_stock: int = Field(5, ge=0)
    is_rental: bool = False
    rental_duration: Optional[str] = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    sku: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    min_stock: Optional[int] = Field(None, ge=0)
    is_rental: Optional[bool] = None
    rental_duration: Optional[str] = None
    is_active: Optional[bool] = None


class StockAdjustmentRequest(BaseModel):
    quantity: int = Field(..., description="Positive for add, negative for subtract")
    reason: str = Field(..., min_length=1)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    sort_order: int = 0


# ============== Category Endpoints ==============

@router.get("/categories")
def get_categories(auth: dict = Depends(verify_bearer_token)):
    """Get all product categories"""
    check_permission(auth, "product.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT pc.*, COUNT(p.id) as product_count
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


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(request: CategoryCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new product category"""
    check_permission(auth, "product.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            INSERT INTO product_categories (name, description, sort_order, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (request.name, request.description, request.sort_order, datetime.now()),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Kategori berhasil dibuat",
            "data": {"id": cursor.lastrowid},
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_CATEGORY_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete a product category"""
    check_permission(auth, "product.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if category has products
        cursor.execute(
            "SELECT COUNT(*) as count FROM products WHERE category_id = %s AND is_active = 1",
            (category_id,),
        )
        result = cursor.fetchone()
        if result and result["count"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "CATEGORY_HAS_PRODUCTS",
                    "message": f"Kategori masih memiliki {result['count']} produk aktif",
                },
            )

        cursor.execute("DELETE FROM product_categories WHERE id = %s", (category_id,))
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "CATEGORY_NOT_FOUND", "message": "Kategori tidak ditemukan"},
            )
        conn.commit()

        return {"success": True, "message": "Kategori berhasil dihapus"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_CATEGORY_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Product Endpoints ==============

@router.get("")
def get_products(
    category_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_rental: Optional[bool] = Query(None),
    low_stock: bool = Query(False, description="Filter products with stock below min_stock"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get all products with filters. When branch_id is provided, includes per-branch stock info."""
    check_permission(auth, "product.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if category_id:
            where_clauses.append("p.category_id = %s")
            params.append(category_id)

        if is_active is not None:
            where_clauses.append("p.is_active = %s")
            params.append(1 if is_active else 0)

        if is_rental is not None:
            where_clauses.append("p.is_rental = %s")
            params.append(1 if is_rental else 0)

        if low_stock:
            if branch_id:
                where_clauses.append(
                    "bps.stock <= bps.min_stock AND p.is_rental = 0"
                )
            else:
                where_clauses.append("p.stock <= p.min_stock AND p.is_rental = 0")

        if search:
            where_clauses.append("(p.name LIKE %s OR p.sku LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Build branch JOIN clause
        branch_join = ""
        branch_select = ""
        count_join = ""
        if branch_id:
            branch_join = " LEFT JOIN branch_product_stock bps ON p.id = bps.product_id AND bps.branch_id = %s"
            branch_select = ", bps.stock AS branch_stock, bps.min_stock AS branch_min_stock"
            count_join = branch_join
        else:
            # When no branch selected, get total stock across all branches
            branch_select = ", (SELECT COALESCE(SUM(bps2.stock), 0) FROM branch_product_stock bps2 WHERE bps2.product_id = p.id) AS total_branch_stock"

        # Count total
        count_params = ([branch_id] + params) if branch_id else list(params)
        cursor.execute(
            f"SELECT COUNT(*) as total FROM products p{count_join}{where_sql}",
            count_params,
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        image_select = """, (
            SELECT img.file_path FROM images img
            WHERE img.category = 'product' AND img.reference_id = p.id AND img.is_active = 1
            ORDER BY img.sort_order ASC LIMIT 1
        ) AS image_url"""
        data_params = ([branch_id] + params + [limit, offset]) if branch_id else (params + [limit, offset])
        cursor.execute(
            f"""
            SELECT p.*, pc.name as category_name{branch_select}{image_select}
            FROM products p
            LEFT JOIN product_categories pc ON p.category_id = pc.id
            {branch_join}
            {where_sql}
            ORDER BY p.name ASC
            LIMIT %s OFFSET %s
            """,
            data_params,
        )
        products = cursor.fetchall()

        for p in products:
            p["price"] = float(p["price"]) if p.get("price") else 0
            p["cost_price"] = float(p["cost_price"]) if p.get("cost_price") else 0
            p["is_active"] = bool(p.get("is_active"))
            p["is_rental"] = bool(p.get("is_rental"))
            p["is_low_stock"] = p["stock"] <= p["min_stock"] if not p["is_rental"] else False

            if branch_id:
                b_stock = p.get("branch_stock")
                b_min = p.get("branch_min_stock")
                p["branch_stock"] = {
                    "branch_id": branch_id,
                    "stock": b_stock if b_stock is not None else 0,
                    "min_stock": b_min if b_min is not None else 0,
                    "is_low_stock": (
                        (b_stock or 0) <= (b_min or 0)
                        if not p["is_rental"] and b_stock is not None
                        else False
                    ),
                }
                # Remove flat branch columns from top-level
                p.pop("branch_min_stock", None)
            else:
                # Replace global stock with total from all branches
                total_b_stock = p.pop("total_branch_stock", 0)
                p["total_stock"] = int(total_b_stock) if total_b_stock else 0

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PRODUCTS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(request: ProductCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new product"""
    check_permission(auth, "product.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check SKU uniqueness
        if request.sku:
            cursor.execute("SELECT id FROM products WHERE sku = %s", (request.sku,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "SKU_EXISTS", "message": "SKU sudah digunakan"},
                )

        cursor.execute(
            """
            INSERT INTO products
            (category_id, sku, name, description, price, cost_price, stock, min_stock,
             is_rental, rental_duration, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.category_id,
                request.sku,
                request.name,
                request.description,
                request.price,
                request.cost_price,
                request.stock,
                request.min_stock,
                1 if request.is_rental else 0,
                request.rental_duration,
                1 if request.is_active else 0,
                datetime.now(),
            ),
        )
        conn.commit()
        product_id = cursor.lastrowid

        # Log initial stock
        if request.stock > 0:
            cursor.execute(
                """
                INSERT INTO product_stock_logs
                (product_id, type, quantity, stock_before, stock_after, reference_type, notes, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (product_id, "in", request.stock, 0, request.stock, "adjustment", "Initial stock", auth["user_id"], datetime.now()),
            )
            conn.commit()

        return {
            "success": True,
            "message": "Produk berhasil dibuat",
            "data": {"id": product_id},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating product: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_PRODUCT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{product_id}")
def get_product(product_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get a specific product"""
    check_permission(auth, "product.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT p.*, pc.name as category_name
            FROM products p
            LEFT JOIN product_categories pc ON p.category_id = pc.id
            WHERE p.id = %s
            """,
            (product_id,),
        )
        product = cursor.fetchone()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Produk tidak ditemukan"},
            )

        product["price"] = float(product["price"]) if product.get("price") else 0
        product["cost_price"] = float(product["cost_price"]) if product.get("cost_price") else 0
        product["is_active"] = bool(product.get("is_active"))
        product["is_rental"] = bool(product.get("is_rental"))

        return {
            "success": True,
            "data": product,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PRODUCT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{product_id}")
def update_product(
    product_id: int, request: ProductUpdate, auth: dict = Depends(verify_bearer_token)
):
    """Update a product"""
    check_permission(auth, "product.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if product exists
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Produk tidak ditemukan"},
            )

        # Check SKU uniqueness
        if request.sku:
            cursor.execute("SELECT id FROM products WHERE sku = %s AND id != %s", (request.sku, product_id))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "SKU_EXISTS", "message": "SKU sudah digunakan"},
                )

        # Build update query
        update_fields = []
        params = []

        for field in ["category_id", "sku", "name", "description", "price", "cost_price", "min_stock", "rental_duration"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"{field} = %s")
                params.append(value)

        if request.is_rental is not None:
            update_fields.append("is_rental = %s")
            params.append(1 if request.is_rental else 0)

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        # Handle stock change with logging
        if request.stock is not None and request.stock != product["stock"]:
            diff = request.stock - product["stock"]
            cursor.execute(
                """
                INSERT INTO product_stock_logs
                (product_id, type, quantity, stock_before, stock_after, reference_type, notes, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    product_id,
                    "in" if diff > 0 else "out",
                    abs(diff),
                    product["stock"],
                    request.stock,
                    "adjustment",
                    "Stock update via product edit",
                    auth["user_id"],
                    datetime.now(),
                ),
            )
            update_fields.append("stock = %s")
            params.append(request.stock)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(product_id)

        cursor.execute(
            f"UPDATE products SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Produk berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating product: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_PRODUCT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{product_id}")
def delete_product(product_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete a product (soft delete)"""
    check_permission(auth, "product.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Produk tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE products SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), product_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Produk berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting product: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_PRODUCT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{product_id}/adjust-stock")
def adjust_stock(
    product_id: int,
    request: StockAdjustmentRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Adjust product stock for a specific branch"""
    check_permission(auth, "product.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Produk tidak ditemukan"},
            )

        if product["is_rental"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "RENTAL_PRODUCT", "message": "Tidak bisa adjust stock untuk produk rental"},
            )

        # Get current branch stock (or 0 if no row exists yet)
        cursor.execute(
            "SELECT stock FROM branch_product_stock WHERE branch_id = %s AND product_id = %s",
            (branch_id, product_id),
        )
        branch_row = cursor.fetchone()
        current_stock = branch_row["stock"] if branch_row else 0

        new_stock = current_stock + request.quantity
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INSUFFICIENT_STOCK", "message": "Stok tidak mencukupi"},
            )

        # Upsert branch_product_stock
        if branch_row:
            cursor.execute(
                "UPDATE branch_product_stock SET stock = %s WHERE branch_id = %s AND product_id = %s",
                (new_stock, branch_id, product_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO branch_product_stock (branch_id, product_id, stock, min_stock)
                VALUES (%s, %s, %s, %s)
                """,
                (branch_id, product_id, new_stock, product["min_stock"]),
            )

        # Log with branch_id
        cursor.execute(
            """
            INSERT INTO product_stock_logs
            (branch_id, product_id, type, quantity, stock_before, stock_after, reference_type, notes, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
                product_id,
                "in" if request.quantity > 0 else "out",
                abs(request.quantity),
                current_stock,
                new_stock,
                "adjustment",
                request.reason,
                auth["user_id"],
                datetime.now(),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Stok berhasil disesuaikan",
            "data": {
                "branch_id": branch_id,
                "stock_before": current_stock,
                "adjustment": request.quantity,
                "stock_after": new_stock,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adjusting stock: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ADJUST_STOCK_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{product_id}/stock-logs")
def get_stock_logs(
    product_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get stock logs for a product"""
    check_permission(auth, "product.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Count total
        cursor.execute(
            "SELECT COUNT(*) as total FROM product_stock_logs WHERE product_id = %s",
            (product_id,),
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            """
            SELECT psl.*, u.name as created_by_name, b.name as branch_name
            FROM product_stock_logs psl
            LEFT JOIN users u ON psl.created_by = u.id
            LEFT JOIN branches b ON psl.branch_id = b.id
            WHERE psl.product_id = %s
            ORDER BY psl.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (product_id, limit, offset),
        )
        logs = cursor.fetchall()

        return {
            "success": True,
            "data": logs,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"Error getting stock logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_STOCK_LOGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
