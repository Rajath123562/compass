# Script / automation / bot checklist
- State inputs, outputs, and schedule clearly. Provide `--help` and a dry-run mode.
- Idempotent: running twice must not duplicate or corrupt results.
- Handle: missing files, bad input, network failure, API rate limits, partial failure (resume or report).
- Config via env variables or a config file; no secrets in code.
- Logging with timestamps and levels; clear exit codes.
- Respect website terms and robots.txt; use official APIs where they exist; add delays between requests.
- Test with sample data and a failure case. Document how to schedule it (cron, Task Scheduler, hosted runner).
