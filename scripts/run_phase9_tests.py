import subprocess
import sys


def run_tests():
    print("==================================================")
    print("COMPASS Phase 9 - Reliability & Self-Repair Tests")
    print("==================================================")
    print("\nRunning legacy regressions & Phase 9 isolated tests...")

    # We must ensure there are 0 regressions across all planner tests and reliability tests
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "planner/tests",
        "backend/tests/test_reliability_api.py",
        "backend/tests/test_reliability_sse.py",
        "-v",
    ]

    result = subprocess.run(cmd)  # noqa: PLW1510

    if result.returncode == 0:
        print("\n==================================================")
        print("PHASE 9 VALIDATION PASSED: ZERO REGRESSIONS")
        print("Reliability shell is active.")
        print("==================================================")
        sys.exit(0)
    else:
        print("\n==================================================")
        print("PHASE 9 VALIDATION FAILED: REGRESSIONS DETECTED")
        print("==================================================")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
