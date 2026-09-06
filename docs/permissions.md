# Permissions

`config/config.toml` is a Codex configuration source. Workflow prose expresses intent; Codex's sandbox and approval engine enforce the supported runtime settings. Neither is a universal security boundary over every connected tool.

The default allows local workspace writes and restricts shell network access. Escalations use `on-request` with `auto_review`, matching Owen's preference for low-friction authorized work. Auto-review only handles eligible escalation requests; it does not examine every action already allowed inside the sandbox. The target workspace and normal temporary directories are writable; no additional personal directory is granted by this kit.

A workspace-write sandbox is not read isolation. Codex may read outside the workspace. Do not use this profile as a container for unknown code with sensitive host data. Additional protections for untrusted code must be provided by an isolated host/container and constrained credentials.

Research enables live web search, which is separate from shell networking. Tutor uses a read-only shell and disables app tools. Unattended disallows escalation and disables app tools; those settings do not revoke credentials from arbitrary MCP servers or hooks. Audit those before unattended use. No unattended schedule is installed.

App tool writes default to approval prompts. Ops routes those prompts to the user. Connector settings do not cover every MCP server, CLI, or UI action, and read-only role sandboxes constrain shell writes rather than all possible tools. User authorization and provider-side scopes remain necessary for outward-facing actions.

The launcher overlays the user's existing Codex environment. It retains existing skills, plugins, MCP servers, and hooks; it is not a sterile runtime. Organization requirements can restrict the result. Use `doctor`, inspect effective prompt/config in your installed client, and verify a disposable workspace before relying on permissions. No profile enables `danger-full-access` or a sandbox bypass.

The repository does not set a model. Owen's current selection is inherited, avoiding stale model IDs and surprise cost changes. Select another model explicitly in Codex when needed and record it during evaluations.

For non-Codex agents, use the explicit native mappings in [[docs/adapters]]. The shared workflow is not an instruction to use a different vendor's permission settings. In Codex, `apps._default` is a default: explicit per-app settings inherited from the user's configuration can override it. Inspect those settings before relying on app defaults, especially for unattended use.
