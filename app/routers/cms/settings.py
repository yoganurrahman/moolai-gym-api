"""
CMS Settings Router - App Settings Management
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["CMS - Settings"])


# ============== Request Models ==============

class SettingItem(BaseModel):
    key: str
    value: str


class SettingsUpdateRequest(BaseModel):
    settings: List[SettingItem]


# ============== Category Mapping ==============

SETTING_GROUPS = {
    "Informasi Gym": ["gym_name", "gym_address", "gym_phone", "gym_email"],
    "Pajak": ["tax_enabled", "tax_name", "tax_percentage"],
    "Service Charge": ["service_charge_enabled", "service_charge_percentage"],
    "Check-in": ["checkin_cooldown_minutes"],
    "Booking Kelas": ["class_booking_advance_days", "class_cancel_hours"],
    "Booking PT": ["pt_booking_advance_days", "pt_cancel_hours"],
    "Subscription": ["subscription_retry_days", "subscription_retry_count"],
}


# ============== Endpoints ==============

@router.get("")
def get_settings(auth: dict = Depends(verify_bearer_token)):
    """Get all settings grouped by category"""
    check_permission(auth, "settings.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT `key`, `value`, `type`, `description` FROM settings ORDER BY id")
        rows = cursor.fetchall()

        settings_map = {row["key"]: row for row in rows}

        grouped = []
        for group_name, keys in SETTING_GROUPS.items():
            items = []
            for key in keys:
                if key in settings_map:
                    items.append(settings_map[key])
            if items:
                grouped.append({"group": group_name, "items": items})

        return {"success": True, "data": grouped}

    except Exception as e:
        logger.error(f"Error getting settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_SETTINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.put("")
def update_settings(request: SettingsUpdateRequest, auth: dict = Depends(verify_bearer_token)):
    """Update multiple settings at once"""
    check_permission(auth, "settings.update")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        for item in request.settings:
            cursor.execute(
                "UPDATE settings SET `value` = %s WHERE `key` = %s",
                (item.value, item.key),
            )

        conn.commit()

        return {"success": True, "message": "Pengaturan berhasil disimpan"}

    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPDATE_SETTINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
