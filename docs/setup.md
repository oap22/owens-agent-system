# Setup and adoption

1. Clone the private repository into `~/Developer/active/personal/owens-agent-system` and install Python 3.11+ and the CLI for your chosen agent. Authenticate that agent using its normal login; no credentials belong here.
2. Run `python3 scripts/oas.py check` and the unit tests.
3. Run `python3 scripts/oas.py doctor development`. Inspect errors, including inherited configuration conflicts. Do not treat a successful TOML parse as proof of runtime enforcement.
4. Create a development worktree using the repository's workflow, or select the relevant research/ops artifact workspace. Run `preview`, inspect the assembled instruction and permission overrides, then `run`.
5. Start with one low-impact task. Observe writes, approval behavior, skill discovery, and the final artifact. Record failures in the evaluation bank before broad adoption.

The launcher passes config values directly, so no global installation is required. To use a named native Codex profile instead, use `python3 scripts/oas.py export development --output /absolute/path/to/owen-development.config.toml`. The command refuses to overwrite any existing file. Review the generated file, then place it at `$CODEX_HOME/owen-development.config.toml` (normally `~/.codex/`) and launch `codex --profile owen-development`. Current CLI 0.153.0 uses separate profile files; older `[profiles.name]` recipes should not be assumed compatible.

Exported role paths point to the permanent clone and must be regenerated if it moves. Exported settings do not contain the workflow prompt: give Codex the shared prompt and selected workflow, or use the launcher. Desktop profile support and discovery must be checked in that client. Never blindly replace `~/.codex/config.toml` or inject this system's instructions into every existing repository.

For portable use in Claude or another assistant, provide `prompts/core.md`, `prompts/owen.md`, and one workflow. Configure that tool's own permissions separately. The Claude adapter maps development and research to native `auto`, ops to `default`, and tutoring to `plan`; `adapters/claude/settings.json` keeps bypass mode disabled, and the launcher passes `--autocompact auto`. The installed Claude Code client must support and be eligible for these modes. Argument parsing and JSON validation do not prove provider-side eligibility, classifier behavior, or summary quality.

Rollback: stop the new session and start Codex normally. Because the launcher does not install or modify global settings, ordinary sessions retain their existing setup. Remove only a profile file you deliberately installed to undo that optional path; keep task records for provenance.

## Other agents

Use `run MODE --agent claude|cursor|copilot|opencode` with the same workspace and task arguments. Review [[docs/adapters]] for the native controls and installed-version evidence. A missing CLI is reported before launch.

For any IDE or unsupported CLI, `bundle MODE --agent generic --output /fresh/directory` emits a complete standalone instruction file. Choose a named agent to generate its discovery filename instead. Review/merge into the target project or attach the content to a session. A bundle does not install permissions or prove the client loaded it.

## Install across your local agents

From the permanent clone, preview and apply:

```sh
python3 scripts/setup.py
python3 scripts/setup.py --apply
```

The installer appends a marked shared-guidance section to each native global instruction file, adds Cursor's local user rule, exports five named Codex profiles, configures native permission defaults, and installs `~/.local/bin/oas`. It preserves explicit instructions outside the marked section. Claude's global default mode is retained and bypass mode is disabled; the OAS launcher selects `auto`, `default`, or `plan` per workflow and explicitly enables native auto-compaction. Cursor's sandbox is enabled. OpenCode allows local file operations, asks for other tools and external directories, and has native automatic compaction enabled while other compaction settings are preserved. Copilot's native default approvals and compaction are retained; its managed config file is not edited.

Existing files are backed up under `~/.local/state/owens-agent-system/backups/<run>/`, with a manifest recording which files were created and their original and installed modes. Backups can contain private configuration, so keep them local. Re-running the installer updates the owned sections without duplication. It refuses unmanaged profile/executable collisions and symlink targets. After a partial write failure, recovery restores untouched writes and preserves content or permission edits, symlink replacements, and deletions made concurrently. It reports any skipped recovery and the backup location while retaining the original failure.

After setup, start a new agent session to load the global instructions. For explicit workflow and permission selection, use `oas run development --agent claude --workspace /path/to/worktree --task "Your task"`, or `codex --profile owen-research`. OpenCode is also supported through `--agent opencode`. A bare agent launch gets the shared global instructions but does not get OAS's per-workflow permission flags: in particular, bare `claude` retains the user's existing global default, which may still be `acceptEdits`. Use `oas` when the `auto`/Manual/`plan` mapping is required.

This installation does not authenticate new accounts or establish paid entitlements. Copilot may require login at first launch. Existing model choices, credentials, plugins, hooks, and canonical skill installations remain in place. Cursor rules apply to Agent chat, not Tab completion or Bugbot.

To roll back, run `python3 scripts/setup.py --rollback ~/.local/state/owens-agent-system/backups/<run>` to preview, then add `--apply` to execute. It restores an original or removes an installer-created file only while its SHA-256 and mode match the installed values. Modified files are kept, including preexisting files. Older manifests without an installed mode retain their byte-only comparison. Rollback rechecks its complete plan before writes and restores recorded modes. The backup directory is never deleted. This installer does not uninstall CLI packages.

## Select an installed runtime

`OAS_CODEX_BIN` and `OAS_CLAUDE_BIN` select absolute executable paths for OAS without changing the shell PATH or other applications. Invalid selections fail without fallback. `setup.py --codex-bin PATH --claude-bin PATH` previews persistent choices in the OAS wrapper; add `--apply` to install. Later setup runs preserve these choices, and environment overrides take precedence. See [[docs/models]] for the audited versions and current models.

`doctor MODE --workspace PATH --model ID --lead-effort LEVEL` uses that selected executable and the same workspace/configuration as launch. It also accepts `--worker-model`, `--worker-effort`, `--worker-retry-effort`, and `--worker-retry-model` and creates the immutable role snapshots to validate. Native client startup and account eligibility remain separate checks.
