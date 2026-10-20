---
name: planner
description: Use at the start of a project or feature to produce a complete SPEC.md and TASKS.md before any code. No code is written in this skill.
---
# Planner

Purpose: turn an idea into a plan so complete that a different engineer could build it without asking questions. Write NO application code here.

## Inputs
My idea and answers (or my autonomous-mode prompt), plus templates in `master-builder/templates/`.

## Step 1: Understand
1. Restate the idea in 3-5 lines.
2. Classify: web app, API/backend, mobile, AI/LLM app, or script/automation. Read the matching reference file in `master-builder/references/`.
3. List what is unknown. Unknowns to check: users, must-have vs nice-to-have features, platform, stack preference, data stored, login/accounts, payments, external APIs, hosting, budget, out of scope, look and feel.
4. INTERACTIVE mode: ask at most 8 grouped questions with a suggested default for each, then wait. AUTONOMOUS mode: choose defaults and record them as assumptions.

## Step 2: Choose the stack
- Prefer common, well-documented, free tools that match my skill level and constraints.
- Check exact versions and compatibility (run `--version` commands or read docs). Write exact versions down.
- Justify each choice in one line. Record the main alternative you rejected.

## Step 3: Write SPEC.md
Copy `templates/SPEC.template.md` and fill EVERY section. Rules:
- Each feature has inputs, outputs, errors, edge cases and checkbox done-criteria that can be tested by running something.
- Every route/endpoint/screen is listed with auth, input, output and error responses.
- Edge cases for each feature: empty input, wrong type, too long, duplicates, repeated clicks, network failure, unauthorized access, concurrent use.
- Security section is specific, not generic.
- No empty sections, no "TBD", no vague words like "etc." or "and so on".

## Step 4: Write TASKS.md
Copy `templates/TASKS.template.md`. Rules:
- T1 is always the scaffold with a running "hello world" and a working test runner.
- Each task is small (about 1 hour, at most ~5 files), builds on earlier tasks only, and ends with something runnable.
- Each task states files, exact steps, done-criteria and the exact test command or manual steps.
- Order by dependency: data and core logic first, then API, then UI, then polish.
- Add the risk table: version conflicts, API limits, OS differences, missing keys, edge cases.

## Step 5: Self-review (required)
Check each line; fix anything that fails:
- [ ] Every must-have feature appears in at least one task.
- [ ] Every done-criterion is testable.
- [ ] No task depends on something built later.
- [ ] Versions are compatible; the stack is free/available for my constraints.
- [ ] Data model supports every feature.
- [ ] No contradictions between SPEC.md and TASKS.md.

## Output
`SPEC.md`, `TASKS.md`, and a 5-line summary: what will be built, stack, number of tasks, top 3 risks, assumptions made. INTERACTIVE: wait for approval.
