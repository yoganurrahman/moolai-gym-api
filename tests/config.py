"""
Test Configuration for Moolai Gym API
"""
import os

# Base URL for API
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8181")

# Test user credentials
TEST_ADMIN = {
    "email": "admin@moolaigym.com",
    "password": "admin123",
    "phone": "081234567890"
}

TEST_STAFF = {
    "email": "staff@moolaigym.com",
    "password": "staff123",
    "phone": "081234567891"
}

TEST_MEMBER = {
    "email": "member@test.com",
    "password": "member123",
    "phone": "081234567892",
    "name": "Test Member",
    "gender": "male",
    "birth_date": "1990-01-15"
}

# Test data IDs (will be populated during tests)
class TestData:
    admin_token: str = None
    staff_token: str = None
    member_token: str = None
    member_id: int = None
    membership_id: int = None
    package_id: int = None
    product_id: int = None
    class_type_id: int = None
    class_schedule_id: int = None
    class_booking_id: int = None
    trainer_id: int = None
    pt_package_id: int = None
    pt_session_id: int = None
    transaction_id: int = None
    checkin_id: int = None
    qr_code: str = None

test_data = TestData()
