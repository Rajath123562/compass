# COMPASS Data Retention & Telemetry Policy (§15)

## 1. Overview
COMPASS (**AI-Based System for Guiding Users Through Complex Digital Interfaces**) handles real-time desktop perception, action planning, and user automation. This policy specifies strict boundaries for the retention, scrubbing, and expiration of runtime telemetry, perception captures, AI prompts, and execution logs.

---

## 2. Retention Classifications & Limits

| Data Category | Storage Mechanism | Retention Limit | Eviction Strategy | Secret Scrubbing |
|---|---|---|---|---|
| **Screenshot Frames** | In-Memory Ring Buffer (`planner/resource_governor.py`) | **5 Frames Max** | FIFO (First In, First Out) | Ephemeral in-memory only; never written to persistent disk |
| **Observation Snapshots** | Memory / Task Timeline | **500 Entries / Task** | Bounded per task; cleared on task terminalization | Redacted before logging |
| **Task State & Metadata** | SQLite Database (`storage/compass.db`) | Persistent across sessions | Manual cleanup or archival | Passwords/API keys prohibited |
| **Execution Event Log** | SQLite Table (`task_events`) | Append-only per task lifecycle | Pruned on task deletion via foreign key cascade | Parameters scrubbed |
| **Approval Records** | SQLite Table (`approvals`) | Single-use token lifecycle | Single-use consumption (transitions to `CONSUMED`) | Expiration window enforced |
| **Application Log Files** | Rotating File Handler (`logs/compass.log`) | **5 MB / file, max 3 backups (15 MB total)** | Automatic log rotation | `SecretRedactionFilter` scrubs Bearer tokens, API keys, passwords |

---

## 3. Ephemeral Desktop Perception
1. **Zero Raw Frame Disk Dumping:** Raw desktop bitmap captures and GDI frame buffers are never written to unencrypted persistent disk files.
2. **Ring Buffer Ceiling:** The perception pipeline stores at most five (5) consecutive frames in RAM via `ScreenshotRingBuffer`. When frame #6 arrives, frame #1 is immediately discarded from memory.
3. **Task Completion Eviction:** Upon task termination (COMPLETED, FAILED, STOPPED, or CANCELLED), execution memory buffers and ring buffers are cleared.

---

## 4. Secret & Credential Redaction (§14)
1. **Automated Filter:** The logging pipeline incorporates `SecretRedactionFilter` across both console stdout and persistent rotating file handlers.
2. **Pattern Matching:** All strings matching Bearer authorization headers, API keys (`sk-`, `AIza`, etc.), tokens, and password fields are replaced with `[REDACTED]`.
3. **Zero Secret Persistence:** Database schema and task event payloads reject or redact sensitive authentication headers before SQLite transaction commit.

---

## 5. Storage Maintenance & Integrity
- **SQLite Engine:** Uses Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) with foreign keys enabled (`PRAGMA foreign_keys=ON;`) and bounded timeout (`PRAGMA busy_timeout=5000;`).
- **Restart Auditing:** On system startup, the `CrashRecoveryHandler` scans for orphaned non-terminal tasks, marks them `STOPPED`, and invalidates lingering approval records.
