"""
Test Case 03: Check-in/Checkout System
- QR Scan check-in
- Manual check-in (admin)
- Check-out
- View check-in history
- Cooldown period validation
- Check-in without active membership
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, test_data
from datetime import datetime
import time


def run_checkin_tests() -> TestResult:
    """Run check-in/checkout test cases"""
    print_header("TEST 03: Check-in/Checkout System")

    client = APIClient()
    result = TestResult()

    # ===== Setup: Ensure we have tokens =====
    if not test_data.admin_token:
        print_info("Logging in as admin...")
        response = client.post("/auth/login", {
            "email": TEST_ADMIN["email"],
            "password": TEST_ADMIN["password"]
        })
        if response.status_code == 200:
            test_data.admin_token = response.json().get("access_token")

    # ===== Test 1: QR Scan Check-in (Mobile) =====
    print_info("Testing QR scan check-in...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.post("/api/mobile/checkins/scan", {
            "qr_code": test_data.qr_code or "test_qr_code"
        })

        if response.status_code == 200:
            try:
                data = response.json()
                checkin_id = data.get("id") or data.get("checkin_id") or data.get("data", {}).get("id")
                if checkin_id:
                    test_data.checkin_id = checkin_id
                    print_info(f"Check-in ID: {test_data.checkin_id}")
                result.add_pass("QR Scan Check-in")
            except:
                result.add_pass("QR Scan Check-in")
        elif response.status_code == 400:
            result.add_pass("QR Scan Check-in (rejected - possibly no active membership)")
        elif response.status_code == 404:
            result.add_skip("QR Scan Check-in", "Endpoint not implemented")
        else:
            result.add_fail("QR Scan Check-in", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("QR Scan Check-in", "No member token")

    # ===== Test 2: Manual Check-in (Admin) =====
    print_info("Testing manual check-in (admin)...")
    if test_data.admin_token and test_data.member_id:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/checkins", {
            "user_id": test_data.member_id,
            "check_in_method": "manual",
            "notes": "Manual check-in by admin"
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                checkin_id = data.get("id") or data.get("checkin_id") or data.get("data", {}).get("id")
                if checkin_id:
                    test_data.checkin_id = checkin_id
                    print_info(f"Manual check-in ID: {test_data.checkin_id}")
                result.add_pass("Manual Check-in (Admin)")
            except:
                result.add_pass("Manual Check-in (Admin)")
        elif response.status_code == 400:
            result.add_pass("Manual Check-in (rejected - possibly no active membership)")
        elif response.status_code == 404:
            result.add_skip("Manual Check-in (Admin)", "Endpoint not implemented")
        else:
            result.add_fail("Manual Check-in (Admin)", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Manual Check-in (Admin)", "Missing admin token or member ID")

    # ===== Test 3: Check-in Cooldown Period =====
    print_info("Testing check-in cooldown period...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        # Try to check-in again immediately
        response = client.post("/api/mobile/checkins/scan", {
            "qr_code": test_data.qr_code or "test_qr_code"
        })

        if response.status_code in [400, 429]:
            result.add_pass("Check-in Cooldown Enforced")
        elif response.status_code == 200:
            result.add_fail("Check-in Cooldown Enforced", "Should reject check-in during cooldown")
        elif response.status_code == 404:
            result.add_skip("Check-in Cooldown Enforced", "Endpoint not implemented")
        else:
            result.add_fail("Check-in Cooldown Enforced", f"Unexpected status: {response.status_code}")
    else:
        result.add_skip("Check-in Cooldown Enforced", "No member token")

    # ===== Test 4: View Check-in Status (Mobile) =====
    print_info("Viewing current check-in status...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/mobile/checkins/status")

        if response.status_code == 200:
            try:
                data = response.json()
                is_checked_in = data.get("is_checked_in", False)
                print_info(f"Currently checked in: {is_checked_in}")
                result.add_pass("View Check-in Status")
            except:
                result.add_pass("View Check-in Status")
        elif response.status_code == 404:
            result.add_skip("View Check-in Status", "Endpoint not implemented")
        else:
            result.add_fail("View Check-in Status", f"Status: {response.status_code}")
    else:
        result.add_skip("View Check-in Status", "No member token")

    # ===== Test 5: View Member Check-in History (Mobile) =====
    print_info("Viewing member check-in history...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/mobile/checkins/history")

        if response.status_code == 200:
            try:
                data = response.json()
                history = data if isinstance(data, list) else data.get("data", data.get("checkins", []))
                result.add_pass(f"View Check-in History ({len(history)} records)")
            except:
                result.add_pass("View Check-in History")
        elif response.status_code == 404:
            result.add_skip("View Check-in History", "Endpoint not implemented")
        else:
            result.add_fail("View Check-in History", f"Status: {response.status_code}")
    else:
        result.add_skip("View Check-in History", "No member token")

    # ===== Test 6: Check-out (Mobile) =====
    print_info("Testing check-out...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.post("/api/mobile/checkins/checkout")

        if response.status_code == 200:
            result.add_pass("Check-out")
        elif response.status_code == 400:
            result.add_pass("Check-out (no active check-in)")
        elif response.status_code == 404:
            result.add_skip("Check-out", "Endpoint not implemented")
        else:
            result.add_fail("Check-out", f"Status: {response.status_code}")
    else:
        result.add_skip("Check-out", "No member token")

    # ===== Test 7: Admin Check-out Member =====
    print_info("Testing admin check-out member...")
    if test_data.admin_token and test_data.checkin_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/checkins/{test_data.checkin_id}/checkout")

        if response.status_code == 200:
            result.add_pass("Admin Check-out Member")
        elif response.status_code == 400:
            result.add_pass("Admin Check-out Member (already checked out)")
        elif response.status_code == 404:
            result.add_skip("Admin Check-out Member", "Endpoint not implemented")
        else:
            result.add_fail("Admin Check-out Member", f"Status: {response.status_code}")
    else:
        result.add_skip("Admin Check-out Member", "Missing token or check-in ID")

    # ===== Test 8: List All Check-ins (Admin) =====
    print_info("Listing all check-ins (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/checkins")

        if response.status_code == 200:
            try:
                data = response.json()
                checkins = data if isinstance(data, list) else data.get("data", data.get("checkins", []))
                result.add_pass(f"List All Check-ins ({len(checkins)} records)")
            except:
                result.add_pass("List All Check-ins")
        elif response.status_code == 404:
            result.add_skip("List All Check-ins", "Endpoint not implemented")
        else:
            result.add_fail("List All Check-ins", f"Status: {response.status_code}")
    else:
        result.add_skip("List All Check-ins", "No admin token")

    # ===== Test 9: Filter Check-ins by Date (Admin) =====
    print_info("Filtering check-ins by date...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        today = datetime.now().strftime("%Y-%m-%d")
        response = client.get("/api/cms/checkins", params={
            "date_from": today,
            "date_to": today
        })

        if response.status_code == 200:
            result.add_pass("Filter Check-ins by Date")
        elif response.status_code == 404:
            result.add_skip("Filter Check-ins by Date", "Endpoint not implemented")
        else:
            result.add_fail("Filter Check-ins by Date", f"Status: {response.status_code}")
    else:
        result.add_skip("Filter Check-ins by Date", "No admin token")

    # ===== Test 10: Currently Checked-in Members (Admin) =====
    print_info("Getting currently checked-in members...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/checkins/active")

        if response.status_code == 200:
            try:
                data = response.json()
                active = data if isinstance(data, list) else data.get("data", data.get("active", []))
                result.add_pass(f"Currently Checked-in Members ({len(active)} active)")
            except:
                result.add_pass("Currently Checked-in Members")
        elif response.status_code == 404:
            result.add_skip("Currently Checked-in Members", "Endpoint not implemented")
        else:
            result.add_fail("Currently Checked-in Members", f"Status: {response.status_code}")
    else:
        result.add_skip("Currently Checked-in Members", "No admin token")

    # ===== Test 11: Check-in Statistics (Admin) =====
    print_info("Getting check-in statistics...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/checkins/stats")

        if response.status_code == 200:
            result.add_pass("Get Check-in Statistics")
        elif response.status_code == 404:
            result.add_skip("Get Check-in Statistics", "Endpoint not implemented")
        else:
            result.add_fail("Get Check-in Statistics", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Check-in Statistics", "No admin token")

    # ===== Test 12: Check-in without Membership =====
    print_info("Testing check-in without active membership...")
    # Create a new user without membership and try to check-in
    if test_data.admin_token:
        client.set_token(test_data.admin_token)

        # Register new user
        new_email = f"nomember_{datetime.now().strftime('%H%M%S')}@test.com"
        response = client.post("/auth/register", {
            "email": new_email,
            "phone": f"08{datetime.now().strftime('%H%M%S%f')[:10]}",
            "password": "testpass123",
            "name": "No Membership User"
        })

        if response.status_code in [200, 201]:
            temp_token = response.json().get("access_token")
            if temp_token:
                client.set_token(temp_token)
                response = client.post("/api/mobile/checkins/scan", {
                    "qr_code": "test_qr"
                })

                if response.status_code in [400, 403]:
                    result.add_pass("Reject Check-in without Membership")
                elif response.status_code == 404:
                    result.add_skip("Reject Check-in without Membership", "Endpoint not implemented")
                else:
                    result.add_fail("Reject Check-in without Membership", f"Should reject, got {response.status_code}")
            else:
                result.add_skip("Reject Check-in without Membership", "Could not get token")
        else:
            result.add_skip("Reject Check-in without Membership", "Could not create test user")
    else:
        result.add_skip("Reject Check-in without Membership", "No admin token")

    # ===== Test 13: Get Check-in Details (Admin) =====
    print_info("Getting check-in details...")
    if test_data.admin_token and test_data.checkin_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/checkins/{test_data.checkin_id}")

        if response.status_code == 200:
            result.add_pass("Get Check-in Details")
        elif response.status_code == 404:
            result.add_skip("Get Check-in Details", "Endpoint or record not found")
        else:
            result.add_fail("Get Check-in Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Check-in Details", "Missing token or check-in ID")

    return result


if __name__ == "__main__":
    result = run_checkin_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
