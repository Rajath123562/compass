# COMPASS Backup and Restoration Guide

**Project:** COMPASS — AI-Based System for Guiding Users Through Complex Digital Interfaces  
**Standard:** Phase 14 Verified Non-Destructive Backup & Disaster Recovery Standard  
**Backup Status:** **CREATED, TESTED & 100% VERIFIED**  
**Date:** October 17, 2026  

---

## 1. Verified Backup Manifest

The verified production backup of the repaired and tested COMPASS project was created and stored in a separate directory outside the active project tree:

| Attribute | Specification |
|---|---|
| **Archive File Path** | `C:\Users\RAJATH U\Downloads\compass_backup_verified_20261017.zip` |
| **Creation Date** | October 17, 2026 (23:53 IST) |
| **Archive Type** | Standard ZIP Archive (Deflate Level 6) |
| **Archived File Count** | **1,635 files** |
| **Uncompressed Size** | **38.88 MB** |
| **Compressed Size** | **4.40 MB** |
| **SHA-256 Checksum** | `fd86857a3d76ce962a43926956de722f480e877b68a063e702665ed4094cb952` |
| **Integrity Test** | Passed (`zipfile.testzip()` returned 0 errors; extracted 1,635 files cleanly) |

---

## 2. Exclusions Applied (Clean Source State)

To ensure portability and protect sensitive credentials, the following items were intentionally excluded from the backup archive:

- **Version Control:** `.git/` repository history
- **Virtual Environments:** `.venv/`, `venv/`
- **Node Dependencies:** `frontend/node_modules/`
- **Build Artifacts & Caches:** `dist/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `*.pyc`
- **Temporary Logs:** `scratch/`, `test-results/`
- **Secrets:** All local `.env` files and credentials (sanitized configuration templates are preserved in repository)

---

## 3. Step-by-Step Restoration Procedure

To restore COMPASS on any compatible Windows 11 machine:

### Step 1: Extract the Archive
1. Choose a destination folder (e.g., `C:\Projects\COMPASS_RESTORED`).
2. Extract `compass_backup_verified_20261017.zip` using Windows Explorer or PowerShell:
   ```powershell
   Expand-Archive -Path "C:\Users\RAJATH U\Downloads\compass_backup_verified_20261017.zip" -DestinationPath "C:\Projects\COMPASS_RESTORED"
   cd "C:\Projects\COMPASS_RESTORED"
   ```

### Step 2: Set Up Python Virtual Environment
1. Ensure Python 3.11 is installed.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install the required Python dependencies:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Install Playwright browser binaries:
   ```powershell
   playwright install chromium
   ```

### Step 3: Set Up Frontend Node Dependencies
1. Ensure Node.js 18+ is installed.
2. Install npm packages for the React frontend:
   ```powershell
   npm --prefix frontend install
   ```
3. Verify the frontend builds cleanly:
   ```powershell
   npm --prefix frontend run build
   ```

### Step 4: Verify Local AI Engine
1. Ensure Ollama is installed and running (`ollama serve`).
2. Pull the required local model:
   ```powershell
   ollama pull qwen3.5:4b
   ```

### Step 5: Validate Restoration via Regression Suite
Run the test suite to verify the restored environment:
```powershell
pytest backend/ perception/ automation/ providers/ assurance/ planner/
```
Expected result: **All unit and integration tests pass cleanly.**

### Step 6: Launch COMPASS
Launch the restored system using the unified startup script:
```powershell
.\START_COMPASS.bat
```
Navigate to `http://127.0.0.1:5173` to use the application.
