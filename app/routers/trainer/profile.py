"""
Trainer Profile Router - Lihat dan update profil trainer sendiri
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Trainer - Profile"])


# ============== Request Models ==============

class UpdateTrainerProfile(BaseModel):
    specialization: Optional[str] = None
    bio: Optional[str] = None
    certifications: Optional[List[str]] = None


# ============== Endpoints ==============

@router.get("")
def get_my_profile(auth: dict = Depends(verify_bearer_token)):
    """Get trainer's own profile"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT t.id as trainer_id, t.specialization, t.bio, t.certifications,
                   t.experience_years, t.rate_per_session, t.commission_percentage, t.is_active,
                   u.id as user_id, u.name, u.email, u.phone, u.avatar,
                   u.date_of_birth, u.gender, u.address
            FROM trainers t
            JOIN users u ON t.user_id = u.id
            WHERE t.user_id = %s
            """,
            (auth["user_id"],),
        )
        profile = cursor.fetchone()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_A_TRAINER", "message": "Anda bukan trainer"},
            )

        # Parse certifications JSON
        if profile.get("certifications"):
            import json
            profile["certifications"] = json.loads(profile["certifications"]) if isinstance(profile["certifications"], str) else profile["certifications"]

        if profile.get("rate_per_session"):
            profile["rate_per_session"] = float(profile["rate_per_session"])
        if profile.get("commission_percentage"):
            profile["commission_percentage"] = float(profile["commission_percentage"])

        # Get assigned class schedules
        cursor.execute(
            """
            SELECT cs.id, cs.day_of_week, cs.start_time, cs.end_time, cs.room, cs.capacity,
                   ct.name as class_name,
                   br.name as branch_name, br.code as branch_code
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN branches br ON cs.branch_id = br.id
            WHERE cs.trainer_id = %s AND cs.is_active = 1
            ORDER BY cs.day_of_week ASC, cs.start_time ASC
            """,
            (profile["trainer_id"],),
        )
        schedules = cursor.fetchall()

        day_names = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
        for s in schedules:
            s["day_name"] = day_names[s["day_of_week"]]
            s["start_time"] = str(s["start_time"])
            s["end_time"] = str(s["end_time"])

        # Get assigned branches
        cursor.execute(
            """
            SELECT b.id, b.code, b.name, b.city, tb.is_primary
            FROM trainer_branches tb
            JOIN branches b ON tb.branch_id = b.id
            WHERE tb.trainer_id = %s AND b.is_active = 1
            ORDER BY tb.is_primary DESC, b.sort_order ASC
            """,
            (profile["trainer_id"],),
        )
        branches = cursor.fetchall()
        for br in branches:
            br["is_primary"] = bool(br["is_primary"])
        profile["assigned_branches"] = branches

        profile["class_schedules"] = schedules

        # Get PT stats
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_sessions_handled,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'no_show' THEN 1 END) as no_shows
            FROM pt_bookings
            WHERE trainer_id = %s
            """,
            (profile["trainer_id"],),
        )
        pt_stats = cursor.fetchone()
        profile["pt_stats"] = pt_stats

        return {
            "success": True,
            "data": profile,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PROFILE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("")
def update_my_profile(
    request: UpdateTrainerProfile,
    auth: dict = Depends(verify_bearer_token),
):
    """Update trainer's own profile (specialization, bio, certifications)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check trainer exists
        cursor.execute(
            "SELECT id FROM trainers WHERE user_id = %s AND is_active = 1",
            (auth["user_id"],),
        )
        trainer = cursor.fetchone()
        if not trainer:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_A_TRAINER", "message": "Anda bukan trainer aktif"},
            )

        # Build update
        update_fields = []
        params = []

        if request.specialization is not None:
            update_fields.append("specialization = %s")
            params.append(request.specialization)

        if request.bio is not None:
            update_fields.append("bio = %s")
            params.append(request.bio)

        if request.certifications is not None:
            import json
            update_fields.append("certifications = %s")
            params.append(json.dumps(request.certifications))

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(trainer["id"])

        cursor.execute(
            f"UPDATE trainers SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Profil trainer berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating trainer profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_PROFILE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
