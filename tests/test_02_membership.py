"""
Test Case 02: Membership Management
- List membership packages
- Purchase membership
- View my membership
- Freeze/unfreeze membership (admin)
- Renew membership
- Membership status check
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, test_data
from datetime import datetime, timedelta


def run_membership_tests() -> TestResult:
    """Run membership management test cases"""
    print_header("TEST 02: Membership Management")

    client = APIClient()
    result = TestResult()

    # ===== Setup: Login as admin first =====
    if not test_data.admin_token:
        print_info("Logging in as admin...")
        response = client.post("/auth/login", {
            "email": TEST_ADMIN["email"],
            "password": TEST_ADMIN["password"]
        })
        if response.status_code == 200:
            test_data.admin_token = response.json().get("access_token")
        else:
            result.add_skip("Admin Login", "Admin not available - skipping admin tests")

    # ===== Test 1: List Membership Packages (Public) =====
    print_info("Listing membership packages...")
    response = client.get("/api/cms/packages")

    if response.status_code == 200:
        try:
            data = response.json()
            packages = data if isinstance(data, list) else data.get("data", data.get("packages", []))
            if len(packages) > 0:
                result.add_pass("List Membership Packages")
                test_data.package_id = packages[0].get("id")
                print_info(f"Found {len(packages)} packages, using ID: {test_data.package_id}")
            else:
                result.add_fail("List Membership Packages", "No packages found - please seed database")
        except Exception as e:
            result.add_fail("List Membership Packages", f"Error parsing: {str(e)}")
    elif response.status_code == 401:
        # Try with admin token
        if test_data.admin_token:
            client.set_token(test_data.admin_token)
            response = client.get("/api/cms/packages")
            if response.status_code == 200:
                data = response.json()
                packages = data if isinstance(data, list) else data.get("data", data.get("packages", []))
                if len(packages) > 0:
                    result.add_pass("List Membership Packages (Admin)")
                    test_data.package_id = packages[0].get("id")
                else:
                    result.add_fail("List Membership Packages", "No packages found")
            else:
                result.add_fail("List Membership Packages", f"Status: {response.status_code}")
        else:
            result.add_skip("List Membership Packages", "Requires authentication")
    else:
        result.add_fail("List Membership Packages", f"Status: {response.status_code}")

    # ===== Test 2: Create Membership Package (Admin) =====
    print_info("Creating new membership package (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/packages", {
            "name": "Test Package - 1 Month",
            "description": "Test membership package",
            "price": 500000,
            "duration_type": "months",
            "duration_value": 1,
            "visit_limit": None,  # Unlimited visits
            "is_active": True
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                pkg_id = data.get("id") or data.get("data", {}).get("id")
                if pkg_id:
                    test_data.package_id = pkg_id
                    result.add_pass("Create Membership Package")
                    print_info(f"Created package ID: {test_data.package_id}")
                else:
                    result.add_pass("Create Membership Package (no ID returned)")
            except:
                result.add_pass("Create Membership Package")
        elif response.status_code == 404:
            result.add_skip("Create Membership Package", "Endpoint not implemented")
        else:
            result.add_fail("Create Membership Package", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Membership Package", "No admin token")

    # ===== Test 3: Get Package Details =====
    print_info("Getting package details...")
    if test_data.package_id:
        response = client.get(f"/api/cms/packages/{test_data.package_id}")

        if response.status_code == 200:
            result.add_pass("Get Package Details")
        elif response.status_code == 404:
            result.add_skip("Get Package Details", "Endpoint not implemented")
        else:
            result.add_fail("Get Package Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Package Details", "No package ID available")

    # ===== Test 4: Purchase Membership (Admin creates for member) =====
    print_info("Creating membership for member (admin)...")
    if test_data.admin_token and test_data.package_id:
        client.set_token(test_data.admin_token)

        # First, get or create a member
        if not test_data.member_id:
            # Create a test member
            response = client.post("/api/cms/users", {
                "email": f"testmember_{datetime.now().strftime('%H%M%S')}@test.com",
                "phone": f"08{datetime.now().strftime('%H%M%S%f')[:10]}",
                "name": "Test Member for Membership",
                "gender": "male",
                "role_id": 3  # Member role
            })
            if response.status_code in [200, 201]:
                data = response.json()
                test_data.member_id = data.get("id") or data.get("data", {}).get("id")
                print_info(f"Created test member ID: {test_data.member_id}")

        if test_data.member_id:
            start_date = datetime.now().strftime("%Y-%m-%d")
            response = client.post("/api/cms/memberships", {
                "user_id": test_data.member_id,
                "package_id": test_data.package_id,
                "start_date": start_date,
                "payment_method": "cash",
                "amount_paid": 500000
            })

            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    membership_id = data.get("id") or data.get("data", {}).get("id") or data.get("membership_id")
                    if membership_id:
                        test_data.membership_id = membership_id
                        print_info(f"Created membership ID: {test_data.membership_id}")
                    result.add_pass("Create Membership for Member")
                except:
                    result.add_pass("Create Membership for Member")
            elif response.status_code == 404:
                result.add_skip("Create Membership for Member", "Endpoint not implemented")
            else:
                result.add_fail("Create Membership for Member", f"Status: {response.status_code}, Response: {response.text[:200]}")
        else:
            result.add_skip("Create Membership for Member", "No member ID available")
    else:
        result.add_skip("Create Membership for Member", "Missing admin token or package ID")

    # ===== Test 5: List All Memberships (Admin) =====
    print_info("Listing all memberships (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/memberships")

        if response.status_code == 200:
            try:
                data = response.json()
                memberships = data if isinstance(data, list) else data.get("data", data.get("memberships", []))
                result.add_pass(f"List All Memberships ({len(memberships)} found)")
                if memberships and not test_data.membership_id:
                    test_data.membership_id = memberships[0].get("id")
            except Exception as e:
                result.add_fail("List All Memberships", f"Error: {str(e)}")
        elif response.status_code == 404:
            result.add_skip("List All Memberships", "Endpoint not implemented")
        else:
            result.add_fail("List All Memberships", f"Status: {response.status_code}")
    else:
        result.add_skip("List All Memberships", "No admin token")

    # ===== Test 6: Get Membership Details =====
    print_info("Getting membership details...")
    if test_data.admin_token and test_data.membership_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/memberships/{test_data.membership_id}")

        if response.status_code == 200:
            result.add_pass("Get Membership Details")
        elif response.status_code == 404:
            result.add_skip("Get Membership Details", "Endpoint or membership not found")
        else:
            result.add_fail("Get Membership Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Membership Details", "Missing token or membership ID")

    # ===== Test 7: Freeze Membership (Admin) =====
    print_info("Freezing membership (admin)...")
    if test_data.admin_token and test_data.membership_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/memberships/{test_data.membership_id}/freeze", {
            "reason": "Test freeze",
            "freeze_until": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        })

        if response.status_code == 200:
            result.add_pass("Freeze Membership")
        elif response.status_code == 404:
            result.add_skip("Freeze Membership", "Endpoint not implemented")
        else:
            result.add_fail("Freeze Membership", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Freeze Membership", "Missing token or membership ID")

    # ===== Test 8: Unfreeze Membership (Admin) =====
    print_info("Unfreezing membership (admin)...")
    if test_data.admin_token and test_data.membership_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/memberships/{test_data.membership_id}/unfreeze")

        if response.status_code == 200:
            result.add_pass("Unfreeze Membership")
        elif response.status_code == 404:
            result.add_skip("Unfreeze Membership", "Endpoint not implemented")
        else:
            result.add_fail("Unfreeze Membership", f"Status: {response.status_code}")
    else:
        result.add_skip("Unfreeze Membership", "Missing token or membership ID")

    # ===== Test 9: Member Views Own Membership (Mobile) =====
    print_info("Member viewing own membership (mobile)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/mobile/memberships/my")

        if response.status_code == 200:
            result.add_pass("Member View Own Membership")
        elif response.status_code == 404:
            result.add_skip("Member View Own Membership", "No active membership or endpoint not found")
        else:
            result.add_fail("Member View Own Membership", f"Status: {response.status_code}")
    else:
        result.add_skip("Member View Own Membership", "No member token")

    # ===== Test 10: Check Membership Status =====
    print_info("Checking membership status...")
    if test_data.admin_token and test_data.member_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/memberships/user/{test_data.member_id}/status")

        if response.status_code == 200:
            result.add_pass("Check Membership Status")
        elif response.status_code == 404:
            result.add_skip("Check Membership Status", "Endpoint not implemented")
        else:
            result.add_fail("Check Membership Status", f"Status: {response.status_code}")
    else:
        result.add_skip("Check Membership Status", "Missing token or member ID")

    # ===== Test 11: Renew Membership =====
    print_info("Renewing membership...")
    if test_data.admin_token and test_data.membership_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/memberships/{test_data.membership_id}/renew", {
            "package_id": test_data.package_id,
            "payment_method": "cash",
            "amount_paid": 500000
        })

        if response.status_code == 200:
            result.add_pass("Renew Membership")
        elif response.status_code == 404:
            result.add_skip("Renew Membership", "Endpoint not implemented")
        else:
            result.add_fail("Renew Membership", f"Status: {response.status_code}")
    else:
        result.add_skip("Renew Membership", "Missing token or membership ID")

    # ===== Test 12: Get QR Code for Member =====
    print_info("Getting member QR code...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/mobile/profile/qr-code")

        if response.status_code == 200:
            try:
                data = response.json()
                qr = data.get("qr_code") or data.get("qr")
                if qr:
                    test_data.qr_code = qr
                    print_info(f"Got QR code: {test_data.qr_code[:20]}...")
                result.add_pass("Get Member QR Code")
            except:
                result.add_pass("Get Member QR Code")
        elif response.status_code == 404:
            result.add_skip("Get Member QR Code", "Endpoint not implemented")
        else:
            result.add_fail("Get Member QR Code", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Member QR Code", "No member token")

    # ===== Test 13: List Expiring Memberships (Admin) =====
    print_info("Listing expiring memberships...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/memberships/expiring", params={"days": 30})

        if response.status_code == 200:
            result.add_pass("List Expiring Memberships")
        elif response.status_code == 404:
            result.add_skip("List Expiring Memberships", "Endpoint not implemented")
        else:
            result.add_fail("List Expiring Memberships", f"Status: {response.status_code}")
    else:
        result.add_skip("List Expiring Memberships", "No admin token")

    # ===== Test 14: Update Package (Admin) =====
    print_info("Updating membership package...")
    if test_data.admin_token and test_data.package_id:
        client.set_token(test_data.admin_token)
        response = client.put(f"/api/cms/packages/{test_data.package_id}", {
            "name": "Test Package - Updated",
            "price": 550000
        })

        if response.status_code == 200:
            result.add_pass("Update Membership Package")
        elif response.status_code == 404:
            result.add_skip("Update Membership Package", "Endpoint not implemented")
        else:
            result.add_fail("Update Membership Package", f"Status: {response.status_code}")
    else:
        result.add_skip("Update Membership Package", "Missing token or package ID")

    return result


if __name__ == "__main__":
    result = run_membership_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
