# Owen's Agent System

Read `prompts/core.md` and `prompts/owen.md`, then the workflow relevant to the task. These are behavioral instructions, not additional permissions. Respect the host's instruction hierarchy and the user's current authorization.

For changes to this repository, use an isolated git worktree. Keep task artifacts in ignored `.oas/` folders. Validate with `python3 scripts/oas.py check` and `python3 -m unittest discover -s tests -v`. Never copy vault notes, credentials, or runtime account state into commits.

Maintain `config/` and its launcher together. Changes to permission behavior require negative-path tests and installed-runtime validation. Update sources when relying on new product behavior. Do not create another skill catalog here; use the canonical skills repository for reusable skills. Edits to `prompts/`, `workflows/`, `config/agents/`, or a skill description follow `docs/instruction-authoring.md`.

Do not claim an agent system is optimal or self-improving without comparative outcome evidence. Preserve the distinction between policy guidance, runtime controls, and observed behavior.

## Claude Code

The shared contract is already in Claude's global instructions after setup. Codex TOML settings do not apply to Claude. Use Claude's own permission controls; do not represent this kit's shell or connector restrictions as enforced there. Workflows are portable; runtime configuration is Codex-specific.
