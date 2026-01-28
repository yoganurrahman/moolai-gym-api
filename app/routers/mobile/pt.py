"""
Mobile PT Router - Personal Training for members
"""
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pt", tags=["Mobile - Personal Training"])


# ============== Request Models ==============

class BookPTRequest(BaseModel):
    pt_session_id: int
    trainer_id: int
    booking_date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    notes: Optional[str] = None


# ============== Endpoints ==============

@router.get("/packages")
def get_pt_packages(auth: dict = Depends(verify_bearer_token)):
    """Get available PT packages"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, name, description, sessions, price, validity_days
            FROM pt_packages
            WHERE is_active = 1
            ORDER BY sort_order ASC, price ASC
            """
        )
        packages = cursor.fetchall()

        for p in packages:
            p["price"] = float(p["price"]) if p.get("price") else 0

        return {
            "success": True,
            "data": packages,
        }

    except Exception as e:
        logger.error(f"Error getting PT packages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PT_PACKAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-sessions")
def get_my_pt_sessions(auth: dict = Depends(verify_bearer_token)):
    """Get my PT session balance"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT mps.*, pp.name as package_name
            FROM member_pt_sessions mps
            JOIN pt_packages pp ON mps.package_id = pp.id
            WHERE mps.user_id = %s AND mps.status = 'active'
            ORDER BY mps.expire_date ASC
            """,
            (auth["user_id"],),
        )
        sessions = cursor.fetchall()

        total_remaining = sum(s["remaining_sessions"] for s in sessions)

        return {
            "success": True,
            "data": {
                "sessions": sessions,
                "total_remaining": total_remaining,
            },
        }

    except Exception as e:
        logger.error(f"Error getting PT sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PT_SESSIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/trainers")
def get_available_trainers(
    specialization: Optional[str] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get available trainers"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clause = "t.is_active = 1"
        params = []

        if specialization:
            where_clause += " AND t.specialization LIKE %s"
            params.append(f"%{specialization}%")

        cursor.execute(
            f"""
            SELECT t.id, t.specialization, t.bio,
                   u.name, u.email, u.phone, u.profile_photo
            FROM trainers t
            JOIN users u ON t.user_id = u.id
            WHERE {where_clause}
            ORDER BY u.name ASC
            """,
            params,
        )
        trainers = cursor.fetchall()

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


@router.get("/trainers/{trainer_id}/availability")
def get_trainer_availability(
    trainer_id: int,
    date_from: date = Query(default_factory=date.today),
    date_to: Optional[date] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get trainer availability for booking"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if not date_to:
            date_to = date_from + timedelta(days=7)

        # Check trainer exists
        cursor.execute(
            "SELECT t.id, u.name FROM trainers t JOIN users u ON t.user_id = u.id WHERE t.id = %s AND t.is_active = 1",
            (trainer_id,),
        )
        trainer = cursor.fetchone()
        if not trainer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        # Get booked slots
        cursor.execute(
            """
            SELECT booking_date, start_time, end_time
            FROM pt_bookings
            WHERE trainer_id = %s AND booking_date BETWEEN %s AND %s AND status IN ('booked', 'completed')
            ORDER BY booking_date, start_time
            """,
            (trainer_id, date_from, date_to),
        )
        booked_slots = cursor.fetchall()

        # Format booked slots by date
        booked_by_date = {}
        for slot in booked_slots:
            date_str = str(slot["booking_date"])
            if date_str not in booked_by_date:
                booked_by_date[date_str] = []
            booked_by_date[date_str].append({
                "start_time": str(slot["start_time"]),
                "end_time": str(slot["end_time"]),
            })

        return {
            "success": True,
            "data": {
                "trainer": trainer,
                "booked_slots": booked_by_date,
                "date_range": {
                    "from": str(date_from),
                    "to": str(date_to),
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trainer availability: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_AVAILABILITY_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/book")
def book_pt_session(request: BookPTRequest, auth: dict = Depends(verify_bearer_token)):
    """Book a PT session"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Check PT session exists and has remaining
        cursor.execute(
            """
            SELECT * FROM member_pt_sessions
            WHERE id = %s AND user_id = %s AND status = 'active' AND remaining_sessions > 0
            """,
            (request.pt_session_id, user_id),
        )
        pt_session = cursor.fetchone()

        if not pt_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "NO_PT_SESSION", "message": "Tidak ada sesi PT aktif atau sesi habis"},
            )

        # Check expiry
        if pt_session["expire_date"] and pt_session["expire_date"] < request.booking_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "SESSION_EXPIRED", "message": "Sesi PT sudah expired"},
            )

        # Check trainer exists
        cursor.execute(
            "SELECT t.id, u.name FROM trainers t JOIN users u ON t.user_id = u.id WHERE t.id = %s AND t.is_active = 1",
            (request.trainer_id,),
        )
        trainer = cursor.fetchone()
        if not trainer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        # Check booking date not in past
        if request.booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PAST_DATE", "message": "Tidak bisa booking di tanggal yang sudah lewat"},
            )

        # Calculate end time (assume 1 hour session)
        start_parts = request.start_time.split(":")
        end_hour = int(start_parts[0]) + 1
        end_time = f"{end_hour:02d}:{start_parts[1]}"

        # Check trainer availability
        cursor.execute(
            """
            SELECT id FROM pt_bookings
            WHERE trainer_id = %s AND booking_date = %s AND status IN ('booked', 'completed')
            AND ((start_time <= %s AND end_time > %s) OR (start_time < %s AND end_time >= %s))
            """,
            (request.trainer_id, request.booking_date, request.start_time, request.start_time, end_time, end_time),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "SLOT_TAKEN", "message": "Slot sudah dibooking"},
            )

        # Create booking
        cursor.execute(
            """
            INSERT INTO pt_bookings
            (pt_session_id, user_id, trainer_id, booking_date, start_time, end_time, status, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.pt_session_id,
                user_id,
                request.trainer_id,
                request.booking_date,
                request.start_time,
                end_time,
                "booked",
                request.notes,
                datetime.now(),
            ),
        )
        booking_id = cursor.lastrowid

        # Deduct session
        cursor.execute(
            """
            UPDATE member_pt_sessions
            SET remaining_sessions = remaining_sessions - 1, used_sessions = used_sessions + 1, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), request.pt_session_id),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Booking PT berhasil",
            "data": {
                "booking_id": booking_id,
                "trainer_name": trainer["name"],
                "booking_date": str(request.booking_date),
                "start_time": request.start_time,
                "end_time": end_time,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error booking PT: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "BOOK_PT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-bookings")
def get_my_pt_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    upcoming_only: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get my PT bookings"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = ["pb.user_id = %s"]
        params = [auth["user_id"]]

        if status_filter:
            where_clauses.append("pb.status = %s")
            params.append(status_filter)

        if upcoming_only:
            where_clauses.append("pb.booking_date >= %s")
            params.append(date.today())

        where_sql = " WHERE " + " AND ".join(where_clauses)

        # Count
        cursor.execute(f"SELECT COUNT(*) as total FROM pt_bookings pb{where_sql}", params)
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT pb.*, u.name as trainer_name
            FROM pt_bookings pb
            JOIN trainers t ON pb.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
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

    except Exception as e:
        logger.error(f"Error getting PT bookings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PT_BOOKINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/book/{booking_id}")
def cancel_pt_booking(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Cancel a PT booking"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get booking
        cursor.execute(
            """
            SELECT * FROM pt_bookings
            WHERE id = %s AND user_id = %s AND status = 'booked'
            """,
            (booking_id, auth["user_id"]),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

        # Check cancel window (24 hours before)
        booking_datetime = datetime.combine(booking["booking_date"], booking["start_time"])
        if datetime.now() > booking_datetime - timedelta(hours=24):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "CANCEL_TOO_LATE", "message": "Pembatalan harus dilakukan minimal 24 jam sebelumnya"},
            )

        # Cancel booking
        cursor.execute(
            "UPDATE pt_bookings SET status = 'cancelled', updated_at = %s WHERE id = %s",
            (datetime.now(), booking_id),
        )

        # Refund session
        cursor.execute(
            """
            UPDATE member_pt_sessions
            SET remaining_sessions = remaining_sessions + 1, used_sessions = used_sessions - 1, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking["pt_session_id"]),
        )

        conn.commit()

        return {
            "success": True,
            "message": "Booking berhasil dibatalkan, sesi dikembalikan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error cancelling PT booking: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CANCEL_PT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
