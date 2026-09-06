# Evidence and design decisions

Reviewed 2026-09-06. These are primary engineering reports and official product documentation, not proof this configuration is optimal for Owen. Vendor results come from their own tasks and infrastructure.

| Source | Adopted here | Limit |
|---|---|---|
| [OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) | Sandbox, approval reviewer, app settings, role config files | Installed runtime validation remains necessary; user/organization layers can change the result |
| [OpenAI subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Bounded specialist roles and explicit delegation | Extra agents consume additional tokens; availability depends on the client |
| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Simple composable workflows before framework complexity | Published 2024; useful architecture evidence, not current API instructions |
| [Anthropic: Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Bounded independent questions, precise ownership, citation checking | Their internal research results do not transfer directly to coupled software edits |
| [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Incremental slices, explicit acceptance criteria, durable checkpoints | Their application example does not establish universal performance gains |
| [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Outcome-based checks, multiple grader types, regression scenarios | Subjective graders require calibration and human review |

Local evidence: Codex CLI 0.153.0 `--help` documents separate `<name>.config.toml` profiles, `-c` overrides, `--strict-config`, and `doctor`. The existing local configuration selects on-request approvals, auto-review, and workspace writes. No account-specific credentials or server configuration were copied.

Owen-specific design choices: three child slots, a separate tutoring mode, draft-first operations, no duplicated skill catalog, and Frame → Work → Prove → Hand off. These are initial hypotheses tailored to his stated preferences. Evaluate them before calling them improvements.

## Native adapter sources

- [Claude Code permissions](https://code.claude.com/docs/en/permissions) and [CLI reference](https://code.claude.com/docs/en/cli-usage): explicit edit/manual/plan modes and additional settings. Validated against installed CLI help; these are approval modes, not universal filesystem isolation.
- [Gemini CLI configuration](https://geminicli.com/docs/reference/configuration/): interactive prompt, approval mode, sandbox flag, and plan-mode availability caveat. Documentation-checked; CLI unavailable locally.
- [GitHub Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference): interactive prompt, plan mode, deny-tool patterns, and environment overrides. Documentation-checked; CLI unavailable locally.
- [Cursor rules](https://prod.cursor.com/help/customization/rules): project rule discovery. CLI flags additionally checked in installed Cursor Agent help, including sandbox, ask mode, and auto-review.

Instruction bundles use native filenames and the generic AGENTS.md convention. Supporting a filename or generating an argument list is not proof of successful model execution or permission parity across vendors.
