#!/usr/bin/env python3
"""
Scenario: Daily Gym Operations

This scenario simulates typical daily operations at the gym:
1. Staff opens shift and checks dashboard
2. Processes multiple member check-ins
3. Handles walk-in membership sale
4. Processes POS transactions
5. Manages class attendance
6. Handles PT session completion
7. End of day reporting

This tests the CMS/Admin functionality comprehensively.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import APIClient, TestResult, print_header, print_info, Colors
from config import BASE_URL, TEST_ADMIN
from datetime import datetime, timedelta
import random


def run_scenario():
    """Run the daily operations scenario"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  SCENARIO: DAILY GYM OPERATIONS")
    print(f"  Date: {datetime.now().strftime('%A, %d %B %Y')}")
    print("=" * 70)
    print(f"{Colors.END}")

    client = APIClient()
    result = TestResult()

    # ===== STEP 1: Staff Login & Dashboard Check =====
    print_header("STEP 1: Staff Opens Shift")

    print_info("Staff logging in...")
    response = client.post("/auth/login", {
        "email": TEST_ADMIN["email"],
        "password": TEST_ADMIN["password"]
    })

    if response.status_code != 200:
        result.add_fail("Staff login", "Cannot login - stopping scenario")
        return result

    admin_token = response.json().get("access_token")
    client.set_token(admin_token)
    result.add_pass("Staff logged in successfully")
    print_info("Good morning! Starting shift...")

    # Check dashboard
    print_info("Loading dashboard...")
    response = client.get("/api/cms/dashboard/stats")

    if response.status_code == 200:
        data = response.json()
        result.add_pass("Dashboard loaded")
        # Display stats if available
        active = data.get("active_members", "N/A")
        checkins = data.get("today_checkins", "N/A")
        revenue = data.get("today_revenue", "N/A")
        print_info(f"Active Members: {active}")
        print_info(f"Today's Check-ins: {checkins}")
        print_info(f"Today's Revenue: Rp {revenue}")
    elif response.status_code == 404:
        result.add_skip("Dashboard", "Not implemented")
    else:
        result.add_fail("Dashboard", f"Status: {response.status_code}")

    # ===== STEP 2: Process Member Check-ins =====
    print_header("STEP 2: Process Member Check-ins")

    # Get some members to check in
    response = client.get("/api/cms/users", params={"role": "member", "limit": 5})

    members_to_checkin = []
    if response.status_code == 200:
        data = response.json()
        members = data if isinstance(data, list) else data.get("data", [])
        members_to_checkin = members[:3] if len(members) >= 3 else members
        print_info(f"Found {len(members)} members in system")

    checkin_count = 0
    for member in members_to_checkin:
        member_id = member.get("id")
        member_name = member.get("name", f"Member {member_id}")
        print_info(f"Checking in: {member_name}")

        response = client.post("/api/cms/checkins", {
            "user_id": member_id,
            "check_in_method": "manual",
            "notes": "Morning check-in"
        })

        if response.status_code in [200, 201]:
            checkin_count += 1
            print_info(f"  ✓ {member_name} checked in")
        elif response.status_code == 400:
            print_info(f"  ⊘ {member_name} - no active membership or already checked in")

    if checkin_count > 0:
        result.add_pass(f"Processed {checkin_count} check-ins")
    else:
        result.add_skip("Check-ins", "No members available or all rejected")

    # ===== STEP 3: Walk-in Membership Sale =====
    print_header("STEP 3: Walk-in Membership Sale")

    print_info("New customer wants to purchase membership...")

    # Register new walk-in customer
    walkin_email = f"walkin_{datetime.now().strftime('%H%M%S')}@test.com"
    walkin_phone = f"08{random.randint(1000000000, 9999999999)}"

    response = client.post("/api/cms/users", {
        "email": walkin_email,
        "phone": walkin_phone,
        "name": "Walk-in Customer",
        "gender": "female",
        "role_id": 3,
        "is_active": True
    })

    walkin_id = None
    if response.status_code in [200, 201]:
        data = response.json()
        walkin_id = data.get("id") or data.get("data", {}).get("id")
        result.add_pass("Created walk-in customer account")
        print_info(f"Customer ID: {walkin_id}")
    else:
        result.add_fail("Create walk-in customer", f"Status: {response.status_code}")

    # Get packages and sell membership
    if walkin_id:
        response = client.get("/api/cms/packages")
        if response.status_code == 200:
            data = response.json()
            packages = data if isinstance(data, list) else data.get("data", [])
            if packages:
                pkg = packages[0]
                pkg_id = pkg.get("id")
                pkg_price = pkg.get("price", 500000)
                pkg_name = pkg.get("name", "Membership")

                print_info(f"Selling: {pkg_name} @ Rp {pkg_price:,}")

                response = client.post("/api/cms/memberships", {
                    "user_id": walkin_id,
                    "package_id": pkg_id,
                    "start_date": datetime.now().strftime("%Y-%m-%d"),
                    "payment_method": "cash",
                    "amount_paid": pkg_price
                })

                if response.status_code in [200, 201]:
                    result.add_pass("Membership sold to walk-in customer")
                    print_info("Payment received, membership activated!")
                else:
                    result.add_fail("Sell membership", f"Status: {response.status_code}")

    # ===== STEP 4: POS Transactions =====
    print_header("STEP 4: POS Transactions")

    # Get products
    response = client.get("/api/cms/products")
    products = []
    if response.status_code == 200:
        data = response.json()
        products = data if isinstance(data, list) else data.get("data", [])

    if products and members_to_checkin:
        for i, member in enumerate(members_to_checkin[:2]):
            member_id = member.get("id")
            member_name = member.get("name", f"Member {member_id}")
            product = products[i % len(products)]
            product_id = product.get("id")
            product_name = product.get("name", "Product")
            product_price = product.get("price", 25000)

            print_info(f"{member_name} purchasing {product_name}...")

            response = client.post("/api/cms/transactions", {
                "user_id": member_id,
                "type": "pos",
                "items": [{
                    "item_type": "product",
                    "item_id": product_id,
                    "quantity": 1,
                    "unit_price": product_price
                }],
                "payment_method": "cash"
            })

            if response.status_code in [200, 201]:
                result.add_pass(f"POS: {member_name} - {product_name}")
                print_info(f"  ✓ Rp {product_price:,} - Cash")
            elif response.status_code == 404:
                result.add_skip("POS Transaction", "Endpoint not implemented")
                break
            else:
                result.add_fail("POS Transaction", f"Status: {response.status_code}")
    else:
        result.add_skip("POS Transactions", "No products or members available")

    # ===== STEP 5: Class Attendance =====
    print_header("STEP 5: Manage Class Attendance")

    response = client.get("/api/cms/classes/schedules", params={
        "date": datetime.now().strftime("%Y-%m-%d")
    })

    if response.status_code == 200:
        data = response.json()
        schedules = data if isinstance(data, list) else data.get("data", [])
        if schedules:
            schedule = schedules[0]
            schedule_id = schedule.get("id")
            class_name = schedule.get("class_name") or schedule.get("name", "Class")

            print_info(f"Managing attendance for: {class_name}")

            # Get bookings for this class
            response = client.get(f"/api/cms/classes/schedules/{schedule_id}/bookings")
            if response.status_code == 200:
                data = response.json()
                bookings = data if isinstance(data, list) else data.get("data", data.get("bookings", []))
                print_info(f"  {len(bookings)} bookings for this class")

                # Mark some as attended
                attended = 0
                for booking in bookings[:3]:
                    booking_id = booking.get("id")
                    response = client.post(f"/api/cms/classes/bookings/{booking_id}/attend")
                    if response.status_code == 200:
                        attended += 1

                if attended > 0:
                    result.add_pass(f"Marked {attended} members as attended")
                else:
                    result.add_skip("Class attendance", "No bookings to mark")
            else:
                result.add_skip("Class bookings", "Could not get bookings")
        else:
            result.add_skip("Class attendance", "No classes scheduled today")
    elif response.status_code == 404:
        result.add_skip("Class attendance", "Endpoint not implemented")
    else:
        result.add_fail("Class attendance", f"Status: {response.status_code}")

    # ===== STEP 6: PT Session Management =====
    print_header("STEP 6: PT Session Management")

    response = client.get("/api/cms/pt/sessions", params={
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "scheduled"
    })

    if response.status_code == 200:
        data = response.json()
        sessions = data if isinstance(data, list) else data.get("data", [])
        if sessions:
            session = sessions[0]
            session_id = session.get("id")
            member_name = session.get("member_name", "Member")
            trainer_name = session.get("trainer_name", "Trainer")

            print_info(f"Completing PT session: {member_name} with {trainer_name}")

            response = client.post(f"/api/cms/pt/sessions/{session_id}/complete", {
                "notes": "Great workout session, good progress on strength",
                "trainer_notes": "Member showed excellent form"
            })

            if response.status_code == 200:
                result.add_pass("PT session completed")
                print_info("  ✓ Session marked as complete")
            else:
                result.add_fail("Complete PT session", f"Status: {response.status_code}")
        else:
            result.add_skip("PT sessions", "No sessions scheduled today")
    elif response.status_code == 404:
        result.add_skip("PT sessions", "Endpoint not implemented")
    else:
        result.add_fail("PT sessions", f"Status: {response.status_code}")

    # ===== STEP 7: Process Check-outs =====
    print_header("STEP 7: Process Check-outs")

    response = client.get("/api/cms/checkins/active")

    if response.status_code == 200:
        data = response.json()
        active = data if isinstance(data, list) else data.get("data", [])
        print_info(f"{len(active)} members currently checked in")

        checkout_count = 0
        for checkin in active[:2]:
            checkin_id = checkin.get("id")
            member_name = checkin.get("member_name") or checkin.get("user", {}).get("name", "Member")

            response = client.post(f"/api/cms/checkins/{checkin_id}/checkout")
            if response.status_code == 200:
                checkout_count += 1
                print_info(f"  ✓ {member_name} checked out")

        if checkout_count > 0:
            result.add_pass(f"Processed {checkout_count} check-outs")
        else:
            result.add_skip("Check-outs", "No active check-ins to process")
    elif response.status_code == 404:
        result.add_skip("Check-outs", "Endpoint not implemented")
    else:
        result.add_fail("Check-outs", f"Status: {response.status_code}")

    # ===== STEP 8: End of Day Report =====
    print_header("STEP 8: End of Day Report")

    today = datetime.now().strftime("%Y-%m-%d")

    print_info("Generating daily report...")
    response = client.get("/api/cms/reports/daily", params={"date": today})

    if response.status_code == 200:
        data = response.json()
        result.add_pass("Daily report generated")

        print(f"\n  {Colors.BOLD}═══ DAILY REPORT: {today} ═══{Colors.END}")
        print(f"  Total Check-ins: {data.get('total_checkins', 'N/A')}")
        print(f"  New Members: {data.get('new_members', 'N/A')}")
        print(f"  Classes Held: {data.get('classes_held', 'N/A')}")
        print(f"  PT Sessions: {data.get('pt_sessions', 'N/A')}")
        print(f"  Total Revenue: Rp {data.get('total_revenue', 'N/A')}")
        print(f"  - Memberships: Rp {data.get('membership_revenue', 'N/A')}")
        print(f"  - POS Sales: Rp {data.get('pos_revenue', 'N/A')}")
        print(f"  - PT: Rp {data.get('pt_revenue', 'N/A')}")
        print(f"  {Colors.BOLD}═══════════════════════════════{Colors.END}\n")

    elif response.status_code == 404:
        result.add_skip("Daily report", "Endpoint not implemented")
    else:
        result.add_fail("Daily report", f"Status: {response.status_code}")

    # Transaction summary
    print_info("Getting transaction summary...")
    response = client.get("/api/cms/transactions/summary", params={"date": today})

    if response.status_code == 200:
        data = response.json()
        result.add_pass("Transaction summary generated")
        print_info(f"Total transactions: {data.get('count', 'N/A')}")
        print_info(f"Total amount: Rp {data.get('total', 'N/A')}")
    elif response.status_code == 404:
        result.add_skip("Transaction summary", "Endpoint not implemented")

    # ===== SUMMARY =====
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  SCENARIO COMPLETE: DAILY OPERATIONS")
    print("=" * 70)
    print(f"{Colors.END}")

    result.summary()

    print_info("Shift complete! Have a good rest.")
    print()

    return result


if __name__ == "__main__":
    result = run_scenario()
    sys.exit(0 if result.failed == 0 else 1)
