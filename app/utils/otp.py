"""
OTP Utility for Moolai Gym
Handles OTP generation, storage, and verification for multiple use cases
"""
import random
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Literal

from app.db import get_db_connection
from app.config import OTP_EXPIRY_MINUTES, OTP_LENGTH

# OTP Types
OTPType = Literal[
    "password_reset",
    "email_verification",
    "phone_verification",
    "two_factor_auth",
    "transaction_verification",
    "login_verification",
    "registration_verification"
]

ContactType = Literal["email", "phone"]


def generate_otp_code(length: int = None) -> str:
    """
    Generate random OTP code

    Args:
        length: Length of OTP code (default from config)

    Returns:
        str: Random numeric OTP code
    """
    if length is None:
        length = OTP_LENGTH
    return str(random.randint(10**(length-1), 10**length - 1))


def create_otp(
    otp_type: OTPType,
    contact_type: ContactType,
    contact_value: str,
    user_id: Optional[int] = None,
    expiry_minutes: int = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> tuple[str, bool]:
    """
    Create and store OTP in database

    Args:
        otp_type: Type of OTP (password_reset, email_verification, etc)
        contact_type: Type of contact (email or phone)
        contact_value: Email address or phone number
        user_id: Optional user ID (nullable for pre-registration)
        expiry_minutes: OTP validity in minutes (default from config)
        metadata: Optional additional context as dict

    Returns:
        tuple: (otp_code, success)
    """
    if expiry_minutes is None:
        expiry_minutes = OTP_EXPIRY_MINUTES

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Generate OTP code
        otp_code = generate_otp_code()

        # Calculate expiry time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

        # Convert metadata to JSON string
        metadata_json = json.dumps(metadata) if metadata else None

        # Invalidate all previous unused OTP codes for same contact and type
        cursor.execute(
            """
            UPDATE otp_verifications
            SET is_used = TRUE
            WHERE contact_value = %s
              AND otp_type = %s
              AND is_used = FALSE
              AND is_expired = FALSE
            """,
            (contact_value, otp_type),
        )

        # Insert new OTP
        cursor.execute(
            """
            INSERT INTO otp_verifications
                (user_id, otp_type, contact_type, contact_value,
                 otp_code, expires_at, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, otp_type, contact_type, contact_value,
             otp_code, expires_at, metadata_json),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return (otp_code, True)

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"Error creating OTP: {e}")
        return ("", False)


def verify_otp(
    contact_value: str,
    otp_code: str,
    otp_type: OTPType,
    mark_as_used: bool = True,
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Verify OTP code

    Args:
        contact_value: Email or phone number
        otp_code: OTP code to verify
        otp_type: Type of OTP to verify
        mark_as_used: Whether to mark OTP as used after verification

    Returns:
        tuple: (is_valid, otp_data)
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Find matching OTP
        cursor.execute(
            """
            SELECT otp_id, user_id, otp_code, is_used, is_expired,
                   expires_at, metadata, created_at
            FROM otp_verifications
            WHERE contact_value = %s
              AND otp_code = %s
              AND otp_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (contact_value, otp_code, otp_type),
        )

        otp_record = cursor.fetchone()

        if not otp_record:
            cursor.close()
            conn.close()
            return (False, None)

        # Check if already used
        if otp_record["is_used"]:
            cursor.close()
            conn.close()
            return (False, {"error": "OTP sudah digunakan"})

        # Check if manually expired
        if otp_record["is_expired"]:
            cursor.close()
            conn.close()
            return (False, {"error": "OTP sudah expired"})

        # Check if expired by time
        now = datetime.now(timezone.utc)
        expires_at = otp_record["expires_at"]

        # Convert to timezone-aware if needed
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            cursor.close()
            conn.close()
            return (False, {"error": "OTP sudah expired (timeout)"})

        # OTP is valid!
        if mark_as_used:
            # Mark as used
            cursor.execute(
                """
                UPDATE otp_verifications
                SET is_used = TRUE, used_at = NOW()
                WHERE otp_id = %s
                """,
                (otp_record["otp_id"],),
            )
            conn.commit()

        # Parse metadata
        metadata = json.loads(otp_record["metadata"]) if otp_record["metadata"] else None

        result_data = {
            "otp_id": otp_record["otp_id"],
            "user_id": otp_record["user_id"],
            "metadata": metadata,
            "created_at": otp_record["created_at"],
        }

        cursor.close()
        conn.close()

        return (True, result_data)

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"Error verifying OTP: {e}")
        return (False, {"error": str(e)})


def invalidate_otp(
    contact_value: str,
    otp_type: OTPType,
) -> bool:
    """
    Invalidate all unused OTP codes for a contact and type

    Args:
        contact_value: Email or phone number
        otp_type: Type of OTP to invalidate

    Returns:
        bool: Success status
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE otp_verifications
            SET is_expired = TRUE
            WHERE contact_value = %s
              AND otp_type = %s
              AND is_used = FALSE
              AND is_expired = FALSE
            """,
            (contact_value, otp_type),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"Error invalidating OTP: {e}")
        return False


def cleanup_expired_otps(older_than_hours: int = 24) -> int:
    """
    Clean up expired OTP codes older than specified hours

    Args:
        older_than_hours: Delete OTPs older than this many hours

    Returns:
        int: Number of deleted records
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)

        cursor.execute(
            """
            DELETE FROM otp_verifications
            WHERE expires_at < %s
            """,
            (cutoff_time,),
        )

        deleted_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return deleted_count

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"Error cleaning up OTPs: {e}")
        return 0
