"""
CMS Check-ins Router - Admin management of check-ins
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission, get_branch_id, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checkins", tags=["CMS - Check-ins"])


# ============== Request Models ==============

class ManualCheckinRequest(BaseModel):
    user_id: int
    checkin_type: Optional[str] = None  # 'gym' or 'class_only', auto-detected if not provided
    notes: Optional[str] = None


# ============== Endpoints ==============

@router.get("")
def get_all_checkins(
    user_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    currently_in: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get all check-ins with filters"""
    check_permission(auth, "checkin.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        where_clauses = []
        params = []

        if branch_id:
            where_clauses.append("mc.branch_id = %s")
            params.append(branch_id)

        if user_id:
            where_clauses.append("mc.user_id = %s")
            params.append(user_id)

        if search:
            where_clauses.append("(u.name LIKE %s OR u.email LIKE %s OR mm.membership_code LIKE %s)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        if date_from:
            where_clauses.append("DATE(mc.checkin_time) >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("DATE(mc.checkin_time) <= %s")
            params.append(date_to)

        if currently_in is True:
            where_clauses.append("mc.checkout_time IS NULL")
        elif currently_in is False:
            where_clauses.append("mc.checkout_time IS NOT NULL")

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        cursor.execute(
            f"""
            SELECT COUNT(*) as total
            FROM member_checkins mc
            JOIN users u ON mc.user_id = u.id
            LEFT JOIN member_memberships mm ON mc.membership_id = mm.id
            LEFT JOIN member_class_passes mcp ON mc.class_pass_id = mcp.id
            LEFT JOIN class_pass_types cpt ON mcp.class_pass_type_id = cpt.id
            LEFT JOIN branches b ON mc.branch_id = b.id
            {where_sql}
            """,
            params
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT mc.*, u.name as member_name, u.email as member_email, u.phone as member_phone,
                   mm.membership_code, mp.name as package_name,
                   staff.name as checked_in_by_name,
                   cpt.name as class_pass_name,
                   b.name as branch_name, b.code as branch_code
            FROM member_checkins mc
            JOIN users u ON mc.user_id = u.id
            LEFT JOIN member_memberships mm ON mc.membership_id = mm.id
            LEFT JOIN membership_packages mp ON mm.package_id = mp.id
            LEFT JOIN users staff ON mc.checked_in_by = staff.id
            LEFT JOIN member_class_passes mcp ON mc.class_pass_id = mcp.id
            LEFT JOIN class_pass_types cpt ON mcp.class_pass_type_id = cpt.id
            LEFT JOIN branches b ON mc.branch_id = b.id
            {where_sql}
            ORDER BY mc.checkin_time DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        checkins = cursor.fetchall()

        # Calculate duration for each
        for c in checkins:
            if c["checkout_time"]:
                c["duration_minutes"] = int(
                    (c["checkout_time"] - c["checkin_time"]).total_seconds() / 60
                )
            else:
                c["duration_minutes"] = int(
                    (datetime.now() - c["checkin_time"]).total_seconds() / 60
                )
                c["is_currently_in"] = True

        return {
            "success": True,
            "data": checkins,
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
        logger.error(f"Error getting check-ins: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CHECKINS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/today")
def get_today_checkins(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get today's check-ins with summary"""
    check_permission(auth, "checkin.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())

        branch_filter = ""
        branch_params = ()
        if branch_id:
            branch_filter = " AND mc.branch_id = %s"
            branch_params = (branch_id,)

        # Count total
        cursor.execute(
            f"""
            SELECT COUNT(*) as total FROM member_checkins mc
            WHERE mc.checkin_time BETWEEN %s AND %s{branch_filter}
            """,
            (today_start, today_end) + branch_params,
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            f"""
            SELECT mc.*, u.name as member_name, u.email as member_email, u.phone as member_phone,
                   mm.membership_code, mp.name as package_name,
                   cpt.name as class_pass_name,
                   b.name as branch_name, b.code as branch_code
            FROM member_checkins mc
            JOIN users u ON mc.user_id = u.id
            LEFT JOIN member_memberships mm ON mc.membership_id = mm.id
            LEFT JOIN membership_packages mp ON mm.package_id = mp.id
            LEFT JOIN member_class_passes mcp ON mc.class_pass_id = mcp.id
            LEFT JOIN class_pass_types cpt ON mcp.class_pass_type_id = cpt.id
            LEFT JOIN branches b ON mc.branch_id = b.id
            WHERE mc.checkin_time BETWEEN %s AND %s{branch_filter}
            ORDER BY mc.checkin_time DESC
            LIMIT %s OFFSET %s
            """,
            (today_start, today_end) + branch_params + (limit, offset),
        )
        checkins = cursor.fetchall()

        # Get summary
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as total_checkins,
                COUNT(DISTINCT mc.user_id) as unique_members,
                COUNT(CASE WHEN mc.checkout_time IS NULL THEN 1 END) as currently_in,
                COUNT(CASE WHEN mc.checkin_type = 'gym' THEN 1 END) as gym_checkins,
                COUNT(CASE WHEN mc.checkin_type = 'class_only' THEN 1 END) as class_only_checkins
            FROM member_checkins mc
            WHERE mc.checkin_time BETWEEN %s AND %s{branch_filter}
            """,
            (today_start, today_end) + branch_params,
        )
        summary = cursor.fetchone()

        return {
            "success": True,
            "data": checkins,
            "summary": summary,
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
        logger.error(f"Error getting today's check-ins: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CHECKINS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/currently-in")
def get_currently_in_members(
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get members who are currently in the gym"""
    check_permission(auth, "checkin.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        branch_filter = ""
        branch_params = ()
        if branch_id:
            branch_filter = " AND mc.branch_id = %s"
            branch_params = (branch_id,)

        cursor.execute(
            f"""
            SELECT mc.*, u.name as member_name, u.email as member_email, u.phone as member_phone,
                   mm.membership_code, mp.name as package_name,
                   cpt.name as class_pass_name,
                   b.name as branch_name, b.code as branch_code
            FROM member_checkins mc
            JOIN users u ON mc.user_id = u.id
            LEFT JOIN member_memberships mm ON mc.membership_id = mm.id
            LEFT JOIN membership_packages mp ON mm.package_id = mp.id
            LEFT JOIN member_class_passes mcp ON mc.class_pass_id = mcp.id
            LEFT JOIN class_pass_types cpt ON mcp.class_pass_type_id = cpt.id
            LEFT JOIN branches b ON mc.branch_id = b.id
            WHERE mc.checkout_time IS NULL{branch_filter}
            ORDER BY mc.checkin_time ASC
            """,
            branch_params,
        )
        members = cursor.fetchall()

        for m in members:
            m["duration_minutes"] = int(
                (datetime.now() - m["checkin_time"]).total_seconds() / 60
            )

        return {
            "success": True,
            "data": members,
            "total": len(members),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting currently in members: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_CURRENTLY_IN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/manual")
def manual_checkin(
    request: ManualCheckinRequest,
    auth: dict = Depends(verify_bearer_token),
    branch_id: int = Depends(require_branch_id),
):
    """Manual check-in by staff"""
    check_permission(auth, "checkin.create")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get user info
        cursor.execute("SELECT id, name FROM users WHERE id = %s", (request.user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Determine checkin type and access source
        checkin_type = None
        checkin_membership_id = None
        checkin_class_pass_id = None
        membership = None
        class_pass = None

        # Get user's active membership
        cursor.execute(
            """
            SELECT mm.*, mp.name as package_name, mp.package_type
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.user_id = %s AND mm.status = 'active'
            ORDER BY mm.created_at DESC
            LIMIT 1
            """,
            (request.user_id,),
        )
        membership = cursor.fetchone()

        if membership:
            # Check if membership expired
            if membership["end_date"] and membership["end_date"] < date.today():
                membership = None  # Expired, check class pass
            elif membership["package_type"] == "visit":
                if not membership["visit_remaining"] or membership["visit_remaining"] <= 0:
                    membership = None  # No visits left
                else:
                    checkin_type = "gym"
                    checkin_membership_id = membership["id"]
            else:
                checkin_type = "gym"
                checkin_membership_id = membership["id"]

        # Override checkin_type if staff explicitly set class_only
        if request.checkin_type == "class_only":
            checkin_type = None  # Force class pass lookup

        # If no gym access or explicitly class_only, check for class pass
        if not checkin_type:
            cursor.execute(
                """
                SELECT mcp.*, cpt.name as pass_name
                FROM member_class_passes mcp
                JOIN class_pass_types cpt ON mcp.class_pass_type_id = cpt.id
                WHERE mcp.user_id = %s AND mcp.status = 'active' AND mcp.remaining_classes > 0
                  AND (mcp.expire_date IS NULL OR mcp.expire_date >= %s)
                ORDER BY mcp.expire_date ASC
                LIMIT 1
                """,
                (request.user_id, date.today()),
            )
            class_pass = cursor.fetchone()

            if class_pass:
                checkin_type = "class_only"
                checkin_class_pass_id = class_pass["id"]
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "NO_ACTIVE_MEMBERSHIP",
                        "message": "Member tidak memiliki membership aktif atau class pass yang valid",
                    },
                )

        # Check if already checked in
        cursor.execute(
            """
            SELECT id FROM member_checkins
            WHERE user_id = %s AND checkout_time IS NULL
            """,
            (request.user_id,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ALREADY_CHECKED_IN",
                    "message": "Member sudah check-in dan belum checkout",
                },
            )

        # Create check-in
        cursor.execute(
            """
            INSERT INTO member_checkins
            (branch_id, user_id, checkin_type, membership_id, class_pass_id,
             checkin_time, checkin_method, checked_in_by, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_id,
                request.user_id,
                checkin_type,
                checkin_membership_id,
                checkin_class_pass_id,
                datetime.now(),
                "manual",
                auth["user_id"],
                request.notes,
                datetime.now(),
            ),
        )
        checkin_id = cursor.lastrowid

        # Deduct visit for visit-based membership
        new_visit_remaining = None
        if checkin_type == "gym" and membership and membership["package_type"] == "visit":
            cursor.execute(
                """
                UPDATE member_memberships
                SET visit_remaining = visit_remaining - 1, updated_at = %s
                WHERE id = %s
                """,
                (datetime.now(), membership["id"]),
            )
            new_visit_remaining = membership["visit_remaining"] - 1

        conn.commit()

        # Build response
        response_data = {
            "checkin_id": checkin_id,
            "checkin_type": checkin_type,
            "member_name": user["name"],
        }
        if checkin_type == "gym":
            response_data["package_name"] = membership["package_name"]
            response_data["visit_remaining"] = new_visit_remaining
        else:
            response_data["class_pass_name"] = class_pass["pass_name"]
            response_data["remaining_classes"] = class_pass["remaining_classes"]

        return {
            "success": True,
            "message": f"Check-in manual berhasil untuk {user['name']}",
            "data": response_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during manual check-in: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MANUAL_CHECKIN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/{checkin_id}/checkout")
def force_checkout(checkin_id: int, auth: dict = Depends(verify_bearer_token)):
    """Force checkout a member (admin)"""
    check_permission(auth, "checkin.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check checkin exists and not checked out
        cursor.execute(
            """
            SELECT mc.*, u.name as member_name
            FROM member_checkins mc
            JOIN users u ON mc.user_id = u.id
            WHERE mc.id = %s
            """,
            (checkin_id,),
        )
        checkin = cursor.fetchone()

        if not checkin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "CHECKIN_NOT_FOUND", "message": "Check-in tidak ditemukan"},
            )

        if checkin["checkout_time"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ALREADY_CHECKED_OUT", "message": "Member sudah checkout"},
            )

        # Force checkout
        checkout_time = datetime.now()
        cursor.execute(
            "UPDATE member_checkins SET checkout_time = %s WHERE id = %s",
            (checkout_time, checkin_id),
        )
        conn.commit()

        duration_minutes = int((checkout_time - checkin["checkin_time"]).total_seconds() / 60)

        return {
            "success": True,
            "message": f"Checkout berhasil untuk {checkin['member_name']}",
            "data": {
                "checkin_time": checkin["checkin_time"].isoformat(),
                "checkout_time": checkout_time.isoformat(),
                "duration_minutes": duration_minutes,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during force checkout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "FORCE_CHECKOUT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
