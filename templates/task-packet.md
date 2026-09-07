# Task packet

The lead writes one packet per delegated slice. The implementor receives only this packet plus the workspace; it never receives the lead's transcript, the full task record, or the vault. Keep it under roughly forty lines. If the packet needs more, the slice is not independent enough to delegate.

## Packet (lead → implementor)

- Slice: one sentence naming the observable behavior to produce.
- Owned paths: exact files or module the implementor may edit. Everything else is read-only.
- Entry points: the two to five files or symbols to read first. Do not say "explore the codebase".
- Acceptance check: the exact command whose passing output proves the slice, and the failing output it currently produces.
- Constraints: interfaces that must not change, style or dependency rules, anything another slice depends on.
- Budget: maximum turns or iterations and the stop rule (for example: two failing runs of the check, then stop and report).
- Return format: the report shape below, nothing else.

## Report (implementor → lead)

- Result: done, partial, or blocked.
- Files changed: paths only.
- Check output: the last ten lines of the acceptance command, verbatim.
- Deviations: any edit outside owned paths, any interface change, any assumption made.
- Blocker: the single missing thing, if blocked.

The lead reads the diff and the check output, not the implementor's reasoning. A report that claims success without check output is treated as partial.

## When not to write a packet

Do the slice in the lead when any of these hold: the slice depends on the result of another slice still in progress; the lead would have to keep most of the same files in its own context to judge the result; the whole change fits in one short edit; or the slice requires judgment about the user's intent. In each of those cases a packet adds a plan, a handoff, and a merge that a single agent gets for free. See [[docs/token-economy]].
