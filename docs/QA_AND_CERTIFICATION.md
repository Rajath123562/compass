# COMPASS — QA & Certification Specification

## 1. Principles of Release Certification

COMPASS employs a strict, fail-closed release certification architecture. A release candidate can be certified only when every mandatory assurance gate yields fresh, schema-valid `PASS` evidence tied to the tested source tree hash.

Under no circumstances may an `UNVERIFIED`, `BLOCKED`, `NOT RUN`, or `FAIL` status be synthesized into release readiness.

---

## 2. Mandatory Release Gate Matrix

Release readiness is evaluated by `assurance/tools/release_gate.py` across 8 mandatory gates:

| Gate | Scope | Required Evidence Artifact | Pass Criteria |
|------|-------|----------------------------|---------------|
| **Functional** | Core task execution & planning | `artifacts/phase14/phase14_master_report.json` | `overall_status == "PASS"`, all mandatory stages green |
| **Security** | Vulnerability register | `assurance/findings/finding_register.json` | 0 open CRITICAL, 0 open HIGH findings |
| **SAST** | Static code analysis | `assurance/reports/sast_report.json` | Bandit executed, 0 high/critical issues |
| **Dependency** | Python & Node dependencies | `assurance/reports/dependency_report.json` | 0 pip-audit vulnerabilities, 0 npm critical/high vulnerabilities |
| **Secret Scan** | Credential hygiene | `assurance/reports/secret_scan_report.json` | 0 leaked secrets across source, config, dotfiles, and assurance |
| **API Security** | Fuzz & boundary testing | `assurance/reports/api_security_report.json` | All attack scenarios defended safely, status != BLOCKED |
| **Performance** | Latency & resource SLOs | `artifacts/phase14/benchmark_comparison.json` | All latency metrics within justified SLO thresholds |
| **Real Product** | Assembled product E2E | `assurance/reports/real_product_test_report.json` | Real backend + frontend + OS tests passed with zero failures |

---

## 3. Justified Performance SLOs

All benchmarks are measured against defensible operational limits:

* **Planning Latency:** `<= 2000.0 ms` (cached local planner `<= 500.0 ms`)
* **Emergency STOP Preemption:** `<= 500.0 ms`
* **Database Operation:** `<= 100.0 ms`
* **UI Action Dispatch:** `<= 250.0 ms`
* **Single Step E2E Turnaround:** `<= 1000.0 ms`

---

## 4. Certification Run Execution

To evaluate the production release gate:

```bash
# Execute master assurance runner
python assurance/compass_assure.py --full

# Evaluate release readiness gate directly
python assurance/tools/release_gate.py
```

The evaluator exits with code `0` on confirmed `PASS` and code `1` on any failing or blocked mandatory gate.
