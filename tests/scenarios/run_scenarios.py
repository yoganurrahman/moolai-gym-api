#!/usr/bin/env python3
"""
Run all test scenarios
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Colors
from datetime import datetime

def main():
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  MOOLAI GYM API - SCENARIO TESTS")
    print("=" * 70)
    print(f"{Colors.END}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_results = []

    # Run New Member Journey
    try:
        from scenario_new_member import run_scenario as run_new_member
        print(f"\n{Colors.YELLOW}Running: New Member Journey...{Colors.END}")
        result = run_new_member()
        all_results.append(("New Member Journey", result))
    except Exception as e:
        print(f"{Colors.RED}Error in New Member scenario: {e}{Colors.END}")

    # Run Daily Operations
    try:
        from scenario_daily_ops import run_scenario as run_daily_ops
        print(f"\n{Colors.YELLOW}Running: Daily Operations...{Colors.END}")
        result = run_daily_ops()
        all_results.append(("Daily Operations", result))
    except Exception as e:
        print(f"{Colors.RED}Error in Daily Operations scenario: {e}{Colors.END}")

    # Final Summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("=" * 70)
    print("  ALL SCENARIOS COMPLETE")
    print("=" * 70)
    print(f"{Colors.END}")

    total_passed = sum(r.passed for _, r in all_results)
    total_failed = sum(r.failed for _, r in all_results)
    total_skipped = sum(r.skipped for _, r in all_results)

    print(f"\n  {'Scenario':<30} {'Passed':<10} {'Failed':<10} {'Skipped':<10}")
    print(f"  {'-'*60}")
    for name, result in all_results:
        print(f"  {name:<30} {Colors.GREEN}{result.passed:<10}{Colors.END} {Colors.RED}{result.failed:<10}{Colors.END} {Colors.YELLOW}{result.skipped:<10}{Colors.END}")
    print(f"  {'-'*60}")
    print(f"  {'TOTAL':<30} {Colors.GREEN}{total_passed:<10}{Colors.END} {Colors.RED}{total_failed:<10}{Colors.END} {Colors.YELLOW}{total_skipped:<10}{Colors.END}")

    if total_failed == 0:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}✓ ALL SCENARIOS PASSED!{Colors.END}\n")
    else:
        print(f"\n  {Colors.RED}{Colors.BOLD}✗ {total_failed} TEST(S) FAILED{Colors.END}\n")

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
