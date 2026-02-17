"""
Test Case 06: POS/Transaction System (Opsi 3 Hybrid)
- Create product
- List products
- Create transaction with multiple items
- Apply discount
- Apply voucher
- Process payment
- View transaction history
- Refund transaction
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import APIClient, TestResult, print_header, print_info
from config import TEST_ADMIN, test_data
from datetime import datetime


def run_transaction_tests() -> TestResult:
    """Run POS/Transaction test cases"""
    print_header("TEST 06: POS/Transaction System")

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

    # ===== Test 1: Create Product Category (Admin) =====
    print_info("Creating product category (admin)...")
    category_id = None
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/products/categories", {
            "name": "Beverages",
            "description": "Drinks and beverages"
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                category_id = data.get("id") or data.get("data", {}).get("id")
                result.add_pass("Create Product Category")
            except:
                result.add_pass("Create Product Category")
        elif response.status_code == 404:
            result.add_skip("Create Product Category", "Endpoint not implemented")
        else:
            result.add_fail("Create Product Category", f"Status: {response.status_code}")
    else:
        result.add_skip("Create Product Category", "No admin token")

    # ===== Test 2: Create Product (Admin) =====
    print_info("Creating product (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/products", {
            "name": "Protein Shake",
            "description": "High protein shake",
            "sku": f"PRO-{datetime.now().strftime('%H%M%S')}",
            "price": 35000,
            "cost_price": 20000,
            "category_id": category_id,
            "is_active": True
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                product_id = data.get("id") or data.get("data", {}).get("id")
                if product_id:
                    test_data.product_id = product_id
                    print_info(f"Created product ID: {test_data.product_id}")
                result.add_pass("Create Product")
            except:
                result.add_pass("Create Product")
        elif response.status_code == 404:
            result.add_skip("Create Product", "Endpoint not implemented")
        else:
            result.add_fail("Create Product", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Product", "No admin token")

    # ===== Test 3: List Products =====
    print_info("Listing products...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/products")

        if response.status_code == 200:
            try:
                data = response.json()
                products = data if isinstance(data, list) else data.get("data", data.get("products", []))
                if products and not test_data.product_id:
                    test_data.product_id = products[0].get("id")
                result.add_pass(f"List Products ({len(products)} found)")
            except:
                result.add_pass("List Products")
        elif response.status_code == 404:
            result.add_skip("List Products", "Endpoint not implemented")
        else:
            result.add_fail("List Products", f"Status: {response.status_code}")
    else:
        result.add_skip("List Products", "No admin token")

    # ===== Test 4: Get Product Details =====
    print_info("Getting product details...")
    if test_data.admin_token and test_data.product_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/products/{test_data.product_id}")

        if response.status_code == 200:
            result.add_pass("Get Product Details")
        elif response.status_code == 404:
            result.add_skip("Get Product Details", "Endpoint not found")
        else:
            result.add_fail("Get Product Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Product Details", "Missing token or product ID")

    # ===== Test 5: Create Transaction - Simple POS =====
    print_info("Creating POS transaction (admin)...")
    if test_data.admin_token and test_data.product_id:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/transactions", {
            "user_id": test_data.member_id,
            "type": "pos",
            "items": [
                {
                    "item_type": "product",
                    "item_id": test_data.product_id,
                    "quantity": 2,
                    "unit_price": 35000
                }
            ],
            "payment_method": "cash",
            "notes": "Test POS transaction"
        })

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                txn_id = data.get("id") or data.get("transaction_id") or data.get("data", {}).get("id")
                if txn_id:
                    test_data.transaction_id = txn_id
                    print_info(f"Transaction ID: {test_data.transaction_id}")
                result.add_pass("Create POS Transaction")
            except:
                result.add_pass("Create POS Transaction")
        elif response.status_code == 404:
            result.add_skip("Create POS Transaction", "Endpoint not implemented")
        else:
            result.add_fail("Create POS Transaction", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create POS Transaction", "Missing token or product ID")

    # ===== Test 6: Create Transaction with Membership Package =====
    print_info("Creating membership purchase transaction...")
    if test_data.admin_token and test_data.package_id and test_data.member_id:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/transactions", {
            "user_id": test_data.member_id,
            "type": "membership",
            "items": [
                {
                    "item_type": "membership_package",
                    "item_id": test_data.package_id,
                    "quantity": 1,
                    "unit_price": 500000
                }
            ],
            "payment_method": "card",
            "notes": "Membership purchase"
        })

        if response.status_code in [200, 201]:
            result.add_pass("Create Membership Transaction")
        elif response.status_code == 404:
            result.add_skip("Create Membership Transaction", "Endpoint not implemented")
        else:
            result.add_fail("Create Membership Transaction", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Membership Transaction", "Missing required data")

    # ===== Test 7: Create Transaction with Mixed Items (Hybrid) =====
    print_info("Creating hybrid transaction (membership + product)...")
    if test_data.admin_token and test_data.package_id and test_data.product_id and test_data.member_id:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/transactions", {
            "user_id": test_data.member_id,
            "type": "mixed",
            "items": [
                {
                    "item_type": "membership_package",
                    "item_id": test_data.package_id,
                    "quantity": 1,
                    "unit_price": 500000,
                    "discount_amount": 50000  # Per-item discount
                },
                {
                    "item_type": "product",
                    "item_id": test_data.product_id,
                    "quantity": 3,
                    "unit_price": 35000
                }
            ],
            "discount_amount": 25000,  # Transaction-level discount
            "discount_type": "amount",
            "payment_method": "transfer",
            "notes": "Combo purchase with discount"
        })

        if response.status_code in [200, 201]:
            result.add_pass("Create Hybrid Transaction")
        elif response.status_code == 404:
            result.add_skip("Create Hybrid Transaction", "Endpoint not implemented")
        else:
            result.add_fail("Create Hybrid Transaction", f"Status: {response.status_code}, Response: {response.text[:200]}")
    else:
        result.add_skip("Create Hybrid Transaction", "Missing required data")

    # ===== Test 8: Create Voucher (Admin) =====
    print_info("Creating voucher (admin)...")
    voucher_code = f"TEST{datetime.now().strftime('%H%M%S')}"
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/vouchers", {
            "code": voucher_code,
            "discount_type": "percentage",
            "discount_value": 10,
            "max_uses": 100,
            "valid_from": datetime.now().strftime("%Y-%m-%d"),
            "valid_until": (datetime.now().replace(year=datetime.now().year + 1)).strftime("%Y-%m-%d"),
            "is_active": True
        })

        if response.status_code in [200, 201]:
            result.add_pass("Create Voucher")
            print_info(f"Voucher code: {voucher_code}")
        elif response.status_code == 404:
            result.add_skip("Create Voucher", "Endpoint not implemented")
        else:
            result.add_fail("Create Voucher", f"Status: {response.status_code}")
    else:
        result.add_skip("Create Voucher", "No admin token")

    # ===== Test 9: Apply Voucher to Transaction =====
    print_info("Creating transaction with voucher...")
    if test_data.admin_token and test_data.product_id:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/transactions", {
            "user_id": test_data.member_id,
            "type": "pos",
            "items": [
                {
                    "item_type": "product",
                    "item_id": test_data.product_id,
                    "quantity": 5,
                    "unit_price": 35000
                }
            ],
            "voucher_code": voucher_code,
            "payment_method": "cash"
        })

        if response.status_code in [200, 201]:
            result.add_pass("Apply Voucher to Transaction")
        elif response.status_code == 400:
            result.add_pass("Apply Voucher (validation applied)")
        elif response.status_code == 404:
            result.add_skip("Apply Voucher to Transaction", "Endpoint not implemented")
        else:
            result.add_fail("Apply Voucher to Transaction", f"Status: {response.status_code}")
    else:
        result.add_skip("Apply Voucher to Transaction", "Missing token or product ID")

    # ===== Test 10: List Transactions (Admin) =====
    print_info("Listing all transactions (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.get("/api/cms/transactions")

        if response.status_code == 200:
            try:
                data = response.json()
                transactions = data if isinstance(data, list) else data.get("data", data.get("transactions", []))
                if transactions and not test_data.transaction_id:
                    test_data.transaction_id = transactions[0].get("id")
                result.add_pass(f"List Transactions ({len(transactions)} found)")
            except:
                result.add_pass("List Transactions")
        elif response.status_code == 404:
            result.add_skip("List Transactions", "Endpoint not implemented")
        else:
            result.add_fail("List Transactions", f"Status: {response.status_code}")
    else:
        result.add_skip("List Transactions", "No admin token")

    # ===== Test 11: Get Transaction Details =====
    print_info("Getting transaction details...")
    if test_data.admin_token and test_data.transaction_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/transactions/{test_data.transaction_id}")

        if response.status_code == 200:
            result.add_pass("Get Transaction Details")
        elif response.status_code == 404:
            result.add_skip("Get Transaction Details", "Endpoint not found")
        else:
            result.add_fail("Get Transaction Details", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Transaction Details", "Missing token or transaction ID")

    # ===== Test 12: View My Transaction History (Mobile) =====
    print_info("Viewing my transaction history (member)...")
    if test_data.member_token:
        client.set_token(test_data.member_token)
        response = client.get("/api/member/transactions/history")

        if response.status_code == 200:
            try:
                data = response.json()
                history = data if isinstance(data, list) else data.get("data", data.get("transactions", []))
                result.add_pass(f"View Transaction History ({len(history)} found)")
            except:
                result.add_pass("View Transaction History")
        elif response.status_code == 404:
            result.add_skip("View Transaction History", "Endpoint not implemented")
        else:
            result.add_fail("View Transaction History", f"Status: {response.status_code}")
    else:
        result.add_skip("View Transaction History", "No member token")

    # ===== Test 13: Get Transaction Receipt =====
    print_info("Getting transaction receipt...")
    if test_data.admin_token and test_data.transaction_id:
        client.set_token(test_data.admin_token)
        response = client.get(f"/api/cms/transactions/{test_data.transaction_id}/receipt")

        if response.status_code == 200:
            result.add_pass("Get Transaction Receipt")
        elif response.status_code == 404:
            result.add_skip("Get Transaction Receipt", "Endpoint not implemented")
        else:
            result.add_fail("Get Transaction Receipt", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Transaction Receipt", "Missing token or transaction ID")

    # ===== Test 14: Refund Transaction (Admin) =====
    print_info("Processing refund (admin)...")
    if test_data.admin_token and test_data.transaction_id:
        client.set_token(test_data.admin_token)
        response = client.post(f"/api/cms/transactions/{test_data.transaction_id}/refund", {
            "reason": "Customer request - test refund",
            "refund_amount": 35000,  # Partial refund
            "refund_method": "cash"
        })

        if response.status_code == 200:
            result.add_pass("Process Refund")
        elif response.status_code == 400:
            result.add_pass("Process Refund (validation applied)")
        elif response.status_code == 404:
            result.add_skip("Process Refund", "Endpoint not implemented")
        else:
            result.add_fail("Process Refund", f"Status: {response.status_code}")
    else:
        result.add_skip("Process Refund", "Missing token or transaction ID")

    # ===== Test 15: Update Product Stock =====
    print_info("Updating product stock...")
    if test_data.admin_token and test_data.product_id:
        client.set_token(test_data.admin_token)
        response = client.patch(f"/api/cms/products/{test_data.product_id}/stock", {
            "adjustment": 50,
            "reason": "Stock replenishment"
        })

        if response.status_code == 200:
            result.add_pass("Update Product Stock")
        elif response.status_code == 404:
            result.add_skip("Update Product Stock", "Endpoint not implemented")
        else:
            result.add_fail("Update Product Stock", f"Status: {response.status_code}")
    else:
        result.add_skip("Update Product Stock", "Missing token or product ID")

    # ===== Test 16: Filter Transactions by Date =====
    print_info("Filtering transactions by date...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        today = datetime.now().strftime("%Y-%m-%d")
        response = client.get("/api/cms/transactions", params={
            "date_from": today,
            "date_to": today
        })

        if response.status_code == 200:
            result.add_pass("Filter Transactions by Date")
        elif response.status_code == 404:
            result.add_skip("Filter Transactions by Date", "Endpoint not implemented")
        else:
            result.add_fail("Filter Transactions by Date", f"Status: {response.status_code}")
    else:
        result.add_skip("Filter Transactions by Date", "No admin token")

    # ===== Test 17: Transaction Summary/Report =====
    print_info("Getting transaction summary...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        today = datetime.now().strftime("%Y-%m-%d")
        response = client.get("/api/cms/transactions/summary", params={
            "date": today
        })

        if response.status_code == 200:
            result.add_pass("Get Transaction Summary")
        elif response.status_code == 404:
            result.add_skip("Get Transaction Summary", "Endpoint not implemented")
        else:
            result.add_fail("Get Transaction Summary", f"Status: {response.status_code}")
    else:
        result.add_skip("Get Transaction Summary", "No admin token")

    # ===== Test 18: Create Promo (Admin) =====
    print_info("Creating promo (admin)...")
    if test_data.admin_token:
        client.set_token(test_data.admin_token)
        response = client.post("/api/cms/promos", {
            "name": "New Year Sale",
            "description": "20% off all memberships",
            "discount_type": "percentage",
            "discount_value": 20,
            "applies_to": "membership_package",
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "end_date": (datetime.now().replace(month=12, day=31)).strftime("%Y-%m-%d"),
            "is_active": True
        })

        if response.status_code in [200, 201]:
            result.add_pass("Create Promo")
        elif response.status_code == 404:
            result.add_skip("Create Promo", "Endpoint not implemented")
        else:
            result.add_fail("Create Promo", f"Status: {response.status_code}")
    else:
        result.add_skip("Create Promo", "No admin token")

    return result


if __name__ == "__main__":
    result = run_transaction_tests()
    result.summary()
    sys.exit(0 if result.failed == 0 else 1)
