"""
Member PT Router - Personal Training for members
"""
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, get_branch_id, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pt", tags=["Member - Personal Training"])


# ============== Request Models ==============

class BookPTRequest(BaseModel):
    pt_session_id: int
    trainer_id: int
    booking_date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    notes: Optional[str] = None


class PurchasePTRequest(BaseModel):
    package_id: int
    trainer_id: int
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")


# ============== Helper Functions ==============

def _generate_transaction_code():
    return f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ============== Endpoints ==============

@router.get("/packages")
def get_pt_packages(auth: dict = Depends(verify_bearer_token)):
    """Get available PT packages"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, name, description, session_count, price, valid_days
            FROM pt_packages
            WHERE is_active = 1
            ORDER BY price ASC
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
            SELECT mps.*, pp.name as package_name, t.user_id as trainer_user_id,
                   u.name as trainer_name,
                   (SELECT file_path FROM images
                    WHERE category = 'pt'
                      AND reference_id = t.id
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1) as trainer_image
            FROM member_pt_sessions mps
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            LEFT JOIN trainers t ON mps.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            WHERE mps.user_id = %s AND mps.status = 'active'
            ORDER BY mps.expire_date ASC
            """,
            (auth["user_id"],),
        )
        sessions = cursor.fetchall()

        total_remaining = sum(s["remaining_sessions"] for s in sessions)

        # Aggregate per trainer
        per_trainer = {}
        for s in sessions:
            tid = s.get("trainer_id")
            if tid is None:
                continue
            if tid not in per_trainer:
                expire_dt = s.get("expire_date")
                per_trainer[tid] = {
                    "trainer_id": tid,
                    "trainer_name": s.get("trainer_name") or "Trainer",
                    "trainer_image": s.get("trainer_image"),
                    "package_name": s.get("package_name"),
                    "remaining_sessions": 0,
                    "expire_date": expire_dt.isoformat() if expire_dt else None,
                }
            per_trainer[tid]["remaining_sessions"] += s["remaining_sessions"]
            # Keep the earliest expire_date
            current_expire = per_trainer[tid].get("expire_date")
            new_expire = s.get("expire_date")
            if new_expire:
                new_expire_str = new_expire.isoformat() if hasattr(new_expire, 'isoformat') else str(new_expire)
                if current_expire is None or new_expire_str < current_expire:
                    per_trainer[tid]["expire_date"] = new_expire_str

        return {
            "success": True,
            "data": {
                "sessions": sessions,
                "total_remaining": total_remaining,
                "per_trainer": list(per_trainer.values()),
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
    include_stats: bool = Query(False),
    limit: int = Query(10, ge=1, le=50),
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get available trainers"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clause = "t.is_active = 1"
        params = []
        join_clause = ""

        if branch_id:
            join_clause = " JOIN trainer_branches tb ON t.id = tb.trainer_id AND tb.branch_id = %s"
            params.append(branch_id)

        if specialization:
            where_clause += " AND t.specialization LIKE %s"
            params.append(f"%{specialization}%")

        # Always include total_bookings for rating calculation
        order_by = "total_bookings DESC, u.name ASC" if include_stats else "u.name ASC"
        cursor.execute(
            f"""
            SELECT t.id, t.specialization, t.bio, t.certifications,
                   u.name, u.email, u.phone, u.avatar as profile_photo,
                   (SELECT file_path FROM images
                    WHERE category = 'pt'
                      AND reference_id = t.id
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1) as image,
                   COUNT(pb.id) as total_bookings
            FROM trainers t
            {join_clause}
            JOIN users u ON t.user_id = u.id
            LEFT JOIN pt_bookings pb
                   ON pb.trainer_id = t.id
                   AND pb.status IN ('booked', 'attended')
            WHERE {where_clause}
            GROUP BY t.id, t.specialization, t.bio, t.certifications, u.name, u.email, u.phone, u.avatar
            ORDER BY {order_by}
            LIMIT %s
            """,
            params + [limit],
        )
        trainers = cursor.fetchall()

        for t in trainers:
            if t.get("certifications"):
                t["certifications"] = json.loads(t["certifications"]) if isinstance(t["certifications"], str) else t["certifications"]

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
    branch_id: Optional[int] = Depends(get_branch_id),
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
        booked_where = "trainer_id = %s AND booking_date BETWEEN %s AND %s AND status IN ('booked', 'attended')"
        booked_params = [trainer_id, date_from, date_to]

        if branch_id:
            booked_where += " AND branch_id = %s"
            booked_params.append(branch_id)

        cursor.execute(
            f"""
            SELECT booking_date, start_time, end_time
            FROM pt_bookings
            WHERE {booked_where}
            ORDER BY booking_date, start_time
            """,
            booked_params,
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
def book_pt_session(request: BookPTRequest, branch_id: int = Depends(require_branch_id), auth: dict = Depends(verify_bearer_token)):
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

        # Check trainer is assigned to this branch
        cursor.execute(
            "SELECT id FROM trainer_branches WHERE trainer_id = %s AND branch_id = %s",
            (request.trainer_id, branch_id),
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TRAINER_NOT_IN_BRANCH", "message": "Trainer tidak tersedia di cabang ini"},
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
            WHERE trainer_id = %s AND booking_date = %s AND status IN ('booked', 'attended')
            AND ((start_time <= %s AND end_time > %s) OR (start_time < %s AND end_time >= %s))
            """,
            (request.trainer_id, request.booking_date, request.start_time, request.start_time, end_time, end_time),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "SLOT_TAKEN", "message": "Slot sudah dibooking"},
            )

        # Check member availability (no overlapping bookings for same member)
        cursor.execute(
            """
            SELECT id FROM pt_bookings
            WHERE user_id = %s AND booking_date = %s AND status IN ('booked', 'attended')
            AND ((start_time <= %s AND end_time > %s) OR (start_time < %s AND end_time >= %s))
            """,
            (user_id, request.booking_date, request.start_time, request.start_time, end_time, end_time),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "MEMBER_BUSY", "message": "Kamu sudah memiliki booking PT pada waktu tersebut"},
            )

        # Check member availability against class bookings
        cursor.execute(
            """
            SELECT cb.id, ct.name as class_name
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN class_types ct ON cs.class_type_id = ct.id
            WHERE cb.user_id = %s AND cb.class_date = %s AND cb.status != 'cancelled'
              AND cs.start_time < %s AND cs.end_time > %s
            """,
            (user_id, request.booking_date, end_time, request.start_time),
        )
        class_overlap = cursor.fetchone()
        if class_overlap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "CLASS_TIME_CONFLICT",
                    "message": f"Kamu sudah memiliki kelas '{class_overlap['class_name']}' pada waktu tersebut",
                },
            )

        # Create booking
        cursor.execute(
            """
            INSERT INTO pt_bookings
            (branch_id, member_pt_session_id, user_id, trainer_id, booking_date, start_time, end_time, status, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
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
            SET used_sessions = used_sessions + 1, updated_at = %s
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

        if status_filter and status_filter != "all":
            where_clauses.append("pb.status = %s")
            params.append(status_filter)
        elif not status_filter:
            where_clauses.append("pb.status = 'booked'")

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
            SELECT pb.*, u.name as trainer_name,
                   (SELECT file_path FROM images
                    WHERE category = 'pt'
                      AND reference_id = t.id
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1) as trainer_image,
                   br.name as branch_name, br.code as branch_code
            FROM pt_bookings pb
            JOIN trainers t ON pb.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
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

        # Check cancel window
        cursor.execute("SELECT value FROM settings WHERE `key` = 'pt_cancel_hours'")
        setting = cursor.fetchone()
        cancel_hours = int(setting["value"]) if setting else 24

        start_time = booking["start_time"]
        if isinstance(start_time, timedelta):
            start_time = (datetime.min + start_time).time()
        booking_datetime = datetime.combine(booking["booking_date"], start_time)
        if datetime.now() > booking_datetime - timedelta(hours=cancel_hours):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "CANCEL_TOO_LATE",
                    "message": f"Pembatalan harus dilakukan minimal {cancel_hours} jam sebelum sesi PT",
                },
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
            SET used_sessions = used_sessions - 1, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), booking["member_pt_session_id"]),
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


@router.post("/purchase")
def purchase_pt_package(
    request: PurchasePTRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Purchase a PT package"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate package
        cursor.execute(
            "SELECT * FROM pt_packages WHERE id = %s AND is_active = 1",
            (request.package_id,),
        )
        package = cursor.fetchone()

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PACKAGE_NOT_FOUND", "message": "Paket PT tidak ditemukan"},
            )

        # Validate trainer
        cursor.execute(
            "SELECT * FROM trainers WHERE id = %s AND is_active = 1",
            (request.trainer_id,),
        )
        trainer = cursor.fetchone()

        if not trainer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
            )

        # If package is for specific trainer, validate match
        if package.get("trainer_id") and package["trainer_id"] != request.trainer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TRAINER_MISMATCH", "message": "Paket ini hanya untuk trainer tertentu"},
            )

        # Get tax settings
        cursor.execute("SELECT `key`, `value` FROM settings WHERE `key` IN ('tax_enabled', 'tax_percentage')")
        settings = {row["key"]: row["value"] for row in cursor.fetchall()}
        tax_enabled = settings.get("tax_enabled", "false") == "true"
        tax_percentage = float(settings.get("tax_percentage", "0"))

        # Calculate pricing
        subtotal = float(package["price"])
        tax_amount = subtotal * (tax_percentage / 100) if tax_enabled else 0
        grand_total = subtotal + tax_amount

        # Create transaction
        transaction_code = _generate_transaction_code()
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

        # Create transaction item
        cursor.execute(
            """
            INSERT INTO transaction_items
            (transaction_id, item_type, item_id, item_name, quantity, unit_price, subtotal, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_id,
                "pt_package",
                package["id"],
                package["name"],
                1,
                subtotal,
                subtotal,
                json.dumps({"trainer_id": request.trainer_id, "session_count": package["session_count"]}),
                datetime.now(),
            ),
        )

        # Create member PT session
        start_date = date.today()
        expire_date = start_date + timedelta(days=package["valid_days"])

        cursor.execute(
            """
            INSERT INTO member_pt_sessions
            (user_id, pt_package_id, transaction_id, trainer_id,
             total_sessions, used_sessions, start_date, expire_date, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                auth["user_id"],
                package["id"],
                transaction_id,
                request.trainer_id,
                package["session_count"],
                0,
                start_date,
                expire_date,
                "active",
                datetime.now(),
            ),
        )
        pt_session_id = cursor.lastrowid

        conn.commit()

        return {
            "success": True,
            "message": "Paket PT berhasil dibeli",
            "data": {
                "pt_session_id": pt_session_id,
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "package_name": package["name"],
                "total_sessions": package["session_count"],
                "expire_date": str(expire_date),
                "total_paid": grand_total,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error purchasing PT package: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PT_PURCHASE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
