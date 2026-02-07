"""
Trainer Dashboard Router - Jadwal kelas & ringkasan harian trainer
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.db import get_db_connection
from app.middleware import verify_bearer_token, get_branch_id

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
def get_dashboard_summary(
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get trainer dashboard summary (today's stats)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])
        today = date.today()

        # Today's PT bookings
        pt_today_sql = """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN pb.status = 'booked' THEN 1 END) as upcoming,
                   COUNT(CASE WHEN pb.status = 'completed' THEN 1 END) as completed
            FROM pt_bookings pb
            WHERE pb.trainer_id = %s AND pb.booking_date = %s
        """
        pt_today_params = [trainer_id, today]
        if branch_id:
            pt_today_sql += " AND pb.branch_id = %s"
            pt_today_params.append(branch_id)
        cursor.execute(pt_today_sql, pt_today_params)
        pt_today = cursor.fetchone()

        # This week's PT bookings
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        pt_week_sql = """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN pb.status = 'booked' THEN 1 END) as upcoming,
                   COUNT(CASE WHEN pb.status = 'completed' THEN 1 END) as completed
            FROM pt_bookings pb
            WHERE pb.trainer_id = %s AND pb.booking_date BETWEEN %s AND %s
        """
        pt_week_params = [trainer_id, week_start, week_end]
        if branch_id:
            pt_week_sql += " AND pb.branch_id = %s"
            pt_week_params.append(branch_id)
        cursor.execute(pt_week_sql, pt_week_params)
        pt_week = cursor.fetchone()

        # Today's class schedules
        day_of_week = today.weekday() + 1  # 0=Sunday in DB, Python monday=0
        if day_of_week == 7:
            day_of_week = 0
        classes_today_sql = """
            SELECT COUNT(*) as total
            FROM class_schedules cs
            WHERE cs.trainer_id = %s AND cs.day_of_week = %s AND cs.is_active = 1
        """
        classes_today_params = [trainer_id, day_of_week]
        if branch_id:
            classes_today_sql += " AND cs.branch_id = %s"
            classes_today_params.append(branch_id)
        cursor.execute(classes_today_sql, classes_today_params)
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

        # Trainer profile image from images table
        cursor.execute(
            """
            SELECT file_path FROM images
            WHERE category = 'pt' AND reference_id = %s AND is_active = 1
            ORDER BY sort_order ASC, id ASC LIMIT 1
            """,
            (trainer_id,),
        )
        img_row = cursor.fetchone()
        trainer_image = img_row["file_path"] if img_row else None

        return {
            "success": True,
            "data": {
                "trainer_image": trainer_image,
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
    branch_id: Optional[int] = Depends(get_branch_id),
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
        recurring_sql = """
            SELECT cs.*, ct.name as class_name, ct.description as class_description,
                   COALESCE(
                       (SELECT file_path FROM images
                        WHERE category = 'class' AND reference_id = ct.id AND is_active = 1
                        ORDER BY sort_order ASC, id ASC LIMIT 1),
                       ct.image
                   ) as class_image,
                   br.name as branch_name, br.code as branch_code
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN branches br ON cs.branch_id = br.id
            WHERE cs.trainer_id = %s AND cs.is_active = 1 AND cs.is_recurring = 1
        """
        recurring_params = [trainer_id]
        if branch_id:
            recurring_sql += " AND cs.branch_id = %s"
            recurring_params.append(branch_id)
        recurring_sql += " ORDER BY cs.day_of_week ASC, cs.start_time ASC"
        cursor.execute(recurring_sql, recurring_params)
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
                        "class_type_id": s["class_type_id"],
                        "class_name": s["class_name"],
                        "class_image": s.get("class_image"),
                        "start_time": str(s["start_time"]),
                        "end_time": str(s["end_time"]),
                        "room": s["room"],
                        "capacity": s["capacity"],
                        "booked": booked,
                        "branch_name": s["branch_name"],
                        "branch_code": s["branch_code"],
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
