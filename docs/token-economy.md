# Token economy

Optimize cost per completed task. Start with one agent, explicit acceptance criteria, and appropriate effort. Current model IDs and source-backed starting points are in [[docs/models]].

## Reduce repeated work

- Load the selected workflow and relevant skill resources. `--shared auto` avoids resending current shared guidance installed globally. A stale installation cannot be deduplicated safely.
- Batch independent reads and searches. Save long output to a log; report relevant excerpts, command, and exit status. Do not hide an earlier failure behind a successful final line.
- Check a coherent completed change. Repeat checks only after edits, failures, or new evidence. Stop when required checks and requirement coverage are satisfied.
- Checkpoint completed phases. Native compaction is not durable task state. A million-token window is capacity, not an instruction to fill it.
- Tune effort before changing model or adding workers. OAS exposes the common levels `low`, `medium`, `high`, `xhigh`, and `max`; native extensions such as Codex's model-specific `ultra` are not portable and are not exposed.

Anthropic's [cost and intelligence study](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence) supports trying lower effort on capable models and retrying only failures with a reliable acceptance signal. Delegation can help large independent workloads, while coordination can make coupled tasks more expensive. These vendor workload results are not measured savings for this repository.

## Delegate when the split earns its cost

Delegation needs authorization. Use [[templates/task-packet]] for disjoint owned files, entry points, acceptance criteria, a budget, and a compact report. Keep coupled changes and intent decisions in the lead. Select the host's fresh-context option when available: Codex collaboration APIs can inherit history, so a new agent does not necessarily mean an empty context. Reuse a worker for related follow-ups.

Specify worker model and effort in comparisons; inherited settings can make a supposedly cheap worker expensive. OAS preserves omission as inheritance and never silently selects a cheaper model.

Diagnose failure before retrying. Missing access, wrong inputs, invalid checks, and unavailable models need correction rather than more effort. A configured `implementor-retry` role permits one higher-effort retry on the same model. It does not automatically dispatch work or enforce a total token budget. Count failed attempts and lead repair.

| Harness | Lead effort | Worker configuration |
|---|---|---|
| Claude Code | Native `--effort` | Inline `--agents` with model, effort, tools, `maxTurns`, and an optional retry role |
| Codex | `model_reasoning_effort` | Immutable role snapshots in `.oas/roles/` and an optional retry role |
| Cursor, Copilot, OpenCode | Not mapped by OAS | Worker options are refused |

`preview` calculates snapshot paths without writing. `run` and `doctor` publish complete snapshots atomically. Different model/effort settings get different files; modified snapshots are rejected. Keep `.oas/` ignored.

## Cache behavior is model and runtime specific

Keep stable guidance ahead of changing task data. Models have separate caches. [Claude Code's cache guide](https://code.claude.com/docs/en/prompt-caching) documents preserved effort changes for Fable 5.1 on supported direct API/subscription paths from 2.1.260; other providers and configurations have exceptions. [Claude API effort changes](https://platform.claude.com/docs/en/build-with-claude/effort) and [Astra configuration updates](https://developers.openai.com/api/docs/guides/latest-model) also offer cache-preserving mechanisms. OAS launches native clients and does not implement those APIs; native clients may expose different capabilities.

Leave native compaction thresholds model-aware. Checkpoint before context loss and reverify volatile state afterward. See [[docs/compaction]].

## Measure rather than guess

`preview` estimates OAS guidance and task size as characters divided by 3.2. `evals/token-calibration.json` records a historical Claude Sonnet 5 calibration, not an exact tokenizer for Astra, Fable, arbitrary code, or tools. `check` reports the largest guidance estimate and warns above its budget; tests enforce deliberate changes to that budget. Runtime instructions, plugins, tools, inherited history, and reasoning add costs.

Compare candidates on the same versioned task set and runtime. Include a single-agent baseline, completion quality, corrections, time, observed telemetry, and failed attempts. Use stable task IDs across retries and distinct IDs for independent trials.

```sh
python3 scripts/oas.py log-run --output /path/to/project/.oas --task csv-trial-1 \
  --harness claude --runtime-version 2.1.266 --cohort coding-v1 --mode development \
  --lead-model claude-opus-5 --lead-effort medium --result pass --minutes 18
python3 scripts/oas.py report-runs --output /path/to/project/.oas
```

Set `--cost-usd` only from telemetry. Missing cost stays unknown. Reports group by workflow, cohort, runtime version, and lead/worker settings. Every attempt contributes cost; repeated passes of one task count once. Non-finite numbers are rejected; legacy invalid costs become unknown. Older logs remain readable. Runs without a cohort or resolved model/effort are exploratory, not controlled comparisons.

Grouping does not make different task sets comparable. Lost work, unauthorized actions, or false completion block promotion regardless of savings.
