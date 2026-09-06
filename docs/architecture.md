# Architecture

The lead assistant is the interface. A compact shared contract sets working behavior; one mode supplies the workflow; existing skills supply procedures; tools supply real capabilities. A task contract carries state across sessions. Verification closes the loop.

For Codex, the Python launcher merges the common TOML with one mode, resolves specialist config paths, and passes explicit values through Codex's `-c` interface. It supplies the shared guidance as the initial task prompt so it does not replace Codex's built-in developer instructions. Target workspace `AGENTS.md` remains in effect. This design avoids maintaining a separate account or copying credentials.

The three specialists are capabilities, not an always-running organization: researcher investigates one question, builder owns one implementation slice, reviewer looks for concrete failure. Delegation needs authorization from the user or applicable workspace instructions and a useful independent task. The configured cap is three child threads; the lead makes four total.

The task state separates planned, active, blocked, and complete. Each criterion has evidence and a boolean result. The evidence checker checks the record's structure and existence of local evidence; it cannot establish that a paper is correct or an agent's judgment is sound. Completion claims remain the lead's responsibility.

A candidate workflow earns promotion through repeated task outcomes: completion, correctness, unnecessary interruptions, recovery behavior, elapsed time, and cost where available. Changes live on a branch and preserve a rollback commit. No autonomous rewriting of active permissions or test criteria.

This kit intentionally leaves scheduling to the existing automation host and experiment execution to the existing research tooling. Those integrations require live verification. It does not add a second task database, skill installer, or multi-provider inference router.

## Agent portability

Every adapter consumes the same assembled core, Owen profile, selected workflow, and task. Native instruction bundles flatten that same source for IDE discovery. There is one workflow implementation, not five independently drifting prompts. Task JSON and handoff artifacts contain no vendor session IDs and can be continued by another agent.

The launcher checks whether the target agent's global instruction file already contains the current managed block with the shared prompts. When it does, `run` sends only the workflow and task and states that the shared guidance is loaded globally; when it does not, or when `--shared always` is given, the full prompt is sent. For Claude Code, guidance goes through `--append-system-prompt` and the task is the user turn, matching how that client treats `CLAUDE.md` content. Both are structural de-duplication and placement choices, not measured quality gains.

Native runtime control stays in the adapter. No translation claims that a Claude permission mode is equivalent to a Codex sandbox. The capability matrix states gaps; unsupported unattended launch combinations fail before starting a process. Generic bundles support additional assistants through their instruction interface, with no unverified runtime guarantees.
