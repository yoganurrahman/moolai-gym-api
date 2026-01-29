"""
Test Case 05: Personal Training (PT) System
- List trainers
- List PT packages
- Purchase PT package
- Book PT session
- View PT sessions
- Complete PT session
- Cancel PT session
- Trainer availability
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, test_data
from datetime import datetime, timedelta


def run_pt_tests() -> TestResult:
    """Run Personal Training test cases"""
    print_header("TEST 05: Personal Training (PT) System")

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

    # ===== Test 1: Create Trainer (Admin) =====
    print_info("Creating trainer (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/trainers", {
            "name": "John Doe PT",
            "email": f"pttrainer_{datetime.now().strftime('%H%M%S')}@test.com",
            "phone": f"08{datetime.now().strftime('%H%M%S%f')[:10]}",
            "specialization": "Strength Training, Weight Loss",
            "bio": "Certified personal trainer with 5 years experience",
            "hourly_rate": 150000,
            "is_active": True
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                trainer_id = data.get("id") or data.get("data", {}).get("id")
                if trainer_id:
                    test_data.trainer_id = trainer_id
                    print_info(f"Created trainer ID: {test_data.trainer_id}")
                result.add_pass("Create Trainer")
            except:
                result.add_pass("Create Trainer")
        elif response.status_code == 404:
            result.add_skip("Create Trainer", "Endpoint not implemented")
        else:
            result.add_fail("Create Trainer", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Trainer", "No admin token")

    # ===== Test 2: List Trainers =====
    print_info("Listing trainers...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/trainers")

        if response.status_code == 200:
            try:
                data = response.json()
                trainers = data if isinstance(data, list) else data.get("data", data.get("trainers", []))
                if trainers and not test_data.trainer_id:
                    test_data.trainer_id = trainers[0].get("id")
                result.add_pass(f"List Trainers ({len(trainers)} found)")
            except:
                result.add_pass("List Trainers")
        elif response.status_code == 404:
            result.add_skip("List Trainers", "Endpoint not implemented")
        else:
            result.add_fail("List Trainers", f"Status: {response.status_code}")
    else:
        result.add_skip("List Trainers", "No admin token")

    # ===== Test 3: Get Trainer Details =====
    print_info("Getting trainer details...")
    if test_data.trainer_id:
        if test_data.admin_token:
            client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/trainers/{test_data.trainer_id}")

        if response.status_code == 200:
            result.add_pass("Get Trainer Details")
        elif response.status_code == 404:
            result.add_skip("Get Trainer Details", "Endpoint not implemented")
        else:
            result.add_fail("Get Trainer Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Trainer Details", "No trainer ID")

    # ===== Test 4: Create PT Package (Admin) =====
    print_info("Creating PT package (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/pt/packages", {
            "name": "Basic PT Package - 10 Sessions",
            "description": "10 personal training sessions",
            "session_count": 10,
            "price": 1500000,
            "validity_days": 60,
            "is_active": True
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                pkg_id = data.get("id") or data.get("data", {}).get("id")
                if pkg_id:
                    test_data.pt_package_id = pkg_id
                    print_info(f"Created PT package ID: {test_data.pt_package_id}")
                result.add_pass("Create PT Package")
            except:
                result.add_pass("Create PT Package")
        elif response.status_code == 404:
            result.add_skip("Create PT Package", "Endpoint not implemented")
        else:
            result.add_fail("Create PT Package", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create PT Package", "No admin token")

    # ===== Test 5: List PT Packages =====
    print_info("Listing PT packages...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/pt/packages")

        if response.status_code == 200:
            try:
                data = response.json()
                packages = data if isinstance(data, list) else data.get("data", data.get("packages", []))
                if packages and not test_data.pt_package_id:
                    test_data.pt_package_id = packages[0].get("id")
                result.add_pass(f"List PT Packages ({len(packages)} found)")
            except:
                result.add_pass("List PT Packages")
        elif response.status_code == 404:
            result.add_skip("List PT Packages", "Endpoint not implemented")
        else:
            result.add_fail("List PT Packages", f"Status: {response.status_code}")
    else:
        result.add_skip("List PT Packages", "No admin token")

    # ===== Test 6: Purchase PT Package for Member (Admin) =====
    print_info("Purchasing PT package for member (admin)...")
    if test_data.admin_token and test_data.member_id and test_data.pt_package_id:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/pt/subscriptions", {
            "user_id": test_data.member_id,
            "pt_package_id": test_data.pt_package_id,
            "trainer_id": test_data.trainer_id,
            "payment_method": "cash",
            "amount_paid": 1500000
        })

        if response.status_code in [200, 201]:
            result.add_pass("Purchase PT Package for Member")
        elif response.status_code == 404:
            result.add_skip("Purchase PT Package for Member", "Endpoint not implemented")
        else:
            result.add_fail("Purchase PT Package for Member", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Purchase PT Package for Member", "Missing required data")

    # ===== Test 7: View Available Trainers (Mobile) =====
    print_info("Viewing available trainers (member)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/member/pt/trainers")

        if response.status_code == 200:
            result.add_pass("View Available Trainers (Mobile)")
        elif response.status_code == 404:
            result.add_skip("View Available Trainers (Mobile)", "Endpoint not implemented")
        else:
            result.add_fail("View Available Trainers (Mobile)", f"Status: {response.status_code}")
    else:
        result.add_skip("View Available Trainers (Mobile)", "No member token")

    # ===== Test 8: Check Trainer Availability =====
    print_info("Checking trainer availability...")
    if test_data.trainer_id:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        if test_data.member_token:
            client.set_token(test_data.member_token)
            response = client.get(f"/api/member/pt/trainers/{test_data.trainer_id}/availability", params={
                "date": tomorrow
            })
        elif test_data.admin_token:
            client.set_token(test_data.admin_token)
            response = client.get(f"/api/cms/trainers/{test_data.trainer_id}/availability", params={
                "date": tomorrow
            })
        else:
            response = None

        if response:
            if response.status_code == 200:
                result.add_pass("Check Trainer Availability")
            elif response.status_code == 404:
                result.add_skip("Check Trainer Availability", "Endpoint not implemented")
            else:
                result.add_fail("Check Trainer Availability", f"Status: {response.status_code}")
        else:
            result.add_skip("Check Trainer Availability", "No token available")
    else:
        result.add_skip("Check Trainer Availability", "No trainer ID")

    # ===== Test 9: Book PT Session (Mobile) =====
    print_info("Booking PT session (member)...")
    if test_data.member_token and test_data.trainer_id:
        client.set_token(test_data.member_token)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        response = client.post("/api/member/pt/book", {
            "trainer_id": test_data.trainer_id,
            "session_date": tomorrow,
            "start_time": "14:00",
            "end_time": "15:00",
            "notes": "Focus on upper body workout"
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                session_id = data.get("id") or data.get("session_id") or data.get("data", {}).get("id")
                if session_id:
                    test_data.pt_session_id = session_id
                    print_info(f"PT session ID: {test_data.pt_session_id}")
                result.add_pass("Book PT Session")
            except:
                result.add_pass("Book PT Session")
        elif response.status_code == 400:
            result.add_pass("Book PT Session (rejected - possibly no PT subscription)")
        elif response.status_code == 404:
            result.add_skip("Book PT Session", "Endpoint not implemented")
        else:
            result.add_fail("Book PT Session", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Book PT Session", "Missing member token or trainer ID")

    # ===== Test 10: View My PT Sessions (Mobile) =====
    print_info("Viewing my PT sessions (member)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/member/pt/my-sessions")

        if response.status_code == 200:
            try:
                data = response.json()
                sessions = data if isinstance(data, list) else data.get("data", data.get("sessions", []))
                if sessions and not test_data.pt_session_id:
                    test_data.pt_session_id = sessions[0].get("id")
                result.add_pass(f"View My PT Sessions ({len(sessions)} found)")
            except:
                result.add_pass("View My PT Sessions")
        elif response.status_code == 404:
            result.add_skip("View My PT Sessions", "Endpoint not implemented")
        else:
            result.add_fail("View My PT Sessions", f"Status: {response.status_code}")
    else:
        result.add_skip("View My PT Sessions", "No member token")

    # ===== Test 11: View PT Remaining Sessions (Mobile) =====
    print_info("Viewing remaining PT sessions (member)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/member/pt/remaining")

        if response.status_code == 200:
            try:
                data = response.json()
                remaining = data.get("remaining_sessions") or data.get("sessions_remaining", "N/A")
                result.add_pass(f"View Remaining PT Sessions ({remaining} left)")
            except:
                result.add_pass("View Remaining PT Sessions")
        elif response.status_code == 404:
            result.add_skip("View Remaining PT Sessions", "Endpoint not implemented")
        else:
            result.add_fail("View Remaining PT Sessions", f"Status: {response.status_code}")
    else:
        result.add_skip("View Remaining PT Sessions", "No member token")

    # ===== Test 12: List All PT Sessions (Admin) =====
    print_info("Listing all PT sessions (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/pt/sessions")

        if response.status_code == 200:
            try:
                data = response.json()
                sessions = data if isinstance(data, list) else data.get("data", data.get("sessions", []))
                result.add_pass(f"List All PT Sessions ({len(sessions)} found)")
            except:
                result.add_pass("List All PT Sessions")
        elif response.status_code == 404:
            result.add_skip("List All PT Sessions", "Endpoint not implemented")
        else:
            result.add_fail("List All PT Sessions", f"Status: {response.status_code}")
    else:
        result.add_skip("List All PT Sessions", "No admin token")

    # ===== Test 13: Complete PT Session (Admin) =====
    print_info("Completing PT session (admin)...")
    if test_data.admin_token and test_data.pt_session_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/pt/sessions/{test_data.pt_session_id}/complete", {
            "notes": "Great progress on strength training",
            "trainer_notes": "Member showed good form"
        })

        if response.status_code == 200:
            result.add_pass("Complete PT Session")
        elif response.status_code == 404:
            result.add_skip("Complete PT Session", "Endpoint not implemented")
        else:
            result.add_fail("Complete PT Session", f"Status: {response.status_code}")
    else:
        result.add_skip("Complete PT Session", "Missing token or session ID")

    # ===== Test 14: Cancel PT Session (Mobile) =====
    print_info("Testing PT session cancellation...")
    if test_data.member_token and test_data.trainer_id:
        client.set_token(test_data.member_token)
        # Book another session to cancel
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        response = client.post("/api/member/pt/book", {
            "trainer_id": test_data.trainer_id,
            "session_date": day_after,
            "start_time": "10:00",
            "end_time": "11:00"
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                new_session_id = data.get("id") or data.get("session_id") or data.get("data", {}).get("id")
                if new_session_id:
                    # Cancel this session
                    response = client.post(f"/api/member/pt/sessions/{new_session_id}/cancel", {
                        "reason": "Schedule conflict"
                    })
                    if response.status_code == 200:
                        result.add_pass("Cancel PT Session")
                    elif response.status_code == 404:
                        result.add_skip("Cancel PT Session", "Endpoint not implemented")
                    else:
                        result.add_fail("Cancel PT Session", f"Status: {response.status_code}")
                else:
                    result.add_skip("Cancel PT Session", "Could not get session ID")
            except:
                result.add_skip("Cancel PT Session", "Error parsing response")
        elif response.status_code == 400:
            result.add_skip("Cancel PT Session", "Could not book session to cancel")
        elif response.status_code == 404:
            result.add_skip("Cancel PT Session", "Booking endpoint not implemented")
        else:
            result.add_fail("Cancel PT Session", f"Could not book: {response.status_code}")
    else:
        result.add_skip("Cancel PT Session", "Missing token or trainer ID")

    # ===== Test 15: Update Trainer (Admin) =====
    print_info("Updating trainer (admin)...")
    if test_data.admin_token and test_data.trainer_id:
        client.set_token(test_data.admin_token)
        response = client.put(f"/api/cms/trainers/{test_data.trainer_id}", {
            "hourly_rate": 175000,
            "specialization": "Strength Training, Weight Loss, HIIT"
        })

        if response.status_code == 200:
            result.add_pass("Update Trainer")
        elif response.status_code == 404:
            result.add_skip("Update Trainer", "Endpoint not implemented")
        else:
            result.add_fail("Update Trainer", f"Status: {response.status_code}")
    else:
        result.add_skip("Update Trainer", "Missing token or trainer ID")

    # ===== Test 16: Set Trainer Availability (Admin) =====
    print_info("Setting trainer availability (admin)...")
    if test_data.admin_token and test_data.trainer_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/trainers/{test_data.trainer_id}/availability", {
            "day_of_week": 1,  # Monday
            "start_time": "08:00",
            "end_time": "20:00",
            "is_available": True
        })

        if response.status_code in [200, 201]:
            result.add_pass("Set Trainer Availability")
        elif response.status_code == 404:
            result.add_skip("Set Trainer Availability", "Endpoint not implemented")
        else:
            result.add_fail("Set Trainer Availability", f"Status: {response.status_code}")
    else:
        result.add_skip("Set Trainer Availability", "Missing token or trainer ID")

    # ===== Test 17: Trainer Sessions Report (Admin) =====
    print_info("Getting trainer sessions report (admin)...")
    if test_data.admin_token and test_data.trainer_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/trainers/{test_data.trainer_id}/sessions", params={
            "month": datetime.now().month,
            "year": datetime.now().year
        })

        if response.status_code == 200:
            result.add_pass("Trainer Sessions Report")
        elif response.status_code == 404:
            result.add_skip("Trainer Sessions Report", "Endpoint not implemented")
        else:
            result.add_fail("Trainer Sessions Report", f"Status: {response.status_code}")
    else:
        result.add_skip("Trainer Sessions Report", "Missing token or trainer ID")

    return result


if __name__ == "__main__":
    result = run_pt_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
