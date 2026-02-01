"""
Personal Training Router - Packages, Purchase, Booking
"""
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission, get_branch_id, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pt", tags=["CMS - Personal Training"])


# ============== Request Models ==============

class PTPackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    session_count: int = Field(..., ge=1)
    session_duration: int = Field(60, ge=30, le=180)
    price: float = Field(..., gt=0)
    valid_days: int = Field(90, ge=1)
    trainer_id: Optional[int] = None


class PurchasePTRequest(BaseModel):
    package_id: int
    trainer_id: int
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")


class BookPTRequest(BaseModel):
    member_pt_session_id: int
    booking_date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")


class BookPTForMemberRequest(BaseModel):
    user_id: int
    member_pt_session_id: int
    booking_date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")


# ============== Helper Functions ==============

def generate_transaction_code():
    return f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ============== Endpoints ==============

@router.get("/packages")
def get_pt_packages(
    trainer_id: Optional[int] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all PT packages"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = ["pp.is_active = 1"]
        params = []

        if trainer_id:
            where_clauses.append("(pp.trainer_id = %s OR pp.trainer_id IS NULL)")
            params.append(trainer_id)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT pp.*, u.name as trainer_name
            FROM pt_packages pp
            LEFT JOIN trainers t ON pp.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            {where_sql}
            ORDER BY pp.session_count ASC
            """,
            params,
        )
        packages = cursor.fetchall()

        for pkg in packages:
            pkg["price"] = float(pkg["price"]) if pkg.get("price") else 0

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
        user_id = auth["user_id"]

        # Get package
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

        # Check if package is for specific trainer
        if package["trainer_id"] and package["trainer_id"] != request.trainer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TRAINER_MISMATCH", "message": "Paket ini khusus untuk trainer tertentu"},
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
        transaction_code = generate_transaction_code()
        cursor.execute(
            """
            INSERT INTO transactions
            (branch_id, transaction_code, user_id, subtotal, subtotal_after_discount,
             tax_percentage, tax_amount, grand_total, payment_method, payment_status,
             paid_amount, paid_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
                transaction_code,
                user_id,
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
        import json
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
            (user_id, pt_package_id, transaction_id, trainer_id, total_sessions, used_sessions,
             start_date, expire_date, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
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
            detail={"error_code": "PURCHASE_PT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/book")
def book_pt_session(
    request: BookPTRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Book a PT session"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get member PT session
        cursor.execute(
            """
            SELECT mps.*, pp.session_duration, u.name as trainer_name
            FROM member_pt_sessions mps
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            JOIN trainers t ON mps.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
            WHERE mps.id = %s AND mps.user_id = %s AND mps.status = 'active'
            """,
            (request.member_pt_session_id, user_id),
        )
        pt_session = cursor.fetchone()

        if not pt_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PT_SESSION_NOT_FOUND", "message": "Paket PT tidak ditemukan atau sudah expired"},
            )

        # Check remaining sessions
        if pt_session["remaining_sessions"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "NO_SESSION_REMAINING", "message": "Sesi PT Anda sudah habis"},
            )

        # Check if expired
        if pt_session["expire_date"] < date.today():
            cursor.execute(
                "UPDATE member_pt_sessions SET status = 'expired' WHERE id = %s",
                (pt_session["id"],),
            )
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PT_EXPIRED", "message": "Paket PT Anda sudah expired"},
            )

        # Validate booking date
        if request.booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PAST_DATE", "message": "Tidak bisa booking untuk tanggal yang sudah lewat"},
            )

        # Get booking advance days setting
        cursor.execute("SELECT value FROM settings WHERE `key` = 'pt_booking_advance_days'")
        setting = cursor.fetchone()
        max_advance_days = int(setting["value"]) if setting else 14

        if request.booking_date > date.today() + timedelta(days=max_advance_days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TOO_FAR_ADVANCE", "message": f"Booking maksimal H-{max_advance_days}"},
            )

        # Check trainer availability (no overlapping bookings)
        start_time = datetime.strptime(request.start_time, "%H:%M").time()
        end_time = (datetime.combine(date.today(), start_time) + timedelta(minutes=pt_session["session_duration"])).time()

        cursor.execute(
            """
            SELECT id FROM pt_bookings
            WHERE trainer_id = %s AND booking_date = %s
            AND status IN ('booked', 'completed')
            AND (
                (start_time <= %s AND end_time > %s)
                OR (start_time < %s AND end_time >= %s)
                OR (start_time >= %s AND end_time <= %s)
            )
            """,
            (
                pt_session["trainer_id"], request.booking_date,
                start_time, start_time,
                end_time, end_time,
                start_time, end_time,
            ),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TRAINER_BUSY", "message": "Trainer tidak tersedia pada waktu tersebut"},
            )

        # Create booking
        cursor.execute(
            """
            INSERT INTO pt_bookings
            (branch_id, member_pt_session_id, user_id, trainer_id, booking_date, start_time, end_time, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
                pt_session["id"],
                user_id,
                pt_session["trainer_id"],
                request.booking_date,
                start_time,
                end_time,
                "booked",
                datetime.now(),
            ),
        )
        booking_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "message": "Booking PT berhasil",
            "data": {
                "booking_id": booking_id,
                "trainer_name": pt_session["trainer_name"],
                "booking_date": str(request.booking_date),
                "start_time": str(start_time),
                "end_time": str(end_time),
                "remaining_sessions": pt_session["remaining_sessions"],
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


@router.delete("/book/{booking_id}")
def cancel_pt_booking(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Cancel a PT booking"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get booking
        cursor.execute(
            """
            SELECT * FROM pt_bookings
            WHERE id = %s AND user_id = %s AND status = 'booked'
            """,
            (booking_id, user_id),
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
                    "message": f"Pembatalan harus dilakukan minimal {cancel_hours} jam sebelumnya",
                },
            )

        # Cancel
        cursor.execute(
            """
            UPDATE pt_bookings
            SET status = 'cancelled', cancelled_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), datetime.now(), booking_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Booking PT berhasil dibatalkan",
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


@router.get("/my-sessions")
def get_my_pt_sessions(
    status_filter: Optional[str] = Query(None, alias="status"),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get my PT sessions"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        where_clauses = ["mps.user_id = %s"]
        params = [user_id]

        if status_filter:
            where_clauses.append("mps.status = %s")
            params.append(status_filter)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT mps.*, pp.name as package_name, pp.session_duration,
                   u.name as trainer_name, u.phone as trainer_phone
            FROM member_pt_sessions mps
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            JOIN trainers t ON mps.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
            {where_sql}
            ORDER BY mps.created_at DESC
            """,
            params,
        )
        sessions = cursor.fetchall()

        # Get bookings for each session
        for session in sessions:
            booking_where = ["pb.member_pt_session_id = %s"]
            booking_params = [session["id"]]

            if branch_id:
                booking_where.append("pb.branch_id = %s")
                booking_params.append(branch_id)

            booking_where_sql = " WHERE " + " AND ".join(booking_where)

            cursor.execute(
                f"""
                SELECT pb.*, b.name as branch_name
                FROM pt_bookings pb
                LEFT JOIN branches b ON pb.branch_id = b.id
                {booking_where_sql}
                ORDER BY pb.booking_date DESC, pb.start_time DESC
                """,
                booking_params,
            )
            session["bookings"] = cursor.fetchall()

        return {
            "success": True,
            "data": sessions,
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


@router.get("/member-sessions")
def get_member_pt_sessions(
    user_id: int = Query(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    auth: dict = Depends(verify_bearer_token),
):
    """Get PT sessions for a specific member (CMS)"""
    check_permission(auth, "trainer.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = ["mps.user_id = %s"]
        params = [user_id]

        if status_filter:
            where_clauses.append("mps.status = %s")
            params.append(status_filter)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT mps.*, pp.name as package_name, pp.session_duration,
                   u.name as trainer_name
            FROM member_pt_sessions mps
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            JOIN trainers t ON mps.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
            {where_sql}
            ORDER BY mps.created_at DESC
            """,
            params,
        )
        sessions = cursor.fetchall()

        return {
            "success": True,
            "data": sessions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting member PT sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_MEMBER_PT_SESSIONS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== CMS Endpoints ==============

@router.post("/packages", status_code=status.HTTP_201_CREATED)
def create_pt_package(request: PTPackageCreate, auth: dict = Depends(verify_bearer_token)):
    """Create a new PT package (CMS)"""
    check_permission(auth, "trainer.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate trainer if specified
        if request.trainer_id:
            cursor.execute("SELECT id FROM trainers WHERE id = %s AND is_active = 1", (request.trainer_id,))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
                )

        cursor.execute(
            """
            INSERT INTO pt_packages
            (name, description, session_count, session_duration, price, valid_days, trainer_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.name,
                request.description,
                request.session_count,
                request.session_duration,
                request.price,
                request.valid_days,
                request.trainer_id,
                datetime.now(),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Paket PT berhasil dibuat",
            "data": {"id": cursor.lastrowid},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating PT package: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_PT_PACKAGE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/bookings/{booking_id}/complete")
def complete_pt_booking(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Mark PT booking as completed (CMS/Trainer)"""
    check_permission(auth, "trainer.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get booking
        cursor.execute(
            "SELECT * FROM pt_bookings WHERE id = %s AND status = 'booked'",
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

        # Update booking
        cursor.execute(
            """
            UPDATE pt_bookings
            SET status = 'completed', completed_at = %s, completed_by = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), auth["user_id"], datetime.now(), booking_id),
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
            "message": "Sesi PT berhasil diselesaikan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error completing PT booking: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "COMPLETE_PT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Book PT for Member (CMS) ==============

@router.post("/book-for-member", status_code=status.HTTP_201_CREATED)
def book_pt_for_member(
    request: BookPTForMemberRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Book a PT session on behalf of a member (CMS staff)"""
    check_permission(auth, "trainer.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate user exists
        cursor.execute("SELECT id, name FROM users WHERE id = %s AND is_active = 1", (request.user_id,))
        member = cursor.fetchone()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "Member tidak ditemukan"},
            )

        # Get member PT session
        cursor.execute(
            """
            SELECT mps.*, pp.session_duration, u.name as trainer_name
            FROM member_pt_sessions mps
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            JOIN trainers t ON mps.trainer_id = t.id
            JOIN users u ON t.user_id = u.id
            WHERE mps.id = %s AND mps.user_id = %s AND mps.status = 'active'
            """,
            (request.member_pt_session_id, request.user_id),
        )
        pt_session = cursor.fetchone()

        if not pt_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PT_SESSION_NOT_FOUND", "message": "Paket PT member tidak ditemukan atau sudah expired"},
            )

        # Check remaining sessions
        remaining = pt_session["total_sessions"] - pt_session["used_sessions"]
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "NO_SESSION_REMAINING", "message": "Sesi PT member sudah habis"},
            )

        # Check if expired
        if pt_session["expire_date"] < date.today():
            cursor.execute(
                "UPDATE member_pt_sessions SET status = 'expired' WHERE id = %s",
                (pt_session["id"],),
            )
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PT_EXPIRED", "message": "Paket PT member sudah expired"},
            )

        # Validate booking date
        if request.booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PAST_DATE", "message": "Tidak bisa booking untuk tanggal yang sudah lewat"},
            )

        # Check trainer availability
        start_time = datetime.strptime(request.start_time, "%H:%M").time()
        end_time = (datetime.combine(date.today(), start_time) + timedelta(minutes=pt_session["session_duration"])).time()

        cursor.execute(
            """
            SELECT id FROM pt_bookings
            WHERE trainer_id = %s AND booking_date = %s
            AND status IN ('booked', 'completed')
            AND (
                (start_time <= %s AND end_time > %s)
                OR (start_time < %s AND end_time >= %s)
                OR (start_time >= %s AND end_time <= %s)
            )
            """,
            (
                pt_session["trainer_id"], request.booking_date,
                start_time, start_time,
                end_time, end_time,
                start_time, end_time,
            ),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TRAINER_BUSY", "message": "Trainer tidak tersedia pada waktu tersebut"},
            )

        # Create booking
        cursor.execute(
            """
            INSERT INTO pt_bookings
            (branch_id, member_pt_session_id, user_id, trainer_id, booking_date, start_time, end_time, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
                pt_session["id"],
                request.user_id,
                pt_session["trainer_id"],
                request.booking_date,
                start_time,
                end_time,
                "booked",
                datetime.now(),
            ),
        )
        booking_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "message": f"Booking PT berhasil untuk {member['name']}",
            "data": {
                "booking_id": booking_id,
                "member_name": member["name"],
                "trainer_name": pt_session["trainer_name"],
                "booking_date": str(request.booking_date),
                "start_time": str(start_time),
                "end_time": str(end_time),
                "remaining_sessions": remaining - 1,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error booking PT for member: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "BOOK_PT_FOR_MEMBER_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Calendar Endpoints ==============

@router.get("/bookings/calendar")
def get_pt_bookings_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get PT bookings summary grouped by date for calendar view"""
    check_permission(auth, "trainer.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        branch_filter = ""
        params_summary = [start_date, end_date]
        params_bookings = [start_date, end_date]
        if branch_id:
            branch_filter = " AND pb.branch_id = %s"
            params_summary.append(branch_id)
            params_bookings.append(branch_id)

        # Get booking counts per date
        cursor.execute(
            f"""
            SELECT pb.booking_date,
                   COUNT(*) as total_bookings,
                   SUM(CASE WHEN pb.status = 'booked' THEN 1 ELSE 0 END) as booked_count,
                   SUM(CASE WHEN pb.status = 'completed' THEN 1 ELSE 0 END) as completed_count
            FROM pt_bookings pb
            WHERE pb.booking_date BETWEEN %s AND %s
            AND pb.status != 'cancelled'
            {branch_filter}
            GROUP BY pb.booking_date
            ORDER BY pb.booking_date
            """,
            params_summary,
        )
        date_summary = cursor.fetchall()

        for d in date_summary:
            d["booking_date"] = str(d["booking_date"])

        # Get bookings grouped by date
        cursor.execute(
            f"""
            SELECT pb.booking_date, pb.id as booking_id,
                   pb.start_time, pb.end_time, pb.status,
                   u_member.name as member_name,
                   u_trainer.name as trainer_name
            FROM pt_bookings pb
            JOIN users u_member ON pb.user_id = u_member.id
            JOIN trainers t ON pb.trainer_id = t.id
            JOIN users u_trainer ON t.user_id = u_trainer.id
            WHERE pb.booking_date BETWEEN %s AND %s
            AND pb.status != 'cancelled'
            {branch_filter}
            ORDER BY pb.booking_date, pb.start_time
            """,
            params_bookings,
        )
        bookings_raw = cursor.fetchall()

        bookings_by_date = {}
        for b in bookings_raw:
            d = str(b["booking_date"])
            b["booking_date"] = d
            b["start_time"] = str(b["start_time"])
            b["end_time"] = str(b["end_time"])
            if d not in bookings_by_date:
                bookings_by_date[d] = []
            bookings_by_date[d].append(b)

        return {
            "success": True,
            "data": {
                "date_summary": date_summary,
                "bookings_by_date": bookings_by_date,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PT bookings calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PT_CALENDAR_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/bookings/date/{booking_date}")
def get_pt_bookings_by_date(
    booking_date: date,
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get detailed PT bookings for a specific date"""
    check_permission(auth, "trainer.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        branch_filter = ""
        params = [booking_date]
        if branch_id:
            branch_filter = " AND pb.branch_id = %s"
            params.append(branch_id)

        cursor.execute(
            f"""
            SELECT pb.id, pb.booking_date, pb.start_time, pb.end_time,
                   pb.status, pb.notes, pb.completed_at,
                   u_member.name as member_name, u_member.email as member_email,
                   u_member.phone as member_phone,
                   u_trainer.name as trainer_name,
                   t.id as trainer_id, t.specialization,
                   pp.name as package_name,
                   b.name as branch_name
            FROM pt_bookings pb
            JOIN users u_member ON pb.user_id = u_member.id
            JOIN trainers t ON pb.trainer_id = t.id
            JOIN users u_trainer ON t.user_id = u_trainer.id
            JOIN member_pt_sessions mps ON pb.member_pt_session_id = mps.id
            JOIN pt_packages pp ON mps.pt_package_id = pp.id
            LEFT JOIN branches b ON pb.branch_id = b.id
            WHERE pb.booking_date = %s
            AND pb.status != 'cancelled'
            {branch_filter}
            ORDER BY pb.start_time ASC
            """,
            params,
        )
        bookings = cursor.fetchall()

        for b in bookings:
            b["booking_date"] = str(b["booking_date"])
            b["start_time"] = str(b["start_time"])
            b["end_time"] = str(b["end_time"])
            if b.get("completed_at"):
                b["completed_at"] = str(b["completed_at"])

        return {
            "success": True,
            "data": bookings,
            "date": str(booking_date),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PT bookings by date: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PT_DATE_BOOKINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
