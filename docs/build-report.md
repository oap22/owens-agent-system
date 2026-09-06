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
