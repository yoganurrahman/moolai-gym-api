"""
Trainer PT Router - Personal Training management dari sisi trainer
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel

from app.db import get_db_connection
from app.middleware import verify_bearer_token, get_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pt", tags=["Trainer - Personal Training"])


# ============== Request Models ==============

class CompleteSessionRequest(BaseModel):
    notes: Optional[str] = None


# ============== Helper ==============

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


# ============== Endpoints ==============

@router.get("/bookings")
def get_my_pt_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get PT bookings assigned to this trainer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        where_clauses = ["pb.trainer_id = %s"]
        params = [trainer_id]

        if status_filter:
            where_clauses.append("pb.status = %s")
            params.append(status_filter)

        if date_from:
            where_clauses.append("pb.booking_date >= %s")
            params.append(date_from)
        else:
            # Default: from today
            where_clauses.append("pb.booking_date >= %s")
            params.append(date.today())

        if date_to:
            where_clauses.append("pb.booking_date <= %s")
            params.append(date_to)

        if branch_id:
            where_clauses.append("pb.branch_id = %s")
            params.append(branch_id)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        # Count
        cursor.execute(f"SELECT COUNT(*) as total FROM pt_bookings pb{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT pb.*, u.name as member_name, u.email as member_email, u.phone as member_phone,
                   pp.name as package_name, pp.session_duration,
                   br.name as branch_name, br.code as branch_code
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            JOIN member_pt_sessions mps ON pb.member_pt_session_id = mps.id
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            LEFT JOIN branches br ON pb.branch_id = br.id
            {where_sql}
            ORDER BY pb.booking_date ASC, pb.start_time ASC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        bookings = cursor.fetchall()

        for b in bookings:
            b["start_time"] = str(b["start_time"])
            b["end_time"] = str(b["end_time"])

        return {
            "success": True,
            "data": bookings,
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
        logger.error(f"Error getting trainer PT bookings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PT_BOOKINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/bookings/today")
def get_today_pt_bookings(
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get today's PT bookings for this trainer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])
        today = date.today()

        branch_filter = ""
        query_params = [trainer_id, today]
        if branch_id:
            branch_filter = "AND pb.branch_id = %s"
            query_params.append(branch_id)

        cursor.execute(
            f"""
            SELECT pb.*, u.name as member_name, u.phone as member_phone,
                   pp.name as package_name, pp.session_duration,
                   mps.remaining_sessions,
                   br.name as branch_name, br.code as branch_code
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            JOIN member_pt_sessions mps ON pb.member_pt_session_id = mps.id
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            LEFT JOIN branches br ON pb.branch_id = br.id
            WHERE pb.trainer_id = %s AND pb.booking_date = %s
            {branch_filter}
            ORDER BY pb.start_time ASC
            """,
            query_params,
        )
        bookings = cursor.fetchall()

        for b in bookings:
            b["start_time"] = str(b["start_time"])
            b["end_time"] = str(b["end_time"])

        return {
            "success": True,
            "data": bookings,
            "total": len(bookings),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting today's PT bookings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TODAY_PT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/bookings/{booking_id}/complete")
def complete_pt_session(
    booking_id: int,
    request: CompleteSessionRequest = None,
    auth: dict = Depends(verify_bearer_token),
):
    """Mark a PT booking as completed"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Get booking - must belong to this trainer
        cursor.execute(
            """
            SELECT pb.*, u.name as member_name
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            WHERE pb.id = %s AND pb.trainer_id = %s AND pb.status = 'booked'
            """,
            (booking_id, trainer_id),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan atau bukan milik Anda"},
            )

        # Update booking to completed
        notes = request.notes if request else None
        cursor.execute(
            """
            UPDATE pt_bookings
            SET status = 'completed', completed_at = %s, completed_by = %s,
                notes = COALESCE(%s, notes), updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), auth["user_id"], notes, datetime.now(), booking_id),
        )

        # Update used sessions
        cursor.execute(
            """
            UPDATE member_pt_sessions
            SET used_sessions = used_sessions + 1, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking["member_pt_session_id"]),
        )

        # Check if all sessions used
        cursor.execute(
            "SELECT remaining_sessions FROM member_pt_sessions WHERE id = %s",
            (booking["member_pt_session_id"],),
        )
        pt_session = cursor.fetchone()
        if pt_session and pt_session["remaining_sessions"] <= 0:
            cursor.execute(
                "UPDATE member_pt_sessions SET status = 'completed' WHERE id = %s",
                (booking["member_pt_session_id"],),
            )

        conn.commit()

        return {
            "success": True,
            "message": f"Sesi PT dengan {booking['member_name']} berhasil diselesaikan",
            "data": {
                "booking_id": booking_id,
                "member_name": booking["member_name"],
                "remaining_sessions": pt_session["remaining_sessions"] if pt_session else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error completing PT session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "COMPLETE_PT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/bookings/{booking_id}/no-show")
def mark_no_show(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Mark a PT booking as no-show (member didn't come)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        # Get booking
        cursor.execute(
            """
            SELECT pb.*, u.name as member_name
            FROM pt_bookings pb
            JOIN users u ON pb.user_id = u.id
            WHERE pb.id = %s AND pb.trainer_id = %s AND pb.status = 'booked'
            """,
            (booking_id, trainer_id),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan atau bukan milik Anda"},
            )

        # Mark as no-show (session is consumed, not refunded)
        cursor.execute(
            """
            UPDATE pt_bookings
            SET status = 'no_show', updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking_id),
        )

        # Deduct session (no-show still counts)
        cursor.execute(
            """
            UPDATE member_pt_sessions
            SET used_sessions = used_sessions + 1, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking["member_pt_session_id"]),
        )

        # Check if all sessions used
        cursor.execute(
            "SELECT remaining_sessions FROM member_pt_sessions WHERE id = %s",
            (booking["member_pt_session_id"],),
        )
        pt_session = cursor.fetchone()
        if pt_session and pt_session["remaining_sessions"] <= 0:
            cursor.execute(
                "UPDATE member_pt_sessions SET status = 'completed' WHERE id = %s",
                (booking["member_pt_session_id"],),
            )

        conn.commit()

        return {
            "success": True,
            "message": f"{booking['member_name']} ditandai no-show. Sesi tetap terhitung.",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking no-show: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "NO_SHOW_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/clients")
def get_my_clients(
    status_filter: Optional[str] = Query(None, alias="status"),
    auth: dict = Depends(verify_bearer_token),
):
    """Get members who have PT sessions with this trainer"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        trainer_id = _get_trainer_id(cursor, auth["user_id"])

        where_clauses = ["mps.trainer_id = %s"]
        params = [trainer_id]

        if status_filter:
            where_clauses.append("mps.status = %s")
            params.append(status_filter)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        # Get aggregated per-member summary
        cursor.execute(
            f"""
            SELECT u.id as user_id, u.name as member_name, u.email as member_email,
                   u.phone as member_phone,
                   SUM(mps.total_sessions) as total_sessions,
                   SUM(mps.used_sessions) as used_sessions,
                   SUM(mps.remaining_sessions) as remaining_sessions,
                   SUM(CASE WHEN mps.status = 'active' THEN 1 ELSE 0 END) as active_packages,
                   COUNT(*) as package_count
            FROM member_pt_sessions mps
            JOIN users u ON mps.user_id = u.id
            {where_sql}
            GROUP BY u.id, u.name, u.email, u.phone
            ORDER BY active_packages DESC, remaining_sessions DESC
            """,
            params,
        )
        members = cursor.fetchall()
        member_ids = [m["user_id"] for m in members]

        # Get individual sessions for these members
        sessions_by_user = {}
        if member_ids:
            placeholders = ",".join(["%s"] * len(member_ids))
            sess_where = list(where_clauses)
            sess_params = list(params)
            sess_where.append(f"mps.user_id IN ({placeholders})")
            sess_params.extend(member_ids)
            sess_where_sql = " WHERE " + " AND ".join(sess_where)

            cursor.execute(
                f"""
                SELECT mps.id as session_id, mps.user_id, mps.total_sessions, mps.used_sessions,
                       mps.remaining_sessions, mps.start_date, mps.expire_date, mps.status,
                       pp.name as package_name
                FROM member_pt_sessions mps
                JOIN pt_packages pp ON mps.pt_package_id = pp.id
                {sess_where_sql}
                ORDER BY mps.status ASC, mps.expire_date ASC
                """,
                sess_params,
            )
            for s in cursor.fetchall():
                sessions_by_user.setdefault(s["user_id"], []).append(s)

        for m in members:
            m["total_sessions"] = int(m["total_sessions"] or 0)
            m["used_sessions"] = int(m["used_sessions"] or 0)
            m["remaining_sessions"] = int(m["remaining_sessions"] or 0)
            m["active_packages"] = int(m["active_packages"] or 0)
            m["sessions"] = sessions_by_user.get(m["user_id"], [])

        return {
            "success": True,
            "data": members,
            "total": len(members),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer clients: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CLIENTS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
