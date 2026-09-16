# Evidence and design decisions

Initial sources reviewed 2026-09-06; model and cache guidance refreshed 2026-09-15. These are primary engineering reports and official product documentation, not proof this configuration is optimal for Owen. Vendor results come from their own tasks and infrastructure.

| Source | Adopted here | Limit |
|---|---|---|
| [OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) | Sandbox, approval reviewer, app settings, role config files | Installed runtime validation remains necessary; user/organization layers can change the result |
| [OpenAI subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Bounded specialist roles and explicit delegation | Extra agents consume additional tokens; availability depends on the client |
| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Simple composable workflows before framework complexity | Published 2024; useful architecture evidence, not current API instructions |
| [Anthropic: Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Bounded independent questions, precise ownership, citation checking | Their internal research results do not transfer directly to coupled software edits |
| [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Incremental slices, explicit acceptance criteria, durable checkpoints | Their application example does not establish universal performance gains |
| [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Outcome-based checks, multiple grader types, regression scenarios | Subjective graders require calibration and human review |
| [Anthropic: Cost optimization cookbook](https://platform.claude.com/cookbook/cost-optimization-cost-optimization) and platform guide on cost and intelligence (reviewed 2026-09-07) | Effort before model; orchestrator pays only with bulk independent work; run cheap and re-run failures; cost per completed task | Their benchmarks and harness, not Owen's tasks; single-run differences of a point or two are noise |
| [Claude Code subagents](https://code.claude.com/docs/en/sub-agents), [model configuration](https://code.claude.com/docs/en/model-config), [CLI reference](https://code.claude.com/docs/en/cli-reference) | Subagent `model`, `effort`, `tools`, `maxTurns`; `--effort`; inline `--agents`; fresh subagent context returning only its final message; a subagent with no `effort` inherits the session's; `/effort` changes the level mid-session; `--max-budget-usd` counts subagent spend but applies to print mode only | Documentation-checked on 2026-09-07 and 2026-09-08; no live run of the delegation path in this repository |
| [Claude Code prompt caching](https://code.claude.com/docs/en/prompt-caching) | Stable context prefixes; model switches and runtime-dependent effort changes affect cache reuse; Fable 5.1 has supported cache-preserving effort changes from 2.1.260 | Refreshed 2026-09-15; provider and configuration exceptions apply; no speculative output or compaction setting added |
| [Codex config schema](https://developers.openai.com/codex/config-schema.json) | Model/effort overrides and role config layers | Selected Astra/worker layers passed installed-runtime config checks on 2026-09-15; no live delegated task or quality benchmark implied |
| [GitHub CLI manual: `gh issue create`](https://cli.github.com/manual/gh_issue_create) | `--repo`, `--title`, `--body-file`, and repeatable `--label`; the created issue URL is the last stdout line | Checked against installed gh 2.98.0 on 2026-09-16; a label must already exist in the repository, and the first live filing is the only runtime evidence |
| [Codex developer commands](https://developers.openai.com/codex/cli/slash-commands), [Claude Code context window](https://code.claude.com/docs/en/context-window), [Cursor summarization](https://docs.cursor.com/en/agent/chat/summarization), [Copilot CLI context management](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/context-management), and [OpenCode configuration](https://dev.opencode.ai/docs/config) | Native automatic compaction, manual commands, durable phase checkpoints, and post-compaction verification rather than a universal OAS threshold | Summaries are lossy and provider behavior changes; prompt/command checks do not establish cross-provider summary quality |

Local evidence: Codex CLI 0.153.0 `--help` documents separate `<name>.config.toml` profiles, `-c` overrides, `--strict-config`, and `doctor`. The existing local configuration selects on-request approvals, auto-review, and workspace writes. No account-specific credentials or server configuration were copied.

Owen-specific design choices: three child slots, a separate tutoring mode, draft-first operations, no duplicated skill catalog, and Frame → Work → Prove → Hand off. These are initial hypotheses tailored to his stated preferences. Evaluate them before calling them improvements.

## Native adapter sources

- [Claude Code permission modes](https://code.claude.com/docs/en/permission-modes), [permissions](https://code.claude.com/docs/en/permissions), and [CLI reference](https://code.claude.com/docs/en/cli-reference): `auto`, `default`, and `plan` mappings plus the distinction between classifier-backed auto mode and unrestricted bypass mode. Auto eligibility still depends on the installed client, plan, model, provider, and organization policy; these modes are not universal filesystem isolation.
- [GitHub Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference): interactive prompt, plan mode, deny-tool patterns, and environment overrides. Documentation-checked; CLI unavailable locally.
- [Cursor rules](https://prod.cursor.com/help/customization/rules): project rule discovery. CLI flags additionally checked in installed Cursor Agent help, including sandbox, ask mode, and auto-review.

Instruction bundles use native filenames and the generic AGENTS.md convention. Supporting a filename or generating an argument list is not proof of successful model execution or permission parity across vendors.

Local setup sources: [Claude global instructions](https://code.claude.com/docs/en/memory), [Copilot user instructions](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions), [Cursor local user rules](https://prod.cursor.com/help/customization/rules), [OpenCode global rules](https://opencode.ai/docs/rules/), and [OpenCode permissions](https://opencode.ai/docs/permissions/). The setup follows native discovery paths and keeps permission implementations separate.

## September 15 model audit

- [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), [current OpenAI guidance](https://developers.openai.com/api/docs/guides/latest-model): exact target, supported API effort, authority clarity, and completing authorized work.
- [Fable 5.1](https://platform.claude.com/docs/en/models/fable-5-1/overview), [prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1): explicit scope, batched reads, and durable compaction context.
- [Opus 5 changes](https://platform.claude.com/docs/en/models/opus-5/whats-new-opus-5), [effort](https://platform.claude.com/docs/en/build-with-claude/effort): stopping conditions, avoiding repeated verification prompts, and fresh effort comparisons.
- [Cost and intelligence](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence): lower effort and independent delegation are candidates to measure, not guaranteed savings.

These pages were opened from the primary providers. Model-specific advice is kept in [[docs/models]] and [[docs/token-economy]], outside the automatically loaded prompt. Runtime observations and acceptance evidence are in [[docs/audit-2026-09-15]].
