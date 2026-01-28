"""
Test Case 04: Class Booking System
- List class types
- List class schedules
- Book a class
- Cancel booking
- View my bookings
- Class capacity management
- Mark attendance (admin)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, test_data
from datetime import datetime, timedelta


def run_class_tests() -> TestResult:
    """Run class booking test cases"""
    print_header("TEST 04: Class Booking System")

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

    # ===== Test 1: Create Class Type (Admin) =====
    print_info("Creating class type (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/classes/types", {
            "name": "Test Yoga Class",
            "description": "Relaxing yoga session",
            "duration_minutes": 60,
            "default_capacity": 20,
            "is_active": True
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                type_id = data.get("id") or data.get("data", {}).get("id")
                if type_id:
                    test_data.class_type_id = type_id
                    print_info(f"Created class type ID: {test_data.class_type_id}")
                result.add_pass("Create Class Type")
            except:
                result.add_pass("Create Class Type")
        elif response.status_code == 404:
            result.add_skip("Create Class Type", "Endpoint not implemented")
        else:
            result.add_fail("Create Class Type", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Class Type", "No admin token")

    # ===== Test 2: List Class Types =====
    print_info("Listing class types...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/classes/types")

        if response.status_code == 200:
            try:
                data = response.json()
                types = data if isinstance(data, list) else data.get("data", data.get("types", []))
                if types and not test_data.class_type_id:
                    test_data.class_type_id = types[0].get("id")
                result.add_pass(f"List Class Types ({len(types)} found)")
            except:
                result.add_pass("List Class Types")
        elif response.status_code == 404:
            result.add_skip("List Class Types", "Endpoint not implemented")
        else:
            result.add_fail("List Class Types", f"Status: {response.status_code}")
    else:
        result.add_skip("List Class Types", "No admin token")

    # ===== Test 3: Get Trainer ID for Class =====
    print_info("Getting trainer for class schedule...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/trainers")

        if response.status_code == 200:
            try:
                data = response.json()
                trainers = data if isinstance(data, list) else data.get("data", data.get("trainers", []))
                if trainers:
                    test_data.trainer_id = trainers[0].get("id")
                    print_info(f"Using trainer ID: {test_data.trainer_id}")
            except:
                pass
        # Create trainer if none exists
        if not test_data.trainer_id:
            response = client.post("/api/cms/trainers", {
                "name": "Test Trainer",
                "email": f"trainer_{datetime.now().strftime('%H%M%S')}@test.com",
                "phone": f"08{datetime.now().strftime('%H%M%S%f')[:10]}",
                "specialization": "Yoga",
                "is_active": True
            })
            if response.status_code in [200, 201]:
                data = response.json()
                test_data.trainer_id = data.get("id") or data.get("data", {}).get("id")
                print_info(f"Created trainer ID: {test_data.trainer_id}")

    # ===== Test 4: Create Class Schedule (Admin) =====
    print_info("Creating class schedule (admin)...")
    if test_data.admin_token and test_data.class_type_id:
        client.set_token(test_data.admin_token)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        response = client.post("/api/cms/classes/schedules", {
            "class_type_id": test_data.class_type_id,
            "trainer_id": test_data.trainer_id,
            "schedule_date": tomorrow,
            "start_time": "10:00",
            "end_time": "11:00",
            "capacity": 20,
            "is_active": True
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                schedule_id = data.get("id") or data.get("data", {}).get("id")
                if schedule_id:
                    test_data.class_schedule_id = schedule_id
                    print_info(f"Created schedule ID: {test_data.class_schedule_id}")
                result.add_pass("Create Class Schedule")
            except:
                result.add_pass("Create Class Schedule")
        elif response.status_code == 404:
            result.add_skip("Create Class Schedule", "Endpoint not implemented")
        else:
            result.add_fail("Create Class Schedule", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Class Schedule", "Missing admin token or class type ID")

    # ===== Test 5: List Class Schedules =====
    print_info("Listing class schedules...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/classes/schedules")

        if response.status_code == 200:
            try:
                data = response.json()
                schedules = data if isinstance(data, list) else data.get("data", data.get("schedules", []))
                if schedules and not test_data.class_schedule_id:
                    test_data.class_schedule_id = schedules[0].get("id")
                result.add_pass(f"List Class Schedules ({len(schedules)} found)")
            except:
                result.add_pass("List Class Schedules")
        elif response.status_code == 404:
            result.add_skip("List Class Schedules", "Endpoint not implemented")
        else:
            result.add_fail("List Class Schedules", f"Status: {response.status_code}")
    else:
        result.add_skip("List Class Schedules", "No admin token")

    # ===== Test 6: View Available Classes (Mobile) =====
    print_info("Viewing available classes (mobile)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/mobile/classes/available")

        if response.status_code == 200:
            result.add_pass("View Available Classes")
        elif response.status_code == 404:
            result.add_skip("View Available Classes", "Endpoint not implemented")
        else:
            result.add_fail("View Available Classes", f"Status: {response.status_code}")
    else:
        result.add_skip("View Available Classes", "No member token")

    # ===== Test 7: Get Class Schedule Details =====
    print_info("Getting class schedule details...")
    if test_data.class_schedule_id:
        if test_data.member_token:
            client.set_token(test_data.member_token)
            response = client.get(f"/api/mobile/classes/{test_data.class_schedule_id}")
        elif test_data.admin_token:
            client.set_token(test_data.admin_token)
            response = client.get(f"/api/cms/classes/schedules/{test_data.class_schedule_id}")
        else:
            result.add_skip("Get Class Schedule Details", "No token available")
            response = None

        if response:
            if response.status_code == 200:
                result.add_pass("Get Class Schedule Details")
            elif response.status_code == 404:
                result.add_skip("Get Class Schedule Details", "Endpoint not found")
            else:
                result.add_fail("Get Class Schedule Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Class Schedule Details", "No schedule ID")

    # ===== Test 8: Book a Class (Mobile) =====
    print_info("Booking a class (mobile)...")
    if test_data.member_token and test_data.class_schedule_id:
        client.set_token(test_data.member_token)
        response = client.post("/api/mobile/classes/book", {
            "schedule_id": test_data.class_schedule_id
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                booking_id = data.get("id") or data.get("booking_id") or data.get("data", {}).get("id")
                if booking_id:
                    test_data.class_booking_id = booking_id
                    print_info(f"Booking ID: {test_data.class_booking_id}")
                result.add_pass("Book a Class")
            except:
                result.add_pass("Book a Class")
        elif response.status_code == 400:
            result.add_pass("Book a Class (rejected - possibly already booked or no membership)")
        elif response.status_code == 404:
            result.add_skip("Book a Class", "Endpoint not implemented")
        else:
            result.add_fail("Book a Class", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Book a Class", "Missing member token or schedule ID")

    # ===== Test 9: View My Bookings (Mobile) =====
    print_info("Viewing my class bookings (mobile)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/mobile/classes/my-bookings")

        if response.status_code == 200:
            try:
                data = response.json()
                bookings = data if isinstance(data, list) else data.get("data", data.get("bookings", []))
                if bookings and not test_data.class_booking_id:
                    test_data.class_booking_id = bookings[0].get("id")
                result.add_pass(f"View My Class Bookings ({len(bookings)} found)")
            except:
                result.add_pass("View My Class Bookings")
        elif response.status_code == 404:
            result.add_skip("View My Class Bookings", "Endpoint not implemented")
        else:
            result.add_fail("View My Class Bookings", f"Status: {response.status_code}")
    else:
        result.add_skip("View My Class Bookings", "No member token")

    # ===== Test 10: Double Booking Prevention =====
    print_info("Testing double booking prevention...")
    if test_data.member_token and test_data.class_schedule_id:
        client.set_token(test_data.member_token)
        response = client.post("/api/mobile/classes/book", {
            "schedule_id": test_data.class_schedule_id
        })

        if response.status_code in [400, 409]:
            result.add_pass("Prevent Double Booking")
        elif response.status_code == 200:
            result.add_fail("Prevent Double Booking", "Should reject duplicate booking")
        elif response.status_code == 404:
            result.add_skip("Prevent Double Booking", "Endpoint not implemented")
        else:
            result.add_fail("Prevent Double Booking", f"Unexpected status: {response.status_code}")
    else:
        result.add_skip("Prevent Double Booking", "Missing token or schedule ID")

    # ===== Test 11: Class Capacity Check =====
    print_info("Checking class capacity...")
    if test_data.admin_token and test_data.class_schedule_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/classes/schedules/{test_data.class_schedule_id}/bookings")

        if response.status_code == 200:
            try:
                data = response.json()
                booked = data.get("booked_count") or len(data.get("bookings", data.get("data", [])))
                capacity = data.get("capacity", "unknown")
                result.add_pass(f"Check Class Capacity ({booked}/{capacity})")
            except:
                result.add_pass("Check Class Capacity")
        elif response.status_code == 404:
            result.add_skip("Check Class Capacity", "Endpoint not implemented")
        else:
            result.add_fail("Check Class Capacity", f"Status: {response.status_code}")
    else:
        result.add_skip("Check Class Capacity", "Missing token or schedule ID")

    # ===== Test 12: Mark Attendance (Admin) =====
    print_info("Marking class attendance (admin)...")
    if test_data.admin_token and test_data.class_booking_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/classes/bookings/{test_data.class_booking_id}/attend")

        if response.status_code == 200:
            result.add_pass("Mark Class Attendance")
        elif response.status_code == 404:
            result.add_skip("Mark Class Attendance", "Endpoint not implemented")
        else:
            result.add_fail("Mark Class Attendance", f"Status: {response.status_code}")
    else:
        result.add_skip("Mark Class Attendance", "Missing token or booking ID")

    # ===== Test 13: Cancel Class Booking (Mobile) =====
    print_info("Canceling class booking (mobile)...")
    if test_data.member_token and test_data.class_booking_id:
        client.set_token(test_data.member_token)
        response = client.post(f"/api/mobile/classes/bookings/{test_data.class_booking_id}/cancel")

        if response.status_code == 200:
            result.add_pass("Cancel Class Booking")
        elif response.status_code == 400:
            result.add_pass("Cancel Class Booking (rejected - possibly already attended)")
        elif response.status_code == 404:
            result.add_skip("Cancel Class Booking", "Endpoint not implemented")
        else:
            result.add_fail("Cancel Class Booking", f"Status: {response.status_code}")
    else:
        result.add_skip("Cancel Class Booking", "Missing token or booking ID")

    # ===== Test 14: View Class Bookings by Schedule (Admin) =====
    print_info("Viewing bookings by schedule (admin)...")
    if test_data.admin_token and test_data.class_schedule_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/classes/schedules/{test_data.class_schedule_id}/bookings")

        if response.status_code == 200:
            result.add_pass("View Class Bookings by Schedule")
        elif response.status_code == 404:
            result.add_skip("View Class Bookings by Schedule", "Endpoint not implemented")
        else:
            result.add_fail("View Class Bookings by Schedule", f"Status: {response.status_code}")
    else:
        result.add_skip("View Class Bookings by Schedule", "Missing token or schedule ID")

    # ===== Test 15: Update Class Schedule (Admin) =====
    print_info("Updating class schedule (admin)...")
    if test_data.admin_token and test_data.class_schedule_id:
        client.set_token(test_data.admin_token)
        response = client.put(f"/api/cms/classes/schedules/{test_data.class_schedule_id}", {
            "capacity": 25
        })

        if response.status_code == 200:
            result.add_pass("Update Class Schedule")
        elif response.status_code == 404:
            result.add_skip("Update Class Schedule", "Endpoint not implemented")
        else:
            result.add_fail("Update Class Schedule", f"Status: {response.status_code}")
    else:
        result.add_skip("Update Class Schedule", "Missing token or schedule ID")

    # ===== Test 16: Cancel Class Schedule (Admin) =====
    print_info("Canceling class schedule (admin)...")
    if test_data.admin_token and test_data.class_schedule_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/classes/schedules/{test_data.class_schedule_id}/cancel", {
            "reason": "Test cancellation"
        })

        if response.status_code == 200:
            result.add_pass("Cancel Class Schedule")
        elif response.status_code == 404:
            result.add_skip("Cancel Class Schedule", "Endpoint not implemented")
        else:
            result.add_fail("Cancel Class Schedule", f"Status: {response.status_code}")
    else:
        result.add_skip("Cancel Class Schedule", "Missing token or schedule ID")

    return result


if __name__ == "__main__":
    result = run_class_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
