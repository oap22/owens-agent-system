# Initial build verification

Date: 2026-09-06.

- Built in an isolated worktree of a new repository. Existing vault notes and the canonical skills repository were not changed.
- `python3 scripts/oas.py check`: passed for five profiles, three roles, and twelve evaluation scenarios.
- `python3 -m unittest discover -s tests -v`: 25 tests passed. Tests include permission defaults, all native adapter argument construction, file preservation, shell argument boundaries, task evidence validation, and unsupported unattended combinations.
- Codex prompt discovery: all five modes returned success from `codex debug prompt-input`, and the assembled shared instructions and current task were present. No model task was executed.
- Codex strict configuration diagnostics: all five profiles loaded and returned exit 0 with a proper terminal environment and network access. Existing optional MCP configuration warnings remain. `codex --version` reports 0.153.0 while `doctor` identifies a separate installed Homebrew runtime at 0.147.0; this version discrepancy is recorded, not treated as a single-version certification. The diagnostic sandbox summary is coarse and does not prove enforcement of every setting.
- Claude Code 2.1.259 and Cursor Agent 2026.08.11-e8db854: native options inspected through installed help. No live model execution or OS sandbox enforcement test performed for these adapters.
- Gemini CLI (adapter since removed) and Copilot CLI: official documentation checked; executables unavailable locally. Generated adapter arguments and bundles are covered by unit tests, not live end-to-end runs.
- Publication review: authored source files inspected; no source vault notes, credential files, account configuration, transcripts, or data exports included. No credential-pattern hits in the candidate files. No dedicated secret scanner was installed; pattern scanning is a heuristic rather than proof.

This establishes a tested workflow/configuration kit. It does not establish optimal model performance, cross-vendor permission equivalence, successful external integrations, or desktop adoption. The evaluation scenario bank is ready to run; no comparative agent-quality results are claimed.

## 2026-09-06 audit and optimization

- Measured before the change: after `setup.py --apply`, every global instruction file carried the managed block while the launcher still sent `prompts/core.md` and `prompts/owen.md` as the session prompt, so each `run` loaded the same guidance twice.

| mode | full prompt chars | workflow-only chars | redundant |
|---|---|---|---|
| development | 6401 | 1703 | 73% |
| research | 6328 | 1630 | 74% |
| ops | 6252 | 1554 | 75% |
| tutor | 5190 | 492 | 90% |
| unattended | 5513 | 815 | 85% |

- Changes: `--shared auto|always|never` on `preview`, `run`, and `bundle`; the Claude adapter passes guidance through `--append-system-prompt` with the task as the final prompt; `task --scenario ID`; an advisory skill-routing drift warning in `check`; `setup.py --rollback`; `check` invariants raised explicitly instead of with `assert`; UTF-8 encoding on all text reads and writes.
- `python3 scripts/oas.py check` and `python3 -O scripts/oas.py check`: passed.
- `python3 -m unittest discover -s tests -v`: 61 tests passed.
- Installed CLIs at this date: Codex 0.153.0, Claude Code 2.1.259, Cursor Agent 2026.08.11-e8db854, Gemini CLI 0.58.0 (adapter since removed), GitHub Copilot CLI 1.0.83, OpenCode 1.16.2. Launcher flags were checked against installed `--help` output. No live model run was performed.
- The prompt reduction and the Claude placement are structural de-duplication and alignment with the native convention. No model-quality gain is claimed or measured.

## 2026-09-07 tutor and unattended launch fix

Codex 0.153.0 rejected `apps._default.default_tools_enabled` at interactive startup as an unknown field, so tutor and unattended could not launch. Codex `doctor` with the same overrides reported no failure, and the initial build's `debug prompt-input` check cannot take `--strict-config`, so neither validation exercised the client's loader. The published config schema lists `enabled`, `approvals_reviewer`, `default_tools_approval_mode`, `destructive_enabled`, and `open_world_enabled` under `apps._default`; both profiles now use `enabled = false`. Verified by starting the real client with the tutor overrides in a pseudo-terminal and observing no config error. The launcher now pauses on the agent's own output after a non-zero exit instead of redrawing over it.

## 2026-09-07 live adapter verification

Each adapter was started once with the launcher's exact tutor-mode argv (open session, read-only) in a pseudo-terminal and its first 14 seconds of output captured, then terminated. Results on this machine:

| Adapter | Result |
|---|---|
| Codex 0.153.0 | Starts; waits at its directory-trust prompt |
| Claude Code 2.1.259 | Starts; waits at its folder-trust prompt |
| Cursor Agent 2026.08.11 | Starts; waits at its workspace-trust prompt |
| Gemini CLI 0.58.0 | Exits 1 after about 2.5 s with no message on screen. Headless mode explains it: no auth method is configured (no `~/.gemini/oauth_creds.json`, no `security.auth.selectedType`, no `GEMINI_API_KEY`). Not a launcher defect; login is a one-time user action. The launcher now shows `login needed` on the Gemini row and refuses to launch with the fix spelled out instead of letting Gemini vanish. |
| GitHub Copilot CLI 1.0.83 | Starts; shows its home screen |
| OpenCode 1.16.2 | Starts; shows its session screen |

No model turn was completed and no file was changed. Trust prompts are each CLI's own first-run behavior for a directory. Gemini was never verified past login; Owen cancelled the Gemini CLI subscription on 2026-09-07 and the adapter, its bundle target, its global-instruction install, and its settings patch were removed. Files the installer had already placed under `~/.gemini` are no longer managed and can be deleted by hand.

## 2026-09-07 Claude auto-mode mapping

Claude development and research changed from `acceptEdits` to native `auto`; ops now passes Claude's documented `default` value, which the client displays as Manual; tutor remains `plan`. The supplied settings select `auto` and continue to disable `bypassPermissions`. The local Homebrew installation was upgraded from Claude Code 2.1.39, which rejected `auto`, to 2.1.236. `claude --permission-mode auto --version` then exited 0, `claude auto-mode defaults` returned the classifier policy, and an interactive launch with the supplied settings visibly reported `auto mode on`. A separate ops launch visibly reported `manual mode on`, confirming the explicit flag overrides the settings default. The sessions were exited without a model turn and reported 0.0K tokens. A startup hook could not create its session environment under the validation harness's filesystem sandbox; this is unrelated to permission-mode parsing and remains a host-level integration warning rather than a clean end-to-end task run.

Earlier sections in this append-only report recorded Claude Code 2.1.259. That observation cannot be reconciled with the pre-upgrade binary and Homebrew symlink inspected for this change, both of which reported 2.1.39. Treat the earlier version labels as stale or from a different installation state; the auto-mode evidence in this section applies specifically to 2.1.236.
