# Context compaction and continuity

Compaction is lossy working-memory compression. The runtime summarizes older conversation so a long task can continue inside a finite model context window. The summary is useful continuity, but exact evidence, authorization, current external state, and test results belong in durable artifacts.

OAS leaves token accounting and the trigger to each native runtime. Model context windows, output reserves, tool schemas, and available controls differ, so one OAS percentage would not mean the same thing across agents. The shared workflow supplies the portable part: checkpoint at completed phase boundaries, preserve explicit state, and verify volatile facts after compaction or resume.

## Native behavior

Reviewed 2026-09-07 against official documentation and the locally installed CLI help.

| Agent | Automatic behavior | Manual command | OAS behavior |
|---|---|---|---|
| Codex | Uses the selected model's native auto-compaction limit; an absolute `model_auto_compact_token_limit` override exists | `/compact` | Inherits the model-aware native limit; no fixed override |
| Claude Code | Automatically compacts near its effective window | `/compact [focus]` | Passes `--autocompact auto` explicitly |
| Cursor Agent | Automatically summarizes older messages near capacity | `/summarize` (`/compress`) | Inherits native behavior; `preCompact` is observational and cannot change the trigger |
| GitHub Copilot CLI | Begins background compaction at about 80 percent and waits at about 95 percent if needed | `/compact [focus]` | Inherits native behavior and its saved compaction checkpoints |
| OpenCode | `compaction.auto` defaults to true and reserves room for compaction | `/compact` (`/summarize`) | Setup explicitly enables the global setting while preserving siblings; no project config is overwritten |

Use the manual command before a large new phase of the same task when the current session is already full of exploration. Start a fresh session when the objective changes, the session has accumulated repeated wrong turns, or the compacted summary no longer contains enough trustworthy state.

## What the checkpoint preserves

- Requested outcome and remaining acceptance criteria.
- Authorization and ownership boundaries.
- Workspace, worktree, branch, commit, and owned or changed files.
- Decisions and their rationale.
- Evidence paths and the exact commands that produced them.
- Failing checks, unresolved claims, blockers, and next action.
- Mode-specific state such as research sources, operational cursors, or the learner's demonstrated answer.

Do not make the checkpoint a transcript. Large tool output stays in an artifact with a path and a short result. Credentials and private source material do not belong in the checkpoint.

## After compaction

1. Reload the task checkpoint and relevant repository instructions.
2. Verify live or volatile state rather than trusting the summary.
3. Re-read only the entry points needed for the next action.
4. Continue from the next incomplete criterion.

For bounded specialist work, needing repeated compaction is a signal that the task packet is too broad. Split the packet or return a blocker rather than turning a narrow researcher, reviewer, builder, or implementor into a second unbounded lead.

## Sources and limits

- [OpenAI developer commands](https://developers.openai.com/codex/cli/slash-commands) documents `/compact`; the [Codex configuration schema](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json) documents the token-limit override and scope.
- [Claude Code context window](https://code.claude.com/docs/en/context-window) documents automatic and focused manual compaction, reinjected instructions, recent-file reload, and limits on what survives.
- [Cursor summarization](https://docs.cursor.com/en/agent/chat/summarization), [CLI slash commands](https://prod.cursor.com/docs/cli/reference/slash-commands), and [hooks](https://prod.cursor.com/docs/hooks) document automatic summarization, `/summarize`, and the observational `preCompact` event.
- [GitHub Copilot CLI context management](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/context-management) documents the approximately 80/95 percent background behavior, structured summaries, and checkpoints.
- [OpenCode configuration](https://dev.opencode.ai/docs/config) documents automatic compaction, pruning, and reserved token space. Local help and resolved configuration still need validation after client upgrades.

These product behaviors can change with client versions and model catalogs. OAS checks prompt and command construction locally; it does not claim cross-provider summary quality or identical preservation behavior without end-to-end evaluation.
