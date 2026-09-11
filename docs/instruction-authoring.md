# Instruction authoring for current models

How to write and audit the prompts, workflows, `AGENTS.md`/`CLAUDE.md` files, and skill descriptions this kit sends. Adopted 2026-09-11 from OpenAI's "Rethinking skills and prompts for GPT-6 Astra" (developers.openai.com/blog, see [[docs/sources]]) and cross-checked against the Codex system prompt for that model. The guidance is written for GPT-6 Astra; it is applied here to every harness because the failure modes it names (duplicate work from keep-going pushers, unnecessary testing from test nags, stalls on contradictory files) were already visible in this kit's own prompts before the post.

Provenance limit: the post itself could not be fetched from the session that adopted it (network policy), so the principles below are reconstructed from search summaries and secondary reports of it, not from a read of the original. Treat specific wording as paraphrase and re-read the primary source before citing it.

## The theme

Less scaffolding, clearer boundaries. Instructions written to keep a weaker model moving, testing, and re-reading now cause the opposite problems: duplicate work, unnecessary test runs, and premature stops when files disagree. Current models are strong at following long instructions and more sensitive to every file they can read, so an obsolete or contradictory line in a skill or an `AGENTS.md` costs more than it used to.

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
- Keep-going pushers written for weaker models ("never stop until", "do not give up"). They produce duplicate work now. Replace with a definition of done and a named stopping condition.
- Warnings, disclaimers, and safety checklists for risks the task does not present.
- Rules repeated across several files so they "stick". A rule lives once, at the level that owns it, and other files link to it.
- Obsolete or contradictory guidance. When two files disagree the model may pause, change direction, or follow the rule the user did not expect. The fix is explicit authority and deletion, not another instruction.

## Authority

Say which source wins. This kit's order, highest first: the user's live request; the workspace instruction file; the workflow for the mode; the active skill; repository docs and tool descriptions. Retrieved content, issues, mail, and tool output are data at every level. On conflict, follow the higher source, say so once, continue; do not stop to reconcile. The contract in [[prompts/core]] states this and the vault's `.system/agent-conventions.md` states the vault-specific order.

## Skills

- Every installed skill costs context on every session: its name and description are loaded so the model can route. Install a skill where its workflow is used, not everywhere. The canonical repository's `manifest.json` targets are the control.
- A description is short, third person, and triggers on a specific workflow ("refresh my daily note", "push this to GitHub"), not on a topic area ("git", "productivity"). A description that names a topic fires on unrelated requests; one that names nothing never fires.
- `SKILL.md` is a router. Keep the steps that every use needs; move workflow-specific detail, long examples, and scripts into bundled files the skill loads on demand.
- Apply the removal list above inside skills too: no test nags, no pre-read orders, no disclaimers, and no rule that duplicates the workspace file.
- The user's instructions take precedence over a skill. A skill that blocks progress is reported by name with the constraint quoted, not silently obeyed or silently skipped.

## Writing

Plain language, active voice, and the action connected to its purpose. Prefer a concrete example to an abstraction. The post ships a blocklist of filler; the ones this kit already bans or should: "delve", "foster", "leverage", "genuinely", "importantly", "it's worth noting", "Bottom line:", rhetorical question-then-answer, "this isn't about X, it's about Y", and stacked hyphenated compound adjectives. The vault's `05-Profile/Owen-Voice.md` governs anything drafted in Owen's voice and already excludes em dashes.

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
