"""
Trainer Dashboard Router - Jadwal kelas & ringkasan harian trainer
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel

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
        pt_today_where = "pb.trainer_id = %s AND pb.booking_date = %s"
        pt_today_params = [trainer_id, today]
        if branch_id:
            pt_today_where += " AND pb.branch_id = %s"
            pt_today_params.append(branch_id)
        pt_today_where += " AND pb.status IN ('booked', 'attended', 'no_show')"

        cursor.execute(
            f"""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN pb.status = 'booked' THEN 1 END) as upcoming,
                   COUNT(CASE WHEN pb.status = 'attended' THEN 1 END) as completed
            FROM pt_bookings pb
            WHERE {pt_today_where}
            """,
            pt_today_params,
        )
        pt_today = cursor.fetchone()

        # This week's PT bookings
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        pt_week_where = "pb.trainer_id = %s AND pb.booking_date BETWEEN %s AND %s"
        pt_week_params = [trainer_id, week_start, week_end]
        if branch_id:
            pt_week_where += " AND pb.branch_id = %s"
            pt_week_params.append(branch_id)
        pt_week_where += " AND pb.status IN ('booked', 'attended', 'no_show')"

        cursor.execute(
            f"""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN pb.status = 'booked' THEN 1 END) as upcoming,
                   COUNT(CASE WHEN pb.status = 'attended' THEN 1 END) as completed
            FROM pt_bookings pb
            WHERE {pt_week_where}
            """,
            pt_week_params,
        )
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
            WHERE cb.schedule_id = %s AND cb.class_date = %s AND cb.status IN ('booked', 'attended', 'no_show')
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


@router.get("/statistics")
def get_trainer_statistics(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get trainer performance statistics for a date range"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        if not date_to:
            date_to = date.today()
        if not date_from:
            date_from = date_to - timedelta(days=29)

        # PT booking summary
        cursor.execute(
            """
            SELECT
                COUNT(CASE WHEN status IN ('booked', 'attended', 'no_show') THEN 1 END) as total_pt_sessions,
                COUNT(CASE WHEN status = 'attended' THEN 1 END) as attended,
                COUNT(CASE WHEN status = 'no_show' THEN 1 END) as no_show,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
                COUNT(CASE WHEN status = 'booked' THEN 1 END) as booked,
                COUNT(
                    CASE
                        WHEN status = 'booked' AND TIMESTAMP(booking_date, end_time) < NOW() THEN 1
                    END
                ) as pt_pending_update
            FROM pt_bookings
            WHERE trainer_id = %s AND booking_date BETWEEN %s AND %s
            """,
            (trainer_id, date_from, date_to),
        )
        pt_summary = cursor.fetchone()

        done = pt_summary["attended"] + pt_summary["no_show"]
        attendance_rate = round((pt_summary["attended"] / done * 100), 1) if done > 0 else 0

        # Class session stats
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_class_bookings,
                COUNT(CASE WHEN cb.status = 'attended' THEN 1 END) as class_attended,
                COUNT(CASE WHEN cb.status = 'no_show' THEN 1 END) as class_no_show,
                COUNT(
                    CASE
                        WHEN cb.status = 'booked'
                             AND TIMESTAMP(cb.class_date, cs.end_time) < NOW() THEN 1
                    END
                ) as class_pending_update
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            WHERE cs.trainer_id = %s AND cb.class_date BETWEEN %s AND %s
            """,
            (trainer_id, date_from, date_to),
        )
        class_summary = cursor.fetchone()

        # Count unique class sessions (distinct schedule+date combos)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT CONCAT(cb.schedule_id, '-', cb.class_date)) as total_class_sessions
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            WHERE cs.trainer_id = %s AND cb.class_date BETWEEN %s AND %s
                AND cb.status IN ('booked', 'attended', 'no_show')
            """,
            (trainer_id, date_from, date_to),
        )
        total_class_sessions = cursor.fetchone()["total_class_sessions"]

        # Commission info
        cursor.execute(
            "SELECT rate_per_session, commission_percentage FROM trainers WHERE id = %s",
            (trainer_id,),
        )
        trainer_info = cursor.fetchone()
        rate = float(trainer_info["rate_per_session"] or 0)
        commission_pct = float(trainer_info["commission_percentage"] or 0)
        commission_sessions = (
            pt_summary["attended"] + pt_summary["no_show"] + pt_summary["pt_pending_update"]
        )
        estimated_earnings = round(rate * commission_sessions * commission_pct / 100)

        # PT by period (daily breakdown)
        cursor.execute(
            """
            SELECT
                booking_date as date,
                COUNT(CASE WHEN status = 'attended' THEN 1 END) as attended,
                COUNT(CASE WHEN status = 'no_show' THEN 1 END) as no_show,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled
            FROM pt_bookings
            WHERE trainer_id = %s AND booking_date BETWEEN %s AND %s
            GROUP BY booking_date
            ORDER BY booking_date DESC
            """,
            (trainer_id, date_from, date_to),
        )
        pt_by_period = cursor.fetchall()
        for row in pt_by_period:
            row["date"] = str(row["date"])

        # Top clients
        cursor.execute(
            """
            SELECT u.name as member_name,
                   COUNT(*) as total_sessions,
                   COUNT(CASE WHEN pb.status = 'attended' THEN 1 END) as attended,
                   COUNT(CASE WHEN pb.status = 'no_show' THEN 1 END) as no_show
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            WHERE pb.trainer_id = %s AND pb.booking_date BETWEEN %s AND %s
                AND pb.status IN ('attended', 'no_show', 'booked')
            GROUP BY pb.user_id, u.name
            ORDER BY total_sessions DESC
            LIMIT 5
            """,
            (trainer_id, date_from, date_to),
        )
        top_clients = cursor.fetchall()

        return {
            "success": True,
            "data": {
                "summary": {
                    "total_pt_sessions": pt_summary["total_pt_sessions"],
                    "attended": pt_summary["attended"],
                    "no_show": pt_summary["no_show"],
                    "cancelled": pt_summary["cancelled"],
                    "booked": pt_summary["booked"],
                    "attendance_rate": attendance_rate,
                    "pt_pending_update": pt_summary["pt_pending_update"],
                    "total_class_sessions": total_class_sessions,
                    "class_attended": class_summary["class_attended"],
                    "class_no_show": class_summary["class_no_show"],
                    "class_pending_update": class_summary["class_pending_update"],
                },
                "commission": {
                    "rate_per_session": rate,
                    "commission_percentage": commission_pct,
                    "session_count": commission_sessions,
                    "estimated_earnings": estimated_earnings,
                },
                "pt_by_period": pt_by_period,
                "top_clients": top_clients,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_STATISTICS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/class-bookings/{booking_id}/attend")
def mark_class_attended(
    booking_id: int,
    auth: dict = Depends(verify_bearer_token),
):
    """Mark a class booking as attended"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Get booking and verify it belongs to this trainer's class
        cursor.execute(
            """
            SELECT cb.id, cb.status, u.name as member_name, cs.trainer_id
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN users u ON cb.user_id = u.id
            WHERE cb.id = %s AND cb.status = 'booked'
            """,
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

        if booking["trainer_id"] != trainer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_YOUR_CLASS", "message": "Kelas ini bukan milik Anda"},
            )

        # Update to attended
        cursor.execute(
            """
            UPDATE class_bookings
            SET status = 'attended', attended_at = %s, completed_by = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), auth["user_id"], datetime.now(), booking_id),
        )

        conn.commit()

        return {
            "success": True,
            "message": f"{booking['member_name']} berhasil ditandai hadir",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking class attended: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MARK_ATTENDED_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/class-bookings/{booking_id}/no-show")
def mark_class_no_show(
    booking_id: int,
    auth: dict = Depends(verify_bearer_token),
):
    """Mark a class booking as no-show"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Get booking and verify it belongs to this trainer's class
        cursor.execute(
            """
            SELECT cb.id, cb.status, u.name as member_name, cs.trainer_id
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN users u ON cb.user_id = u.id
            WHERE cb.id = %s AND cb.status = 'booked'
            """,
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

        if booking["trainer_id"] != trainer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_YOUR_CLASS", "message": "Kelas ini bukan milik Anda"},
            )

        # Update to no_show
        cursor.execute(
            """
            UPDATE class_bookings
            SET status = 'no_show', updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking_id),
        )

        conn.commit()

        return {
            "success": True,
            "message": f"{booking['member_name']} ditandai tidak hadir",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking class no-show: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MARK_NO_SHOW_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/pt-bookings/{booking_id}/attend")
def mark_pt_attended(
    booking_id: int,
    auth: dict = Depends(verify_bearer_token),
):
    """Mark a PT booking as attended"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Get booking and verify it belongs to this trainer
        cursor.execute(
            """
            SELECT pb.id, pb.status, u.name as member_name, pb.trainer_id
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            WHERE pb.id = %s AND pb.status = 'booked'
            """,
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

        if booking["trainer_id"] != trainer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_YOUR_BOOKING", "message": "Booking ini bukan milik Anda"},
            )

        # Update to attended
        cursor.execute(
            """
            UPDATE pt_bookings
            SET status = 'attended', attended_at = %s, completed_by = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), auth["user_id"], datetime.now(), booking_id),
        )

        conn.commit()

        return {
            "success": True,
            "message": f"{booking['member_name']} berhasil ditandai hadir",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking PT attended: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MARK_PT_ATTENDED_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/pt-bookings/{booking_id}/no-show")
def mark_pt_no_show(
    booking_id: int,
    auth: dict = Depends(verify_bearer_token),
):
    """Mark a PT booking as no-show"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Get booking and verify it belongs to this trainer
        cursor.execute(
            """
            SELECT pb.id, pb.status, u.name as member_name, pb.trainer_id
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            WHERE pb.id = %s AND pb.status = 'booked'
            """,
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

        if booking["trainer_id"] != trainer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "NOT_YOUR_BOOKING", "message": "Booking ini bukan milik Anda"},
            )

        # Update to no_show
        cursor.execute(
            """
            UPDATE pt_bookings
            SET status = 'no_show', updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking_id),
        )

        conn.commit()

        return {
            "success": True,
            "message": f"{booking['member_name']} ditandai tidak hadir",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking PT no-show: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MARK_PT_NO_SHOW_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


class TrainerScanQRRequest(BaseModel):
    token: str


@router.post("/scan-qr")
def trainer_scan_qr(
    request: TrainerScanQRRequest,
    auth: dict = Depends(verify_bearer_token),
):
    """Trainer scans member QR to mark attendance for class or PT"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Look up token
        cursor.execute(
            """
            SELECT cqt.*, u.name as member_name, u.email as member_email
            FROM checkin_qr_tokens cqt
            JOIN users u ON cqt.user_id = u.id
            WHERE cqt.token = %s
            """,
            (request.token,),
        )
        token_row = cursor.fetchone()

        if not token_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "QR_TOKEN_INVALID", "message": "QR code tidak valid"},
            )

        if token_row["is_used"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "QR_TOKEN_USED", "message": "QR code sudah digunakan"},
            )

        if token_row["expires_at"] < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "QR_TOKEN_EXPIRED", "message": "QR code sudah expired, minta member generate ulang"},
            )

        checkin_type = token_row["checkin_type"]
        booking_id = token_row["booking_id"]

        # Mark token as used
        cursor.execute(
            "UPDATE checkin_qr_tokens SET is_used = 1, used_at = %s WHERE id = %s",
            (datetime.now(), token_row["id"]),
        )

        # Check if already checked in → auto-detect checkout
        cursor.execute(
            """
            SELECT mc.id, mc.checkin_type, mc.checkin_time
            FROM member_checkins mc
            WHERE mc.user_id = %s AND mc.checkout_time IS NULL
            ORDER BY mc.checkin_time DESC LIMIT 1
            """,
            (token_row["user_id"],),
        )
        active_checkin = cursor.fetchone()

        if active_checkin:
            # ── CHECKOUT FLOW ──
            checkout_time = datetime.now()
            cursor.execute(
                "UPDATE member_checkins SET checkout_time = %s WHERE id = %s",
                (checkout_time, active_checkin["id"]),
            )
            conn.commit()

            duration_minutes = int((checkout_time - active_checkin["checkin_time"]).total_seconds() / 60)

            return {
                "success": True,
                "message": f"Check-out berhasil untuk {token_row['member_name']}",
                "data": {
                    "action": "checkout",
                    "checkin_type": active_checkin["checkin_type"],
                    "member_name": token_row["member_name"],
                    "booking_id": booking_id,
                    "checkin_time": active_checkin["checkin_time"].isoformat(),
                    "checkout_time": checkout_time.isoformat(),
                    "duration_minutes": duration_minutes,
                },
            }

        # ── CHECKIN FLOW ──
        if checkin_type not in ("class_only", "pt"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_TYPE", "message": "QR ini untuk check-in gym, bukan untuk kelas/PT. Gunakan scan di CMS."},
            )

        if not booking_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "NO_BOOKING", "message": "QR token tidak memiliki booking_id"},
            )

        response_data = {
            "checkin_type": checkin_type,
            "member_name": token_row["member_name"],
            "booking_id": booking_id,
        }

        if checkin_type == "class_only":
            # Verify booking belongs to trainer's class
            cursor.execute(
                """
                SELECT cb.id, cb.status, cb.schedule_id, cb.class_date,
                       cs.trainer_id, cs.start_time, cs.end_time,
                       ct.name as class_name
                FROM class_bookings cb
                JOIN class_schedules cs ON cb.schedule_id = cs.id
                JOIN class_types ct ON cs.class_type_id = ct.id
                WHERE cb.id = %s AND cb.user_id = %s AND cb.status = 'booked'
                """,
                (booking_id, token_row["user_id"]),
            )
            booking = cursor.fetchone()

            if not booking:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan atau sudah diproses"},
                )

            if booking["trainer_id"] != trainer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error_code": "NOT_YOUR_CLASS", "message": "Booking ini bukan untuk kelas Anda"},
                )

            # Check timing setting
            cursor.execute(
                "SELECT `value` FROM settings WHERE `key` = 'class_checkin_before_minutes'"
            )
            setting_row = cursor.fetchone()
            before_minutes = int(setting_row["value"]) if setting_row else 0

            if before_minutes > 0:
                now = datetime.now()
                start_time = booking["start_time"]
                if hasattr(start_time, "total_seconds"):
                    total_sec = int(start_time.total_seconds())
                    start_hour = total_sec // 3600
                    start_minute = (total_sec % 3600) // 60
                else:
                    parts = str(start_time).split(":")
                    start_hour = int(parts[0])
                    start_minute = int(parts[1])

                class_date = booking["class_date"]
                if isinstance(class_date, str):
                    class_date = datetime.strptime(class_date, "%Y-%m-%d").date()
                class_start = datetime(class_date.year, class_date.month, class_date.day, start_hour, start_minute)
                earliest = class_start - timedelta(minutes=before_minutes)

                if now < earliest:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "TOO_EARLY",
                            "message": f"Scan bisa dilakukan mulai {before_minutes} menit sebelum kelas ({start_hour:02d}:{start_minute:02d})",
                        },
                    )

            # Mark attended
            cursor.execute(
                "UPDATE class_bookings SET status = 'attended', attended_at = %s, completed_by = %s WHERE id = %s",
                (datetime.now(), auth["user_id"], booking_id),
            )

            response_data["class_name"] = booking["class_name"]

        elif checkin_type == "pt":
            # Verify PT booking belongs to this trainer
            cursor.execute(
                """
                SELECT pb.id, pb.status, pb.trainer_id, pb.booking_date,
                       pb.start_time, pb.end_time, pb.member_pt_session_id,
                       u.name as member_name
                FROM pt_bookings pb
                JOIN users u ON pb.user_id = u.id
                WHERE pb.id = %s AND pb.user_id = %s AND pb.status = 'booked'
                """,
                (booking_id, token_row["user_id"]),
            )
            pt_booking = cursor.fetchone()

            if not pt_booking:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking PT tidak ditemukan atau sudah diproses"},
                )

            if pt_booking["trainer_id"] != trainer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error_code": "NOT_YOUR_BOOKING", "message": "Booking PT ini bukan milik Anda"},
                )

            # Check timing setting
            cursor.execute(
                "SELECT `value` FROM settings WHERE `key` = 'pt_checkin_before_minutes'"
            )
            setting_row = cursor.fetchone()
            before_minutes = int(setting_row["value"]) if setting_row else 0

            if before_minutes > 0:
                now = datetime.now()
                start_time = pt_booking["start_time"]
                if hasattr(start_time, "total_seconds"):
                    total_sec = int(start_time.total_seconds())
                    start_hour = total_sec // 3600
                    start_minute = (total_sec % 3600) // 60
                else:
                    parts = str(start_time).split(":")
                    start_hour = int(parts[0])
                    start_minute = int(parts[1])

                booking_date = pt_booking["booking_date"]
                if isinstance(booking_date, str):
                    booking_date = datetime.strptime(booking_date, "%Y-%m-%d").date()
                session_start = datetime(booking_date.year, booking_date.month, booking_date.day, start_hour, start_minute)
                earliest = session_start - timedelta(minutes=before_minutes)

                if now < earliest:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "TOO_EARLY",
                            "message": f"Scan bisa dilakukan mulai {before_minutes} menit sebelum sesi PT ({start_hour:02d}:{start_minute:02d})",
                        },
                    )

            # Mark attended
            cursor.execute(
                "UPDATE pt_bookings SET status = 'attended', attended_at = %s, completed_by = %s, updated_at = %s WHERE id = %s",
                (datetime.now(), auth["user_id"], datetime.now(), booking_id),
            )

        conn.commit()

        response_data["action"] = "checkin"

        return {
            "success": True,
            "message": f"Kehadiran {token_row['member_name']} berhasil dicatat",
            "data": response_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during trainer QR scan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SCAN_QR_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/checkin-settings")
def get_checkin_settings(
    auth: dict = Depends(verify_bearer_token),
):
    """Get check-in timing settings for trainer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        _get_trainer_id(cursor, auth["user_id"])

        cursor.execute(
            "SELECT `key`, `value` FROM settings WHERE `key` IN "
            "('class_checkin_before_minutes', 'pt_checkin_before_minutes')"
        )
        rows = cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}

        return {
            "success": True,
            "data": {
                "class_checkin_before_minutes": int(settings.get("class_checkin_before_minutes", "0")),
                "pt_checkin_before_minutes": int(settings.get("pt_checkin_before_minutes", "0")),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting checkin settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SETTINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
