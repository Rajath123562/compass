# COMPASS Continuous Production Assurance System

## Overview

The COMPASS Assurance System is a **continuous adversarial QA, security, runtime verification, and release-readiness layer** built around the COMPASS application (Phases 1–14).

It does **NOT** replace Phases 1–14. It continuously examines the real application across source code, dependencies, APIs, runtime behavior, Windows UI, security, AI-agent behavior, and performance.

## Core Principle

```
DISCOVER → INVENTORY → THREAT MODEL → BASELINE → TEST → ATTACK → FUZZ →
OBSERVE → DETECT → REPRODUCE → TRIAGE → FIX → RETEST → RE-ATTACK →
REGRESSION → PERFORMANCE → SECURITY REVIEW → EVIDENCE → RELEASE GATE
```

## Quick Start

### One-Click Assurance
Double-click `COMPASS_ASSURE.bat` in the repository root. It defaults to `--quick` mode.

### Command Line
```powershell
# Quick scan (Inventory + Static Analysis + Secrets + Regression)
.venv\Scripts\python.exe assurance\compass_assure.py --quick

# Full assurance pipeline
.venv\Scripts\python.exe assurance\compass_assure.py --full

# Security-focused scan
.venv\Scripts\python.exe assurance\compass_assure.py --security

# Runtime testing (requires running COMPASS server)
.venv\Scripts\python.exe assurance\compass_assure.py --runtime

# Regression only
.venv\Scripts\python.exe assurance\compass_assure.py --regression

# Real Assembled Product E2E Suite (Backend + Frontend + Real Windows)
.venv\Scripts\python.exe assurance\compass_assure.py --real-product

# Performance benchmarks only
.venv\Scripts\python.exe assurance\compass_assure.py --performance
```

## Architecture

```
assurance/
├── compass_assure.py          # Master orchestrator runner
├── finding_schema.py          # Central finding registry & schema
├── inventory_builder.py       # Application inventory & attack surface discovery
├── real_product_harness.py    # Real product lifecycle manager & external Win32 observer
├── real_product_suite.py      # Real assembled product E2E test suite (18 tests)
├── tools/
│   ├── sast_runner.py         # Static analysis (Bandit)
│   ├── dependency_scanner.py  # pip-audit + npm audit
│   ├── secret_scanner.py      # Pattern-based secret detection
│   ├── api_security_tester.py # API fuzzing & input validation
│   └── release_gate.py        # Production readiness evaluator
├── findings/                  # Persistent finding register (JSON)
├── evidence/                  # Preserved test evidence
└── reports/                   # Generated analysis reports
```

## Modes

| Mode | What It Tests | When To Use |
|------|--------------|-------------|
| `--quick` | Inventory, SAST, Secrets, Regression | Day-to-day development checks |
| `--full` | Everything including live Windows and real product tests | Before releases or major changes |
| `--real-product` | Assembled Backend + Frontend + Real Windows E2E | Verifying live product behavior |
| `--security` | SAST, Dependencies, Secrets, API | After adding dependencies or APIs |
| `--runtime` | API, Adversarial, Real Windows, Real Product | After UI/automation changes |
| `--regression` | Full pytest suite (595+ tests) | After any code change |
| `--performance` | Benchmarks, Stability, Memory | After optimization work |

## Key Reports & Standards

- [Actual Product Test Report](file:///c:/Users/RAJATH%20U/Downloads/personal%20assitant/docs/ASSURANCE/ACTUAL_PRODUCT_TEST_REPORT.md): Complete audit of real assembled product testing on Windows 11.
- [Product Capability Matrix](file:///c:/Users/RAJATH%20U/Downloads/personal%20assitant/docs/ASSURANCE/PRODUCT_TEST_MATRIX.md): 12-dimension verification matrix across all core capabilities.
- [Production Assurance Report](file:///c:/Users/RAJATH%20U/Downloads/personal%20assitant/docs/ASSURANCE/PRODUCTION_ASSURANCE_REPORT.md): High-level assurance executive summary.

## Finding Management

All findings from all tools feed into `assurance/findings/finding_register.json` with:
- Unique ID, source tool, severity, confidence
- Reproduction steps and evidence
- Remediation status tracking
- Re-attack verification status

## Zero-Trust Principles

- Every tool output is treated as evidence requiring validation
- No finding is auto-confirmed without reproducible evidence
- No "100% secure" claims are ever made
- Coverage limitations are documented honestly
- External systems are never attacked
