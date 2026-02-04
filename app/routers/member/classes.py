"""
Member Classes Router - Class schedules and booking for members
"""
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, get_branch_id, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classes", tags=["Member - Classes"])


# ============== Request Models ==============

class BookClassRequest(BaseModel):
    schedule_id: int
    class_date: date


class PurchaseClassPassRequest(BaseModel):
    class_package_id: int
    payment_method: str = Field(..., pattern=r"^(cash|transfer|qris|card|ewallet)$")


# ============== Helper Functions ==============

def _generate_transaction_code():
    return f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ============== Endpoints ==============

@router.get("/types")
def get_class_types(auth: dict = Depends(verify_bearer_token)):
    """Get all available class types"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, name, description, default_duration, color
            FROM class_types
            WHERE is_active = 1
            ORDER BY name ASC
            """
        )
        class_types = cursor.fetchall()

        return {
            "success": True,
            "data": class_types,
        }

    except Exception as e:
        logger.error(f"Error getting class types: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CLASS_TYPES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/schedules")
def get_class_schedules(
    class_type_id: Optional[int] = Query(None),
    date_from: date = Query(default_factory=date.today),
    date_to: Optional[date] = Query(None),
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get class schedules with availability info"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Default to 7 days range
        if not date_to:
            date_to = date_from + timedelta(days=7)

        where_clauses = ["cs.is_active = 1"]
        params = []

        if class_type_id:
            where_clauses.append("cs.class_type_id = %s")
            params.append(class_type_id)

        if branch_id:
            where_clauses.append("cs.branch_id = %s")
            params.append(branch_id)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT cs.*,
                   ct.name as class_name, ct.description as class_description, ct.color, ct.image as class_image,
                   u.name as trainer_name,
                   br.name as branch_name, br.code as branch_code
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN branches br ON cs.branch_id = br.id
            {where_sql}
            ORDER BY cs.day_of_week ASC, cs.start_time ASC
            """,
            params,
        )
        schedules = cursor.fetchall()

        # Build schedule list with dates
        result = []
        current_date = date_from
        while current_date <= date_to:
            day_of_week = current_date.weekday()
            # Convert to Sunday=0 format
            day_of_week_sunday = (day_of_week + 1) % 7

            for schedule in schedules:
                if schedule["day_of_week"] == day_of_week_sunday:
                    # Get booking count for this date
                    cursor.execute(
                        """
                        SELECT COUNT(*) as booked
                        FROM class_bookings
                        WHERE schedule_id = %s AND class_date = %s AND status IN ('booked', 'attended')
                        """,
                        (schedule["id"], current_date),
                    )
                    booked = cursor.fetchone()["booked"]

                    # Check if user already booked
                    cursor.execute(
                        """
                        SELECT id FROM class_bookings
                        WHERE user_id = %s AND schedule_id = %s AND class_date = %s AND status != 'cancelled'
                        """,
                        (auth["user_id"], schedule["id"], current_date),
                    )
                    user_booking = cursor.fetchone()

                    schedule_copy = {
                        "id": schedule["id"],
                        "class_type_id": schedule["class_type_id"],
                        "class_name": schedule["class_name"],
                        "class_description": schedule["class_description"],
                        "class_image": schedule["class_image"],
                        "color": schedule["color"],
                        "trainer_name": schedule["trainer_name"],
                        "branch_name": schedule["branch_name"],
                        "branch_code": schedule["branch_code"],
                        "start_time": str(schedule["start_time"]),
                        "end_time": str(schedule["end_time"]),
                        "room": schedule["room"],
                        "capacity": schedule["capacity"],
                        "class_date": str(current_date),
                        "booked_count": booked,
                        "available_slots": schedule["capacity"] - booked,
                        "is_full": booked >= schedule["capacity"],
                        "is_booked": user_booking is not None,
                        "booking_id": user_booking["id"] if user_booking else None,
                    }
                    result.append(schedule_copy)

            current_date += timedelta(days=1)

        return {
            "success": True,
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error getting schedules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SCHEDULES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-passes")
def get_my_class_passes(auth: dict = Depends(verify_bearer_token)):
    """Get my active class passes with remaining quota"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT mcp.*, cp.name as package_name
            FROM member_class_passes mcp
            JOIN class_packages cp ON mcp.class_package_id = cp.id
            WHERE mcp.user_id = %s AND mcp.status = 'active'
            ORDER BY mcp.expire_date ASC
            """,
            (auth["user_id"],),
        )
        passes = cursor.fetchall()

        total_remaining = sum(p["remaining_classes"] for p in passes)

        return {
            "success": True,
            "data": {
                "passes": passes,
                "total_remaining": total_remaining,
            },
        }

    except Exception as e:
        logger.error(f"Error getting class passes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CLASS_PASSES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/book")
def book_class(request: BookClassRequest, auth: dict = Depends(verify_bearer_token)):
    """Book a class"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get schedule
        cursor.execute(
            """
            SELECT cs.*, ct.name as class_name
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            WHERE cs.id = %s AND cs.is_active = 1
            """,
            (request.schedule_id,),
        )
        schedule = cursor.fetchone()

        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SCHEDULE_NOT_FOUND", "message": "Jadwal kelas tidak ditemukan"},
            )

        # Validate date is correct day of week
        day_of_week_sunday = (request.class_date.weekday() + 1) % 7
        if day_of_week_sunday != schedule["day_of_week"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_DATE", "message": "Tanggal tidak sesuai dengan jadwal kelas"},
            )

        # Check if date is not in the past
        if request.class_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "PAST_DATE", "message": "Tidak bisa booking kelas yang sudah lewat"},
            )

        # Get booking advance days setting
        cursor.execute("SELECT value FROM settings WHERE `key` = 'class_booking_advance_days'")
        setting = cursor.fetchone()
        max_advance_days = int(setting["value"]) if setting else 7

        if request.class_date > date.today() + timedelta(days=max_advance_days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "TOO_FAR_ADVANCE",
                    "message": f"Booking maksimal H-{max_advance_days}",
                },
            )

        # Check if already booked (active or cancelled)
        cursor.execute(
            """
            SELECT id, status FROM class_bookings
            WHERE user_id = %s AND schedule_id = %s AND class_date = %s
            """,
            (user_id, request.schedule_id, request.class_date),
        )
        existing_booking = cursor.fetchone()

        if existing_booking and existing_booking["status"] != "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ALREADY_BOOKED", "message": "Anda sudah booking kelas ini"},
            )

        # If there's a cancelled booking, we'll reactivate it instead of creating new
        reactivate_booking_id = existing_booking["id"] if existing_booking else None

        # Check capacity
        cursor.execute(
            """
            SELECT COUNT(*) as booked FROM class_bookings
            WHERE schedule_id = %s AND class_date = %s AND status IN ('booked', 'attended')
            """,
            (request.schedule_id, request.class_date),
        )
        booked_count = cursor.fetchone()["booked"]

        if booked_count >= schedule["capacity"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "CLASS_FULL", "message": "Kelas sudah penuh"},
            )

        # Check membership/class pass
        cursor.execute(
            """
            SELECT mm.*, mp.include_classes, mp.class_quota
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.user_id = %s AND mm.status = 'active'
            ORDER BY mm.created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        membership = cursor.fetchone()

        access_type = None
        booking_membership_id = None
        booking_class_pass_id = None

        if membership and membership["include_classes"]:
            # Check if has quota or unlimited
            if membership["class_remaining"] is None or membership["class_remaining"] > 0:
                access_type = "membership"
                booking_membership_id = membership["id"]
                # Deduct class quota if not unlimited
                if membership["class_remaining"] is not None:
                    cursor.execute(
                        "UPDATE member_memberships SET class_remaining = class_remaining - 1 WHERE id = %s",
                        (membership["id"],),
                    )

        if not access_type:
            # Check class pass
            cursor.execute(
                """
                SELECT * FROM member_class_passes
                WHERE user_id = %s AND status = 'active' AND remaining_classes > 0
                ORDER BY expire_date ASC
                LIMIT 1
                """,
                (user_id,),
            )
            class_pass = cursor.fetchone()

            if class_pass:
                access_type = "class_pass"
                booking_class_pass_id = class_pass["id"]
                cursor.execute(
                    "UPDATE member_class_passes SET used_classes = used_classes + 1 WHERE id = %s",
                    (class_pass["id"],),
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "NO_CLASS_ACCESS",
                        "message": "Anda tidak memiliki akses kelas. Silakan beli class pass atau upgrade membership.",
                    },
                )

        # Create or reactivate booking
        if reactivate_booking_id:
            # Reactivate cancelled booking
            cursor.execute(
                """
                UPDATE class_bookings
                SET access_type = %s, membership_id = %s, class_pass_id = %s,
                    status = 'booked', booked_at = %s, cancelled_at = NULL, updated_at = %s
                WHERE id = %s
                """,
                (access_type, booking_membership_id, booking_class_pass_id,
                 datetime.now(), datetime.now(), reactivate_booking_id),
            )
            booking_id = reactivate_booking_id
        else:
            # Create new booking
            cursor.execute(
                """
                INSERT INTO class_bookings
                (branch_id, user_id, schedule_id, class_date, access_type, membership_id, class_pass_id,
                 status, booked_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (schedule["branch_id"], user_id, request.schedule_id, request.class_date, access_type,
                 booking_membership_id, booking_class_pass_id,
                 "booked", datetime.now(), datetime.now()),
            )
            booking_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "message": "Booking berhasil",
            "data": {
                "booking_id": booking_id,
                "class_name": schedule["class_name"],
                "class_date": str(request.class_date),
                "start_time": str(schedule["start_time"]),
                "room": schedule["room"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error booking class: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "BOOK_CLASS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/book/{booking_id}")
def cancel_booking(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Cancel a class booking"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get booking (include access_type, membership_id, class_pass_id for refund)
        cursor.execute(
            """
            SELECT cb.*, cs.start_time
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            WHERE cb.id = %s AND cb.user_id = %s AND cb.status = 'booked'
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
        cursor.execute("SELECT value FROM settings WHERE `key` = 'class_cancel_hours'")
        setting = cursor.fetchone()
        cancel_hours = int(setting["value"]) if setting else 2

        start_time = booking["start_time"]
        if isinstance(start_time, timedelta):
            start_time = (datetime.min + start_time).time()
        class_datetime = datetime.combine(booking["class_date"], start_time)
        if datetime.now() > class_datetime - timedelta(hours=cancel_hours):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "CANCEL_TOO_LATE",
                    "message": f"Pembatalan harus dilakukan minimal {cancel_hours} jam sebelum kelas",
                },
            )

        # Cancel booking
        cursor.execute(
            """
            UPDATE class_bookings
            SET status = 'cancelled', cancelled_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), datetime.now(), booking_id),
        )

        # Refund class quota based on access_type
        if booking.get("access_type") == "membership" and booking.get("membership_id"):
            # Refund membership class quota (only if not unlimited)
            cursor.execute(
                """
                SELECT class_remaining FROM member_memberships WHERE id = %s
                """,
                (booking["membership_id"],),
            )
            mm = cursor.fetchone()
            if mm and mm["class_remaining"] is not None:
                cursor.execute(
                    "UPDATE member_memberships SET class_remaining = class_remaining + 1 WHERE id = %s",
                    (booking["membership_id"],),
                )
        elif booking.get("access_type") == "class_pass" and booking.get("class_pass_id"):
            # Refund class pass
            cursor.execute(
                """
                UPDATE member_class_passes
                SET used_classes = used_classes - 1
                WHERE id = %s
                """,
                (booking["class_pass_id"],),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Booking berhasil dibatalkan",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error cancelling booking: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CANCEL_BOOKING_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/my-bookings")
def get_my_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    upcoming_only: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get my class bookings"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        where_clauses = ["cb.user_id = %s"]
        params = [user_id]

        if status_filter and status_filter != "all":
            where_clauses.append("cb.status = %s")
            params.append(status_filter)
        elif not status_filter:
            where_clauses.append("cb.status = 'booked'")

        if upcoming_only:
            where_clauses.append("cb.class_date >= %s")
            params.append(date.today())

        where_sql = " WHERE " + " AND ".join(where_clauses)

        # Count total
        cursor.execute(
            f"SELECT COUNT(*) as total FROM class_bookings cb{where_sql}", params
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT cb.*, cs.start_time, cs.end_time, cs.room,
                   ct.name as class_name, ct.color,
                   u.name as trainer_name,
                   br.name as branch_name, br.code as branch_code
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN branches br ON cb.branch_id = br.id
            {where_sql}
            ORDER BY cb.class_date ASC, cs.start_time ASC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        bookings = cursor.fetchall()

        # Format times
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
        logger.error(f"Error getting bookings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_BOOKINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/packages")
def get_class_packages(auth: dict = Depends(verify_bearer_token)):
    """Get available class packages for purchase"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, name, description, class_count, price, valid_days, class_type_id
            FROM class_packages
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
        logger.error(f"Error getting class packages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CLASS_PACKAGES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/packages/purchase")
def purchase_class_pass(
    request: PurchaseClassPassRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Purchase a class pass"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate package
        cursor.execute(
            "SELECT * FROM class_packages WHERE id = %s AND is_active = 1",
            (request.class_package_id,),
        )
        package = cursor.fetchone()

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PACKAGE_NOT_FOUND", "message": "Paket kelas tidak ditemukan"},
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
            (transaction_id, item_type, item_id, item_name, quantity, unit_price, subtotal, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                transaction_id,
                "class_pass",
                package["id"],
                package["name"],
                1,
                subtotal,
                subtotal,
                datetime.now(),
            ),
        )

        # Create member class pass
        start_date = date.today()
        expire_date = start_date + timedelta(days=package["valid_days"])

        cursor.execute(
            """
            INSERT INTO member_class_passes
            (user_id, class_package_id, transaction_id,
             total_classes, used_classes, start_date, expire_date, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                auth["user_id"],
                package["id"],
                transaction_id,
                package["class_count"],
                0,
                start_date,
                expire_date,
                "active",
                datetime.now(),
            ),
        )
        class_pass_id = cursor.lastrowid

        conn.commit()

        return {
            "success": True,
            "message": "Class pass berhasil dibeli",
            "data": {
                "class_pass_id": class_pass_id,
                "transaction_id": transaction_id,
                "transaction_code": transaction_code,
                "package_name": package["name"],
                "total_classes": package["class_count"],
                "expire_date": str(expire_date),
                "total_paid": grand_total,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error purchasing class pass: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CLASS_PASS_PURCHASE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
