# Owen's Agent System

A personal operating system for research, software development, everyday operations, and learning. Shared across coding agents, with native launch adapters for Codex, Claude Code, Cursor, Gemini CLI, and GitHub Copilot.

**The loop: Frame → Work → Prove → Hand off.** Every substantial task has an outcome, an ownership boundary, evidence, and a next action. Simple requests stay simple.

This is a working configuration and workflow kit, not a new hosted agent service or a trained model. It uses your existing agent accounts and skills. No API key, daemon, external scheduler, or paid service is created by setup.

## Start here

Requires Python 3.11+, Git, and the CLI for your chosen agent. See [[docs/adapters]] for tested versions and capability differences.

```sh
python3 scripts/oas.py check
python3 scripts/oas.py preview development --workspace /absolute/path/to/project --task "Fix the failing CSV import and verify it"
python3 scripts/oas.py run development --agent claude --workspace /absolute/path/to/project --task "Fix the failing CSV import and verify it"
```

`preview` prints the exact command and assembled instructions without starting an agent. `run` opens the selected agent in the target workspace with the same core instructions and its native permission controls. `--agent` defaults to `codex`; use `claude`, `cursor`, `gemini`, or `copilot` to switch. Existing account login, installed skills, and connectors remain available where that agent supports them. It does not overwrite your global configuration or project instructions. Choose a task worktree first for development; see [[workflows/development]].

| Mode | Use it for | Codex permission mapping |
|---|---|---|
| `development` | Implement, debug, test, review | Workspace writes, network escalation through auto-review |
| `research` | Literature, synthesis, experiment design | Workspace writes for artifacts, live web search, shell network restricted |
| `ops` | Daily planning, commitments, drafts, owned maintenance | Workspace writes; app tools prompt on writes |
| `tutor` | Coursework and research understanding | Read-only shell; one question at a time |
| `unattended` | Explicitly owned local jobs | Workspace writes, no approval escalation, app tools disabled |

```sh
python3 scripts/oas.py task research --output /absolute/path/to/project/.oas --title "Compare deblending baselines" --criterion "Each material claim has a source" --criterion "A reproducible next experiment is specified"
python3 scripts/oas.py run research --workspace /absolute/path/to/project --task "Use the task contract in .oas/<created-id>/task.json"
```

For IDE agents or another assistant, generate a standalone instruction bundle:

```sh
python3 scripts/oas.py bundle development --agent cursor --output /tmp/owen-cursor-bundle
python3 scripts/oas.py bundle research --agent generic --output /tmp/owen-generic-bundle
```

Bundles target `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot instructions, or Cursor rules. They are created in a fresh directory for review, so existing project files are never overwritten. The generic bundle can be attached or pasted into any agent that accepts instructions. Native controls differ; see [[docs/adapters]] before use.

## What is included

- `config/config.toml`: Codex permissions and bounded specialist roles.
- `adapters/`: agent-native settings; shared workflows remain in one place.
- `config/profiles/`: mode-specific settings; these are source layers, not legacy inline Codex profiles.
- `prompts/`: concise shared guidance and a sanitized working profile.
- `workflows/`: development, research, operations, tutoring, and unattended contracts.
- `scripts/oas.py`: launcher, configuration checks, task creation, and evidence validation.
- `evals/`: scenario bank and a measurable improvement protocol.
- `docs/sources.md`: current primary sources, adoption decisions, and limits of the evidence.

Your canonical skills remain in `~/Developer/active/skills`. This repository orchestrates them; it does not fork their implementations. Vault data stays in the vault. Personal task records belong in ignored `.oas/` folders.

## Quality bar

Run `python3 -m unittest discover -s tests -v` and `python3 scripts/oas.py check` before proposing changes. Run `python3 scripts/oas.py doctor development` to ask the installed Codex runtime to validate the effective config. That command also diagnoses unrelated local integrations; see [[docs/validation]].

The initial defaults are evidence-informed, not demonstrated optimal. Judge them against your own completed tasks using [[evals/README]]. Never promote a prompt change solely because its author says it improved.

See [[docs/architecture]], [[docs/permissions]], [[docs/setup]], and [[docs/personalization]] for the design and adoption path.
