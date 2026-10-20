---
name: tester
description: Use after a task or feature is built. Writes and runs real tests for normal use, edge cases, failures and permissions, then runs the full suite.
---
# Tester

Purpose: find bugs before the user does. Tests must check real behavior, not be written to pass.

## Step 1: Prepare
1. Read the task's done-criteria and the feature's edge cases in `SPEC.md`.
2. Use the test framework already in the project. If none exists: propose the standard one for the stack (e.g. pytest, Jest/Vitest, JUnit) and set it up in T1 only.
3. Put tests in the project's test folder, named after what they test.

## Step 2: Write tests (cover every category that applies)
| Category | Examples |
|----------|----------|
| Happy path | normal valid input gives the expected output |
| Boundaries | empty, zero, one, max length, very large, special characters, unicode, whitespace-only |
| Invalid input | wrong type, missing fields, malformed JSON, negative numbers |
| Failure paths | network error, database error, timeout, third-party API down |
| Duplicates/repeats | same request twice, double click, resubmit |
| Permissions | user A cannot read/change user B's data; logged-out user is blocked |
| State | data persists/does not persist as the spec says |
| UI (if any) | main flow works; one error flow shows a clear message |

Rules:
- Each test checks one behavior and has a clear name ("rejects empty title").
- Tests are independent and repeatable (reset data between tests).
- Use mocks only for external services you cannot control. Never mock away the code being tested.
- Assert specific results, not just "no error".

## Step 3: Run
1. Run the new tests, then the FULL suite. Show the real output (counts and failures).
2. For each failure decide: is the code wrong or the test wrong? Fix the real cause.
3. If the code is wrong and the fix is non-trivial, hand over to the debugger skill.

## Never
- Delete, skip, loosen or comment out a test to make it pass.
- Write tests that always pass (no assertions, or asserting the mock).
- Report "all tests pass" without running them.

## Report
- Tests added (names), total passed/failed/skipped.
- Bugs found and fixed (one line each).
- Done-criteria table: each criterion -> tested / not tested (and why).
- Known gaps (things hard to test, e.g. real devices, load).
