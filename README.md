# Owen's Agent System

A personal operating system for research, software development, everyday operations, and learning. Shared across coding agents, with native launch adapters for Codex, Claude Code, Cursor, GitHub Copilot, and OpenCode.

**The loop: Frame → Work → Prove → Hand off → Reflect.** Every substantial task has an outcome, an ownership boundary, evidence, a next action, and a retrospective that files one implementation-ready issue. Simple requests stay simple.

This is a working configuration and workflow kit, not a new hosted agent service or a trained model. It uses your existing agent accounts and skills. No API key, daemon, external scheduler, or paid service is created by setup.

## Start here

Requires Python 3.11+, Git, and the CLI for your chosen agent. See [[docs/adapters]] for tested versions and capability differences.

```sh
python3 scripts/oas.py check
python3 scripts/oas.py preview development --workspace /absolute/path/to/project --task "Fix the failing CSV import and verify it"
python3 scripts/oas.py run development --agent claude --workspace /absolute/path/to/project --task "Fix the failing CSV import and verify it"
```

For substantial work, start with one agent at appropriate effort. When delegation is authorized and the slices are independent, configure a worker explicitly:

```sh
python3 scripts/oas.py run development --agent claude --workspace /absolute/path/to/project --task "Use the task contract in .oas/<id>/task.json" --lead-effort high --worker-model claude-sonnet-5 --worker-effort low
```

`--lead-effort` sets the lead session's reasoning effort; `--worker-model` and `--worker-effort` define the `implementor` role (a Claude Code subagent passed inline, or a Codex role layer written under the workspace's ignored `.oas/roles/`). Set both: a Claude Code subagent with no effort of its own inherits the lead's. Add `--worker-retry-effort medium` to launch a second rung, `implementor-retry`, on the same cheap model at higher effort; the lead re-sends a failed packet to it once before taking the slice itself. Codex and Claude only; other adapters refuse the options. The lead delegates by task packet and verifies from diffs, per [[docs/token-economy]] and [[templates/task-packet]]. Model choices remain explicit; current examples and tuning guidance are in [[docs/models]].

`preview` also prints an estimated token count for the guidance and task it would send. After a task, `python3 scripts/oas.py log-run --output /path/.oas ...` records the configuration, result, and cost, and `report-runs` prints cost per completed task by configuration, which is the number that decides whether the split stays.

## Reflect after the session

After the hand off, the lead writes a retrospective and files it as a GitHub issue that another agent can implement without asking questions:

```sh
python3 scripts/oas.py retro --output /absolute/path/to/project/.oas --title "Fix the failing CSV import" --mode development --harness claude --outcome pass --corrections 1
python3 scripts/oas.py verify-retro /absolute/path/to/project/.oas/retros/<id>/retrospective.md
python3 scripts/oas.py retro-issue /absolute/path/to/project/.oas/retros/<id>/retrospective.md
```

`retro` scaffolds `templates/retrospective.md` with the known session facts: what went well, what went wrong with evidence, root causes by layer, and one proposed change with files, steps, acceptance criteria, validation, and scope. `verify-retro` refuses unfilled placeholders, a proposal an agent could not act on, and lines shaped like credentials. `retro-issue` opens the issue through `gh` in this repository by default, labeled `retrospective`, records the URL in `issue.json`, and will not file the same report twice; `--dry-run` prints what it would send. A summary of exactly `No change proposed.` skips the issue. The issue is a proposal with a failure example, not authorization and not evidence of improvement. See [[docs/retrospective]].

`preview` prints the planned command and assembled instructions without starting an agent or writing files. Worker snapshot paths are materialized by `run` or `doctor`. `run` opens the selected agent in the target workspace with the same core instructions and its native permission controls. `--agent` defaults to `codex`; use `claude`, `cursor`, `copilot`, or `opencode` to switch. `--model ALIAS_OR_ID` picks the session model through the agent's native flag; omit it to inherit your current default. Both accept `--shared auto|always|never` (default `auto`): `auto` omits `prompts/core.md` and `prompts/owen.md` when the agent's global instruction file already contains the current managed block, `always` sends them regardless, and `never` omits them; the workflow and task are always sent. Existing account login, installed skills, and connectors remain available where that agent supports them. It does not overwrite your global configuration or project instructions. Choose a task worktree first for development; see [[workflows/development]].

| Mode | Use it for | Codex permission mapping |
|---|---|---|
| `development` | Implement, debug, test, review | Workspace writes, network escalation through auto-review |
| `research` | Literature, synthesis, experiment design | Workspace writes for artifacts, live web search, shell network restricted |
| `ops` | Daily planning, commitments, drafts, owned maintenance | Workspace writes; app tools prompt on writes |
| `tutor` | Coursework and research understanding | Read-only shell; one question at a time |
| `unattended` | Explicitly owned local jobs | Workspace writes, no approval escalation, app tools disabled |

```sh
python3 scripts/oas.py task research --output /absolute/path/to/project/.oas --title "Compare deblending baselines" --criterion "Each material claim has a source" --criterion "A reproducible next experiment is specified"
python3 scripts/oas.py task tutor --scenario coursework --output /absolute/path/to/project/.oas
python3 scripts/oas.py run research --workspace /absolute/path/to/project --task "Use the task contract in .oas/<created-id>/task.json"
```

`task --scenario ID` prefills the mode, title, and criteria from `evals/scenarios.json`; explicit `--title` and `--criterion` still work without it.

Long sessions use each agent's native automatic context compaction. OAS preserves continuity through schema-version-2 task checkpoints at completed phase boundaries and requires volatile state to be reverified afterward; it does not impose one threshold across different model windows. Claude launches with `--autocompact auto`, setup enables OpenCode's native automatic setting, and the other adapters retain their model-aware defaults. See [[docs/compaction]] for manual commands, preservation rules, and provider limits.

For IDE agents or another assistant, generate a standalone instruction bundle (`bundle` defaults to `--shared always`):

```sh
python3 scripts/oas.py bundle development --agent cursor --output /tmp/owen-cursor-bundle
python3 scripts/oas.py bundle research --agent generic --output /tmp/owen-generic-bundle
```

Bundles target `AGENTS.md`, `CLAUDE.md`, Copilot instructions, or Cursor rules. They are created in a fresh directory for review, so existing project files are never overwritten. The generic bundle can be attached or pasted into any agent that accepts instructions. Native controls differ; see [[docs/adapters]] before use.

## Interactive launcher

Run bare `oas` on an interactive terminal, or `oas ui` explicitly, to pick mode, agent, and workspace from full-screen panels instead of typing flags. Arrow keys and Enter move through the mode, agent, and model lists (`inherit` keeps the agent's own default; Codex, Cursor, and OpenCode list their live catalogs, Claude documented current IDs and aliases, and a last row takes a typed id); choosing a workspace launches immediately, and a directory browser is available when the workspace you want is not under `~/Developer/active`. The session opens without a task: Claude starts with the workflow in its system prompt and waits for you, and agents that need an opening message get a one-line instruction to follow the workflow for your next request. Launching runs the same `run` path underneath, so behavior and permissions are identical to the flag form, and a green `oas:` banner line naming the agent, workspace, and workflow stays in scrollback above the session as a record of what was passed. `--plain` (or the `NO_COLOR` environment variable) drops the matrix-rain background and colors and keeps the same keys and flow, for accessibility or a plain terminal. Nothing is written to disk by the launcher; screen selections live only in memory for that run. `oas` with no arguments on a non-interactive stream (a script, CI, a pipe) is unchanged: it prints the usual argparse usage error and exits 2.

## What is included

- `config/config.toml`: Codex permissions and bounded specialist roles, including the `implementor` role shared with Claude Code delegation.
- `adapters/`: agent-native settings; shared workflows remain in one place.
- `config/profiles/`: mode-specific settings; these are source layers, not legacy inline Codex profiles.
- `prompts/`: concise shared guidance and a sanitized working profile.
- `workflows/`: development, research, operations, tutoring, and unattended contracts.
- `templates/`: task contract, task packet, handoff, claim ledger, and retrospective outlines.
- `scripts/oas.py`: launcher, configuration checks, task creation, evidence validation, the run log (`log-run`, `report-runs`), and retrospectives (`retro`, `verify-retro`, `retro-issue`).
- `evals/`: scenario bank and a measurable improvement protocol.
- `docs/sources.md`: current primary sources, adoption decisions, and limits of the evidence.

Your canonical skills remain in `~/Developer/active/skills`. This repository orchestrates them; it does not fork their implementations. Vault data stays in the vault. Personal task records belong in ignored `.oas/` folders.

## Quality bar

Run `python3 -m unittest discover -s tests -v` and `python3 scripts/oas.py check` before proposing changes. Run `python3 scripts/oas.py doctor development` to ask the installed Codex runtime to validate the effective config. That command also diagnoses unrelated local integrations; see [[docs/validation]].

The initial defaults are evidence-informed, not demonstrated optimal. Judge them against your own completed tasks using [[evals/README]]. Never promote a prompt change solely because its author says it improved.

See [[docs/architecture]], [[docs/permissions]], [[docs/setup]], [[docs/personalization]], [[docs/models]], [[docs/audit-2026-09-15]], [[docs/token-economy]], and [[docs/retrospective]] for the design and adoption path.

## Use it in your normal agent sessions

Run `python3 scripts/setup.py` to preview global setup, then `python3 scripts/setup.py --apply` from the permanent clone. This installs shared guidance for Codex, Claude Code, Cursor, GitHub Copilot CLI, and OpenCode, preserves existing personal instructions, and creates local backups. After setup, the launcher detects the installed block and sends only the workflow and task. `python3 scripts/setup.py --rollback BACKUP_DIR` previews a rollback and `--apply` executes it. See [[docs/setup]] for permission changes, login requirements, and rollback.
