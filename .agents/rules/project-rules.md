# Global Rules (always apply, every project)

1. READ FIRST: Before changing code, read SPEC.md, TASKS.md and PROGRESS.md if they exist. If they do not exist and I asked to build something, use the master-builder skill.
2. NO GUESSING: If a requirement, version, API or behavior is unclear, check the official docs or ask me. Never invent function names, packages, flags or file paths. If you are not sure something exists, verify it by running a command or reading the docs.
3. ONE TASK AT A TIME: Do only the task I named or the next task in TASKS.md. No extra features, no unrelated refactors, no "while I'm here" changes.
4. PROOF BEFORE "DONE": A task is done only after you ran it and saw it work. Show the exact command and its real output. If you could not run something, say so plainly.
5. STACK DISCIPLINE: Use only the stack in SPEC.md. Ask before adding any library, framework, service or tool.
6. SECRETS: Never hardcode or commit secrets. Use environment variables, keep `.env` in `.gitignore`, and keep an `.env.example` with placeholder values.
7. SAFETY: Never delete files, drop data, force-push, or run destructive commands without my explicit approval.
8. HONESTY: Report failures, assumptions and unfinished work clearly. Never hide errors, silence warnings, delete failing tests, or write fake data to look finished.
9. STOP CONDITIONS: Stop and ask me if you fail twice at the same problem, need a paid service, or find that my requirements contradict each other.
10. ENVIRONMENT: I use Windows with PowerShell. Use commands that work there (use `;` not `&&` in Windows PowerShell 5.1, use backslash-safe paths, check `python`/`py` and `node` availability before using them).
11. REPORT: End every task with: Done / Proof / How I verify / Not done or assumed.
