# Project Overview: COMPASS

COMPASS is an AI-based system designed to guide users step-by-step through complex digital interfaces. It includes a frontend overlay, backend APIs, and several core engines:
- **Planner**: Handles multi-step verifications, state reconciliation, and orchestration.
- **Perception**: Interacts with the OS (Windows) and parses UI components.
- **Automation**: Coordinates UI automation actions safely.
- **Storage**: SQLite WAL database for resilience.

## Codebase Organization
The project is strictly organized to allow agents to easily ingest and resolve errors:
1. `backend/`: Fastapi server and core APIs.
2. `frontend/`: React components.
3. `planner/`: Core logic for DAG workflows and execution.
4. `perception/`: Vision and UI trees.
5. `automation/`: Action dispatchers.
6. `docs/`: Comprehensive agent-readable documentation suite.

*Optimized for production and AI readability.*
