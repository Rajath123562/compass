# COMPASS Backup and Restoration Guide

**Project:** COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces  
**Backup Archive:** `compass_backup_verified_20261017.zip`  
**Storage Location:** `C:\Users\RAJATH U\Downloads\compass_backup_verified_20261017.zip`  
**Date:** 2026-10-18  

---

## 1. Verified Backup Specifications

The verified release backup archive was generated and self-tested via `scripts/create_verified_backup.py`.

### Archive Metadata
- **Archive Path:** `c:\Users\RAJATH U\Downloads\compass_backup_verified_20261017.zip`
- **Total Files Archived:** **1,712 files**
- **Uncompressed Source Size:** **39.59 MB**
- **Compressed Zip Size:** **4.50 MB**
- **Cryptographic Hash (SHA-256):**  
  `f9b4cd9176556071f9dc554622892aedd3d393d042a94bbcdec9124adfd6b824`
- **Integrity Verification:** **PASSED** (100% extracted and verified against test sandbox).

---

## 2. Contents Preserved

The backup archive contains the complete, production-ready codebase including:
1. **Core Source Code:**
   - `backend/` (FastAPI endpoints, state machine, database models, services).
   - `frontend/` (React components, Vite configuration, CSS tokens, assets).
   - `planner/` (Goal understanding, DAG orchestrator, verification engine, human approval).
   - `perception/` (UIA inspector, OpenCV processor, evidence fusion, DPI coordinate mapper).
   - `automation/` (Action dispatcher, Win32 input synthesizer, Playwright adapter).
   - `providers/` (OmniRoute provider with TTL caching, free-only policy enforcement).
   - `assurance/` (Safety harness, finding registry, secret scanner).
2. **Operational Scripts & Launchers:**
   - `START_COMPASS.bat` and `STOP_COMPASS.bat`.
   - `scripts/start_compass.py`, `scripts/stop_compass.py`, `scripts/benchmark_baseline.py`.
3. **Reports & Audit Artifacts:**
   - `reports/optimization/` (Complete performance data, architecture review, readiness assessment).
   - `reports/qa/` (Historical QA audit and certification reports).
4. **Configuration & Testing Suites:**
   - All 714 pytest test cases across 6 test suites.
   - `package.json`, `package-lock.json`, `requirements.txt`, `pytest.ini`.

*Note: Ephemeral runtime caches (`__pycache__`, `node_modules`, `.pytest_cache`, `dist`) are intentionally excluded to keep the archive compact and prevent platform-specific binary corruption.*

---

## 3. Restoration Procedure

Follow these steps to restore the COMPASS project onto any compatible Windows 11 machine:

### Step 1: Verify Archive Hash
Open PowerShell in the directory containing the zip archive and run:
```powershell
Get-FileHash -Algorithm SHA256 "compass_backup_verified_20261017.zip"
```
Verify that the output hash matches:
`f9b4cd9176556071f9dc554622892aedd3d393d042a94bbcdec9124adfd6b824`

### Step 2: Extract the Archive
Extract the zip file to your desired project directory:
```powershell
Expand-Archive -Path "compass_backup_verified_20261017.zip" -DestinationPath "C:\COMPASS"
```

### Step 3: Install Dependencies
Navigate into the extracted folder and run:
```powershell
cd C:\COMPASS

# 1. Install Python dependencies
python -m pip install -r requirements.txt

# 2. Install Frontend dependencies
cd frontend
npm install
npm run build
cd ..
```

### Step 4: Verify Installation
Execute the quick test suite to ensure all dependencies and modules are verified:
```powershell
python -m pytest backend/tests/ test_health.py
```

### Step 5: Launch Application
Double-click `START_COMPASS.bat` or run:
```powershell
python scripts/start_compass.py
```
The browser will automatically open to `http://localhost:5173`.
