"""
Test Utilities for Moolai Gym API
"""
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from config import BASE_URL

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_test(name: str, passed: bool, message: str = ""):
    """Print test result"""
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"  {status} - {name}")
    if message and not passed:
        print(f"       {Colors.YELLOW}{message}{Colors.END}")


def print_info(message: str):
    """Print info message"""
    print(f"  {Colors.BLUE}ℹ {message}{Colors.END}")


def print_warning(message: str):
    """Print warning message"""
    print(f"  {Colors.YELLOW}⚠ {message}{Colors.END}")


class APIClient:
    """HTTP Client for API testing"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None

    def set_token(self, token: str):
        """Set authorization token"""
        self.token = token

    def clear_token(self):
        """Clear authorization token"""
        self.token = None

    def _headers(self, extra_headers: Dict = None) -> Dict:
        """Build request headers"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def get(self, endpoint: str, params: Dict = None) -> requests.Response:
        """GET request"""
        url = f"{self.base_url}{endpoint}"
        return requests.get(url, params=params, headers=self._headers())

    def post(self, endpoint: str, data: Dict = None) -> requests.Response:
        """POST request"""
        url = f"{self.base_url}{endpoint}"
        return requests.post(url, json=data, headers=self._headers())

    def put(self, endpoint: str, data: Dict = None) -> requests.Response:
        """PUT request"""
        url = f"{self.base_url}{endpoint}"
        return requests.put(url, json=data, headers=self._headers())

    def patch(self, endpoint: str, data: Dict = None) -> requests.Response:
        """PATCH request"""
        url = f"{self.base_url}{endpoint}"
        return requests.patch(url, json=data, headers=self._headers())

    def delete(self, endpoint: str) -> requests.Response:
        """DELETE request"""
        url = f"{self.base_url}{endpoint}"
        return requests.delete(url, headers=self._headers())


class TestResult:
    """Track test results"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []

    def add_pass(self, name: str):
        self.passed += 1
        self.results.append({"name": name, "status": "pass"})
        print_test(name, True)

    def add_fail(self, name: str, message: str = ""):
        self.failed += 1
        self.results.append({"name": name, "status": "fail", "message": message})
        print_test(name, False, message)

    def add_skip(self, name: str, reason: str = ""):
        self.skipped += 1
        self.results.append({"name": name, "status": "skip", "reason": reason})
        print(f"  {Colors.YELLOW}⊘ SKIP{Colors.END} - {name}")
        if reason:
            print(f"       {Colors.YELLOW}{reason}{Colors.END}")

    def summary(self):
        """Print test summary"""
        total = self.passed + self.failed + self.skipped
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}  TEST SUMMARY{Colors.END}")
        print(f"{'='*60}")
        print(f"  Total:   {total}")
        print(f"  {Colors.GREEN}Passed:  {self.passed}{Colors.END}")
        print(f"  {Colors.RED}Failed:  {self.failed}{Colors.END}")
        print(f"  {Colors.YELLOW}Skipped: {self.skipped}{Colors.END}")
        print(f"{'='*60}\n")

        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}All tests passed! ✓{Colors.END}\n")
        else:
            print(f"{Colors.RED}{Colors.BOLD}Some tests failed! ✗{Colors.END}\n")

        return self.failed == 0


def assert_status(response: requests.Response, expected: int, result: TestResult, test_name: str) -> bool:
    """Assert response status code"""
    if response.status_code == expected:
        result.add_pass(test_name)
        return True
    else:
        result.add_fail(test_name, f"Expected {expected}, got {response.status_code}: {response.text[:200]}")
        return False


def assert_json_key(response: requests.Response, key: str, result: TestResult, test_name: str) -> Any:
    """Assert response has JSON key and return its value"""
    try:
        data = response.json()
        if key in data:
            result.add_pass(test_name)
            return data[key]
        else:
            result.add_fail(test_name, f"Key '{key}' not found in response")
            return None
    except Exception as e:
        result.add_fail(test_name, f"Invalid JSON response: {str(e)}")
        return None
