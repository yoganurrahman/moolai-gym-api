"""
Audit Logging Utility
Centralized audit logging for all master data operations
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def log_audit(
    conn,
    table_name: str,
    record_id: int,
    action: str,  # INSERT, UPDATE, DELETE
    user_id: int,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
):
    """
    Log audit trail to audit_logs table

    Args:
        conn: Database connection
        table_name: Name of the table being modified
        record_id: ID of the record being modified
        action: Action performed (INSERT, UPDATE, DELETE)
        user_id: ID of the user performing the action
        old_data: Previous values (for UPDATE/DELETE)
        new_data: New values (for INSERT/UPDATE)
    """
    cursor = conn.cursor()

    try:
        # Sanitize data before logging
        old_data_sanitized = sanitize_for_audit(old_data) if old_data else None
        new_data_sanitized = sanitize_for_audit(new_data) if new_data else None

        # Convert dictionaries to JSON strings
        old_data_json = json.dumps(old_data_sanitized, default=str) if old_data_sanitized else None
        new_data_json = json.dumps(new_data_sanitized, default=str) if new_data_sanitized else None

        # Insert audit log
        cursor.execute(
            """
            INSERT INTO audit_logs (
                table_name, record_id, action, user_id,
                old_data, new_data, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                table_name,
                record_id,
                action,
                user_id,
                old_data_json,
                new_data_json,
                datetime.now(),
            ),
        )

        # Don't commit here - let the caller handle transaction
        cursor.close()

    except Exception as e:
        cursor.close()
        # Don't raise - audit logging should not break the main operation
        logger.warning(f"Audit logging failed: {str(e)}")


def get_record_for_audit(conn, table_name: str, record_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch current record values for audit logging (before UPDATE/DELETE)

    Args:
        conn: Database connection
        table_name: Name of the table
        record_id: ID of the record

    Returns:
        Dictionary of current values or None if not found
    """
    cursor = conn.cursor(dictionary=True)

    try:
        # Whitelist of allowed tables to prevent SQL injection
        allowed_tables = [
            'users', 'roles', 'permissions', 'role_permissions',
            'members', 'memberships', 'trainers', 'gym_classes'
        ]

        if table_name not in allowed_tables:
            logger.warning(f"Table {table_name} not in whitelist for audit")
            cursor.close()
            return None

        cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (record_id,))
        record = cursor.fetchone()
        cursor.close()
        return record
    except Exception as e:
        cursor.close()
        logger.warning(f"Failed to fetch record for audit: {str(e)}")
        return None


def sanitize_for_audit(data: Dict[str, Any], exclude_fields: list = None) -> Dict[str, Any]:
    """
    Sanitize data for audit logging (remove sensitive fields)

    Args:
        data: Data dictionary
        exclude_fields: List of field names to exclude (e.g., passwords)

    Returns:
        Sanitized dictionary
    """
    if not data:
        return {}

    # Default sensitive fields to exclude
    default_excludes = ['password', 'pin', 'token', 'secret', 'credential']
    exclude_fields = exclude_fields or []
    all_excludes = default_excludes + exclude_fields

    # Create copy and remove sensitive fields
    sanitized = dict(data)
    for field in all_excludes:
        if field in sanitized:
            sanitized[field] = "***REDACTED***"

    return sanitized
