"""
Member Check-ins Router - Member check-in/out via QR
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.db import get_db_connection
from app.middleware import verify_bearer_token, require_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checkins", tags=["Member - Check-ins"])


# ============== Endpoints ==============

@router.post("/scan")
def scan_checkin(branch_id: int = Depends(require_branch_id), auth: dict = Depends(verify_bearer_token)):
    """Check-in member via QR scan"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = auth["user_id"]

        # Get active membership
        cursor.execute(
            """
            SELECT mm.*, mp.name as package_name, mp.package_type
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            WHERE mm.user_id = %s AND mm.status = 'active'
            ORDER BY mm.created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        membership = cursor.fetchone()

        # Determine checkin type and access source
        checkin_type = None
        checkin_membership_id = None
        checkin_class_pass_id = None

        if membership:
            # Check if membership expired
            if membership["end_date"] and membership["end_date"] < date.today():
                # Update status to expired
                cursor.execute(
                    "UPDATE member_memberships SET status = 'expired', updated_at = %s WHERE id = %s",
                    (datetime.now(), membership["id"]),
                )
                conn.commit()
                membership = None  # Treat as no membership
            elif membership["package_type"] == "visit":
                if not membership["visit_remaining"] or membership["visit_remaining"] <= 0:
                    membership = None  # No visits left, check class pass
                else:
                    checkin_type = "gym"
                    checkin_membership_id = membership["id"]
            else:
                checkin_type = "gym"
                checkin_membership_id = membership["id"]

        # If no valid membership, check for class pass (class-only check-in)
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
                (user_id, date.today()),
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
                        "message": "Anda tidak memiliki membership aktif atau class pass yang valid",
                    },
                )

        # Check if already checked in (no checkout yet)
        cursor.execute(
            """
            SELECT * FROM member_checkins
            WHERE user_id = %s AND checkout_time IS NULL
            ORDER BY checkin_time DESC
            LIMIT 1
            """,
            (user_id,),
        )
        open_checkin = cursor.fetchone()

        if open_checkin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ALREADY_CHECKED_IN",
                    "message": "Anda sudah check-in. Silakan check-out terlebih dahulu.",
                },
            )

        # Get cooldown setting
        cursor.execute("SELECT value FROM settings WHERE `key` = 'checkin_cooldown_minutes'")
        setting = cursor.fetchone()
        cooldown_minutes = int(setting["value"]) if setting else 60

        # Check cooldown period
        cursor.execute(
            """
            SELECT * FROM member_checkins
            WHERE user_id = %s AND checkout_time IS NOT NULL AND checkout_time <= NOW() AND checkin_time > %s
            ORDER BY checkin_time DESC
            LIMIT 1
            """,
            (user_id, datetime.now() - timedelta(minutes=cooldown_minutes)),
        )
        recent_checkin = cursor.fetchone()

        if recent_checkin:
            next_checkin_time = recent_checkin["checkout_time"] + timedelta(minutes=cooldown_minutes)
            if datetime.now() < next_checkin_time:
                remaining_minutes = int((next_checkin_time - datetime.now()).total_seconds() / 60)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "CHECKIN_COOLDOWN",
                        "message": f"Anda baru saja check-in. Coba lagi dalam {remaining_minutes} menit.",
                    },
                )

        # Create check-in
        cursor.execute(
            """
            INSERT INTO member_checkins
            (branch_id, user_id, checkin_type, membership_id, class_pass_id, checkin_time, checkin_method, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (branch_id, user_id, checkin_type, checkin_membership_id, checkin_class_pass_id,
             datetime.now(), "qr_code", datetime.now()),
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

        # Build response based on checkin type
        if checkin_type == "gym":
            return {
                "success": True,
                "message": "Check-in berhasil",
                "data": {
                    "checkin_id": checkin_id,
                    "checkin_type": "gym",
                    "checkin_time": datetime.now().isoformat(),
                    "membership": {
                        "code": membership["membership_code"],
                        "package": membership["package_name"],
                        "end_date": str(membership["end_date"]) if membership["end_date"] else None,
                        "visit_remaining": new_visit_remaining,
                    },
                },
            }
        else:
            return {
                "success": True,
                "message": "Check-in kelas berhasil",
                "data": {
                    "checkin_id": checkin_id,
                    "checkin_type": "class_only",
                    "checkin_time": datetime.now().isoformat(),
                    "class_pass": {
                        "id": class_pass["id"],
                        "name": class_pass["pass_name"],
                        "remaining_classes": class_pass["remaining_classes"],
                    },
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during check-in: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKIN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/checkout")
def checkout(auth: dict = Depends(verify_bearer_token)):
    """Check-out member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Find active check-in
        cursor.execute(
            """
            SELECT * FROM member_checkins
            WHERE user_id = %s AND checkout_time IS NULL
            ORDER BY checkin_time DESC
            LIMIT 1
            """,
            (auth["user_id"],),
        )
        checkin = cursor.fetchone()

        if not checkin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "NO_ACTIVE_CHECKIN",
                    "message": "Anda belum check-in",
                },
            )

        # Update checkout time
        checkout_time = datetime.now()
        cursor.execute(
            "UPDATE member_checkins SET checkout_time = %s WHERE id = %s",
            (checkout_time, checkin["id"]),
        )
        conn.commit()

        # Calculate duration
        duration_minutes = int((checkout_time - checkin["checkin_time"]).total_seconds() / 60)

        return {
            "success": True,
            "message": "Check-out berhasil",
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
        logger.error(f"Error during check-out: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKOUT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/status")
def get_checkin_status(auth: dict = Depends(verify_bearer_token)):
    """Get current check-in status"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Find active check-in
        cursor.execute(
            """
            SELECT mc.*, mm.membership_code, mp.name as package_name,
                   br.name as branch_name, br.code as branch_code
            FROM member_checkins mc
            LEFT JOIN member_memberships mm ON mc.membership_id = mm.id
            LEFT JOIN membership_packages mp ON mm.package_id = mp.id
            LEFT JOIN branches br ON mc.branch_id = br.id
            WHERE mc.user_id = %s AND mc.checkout_time IS NULL
            ORDER BY mc.checkin_time DESC
            LIMIT 1
            """,
            (auth["user_id"],),
        )
        checkin = cursor.fetchone()

        if checkin:
            duration_minutes = int((datetime.now() - checkin["checkin_time"]).total_seconds() / 60)
            return {
                "success": True,
                "data": {
                    "is_checked_in": True,
                    "checkin_id": checkin["id"],
                    "checkin_time": checkin["checkin_time"].isoformat(),
                    "duration_minutes": duration_minutes,
                    "membership_code": checkin["membership_code"],
                    "package_name": checkin["package_name"],
                    "branch_name": checkin.get("branch_name"),
                    "branch_code": checkin.get("branch_code"),
                },
            }
        else:
            return {
                "success": True,
                "data": {
                    "is_checked_in": False,
                },
            }

    except Exception as e:
        logger.error(f"Error getting check-in status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_STATUS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/history")
def get_my_checkin_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_bearer_token),
):
    """Get check-in history for logged-in member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Count total
        cursor.execute(
            "SELECT COUNT(*) as total FROM member_checkins WHERE user_id = %s",
            (auth["user_id"],),
        )
        total = cursor.fetchone()["total"]

        # Get data
        offset = (page - 1) * limit
        cursor.execute(
            """
            SELECT mc.*, mm.membership_code, mp.name as package_name,
                   br.name as branch_name, br.code as branch_code
            FROM member_checkins mc
            LEFT JOIN member_memberships mm ON mc.membership_id = mm.id
            LEFT JOIN membership_packages mp ON mm.package_id = mp.id
            LEFT JOIN branches br ON mc.branch_id = br.id
            WHERE mc.user_id = %s
            ORDER BY mc.checkin_time DESC
            LIMIT %s OFFSET %s
            """,
            (auth["user_id"], limit, offset),
        )
        checkins = cursor.fetchall()

        # Calculate duration for each
        for c in checkins:
            if c["checkout_time"]:
                c["duration_minutes"] = int(
                    (c["checkout_time"] - c["checkin_time"]).total_seconds() / 60
                )
            else:
                c["duration_minutes"] = None

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

    except Exception as e:
        logger.error(f"Error getting check-in history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_HISTORY_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
