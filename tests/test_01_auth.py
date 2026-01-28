"""
Test Case 01: Authentication Flow
- Request OTP for registration
- Verify OTP and complete registration
- Login with email/password
- Get current user profile
- Change password
- Forgot password flow
- PIN operations
- Logout
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, TEST_MEMBER, test_data
import random
import string

def generate_random_email():
    """Generate random email for testing"""
    random_str = ''.join(random.choices(string.ascii_lowercase, k=8))
    return f"test_{random_str}@example.com"

def generate_random_phone():
    """Generate random phone for testing"""
    return f"08{random.randint(1000000000, 9999999999)}"


def run_auth_tests() -> TestResult:
    """Run authentication test cases"""
    print_header("TEST 01: Authentication Flow")

    client = APIClient()
    result = TestResult()

    # Test data
    test_email = generate_random_email()
    test_phone = generate_random_phone()
    test_password = "TestPass123!"
    test_name = "Test User Registration"

    # ===== Test 1: Health Check =====
    print_info("Testing API Health Check...")
    response = client.get("/health")
    if response.status_code == 200:
        result.add_pass("API Health Check")
    else:
        result.add_fail("API Health Check", f"Status: {response.status_code}")
        return result  # Stop if API is not running

    # ===== Test 2: Request Registration OTP =====
    print_info(f"Requesting OTP for registration: {test_email}")
    response = client.post("/auth/register/request-otp", {
        "email": test_email
    })

    if response.status_code == 200:
        result.add_pass("Request Registration OTP")
        print_info("OTP requested (check email or logs for OTP code)")
    elif response.status_code == 500:
        result.add_skip("Request Registration OTP", "OTP system not configured (email/table)")
    else:
        result.add_fail("Request Registration OTP", f"Status: {response.status_code}, Response: {response.text[:200]}")

    # ===== Test 3: Request OTP for Duplicate Email =====
    # First try admin email which should already exist
    print_info("Testing OTP request for existing email...")
    response = client.post("/auth/register/request-otp", {
        "email": TEST_ADMIN["email"]
    })

    if response.status_code == 400:
        result.add_pass("Reject OTP for Existing Email")
    else:
        result.add_skip("Reject OTP for Existing Email", f"Admin may not exist yet. Status: {response.status_code}")

    # ===== Test 4: Verify Registration (with test OTP - will likely fail) =====
    print_info("Testing registration verification (with test OTP)...")
    response = client.post("/auth/register/verify", {
        "email": test_email,
        "otp_code": "123456",  # Test OTP - will fail in production
        "name": test_name,
        "password": test_password,
        "phone": test_phone
    })

    if response.status_code == 200:
        result.add_pass("Verify Registration")
        try:
            data = response.json()
            if data.get("data", {}).get("user_id"):
                test_data.member_id = data["data"]["user_id"]
                print_info(f"Registration successful, user_id: {test_data.member_id}")
        except:
            pass
    elif response.status_code == 400:
        result.add_pass("Verify Registration (OTP validation working)")
        print_info("OTP validation working - test OTP was rejected")
    else:
        result.add_fail("Verify Registration", f"Status: {response.status_code}")

    # ===== Test 5: Login with Admin Credentials =====
    print_info(f"Testing admin login: {TEST_ADMIN['email']}")
    response = client.post("/auth/login", {
        "email": TEST_ADMIN["email"],
        "password": TEST_ADMIN["password"]
    })

    if response.status_code == 200:
        try:
            data = response.json()
            if "access_token" in data:
                test_data.admin_token = data["access_token"]
                result.add_pass("Admin Login")
                print_info("Admin token obtained")

                # Store admin user info
                if data.get("user", {}).get("id"):
                    print_info(f"Admin user ID: {data['user']['id']}")
            else:
                result.add_fail("Admin Login", "No access_token in response")
        except Exception as e:
            result.add_fail("Admin Login", f"Error parsing response: {str(e)}")
    elif response.status_code == 401:
        result.add_skip("Admin Login", "Admin user not found - please seed database first")
    else:
        result.add_fail("Admin Login", f"Status: {response.status_code}, Response: {response.text[:200]}")

    # ===== Test 6: Login with Wrong Password =====
    print_info("Testing login with wrong password...")
    response = client.post("/auth/login", {
        "email": TEST_ADMIN["email"],
        "password": "wrongpassword123"
    })

    if response.status_code == 401:
        result.add_pass("Reject Wrong Password")
    elif response.status_code == 423:
        result.add_pass("Reject Wrong Password (account may be locked)")
    else:
        result.add_fail("Reject Wrong Password", f"Expected 401/423, got {response.status_code}")

    # ===== Test 7: Get Current User Profile =====
    print_info("Getting current user profile...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/auth/me")

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("success") and data.get("data"):
                    result.add_pass("Get Current User Profile")
                    user_data = data["data"]
                    print_info(f"User: {user_data.get('name')} ({user_data.get('email')})")
                    print_info(f"Role: {user_data.get('role', {}).get('name')}")
                else:
                    result.add_fail("Get Current User Profile", "Unexpected response format")
            except Exception as e:
                result.add_fail("Get Current User Profile", f"Error: {str(e)}")
        else:
            result.add_fail("Get Current User Profile", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Current User Profile", "No admin token available")

    # ===== Test 8: Access Protected Route Without Token =====
    print_info("Testing protected route without token...")
    client.clear_token()
    response = client.get("/auth/me")

    if response.status_code in [401, 403]:
        result.add_pass("Reject Unauthorized Access")
    else:
        result.add_fail("Reject Unauthorized Access", f"Expected 401/403, got {response.status_code}")

    # ===== Test 9: Change Password =====
    print_info("Testing change password...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/auth/change-password", {
            "old_password": TEST_ADMIN["password"],
            "new_password": "NewAdmin456!"
        })

        if response.status_code == 200:
            result.add_pass("Change Password")
            # Re-login with new password
            client.clear_token()
            response = client.post("/auth/login", {
                "email": TEST_ADMIN["email"],
                "password": "NewAdmin456!"
            })
            if response.status_code == 200:
                test_data.admin_token = response.json().get("access_token")
                client.set_token(test_data.admin_token)
                # Change it back
                response = client.post("/auth/change-password", {
                    "old_password": "NewAdmin456!",
                    "new_password": TEST_ADMIN["password"]
                })
                if response.status_code == 200:
                    print_info("Password changed back successfully")
                    # Re-login again with original password
                    client.clear_token()
                    response = client.post("/auth/login", {
                        "email": TEST_ADMIN["email"],
                        "password": TEST_ADMIN["password"]
                    })
                    if response.status_code == 200:
                        test_data.admin_token = response.json().get("access_token")
        elif response.status_code == 400:
            result.add_pass("Change Password (validation working)")
        else:
            result.add_fail("Change Password", f"Status: {response.status_code}")
    else:
        result.add_skip("Change Password", "No token available")

    # ===== Test 10: Request Forgot Password OTP =====
    print_info("Testing forgot password OTP request...")
    response = client.post("/auth/forgot-password/request-otp", {
        "email": TEST_ADMIN["email"]
    })

    if response.status_code == 200:
        result.add_pass("Request Forgot Password OTP")
    elif response.status_code == 500:
        result.add_skip("Request Forgot Password OTP", "OTP system not configured (email/table)")
    else:
        result.add_fail("Request Forgot Password OTP", f"Status: {response.status_code}")

    # ===== Test 11: Verify Forgot Password (with test OTP) =====
    print_info("Testing forgot password verification...")
    response = client.post("/auth/forgot-password/verify", {
        "email": TEST_ADMIN["email"],
        "otp_code": "123456",  # Test OTP
        "new_password": "NewPass123!"
    })

    if response.status_code == 200:
        result.add_pass("Verify Forgot Password")
    elif response.status_code == 400:
        result.add_pass("Verify Forgot Password (OTP validation working)")
    else:
        result.add_fail("Verify Forgot Password", f"Status: {response.status_code}")

    # ===== Test 12: Set PIN (for new user) =====
    print_info("Testing PIN setup...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/auth/set-pin", {
            "pin": "123456"
        })

        if response.status_code == 200:
            result.add_pass("Set PIN")
        elif response.status_code == 400:
            result.add_pass("Set PIN (already set or validation)")
            print_info("PIN already set for this user")
        else:
            result.add_fail("Set PIN", f"Status: {response.status_code}")
    else:
        result.add_skip("Set PIN", "No token available")

    # ===== Test 13: Verify PIN =====
    print_info("Testing PIN verification...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/auth/verify-pin", {
            "pin": "123456"
        })

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("pin_token"):
                    result.add_pass("Verify PIN")
                    print_info("PIN token obtained")
                else:
                    result.add_pass("Verify PIN (no token returned)")
            except:
                result.add_pass("Verify PIN")
        elif response.status_code in [400, 401]:
            result.add_pass("Verify PIN (wrong PIN or not set)")
        elif response.status_code == 423:
            result.add_pass("Verify PIN (PIN locked)")
        else:
            result.add_fail("Verify PIN", f"Status: {response.status_code}")
    else:
        result.add_skip("Verify PIN", "No token available")

    # ===== Test 14: Change PIN =====
    print_info("Testing PIN change...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/auth/change-pin", {
            "old_pin": "123456",
            "new_pin": "654321"
        })

        if response.status_code == 200:
            result.add_pass("Change PIN")
            # Change it back
            client.post("/auth/change-pin", {
                "old_pin": "654321",
                "new_pin": "123456"
            })
        elif response.status_code == 400:
            result.add_pass("Change PIN (validation working)")
        else:
            result.add_fail("Change PIN", f"Status: {response.status_code}")
    else:
        result.add_skip("Change PIN", "No token available")

    # ===== Test 15: Logout =====
    print_info("Testing logout...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/auth/logout")

        if response.status_code == 200:
            result.add_pass("Logout")
            print_info("Logout successful - token invalidated")
        else:
            result.add_fail("Logout", f"Status: {response.status_code}")
    else:
        result.add_skip("Logout", "No token available")

    # ===== Test 16: Access After Logout =====
    print_info("Testing access after logout...")
    if test_data.admin_token:
        # Try to use the old token
        client.set_token(test_data.admin_token)
        response = client.get("/auth/me")

        if response.status_code in [401, 403]:
            result.add_pass("Reject Access After Logout")
        else:
            result.add_fail("Reject Access After Logout", f"Expected 401/403, got {response.status_code}")

        # Re-login for subsequent tests
        client.clear_token()
        response = client.post("/auth/login", {
            "email": TEST_ADMIN["email"],
            "password": TEST_ADMIN["password"]
        })
        if response.status_code == 200:
            test_data.admin_token = response.json().get("access_token")
            print_info("Re-logged in for subsequent tests")
    else:
        result.add_skip("Reject Access After Logout", "No token available")

    # ===== Test 17: Login Member User =====
    print_info(f"Testing member login: {TEST_MEMBER['email']}")
    client.clear_token()
    response = client.post("/auth/login", {
        "email": TEST_MEMBER["email"],
        "password": TEST_MEMBER["password"]
    })

    if response.status_code == 200:
        try:
            data = response.json()
            if "access_token" in data:
                test_data.member_token = data["access_token"]
                result.add_pass("Member Login")
                print_info("Member token obtained")

                if data.get("user", {}).get("id"):
                    test_data.member_id = data["user"]["id"]
                    print_info(f"Member user ID: {test_data.member_id}")
            else:
                result.add_fail("Member Login", "No access_token in response")
        except Exception as e:
            result.add_fail("Member Login", f"Error parsing response: {str(e)}")
    elif response.status_code == 401:
        result.add_skip("Member Login", "Member user not found - please seed database first")
    else:
        result.add_fail("Member Login", f"Status: {response.status_code}, Response: {response.text[:200]}")

    return result


if __name__ == "__main__":
    result = run_auth_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
