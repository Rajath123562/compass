# COMPASS Assurance — Tool Inventory & Evaluation

## Tool Evaluation Matrix

Every candidate tool is recorded with purpose, license, resource requirements, and integration status.

| Tool | Category | Version | License | Status | Purpose | Notes |
|------|----------|---------|---------|--------|---------|-------|
| **Bandit** | Python SAST | 1.7+ | Apache-2.0 | **USED** | Python security linting (dangerous calls, injection, deserialization) | Installed into .venv via pip |
| **pip-audit** | Python SCA | 2.6+ | Apache-2.0 | **USED** | Python dependency vulnerability scanning against OSV database | Installed into .venv via pip |
| **npm audit** | Node SCA | Bundled with npm | MIT | **USED** | Node.js dependency vulnerability scanning | Pre-installed with Node.js |
| **Custom Secret Scanner** | Secret Detection | Internal | N/A | **USED** | Pattern-based secret detection across source, configs, artifacts | Custom implementation in assurance/tools/secret_scanner.py |
| **Phase 14 Secrets Audit** | Secret Detection | Internal | N/A | **USED** | Legacy audit_security_secrets.py from Phase 14 | Scans 400+ files for credential patterns |
| **Custom API Fuzzer** | API Security | Internal | N/A | **USED** | Malformed JSON, boundary inputs, injection payloads against live API | Custom implementation in assurance/tools/api_security_tester.py |
| **Pytest** | Test Framework | 8.3.3 | MIT | **USED** | 591+ multi-phase regression tests, adversarial tests | Pre-installed in .venv |
| **Phase 12 Windows Tests** | Real Windows | Internal | N/A | **USED** | 24 real desktop workflows against Notepad, Calculator, etc. | Uses Win32/UIA live interaction |
| **Phase 13 Adversarial** | Adversarial QA | Internal | N/A | **USED** | 20 live fault-injection attacks + 15 targeted pytest attacks | Prompt injection, STOP race, state corruption |
| **Phase 14 Benchmark** | Performance | Internal | N/A | **USED** | Latency, memory, throughput, STOP preemption measurement | Before/after comparison with JSON evidence |
| **psutil** | Resource Monitor | 5.9.8 | BSD-3 | **USED** | Process RSS, CPU, thread, handle telemetry | Pre-installed in .venv |
| **Semgrep** | Multi-Language SAST | N/A | LGPL-2.1 | **REVIEWED — NOT USED** | Advanced pattern-based code analysis | Heavy resource requirements; Bandit covers Python adequately |
| **OWASP ZAP** | DAST Web Scanner | N/A | Apache-2.0 | **REVIEWED — NOT USED** | Full DAST proxy scanning | Requires Java runtime, 500MB+ RAM; COMPASS API is localhost-only |
| **Schemathesis** | OpenAPI Fuzzer | N/A | MIT | **REVIEWED — NOT USED** | Schema-driven API property testing | Custom API fuzzer covers critical paths; available for future use |
| **Gitleaks** | Git Secret Scanner | N/A | MIT | **REVIEWED — NOT USED** | Git history secret scanning | Custom scanner covers current codebase; history scanning is a future enhancement |
| **Nuclei** | Vulnerability Templates | N/A | MIT | **NOT APPLICABLE** | Template-based scanning against web targets | COMPASS is a desktop automation app, not a web service |
| **HackAgent** | AI Red Team | N/A | Varies | **REVIEWED — NOT USED** | AI agent security testing framework | Experimental; COMPASS has its own Phase 13 AI red-team suite |
| **Playwright** | Browser Automation | N/A | Apache-2.0 | **BLOCKED — RESOURCE CONSTRAINT** | Headless browser testing | 200MB+ download; COMPASS frontend is a simple React SPA |
| **Atheris** | Python Fuzzer | N/A | Apache-2.0 | **REVIEWED — NOT USED** | Coverage-guided Python fuzzing | Requires compiled instrumentation; future enhancement candidate |
| **Ponytail** | AI Optimization | N/A | Unknown | **UNAVAILABLE** | AI-assisted code optimization | Binary not available in any package registry |

## Integration Policy

1. Tools are installed only when they provide coverage not already achieved by existing tools.
2. Resource constraints (12GB RAM, single laptop) limit concurrent heavy tool execution.
3. Every tool's findings are normalized into the central Finding Registry schema.
4. No tool's output is automatically trusted — findings require reproduction where possible.
