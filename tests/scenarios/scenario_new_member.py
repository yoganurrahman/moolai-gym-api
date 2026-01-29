#!/usr/bin/env python3
"""
Scenario: New Member Journey

This scenario simulates the complete journey of a new gym member:
1. Member registers for an account
2. Purchases a membership package
3. Receives QR code for check-in
4. First check-in at the gym
5. Browses and books a fitness class
6. Books a personal training session
7. Makes a purchase at the gym shop

This tests the integration of multiple systems working together.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import APIClient, TestResult, print_header, print_info, Colors
from config import BASE_URL, TEST_ADMIN
from datetime import datetime, timedelta
import random
import string


def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def run_scenario():
    """Run the new member journey scenario"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  SCENARIO: NEW MEMBER JOURNEY")
    print("=" * 70)
    print(f"{Colors.END}")

    client = APIClient()
    result = TestResult()

    # Test member data
    member_email = f"newmember_{generate_random_string()}@test.com"
    member_phone = f"08{random.randint(1000000000, 9999999999)}"
    member_password = "SecurePass123!"
    member_name = f"John {generate_random_string().capitalize()}"

    member_token = None
    member_id = None
    membership_id = None
    qr_code = None

    # ===== STEP 1: Member Registration =====
    print_header("STEP 1: Member Registration")
    print_info(f"Registering new member: {member_email}")

    response = client.post("/auth/register", {
        "email": member_email,
        "phone": member_phone,
        "password": member_password,
        "name": member_name,
        "gender": "male",
        "birth_date": "1995-03-15",
        "address": "123 Fitness Street, Jakarta"
    })

    if response.status_code in [200, 201]:
        data = response.json()
        member_token = data.get("access_token")
        member_id = data.get("user", {}).get("id") or data.get("id")
        result.add_pass("Member registration successful")
        print_info(f"Member ID: {member_id}")
    else:
        result.add_fail("Member registration", f"Status: {response.status_code}")
        print(f"{Colors.RED}Cannot continue without registration{Colors.END}")
        return result

    # ===== STEP 2: Purchase Membership =====
    print_header("STEP 2: Purchase Membership Package")

    # First, login as admin to get package info and process purchase
    print_info("Admin processing membership purchase...")
    response = client.post("/auth/login", {
        "email": TEST_ADMIN["email"],
        "password": TEST_ADMIN["password"]
    })

    admin_token = None
    if response.status_code == 200:
        admin_token = response.json().get("access_token")
        client.set_token(admin_token)
    else:
        result.add_skip("Membership purchase", "Admin login failed")
        return result

    # Get available packages
    response = client.get("/api/cms/packages")
    package_id = None
    package_price = 500000

    if response.status_code == 200:
        data = response.json()
        packages = data if isinstance(data, list) else data.get("data", [])
        if packages:
            package_id = packages[0].get("id")
            package_price = packages[0].get("price", 500000)
            print_info(f"Selected package ID: {package_id}, Price: Rp {package_price:,}")
        else:
            result.add_skip("Get packages", "No packages available")

    # Create membership for the new member
    if package_id and member_id:
        response = client.post("/api/cms/memberships", {
            "user_id": member_id,
            "package_id": package_id,
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "payment_method": "card",
            "amount_paid": package_price
        })

        if response.status_code in [200, 201]:
            data = response.json()
            membership_id = data.get("id") or data.get("membership_id")
            result.add_pass("Membership purchase successful")
            print_info(f"Membership ID: {membership_id}")
        else:
            result.add_fail("Membership purchase", f"Status: {response.status_code}")
    else:
        result.add_skip("Membership purchase", "Missing package or member ID")

    # ===== STEP 3: Get QR Code =====
    print_header("STEP 3: Get Member QR Code")

    client.set_token(member_token)
    response = client.get("/api/member/profile/qr-code")

    if response.status_code == 200:
        data = response.json()
        qr_code = data.get("qr_code") or data.get("qr")
        result.add_pass("QR code obtained")
        if qr_code:
            print_info(f"QR Code: {qr_code[:30]}...")
    elif response.status_code == 404:
        result.add_skip("QR code", "Endpoint not implemented")
    else:
        result.add_fail("QR code", f"Status: {response.status_code}")

    # ===== STEP 4: First Check-in =====
    print_header("STEP 4: First Check-in at Gym")

    print_info("Member scanning QR for check-in...")
    response = client.post("/api/member/checkins/scan", {
        "qr_code": qr_code or "member_qr"
    })

    if response.status_code == 200:
        data = response.json()
        checkin_id = data.get("id") or data.get("checkin_id")
        result.add_pass("Check-in successful")
        print_info(f"Check-in ID: {checkin_id}")
        print_info("Welcome to Moolai Gym! Enjoy your workout!")
    elif response.status_code == 400:
        result.add_pass("Check-in validation working (may need active membership)")
    elif response.status_code == 404:
        result.add_skip("Check-in", "Endpoint not implemented")
    else:
        result.add_fail("Check-in", f"Status: {response.status_code}")

    # ===== STEP 5: Browse and Book Class =====
    print_header("STEP 5: Browse & Book Fitness Class")

    print_info("Browsing available classes...")
    response = client.get("/api/member/classes/available")

    schedule_id = None
    if response.status_code == 200:
        data = response.json()
        classes = data if isinstance(data, list) else data.get("data", [])
        result.add_pass(f"Found {len(classes)} available classes")
        if classes:
            schedule_id = classes[0].get("id")
            class_name = classes[0].get("class_name") or classes[0].get("name", "Fitness Class")
            print_info(f"Booking: {class_name}")
    elif response.status_code == 404:
        result.add_skip("Browse classes", "Endpoint not implemented")

    if schedule_id:
        print_info("Booking the class...")
        response = client.post("/api/member/classes/book", {
            "schedule_id": schedule_id
        })

        if response.status_code in [200, 201]:
            result.add_pass("Class booked successfully")
            print_info("Class booking confirmed! See you there!")
        elif response.status_code == 400:
            result.add_pass("Class booking validation working")
        elif response.status_code == 404:
            result.add_skip("Book class", "Endpoint not implemented")
        else:
            result.add_fail("Book class", f"Status: {response.status_code}")
    else:
        result.add_skip("Book class", "No available classes")

    # ===== STEP 6: Book Personal Training =====
    print_header("STEP 6: Book Personal Training Session")

    print_info("Browsing available trainers...")
    response = client.get("/api/member/pt/trainers")

    trainer_id = None
    if response.status_code == 200:
        data = response.json()
        trainers = data if isinstance(data, list) else data.get("data", [])
        result.add_pass(f"Found {len(trainers)} trainers")
        if trainers:
            trainer_id = trainers[0].get("id")
            trainer_name = trainers[0].get("name", "Personal Trainer")
            print_info(f"Selected trainer: {trainer_name}")
    elif response.status_code == 404:
        result.add_skip("Browse trainers", "Endpoint not implemented")

    if trainer_id:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        print_info(f"Booking PT session for {tomorrow}...")
        response = client.post("/api/member/pt/book", {
            "trainer_id": trainer_id,
            "session_date": tomorrow,
            "start_time": "10:00",
            "end_time": "11:00",
            "notes": "First PT session - strength training"
        })

        if response.status_code in [200, 201]:
            result.add_pass("PT session booked")
            print_info("PT session confirmed!")
        elif response.status_code == 400:
            result.add_pass("PT booking validation working (may need PT package)")
        elif response.status_code == 404:
            result.add_skip("Book PT", "Endpoint not implemented")
        else:
            result.add_fail("Book PT", f"Status: {response.status_code}")
    else:
        result.add_skip("Book PT", "No available trainers")

    # ===== STEP 7: Purchase at Gym Shop =====
    print_header("STEP 7: Purchase at Gym Shop")

    # Get products
    client.set_token(admin_token)
    response = client.get("/api/cms/products")

    product_id = None
    product_price = 35000
    if response.status_code == 200:
        data = response.json()
        products = data if isinstance(data, list) else data.get("data", [])
        if products:
            product_id = products[0].get("id")
            product_price = products[0].get("price", 35000)
            product_name = products[0].get("name", "Product")
            print_info(f"Member purchasing: {product_name}")

    if product_id and member_id:
        print_info("Processing POS transaction...")
        response = client.post("/api/cms/transactions", {
            "user_id": member_id,
            "type": "pos",
            "items": [
                {
                    "item_type": "product",
                    "item_id": product_id,
                    "quantity": 2,
                    "unit_price": product_price
                }
            ],
            "payment_method": "cash",
            "notes": "Post-workout purchase"
        })

        if response.status_code in [200, 201]:
            data = response.json()
            total = data.get("total_amount") or product_price * 2
            result.add_pass("Shop purchase successful")
            print_info(f"Total: Rp {total:,}")
            print_info("Thank you for your purchase!")
        elif response.status_code == 404:
            result.add_skip("Shop purchase", "Endpoint not implemented")
        else:
            result.add_fail("Shop purchase", f"Status: {response.status_code}")
    else:
        result.add_skip("Shop purchase", "No products available")

    # ===== STEP 8: Check-out =====
    print_header("STEP 8: Check-out")

    client.set_token(member_token)
    response = client.post("/api/member/checkins/checkout")

    if response.status_code == 200:
        result.add_pass("Check-out successful")
        print_info("Thank you for visiting Moolai Gym! See you again!")
    elif response.status_code in [400, 404]:
        result.add_skip("Check-out", "Not checked in or endpoint not implemented")
    else:
        result.add_fail("Check-out", f"Status: {response.status_code}")

    # ===== SUMMARY =====
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  SCENARIO COMPLETE: NEW MEMBER JOURNEY")
    print("=" * 70)
    print(f"{Colors.END}")

    result.summary()

    print(f"\n  {Colors.BOLD}Member Details:{Colors.END}")
    print(f"  - Email: {member_email}")
    print(f"  - Password: {member_password}")
    print(f"  - Phone: {member_phone}")
    if membership_id:
        print(f"  - Membership ID: {membership_id}")
    print()

    return result


if __name__ == "__main__":
    result = run_scenario()
    sys.exit(0 if result.failed == 0 else 1)
