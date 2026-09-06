# Task contract

Use `oas.py task` to generate the JSON record. This outline explains what the record should establish before substantial work.

- Outcome: observable change or answer the user needs.
- Owner and scope: who requested this, which workspace, which files/module, and what actions are authorized.
- Acceptance criteria: concrete observations that distinguish success from a plausible-looking draft.
- Evidence: commands/results, claim ledger, remote state, or review artifacts.
- Budget: time, iterations, compute, and stopping rule where appropriate.
- Checkpoint: current commit/worktree, completed work, blockers, and next action.

Keep evidence files inside the task directory and list relative paths in `criteria[].evidence`. Set `passed` only after checking the evidence. The record validator rejects missing/empty evidence, paths outside the task directory, and completion with unmet criteria or blockers. It checks record integrity, not scientific or semantic truth.

For unattended jobs, active records must additionally have explicit authorized actions, writable scope, positive time/iteration limits, a retry limit, and an idempotency key. These are recorded contracts, not a process supervisor: the host scheduler must enforce runtime deadlines and resource caps.
