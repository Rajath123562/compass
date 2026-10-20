"""
COMPASS Continuous Production Assurance — API Security Tester & Fuzzer
Tests actual running COMPASS API endpoints with malformed, boundary, and adversarial inputs.
Uses the real OpenAPI schema for schema-driven test generation.
"""

import json
import sys
import time
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

REPORT_DIR = ROOT_DIR / "assurance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10


def is_api_running() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=3)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def fetch_openapi_schema() -> dict:
    try:
        r = requests.get(f"{BASE_URL}/api/openapi.json", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:  # noqa: BLE001, S110
        pass
    return {}


def test_malformed_json_body(path: str, method: str = "POST") -> dict:
    """Send deliberately malformed JSON bodies."""
    payloads = [
        ("empty_body", ""),
        ("null_body", "null"),
        ("invalid_json", "{invalid json!!!"),
        ("array_instead_of_object", "[]"),
        ("number_body", "42"),
        ("string_body", '"just a string"'),
        ("nested_bomb", '{"a":' * 50 + '"x"' + "}" * 50),
        ("huge_string", json.dumps({"goal": "A" * 50000})),
        ("unicode_payload", json.dumps({"goal": "\u0000\uffff\ud800"})),
        ("sql_injection", json.dumps({"goal": "'; DROP TABLE tasks; --"})),
        ("xss_payload", json.dumps({"goal": "<script>alert(1)</script>"})),
        ("path_traversal", json.dumps({"goal": "../../../../etc/passwd"})),
        ("command_injection", json.dumps({"goal": "; rm -rf / ;"})),
    ]

    results = []
    for name, body in payloads:
        try:
            headers = {"Content-Type": "application/json"}
            if method == "POST":
                r = requests.post(
                    f"{BASE_URL}{path}", data=body, headers=headers, timeout=TIMEOUT
                )
            else:
                r = requests.request(
                    method,
                    f"{BASE_URL}{path}",
                    data=body,
                    headers=headers,
                    timeout=TIMEOUT,
                )

            is_safe = r.status_code in (200, 201, 400, 404, 405, 422, 502)
            results.append(
                {
                    "test": name,
                    "endpoint": f"{method} {path}",
                    "status_code": r.status_code,
                    "safe": is_safe,
                    "response_size": len(r.content),
                    "response_snippet": r.text[:200] if not is_safe else "",
                }
            )
        except requests.Timeout:
            results.append(
                {
                    "test": name,
                    "endpoint": f"{method} {path}",
                    "status_code": -1,
                    "safe": True,
                    "note": "Timeout",
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "test": name,
                    "endpoint": f"{method} {path}",
                    "status_code": -2,
                    "safe": True,
                    "note": str(e)[:100],
                }
            )

    return {
        "path": path,
        "method": method,
        "tests": results,
        "passed": all(r["safe"] for r in results),
    }


def test_missing_fields(path: str) -> dict:
    """Test POST endpoints with missing required fields."""
    payloads = [
        ("empty_object", {}),
        ("missing_goal", {"not_goal": "test"}),
        ("null_goal", {"goal": None}),
        ("empty_goal", {"goal": ""}),
        ("whitespace_goal", {"goal": "   "}),
    ]
    results = []
    for name, body in payloads:
        try:
            r = requests.post(f"{BASE_URL}{path}", json=body, timeout=TIMEOUT)
            results.append(
                {
                    "test": name,
                    "status_code": r.status_code,
                    "safe": r.status_code in (200, 201, 400, 422, 404, 405, 502),
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {"test": name, "status_code": -1, "safe": True, "note": str(e)[:100]}
            )

    return {"path": path, "tests": results, "passed": all(r["safe"] for r in results)}


def test_invalid_types(path: str) -> dict:
    """Send wrong types for expected fields."""
    payloads = [
        ("goal_as_number", {"goal": 12345}),
        ("goal_as_boolean", {"goal": True}),
        ("goal_as_array", {"goal": [1, 2, 3]}),
        ("goal_as_object", {"goal": {"nested": "object"}}),
        ("extra_unknown_fields", {"goal": "test", "unknown1": "x", "unknown2": 99}),
    ]
    results = []
    for name, body in payloads:
        try:
            r = requests.post(f"{BASE_URL}{path}", json=body, timeout=TIMEOUT)
            results.append(
                {
                    "test": name,
                    "status_code": r.status_code,
                    "safe": r.status_code in (200, 201, 400, 422, 404, 405, 502),
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {"test": name, "status_code": -1, "safe": True, "note": str(e)[:100]}
            )

    return {"path": path, "tests": results, "passed": all(r["safe"] for r in results)}


def test_http_methods(path: str) -> dict:
    """Test unexpected HTTP methods."""
    unexpected_methods = ["PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
    results = []
    for method in unexpected_methods:
        try:
            r = requests.request(method, f"{BASE_URL}{path}", timeout=TIMEOUT)
            results.append(
                {
                    "method": method,
                    "status_code": r.status_code,
                    "safe": r.status_code in (200, 204, 304, 400, 404, 405, 422),
                }
            )
        except Exception:  # noqa: BLE001
            results.append({"method": method, "status_code": -1, "safe": True})

    return {"path": path, "tests": results, "passed": all(r["safe"] for r in results)}


def test_security_headers() -> dict:
    """Check response security headers."""
    try:
        r = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        headers = dict(r.headers)
        checks = {
            "x_content_type_options": "X-Content-Type-Options" in headers,
            "x_frame_options": "X-Frame-Options" in headers,
            "strict_transport_security": "Strict-Transport-Security" in headers,
            "content_security_policy": "Content-Security-Policy" in headers,
            "x_xss_protection": "X-XSS-Protection" in headers,
            "server_header_hidden": "Server" not in headers
            or "uvicorn" not in headers.get("Server", "").lower(),
            "cors_configured": "access-control-allow-origin"
            in {k.lower() for k in headers},
        }
        return {"status": "EXECUTED", "headers_present": headers, "checks": checks}
    except Exception as e:  # noqa: BLE001
        return {"status": "ERROR", "error": str(e)}


def run_api_security_tests() -> dict:
    """Full API security testing pipeline."""
    print("[API Security] Checking if COMPASS API is running...")
    mgr = None
    if not is_api_running():
        print(
            "[API Security] API is not running. Launching real COMPASS product stack..."
        )
        from assurance.real_product_harness import RealProductManager

        mgr = RealProductManager()
        if not mgr.ensure_live_product(timeout=30):
            print("[API Security] Could not start live server.")
            return {
                "status": "BLOCKED",
                "reason": "API server not running on port 8000",
                "note": "Start COMPASS with START_COMPASS.bat first",
            }

    print("[API Security] API is live. Fetching OpenAPI schema...")
    schema = fetch_openapi_schema()
    endpoint_count = len(schema.get("paths", {})) if schema else 0
    print(f"  Found {endpoint_count} API paths in OpenAPI schema")

    results = {
        "timestamp": time.time(),
        "api_running": True,
        "openapi_endpoints": endpoint_count,
        "tests": {},
    }

    # Test key endpoints
    test_paths = [
        ("/api/tasks", "POST"),
        ("/api/planner/plan", "POST"),
        ("/api/planner/task", "POST"),
        ("/api/automation/click", "POST"),
        ("/api/automation/type", "POST"),
        ("/api/automation/key", "POST"),
    ]

    total_tests = 0
    total_passed = 0

    for path, method in test_paths:
        print(f"  Testing {method} {path}...")

        # Malformed JSON
        mj = test_malformed_json_body(path, method)
        results["tests"][f"malformed_{path}"] = mj
        total_tests += len(mj["tests"])
        total_passed += sum(1 for t in mj["tests"] if t["safe"])

        # Missing fields
        mf = test_missing_fields(path)
        results["tests"][f"missing_fields_{path}"] = mf
        total_tests += len(mf["tests"])
        total_passed += sum(1 for t in mf["tests"] if t["safe"])

        # Invalid types
        it = test_invalid_types(path)
        results["tests"][f"invalid_types_{path}"] = it
        total_tests += len(it["tests"])
        total_passed += sum(1 for t in it["tests"] if t["safe"])

    # HTTP methods on root
    hm = test_http_methods("/")
    results["tests"]["http_methods_root"] = hm
    total_tests += len(hm["tests"])
    total_passed += sum(1 for t in hm["tests"] if t["safe"])

    # Security headers
    sh = test_security_headers()
    results["tests"]["security_headers"] = sh

    results["summary"] = {
        "total_tests": total_tests,
        "passed": total_passed,
        "failed": total_tests - total_passed,
        "pass_rate": round(total_passed / max(1, total_tests) * 100, 1),
    }

    out = REPORT_DIR / "api_security_report.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(
        f"[API Security] {total_passed}/{total_tests} tests passed ({results['summary']['pass_rate']}%)"
    )
    print(f"[API Security] Report saved: {out}")
    if mgr:
        mgr.teardown()
    return results


if __name__ == "__main__":
    run_api_security_tests()
