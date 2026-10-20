# COMPASS Assurance — Known Limitations

## What This System Tests

- ✅ Python source code security (Bandit SAST)
- ✅ Python dependency vulnerabilities (pip-audit)
- ✅ Node dependency vulnerabilities (npm audit)
- ✅ Secret/credential leakage in source and artifacts
- ✅ API input validation and boundary testing
- ✅ SQL injection, XSS, path traversal, command injection payloads
- ✅ Full multi-phase pytest regression (591+ tests)
- ✅ Phase 13 adversarial fault injection (35 attacks)
- ✅ Real Windows 11 desktop automation workflows (24 workflows)
- ✅ Memory stability and leak detection (25 cycles)
- ✅ Performance benchmark comparison (baseline vs optimized)
- ✅ Emergency STOP preemption latency
- ✅ AI/planner prompt injection defense
- ✅ State machine integrity and concurrency safety
- ✅ Release readiness gate evaluation

## What This System Does NOT Test

- ❌ **Full DAST web scanning** (OWASP ZAP): Not installed due to Java dependency and resource constraints. COMPASS API binds to localhost only, reducing the attack surface.
- ❌ **Git history secret scanning**: Current scanner covers active codebase only. Git history scanning (gitleaks) is a future enhancement.
- ❌ **Coverage-guided fuzzing** (Atheris): Requires compiled instrumentation; not currently integrated.
- ❌ **JavaScript/React static analysis**: ESLint security rules are not currently run. The frontend is a simple React SPA with no authentication or sensitive data handling.
- ❌ **Browser-based runtime testing** (Playwright): Not installed due to resource constraints. Frontend has no complex client-side security logic.
- ❌ **Network penetration testing**: COMPASS binds to 127.0.0.1 only — no external network exposure.
- ❌ **Production deployment security**: COMPASS is a desktop application, not a cloud service. No cloud infrastructure security testing applies.
- ❌ **Multi-user authorization testing**: COMPASS is single-user desktop software. No multi-tenant authorization model exists.
- ❌ **Mobile or cross-platform testing**: COMPASS is Windows 11 only.
- ❌ **Hardware fault injection**: Real hardware failures (disk corruption, power loss) are not simulated.

## Honest Coverage Statement

> The application has undergone the documented automated, runtime, adversarial, security, performance, and regression testing within the tested and supported scope. Confirmed findings have been addressed or explicitly dispositioned, fixes have been retested and re-attacked where applicable, and remaining limitations and untested areas are documented above.
