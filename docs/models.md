# Current models and runtime selection

Reviewed 2026-09-15 against official documentation and installed CLI metadata. These are explicit choices and evaluation starting points, not hardcoded defaults or claims of optimal performance. OAS inherits the user's model unless `--model` is supplied.

| Model | Exact ID | Starting point |
|---|---|---|
| GPT-6 Astra | `gpt-6-astra` | Complex coding, reasoning, research, and agentic work. Preserve supported effort; compare `medium` and `high` on representative tasks. |
| Claude Opus 5 | `claude-opus-5` | General Claude coding and agentic baseline. Start at documented `high`, then evaluate lower effort for routine work. |
| Claude Fable 5.1 | `claude-fable-5-1` | Demanding reasoning and long-horizon work, including cases where Opus still misses acceptance criteria at higher effort. Start at documented `high`. |

[OpenAI's Astra model page](https://developers.openai.com/api/docs/models/gpt-6-astra) and [model guidance](https://developers.openai.com/api/docs/guides/latest-model) identify its workload and API settings. The installed app-bundled Codex advertises Astra with default `medium`. API and Codex offerings can expose different settings. OAS's portable effort interface remains `low` through `max`.

[Anthropic's Fable overview](https://platform.claude.com/docs/en/models/fable-5-1/overview) recommends Opus 5 for most workloads and Fable for harder work. [Its effort guide](https://platform.claude.com/docs/en/build-with-claude/effort) calls for fresh evaluation after upgrades. Opus 5's base API rates are $5/$25 per million input/output tokens; Fable 5.1's are $10/$50 with $0.25 cache reads. These are API rates, not subscription accounting or cost-per-task predictions.

For independent workers, evaluate lower effort on the selected model before assuming a smaller model wins. Candidate worker IDs such as `gpt-5.6-luna` or `claude-sonnet-5` require account and runtime support. Record the effective model and effort.

## Prompting implications

- Astra: clarify authorization, skill precedence, the requested outcome, and remaining blockers. Preserve the original task when new input steers ongoing work. Avoid repeated approval requests for authorized preparation. See [OpenAI's current guide](https://developers.openai.com/api/docs/guides/latest-model).
- Fable 5.1: batch independent tool calls, bound scope, and specify what compaction must preserve. See [its prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1).
- Opus 5: define acceptance criteria and a stopping condition instead of repeatedly exhorting verification. Anthropic documents [over-verification from older prompts](https://platform.claude.com/docs/en/models/opus-5/whats-new-opus-5). Required checks and permission boundaries still apply.

Shared instructions contain reusable constraints; model research and tuning advice stay in this on-demand document.

## Validate the actual runtime

The audit found three installed Codex copies and two Claude copies. Shell PATH selected older versions despite newer installed copies. OAS never silently switches binaries or installs updates.

Use `OAS_CODEX_BIN` or `OAS_CLAUDE_BIN` for explicit executable paths. The UI catalog, launch, preview, and doctor use the selection. Invalid paths fail without fallback. To persist a choice for OAS alone, preview `scripts/setup.py --codex-bin /absolute/path/to/codex --claude-bin /absolute/path/to/claude`, then add `--apply`. The wrapper preserves selections across reinstalls; environment overrides take precedence.

```sh
python3 scripts/oas.py doctor development --workspace /path/to/worktree \
  --model gpt-6-astra --lead-effort high \
  --worker-model gpt-5.6-luna --worker-effort low --worker-retry-effort medium
python3 scripts/oas.py preview development --agent claude --workspace /path/to/worktree \
  --model claude-fable-5-1 --lead-effort high --task 'Implement the criteria in .oas/task.json'
```

`doctor` validates the selected Codex executable with the same model, effort, roles, and workspace as a run. It cannot establish entitlement, inference quality, or child-agent behavior. Run a bounded representative task before treating a combination as evaluated. Claude's menu offers documented current IDs and aliases; Codex's menu uses the selected executable's catalog.
