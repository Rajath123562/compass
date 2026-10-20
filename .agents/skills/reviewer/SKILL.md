---
name: reviewer
description: Use before release or deployment. Reviews the whole project for security, errors, setup, performance and spec compliance, then reports issues by severity.
---
# Reviewer

Purpose: find everything that would break, leak, or embarrass this project in production. Report first; fix only after approval (autonomous mode: fix High and Medium, then re-test).

## Method
1. Read SPEC.md, TASKS.md, README.md. List the project's files and dependencies.
2. For each area below, actually inspect the code or run the command. Mark PASS / FAIL / N/A with evidence (file and line, or command output).
3. Search the code for risky patterns (secrets, `eval`, string-built SQL, `innerHTML`, `console.log`, `TODO`, `debug=True`).

## Areas
1. Secrets: hardcoded keys/passwords/tokens; `.env` or credentials in git (`git log -p` search); `.gitignore` correct; `.env.example` complete.
2. Authentication: passwords hashed (bcrypt/argon2), session or token expiry, logout works, brute-force limits, secure cookie flags.
3. Authorization: every read/write by ID checks ownership; admin-only routes protected; test as a different user.
4. Input safety: validation on every input; parameterized queries; output escaping (XSS); CSRF protection if cookie auth; file upload type/size limits; no path traversal; no `eval` or shell with user input.
5. Errors: no unhandled exceptions; no empty catch blocks; user-friendly messages; no stack traces shown to users; loading, empty and error states exist.
6. Data: migrations run from scratch; indexes on filtered fields; pagination on lists; no N+1 queries; backups noted.
7. Dependencies: run the audit command (`npm audit`, `pip-audit`, etc.); remove unused packages; versions pinned.
8. Setup: clean clone -> install -> run -> test works from README only; every env variable documented.
9. Production config: debug off, CORS restricted, HTTPS, rate limiting, logging without sensitive data, health check.
10. Quality: no dead code, leftover TODOs, console logs, fake data, skipped tests; build succeeds.
11. UI (if any): works at 360px width, keyboard usable, labels and alt text, readable contrast.
12. Spec compliance: every SPEC.md feature and done-criterion actually met, with proof.

## Output format
For each issue:
`[HIGH|MEDIUM|LOW] <title> | <file:line> | <what is wrong> | <why it matters> | <fix>`
Then a summary table (area -> PASS/FAIL), the count of issues per severity, and a GO / NO-GO recommendation (NO-GO if any High issue is open).

## Rules
- No false assurance: say "not verified" for anything you could not check.
- After fixes, re-run the full test suite and the failed checks, and show results.
