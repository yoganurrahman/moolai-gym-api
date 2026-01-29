"""
Member Profile Router - Member profile management
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, EmailStr

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Member - Profile"])


# ============== Request Models ==============

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^[0-9+\-\s]{8,15}$")
    address: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = Field(None, pattern=r"^(male|female)$")


class SetDefaultBranchRequest(BaseModel):
    branch_id: Optional[int] = Field(None, description="ID cabang default, null untuk hapus default")


# ============== Endpoints ==============

@router.get("")
def get_my_profile(auth: dict = Depends(verify_bearer_token)):
    """Get my profile"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT u.id, u.email, u.name, u.phone, u.address, u.date_of_birth, u.gender,
                   u.avatar, u.has_pin, u.default_branch_id, u.created_at,
                   b.code as default_branch_code, b.name as default_branch_name
            FROM users u
            LEFT JOIN branches b ON u.default_branch_id = b.id
            WHERE u.id = %s
            """,
            (auth["user_id"],),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        user["has_pin"] = bool(user.get("has_pin"))

        # Build default branch info
        default_branch = None
        if user.get("default_branch_id"):
            default_branch = {
                "id": user.pop("default_branch_id"),
                "code": user.pop("default_branch_code"),
                "name": user.pop("default_branch_name"),
            }
        else:
            user.pop("default_branch_id", None)
            user.pop("default_branch_code", None)
            user.pop("default_branch_name", None)
        user["default_branch"] = default_branch

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
            (auth["user_id"],),
        )
        membership = cursor.fetchone()

        return {
            "success": True,
            "data": {
                "user": user,
                "membership": membership,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PROFILE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("")
def update_my_profile(request: UpdateProfileRequest, auth: dict = Depends(verify_bearer_token)):
    """Update my profile"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Build update query
        update_fields = []
        params = []

        if request.name is not None:
            update_fields.append("name = %s")
            params.append(request.name)
        if request.phone is not None:
            update_fields.append("phone = %s")
            params.append(request.phone)
        if request.address is not None:
            update_fields.append("address = %s")
            params.append(request.address)
        if request.birth_date is not None:
            update_fields.append("date_of_birth = %s")
            params.append(request.birth_date)
        if request.gender is not None:
            update_fields.append("gender = %s")
            params.append(request.gender)

        if not update_fields:
            return {"success": True, "message": "Tidak ada perubahan"}

        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        params.append(auth["user_id"])

        cursor.execute(
            f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        conn.commit()

        return {
            "success": True,
            "message": "Profil berhasil diupdate",
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_PROFILE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/default-branch")
def set_default_branch(request: SetDefaultBranchRequest, auth: dict = Depends(verify_bearer_token)):
    """Set or change member's default branch"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # If branch_id provided, validate it exists and is active
        if request.branch_id is not None:
            cursor.execute(
                "SELECT id, code, name FROM branches WHERE id = %s AND is_active = 1",
                (request.branch_id,),
            )
            branch = cursor.fetchone()
            if not branch:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "BRANCH_NOT_FOUND", "message": "Cabang tidak ditemukan atau tidak aktif"},
                )

        cursor.execute(
            "UPDATE users SET default_branch_id = %s, updated_at = %s WHERE id = %s",
            (request.branch_id, datetime.now(), auth["user_id"]),
        )
        conn.commit()

        if request.branch_id is None:
            return {
                "success": True,
                "message": "Default cabang berhasil dihapus",
                "data": {"default_branch": None},
            }

        return {
            "success": True,
            "message": f"Default cabang berhasil diubah ke {branch['name']}",
            "data": {
                "default_branch": {
                    "id": branch["id"],
                    "code": branch["code"],
                    "name": branch["name"],
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error setting default branch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SET_BRANCH_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/qr-code")
def get_my_qr_code(auth: dict = Depends(verify_bearer_token)):
    """Get member's QR code data for check-in"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT mm.membership_code, mm.status, mm.end_date, mm.visit_remaining,
                   mp.name as package_name, mp.package_type,
                   u.name as member_name
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            JOIN users u ON mm.user_id = u.id
            WHERE mm.user_id = %s AND mm.status = 'active'
            ORDER BY mm.created_at DESC
            LIMIT 1
            """,
            (auth["user_id"],),
        )
        membership = cursor.fetchone()

        if not membership:
            return {
                "success": True,
                "data": {
                    "has_active_membership": False,
                    "message": "Tidak memiliki membership aktif",
                },
            }

        # QR code content is the membership code
        return {
            "success": True,
            "data": {
                "has_active_membership": True,
                "qr_content": membership["membership_code"],
                "member_name": membership["member_name"],
                "package_name": membership["package_name"],
                "package_type": membership["package_type"],
                "end_date": str(membership["end_date"]) if membership["end_date"] else None,
                "visit_remaining": membership["visit_remaining"],
            },
        }

    except Exception as e:
        logger.error(f"Error getting QR code: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_QR_CODE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
