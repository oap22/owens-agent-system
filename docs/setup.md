# Setup and adoption

1. Clone the private repository into `~/Developer/active/owens-agent-system` and install Python 3.11+ and the CLI for your chosen agent. Authenticate that agent using its normal login; no credentials belong here.
2. Run `python3 scripts/oas.py check` and the unit tests.
3. Run `python3 scripts/oas.py doctor development`. Inspect errors, including inherited configuration conflicts. Do not treat a successful TOML parse as proof of runtime enforcement.
4. Create a development worktree using the repository's workflow, or select the relevant research/ops artifact workspace. Run `preview`, inspect the assembled instruction and permission overrides, then `run`.
5. Start with one low-impact task. Observe writes, approval behavior, skill discovery, and the final artifact. Record failures in the evaluation bank before broad adoption.

The launcher passes config values directly, so no global installation is required. To use a named native Codex profile instead, use `python3 scripts/oas.py export development --output /absolute/path/to/owen-development.config.toml`. The command refuses to overwrite any existing file. Review the generated file, then place it at `$CODEX_HOME/owen-development.config.toml` (normally `~/.codex/`) and launch `codex --profile owen-development`. Current CLI 0.153.0 uses separate profile files; older `[profiles.name]` recipes should not be assumed compatible.

Exported role paths point to the permanent clone and must be regenerated if it moves. Exported settings do not contain the workflow prompt: give Codex the shared prompt and selected workflow, or use the launcher. Desktop profile support and discovery must be checked in that client. Never blindly replace `~/.codex/config.toml` or inject this system's instructions into every existing repository.

For portable use in Claude or another assistant, provide `prompts/core.md`, `prompts/owen.md`, and one workflow. Configure that tool's own permissions separately. No Claude permission adapter has been validated.

Rollback: stop the new session and start Codex normally. Because the launcher does not install or modify global settings, ordinary sessions retain their existing setup. Remove only a profile file you deliberately installed to undo that optional path; keep task records for provenance.

## Other agents

Use `run MODE --agent claude|cursor|gemini|copilot` with the same workspace and task arguments. Review [[docs/adapters]] for the native controls and installed-version evidence. A missing CLI is reported before launch.

For any IDE or unsupported CLI, `bundle MODE --agent generic --output /fresh/directory` emits a complete standalone instruction file. Choose a named agent to generate its discovery filename instead. Review/merge into the target project or attach the content to a session. A bundle does not install permissions or prove the client loaded it.

## Install across your local agents

From the permanent clone, preview and apply:

```sh
python3 scripts/setup.py
python3 scripts/setup.py --apply
```

The installer appends a marked shared-guidance section to each native global instruction file, adds Cursor's local user rule, exports five named Codex profiles, configures native permission defaults, and installs `~/.local/bin/oas`. It preserves explicit instructions outside the marked section. Claude's existing approval mode is retained, while bypass mode is disabled. Cursor's sandbox is enabled. Gemini gets sandboxed/default approvals. OpenCode allows local file operations and asks for other tools and external directories. Copilot's native default approvals are retained; its managed config file is not edited.

Existing files are backed up under `~/.local/state/owens-agent-system/backups/<run>/`, with a manifest recording which files were created and each original mode. Backups can contain private configuration, so keep them local. Re-running the installer updates the owned sections without duplication. It refuses unmanaged profile/executable collisions and symlink targets; ordinary partial write failures roll back.

After setup, start a new agent session to load the global instructions. For explicit workflow and permission selection, use `oas run development --agent claude --workspace /path/to/worktree --task "Your task"`, or `codex --profile owen-research`. OpenCode is also supported through `--agent opencode`. A normal agent launch gets the shared global instructions and selects a workflow by the request; it does not automatically activate a named Codex mode profile.

This installation does not authenticate new accounts or establish paid entitlements. Gemini/Copilot may require login at first launch. Existing model choices, credentials, plugins, hooks, and canonical skill installations remain in place. Cursor rules apply to Agent chat, not Tab completion or Bugbot.

To roll back, compare the current files with the backup manifest before restoring the matching backed-up file. Remove a newly created file only if its current SHA-256 still matches the manifest's installed hash; preserve any later edits. This installer does not uninstall CLI packages.
