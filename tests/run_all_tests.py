#!/usr/bin/env python3
"""
Moolai Gym API - Complete Test Suite Runner

This script runs all test cases to verify API functionality.
Covers all major GymMaster-like features:
- Authentication (register, login, OTP)
- Membership Management
- Check-in/Checkout System
- Class Booking
- Personal Training (PT)
- POS/Transactions (Opsi 3 Hybrid)
- Admin Operations & Reports

Usage:
    python run_all_tests.py [options]

Options:
    --skip-auth     Skip authentication tests
    --skip-membership   Skip membership tests
    --skip-checkin  Skip check-in tests
    --skip-classes  Skip class booking tests
    --skip-pt       Skip PT tests
    --skip-transactions Skip transaction tests
    --skip-admin    Skip admin tests
    --only=<test>   Run only specified test (auth, membership, checkin, classes, pt, transactions, admin)
"""
import sys
import os
import argparse
from datetime import datetime

# Add tests directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import Colors, print_header


def run_tests(args):
    """Run all test suites"""
    start_time = datetime.now()

    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  MOOLAI GYM API - COMPLETE TEST SUITE")
    print("=" * 70)
    print(f"{Colors.END}")
    print(f"  Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version.split()[0]}")
    print()

    all_results = []
    test_modules = []

    # Determine which tests to run
    if args.only:
        test_map = {
            "auth": ("test_01_auth", "Authentication"),
            "membership": ("test_02_membership", "Membership"),
            "checkin": ("test_03_checkin", "Check-in"),
            "classes": ("test_04_classes", "Classes"),
            "pt": ("test_05_pt", "Personal Training"),
            "transactions": ("test_06_transactions", "Transactions"),
            "admin": ("test_07_admin", "Admin"),
        }
        if args.only in test_map:
            test_modules.append(test_map[args.only])
        else:
            print(f"{Colors.RED}Unknown test: {args.only}{Colors.END}")
            return False
    else:
        if not args.skip_auth:
            test_modules.append(("test_01_auth", "Authentication"))
        if not args.skip_membership:
            test_modules.append(("test_02_membership", "Membership"))
        if not args.skip_checkin:
            test_modules.append(("test_03_checkin", "Check-in"))
        if not args.skip_classes:
            test_modules.append(("test_04_classes", "Classes"))
        if not args.skip_pt:
            test_modules.append(("test_05_pt", "Personal Training"))
        if not args.skip_transactions:
            test_modules.append(("test_06_transactions", "Transactions"))
        if not args.skip_admin:
            test_modules.append(("test_07_admin", "Admin"))

    if not test_modules:
        print(f"{Colors.YELLOW}No tests to run!{Colors.END}")
        return True

    # Run each test module
    for module_name, display_name in test_modules:
        try:
            module = __import__(module_name)
            run_func_name = f"run_{module_name.replace('test_0', '').split('_')[0]}_{module_name.split('_', 2)[2]}_tests"
            # Dynamic function name mapping
            func_map = {
                "test_01_auth": "run_auth_tests",
                "test_02_membership": "run_membership_tests",
                "test_03_checkin": "run_checkin_tests",
                "test_04_classes": "run_class_tests",
                "test_05_pt": "run_pt_tests",
                "test_06_transactions": "run_transaction_tests",
                "test_07_admin": "run_admin_tests",
            }
            run_func = getattr(module, func_map[module_name])
            result = run_func()
            all_results.append((display_name, result))
        except Exception as e:
            print(f"\n{Colors.RED}Error running {display_name} tests: {str(e)}{Colors.END}")
            import traceback
            traceback.print_exc()

    # Calculate totals
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    total_passed = sum(r.passed for _, r in all_results)
    total_failed = sum(r.failed for _, r in all_results)
    total_skipped = sum(r.skipped for _, r in all_results)
    total_tests = total_passed + total_failed + total_skipped

    # Print final summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  FINAL TEST SUMMARY")
    print("=" * 70)
    print(f"{Colors.END}")

    print(f"\n  {'Test Suite':<25} {'Passed':<10} {'Failed':<10} {'Skipped':<10}")
    print(f"  {'-'*55}")
    for name, result in all_results:
        passed_color = Colors.GREEN if result.passed > 0 else ""
        failed_color = Colors.RED if result.failed > 0 else ""
        skipped_color = Colors.YELLOW if result.skipped > 0 else ""
        print(f"  {name:<25} {passed_color}{result.passed:<10}{Colors.END} {failed_color}{result.failed:<10}{Colors.END} {skipped_color}{result.skipped:<10}{Colors.END}")

    print(f"  {'-'*55}")
    print(f"  {'TOTAL':<25} {Colors.GREEN}{total_passed:<10}{Colors.END} {Colors.RED}{total_failed:<10}{Colors.END} {Colors.YELLOW}{total_skipped:<10}{Colors.END}")

    print(f"\n  Duration: {duration:.2f} seconds")
    print(f"  Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

    if total_failed == 0:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.END}\n")
    else:
        print(f"\n  {Colors.RED}{Colors.BOLD}✗ {total_failed} TEST(S) FAILED{Colors.END}\n")

    return total_failed == 0


def main():
    parser = argparse.ArgumentParser(description="Moolai Gym API Test Suite")
    parser.add_argument("--skip-auth", action="store_true", help="Skip authentication tests")
    parser.add_argument("--skip-membership", action="store_true", help="Skip membership tests")
    parser.add_argument("--skip-checkin", action="store_true", help="Skip check-in tests")
    parser.add_argument("--skip-classes", action="store_true", help="Skip class booking tests")
    parser.add_argument("--skip-pt", action="store_true", help="Skip PT tests")
    parser.add_argument("--skip-transactions", action="store_true", help="Skip transaction tests")
    parser.add_argument("--skip-admin", action="store_true", help="Skip admin tests")
    parser.add_argument("--only", type=str, help="Run only specified test suite")

    args = parser.parse_args()

    success = run_tests(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
