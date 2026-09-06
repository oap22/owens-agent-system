# Development

1. Inspect repository instructions, git state, worktrees, and active ownership. Use an isolated task worktree. Never capture unrelated dirty changes in a commit.
2. Reproduce the problem or define an observable before/after behavior. For substantial changes write the acceptance criteria, architecture decisions, risks, and validation plan before implementation. Scale the document to the change; a trivial fix does not need a specification ceremony.
3. Use `plan-then-ship` when appropriate and available. Work in one issue/branch/worktree per change. Parallel builders, when authorized, must own distinct files or modules and know they are not alone.
4. Implement the smallest complete behavior. Test failure cases and meaningful boundaries. For a bug, prefer a regression that fails before and passes after. Do not add tests that merely restate constants or weaken tests to get green output.
5. Review the actual diff and requirement coverage. Use `adversarial-review` when applicable; report self-review honestly when no independent reviewer ran. Check native or target-platform behavior for platform-sensitive changes.
6. Commit only reviewed files. Push or open a PR when the request authorizes it. Honor repository CI, CODEOWNERS, and human review requirements before merge. Report separately: local checks, hosted CI, approval, merge, deployment.
7. Save a checkpoint with commit, worktree, completed criteria, failing checks, known risks, and next action. Never mark complete while required work remains.

Skill routing: `plan-then-ship`, `adversarial-review`, `publish-to-github`, `project-sync`; `turing` for that repository. Their current instructions are loaded at use time.
