# Retrospective: <task title>

- Task: <task id or short title>
- Mode: <development | research | ops | tutor | unattended>
- Harness: <claude | codex | cursor | copilot | opencode>
- Model and effort: <model@effort or inherit>
- Workspace: <absolute path>
- Date: <YYYY-MM-DD>
- Outcome: <pass | partial | fail>
- Corrections by Owen: <count>
- Cost and time: <usd or unknown>, <minutes or unknown>

## What went well

- <observed behavior, and the instruction, skill, or tool that produced it>

## What went wrong

- <observed behavior> | Expected: <behavior> | Evidence: <path, command, or quoted line> | Cost: <minutes, retries, or corrections>

## Root causes

- <failure above> <- <the policy guidance, runtime control, skill, tool, or model behavior that explains it>

## Proposed change

Summary: <one sentence naming the change; it becomes the issue title. Write exactly "No change proposed." to skip the issue>

Why: <what the change prevents, using a failure above as the example>

Files to change:
- `<path/to/file>`: <what changes there>

Implementation steps:
1. <step an agent can execute without asking>

Acceptance criteria:
- <observable check that distinguishes done from plausible>

Validation:
```sh
python3 scripts/oas.py check
python3 -m unittest discover -s tests -v
```

Out of scope:
- <what this issue deliberately leaves alone>
