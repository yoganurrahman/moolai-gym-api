"""
Trainers Router - List Trainers
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trainers", tags=["CMS - Trainers"])


# ============== Request Models ==============

class TrainerCreate(BaseModel):
    user_id: int
    specialization: Optional[str] = None
    bio: Optional[str] = None
    experience_years: int = Field(0, ge=0)
    rate_per_session: Optional[float] = Field(None, gt=0)
    commission_percentage: float = Field(0, ge=0, le=100)


class TrainerUpdate(BaseModel):
    specialization: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0)
    rate_per_session: Optional[float] = Field(None, gt=0)
    commission_percentage: Optional[float] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


# ============== Public Endpoints ==============

@router.get("")
def get_trainers(
    specialization: Optional[str] = Query(None),
    is_active: bool = Query(True),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all trainers"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if is_active:
            where_clauses.append("t.is_active = 1")

        if specialization:
            where_clauses.append("t.specialization LIKE %s")
            params.append(f"%{specialization}%")

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cursor.execute(
            f"""
            SELECT t.*, u.name, u.email, u.phone, u.avatar
            FROM trainers t
            JOIN users u ON t.user_id = u.id
            {where_sql}
            ORDER BY u.name ASC
            """,
            params,
        )
        trainers = cursor.fetchall()

        # Format response
        for trainer in trainers:
            trainer["rate_per_session"] = float(trainer["rate_per_session"]) if trainer.get("rate_per_session") else None
            trainer["commission_percentage"] = float(trainer["commission_percentage"]) if trainer.get("commission_percentage") else 0
            if trainer.get("certifications"):
                import json
                trainer["certifications"] = json.loads(trainer["certifications"]) if isinstance(trainer["certifications"], str) else trainer["certifications"]

        return {
            "success": True,
            "data": trainers,
        }

    except Exception as e:
        logger.error(f"Error getting trainers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TRAINERS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/{trainer_id}")
def get_trainer(trainer_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get trainer detail"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT t.*, u.name, u.email, u.phone, u.avatar
            FROM trainers t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s
            """,
            (trainer_id,),
        )
        trainer = cursor.fetchone()

        if not trainer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        # Get PT packages
        cursor.execute(
            """
            SELECT * FROM pt_packages
            WHERE (trainer_id = %s OR trainer_id IS NULL) AND is_active = 1
            ORDER BY session_count ASC
            """,
            (trainer_id,),
        )
        trainer["pt_packages"] = cursor.fetchall()

        for pkg in trainer["pt_packages"]:
            pkg["price"] = float(pkg["price"]) if pkg.get("price") else 0

        # Get class schedules
        cursor.execute(
            """
            SELECT cs.*, ct.name as class_name, ct.color
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            WHERE cs.trainer_id = %s AND cs.is_active = 1
            ORDER BY cs.day_of_week, cs.start_time
            """,
            (trainer_id,),
        )
        trainer["class_schedules"] = cursor.fetchall()

        trainer["rate_per_session"] = float(trainer["rate_per_session"]) if trainer.get("rate_per_session") else None
        trainer["commission_percentage"] = float(trainer["commission_percentage"]) if trainer.get("commission_percentage") else 0

        return {
            "success": True,
            "data": trainer,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TRAINER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== CMS Endpoints ==============

@router.post("", status_code=status.HTTP_201_CREATED)
def create_trainer(request: TrainerCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new trainer (CMS)"""
    check_permission(auth, "trainer.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if user exists
        cursor.execute("SELECT id, role_id FROM users WHERE id = %s", (request.user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Check if already a trainer
        cursor.execute("SELECT id FROM trainers WHERE user_id = %s", (request.user_id,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ALREADY_TRAINER", "message": "User sudah terdaftar sebagai trainer"},
            )

        # Create trainer
        cursor.execute(
            """
            INSERT INTO trainers
            (user_id, specialization, bio, experience_years, rate_per_session, commission_percentage, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.user_id,
                request.specialization,
                request.bio,
                request.experience_years,
                request.rate_per_session,
                request.commission_percentage,
                datetime.now(),
            ),
        )
        trainer_id = cursor.lastrowid

        # Update user role to trainer
        cursor.execute(
            "SELECT id FROM roles WHERE name = 'trainer'",
        )
        trainer_role = cursor.fetchone()
        if trainer_role:
            cursor.execute(
                "UPDATE users SET role_id = %s WHERE id = %s",
                (trainer_role["id"], request.user_id),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Trainer berhasil ditambahkan",
            "data": {"id": trainer_id},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating trainer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_TRAINER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/{trainer_id}")
def update_trainer(
    trainer_id: int, request: TrainerUpdate, auth: dict = Depends(verify_bearer_token)
):
    """Update a trainer (CMS)"""
    check_permission(auth, "trainer.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if trainer exists
        cursor.execute("SELECT id FROM trainers WHERE id = %s", (trainer_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        # Build update query
        update_fields = []
        params = []

        for field in ["specialization", "bio", "experience_years", "rate_per_session", "commission_percentage"]:
            value = getattr(request, field)
            if value is not None:
                update_fields.append(f"{field} = %s")
                params.append(value)

        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(trainer_id)

        cursor.execute(
            f"UPDATE trainers SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Trainer berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating trainer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_TRAINER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/{trainer_id}")
def delete_trainer(trainer_id: int, auth: dict = Depends(verify_bearer_token)):
    """Deactivate a trainer (CMS)"""
    check_permission(auth, "trainer.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM trainers WHERE id = %s", (trainer_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE trainers SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), trainer_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Trainer berhasil dinonaktifkan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting trainer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_TRAINER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
