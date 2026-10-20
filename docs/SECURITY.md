# COMPASS — Security & Trust Boundary Architecture

## 1. Trust Boundaries

COMPASS operates as a high-authority desktop automation system. It defines four primary trust boundaries:

1. **Browser-to-Localhost Trust Boundary:**
   - The FastAPI backend listens on `127.0.0.1:8000`.
   - Wildcard CORS (`*`) with credentials is prohibited.
   - CORS is restricted to explicit allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`, and configured ports.
   - The `validate_browser_origin` middleware intercepts requests carrying an external `Origin` header and immediately rejects untrusted web domains with `403 Forbidden`.

2. **AI-to-Execution Trust Boundary:**
   - Model proposals are treated as untrusted input.
   - `PlanValidator` exhaustively verifies every `PlannerActionType` against strict schemas, parameter bounds, and forbidden injection keywords (`cmd`, `shell`, `exec`, `powershell`, etc.).
   - Actions with consequential impact (deletion, purchase, file truncation, system modifications) are forced to `RiskLevel.HIGH` or `CONSEQUENTIAL`, requiring explicit human approval.

3. **Perception-to-Action Trust Boundary:**
   - Prior to mouse or keyboard dispatch, `StaleGuard` verifies that the target window HWND is alive, not minimized, in foreground focus, and has not drifted in screen space.
   - Coordinates are validated against virtual desktop half-open screen space `[vx, vx + vw)` and `[vy, vy + vh)`.

4. **Credential Hygiene & Secret Redaction:**
   - Secret scanner continuously audits all source code, config files, assurance tools, and `.env` files.
   - Observability traces and logs deterministically redact API keys, bearer tokens, passwords, and PII before disk serialization.

---

## 2. Vulnerability Management & Finding Registry

Findings are tracked in `assurance/findings/finding_register.json` using the atomic, thread-safe `FindingRegistry`:

* **Finding Lifecycle:** `OPEN` -> `IN_PROGRESS` -> `FIXED` -> `RETESTED` -> `CLOSED`
* **Closure Rule:** No finding may enter `CLOSED` without a permanent linked regression test (`regression_test_id`) and verified re-test evidence (`verification_status == "VERIFIED"`).
* **Corruption Quarantine:** Any corrupted or unparseable registry file is automatically preserved to `.corrupt.<timestamp>.json`, blocking certification fail-closed.
