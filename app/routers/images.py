"""
Global Images Router - CRUD & Upload untuk semua kebutuhan gambar
Kategori: splash_screen, onboarding, banner, pop_promo, product, class, pt, content, login, other
"""
import os
import logging
import uuid
import shutil
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["Images"])

# Upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/images")
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"]
MAX_FILE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", 5 * 1024 * 1024))  # 5MB default

VALID_CATEGORIES = [
    "splash_screen", "onboarding", "banner", "banner_member",
    "banner_class", "banner_pt", "banner_product", "pop_promo",
    "product", "class", "pt", "content", "login", "other"
]

VALID_PLATFORMS = ["all", "mobile", "web", "cms"]


# ============== Request Models ==============

class ImageUpdate(BaseModel):
    category: Optional[str] = Field(None, description="Kategori gambar")
    reference_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[str] = Field(None, description="Format: YYYY-MM-DD HH:MM:SS")
    end_date: Optional[str] = Field(None, description="Format: YYYY-MM-DD HH:MM:SS")
    deep_link: Optional[str] = Field(None, max_length=500)
    platform: Optional[str] = Field(None, description="all, mobile, web, cms")


# ============== Helper ==============

def _ensure_upload_dir():
    """Pastikan folder upload ada"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _format_image(img: dict) -> dict:
    """Format image record untuk response"""
    if img.get("created_at") and hasattr(img["created_at"], "isoformat"):
        img["created_at"] = img["created_at"].isoformat()
    if img.get("updated_at") and hasattr(img["updated_at"], "isoformat"):
        img["updated_at"] = img["updated_at"].isoformat()
    if img.get("start_date") and hasattr(img["start_date"], "isoformat"):
        img["start_date"] = img["start_date"].isoformat()
    if img.get("end_date") and hasattr(img["end_date"], "isoformat"):
        img["end_date"] = img["end_date"].isoformat()
    img["is_active"] = bool(img.get("is_active"))
    return img


# ============== Endpoints ==============

@router.get("/public")
def get_public_images(
    category: str = Query(..., description="Filter by category"),
    reference_id: Optional[int] = Query(None),
    platform: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Get active images (public, no auth required) — for splash, onboarding, banners"""
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CATEGORY",
                "message": f"Kategori tidak valid. Pilihan: {', '.join(VALID_CATEGORIES)}",
            },
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = [
            "i.category = %s",
            "i.is_active = 1",
            "(i.start_date IS NULL OR i.start_date <= NOW())",
            "(i.end_date IS NULL OR i.end_date >= NOW())",
        ]
        params = [category]

        if reference_id is not None:
            where_clauses.append("i.reference_id = %s")
            params.append(reference_id)

        if platform:
            where_clauses.append("(i.platform = %s OR i.platform = 'all')")
            params.append(platform)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT i.id, i.category, i.reference_id, i.title, i.description,
                   i.file_path, i.sort_order, i.deep_link, i.platform
            FROM images i
            {where_sql}
            ORDER BY i.sort_order ASC, i.created_at DESC
            LIMIT %s
            """,
            params + [limit],
        )
        images = cursor.fetchall()

        return {
            "success": True,
            "data": images,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting public images: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PUBLIC_IMAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("")
def get_images(
    category: Optional[str] = Query(None, description="Filter by category"),
    reference_id: Optional[int] = Query(None, description="Filter by reference_id"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    is_active: Optional[bool] = Query(None),
    active_only: bool = Query(False, description="Hanya gambar yang sedang aktif (berdasarkan tanggal)"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all images with filters"""
    check_permission(auth, "image.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if category:
            if category not in VALID_CATEGORIES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "INVALID_CATEGORY",
                        "message": f"Kategori tidak valid. Pilihan: {', '.join(VALID_CATEGORIES)}",
                    },
                )
            where_clauses.append("i.category = %s")
            params.append(category)

        if reference_id is not None:
            where_clauses.append("i.reference_id = %s")
            params.append(reference_id)

        if platform:
            if platform not in VALID_PLATFORMS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "INVALID_PLATFORM",
                        "message": f"Platform tidak valid. Pilihan: {', '.join(VALID_PLATFORMS)}",
                    },
                )
            where_clauses.append("(i.platform = %s OR i.platform = 'all')")
            params.append(platform)

        if is_active is not None:
            where_clauses.append("i.is_active = %s")
            params.append(1 if is_active else 0)

        if active_only:
            where_clauses.append("i.is_active = 1")
            where_clauses.append(
                "(i.start_date IS NULL OR i.start_date <= NOW())"
            )
            where_clauses.append(
                "(i.end_date IS NULL OR i.end_date >= NOW())"
            )

        if search:
            where_clauses.append("(i.title LIKE %s OR i.description LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(f"SELECT COUNT(*) as total FROM images i{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT i.*, u.name as created_by_name
            FROM images i
            LEFT JOIN users u ON i.created_by = u.id
            {where_sql}
            ORDER BY i.sort_order ASC, i.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        images = cursor.fetchall()

        for img in images:
            _format_image(img)

        return {
            "success": True,
            "data": images,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting images: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_IMAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{image_id}")
def get_image(image_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get a specific image by ID"""
    check_permission(auth, "image.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT i.*, u.name as created_by_name
            FROM images i
            LEFT JOIN users u ON i.created_by = u.id
            WHERE i.id = %s
            """,
            (image_id,),
        )
        image = cursor.fetchone()

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "IMAGE_NOT_FOUND", "message": "Gambar tidak ditemukan"},
            )

        _format_image(image)

        return {
            "success": True,
            "data": image,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_IMAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile = File(...),
    category: str = Form(...),
    reference_id: Optional[int] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    sort_order: int = Form(0),
    is_active: bool = Form(True),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    deep_link: Optional[str] = Form(None),
    platform: str = Form("all"),
    auth: dict = Depends(verify_bearer_token),
):
    """Upload gambar baru"""
    check_permission(auth, "image.create")

    # Validate category
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CATEGORY",
                "message": f"Kategori tidak valid. Pilihan: {', '.join(VALID_CATEGORIES)}",
            },
        )

    # Validate platform
    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_PLATFORM",
                "message": f"Platform tidak valid. Pilihan: {', '.join(VALID_PLATFORMS)}",
            },
        )

    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_FILE_TYPE",
                "message": f"Tipe file tidak didukung. Tipe yang diizinkan: {', '.join(ALLOWED_MIME_TYPES)}",
            },
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        _ensure_upload_dir()

        # Read file content
        file_content = file.file.read()
        file_size = len(file_content)

        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "FILE_TOO_LARGE",
                    "message": f"Ukuran file melebihi batas maksimal ({MAX_FILE_SIZE // (1024 * 1024)}MB)",
                },
            )

        # Generate unique filename
        ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        unique_name = f"{category}/{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        # Ensure subdirectory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Parse dates
        parsed_start_date = None
        parsed_end_date = None
        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INVALID_DATE_FORMAT",
                            "message": "Format start_date tidak valid. Gunakan: YYYY-MM-DD atau YYYY-MM-DD HH:MM:SS",
                        },
                    )
        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INVALID_DATE_FORMAT",
                            "message": "Format end_date tidak valid. Gunakan: YYYY-MM-DD atau YYYY-MM-DD HH:MM:SS",
                        },
                    )

        # Insert to database
        cursor.execute(
            """
            INSERT INTO images
            (category, reference_id, title, description, file_path, file_name,
             file_size, mime_type, sort_order, is_active, start_date, end_date,
             deep_link, platform, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                category,
                reference_id,
                title,
                description,
                file_path,
                file.filename,
                file_size,
                file.content_type,
                sort_order,
                1 if is_active else 0,
                parsed_start_date,
                parsed_end_date,
                deep_link,
                platform,
                auth["user_id"],
                datetime.now(),
            ),
        )
        conn.commit()
        image_id = cursor.lastrowid

        return {
            "success": True,
            "message": "Gambar berhasil diupload",
            "data": {
                "id": image_id,
                "category": category,
                "file_path": file_path,
                "file_name": file.filename,
                "file_size": file_size,
                "mime_type": file.content_type,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        # Cleanup file if DB insert failed
        if "file_path" in dir() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        logger.error(f"Error uploading image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPLOAD_IMAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/multiple", status_code=status.HTTP_201_CREATED)
def upload_multiple_images(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    reference_id: Optional[int] = Form(None),
    platform: str = Form("all"),
    auth: dict = Depends(verify_bearer_token),
):
    """Upload multiple gambar sekaligus"""
    check_permission(auth, "image.create")

    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CATEGORY",
                "message": f"Kategori tidak valid. Pilihan: {', '.join(VALID_CATEGORIES)}",
            },
        )

    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_PLATFORM",
                "message": f"Platform tidak valid. Pilihan: {', '.join(VALID_PLATFORMS)}",
            },
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    uploaded = []
    saved_files = []

    try:
        _ensure_upload_dir()

        for idx, file in enumerate(files):
            if file.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "INVALID_FILE_TYPE",
                        "message": f"File '{file.filename}' memiliki tipe yang tidak didukung",
                    },
                )

            file_content = file.file.read()
            file_size = len(file_content)

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "FILE_TOO_LARGE",
                        "message": f"File '{file.filename}' melebihi batas maksimal ({MAX_FILE_SIZE // (1024 * 1024)}MB)",
                    },
                )

            ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            unique_name = f"{category}/{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(UPLOAD_DIR, unique_name)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(file_content)
            saved_files.append(file_path)

            cursor.execute(
                """
                INSERT INTO images
                (category, reference_id, file_path, file_name, file_size,
                 mime_type, sort_order, is_active, platform, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    category,
                    reference_id,
                    file_path,
                    file.filename,
                    file_size,
                    file.content_type,
                    idx,
                    1,
                    platform,
                    auth["user_id"],
                    datetime.now(),
                ),
            )

            uploaded.append({
                "id": cursor.lastrowid,
                "file_name": file.filename,
                "file_path": file_path,
                "file_size": file_size,
            })

        conn.commit()

        return {
            "success": True,
            "message": f"{len(uploaded)} gambar berhasil diupload",
            "data": uploaded,
        }

    except HTTPException:
        conn.rollback()
        # Cleanup saved files on error
        for fp in saved_files:
            try:
                os.remove(fp)
            except OSError:
                pass
        raise
    except Exception as e:
        conn.rollback()
        for fp in saved_files:
            try:
                os.remove(fp)
            except OSError:
                pass
        logger.error(f"Error uploading multiple images: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPLOAD_IMAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/reorder")
def reorder_images(
    category: str = Query(...),
    reference_id: Optional[int] = Query(None),
    image_ids: List[int] = Query(..., description="List of image IDs in desired order"),
    auth: dict = Depends(verify_bearer_token),
):
    """Reorder gambar berdasarkan kategori"""
    check_permission(auth, "image.update")

    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CATEGORY",
                "message": f"Kategori tidak valid. Pilihan: {', '.join(VALID_CATEGORIES)}",
            },
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        for idx, img_id in enumerate(image_ids):
            cursor.execute(
                "UPDATE images SET sort_order = %s, updated_at = %s WHERE id = %s AND category = %s",
                (idx, datetime.now(), img_id, category),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Urutan gambar berhasil diupdate",
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error reordering images: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REORDER_IMAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{image_id}")
def update_image(
    image_id: int,
    request: ImageUpdate,
    auth: dict = Depends(verify_bearer_token),
):
    """Update metadata gambar (tanpa ganti file)"""
    check_permission(auth, "image.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "IMAGE_NOT_FOUND", "message": "Gambar tidak ditemukan"},
            )

        # Validate category if provided
        if request.category and request.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_CATEGORY",
                    "message": f"Kategori tidak valid. Pilihan: {', '.join(VALID_CATEGORIES)}",
                },
            )

        # Validate platform if provided
        if request.platform and request.platform not in VALID_PLATFORMS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_PLATFORM",
                    "message": f"Platform tidak valid. Pilihan: {', '.join(VALID_PLATFORMS)}",
                },
            )

        # Build update query
        update_fields = []
        params = []

        for field in ["category", "title", "description", "deep_link", "platform"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"{field} = %s")
                params.append(value)

        if request.reference_id is not None:
            update_fields.append("reference_id = %s")
            params.append(request.reference_id)

        if request.sort_order is not None:
            update_fields.append("sort_order = %s")
            params.append(request.sort_order)

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if request.start_date is not None:
            try:
                parsed = datetime.strptime(request.start_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed = datetime.strptime(request.start_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INVALID_DATE_FORMAT",
                            "message": "Format start_date tidak valid",
                        },
                    )
            update_fields.append("start_date = %s")
            params.append(parsed)

        if request.end_date is not None:
            try:
                parsed = datetime.strptime(request.end_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed = datetime.strptime(request.end_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "INVALID_DATE_FORMAT",
                            "message": "Format end_date tidak valid",
                        },
                    )
            update_fields.append("end_date = %s")
            params.append(parsed)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(image_id)

        cursor.execute(
            f"UPDATE images SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Gambar berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_IMAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{image_id}/replace", status_code=status.HTTP_200_OK)
def replace_image_file(
    image_id: int,
    file: UploadFile = File(...),
    auth: dict = Depends(verify_bearer_token),
):
    """Ganti file gambar tanpa mengubah metadata"""
    check_permission(auth, "image.update")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_FILE_TYPE",
                "message": f"Tipe file tidak didukung. Tipe yang diizinkan: {', '.join(ALLOWED_MIME_TYPES)}",
            },
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "IMAGE_NOT_FOUND", "message": "Gambar tidak ditemukan"},
            )

        file_content = file.file.read()
        file_size = len(file_content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "FILE_TOO_LARGE",
                    "message": f"Ukuran file melebihi batas maksimal ({MAX_FILE_SIZE // (1024 * 1024)}MB)",
                },
            )

        _ensure_upload_dir()

        # Generate new file path
        ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        unique_name = f"{image['category']}/{uuid.uuid4().hex}{ext}"
        new_file_path = os.path.join(UPLOAD_DIR, unique_name)
        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)

        # Save new file
        with open(new_file_path, "wb") as f:
            f.write(file_content)

        # Update database
        old_file_path = image["file_path"]
        cursor.execute(
            """
            UPDATE images
            SET file_path = %s, file_name = %s, file_size = %s, mime_type = %s, updated_at = %s
            WHERE id = %s
            """,
            (new_file_path, file.filename, file_size, file.content_type, datetime.now(), image_id),
        )
        conn.commit()

        # Delete old file
        if old_file_path and os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
            except OSError:
                logger.warning(f"Failed to delete old file: {old_file_path}")

        return {
            "success": True,
            "message": "File gambar berhasil diganti",
            "data": {
                "id": image_id,
                "file_path": new_file_path,
                "file_name": file.filename,
                "file_size": file_size,
                "mime_type": file.content_type,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error replacing image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REPLACE_IMAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{image_id}")
def delete_image(image_id: int, auth: dict = Depends(verify_bearer_token)):
    """Hapus gambar (soft delete - set is_active = 0)"""
    check_permission(auth, "image.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM images WHERE id = %s", (image_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "IMAGE_NOT_FOUND", "message": "Gambar tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE images SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), image_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Gambar berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_IMAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{image_id}/permanent")
def delete_image_permanent(image_id: int, auth: dict = Depends(verify_bearer_token)):
    """Hapus gambar permanen (hapus file & record dari database)"""
    check_permission(auth, "image.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "IMAGE_NOT_FOUND", "message": "Gambar tidak ditemukan"},
            )

        # Delete from database
        cursor.execute("DELETE FROM images WHERE id = %s", (image_id,))
        conn.commit()

        # Delete file from storage
        if image["file_path"] and os.path.exists(image["file_path"]):
            try:
                os.remove(image["file_path"])
            except OSError:
                logger.warning(f"Failed to delete file: {image['file_path']}")

        return {
            "success": True,
            "message": "Gambar berhasil dihapus permanen",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error permanently deleting image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_IMAGE_PERMANENT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
