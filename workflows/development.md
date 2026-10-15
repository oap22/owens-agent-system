# Development

1. Inspect repository instructions, git state, worktrees, and active ownership. Use an isolated task worktree and preserve unrelated changes.
2. Define observable before/after behavior. For substantial changes, record acceptance criteria, design decisions, risks, and validation before implementation, scaled to the change.
3. When delegation is authorized, give `implementor` an independent slice only if its check is executable and its reading would crowd the lead's context. Use `templates/task-packet.md`; keep coupled edits and intent questions in the lead. Workers must know they share the codebase.
4. A worker that exhausts its budget returns partial work and evidence. Diagnose before retrying: missing access, bad inputs, and a broken check need correction, not more effort. For a reasoning failure, use `implementor-retry` once if configured; otherwise take the slice in the lead. Log every attempt with `oas.py log-run` when evaluating the split.
5. Implement every requested behavior. Apply **Fix root causes** to bugs. Add focused regressions for bugs and failure boundaries, sized like neighboring tests. The relevant checks passing on the final diff defines done; reuse passing evidence for unchanged code.
6. Review the diff against the requirements. Use `adversarial-review` when applicable and authorized. Validate native behavior for platform-sensitive changes.
7. Commit reviewed files. Push and merge within the user's authorization after required CI and review gates. Distinguish local checks, hosted CI, merge, installation, and deployment.
8. Checkpoint after planning, completed implementation slices, and before release or compaction. Record commit, worktree, ownership, completed criteria, evidence paths, failing checks, risks, and next action. After compaction or resume, reload the checkpoint and verify the current git state and affected checks before acting.

Skill routing: `engineering-principles`, `plan-then-ship`, `adversarial-review`, `publish-to-github`, `project-sync`; `turing` for that repository. Read selected skill instructions at use time.
