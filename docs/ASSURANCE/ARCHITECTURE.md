# COMPASS Assurance — Architecture

## System Design

The assurance system is a layered pipeline that wraps around the existing COMPASS application without modifying it:

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPASS ASSURE Runner                        │
│  compass_assure.py (Master Orchestrator)                        │
├─────────────────────────────────────────────────────────────────┤
│  Stage Pipeline:                                                │
│  ┌──────────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌──────────────┐ │
│  │ Inventory│→│ SAST │→│DepScan │→│Secrets │→│   Regression │ │
│  └──────────┘ └──────┘ └────────┘ └────────┘ └──────────────┘ │
│       ↓                                            ↓            │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │Adversarial│→│Real Win11│→│Performance│→│  API Security   │  │
│  └──────────┘ └──────────┘ └───────────┘ └─────────────────┘  │
│       ↓                                            ↓            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Release Gate Evaluator                     │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Finding Registry (finding_schema.py)                           │
│  Deduplication • Severity • Confidence • Status Tracking        │
├─────────────────────────────────────────────────────────────────┤
│  Evidence Storage (assurance/evidence/, assurance/reports/)      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **Non-Invasive**: The assurance system never modifies COMPASS source code directly. It examines, tests, and reports.
2. **Tool Agnostic**: Each tool (Bandit, pip-audit, etc.) is wrapped behind a runner that normalizes output into the Finding Registry schema.
3. **Resource-Aware**: All stages run sequentially to respect the 12GB RAM constraint. No parallel heavy tool execution.
4. **Evidence-First**: Every finding requires evidence. Every gate requires evidence. No synthetic results.
5. **Incremental**: Modes (`--quick`, `--security`, etc.) allow targeted assurance without running everything every time.

## Data Flow

```
Source Code → Inventory Builder → Attack Surface Map
Source Code → Bandit (SAST) → Findings
requirements.txt → pip-audit → Findings
package.json → npm audit → Findings
Source + Artifacts → Secret Scanner → Findings
Running API → API Security Tester → Findings
Running App → Phase 12/13/14 Suites → Pass/Fail
All Reports → Release Gate Evaluator → PASS / CONDITIONAL / FAIL
```
