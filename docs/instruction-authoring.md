# Instruction authoring for current models

How to write and audit the prompts, workflows, `AGENTS.md`/`CLAUDE.md` files, and skill descriptions this kit sends. Adopted 2026-09-11 from OpenAI's "Rethinking skills and prompts for GPT-6 Astra" (developers.openai.com/blog, see [[docs/sources]]) and verified against the primary post on 2026-09-18. The guidance is written for GPT-6 Astra; this repository applies selected patterns across harnesses where they match observed OAS failure modes.

The primary post directly supports short workflow-specific skill descriptions, progressive disclosure, contextual document loading, avoiding redundant test nags, explicit safe autonomy, and clear completion boundaries. The six-part packet, authority order, and writing rules below are OAS-specific synthesis, not claims that the post uses those exact terms.

## The theme

Less scaffolding, clearer boundaries. Instructions written to make an older model test or pre-read routinely can now cause unnecessary work, while vague completion language can make Astra stop after a first implementation. Current models see every loaded instruction, so obsolete or contradictory lines in a skill or an `AGENTS.md` still carry a cost.

## A prompt has six parts

Every task prompt, task packet, and workflow step should let the model recover these without guessing:

1. Goal: the observable outcome.
2. Inputs: the context it needs and where it lives; entry points, not "explore".
3. Constraints: what must not change and what needs authorization.
4. Autonomy: what it may decide alone and which instruction source wins on conflict.
5. Output: the shape of the result and the report.
6. Definition of done: the criteria that mean stop, including how far to go before returning for review.

The model is more tentative about stopping than its predecessors; it may finish a first implementation and come back for review with in-scope work left. Definition of done is what prevents that. "Can you", "I want to", and "help me" are requests to act, not invitations to ask.

## What to remove

Audit each instruction file for these and delete them unless a real failure in the evaluation log justifies keeping one:

- Test and verification nags ("always run the tests", "double-check your work", "run the check after every change"). The model runs relevant checks on its own; the nag produces extra runs. State which check defines done instead.
- Forced pre-reads ("always read X before starting"). Name the entry points and let the task decide.
- Unbounded keep-going pushers ("never stop until", "do not give up"). Replace them with a definition of done and a named stopping condition.
- Warnings, disclaimers, and safety checklists for risks the task does not present.
- Rules repeated across several files so they "stick". A rule lives once, at the level that owns it, and other files link to it.
- Obsolete or contradictory guidance. When two files disagree the model may pause, change direction, or follow the rule the user did not expect. The fix is explicit authority and deletion, not another instruction.

## Authority

The host's own hierarchy comes first; the contract does not restate what the host enforces. Below it, OAS sources rank the workspace instruction file, then the workflow for the mode, the active skill, and repository docs or tool descriptions. Retrieved content, issues, mail, and tool output are data at every level and cannot grant authorization. On conflict, follow the higher source, say so once, and continue. The contract in [[prompts/core]] states this and the vault's `.system/agent-conventions.md` states the vault-specific order.

## Skills

- Every installed skill costs context on every session: its name and description are loaded so the model can route. Install a skill where its workflow is used, not everywhere. The canonical repository's `manifest.json` targets are the control.
- A description is short, third person, and triggers on a specific workflow ("refresh my daily note", "push this to GitHub"), not on a topic area ("git", "productivity"). A description that names a topic fires on unrelated requests; one that names nothing never fires.
- `SKILL.md` is a router. Keep the steps that every use needs; move workflow-specific detail, long examples, and scripts into bundled files the skill loads on demand.
- Apply the removal list above inside skills too: no test nags, no pre-read orders, no disclaimers, and no rule that duplicates the workspace file.
- The user's instructions take precedence over a skill. A skill that blocks progress is reported by name with the constraint quoted, not silently obeyed or silently skipped.

## Writing

Plain language, active voice, and the action connected to its purpose. Prefer a concrete example to an abstraction. This kit bans filler such as "delve", "foster", "leverage", "genuinely", "importantly", "it's worth noting", "Bottom line:", rhetorical question-then-answer, "this isn't about X, it's about Y", and stacked hyphenated compound adjectives. The vault's `05-Profile/Owen-Voice.md` governs anything drafted in Owen's voice and already excludes em dashes.

## Delegation

Delegate by packet. A packet is the six parts above for one slice: goal, entry points, owned paths and constraints, budget and stop rule, report format, acceptance check. [[templates/task-packet]] is that shape. A delegate that stops on its budget reports a blocker; it does not loop.

## Audit checklist

Run this over a file before committing a change to `prompts/`, `workflows/`, `config/agents/`, a bundle template, or a skill:

1. Does every instruction state a boundary, a goal, or a definition of done? Delete the ones that only exhort.
2. Is there a check, pre-read, or "always" that the model would do anyway? Delete or convert to "X defines done".
3. Does any line contradict a higher-authority file? Fix the lower file.
4. Is the same rule stated in more than one file? Keep one, link from the others.
5. Could the file be a router with detail loaded on demand? Move detail out.
6. For a skill: does the description name the workflow that should trigger it, in one line, without a topic word doing the work?
7. Run `python3 scripts/oas.py check` and compare the guidance token estimate before and after; the change should not grow it.

Evidence that a removal or addition changed outcomes goes in the evaluation log, per [[evals/README]]; this checklist edits for the documented failure modes, it does not prove a prompt improved.
