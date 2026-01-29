"""
CMS Classes Router - Class types, schedules, and booking management
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classes", tags=["CMS - Classes"])


# ============== Request Models ==============

class ClassTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    default_duration: int = Field(60, ge=15, le=180)
    default_capacity: int = Field(20, ge=1, le=100)
    color: str = Field("#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool = True


class ClassTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    default_duration: Optional[int] = Field(None, ge=15, le=180)
    default_capacity: Optional[int] = Field(None, ge=1, le=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None


class ClassScheduleCreate(BaseModel):
    class_type_id: int
    trainer_id: Optional[int] = None
    name: Optional[str] = None
    day_of_week: int = Field(..., ge=0, le=6)  # 0=Sunday, 6=Saturday
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")  # HH:MM
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    capacity: int = Field(20, ge=1)
    room: Optional[str] = None
    is_active: bool = True


class ClassScheduleUpdate(BaseModel):
    class_type_id: Optional[int] = None
    trainer_id: Optional[int] = None
    name: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    capacity: Optional[int] = Field(None, ge=1)
    room: Optional[str] = None
    is_active: Optional[bool] = None


# ============== Class Types Endpoints ==============

@router.get("/types")
def get_all_class_types(
    is_active: Optional[bool] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all class types"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clause = ""
        params = []

        if is_active is not None:
            where_clause = " WHERE is_active = %s"
            params.append(1 if is_active else 0)

        cursor.execute(
            f"""
            SELECT * FROM class_types
            {where_clause}
            ORDER BY name ASC
            """,
            params
        )
        class_types = cursor.fetchall()

        for ct in class_types:
            ct["is_active"] = bool(ct.get("is_active"))

        return {
            "success": True,
            "data": class_types,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting class types: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CLASS_TYPES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/types", status_code=status.HTTP_201_CREATED)
def create_class_type(
    request: ClassTypeCreate, auth: dict = Depends(verify_bearer_token)
):
    """Create a new class type"""
    check_permission(auth, "class.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            INSERT INTO class_types
            (name, description, default_duration, default_capacity, color, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.name,
                request.description,
                request.default_duration,
                request.default_capacity,
                request.color,
                1 if request.is_active else 0,
                datetime.now(),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Jenis kelas berhasil dibuat",
            "data": {"id": cursor.lastrowid},
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating class type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_CLASS_TYPE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/types/{type_id}")
def get_class_type(type_id: int, auth: dict = Depends(verify_bearer_token)):
    """Get class type by ID"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM class_types WHERE id = %s", (type_id,))
        class_type = cursor.fetchone()

        if not class_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "CLASS_TYPE_NOT_FOUND", "message": "Jenis kelas tidak ditemukan"},
            )

        class_type["is_active"] = bool(class_type.get("is_active"))

        return {
            "success": True,
            "data": class_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting class type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CLASS_TYPE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/types/{type_id}")
def update_class_type(
    type_id: int, request: ClassTypeUpdate, auth: dict = Depends(verify_bearer_token)
):
    """Update a class type"""
    check_permission(auth, "class.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check exists
        cursor.execute("SELECT id FROM class_types WHERE id = %s", (type_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "CLASS_TYPE_NOT_FOUND", "message": "Jenis kelas tidak ditemukan"},
            )

        # Build update query
        update_fields = []
        params = []

        if request.name is not None:
            update_fields.append("name = %s")
            params.append(request.name)
        if request.description is not None:
            update_fields.append("description = %s")
            params.append(request.description)
        if request.default_duration is not None:
            update_fields.append("default_duration = %s")
            params.append(request.default_duration)
        if request.default_capacity is not None:
            update_fields.append("default_capacity = %s")
            params.append(request.default_capacity)
        if request.color is not None:
            update_fields.append("color = %s")
            params.append(request.color)
        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(type_id)

        cursor.execute(
            f"UPDATE class_types SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Jenis kelas berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating class type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_CLASS_TYPE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/types/{type_id}")
def delete_class_type(type_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete (deactivate) a class type"""
    check_permission(auth, "class.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM class_types WHERE id = %s", (type_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "CLASS_TYPE_NOT_FOUND", "message": "Jenis kelas tidak ditemukan"},
            )

        # Soft delete
        cursor.execute(
            "UPDATE class_types SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), type_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Jenis kelas berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting class type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_CLASS_TYPE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Class Schedules Endpoints ==============

@router.get("/schedules")
def get_all_schedules(
    class_type_id: Optional[int] = Query(None),
    trainer_id: Optional[int] = Query(None),
    day_of_week: Optional[int] = Query(None, ge=0, le=6),
    is_active: Optional[bool] = Query(None),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all class schedules"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if class_type_id:
            where_clauses.append("cs.class_type_id = %s")
            params.append(class_type_id)
        if trainer_id:
            where_clauses.append("cs.trainer_id = %s")
            params.append(trainer_id)
        if day_of_week is not None:
            where_clauses.append("cs.day_of_week = %s")
            params.append(day_of_week)
        if is_active is not None:
            where_clauses.append("cs.is_active = %s")
            params.append(1 if is_active else 0)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cursor.execute(
            f"""
            SELECT cs.*,
                   ct.name as class_name, ct.color,
                   u.name as trainer_name
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            {where_sql}
            ORDER BY cs.day_of_week ASC, cs.start_time ASC
            """,
            params,
        )
        schedules = cursor.fetchall()

        for s in schedules:
            s["is_active"] = bool(s.get("is_active"))
            s["start_time"] = str(s["start_time"])
            s["end_time"] = str(s["end_time"])

        return {
            "success": True,
            "data": schedules,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schedules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SCHEDULES_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(
    request: ClassScheduleCreate, auth: dict = Depends(verify_bearer_token)
):
    """Create a new class schedule"""
    check_permission(auth, "class.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate class type
        cursor.execute("SELECT id FROM class_types WHERE id = %s AND is_active = 1", (request.class_type_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "CLASS_TYPE_NOT_FOUND", "message": "Jenis kelas tidak ditemukan"},
            )

        # Validate trainer if provided
        if request.trainer_id:
            cursor.execute("SELECT id FROM trainers WHERE id = %s AND is_active = 1", (request.trainer_id,))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "TRAINER_NOT_FOUND", "message": "Trainer tidak ditemukan"},
                )

        cursor.execute(
            """
            INSERT INTO class_schedules
            (class_type_id, trainer_id, name, day_of_week, start_time, end_time, capacity, room, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.class_type_id,
                request.trainer_id,
                request.name,
                request.day_of_week,
                request.start_time,
                request.end_time,
                request.capacity,
                request.room,
                1 if request.is_active else 0,
                datetime.now(),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Jadwal kelas berhasil dibuat",
            "data": {"id": cursor.lastrowid},
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CREATE_SCHEDULE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int, request: ClassScheduleUpdate, auth: dict = Depends(verify_bearer_token)
):
    """Update a class schedule"""
    check_permission(auth, "class.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check exists
        cursor.execute("SELECT id FROM class_schedules WHERE id = %s", (schedule_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SCHEDULE_NOT_FOUND", "message": "Jadwal tidak ditemukan"},
            )

        # Build update
        update_fields = []
        params = []

        if request.class_type_id is not None:
            update_fields.append("class_type_id = %s")
            params.append(request.class_type_id)
        if request.trainer_id is not None:
            update_fields.append("trainer_id = %s")
            params.append(request.trainer_id)
        if request.name is not None:
            update_fields.append("name = %s")
            params.append(request.name)
        if request.day_of_week is not None:
            update_fields.append("day_of_week = %s")
            params.append(request.day_of_week)
        if request.start_time is not None:
            update_fields.append("start_time = %s")
            params.append(request.start_time)
        if request.end_time is not None:
            update_fields.append("end_time = %s")
            params.append(request.end_time)
        if request.capacity is not None:
            update_fields.append("capacity = %s")
            params.append(request.capacity)
        if request.room is not None:
            update_fields.append("room = %s")
            params.append(request.room)
        if request.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(1 if request.is_active else 0)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(schedule_id)

        cursor.execute(
            f"UPDATE class_schedules SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Jadwal berhasil diupdate",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_SCHEDULE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, auth: dict = Depends(verify_bearer_token)):
    """Delete (deactivate) a class schedule"""
    check_permission(auth, "class.delete")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM class_schedules WHERE id = %s", (schedule_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "SCHEDULE_NOT_FOUND", "message": "Jadwal tidak ditemukan"},
            )

        cursor.execute(
            "UPDATE class_schedules SET is_active = 0, updated_at = %s WHERE id = %s",
            (datetime.now(), schedule_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Jadwal berhasil dihapus",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DELETE_SCHEDULE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Bookings Management ==============

@router.get("/bookings")
def get_all_bookings(
    schedule_id: Optional[int] = Query(None),
    class_date: Optional[date] = Query(None),
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all class bookings"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if schedule_id:
            where_clauses.append("cb.schedule_id = %s")
            params.append(schedule_id)
        if class_date:
            where_clauses.append("cb.class_date = %s")
            params.append(class_date)
        if user_id:
            where_clauses.append("cb.user_id = %s")
            params.append(user_id)
        if status_filter:
            where_clauses.append("cb.status = %s")
            params.append(status_filter)
        if search:
            where_clauses.append("(u.name LIKE %s OR u.email LIKE %s)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(
            f"""
            SELECT COUNT(*) as total
            FROM class_bookings cb
            JOIN users u ON cb.user_id = u.id
            {where_sql}
            """,
            params
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT cb.*, cs.start_time, cs.end_time, cs.room,
                   ct.name as class_name, ct.color,
                   u.name as member_name, u.email as member_email, u.phone as member_phone
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN class_types ct ON cs.class_type_id = ct.id
            JOIN users u ON cb.user_id = u.id
            {where_sql}
            ORDER BY cb.class_date DESC, cs.start_time ASC
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
        logger.error(f"Error getting bookings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_BOOKINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/bookings/today")
def get_today_class_schedule(auth: dict = Depends(verify_bearer_token)):
    """Get today's class schedule with bookings"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        today = date.today()
        day_of_week_sunday = (today.weekday() + 1) % 7

        cursor.execute(
            """
            SELECT cs.*,
                   ct.name as class_name, ct.color,
                   u.name as trainer_name,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.schedule_id = cs.id AND cb.class_date = %s AND cb.status IN ('booked', 'attended')) as booked_count,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.schedule_id = cs.id AND cb.class_date = %s AND cb.status = 'attended') as attended_count
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            WHERE cs.day_of_week = %s AND cs.is_active = 1
            ORDER BY cs.start_time ASC
            """,
            (today, today, day_of_week_sunday),
        )
        schedules = cursor.fetchall()

        for s in schedules:
            s["start_time"] = str(s["start_time"])
            s["end_time"] = str(s["end_time"])
            s["available_slots"] = s["capacity"] - s["booked_count"]

        return {
            "success": True,
            "data": schedules,
            "date": str(today),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting today's schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TODAY_SCHEDULE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/bookings/{booking_id}/attend")
def mark_attendance(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Mark booking as attended"""
    check_permission(auth, "class.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM class_bookings WHERE id = %s AND status = 'booked'",
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan atau sudah diproses"},
            )

        cursor.execute(
            """
            UPDATE class_bookings
            SET status = 'attended', attended_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), datetime.now(), booking_id),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Kehadiran berhasil dicatat",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking attendance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MARK_ATTENDANCE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/bookings/{booking_id}/no-show")
def mark_no_show(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Mark booking as no-show"""
    check_permission(auth, "class.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM class_bookings WHERE id = %s AND status = 'booked'",
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan atau sudah diproses"},
            )

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
            "message": "Member ditandai tidak hadir",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking no-show: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MARK_NO_SHOW_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.delete("/bookings/{booking_id}")
def cancel_booking_admin(booking_id: int, auth: dict = Depends(verify_bearer_token)):
    """Cancel a booking (admin) - refunds class quota"""
    check_permission(auth, "class.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM class_bookings WHERE id = %s AND status = 'booked'",
            (booking_id,),
        )
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "BOOKING_NOT_FOUND", "message": "Booking tidak ditemukan"},
            )

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
                "SELECT class_remaining FROM member_memberships WHERE id = %s",
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
                SET used_classes = used_classes - 1, remaining_classes = remaining_classes + 1
                WHERE id = %s
                """,
                (booking["class_pass_id"],),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Booking berhasil dibatalkan dan kuota dikembalikan",
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
