import random
import string
import bcrypt


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    Handles bcrypt's 72-byte limit by truncating if necessary.
    """
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    """
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def generate_otp(length: int = 4) -> str:
    """
    Generate a random OTP (digits only).

    Args:
        length: number of digits (default 4)

    Returns:
        OTP string
    """
    return "".join(random.choices(string.digits, k=length))


def generate_random_string(length: int = 32) -> str:
    """
    Generate a random alphanumeric string.

    Args:
        length: length of string (default 32)

    Returns:
        Random string
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def format_phone_number(phone: str) -> str:
    """
    Format phone number to international format (628xxx).
    Converts 08xxx to 628xxx.

    Args:
        phone: phone number string

    Returns:
        Formatted phone number
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    if phone.startswith("08"):
        return "62" + phone[1:]
    elif phone.startswith("+62"):
        return phone[1:]
    elif phone.startswith("62"):
        return phone
    else:
        return phone
