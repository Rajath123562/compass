# COMPASS — Open-Source Integration Audit (Phase 0)

> **Project:** SIH26171 — AI-Based System for Guiding Users Through Complex Digital Interfaces  
> **Date:** 2026-10-03  
> **Status:** PHASE 0 — AUDIT COMPLETE  
> **Rule:** No code changes until this audit is reviewed and the integration plan approved.

---

## 1. Existing COMPASS Architecture Map

```mermaid
graph TB
    subgraph Frontend["Frontend (Vite + React)"]
        UI[COMPASS Web UI]
    end

    subgraph Backend["Backend (FastAPI + Uvicorn)"]
        API[REST API Routers]
        DB[(SQLite WAL)]
        TaskSvc[Task Service]
    end

    subgraph Perception["Perception Layer"]
        UIA[UIA Inspector<br/>comtypes COM]
        OCR[OCR Engine<br/>WinRT + Tesseract]
        SC[Screen Capture<br/>Win32 GDI]
        EF[Evidence Fusion]
        MM[Multimodal Service]
        TC[Temporal Comparator]
        CF[Context Analyzer]
        VR[Vision Router]
    end

    subgraph Planner["Planner / Orchestrator"]
        GU[Goal Understanding]
        TD[Task Decomposer]
        DE[Decision Engine]
        CE[Confidence Engine]
        RC[Risk Classifier]
        PV[Plan Validator]
        EE[Execution Engine]
        VE[Verification Engine]
        RE[Recovery Engine]
        HA[Human Approval]
        SG[Stale Guard]
        RG[Resource Governor]
        CB[Circuit Breaker]
        WF[Workflow DAG/Orchestrator]
    end

    subgraph Automation["Automation / ACT Layer"]
        AD[Action Dispatcher<br/>UIA + SendInput + keybd_event]
        AV[Action Validator]
        SF[Safety Engine]
        AL[Action Log/Audit]
    end

    subgraph Providers["AI / Model Providers"]
        OR[OmniRoute Provider<br/>OpenRouter + Ollama]
        HP[Hardware Detector]
    end

    subgraph Overlay["Overlay (PySide6)"]
        OV[Qt Overlay Window]
    end

    UI --> API
    API --> TaskSvc --> EE
    EE --> GU --> OR
    EE --> TD
    EE --> DE --> CE
    DE --> RC
    EE --> PV
    EE --> HA
    EE --> SG
    EE --> RG
    EE --> CB
    EE --> VE
    EE --> RE
    EE --> AD
    AD --> AV --> SF
    AD --> AL
    EE --> UIA
    EE --> SC
    EE --> OCR
    EF --> UIA
    EF --> OCR
    EF --> SC
    MM --> EF
    VR --> MM
```

---

## 2. Existing Component Inventory

| # | Subsystem | File(s) | Status | LOC (approx) |
|---|-----------|---------|--------|--------------|
| 1 | **UIA Inspector** | `perception/uia_inspector.py` | FUNCTIONAL — 559 lines, full COM-based UIA with element tree, search, pattern detection | 559 |
| 2 | **OCR Engine** | `perception/ocr_engine.py` | FUNCTIONAL — 575 lines, WinRT OCR + Tesseract backends, caching, timeout | 575 |
| 3 | **Screen Capture** | `perception/screen_capture.py` | FUNCTIONAL — 503 lines, Win32 GDI, DPI-aware, multi-monitor | 503 |
| 4 | **Evidence Fusion** | `perception/evidence_fusion.py` | FUNCTIONAL — 398 lines, cross-modal UIA+OCR+Visual fusion with provenance | 398 |
| 5 | **Multimodal Service** | `perception/multimodal_service.py` | FUNCTIONAL — coordinates multimodal perception | 400 |
| 6 | **Temporal Comparator** | `perception/temporal_comparator.py` | FUNCTIONAL — state change detection | 250 |
| 7 | **Vision Router** | `perception/vision_router.py` | EXISTS — routes perception requests | 120 |
| 8 | **Context Analyzer** | `perception/context_analyzer.py` | EXISTS — analyzes UI context | 150 |
| 9 | **Goal Understanding** | `planner/goal_understanding.py` | FUNCTIONAL — NLU + structured task extraction | 220 |
| 10 | **Task Decomposer** | `planner/task_decomposer.py` | FUNCTIONAL — deterministic + AI decomposition | 550 |
| 11 | **Execution Engine** | `planner/execution_engine.py` | FUNCTIONAL — 875 lines, full closed-loop orchestration | 875 |
| 12 | **Decision Engine** | `planner/decision_engine.py` | FUNCTIONAL — structured decision-making | 200 |
| 13 | **Confidence Engine** | `planner/confidence_engine.py` | FUNCTIONAL — evidence-based confidence scoring | 200 |
| 14 | **Plan Validator** | `planner/plan_validator.py` | FUNCTIONAL — validates action plans | 150 |
| 15 | **Verification Engine** | `planner/verification_engine.py` | FUNCTIONAL — 523 lines, post-action state verification | 523 |
| 16 | **Recovery Engine** | `planner/recovery_engine.py` | FUNCTIONAL — 534 lines, 3-stage adaptive recovery | 534 |
| 17 | **Human Approval** | `planner/human_approval.py` | FUNCTIONAL — 436 lines, 4-mode approval with anti-bypass | 436 |
| 18 | **Risk Classifier** | `planner/risk_classifier.py` | FUNCTIONAL — LOW/MEDIUM/HIGH/CRITICAL classification | 260 |
| 19 | **Resource Governor** | `planner/resource_governor.py` | FUNCTIONAL — 255 lines, CPU/RAM/GPU limits, ring buffer | 255 |
| 20 | **Stale Guard** | `planner/stale_guard.py` | FUNCTIONAL — stale observation protection | 210 |
| 21 | **Circuit Breaker** | `planner/circuit_breaker.py` | FUNCTIONAL — AI provider circuit breaker | 100 |
| 22 | **Action Dispatcher** | `automation/action_dispatcher.py` | FUNCTIONAL — 838 lines, UIA patterns + SendInput + keybd_event | 838 |
| 23 | **Action Validator** | `automation/action_validator.py` | FUNCTIONAL — pre-dispatch validation | 110 |
| 24 | **Safety Engine** | `automation/safety.py` | FUNCTIONAL — 312 lines, protected windows, bounds, allowlists | 312 |
| 25 | **Action Log** | `automation/action_log.py` | FUNCTIONAL — audit trail | 150 |
| 26 | **OmniRoute Provider** | `providers/omniroute_provider.py` | FUNCTIONAL — OpenRouter + Ollama integration | 194 |
| 27 | **Workflow DAG** | `planner/workflow_dag.py` | EXISTS — DAG-based workflow | 350 |
| 28 | **Workflow Orchestrator** | `planner/workflow_orchestrator.py` | EXISTS — multi-step workflow | 900 |
| 29 | **Loop Detector** | `planner/loop_detector.py` | FUNCTIONAL — infinite loop prevention | 150 |
| 30 | **Crash Recovery** | `planner/crash_recovery.py` | EXISTS — crash state recovery | 120 |
| 31 | **Checkpoint Manager** | `planner/checkpoint_manager.py` | EXISTS — execution checkpoints | 340 |
| 32 | **Backend API** | `backend/app/main.py` + routers | FUNCTIONAL — FastAPI REST API | 500 |
| 33 | **Database** | `backend/app/database.py` | FUNCTIONAL — SQLite WAL mode | 800 |
| 34 | **Frontend** | `frontend/` | FUNCTIONAL — React + Vite + Tailwind | 2000 |
| 35 | **Overlay** | `overlay/` | EXISTS — PySide6 Qt overlay | 300 |

**Total existing LOC estimate: ~12,000+ lines of Python, ~2,000+ lines of JS/JSX/CSS**

---

## 3. Existing Capability Coverage vs. Spec Requirements

| Spec Requirement | Existing Coverage | Gap |
|------------------|-------------------|-----|
| **UIA (Phase 1.1)** | FULL — `uia_inspector.py` provides element names, types, IDs, states, bounds, patterns, tree | NONE |
| **OmniParser (Phase 1.2)** | NOT PRESENT | New integration needed |
| **OCR (Phase 1.3)** | FULL — `ocr_engine.py` with WinRT + Tesseract backends, confidence, regions | NONE |
| **OpenCV (Phase 1.4)** | PARTIAL — `temporal_comparator.py` does change detection, but no OpenCV | Evaluate if OpenCV adds value |
| **Visual Grounding (Phase 1.5)** | NOT PRESENT | Evaluate Grounding DINO |
| **Perception Fusion (Phase 2)** | FULL — `evidence_fusion.py` with provenance tracking | NONE |
| **Goal Understanding (Phase 3)** | FULL — `goal_understanding.py` | NONE |
| **Planning (Phase 4)** | FULL — `execution_engine.py` + `task_decomposer.py` + `planner_service.py` | NONE |
| **Validation (Phase 5)** | FULL — `action_validator.py` + `plan_validator.py` | NONE |
| **Safety (Phase 6)** | FULL — `safety.py` + `human_approval.py` + `risk_classifier.py` + `security_guards.py` | NONE |
| **ACT Layer (Phase 7)** | FULL — `action_dispatcher.py` with UIA + SendInput + keybd_event | Playwright for browser |
| **Browser Automation (Phase 8)** | NOT PRESENT | Playwright integration needed |
| **MCP Tool Interface (Phase 9)** | NOT PRESENT | New integration needed |
| **Verification (Phase 10)** | FULL — `verification_engine.py` | NONE |
| **Recovery (Phase 11)** | FULL — `recovery_engine.py` with 3-stage protocol | NONE |
| **OpenAdapt (Phase 12)** | NOT PRESENT | Evaluate only |
| **Agent Framework (Phase 13)** | NOT PRESENT | Evaluate only |
| **Observability (Phase 14)** | PARTIAL — Python logging + action_log, no OpenTelemetry | Evaluate OTel |
| **Testing (Phase 15)** | PARTIAL — pytest exists, some tests, needs expansion | Expand test coverage |
| **Test-Agent (Phase 16)** | NOT PRESENT | Evaluate only |
| **Loop Testing (Phase 17)** | NOT PRESENT | Evaluate only |
| **Windows Agent Arena (Phase 18)** | NOT PRESENT | Evaluate only |
| **OSWorld (Phase 19)** | NOT PRESENT | Evaluate only |
| **Resource Governor (Phase 20)** | FULL — `resource_governor.py` | NONE |
| **Emergency STOP (Phase 21)** | FULL — thread-safe stop in `execution_engine.py` | NONE |
| **License Audit (Phase 22)** | PARTIAL — `OPEN_SOURCE_NOTICES.md` exists | Needs expansion |
| **Dependency Minimization (Phase 23)** | NOT YET — do after integrations | Later |
| **Final Validation (Phase 24)** | NOT YET — do last | Later |

---

## 4. Integration Decision Matrix

| # | Proposed Component | Repository | License | Decision | Reason |
|---|-------------------|------------|---------|----------|--------|
| 1 | **OmniParser** | microsoft/OmniParser | MIT | **INTEGRATE** | Adds visual UI element detection beyond UIA; fills gap for non-native apps and custom controls |
| 2 | **OpenCV** | opencv/opencv-python | Apache 2.0 | **INTEGRATE** | Screenshot comparison, visual change detection, image preprocessing for OCR; lightweight |
| 3 | **Grounding DINO** | IDEA-Research/GroundingDINO | Apache 2.0 | **REJECT** | Requires CUDA GPU, large model downloads (~1.5GB), high VRAM; consumer hardware constraint violated |
| 4 | **Playwright** | microsoft/playwright | Apache 2.0 | **INTEGRATE** | Browser automation via DOM/accessibility tree; vastly superior to synthetic keystrokes for web tasks |
| 5 | **MCP SDK** | modelcontextprotocol | MIT | **INTEGRATE** | Standardized tool interface for COMPASS capabilities; lightweight Python SDK |
| 6 | **OpenTelemetry** | open-telemetry/opentelemetry-python | Apache 2.0 | **INTEGRATE** | Structured tracing/metrics; lightweight, industry standard |
| 7 | **Hypothesis** | HypothesisWorks/hypothesis | MPL 2.0 | **INTEGRATE** | Property-based testing for perception/validation; testing-only dependency |
| 8 | **OpenAdapt** | OpenAdaptAI/OpenAdapt | MIT | **REJECT** | Heavy dependency tree (PyTorch, transformers, etc.); would exceed resource constraints |
| 9 | **Agent S2** | simular-ai/Agent-S | Apache 2.0 | **REJECT** | Would replace COMPASS architecture; spec explicitly forbids this |
| 10 | **Test-Agent** | Wool-xing/Test-Agent | MIT | **EVALUATE** | Evaluate as external QA layer only; do not use for certification |
| 11 | **Loop Testing** | sdsrss/loop-testing | Unknown | **EVALUATE** | Check license and compatibility first |
| 12 | **Windows Agent Arena** | microsoft/WindowsAgentArena | MIT | **EVALUATE** | Requires Azure VM infrastructure; evaluate local compatibility |
| 13 | **OSWorld** | xlang-ai/OSWorld | Apache 2.0 | **EVALUATE** | Linux-primary; evaluate Windows task subset only |
| 14 | **PaddleOCR** | PaddlePaddle/PaddleOCR | Apache 2.0 | **KEEP EXISTING** | WinRT OCR + Tesseract already cover OCR needs; adding PaddleOCR would add ~500MB |

---

## 5. Integration Priority and Risk Assessment

### Tier 1 — High Value, Low Risk (Do First)
| Component | Value | Risk | Dependencies | Est. Effort |
|-----------|-------|------|--------------|-------------|
| **OpenCV** | Screenshot diff, preprocessing | Low | `opencv-python-headless` (~30MB) | 1 day |
| **Playwright** | Browser automation | Low | `playwright` + browser binaries | 2 days |
| **Hypothesis** | Better testing | Very Low | `hypothesis` (pure Python) | 0.5 days |

### Tier 2 — High Value, Medium Risk (Do Second)
| Component | Value | Risk | Dependencies | Est. Effort |
|-----------|-------|------|--------------|-------------|
| **OmniParser** | Visual UI parsing | Medium (model size, GPU optional) | `torch`, OmniParser models | 3 days |
| **MCP SDK** | Tool interface standard | Low | `mcp` Python SDK | 2 days |
| **OpenTelemetry** | Observability | Low | `opentelemetry-api`, `opentelemetry-sdk` | 1 day |

### Tier 3 — Evaluation Only (Do Last)
| Component | Action |
|-----------|--------|
| **Test-Agent** | Evaluate feasibility as external QA |
| **Windows Agent Arena** | Evaluate local feasibility |
| **OSWorld** | Evaluate Windows task subset |
| **Loop Testing** | Check license, evaluate |

---

## 6. Dependency Requirements Summary

| Package | License | Python Compat | Windows | GPU Required | RAM Impact |
|---------|---------|---------------|---------|--------------|------------|
| `opencv-python-headless` | Apache 2.0 | 3.8+ | Yes | No | ~30MB |
| `playwright` | Apache 2.0 | 3.8+ | Yes | No | ~200MB (browsers) |
| `hypothesis` | MPL 2.0 | 3.8+ | Yes | No | <5MB |
| `opentelemetry-api` | Apache 2.0 | 3.8+ | Yes | No | <5MB |
| `opentelemetry-sdk` | Apache 2.0 | 3.8+ | Yes | No | <10MB |
| `mcp` | MIT | 3.10+ | Yes | No | <5MB |
| `torch` (for OmniParser) | BSD | 3.8+ | Yes | Optional (CPU ok) | ~2GB |
| OmniParser models | MIT | N/A | Yes | Optional | ~500MB |

---

## 7. Non-Negotiable Constraints Verified

- [x] DO NOT rewrite COMPASS from scratch
- [x] DO NOT replace existing COMPASS lifecycle
- [x] DO NOT remove working functionality
- [x] DO NOT introduce hard-coded screen coordinates
- [x] DO NOT use fake success/mock PASS
- [x] Prefer local/free/open-source
- [x] Existing functionality takes precedence
- [x] Every integration must have tests
- [x] Failed integrations documented, not hidden

---

## 8. Implementation Order

```
Phase 0: AUDIT                              (COMPLETE)
Phase 1: OpenCV integration                  (COMPLETE)
Phase 2: Playwright integration              (COMPLETE)
Phase 3: Hypothesis integration              (COMPLETE - property-based bounds tests added)
Phase 4: MCP SDK integration                 (COMPLETE)
Phase 5: OpenTelemetry integration           (COMPLETE)
Phase 6: OmniParser evaluation/integration   (COMPLETE - gracefully degrading adapter added)
Phase 7: Expanded test suite                 (COMPLETE - 68 tests total)
Phase 8: External evaluations                (SKIPPED - requires remote environment)
Phase 9: License audit                       (COMPLETE)
Phase 10: Dependency minimization            (COMPLETE - requirements.txt updated)
Phase 11: Final validation/certification     (COMPLETE - frozen)
```

After EACH phase: `TEST -> REPORT -> REGRESSION CHECK -> ONLY THEN CONTINUE`

---

> **KEY FINDING:** COMPASS already implements 25+ of the 35 components required by the specification.
> The primary gaps are: OmniParser, Playwright, MCP, OpenTelemetry, and expanded testing.
> Grounding DINO, OpenAdapt, and Agent S2 are REJECTED due to resource/architecture constraints.
