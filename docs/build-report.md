# Initial build verification

Date: 2026-09-06.

- Built in an isolated worktree of a new repository. Existing vault notes and the canonical skills repository were not changed.
- `python3 scripts/oas.py check`: passed for five profiles, three roles, and twelve evaluation scenarios.
- `python3 -m unittest discover -s tests -v`: 25 tests passed. Tests include permission defaults, all native adapter argument construction, file preservation, shell argument boundaries, task evidence validation, and unsupported unattended combinations.
- Codex prompt discovery: all five modes returned success from `codex debug prompt-input`, and the assembled shared instructions and current task were present. No model task was executed.
- Codex strict configuration diagnostics: all five profiles loaded and returned exit 0 with a proper terminal environment and network access. Existing optional MCP configuration warnings remain. `codex --version` reports 0.153.0 while `doctor` identifies a separate installed Homebrew runtime at 0.147.0; this version discrepancy is recorded, not treated as a single-version certification. The diagnostic sandbox summary is coarse and does not prove enforcement of every setting.
- Claude Code 2.1.259 and Cursor Agent 2026.08.11-e8db854: native options inspected through installed help. No live model execution or OS sandbox enforcement test performed for these adapters.
- Gemini CLI and Copilot CLI: official documentation checked; executables unavailable locally. Generated adapter arguments and bundles are covered by unit tests, not live end-to-end runs.
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
- Installed CLIs at this date: Codex 0.153.0, Claude Code 2.1.259, Cursor Agent 2026.08.11-e8db854, Gemini CLI 0.58.0, GitHub Copilot CLI 1.0.83, OpenCode 1.16.2. Launcher flags were checked against installed `--help` output. No live model run was performed.
- The prompt reduction and the Claude placement are structural de-duplication and alignment with the native convention. No model-quality gain is claimed or measured.

## 2026-09-07 tutor and unattended launch fix

Codex 0.153.0 rejected `apps._default.default_tools_enabled` at interactive startup as an unknown field, so tutor and unattended could not launch. Codex `doctor` with the same overrides reported no failure, and the initial build's `debug prompt-input` check cannot take `--strict-config`, so neither validation exercised the client's loader. The published config schema lists `enabled`, `approvals_reviewer`, `default_tools_approval_mode`, `destructive_enabled`, and `open_world_enabled` under `apps._default`; both profiles now use `enabled = false`. Verified by starting the real client with the tutor overrides in a pseudo-terminal and observing no config error. The launcher now pauses on the agent's own output after a non-zero exit instead of redrawing over it.

## 2026-09-07 known issue: Gemini adapter

Owen reports the Gemini CLI does not launch from the launcher. Not yet reproduced or fixed; live verification of all six adapters is scheduled and not run. The adapters table in `docs/adapters.md` should be read with that caveat until this entry is replaced by results.
