import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field

from app.db import get_db_connection
from app.middleware import create_access_token, create_pin_token, verify_bearer_token, verify_pin_token
from app.utils.helpers import hash_password, verify_password
from app.utils.otp import create_otp, verify_otp
from app.utils.email import send_registration_otp_email, send_welcome_email, send_otp_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Constants
MAX_LOGIN_ATTEMPTS = 5
MAX_PIN_ATTEMPTS = 3
LOCKOUT_DURATION_MINUTES = 30
PIN_LOCKOUT_DURATION_MINUTES = 15


# ============== Request Models ==============

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=100)


class SetPinRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyPinRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ChangePinRequest(BaseModel):
    old_pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class RequestOTPRequest(BaseModel):
    email: EmailStr


class VerifyRegisterRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


# ============== Endpoints ==============

@router.post("/register/request-otp")
def request_registration_otp(request: RequestOTPRequest):
    """
    Step 1: Request OTP for registration.
    OTP will be sent to the provided email address.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "EMAIL_EXISTS",
                    "message": "Email sudah terdaftar",
                },
            )

        # Create OTP
        otp_code, success = create_otp(
            otp_type="registration_verification",
            contact_type="email",
            contact_value=request.email,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "OTP_CREATION_FAILED",
                    "message": "Gagal membuat kode OTP",
                },
            )

        # Send OTP email
        email_sent = send_registration_otp_email(request.email, otp_code)

        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "EMAIL_SEND_FAILED",
                    "message": "Gagal mengirim email OTP",
                },
            )

        return {
            "success": True,
            "message": "Kode OTP telah dikirim ke email Anda. Berlaku selama 10 menit.",
            "data": {
                "email": request.email,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting registration OTP: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REQUEST_OTP_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/register/verify")
def verify_registration(request: VerifyRegisterRequest):
    """
    Step 2: Verify OTP and complete registration.
    Creates user account after successful OTP verification.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if email already exists (in case someone registered in between)
        cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "EMAIL_EXISTS",
                    "message": "Email sudah terdaftar",
                },
            )

        # Verify OTP
        is_valid, otp_data = verify_otp(
            contact_value=request.email,
            otp_code=request.otp_code,
            otp_type="registration_verification",
        )

        if not is_valid:
            error_message = "Kode OTP tidak valid"
            if otp_data and "error" in otp_data:
                error_message = otp_data["error"]

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_OTP",
                    "message": error_message,
                },
            )

        # Hash password
        hashed_password = hash_password(request.password)

        # Get default role (member)
        cursor.execute("SELECT id FROM roles WHERE name = 'member' LIMIT 1")
        role = cursor.fetchone()
        role_id = role["id"] if role else 3  # Default to 3 if not found

        # Insert user
        cursor.execute(
            """
            INSERT INTO users (name, email, password, phone, role_id, is_active, token_version, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.name,
                request.email,
                hashed_password,
                request.phone,
                role_id,
                1,  # is_active
                1,  # token_version
                datetime.now(),
            ),
        )
        conn.commit()

        user_id = cursor.lastrowid

        # Send welcome email (non-blocking, don't fail if email fails)
        try:
            send_welcome_email(request.email, request.name)
        except Exception as email_error:
            logger.warning(f"Failed to send welcome email: {email_error}")

        return {
            "success": True,
            "message": "Registrasi berhasil. Silakan login dan buat PIN Anda.",
            "data": {
                "user_id": user_id,
                "email": request.email,
                "name": request.name,
                "requires_pin": True,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during registration verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REGISTRATION_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/login")
def login(request: LoginRequest):
    """
    Login with email and password.
    Returns JWT access token on success.
    If user has no PIN, returns requires_pin=true to prompt PIN creation.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get user by email (including PIN status and branch)
        cursor.execute(
            """
            SELECT u.id, u.name, u.email, u.password, u.phone, u.is_active,
                   u.role_id, u.token_version, u.failed_login_attempts, u.locked_until,
                   u.has_pin, u.default_branch_id,
                   r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.email = %s
            """,
            (request.email,),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "Email atau password salah",
                },
            )

        # Check if account is locked
        if user["locked_until"] and datetime.now() < user["locked_until"]:
            remaining_minutes = int(
                (user["locked_until"] - datetime.now()).total_seconds() / 60
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error_code": "ACCOUNT_LOCKED",
                    "message": f"Akun terkunci. Coba lagi dalam {remaining_minutes} menit.",
                },
            )

        # Check if account is active
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": "Akun tidak aktif. Hubungi administrator.",
                },
            )

        # Verify password
        if not verify_password(request.password, user["password"]):
            # Increment failed attempts
            failed_attempts = (user["failed_login_attempts"] or 0) + 1

            if failed_attempts >= MAX_LOGIN_ATTEMPTS:
                # Lock account
                locked_until = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                cursor.execute(
                    """
                    UPDATE users
                    SET failed_login_attempts = %s, locked_until = %s
                    WHERE id = %s
                    """,
                    (failed_attempts, locked_until, user["id"]),
                )
                conn.commit()

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail={
                        "error_code": "ACCOUNT_LOCKED",
                        "message": f"Terlalu banyak percobaan login. Akun terkunci selama {LOCKOUT_DURATION_MINUTES} menit.",
                    },
                )
            else:
                cursor.execute(
                    "UPDATE users SET failed_login_attempts = %s WHERE id = %s",
                    (failed_attempts, user["id"]),
                )
                conn.commit()

                remaining_attempts = MAX_LOGIN_ATTEMPTS - failed_attempts
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "INVALID_CREDENTIALS",
                        "message": f"Email atau password salah. Sisa percobaan: {remaining_attempts}",
                    },
                )

        # Reset failed attempts and update token version
        new_token_version = (user["token_version"] or 0) + 1
        cursor.execute(
            """
            UPDATE users
            SET failed_login_attempts = 0, locked_until = NULL, token_version = %s
            WHERE id = %s
            """,
            (new_token_version, user["id"]),
        )
        conn.commit()

        # Create access token (permissions NOT stored in token - fetched real-time)
        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "role_id": user["role_id"],
            "role_name": user["role_name"] or "member",
            "token_version": new_token_version,
        }
        access_token = create_access_token(token_data)

        # Check if user has PIN
        has_pin = bool(user.get("has_pin"))
        requires_pin = not has_pin

        # Get accessible branches based on role
        role_name = (user["role_name"] or "member").lower()
        if role_name in ("superadmin", "admin", "member"):
            # Superadmin/Admin: all active branches; Member: can visit all branches
            cursor.execute(
                "SELECT id, code, name, city FROM branches WHERE is_active = 1 ORDER BY sort_order ASC"
            )
            accessible_branches = cursor.fetchall()
        elif role_name == "trainer":
            # Trainer: only assigned branches
            cursor.execute(
                """
                SELECT b.id, b.code, b.name, b.city
                FROM trainer_branches tb
                JOIN branches b ON tb.branch_id = b.id
                WHERE tb.trainer_id = (SELECT id FROM trainers WHERE user_id = %s LIMIT 1)
                  AND b.is_active = 1
                ORDER BY tb.is_primary DESC, b.sort_order ASC
                """,
                (user["id"],),
            )
            accessible_branches = cursor.fetchall()
        elif role_name == "staff":
            # Staff: default branch only
            if user["default_branch_id"]:
                cursor.execute(
                    "SELECT id, code, name, city FROM branches WHERE id = %s AND is_active = 1",
                    (user["default_branch_id"],),
                )
                accessible_branches = cursor.fetchall()
            else:
                accessible_branches = []
        else:
            accessible_branches = []

        # Get default branch info
        default_branch = None
        if user.get("default_branch_id"):
            cursor.execute(
                "SELECT id, code, name FROM branches WHERE id = %s",
                (user["default_branch_id"],),
            )
            default_branch = cursor.fetchone()

        response = {
            "success": True,
            "message": "Login berhasil" if has_pin else "Login berhasil. Silakan buat PIN untuk melanjutkan.",
            "access_token": access_token,
            "token_type": "bearer",
            "requires_pin": requires_pin,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "phone": user["phone"],
                "role": user["role_name"] or "member",
                "has_pin": has_pin,
                "default_branch": default_branch,
            },
            "branches": accessible_branches,
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LOGIN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/logout")
def logout(auth: dict = Depends(verify_bearer_token)):
    """
    Logout user by incrementing token_version (invalidates all existing tokens).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Increment token version to invalidate all tokens
        cursor.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = %s",
            (auth["user_id"],),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Logout berhasil",
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Error during logout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LOGOUT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest, auth: dict = Depends(verify_bearer_token)
):
    """
    Change password for authenticated user.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get current password
        cursor.execute(
            "SELECT password FROM users WHERE id = %s", (auth["user_id"],)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        # Verify old password
        if not verify_password(request.old_password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_OLD_PASSWORD",
                    "message": "Password lama salah",
                },
            )

        # Hash new password and update
        hashed_password = hash_password(request.new_password)
        cursor.execute(
            """
            UPDATE users
            SET password = %s, token_version = token_version + 1, updated_at = %s
            WHERE id = %s
            """,
            (hashed_password, datetime.now(), auth["user_id"]),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Password berhasil diubah. Silakan login kembali.",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error changing password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHANGE_PASSWORD_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== Forgot Password Endpoints ==============

@router.post("/forgot-password/request-otp")
def request_forgot_password_otp(request: ForgotPasswordRequest):
    """
    Step 1: Request OTP for password reset.
    OTP will be sent to the registered email address.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if email exists
        cursor.execute(
            "SELECT id, name, is_active FROM users WHERE email = %s",
            (request.email,),
        )
        user = cursor.fetchone()

        if not user:
            # Don't reveal if email exists or not for security
            return {
                "success": True,
                "message": "Jika email terdaftar, kode OTP akan dikirim ke email Anda.",
                "data": {
                    "email": request.email,
                },
            }

        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": "Akun tidak aktif. Hubungi administrator.",
                },
            )

        # Create OTP
        otp_code, success = create_otp(
            otp_type="password_reset",
            contact_type="email",
            contact_value=request.email,
            user_id=user["id"],
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "OTP_CREATION_FAILED",
                    "message": "Gagal membuat kode OTP",
                },
            )

        # Send OTP email
        email_sent = send_otp_email(request.email, otp_code, user["name"])

        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "EMAIL_SEND_FAILED",
                    "message": "Gagal mengirim email OTP",
                },
            )

        return {
            "success": True,
            "message": "Kode OTP telah dikirim ke email Anda. Berlaku selama 10 menit.",
            "data": {
                "email": request.email,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting forgot password OTP: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "REQUEST_OTP_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/forgot-password/verify")
def verify_forgot_password(request: ResetPasswordRequest):
    """
    Step 2: Verify OTP and reset password.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if email exists
        cursor.execute(
            "SELECT id, is_active FROM users WHERE email = %s",
            (request.email,),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "USER_NOT_FOUND",
                    "message": "Email tidak ditemukan",
                },
            )

        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": "Akun tidak aktif. Hubungi administrator.",
                },
            )

        # Verify OTP
        is_valid, otp_data = verify_otp(
            contact_value=request.email,
            otp_code=request.otp_code,
            otp_type="password_reset",
        )

        if not is_valid:
            error_message = "Kode OTP tidak valid"
            if otp_data and "error" in otp_data:
                error_message = otp_data["error"]

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_OTP",
                    "message": error_message,
                },
            )

        # Hash new password and update
        hashed_password = hash_password(request.new_password)
        cursor.execute(
            """
            UPDATE users
            SET password = %s, token_version = token_version + 1, updated_at = %s
            WHERE id = %s
            """,
            (hashed_password, datetime.now(), user["id"]),
        )
        conn.commit()

        return {
            "success": True,
            "message": "Password berhasil direset. Silakan login dengan password baru.",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error resetting password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "RESET_PASSWORD_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/me")
def get_current_user(auth: dict = Depends(verify_bearer_token)):
    """
    Get current authenticated user profile.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT u.id, u.name, u.email, u.phone, u.is_active, u.default_branch_id,
                   u.created_at,
                   r.id as role_id, r.name as role_name,
                   b.code as default_branch_code, b.name as default_branch_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
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

        # Get permissions
        cursor.execute(
            """
            SELECT p.name, p.description
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE rp.role_id = %s
            """,
            (user["role_id"],),
        )
        permissions = cursor.fetchall()

        # Format datetime
        if user["created_at"]:
            user["created_at"] = user["created_at"].isoformat()

        # Build default branch info
        default_branch = None
        if user.get("default_branch_id"):
            default_branch = {
                "id": user["default_branch_id"],
                "code": user["default_branch_code"],
                "name": user["default_branch_name"],
            }

        return {
            "success": True,
            "data": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "phone": user["phone"],
                "is_active": bool(user["is_active"]),
                "role": {
                    "id": user["role_id"],
                    "name": user["role_name"],
                },
                "permissions": permissions,
                "default_branch": default_branch,
                "created_at": user["created_at"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_PROFILE_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


# ============== PIN Endpoints ==============

@router.post("/set-pin")
def set_pin(request: SetPinRequest, auth: dict = Depends(verify_bearer_token)):
    """
    Set PIN for the first time (user must not have PIN yet).
    PIN is used for sensitive operations like transactions.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if user already has PIN
        cursor.execute(
            "SELECT has_pin FROM users WHERE id = %s",
            (auth["user_id"],),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        if user["has_pin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PIN_ALREADY_SET",
                    "message": "PIN sudah diatur. Gunakan endpoint change-pin untuk mengubah PIN.",
                },
            )

        # Hash and save PIN
        hashed_pin = hash_password(request.pin)
        cursor.execute(
            """
            UPDATE users
            SET pin = %s, has_pin = 1, pin_version = 1, updated_at = %s
            WHERE id = %s
            """,
            (hashed_pin, datetime.now(), auth["user_id"]),
        )
        conn.commit()

        return {
            "success": True,
            "message": "PIN berhasil diatur",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error setting PIN: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SET_PIN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/verify-pin")
def verify_pin(request: VerifyPinRequest, auth: dict = Depends(verify_bearer_token)):
    """
    Verify PIN and return a PIN token for sensitive operations.
    PIN token is valid for 1 hour.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get user PIN data
        cursor.execute(
            """
            SELECT pin, has_pin, pin_version, failed_pin_attempts, pin_locked_until
            FROM users WHERE id = %s
            """,
            (auth["user_id"],),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        if not user["has_pin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PIN_NOT_SET",
                    "message": "PIN belum diatur. Silakan atur PIN terlebih dahulu.",
                },
            )

        # Check if PIN is locked
        if user["pin_locked_until"] and datetime.now() < user["pin_locked_until"]:
            remaining_minutes = int(
                (user["pin_locked_until"] - datetime.now()).total_seconds() / 60
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error_code": "PIN_LOCKED",
                    "message": f"PIN terkunci. Coba lagi dalam {remaining_minutes} menit.",
                },
            )

        # Verify PIN
        if not verify_password(request.pin, user["pin"]):
            # Increment failed attempts
            failed_attempts = (user["failed_pin_attempts"] or 0) + 1

            if failed_attempts >= MAX_PIN_ATTEMPTS:
                # Lock PIN
                pin_locked_until = datetime.now() + timedelta(minutes=PIN_LOCKOUT_DURATION_MINUTES)
                cursor.execute(
                    """
                    UPDATE users
                    SET failed_pin_attempts = %s, pin_locked_until = %s
                    WHERE id = %s
                    """,
                    (failed_attempts, pin_locked_until, auth["user_id"]),
                )
                conn.commit()

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail={
                        "error_code": "PIN_LOCKED",
                        "message": f"Terlalu banyak percobaan PIN salah. PIN terkunci selama {PIN_LOCKOUT_DURATION_MINUTES} menit.",
                    },
                )
            else:
                cursor.execute(
                    "UPDATE users SET failed_pin_attempts = %s WHERE id = %s",
                    (failed_attempts, auth["user_id"]),
                )
                conn.commit()

                remaining_attempts = MAX_PIN_ATTEMPTS - failed_attempts
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "INVALID_PIN",
                        "message": f"PIN salah. Sisa percobaan: {remaining_attempts}",
                    },
                )

        # Reset failed attempts
        cursor.execute(
            """
            UPDATE users
            SET failed_pin_attempts = 0, pin_locked_until = NULL
            WHERE id = %s
            """,
            (auth["user_id"],),
        )
        conn.commit()

        # Create PIN token
        pin_token = create_pin_token(auth["user_id"], user["pin_version"])

        return {
            "success": True,
            "message": "PIN terverifikasi",
            "pin_token": pin_token,
            "expires_in": 3600,  # 1 hour in seconds
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error verifying PIN: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "VERIFY_PIN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/change-pin")
def change_pin(request: ChangePinRequest, auth: dict = Depends(verify_bearer_token)):
    """
    Change existing PIN.
    Requires old PIN for verification.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get user PIN data
        cursor.execute(
            "SELECT pin, has_pin, pin_version FROM users WHERE id = %s",
            (auth["user_id"],),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "USER_NOT_FOUND", "message": "User tidak ditemukan"},
            )

        if not user["has_pin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PIN_NOT_SET",
                    "message": "PIN belum diatur. Gunakan endpoint set-pin untuk mengatur PIN.",
                },
            )

        # Verify old PIN
        if not verify_password(request.old_pin, user["pin"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_OLD_PIN",
                    "message": "PIN lama salah",
                },
            )

        # Check if new PIN is same as old PIN
        if request.old_pin == request.new_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "SAME_PIN",
                    "message": "PIN baru tidak boleh sama dengan PIN lama",
                },
            )

        # Hash and save new PIN, increment pin_version to invalidate existing PIN tokens
        hashed_pin = hash_password(request.new_pin)
        new_pin_version = (user["pin_version"] or 0) + 1
        cursor.execute(
            """
            UPDATE users
            SET pin = %s, pin_version = %s, updated_at = %s
            WHERE id = %s
            """,
            (hashed_pin, new_pin_version, datetime.now(), auth["user_id"]),
        )
        conn.commit()

        return {
            "success": True,
            "message": "PIN berhasil diubah",
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error changing PIN: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHANGE_PIN_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
