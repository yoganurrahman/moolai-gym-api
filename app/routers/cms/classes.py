"""
CMS Classes Router - Class types, schedules, and booking management
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission, get_branch_id, require_branch_id

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
    branch_id: int
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
    branch_id: Optional[int] = None
    class_type_id: Optional[int] = None
    trainer_id: Optional[int] = None
    name: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    capacity: Optional[int] = Field(None, ge=1)
    room: Optional[str] = None
    is_active: Optional[bool] = None


class BookClassForMemberRequest(BaseModel):
    user_id: int
    schedule_id: int
    class_date: date


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
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all class schedules"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if branch_id:
            where_clauses.append("cs.branch_id = %s")
            params.append(branch_id)
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
                   u.name as trainer_name,
                   b.name as branch_name
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN branches b ON cs.branch_id = b.id
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
            (branch_id, class_type_id, trainer_id, name, day_of_week, start_time, end_time, capacity, room, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.branch_id,
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

        if request.branch_id is not None:
            update_fields.append("branch_id = %s")
            params.append(request.branch_id)
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
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get all class bookings"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if branch_id:
            where_clauses.append("cb.branch_id = %s")
            params.append(branch_id)
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
                   u.name as member_name, u.email as member_email, u.phone as member_phone,
                   b.name as branch_name
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN class_types ct ON cs.class_type_id = ct.id
            JOIN users u ON cb.user_id = u.id
            LEFT JOIN branches b ON cb.branch_id = b.id
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
def get_today_class_schedule(
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get today's class schedule with bookings"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        today = date.today()
        day_of_week_sunday = (today.weekday() + 1) % 7

        branch_filter = ""
        params = [today, today, day_of_week_sunday]
        if branch_id:
            branch_filter = " AND cs.branch_id = %s"
            params.append(branch_id)

        cursor.execute(
            f"""
            SELECT cs.*,
                   ct.name as class_name, ct.color,
                   u.name as trainer_name,
                   b.name as branch_name,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.schedule_id = cs.id AND cb.class_date = %s AND cb.status IN ('booked', 'attended')) as booked_count,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.schedule_id = cs.id AND cb.class_date = %s AND cb.status = 'attended') as attended_count
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN branches b ON cs.branch_id = b.id
            WHERE cs.day_of_week = %s AND cs.is_active = 1{branch_filter}
            ORDER BY cs.start_time ASC
            """,
            params,
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


@router.get("/bookings/calendar")
def get_bookings_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get bookings summary grouped by date for calendar view, plus schedules for each date"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        branch_filter = ""
        params_summary = [start_date, end_date]
        params_schedules = [start_date, end_date]
        if branch_id:
            branch_filter = " AND cb.branch_id = %s"
            params_summary.append(branch_id)

        # Get booking counts per date
        cursor.execute(
            f"""
            SELECT cb.class_date,
                   COUNT(*) as total_bookings,
                   SUM(CASE WHEN cb.status = 'booked' THEN 1 ELSE 0 END) as booked_count,
                   SUM(CASE WHEN cb.status = 'attended' THEN 1 ELSE 0 END) as attended_count,
                   COUNT(DISTINCT cb.schedule_id) as class_count
            FROM class_bookings cb
            WHERE cb.class_date BETWEEN %s AND %s
            AND cb.status != 'cancelled'
            {branch_filter}
            GROUP BY cb.class_date
            ORDER BY cb.class_date
            """,
            params_summary,
        )
        date_summary = cursor.fetchall()

        # Convert dates to string
        for d in date_summary:
            d["class_date"] = str(d["class_date"])

        # Get schedules with their bookings for this date range
        schedule_branch_filter = ""
        if branch_id:
            schedule_branch_filter = " AND cs.branch_id = %s"
            params_schedules.append(branch_id)

        cursor.execute(
            f"""
            SELECT DISTINCT cb.class_date, cs.id as schedule_id,
                   ct.name as class_name, ct.color,
                   cs.start_time, cs.end_time, cs.room, cs.capacity,
                   u.name as trainer_name,
                   (SELECT COUNT(*) FROM class_bookings cb2
                    WHERE cb2.schedule_id = cs.id AND cb2.class_date = cb.class_date
                    AND cb2.status IN ('booked', 'attended')) as booked_count
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            WHERE cb.class_date BETWEEN %s AND %s
            AND cb.status != 'cancelled'
            {schedule_branch_filter}
            GROUP BY cb.class_date, cs.id
            ORDER BY cb.class_date, cs.start_time
            """,
            params_schedules,
        )
        schedules_by_date_raw = cursor.fetchall()

        schedules_by_date = {}
        for s in schedules_by_date_raw:
            d = str(s["class_date"])
            s["class_date"] = d
            s["start_time"] = str(s["start_time"])
            s["end_time"] = str(s["end_time"])
            if d not in schedules_by_date:
                schedules_by_date[d] = []
            schedules_by_date[d].append(s)

        return {
            "success": True,
            "data": {
                "date_summary": date_summary,
                "schedules_by_date": schedules_by_date,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bookings calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CALENDAR_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/bookings/date/{class_date}")
def get_bookings_by_date(
    class_date: date,
    branch_id: Optional[int] = Depends(get_branch_id),
    auth: dict = Depends(verify_bearer_token),
):
    """Get detailed bookings for a specific date grouped by schedule"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        day_of_week_sunday = (class_date.weekday() + 1) % 7

        branch_filter = ""
        params = [class_date, class_date, day_of_week_sunday]
        if branch_id:
            branch_filter = " AND cs.branch_id = %s"
            params.append(branch_id)

        # Get schedules for this day of week with booking info
        cursor.execute(
            f"""
            SELECT cs.id as schedule_id,
                   ct.name as class_name, ct.color,
                   cs.start_time, cs.end_time, cs.room, cs.capacity,
                   u.name as trainer_name,
                   b.name as branch_name,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.schedule_id = cs.id AND cb.class_date = %s
                    AND cb.status IN ('booked', 'attended')) as booked_count,
                   (SELECT COUNT(*) FROM class_bookings cb
                    WHERE cb.schedule_id = cs.id AND cb.class_date = %s
                    AND cb.status = 'attended') as attended_count
            FROM class_schedules cs
            JOIN class_types ct ON cs.class_type_id = ct.id
            LEFT JOIN trainers t ON cs.trainer_id = t.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN branches b ON cs.branch_id = b.id
            WHERE cs.day_of_week = %s AND cs.is_active = 1{branch_filter}
            ORDER BY cs.start_time ASC
            """,
            params,
        )
        schedules = cursor.fetchall()

        # Get bookings for each schedule
        for s in schedules:
            s["start_time"] = str(s["start_time"])
            s["end_time"] = str(s["end_time"])
            s["available_slots"] = s["capacity"] - s["booked_count"]

            booking_params = [s["schedule_id"], class_date]
            cursor.execute(
                """
                SELECT cb.id, cb.status, cb.access_type, cb.booked_at,
                       u.name as member_name, u.email as member_email, u.phone as member_phone
                FROM class_bookings cb
                JOIN users u ON cb.user_id = u.id
                WHERE cb.schedule_id = %s AND cb.class_date = %s
                AND cb.status != 'cancelled'
                ORDER BY cb.booked_at ASC
                """,
                booking_params,
            )
            s["members"] = cursor.fetchall()
            for m in s["members"]:
                if m.get("booked_at"):
                    m["booked_at"] = str(m["booked_at"])

        return {
            "success": True,
            "data": schedules,
            "date": str(class_date),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bookings by date: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_DATE_BOOKINGS_FAILED", "message": str(e)},
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
                SET used_classes = used_classes - 1
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


# ============== Class Packages ==============

@router.get("/packages")
def get_class_packages(
    auth: dict = Depends(verify_bearer_token),
):
    """Get all class packages"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT cp.*, ct.name as class_type_name
            FROM class_packages cp
            LEFT JOIN class_types ct ON cp.class_type_id = ct.id
            WHERE cp.is_active = 1
            ORDER BY cp.price ASC
            """
        )
        packages = cursor.fetchall()

        return {
            "success": True,
            "data": packages,
        }
    except Exception as e:
        logger.error(f"Error fetching class packages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "FETCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Member Class Passes (CMS) ==============

@router.get("/member-passes")
def get_member_class_passes(
    user_id: int = None,
    status_filter: str = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(get_branch_id),
):
    """Get member class passes grouped by member"""
    check_permission(auth, "class.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = ["1=1"]
        params = []

        if user_id:
            where_clauses.append("mcp.user_id = %s")
            params.append(user_id)

        if status_filter:
            where_clauses.append("mcp.status = %s")
            params.append(status_filter)

        if branch_id:
            where_clauses.append("mcp.transaction_id IN (SELECT id FROM transactions WHERE branch_id = %s)")
            params.append(branch_id)

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # Count distinct members
        cursor.execute(
            f"SELECT COUNT(DISTINCT mcp.user_id) as total FROM member_class_passes mcp {where_sql}",
            params,
        )
        total = cursor.fetchone()["total"]

        # Get paginated member IDs
        offset_val = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT mcp.user_id, u.name as member_name, u.email as member_email, u.phone as member_phone,
                   COUNT(*) as pass_count,
                   SUM(mcp.total_classes) as total_classes,
                   SUM(mcp.used_classes) as total_used,
                   SUM(mcp.remaining_classes) as total_remaining,
                   SUM(CASE WHEN mcp.status = 'active' THEN 1 ELSE 0 END) as active_count
            FROM member_class_passes mcp
            JOIN users u ON mcp.user_id = u.id
            {where_sql}
            GROUP BY mcp.user_id, u.name, u.email, u.phone
            ORDER BY active_count DESC, total_remaining DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset_val],
        )
        members = cursor.fetchall()
        member_ids = [m["user_id"] for m in members]

        # Fetch all passes for these members
        if member_ids:
            placeholders = ",".join(["%s"] * len(member_ids))
            pass_where = where_clauses.copy()
            pass_params = params.copy()
            pass_where.append(f"mcp.user_id IN ({placeholders})")
            pass_params.extend(member_ids)
            pass_where_sql = "WHERE " + " AND ".join(pass_where)

            cursor.execute(
                f"""
                SELECT mcp.*, cp.name as package_name, cp.class_count as package_class_count,
                       cp.valid_days, cp.price
                FROM member_class_passes mcp
                JOIN class_packages cp ON mcp.class_package_id = cp.id
                {pass_where_sql}
                ORDER BY mcp.status = 'active' DESC, mcp.created_at DESC
                """,
                pass_params,
            )
            all_passes = cursor.fetchall()

            # Group passes by user_id
            passes_by_user = {}
            for p in all_passes:
                p["price"] = float(p["price"]) if p.get("price") else 0
                if p.get("expire_date") and p["status"] == "active":
                    remaining_days = (p["expire_date"] - date.today()).days
                    p["remaining_days"] = max(0, remaining_days)
                else:
                    p["remaining_days"] = None
                passes_by_user.setdefault(p["user_id"], []).append(p)
        else:
            passes_by_user = {}

        # Build response
        data = []
        for m in members:
            m["total_classes"] = int(m["total_classes"] or 0)
            m["total_used"] = int(m["total_used"] or 0)
            m["total_remaining"] = int(m["total_remaining"] or 0)
            m["active_count"] = int(m["active_count"] or 0)
            m["passes"] = passes_by_user.get(m["user_id"], [])
            data.append(m)

        return {
            "success": True,
            "data": data,
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
        logger.error(f"Error fetching member class passes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "FETCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Book Class for Member (CMS) ==============

@router.post("/bookings", status_code=status.HTTP_201_CREATED)
def book_class_for_member(
    request: BookClassForMemberRequest,
    auth: dict = Depends(verify_bearer_token),
):
    """Book a class on behalf of a member (CMS staff)"""
    check_permission(auth, "class.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Validate user exists and is a member
        cursor.execute("SELECT id, name FROM users WHERE id = %s AND is_active = 1", (request.user_id,))
        member = cursor.fetchone()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "Member tidak ditemukan"},
            )

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

        # Validate date matches day of week
        day_of_week_sunday = (request.class_date.weekday() + 1) % 7
        if day_of_week_sunday != schedule["day_of_week"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_DATE", "message": "Tanggal tidak sesuai dengan jadwal kelas"},
            )

        # Check if already booked
        cursor.execute(
            """
            SELECT id FROM class_bookings
            WHERE user_id = %s AND schedule_id = %s AND class_date = %s AND status != 'cancelled'
            """,
            (request.user_id, request.schedule_id, request.class_date),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ALREADY_BOOKED", "message": "Member sudah booking kelas ini"},
            )

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

        # Check membership/class pass for the member
        cursor.execute(
            """
            SELECT mm.*, mp.include_classes, mp.class_quota
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.user_id = %s AND mm.status = 'active'
            ORDER BY mm.created_at DESC
            LIMIT 1
            """,
            (request.user_id,),
        )
        membership = cursor.fetchone()

        access_type = None
        booking_membership_id = None
        booking_class_pass_id = None

        if membership and membership.get("include_classes"):
            if membership["class_remaining"] is None or membership["class_remaining"] > 0:
                access_type = "membership"
                booking_membership_id = membership["id"]
                if membership["class_remaining"] is not None:
                    cursor.execute(
                        "UPDATE member_memberships SET class_remaining = class_remaining - 1 WHERE id = %s",
                        (membership["id"],),
                    )

        if not access_type:
            cursor.execute(
                """
                SELECT * FROM member_class_passes
                WHERE user_id = %s AND status = 'active' AND remaining_classes > 0
                ORDER BY expire_date ASC
                LIMIT 1
                """,
                (request.user_id,),
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
                        "message": "Member tidak memiliki akses kelas (membership/class pass)",
                    },
                )

        # Create booking
        cursor.execute(
            """
            INSERT INTO class_bookings
            (branch_id, user_id, schedule_id, class_date, access_type, membership_id, class_pass_id,
             status, booked_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                schedule["branch_id"], request.user_id, request.schedule_id, request.class_date,
                access_type, booking_membership_id, booking_class_pass_id,
                "booked", datetime.now(), datetime.now(),
            ),
        )
        booking_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "message": f"Booking kelas berhasil untuk {member['name']}",
            "data": {
                "booking_id": booking_id,
                "member_name": member["name"],
                "class_name": schedule["class_name"],
                "class_date": str(request.class_date),
                "start_time": str(schedule["start_time"]),
                "room": schedule["room"],
                "access_type": access_type,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error booking class for member: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "BOOK_CLASS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
