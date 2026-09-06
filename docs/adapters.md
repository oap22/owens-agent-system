# Agent adapters

The shared system is portable. Permission enforcement and session management belong to each agent's runtime. All direct launch commands are interactive and avoid blanket tool-approval flags. None changes a model selection, installs a connector, or creates a subscription.

| Agent | Launch adapter | Instruction bundle | Permission mapping | Validation |
|---|---|---|---|---|
| Codex | `--agent codex` | `AGENTS.md` | Explicit TOML overrides; workspace sandbox, auto-review; tutor read-only | Strict config/runtime checks; see build report |
| Claude Code | `--agent claude` | `CLAUDE.md` | `acceptEdits` for dev/research, `manual` for ops, `plan` for tutoring; bypass disabled in supplied settings | Installed 2.1.259 help checked; no paid model run |
| Cursor Agent | `--agent cursor` | `.cursor/rules/owen-agent-system.mdc` | Sandbox enabled; auto-review for dev/research; ask mode for tutoring | Installed 2026.08.11-e8db854 help checked; no model run |
| Gemini CLI | `--agent gemini` | `GEMINI.md` | Sandbox requested; default approvals; tutor plan mode | Official docs checked; not installed locally; plan mode may require experimental planning |
| GitHub Copilot CLI | `--agent copilot` | `.github/copilot-instructions.md` | Interactive approvals inherited; tutor plan with shell/write tools denied | Official docs checked; not installed locally; no OS sandbox configured by adapter |
| Any other agent | `bundle --agent generic` | `AGENTS.md` | Configure its own native controls | Prompt compatibility only |

For example:

```sh
python3 scripts/oas.py preview development --agent claude --workspace /path/to/worktree --task "Implement the agreed feature"
python3 scripts/oas.py run research --agent gemini --workspace /path/to/research --task "Compare these methods with citations"
python3 scripts/oas.py bundle ops --agent copilot --output /tmp/owen-copilot-ops
```

The CLI checks whether the executable exists before launch. Older clients may reject a current flag; update or use the reviewed bundle, never remove permission controls merely to make a command start. For generic/IDE use, merge generated instructions with existing workspace guidance deliberately. Do not overwrite a repository's engineering instructions.

Unattended launch is implemented only for Codex's explicit no-escalation profile, and still requires an audit of inherited hooks and MCP tools. Other adapters refuse that combination. The unattended workflow can be exported as a bundle for a separately audited native automation. A universal no-prompt flag would not provide equivalent protections.

Agent switches should use the task contract and handoff artifact, not copy a whole private transcript. The next agent verifies current files and evidence rather than trusting the previous agent's completion claim. Specialist roles are native Codex definitions today; other agents can use the same role contracts through their own delegation facilities when authorized.

All adapters inherit existing runtime configuration and credentials. Copilot allow-all/autopilot environment overrides are explicitly rejected, but project/global tool grants in any client still need inspection. Plan/ask modes can allow internal planning artifacts and tool-specific behavior; they are not an OS-level write barrier over arbitrary connectors.

OpenCode now has a launch adapter (`--agent opencode`) and global guidance at `~/.config/opencode/AGENTS.md`. Development uses its built-in build agent; tutoring uses plan. Native permission defaults are applied by the local setup script, not by Codex TOML. Installed OpenCode 1.16.2 launch options and resolved configuration were checked during setup. No cross-provider model execution is implied.

The local setup also installs global guidance for all six agents. Gemini 0.58.0 and GitHub Copilot CLI 1.0.83 are now installed locally; this supersedes the initial build's absent-executable status. Authentication and an actual task remain separate checks.
