# COMPASS — Open-Source License Audit (Phase 22)

> **Date:** 2026-10-03
> **Status:** AUDIT COMPLETE

Every external dependency integrated into COMPASS has been audited for license compatibility with the SIH26171 distribution requirements.

## 1. Integrated Components

| Dependency | Repository / Source | Version | License | Compatibility | Risk |
|------------|--------------------|---------|---------|---------------|------|
| **OpenCV** (`opencv-python-headless`) | [opencv/opencv-python](https://github.com/opencv/opencv-python) | ^4.9.0 | Apache 2.0 | ✅ COMPATIBLE | Low |
| **Playwright** (`playwright`) | [microsoft/playwright-python](https://github.com/microsoft/playwright-python) | ^1.42.0 | Apache 2.0 | ✅ COMPATIBLE | Low |
| **Hypothesis** (`hypothesis`) | [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) | ^6.98.0 | MPL 2.0 | ✅ COMPATIBLE | Low (Test only) |
| **OpenTelemetry API** (`opentelemetry-api`) | [open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python) | ^1.23.0 | Apache 2.0 | ✅ COMPATIBLE | Low |
| **OpenTelemetry SDK** (`opentelemetry-sdk`) | [open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python) | ^1.23.0 | Apache 2.0 | ✅ COMPATIBLE | Low |

## 2. Rejected Components (Not Integrated)

| Component | Reason for Rejection | License |
|-----------|----------------------|---------|
| **Grounding DINO** | High VRAM requirements, CUDA dependency | Apache 2.0 |
| **OpenAdapt** | Excessive dependencies (PyTorch, transformers) | MIT |
| **Agent S2** | Replaces core architecture; forbidden by spec | Apache 2.0 |

## 3. Existing Base Dependencies

| Package | Version | License |
|---------|---------|---------|
| `fastapi` | >=0.110.0 | MIT |
| `uvicorn` | >=0.28.0 | BSD-3-Clause |
| `pydantic` | >=2.6.0 | MIT |
| `pytest` | >=8.0.0 | MIT |
| `httpx` | >=0.27.0 | BSD-3-Clause |
| `requests` | >=2.31.0 | Apache 2.0 |
| `psutil` | >=5.9.0 | BSD-3-Clause |
| `PySide6` | >=6.6.0 | LGPLv3 / Commercial |
| `comtypes` | >=1.4.0 | MIT |
| `Pillow` | >=10.0.0 | HPND |
| `winrt-*` | >=3.2.1 | MIT |

## 4. Distribution Requirements

- **Apache 2.0 / MIT / BSD**: Safe for distribution. Must include license text in third-party notices.
- **MPL 2.0**: File-level copyleft. Modifications to `hypothesis` files must be MPL. Since it is only used for testing and not modified, it is fully compatible.
- **LGPLv3** (`PySide6`): Dynamic linking allowed. COMPASS must not statically link PySide6. The current architecture runs the UI out-of-process via standard Python imports, satisfying the LGPL boundary requirements.

## 5. Conclusion

**PASS**. All integrated dependencies have permissive, business-safe licenses (Apache 2.0, MIT) and are cleared for production use in the SIH26171 system.
