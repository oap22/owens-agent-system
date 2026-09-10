# Token economy for heavy workflows

How to run a strong model at high or xhigh effort as the lead while cheaper implementors do the bulk work, without paying for the split when it does not earn its cost. Everything here is a starting configuration; the measurement protocol at the end decides whether it stays.

## What the evidence says

Anthropic's published cost-optimization runs (see [[docs/sources]]) make three claims that shape this design:

1. Effort is the first lever, model choice the last. On research and knowledge work the effort curve is nearly flat: `medium` matched the default accuracy at roughly 70 to 85 percent of the cost. On long-horizon coding it is a real tradeoff: about two points lost at `medium` for half the cost, about eight at `low` for a quarter. Sweep effort on the lead model before adding a second model.
2. An orchestrator with cheaper workers pays only when there is bulk to hand off: many independent pieces, ideally more than fit one context window. On such work it cost about 55 percent less than the frontier model alone. When the work is one dependent chain that fits in one context, the coordinator's own model at lower effort came out ahead in every measured case, because the split pays for a plan, a handoff, and a merge that one agent gets for free.
3. Run cheap, re-run failures expensive. With a usable failure signal (tests, a checker), running everything at `low` and re-running only failures at the default reached the same pass rate for about half the cost. This needs the check to be trustworthy and the failed cheap attempts to be counted.

Their numbers come from their tasks and their harness. They are a reason to try this shape, not proof it wins on Owen's work.

## The shape

Three stages, three effort settings, one model boundary.

| Stage | Who | Effort | Reads | Produces |
|---|---|---|---|---|
| Frame | Lead | `high`, `xhigh` for architecture or ambiguous scope | Instructions, git state, entry points, the failing check | Acceptance criteria, slice plan, one task packet per slice |
| Work | Implementor per slice | `low` first, `medium` if the slice failed once | The packet and its entry points only | Diff plus a report in the packet's return format |
| Prove | Lead | `high` | Diffs and check output, never implementor transcripts | Verified outcome, handoff, checkpoint |

Rules that keep the shape cheap:

- Delegate by packet, never by conversation. The lead writes [[templates/task-packet]] and reads the report. Nothing else crosses the boundary. A subagent starts with a fresh context in both Claude Code and Codex, so anything not in the packet does not exist for it.
- Delegate reading, not only writing. A slice that requires reading many files to change few is the best candidate: the bulk stays in the implementor's context and the lead receives a short report.
- Do not delegate a dependent chain. If slice B needs the result of slice A, the lead does A and B, or one implementor does both in sequence. Parallel packets must own disjoint paths.
- Escalate, do not loop. A packet carries a budget. An implementor that fails its check twice stops and reports. The lead then climbs one rung: with `--worker-retry-effort` an `implementor-retry` role exists on the same cheap model at higher effort, and the lead re-sends the packet to it exactly once; without that rung, or after it fails, the lead fixes the packet or does the slice itself. Never re-run the same packet twice on the same rung. The middle rung is the "run cheap, re-run failures expensive" claim above applied inside one session: the lead redoing a slice at `high` on the strong model is the most expensive path, so it should be the last one.
- Set the worker's effort explicitly. In Claude Code a subagent with no `effort` inherits the session's, so `--worker-model sonnet` alone runs the cheaper model at the lead's `high` or `xhigh`. The launcher passes whatever you give it; pair `--worker-model` with `--worker-effort`.
- Keep the lead's context stable. Shared guidance goes in the global instruction file (`setup.py --apply`), the workflow goes in the system prompt, the task comes last. This is the prefix order that prompt caching rewards and that `--shared auto` already produces. Claude Code documents that switching model or effort mid-session, connecting or disconnecting MCP servers, denying whole tools, and compacting all invalidate the cached prefix. So "xhigh to frame, then `/effort high` to work" costs one uncached re-read of the whole prefix at the switch; on a long session that is usually still cheaper than staying at `xhigh`, on a short one it is not. Pick the effort at launch when the task is short.
- Watch what every launch sends. `preview` prints an estimated token count for the guidance and the task, and `check` warns when any mode's guidance with shared prompts passes the budget in `scripts/oas.py` (`GUIDANCE_BUDGET_TOKENS`). The estimate is characters divided by 3.2, not a tokenizer; it exists to catch drift in `prompts/` and `workflows/`, which are paid on every turn of every session, cached or not. The 3.2 is measured, not assumed: on 2026-09-10 every mode's guidance, `prompts/core.md`, and `templates/task-packet.md` were sent as `--append-system-prompt` to `claude -p --output-format json`, and the input-token delta against the same call with nothing appended gave 3.14 to 3.25 characters per token on all seven prose samples (Python source tokenizes denser, about 2.5). The samples, the method, and the baseline are in `evals/token-calibration.json`, and the unit suite fails if the estimator drifts more than a tenth from those measurements. The earlier characters-divided-by-four figure undercounted the development guidance by 21 percent (1,962 estimated against 2,470 measured). Re-run the measurement when the tokenizer or the prompts change substantially; cost telemetry, not this estimate, decides a configuration.
- Cap tool output at the harness where it supports it. Claude Code documents a `bashOutputMaxChars` setting; its default was not checked here, so choose a value against the current docs before adding it to `adapters/claude/settings.json`. Until then the packet's "last ten lines" rule is the only cap on implementor output.
- Prefer targeted reads. Entry points in a packet, not "explore the codebase". Tail check output, do not paste whole logs. Summarize at slice boundaries, not mid-slice.

## Harness mapping

The launcher exposes three options on `preview` and `run`: `--lead-effort`, `--worker-model`, `--worker-effort`. The implementor role text lives once in `config/agents/implementor.toml` and is sent to whichever harness runs it.

| Harness | Lead effort | Implementor |
|---|---|---|
| Claude Code | `--effort LEVEL` (documented levels `low` to `max`; the documented default is `high`) | `--agents` inline JSON defining `implementor` with `model`, `effort`, a tool allowlist, and `maxTurns`; with `--worker-retry-effort` a second entry `implementor-retry` on the same model at that effort; the lead delegates by naming either |
| Codex | `-c model_reasoning_effort=LEVEL` | Role layer `agents.implementor` from `config/agents/implementor.toml`; with `--worker-model` or `--worker-effort` the launcher writes an overlay under the workspace's ignored `.oas/roles/` and points the role at it; `--worker-retry-effort` writes a second layer and registers `agents.implementor-retry` with a description |
| Cursor, Copilot, OpenCode | Not implemented; the options are refused | Same |

Codex's effort values are advertised by the selected model and are not enumerated in its published schema; `codex doctor` with the same overrides validates a value before a real run. The Codex `[agents.<name>]` entry documents only `config_file`, `description`, and `nickname_candidates`, and the role file is described as a config layer, so `model` and `model_reasoning_effort` in that layer are a reasonable reading of the schema, not a documented guarantee. Confirm with `python3 scripts/oas.py doctor development` before relying on it.

Model identifiers are never written into this repository. `--worker-model` takes whatever alias or identifier the harness accepts (`sonnet`, `haiku`, a full model name), and the choice is recorded in the evaluation log, not in config.

## Measuring it

Cost per completed task, not per request. A cheaper worker that needs a second pass or a lead rewrite is not cheaper. For each candidate configuration record, per task: harness, lead model and effort, worker model and effort, number of packets, packets escalated, wall clock, token or dollar telemetry where the harness reports it (Claude Code reports session cost; `--max-budget-usd` caps print-mode runs and counts subagent spend), pass or fail against the task's acceptance criteria, and substantive corrections by Owen.

Run the comparison on the same tasks with the lead model alone at `medium` and `high`. That is the baseline the split must beat. If the split loses on a task type, record that and stop delegating that type. Keep the log in an ignored `.oas/evals/` folder, per [[evals/README]].

The launcher records and reads that log. After each task:

```sh
python3 scripts/oas.py log-run --output /path/to/project/.oas --task <id-or-title> --harness claude --mode development --result pass \
  --lead-effort xhigh --worker-model sonnet --worker-effort low --retry-effort medium --packets 3 --escalated 1 --cost-usd 1.42 --minutes 18
python3 scripts/oas.py report-runs --output /path/to/project/.oas
```

`log-run` appends one JSON line to `.oas/evals/runs.jsonl`. `--cost-usd` is the figure the harness reports (Claude Code shows session usage under `/usage`; `--max-budget-usd` counts subagent spend but only in print mode); omit it when unknown, and the record stores null rather than zero. `report-runs` groups runs by configuration (harness, lead model and effort, worker model and effort, retry rung) and prints cost per completed task: every dollar spent under that configuration, failed runs included, divided by the tasks it completed. A configuration with any uncosted run reports `unknown` rather than a flattering partial average. Packets escalated, and corrections by Owen, sit beside it so a cheap configuration that needs rescue is visible.

Token counts alone do not decide. A configuration that saves tokens and gives back a correct answer is a regression. Critical boundary failures (lost work, false completion, unauthorized action) block promotion regardless of cost.
