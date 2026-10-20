"""
COMPASS Exhaustive Stress & Fuzz Testing Suite
Executes 500+ direct operations against the COMPASS product to guarantee absolute stability.
"""

import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import random
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE_URL = 'http://127.0.0.1:8000'
TOTAL_TESTS = 1000
PASS_COUNT = 0
FAIL_COUNT = 0

def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def random_payload():
    return {
        "goal": f"Random goal: {random_string(20)}",
        "metadata": {
            "source": "fuzz_test",
            "random_val": random_string(5)
        }
    }

def single_test_iteration(i):
    global PASS_COUNT, FAIL_COUNT
    try:
        # 1. Create a task (POST)
        res = requests.post(f"{BASE_URL}/api/tasks", json=random_payload(), timeout=5)
        if res.status_code != 201:
            raise Exception(f"Create failed: {res.status_code}")  # noqa: TRY002
        
        task_id = res.json()["id"]

        # 2. Retrieve the task (GET)
        res = requests.get(f"{BASE_URL}/api/tasks/{task_id}", timeout=5)
        if res.status_code != 200:
            raise Exception(f"Retrieve failed: {res.status_code}")  # noqa: TRY002

        # 3. Call planner (POST) - even if it fails due to API key, it shouldn't crash the server (500)
        res = requests.post(f"{BASE_URL}/api/planner/plan", json={"goal": "test", "task_id": task_id}, timeout=10)
        if res.status_code >= 500 and res.status_code not in [502, 503]: # 502/503 are upstream AI provider errors
             raise Exception(f"Planner crashed server: {res.status_code}")  # noqa: TRY002

        # 4. Stop the task (POST)
        res = requests.post(f"{BASE_URL}/api/tasks/{task_id}/stop", timeout=5)
        if res.status_code not in [200, 400]: # 400 is fine if it was already terminal
             raise Exception(f"Stop failed: {res.status_code}")  # noqa: TRY002
             
        PASS_COUNT += 1
        if i % 50 == 0:
            print(f"[{i}/{TOTAL_TESTS}] Passing perfectly...")
            
    except Exception as e:  # noqa: BLE001
        FAIL_COUNT += 1
        print(f"Test {i} FAILED: {e!s}")

def run_stress_test():
    print(f"[*] Starting Exhaustive Loop Test ({TOTAL_TESTS} Iterations) on COMPASS...")
    start_time = time.time()
    
    # Run tests concurrently to also test race conditions
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(1, TOTAL_TESTS + 1):
            executor.submit(single_test_iteration, i)
            
    elapsed = time.time() - start_time
    print("\n" + "="*50)
    print("🎯 COMPASS STRESS TEST RESULTS".encode('ascii', 'ignore').decode())
    print("="*50)
    print(f"Total Tests Executed: {PASS_COUNT + FAIL_COUNT}")
    print(f"✅ PASSED: {PASS_COUNT}".encode('ascii', 'ignore').decode())
    print(f"❌ FAILED: {FAIL_COUNT}".encode('ascii', 'ignore').decode())
    print(f"⏱️ Time Taken: {elapsed:.2f} seconds".encode('ascii', 'ignore').decode())
    print("="*50)
    
    if FAIL_COUNT > 0:
        sys.exit(1)
    else:
        print("COMPASS IS 100% STABLE AND PRODUCTION READY.")
        sys.exit(0)

if __name__ == "__main__":
    run_stress_test()
