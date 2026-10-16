# Context compaction and continuity

Compaction is lossy working-memory compression. The runtime summarizes older conversation so a long task can continue inside a finite model context window. The summary is useful continuity, but exact evidence, authorization, current external state, and test results belong in durable artifacts.

OAS leaves token accounting to each native runtime. Where a runtime takes a percentage of its own auto-compact window, setup sets Owen's trigger of 35 percent: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` in `~/.claude/settings.json` and `model.compressionThreshold` in `~/.gemini/settings.json`. A percentage of each runtime's own window keeps the same meaning across models. Codex takes only an absolute token count, which would be a different share of every model window, so Codex keeps its model-aware default. The Claude variable can only lower the trigger; Gemini needs a restart to apply it. The shared workflow supplies the portable part: checkpoint at completed phase boundaries, preserve explicit state, and verify volatile facts after compaction or resume.

## Native behavior

Reviewed 2026-09-07 against official documentation and the locally installed CLI help.

| Agent | Automatic behavior | Manual command | OAS behavior |
|---|---|---|---|
| Codex | Uses the selected model's native auto-compaction limit; an absolute `model_auto_compact_token_limit` override exists | `/compact` | Inherits the model-aware native limit; no fixed override; global post-compaction hook |
| Claude Code | Automatically compacts near its effective window | `/compact [focus]` | Passes `--autocompact auto` explicitly; setup sets a 35 percent trigger and a global post-compaction hook |
| Cursor Agent | Automatically summarizes older messages near capacity | `/summarize` (`/compress`) | Inherits native behavior; `preCompact` is observational and cannot change the trigger |
| GitHub Copilot CLI | Begins background compaction at about 80 percent and waits at about 95 percent if needed | `/compact [focus]` | Inherits native behavior and its saved compaction checkpoints |
| OpenCode | `compaction.auto` defaults to true and reserves room for compaction | `/compact` (`/summarize`) | Setup explicitly enables the global setting while preserving siblings; no project config is overwritten |

## Post-compaction hook for every session

The launcher reaches only sessions that `oas run` starts. Setup therefore also installs a native `SessionStart` hook with matcher `compact` in `~/.claude/settings.json` and `~/.codex/hooks.json`. Both runtimes add the hook's plain stdout to the model's context after automatic or manual compaction, so plain `claude`, the Claude desktop app's Code tab, and plain `codex` get the same continuity step. The hook runs `oas.py compact-context`, which prints the reload-and-reverify reminder and lists each open `.oas/*/task.json` checkpoint in the session's working directory (taken from the hook's stdin `cwd`). Setup keeps other hooks and replaces an older OAS hook in place. Codex asks the user to review and trust a new hook once through `/hooks`.

Claude Code on the web runs in a fresh cloud container where setup never ran. This repository's `.claude/settings.json` carries the same hook for cloud sessions that open this repository. It runs only when `CLAUDE_CODE_REMOTE` is `true`, so local sessions do not get the reminder twice. Other repositories need the same file to get it in the cloud. Claude chat and Cowork on claude.ai do not run Claude Code hooks, so they cannot get this hook.

| Agent | Post-compaction injection | OAS status |
|---|---|---|
| Claude Code (CLI and desktop Code tab) | `SessionStart` matcher `compact` | Installed globally by setup |
| Claude Code on the web | Same hook in a repository's `.claude/settings.json` | In this repository only |
| Claude chat and Cowork | No Claude Code hooks | Not possible |
| Codex | `SessionStart` matcher `compact`; must be trusted once | Installed |
| OpenCode | `experimental.session.compacting` plugin hook adds text to the compaction prompt | Not installed: experimental API, not validated here |
| pi | `session_before_compact` extension event can replace the summary | Not installed: OAS has no pi adapter yet |
| Gemini CLI | `PreCompress` only shows a message to the user; no post-compression event | Not possible; global GEMINI.md guidance only |
| Cursor Agent | `preCompact` is observational | Not possible; global rule only |
| Copilot CLI | `preCompact` is notification only | Not possible; global instructions only |

Hook behavior was checked against official documentation on 2026-10-15. Unit tests prove the installed command and its output; they do not prove that a given client version fires the hook.

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
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars) documents `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (1 to 100, lowers only); [Gemini CLI configuration](https://geminicli.com/docs/reference/configuration/) documents `model.compressionThreshold` (fraction, default 0.5, restart required).
- [Claude Code hooks](https://code.claude.com/docs/en/hooks) and [Codex hooks](https://learn.chatgpt.com/docs/hooks) document the `compact` session-start source and plain-stdout context injection; Codex documents hook trust. [Gemini CLI hooks](https://geminicli.com/docs/hooks/reference/), [Copilot hooks](https://docs.github.com/en/copilot/reference/hooks-reference), [OpenCode plugins](https://opencode.ai/docs/plugins/), and [pi extensions](https://pi.dev/docs/latest/extensions) document their compaction events.
- [OpenCode configuration](https://dev.opencode.ai/docs/config) documents automatic compaction, pruning, and reserved token space. Local help and resolved configuration still need validation after client upgrades.

These product behaviors can change with client versions and model catalogs. OAS checks prompt and command construction locally; it does not claim cross-provider summary quality or identical preservation behavior without end-to-end evaluation.
