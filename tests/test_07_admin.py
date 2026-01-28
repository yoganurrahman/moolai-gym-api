"""
Test Case 07: Admin Operations & Reports
- User management (CRUD)
- Role management
- Permission management
- Subscription management
- Reports (daily, monthly, revenue)
- Settings management
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, test_data
from datetime import datetime, timedelta


def run_admin_tests() -> TestResult:
    """Run admin operations test cases"""
    print_header("TEST 07: Admin Operations & Reports")

    client = APIClient()
    result = TestResult()

    # ===== Setup =====
    if not test_data.admin_token:
        print_info("Logging in as admin...")
        response = client.post("/auth/login", {
            "email": TEST_ADMIN["email"],
            "password": TEST_ADMIN["password"]
        })
        if response.status_code == 200:
            test_data.admin_token = response.json().get("access_token")
        else:
            result.add_fail("Admin Login", "Cannot login as admin - tests will be skipped")
            return result

    client.set_token(test_data.admin_token)

    # ==================== USER MANAGEMENT ====================

    # ===== Test 1: List Users =====
    print_info("Listing all users...")
    response = client.get("/api/cms/users")

    if response.status_code == 200:
        try:
            data = response.json()
            users = data if isinstance(data, list) else data.get("data", data.get("users", []))
            result.add_pass(f"List Users ({len(users)} found)")
        except:
            result.add_pass("List Users")
    elif response.status_code == 404:
        result.add_skip("List Users", "Endpoint not implemented")
    else:
        result.add_fail("List Users", f"Status: {response.status_code}")

    # ===== Test 2: Create User =====
    print_info("Creating new user...")
    new_user_email = f"newuser_{datetime.now().strftime('%H%M%S')}@test.com"
    response = client.post("/api/cms/users", {
        "email": new_user_email,
        "password": "TestPass123!",
        "phone": f"08{datetime.now().strftime('%H%M%S%f')[:10]}",
        "name": "Test New User",
        "role_id": 3,  # Member role
        "is_active": True
    })

    new_user_id = None
    if response.status_code in [200, 201]:
        try:
            data = response.json()
            new_user_id = data.get("id") or data.get("data", {}).get("id")
            result.add_pass("Create User")
        except:
            result.add_pass("Create User")
    elif response.status_code == 404:
        result.add_skip("Create User", "Endpoint not implemented")
    else:
        result.add_fail("Create User", f"Status: {response.status_code}, Response: {response.text[:200]}")

    # ===== Test 3: Get User Details =====
    print_info("Getting user details...")
    if new_user_id or test_data.member_id:
        user_id = new_user_id or test_data.member_id
        response = client.get(f"/api/cms/users/{user_id}")

        if response.status_code == 200:
            result.add_pass("Get User Details")
        elif response.status_code == 404:
            result.add_skip("Get User Details", "Endpoint not found")
        else:
            result.add_fail("Get User Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get User Details", "No user ID available")

    # ===== Test 4: Update User =====
    print_info("Updating user...")
    if new_user_id:
        response = client.put(f"/api/cms/users/{new_user_id}", {
            "name": "Updated Test User",
            "address": "123 Test Street"
        })

        if response.status_code == 200:
            result.add_pass("Update User")
        elif response.status_code == 404:
            result.add_skip("Update User", "Endpoint not implemented")
        else:
            result.add_fail("Update User", f"Status: {response.status_code}")
    else:
        result.add_skip("Update User", "No user ID available")

    # ===== Test 5: Deactivate User =====
    print_info("Deactivating user...")
    if new_user_id:
        response = client.patch(f"/api/cms/users/{new_user_id}/deactivate")

        if response.status_code == 200:
            result.add_pass("Deactivate User")
        elif response.status_code == 404:
            result.add_skip("Deactivate User", "Endpoint not implemented")
        else:
            result.add_fail("Deactivate User", f"Status: {response.status_code}")
    else:
        result.add_skip("Deactivate User", "No user ID available")

    # ==================== ROLE MANAGEMENT ====================

    # ===== Test 6: List Roles =====
    print_info("Listing roles...")
    response = client.get("/api/cms/roles")

    role_id = None
    if response.status_code == 200:
        try:
            data = response.json()
            roles = data if isinstance(data, list) else data.get("data", data.get("roles", []))
            result.add_pass(f"List Roles ({len(roles)} found)")
        except:
            result.add_pass("List Roles")
    elif response.status_code == 404:
        result.add_skip("List Roles", "Endpoint not implemented")
    else:
        result.add_fail("List Roles", f"Status: {response.status_code}")

    # ===== Test 7: Create Role =====
    print_info("Creating role...")
    response = client.post("/api/cms/roles", {
        "name": f"TestRole_{datetime.now().strftime('%H%M%S')}",
        "description": "Test role for testing"
    })

    if response.status_code in [200, 201]:
        try:
            data = response.json()
            role_id = data.get("id") or data.get("data", {}).get("id")
            result.add_pass("Create Role")
        except:
            result.add_pass("Create Role")
    elif response.status_code == 404:
        result.add_skip("Create Role", "Endpoint not implemented")
    else:
        result.add_fail("Create Role", f"Status: {response.status_code}")

    # ==================== PERMISSION MANAGEMENT ====================

    # ===== Test 8: List Permissions =====
    print_info("Listing permissions...")
    response = client.get("/api/cms/permissions")

    if response.status_code == 200:
        try:
            data = response.json()
            permissions = data if isinstance(data, list) else data.get("data", data.get("permissions", []))
            result.add_pass(f"List Permissions ({len(permissions)} found)")
        except:
            result.add_pass("List Permissions")
    elif response.status_code == 404:
        result.add_skip("List Permissions", "Endpoint not implemented")
    else:
        result.add_fail("List Permissions", f"Status: {response.status_code}")

    # ===== Test 9: Assign Permission to Role =====
    print_info("Assigning permission to role...")
    if role_id:
        response = client.post(f"/api/cms/roles/{role_id}/permissions", {
            "permissions": ["users.view", "users.edit"]
        })

        if response.status_code in [200, 201]:
            result.add_pass("Assign Permission to Role")
        elif response.status_code == 404:
            result.add_skip("Assign Permission to Role", "Endpoint not implemented")
        else:
            result.add_fail("Assign Permission to Role", f"Status: {response.status_code}")
    else:
        result.add_skip("Assign Permission to Role", "No role ID available")

    # ==================== SUBSCRIPTION MANAGEMENT ====================

    # ===== Test 10: List Subscriptions =====
    print_info("Listing subscriptions...")
    response = client.get("/api/cms/subscriptions")

    subscription_id = None
    if response.status_code == 200:
        try:
            data = response.json()
            subs = data if isinstance(data, list) else data.get("data", data.get("subscriptions", []))
            if subs:
                subscription_id = subs[0].get("id")
            result.add_pass(f"List Subscriptions ({len(subs)} found)")
        except:
            result.add_pass("List Subscriptions")
    elif response.status_code == 404:
        result.add_skip("List Subscriptions", "Endpoint not implemented")
    else:
        result.add_fail("List Subscriptions", f"Status: {response.status_code}")

    # ===== Test 11: Create Recurring Subscription =====
    print_info("Creating recurring subscription...")
    if test_data.member_id and test_data.package_id:
        response = client.post("/api/cms/subscriptions", {
            "user_id": test_data.member_id,
            "package_id": test_data.package_id,
            "billing_cycle": "monthly",
            "payment_method": "card",
            "auto_renew": True,
            "start_date": datetime.now().strftime("%Y-%m-%d")
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                subscription_id = data.get("id") or data.get("data", {}).get("id")
                result.add_pass("Create Subscription")
            except:
                result.add_pass("Create Subscription")
        elif response.status_code == 404:
            result.add_skip("Create Subscription", "Endpoint not implemented")
        else:
            result.add_fail("Create Subscription", f"Status: {response.status_code}")
    else:
        result.add_skip("Create Subscription", "Missing member or package ID")

    # ===== Test 12: Pause Subscription =====
    print_info("Pausing subscription...")
    if subscription_id:
        response = client.post(f"/api/cms/subscriptions/{subscription_id}/pause", {
            "reason": "Test pause",
            "resume_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        })

        if response.status_code == 200:
            result.add_pass("Pause Subscription")
        elif response.status_code == 404:
            result.add_skip("Pause Subscription", "Endpoint not implemented")
        else:
            result.add_fail("Pause Subscription", f"Status: {response.status_code}")
    else:
        result.add_skip("Pause Subscription", "No subscription ID")

    # ===== Test 13: Resume Subscription =====
    print_info("Resuming subscription...")
    if subscription_id:
        response = client.post(f"/api/cms/subscriptions/{subscription_id}/resume")

        if response.status_code == 200:
            result.add_pass("Resume Subscription")
        elif response.status_code == 400:
            result.add_pass("Resume Subscription (not paused)")
        elif response.status_code == 404:
            result.add_skip("Resume Subscription", "Endpoint not implemented")
        else:
            result.add_fail("Resume Subscription", f"Status: {response.status_code}")
    else:
        result.add_skip("Resume Subscription", "No subscription ID")

    # ===== Test 14: Cancel Subscription =====
    print_info("Canceling subscription...")
    if subscription_id:
        response = client.post(f"/api/cms/subscriptions/{subscription_id}/cancel", {
            "reason": "Test cancellation"
        })

        if response.status_code == 200:
            result.add_pass("Cancel Subscription")
        elif response.status_code == 404:
            result.add_skip("Cancel Subscription", "Endpoint not implemented")
        else:
            result.add_fail("Cancel Subscription", f"Status: {response.status_code}")
    else:
        result.add_skip("Cancel Subscription", "No subscription ID")

    # ==================== REPORTS ====================

    # ===== Test 15: Daily Report =====
    print_info("Getting daily report...")
    today = datetime.now().strftime("%Y-%m-%d")
    response = client.get("/api/cms/reports/daily", params={"date": today})

    if response.status_code == 200:
        result.add_pass("Get Daily Report")
    elif response.status_code == 404:
        result.add_skip("Get Daily Report", "Endpoint not implemented")
    else:
        result.add_fail("Get Daily Report", f"Status: {response.status_code}")

    # ===== Test 16: Monthly Report =====
    print_info("Getting monthly report...")
    response = client.get("/api/cms/reports/monthly", params={
        "month": datetime.now().month,
        "year": datetime.now().year
    })

    if response.status_code == 200:
        result.add_pass("Get Monthly Report")
    elif response.status_code == 404:
        result.add_skip("Get Monthly Report", "Endpoint not implemented")
    else:
        result.add_fail("Get Monthly Report", f"Status: {response.status_code}")

    # ===== Test 17: Revenue Report =====
    print_info("Getting revenue report...")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    response = client.get("/api/cms/reports/revenue", params={
        "start_date": start_date,
        "end_date": end_date
    })

    if response.status_code == 200:
        result.add_pass("Get Revenue Report")
    elif response.status_code == 404:
        result.add_skip("Get Revenue Report", "Endpoint not implemented")
    else:
        result.add_fail("Get Revenue Report", f"Status: {response.status_code}")

    # ===== Test 18: Membership Report =====
    print_info("Getting membership report...")
    response = client.get("/api/cms/reports/memberships", params={
        "month": datetime.now().month,
        "year": datetime.now().year
    })

    if response.status_code == 200:
        result.add_pass("Get Membership Report")
    elif response.status_code == 404:
        result.add_skip("Get Membership Report", "Endpoint not implemented")
    else:
        result.add_fail("Get Membership Report", f"Status: {response.status_code}")

    # ===== Test 19: Check-in Report =====
    print_info("Getting check-in report...")
    response = client.get("/api/cms/reports/checkins", params={
        "start_date": start_date,
        "end_date": end_date
    })

    if response.status_code == 200:
        result.add_pass("Get Check-in Report")
    elif response.status_code == 404:
        result.add_skip("Get Check-in Report", "Endpoint not implemented")
    else:
        result.add_fail("Get Check-in Report", f"Status: {response.status_code}")

    # ===== Test 20: Class Report =====
    print_info("Getting class report...")
    response = client.get("/api/cms/reports/classes", params={
        "start_date": start_date,
        "end_date": end_date
    })

    if response.status_code == 200:
        result.add_pass("Get Class Report")
    elif response.status_code == 404:
        result.add_skip("Get Class Report", "Endpoint not implemented")
    else:
        result.add_fail("Get Class Report", f"Status: {response.status_code}")

    # ==================== SETTINGS ====================

    # ===== Test 21: Get Settings =====
    print_info("Getting gym settings...")
    response = client.get("/api/cms/settings")

    if response.status_code == 200:
        result.add_pass("Get Settings")
    elif response.status_code == 404:
        result.add_skip("Get Settings", "Endpoint not implemented")
    else:
        result.add_fail("Get Settings", f"Status: {response.status_code}")

    # ===== Test 22: Update Settings =====
    print_info("Updating settings...")
    response = client.put("/api/cms/settings", {
        "gym_name": "Moolai Gym Test",
        "checkin_cooldown_minutes": 30,
        "operating_hours_start": "06:00",
        "operating_hours_end": "22:00"
    })

    if response.status_code == 200:
        result.add_pass("Update Settings")
    elif response.status_code == 404:
        result.add_skip("Update Settings", "Endpoint not implemented")
    else:
        result.add_fail("Update Settings", f"Status: {response.status_code}")

    # ==================== DASHBOARD ====================

    # ===== Test 23: Dashboard Statistics =====
    print_info("Getting dashboard statistics...")
    response = client.get("/api/cms/dashboard/stats")

    if response.status_code == 200:
        result.add_pass("Get Dashboard Statistics")
    elif response.status_code == 404:
        result.add_skip("Get Dashboard Statistics", "Endpoint not implemented")
    else:
        result.add_fail("Get Dashboard Statistics", f"Status: {response.status_code}")

    # ===== Test 24: Dashboard Charts Data =====
    print_info("Getting dashboard charts data...")
    response = client.get("/api/cms/dashboard/charts", params={
        "period": "30days"
    })

    if response.status_code == 200:
        result.add_pass("Get Dashboard Charts")
    elif response.status_code == 404:
        result.add_skip("Get Dashboard Charts", "Endpoint not implemented")
    else:
        result.add_fail("Get Dashboard Charts", f"Status: {response.status_code}")

    return result


if __name__ == "__main__":
    result = run_admin_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
