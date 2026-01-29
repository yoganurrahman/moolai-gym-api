"""
Trainer Dashboard Router - Jadwal kelas & ringkasan harian trainer
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Trainer - Dashboard"])


def _get_trainer_id(cursor, user_id: int) -> int:
    """Get trainer record from user_id, raise 403 if not a trainer"""
    cursor.execute("SELECT id FROM trainers WHERE user_id = %s AND is_active = 1", (user_id,))
    trainer = cursor.fetchone()
    if not trainer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "NOT_A_TRAINER", "message": "Anda bukan trainer aktif"},
        )
    return trainer["id"]


@router.get("/summary")
def get_dashboard_summary(auth: dict = Depends(verify_bearer_token)):
    """Get trainer dashboard summary (today's stats)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])
        today = date.today()

        # Today's PT bookings
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status = 'booked' THEN 1 END) as upcoming,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
            FROM pt_bookings
            WHERE trainer_id = %s AND booking_date = %s
            """,
            (trainer_id, today),
        )
        pt_today = cursor.fetchone()

        # This week's PT bookings
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status = 'booked' THEN 1 END) as upcoming,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
            FROM pt_bookings
            WHERE trainer_id = %s AND booking_date BETWEEN %s AND %s
            """,
            (trainer_id, week_start, week_end),
        )
        pt_week = cursor.fetchone()

        # Today's class schedules
        day_of_week = today.weekday() + 1  # 0=Sunday in DB, Python monday=0
        if day_of_week == 7:
            day_of_week = 0
        cursor.execute(
            """
            SELECT COUNT(*) as total
            FROM class_schedules
            WHERE trainer_id = %s AND day_of_week = %s AND is_active = 1
            """,
            (trainer_id, day_of_week),
        )
        classes_today = cursor.fetchone()["total"]

        # Active clients (unique members with active PT sessions)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT user_id) as total
            FROM member_pt_sessions
            WHERE trainer_id = %s AND status = 'active'
            """,
            (trainer_id,),
        )
        active_clients = cursor.fetchone()["total"]

        return {
            "success": True,
            "data": {
                "today": {
                    "pt_bookings": pt_today["total"],
                    "pt_upcoming": pt_today["upcoming"],
                    "pt_completed": pt_today["completed"],
                    "classes": classes_today,
                },
                "this_week": {
                    "pt_total": pt_week["total"],
                    "pt_upcoming": pt_week["upcoming"],
                    "pt_completed": pt_week["completed"],
                },
                "active_clients": active_clients,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_DASHBOARD_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-schedule")
def get_my_class_schedule(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get trainer's class schedules"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        if not date_from:
            date_from = date.today()
        if not date_to:
            date_to = date_from + timedelta(days=7)

        # Get recurring schedules
        cursor.execute(
            """
            SELECT cs.*, ct.name as class_name, ct.description as class_description
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            WHERE cs.trainer_id = %s AND cs.is_active = 1 AND cs.is_recurring = 1
            ORDER BY cs.day_of_week ASC, cs.start_time ASC
            """,
            (trainer_id,),
        )
        recurring = cursor.fetchall()

        # Build schedule per date
        schedule_by_date = []
        current = date_from
        day_names = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']

        while current <= date_to:
            day_of_week = current.weekday() + 1
            if day_of_week == 7:
                day_of_week = 0

            day_classes = []
            for s in recurring:
                if s["day_of_week"] == day_of_week:
                    # Count bookings for this schedule on this date
                    cursor.execute(
                        """
                        SELECT COUNT(*) as booked
                        FROM class_bookings
                        WHERE schedule_id = %s AND class_date = %s AND status IN ('booked', 'attended')
                        """,
                        (s["id"], current),
                    )
                    booked = cursor.fetchone()["booked"]

                    day_classes.append({
                        "schedule_id": s["id"],
                        "class_name": s["class_name"],
                        "start_time": str(s["start_time"]),
                        "end_time": str(s["end_time"]),
                        "room": s["room"],
                        "capacity": s["capacity"],
                        "booked": booked,
                    })

            if day_classes:
                schedule_by_date.append({
                    "date": str(current),
                    "day_name": day_names[day_of_week],
                    "classes": day_classes,
                })

            current += timedelta(days=1)

        return {
            "success": True,
            "data": schedule_by_date,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SCHEDULE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-schedule/{schedule_id}/attendees")
def get_class_attendees(
    schedule_id: int,
    class_date: date = Query(...),
    auth: dict = Depends(verify_bearer_token),
):
    """Get attendee list for a specific class session"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Verify this schedule belongs to this trainer
        cursor.execute(
            "SELECT id FROM class_schedules WHERE id = %s AND trainer_id = %s",
            (schedule_id, trainer_id),
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_YOUR_CLASS", "message": "Kelas ini bukan milik Anda"},
            )

        # Get attendees
        cursor.execute(
            """
            SELECT cb.id as booking_id, cb.status, cb.booked_at, cb.attended_at,
                   u.name as member_name, u.email as member_email, u.phone as member_phone
            FROM class_bookings cb
            JOIN users u ON cb.user_id = u.id
            WHERE cb.schedule_id = %s AND cb.class_date = %s AND cb.status IN ('booked', 'attended')
            ORDER BY cb.booked_at ASC
            """,
            (schedule_id, class_date),
        )
        attendees = cursor.fetchall()

        return {
            "success": True,
            "data": attendees,
            "total": len(attendees),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting class attendees: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_ATTENDEES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
