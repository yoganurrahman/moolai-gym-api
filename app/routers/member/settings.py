"""
Member Settings Router - Public tax/service charge settings
"""
import logging

from fastapi import APIRouter, HTTPException, status, Depends

from app.db import get_db_connection
from app.middleware import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Member - Settings"])


@router.get("/tax")
def get_tax_settings(auth: dict = Depends(verify_bearer_token)):
    """Get tax and service charge settings for checkout display"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT `key`, `value` FROM settings WHERE `key` IN "
            "('tax_enabled', 'tax_percentage', 'service_charge_enabled', 'service_charge_percentage')"
        )
        rows = cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}

        return {
            "success": True,
            "data": {
                "tax_enabled": settings.get("tax_enabled", "false") == "true",
                "tax_percentage": float(settings.get("tax_percentage", "0")),
                "service_charge_enabled": settings.get("service_charge_enabled", "false") == "true",
                "service_charge_percentage": float(settings.get("service_charge_percentage", "0")),
            },
        }

    except Exception as e:
        logger.error(f"Error getting tax settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_TAX_SETTINGS_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
