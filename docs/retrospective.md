# Retrospectives

After the hand off of a substantial session, the lead looks back, writes a report, and files one issue that another agent can implement without asking questions. This is the proposal path that `prompts/core.md` requires for instruction changes: a failure example, its root cause, and a bounded change. It is not self-improvement. An issue is evidence that someone looked; whether the change helps is measured under [[evals/README]] before it is promoted.

## When

Every mode, after Hand off and before the session ends. Simple requests that finished in one turn do not need one. When the mode cannot write files or run commands (tutoring, a read-only shell), the lead gives the same report in the conversation and names the issue to file; Owen or a later development session files it.

## The report

`templates/retrospective.md` fixes the shape, and `verify-retro` enforces it:

- Header facts: task, mode, harness, effective model and effort, workspace, date, outcome, corrections by Owen, cost and time. Unknown cost stays `unknown`; it is never zero.
- What went well: observed behavior and the instruction, skill, or tool that produced it. Praise without a cause is not useful.
- What went wrong: each item carries the observed behavior, the expected behavior, evidence (a path, command, or quoted line), and what it cost in minutes, retries, or corrections.
- Root causes: each failure attributed to a layer. Policy guidance (`prompts/`, `workflows/`, a skill), runtime controls (`config/`, `adapters/`, native permission modes), tooling (`scripts/`), or observed model behavior that no instruction addressed. Keep the layers distinct; a permission gap is not a prompt problem.
- Proposed change: one change, sized for one pull request.

## The proposal bar

The issue is written for an agent that has never seen the session. It must name:

- Files to change, each as a backticked path with what changes there. "Explore the codebase" is not a file.
- Implementation steps an agent can execute in order without asking a question.
- Acceptance criteria that distinguish done from plausible.
- Validation commands. At minimum the kit's own `check` and unit tests; add the negative-path test for a permission change.
- Out of scope, so the implementer does not widen the change.

If nothing is worth changing, write the summary line exactly as `No change proposed.`; verification passes and no issue is opened. Do not invent a change to fill the section. Do not file two proposals from one session; keep the second in the report's root causes and file it after the first lands.

## Commands

```sh
python3 scripts/oas.py retro --output /path/to/project/.oas --title "Fix the failing CSV import" \
  --mode development --harness claude --model claude-fable-5-1@high --workspace /path/to/project \
  --outcome pass --corrections 2 --minutes 40
python3 scripts/oas.py verify-retro /path/to/project/.oas/retros/<id>/retrospective.md
python3 scripts/oas.py retro-issue /path/to/project/.oas/retros/<id>/retrospective.md --dry-run
python3 scripts/oas.py retro-issue /path/to/project/.oas/retros/<id>/retrospective.md
```

`retro` scaffolds the report with the facts given and leaves the rest as placeholders. `verify-retro` rejects unfilled placeholders, missing sections, a proposal without files, steps, criteria, or validation, a summary too long for an issue title, a body over GitHub's limit, and lines shaped like credentials. It checks structure, not judgment.

`retro-issue` verifies, renders the issue, writes the exact body to `issue-body.md` beside the report, and runs `gh issue create` with the label `retrospective`. The issue title is the proposal summary. Its body opens with the reason, then the problem, root causes, and the five proposal fields; the full report follows in a collapsed block. On success it writes `issue.json` with the URL and refuses to file the same retrospective twice. `--dry-run` prints the title, body, and command without opening anything. `OAS_GH_BIN` selects a specific `gh` binary, like the agent runtimes.

## Where the issue goes

The default repository is this kit's own `origin`, because a retrospective proposes a change to the agent system, not to the project the task ran in. Pass `--repo OWNER/NAME` to file elsewhere; that needs explicit authorization under `prompts/owen.md`. The label must exist in the target repository; `gh` fails otherwise, and no record is written.

The issue is public when the repository is public. Retrospectives may quote commands and error lines from the session. They must not carry vault notes, private transcripts, account state, or credentials; the credential check is a heuristic on token shapes, not a guarantee. Keep the report in the ignored `.oas/` folder.

## Limits

- `gh` must be installed and logged in with `repo` scope. The launcher never uses a shell and never stores a token.
- An issue is a proposal. It grants no authorization to change instructions, permissions, or tests; those changes go through the development workflow with review.
- The retrospective is the lead's self-assessment. Corrections by Owen and the run log (`log-run`) are the comparative evidence; the report is context for them.
- Two sessions can reach opposite proposals. Close the losing issue with the reason rather than merging both.
