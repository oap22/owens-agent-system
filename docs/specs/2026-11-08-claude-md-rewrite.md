---
status: agreed
date: 2026-11-08
subject: Rewrite of Owen's global instruction files (explanations and workflows)
---

# CLAUDE.md rewrite

## Findings (checked 2026-11-08)

- `~/.claude/settings.json:94` sets `"outputStyle": "Concise"` for all sessions.
- Three files load together: `~/.claude/CLAUDE.md` (90 lines), `~/AGENTS.md` (93), `~/.claude/AGENTS.md` (89). Mostly copies; they conflict on primary assistant (Claude Code vs Codex), vault output folder, and session-link wording.
- The managed block comes from `prompts/core.md` + `prompts/owen.md` through `scripts/setup.py`. `prompts/owen.md` has an uncommitted change (vault output folder).
- No rule covers explanations in an unfamiliar domain. Teaching rules exist only for coursework (`workflows/tutor.md`).

## Decisions

- Q1 (symptoms): the explanation problems are **undefined jargon** and **too much at once**. Not selected: "skips steps", "report, not explanation".
- Q2 (where): the problems occur in **all four** places: the summary after coding, answers to questions, plans and options, and progress notes. The rule must be global, not tied to one message type.
- Q3 (shape): **plain first, in layers**. Plain-words answer first; each new term gets a short definition at first use; at most 3 new concepts in one message; then stop and name the next layer Owen can ask for. Rejected: tutor-style check questions for non-coursework; a trailing Terms list.
- Q4 (trigger): **always on, with a known list**. The layered shape is the default in all sessions. The instruction file holds a short list of what Owen knows well; all other terms get a definition. "I know X" turns definitions off for X.
- Q5 (known list): **starts empty**. Owen's words: "Let's assume none to start, then we can add them as we go."
- Q6 (assistants): **Claude Code only**. Owen no longer needs Codex or the others to obey these rules. Consequence: `~/AGENTS.md` and `~/.claude/AGENTS.md` are stale copies; removal needs Owen's explicit yes.
- Q7 (rule home): **custom output style**. `~/.claude/output-styles/owen.md` holds all reply-writing rules (STE, layered explanation, snippets, one question at a time). `settings.json` selects it in place of Concise. `CLAUDE.md` keeps only work rules (git, permissions, vault, skills).
- Q8 (workflow problem): **"I do too much alone."** In a domain Owen does not know, Claude makes the design decisions and writes all the code; Owen gets a result he does not fully understand or own. Not selected (no conclusion drawn): too much ceremony, stops or asks too much, skills and agents misused.
- Q9 (division of work): **decision gates** for personal (non-coursework) work. Before code: a short plain plan and the 1-3 design decisions in it, each with a recommendation; Owen decides. Claude writes the code. At the end: a layered walk-through. Rejected: small slices with a go, Owen writes the core, walk-through only.
- Q10 (gate trigger): **design decisions only**, in all domains. A gate is for a choice that shapes the structure and is costly to change: data model, architecture, a new library, a public interface. Bug fixes and mechanical edits get no gate.
- Q11 (source): **edit the prompts**. Changes go into `prompts/core.md`, `prompts/owen.md`, and the hand-written lines of `~/.claude/CLAUDE.md` (lines 1-26 and 79-90); `scripts/setup.py` regenerates the block (lines 27-78). Known side effect: setup also writes the Codex, Cursor and OpenCode files.
- Q12 (depth): **reorganize**. Add the gates and the walk-through, move the writing rules to the output style, delete duplicates, fix conflicts. All other rules keep their meaning. No line-by-line trim.
- Q13 (stale files): **move to `~/arc`**. At the apply step, `~/AGENTS.md` and `~/.claude/AGENTS.md` move to `~/arc/2026-11-08-stale-agents-md/`. Nothing is deleted.
- Q14 (gate bypass): **decide and record**. When Owen says "just do it", or the job is unattended or in the background, Claude uses its recommended option and continues. The walk-through then starts with "Decisions I made": each decision, the reason, and how to reverse it.

## Applied text

### `~/.claude/output-styles/owen.md` (new)

```markdown
---
name: Owen
description: Simplified Technical English, plain first, in layers
keep-coding-instructions: true
---
# How to write to Owen

Write in ASD-STE100 Simplified Technical English (about 80%): short sentences, one idea each, approved words, active voice. Keep code, identifiers, and file names as they are.

These rules apply to every message: progress notes, plans, options, answers, and the summary after work.

1. Lead with the result or the answer in plain words. No preamble. No recap.
2. Define each new term at first use, in one clause. A term is a word from a domain, tool, or library, or an acronym. General programming words (function, loop, class) are not terms. Do not define terms on the known list in `~/.claude/CLAUDE.md`.
3. Put at most 3 new concepts in one message. If the topic needs more, stop after 3.
4. End an explanation with one line that names the next layer Owen can ask for.
5. Show a short code snippet when it makes the point clearer.
6. Ask one question at a time.
7. Errors, failing test output, and confirmations for destructive actions keep their full content.
```

### `prompts/owen.md` (replaces the last sentence of "Protect learning and ownership")

```markdown
For personal software work, Owen owns the design decisions. A design decision shapes the structure and is costly to change: data model, architecture, a new library, a public interface. Before code, give a short plain plan and its 1-3 design decisions, one at a time, recommendation first; Owen decides. Bug fixes and mechanical edits need no gate. When Owen says "just do it", or the job is unattended or in the background, use the recommended option and continue. Then carry the work through implementation and verification, and end with a walk-through in layers; when you decided alone, start it with "Decisions I made": each decision, the reason, and how to reverse it.
```

### `~/.claude/CLAUDE.md` hand-written lines

- Remove line 3 (`**Always speak in 80% ASD-STE100 in all facets.**`) and the `## Writing style` section; the output style owns them.
- Add:

```markdown
## Known list

Terms and domains Owen knows well. Do not define them. Add an item when Owen says "I know X", and say that you did.

- (empty)
```

### Other changes

- `~/.claude/settings.json:94`: `"outputStyle": "Concise"` becomes `"outputStyle": "Owen"`.
- `workflows/development.md` step 1: "Use an isolated task worktree" conflicts with `CLAUDE.md` "Work on the current branch"; change to "Work on the current branch; use a task worktree only when Owen asks".
- Run `scripts/setup.py --apply` to regenerate the managed block (also rewrites the Codex, Cursor, Copilot and OpenCode files).
- Move `~/AGENTS.md` and `~/.claude/AGENTS.md` to `~/arc/2026-11-08-stale-agents-md/`.

## Out of scope

- The Frame-to-Reflect contract, permissions, git finishing flow, delegation, vault rules: meaning unchanged.
- Coursework: `workflows/tutor.md` and `professor` stay as they are.
- A Claude-only flag for `setup.py`.
- The uncommitted vault-folder change in `prompts/owen.md`: kept, not part of this work.

## End-to-end check

1. Repo tests pass (`pytest`).
2. A new Claude Code session shows `Owen` as the output style and loads no `AGENTS.md` copy (`/context`).
3. In that session, a question in an unfamiliar domain gets an answer with each term defined, at most 3 new concepts, and a next-layer line.
4. A request with a design decision gets a plan and a gate before code.

## Anthropic guidance (docs read by a subagent 2026-11-08; not re-verified by the lead)

- Target under 200 lines per `CLAUDE.md`; adherence drops in longer files (code.claude.com/docs/en/memory.md).
- All discovered files concatenate; none overrides another. On a contradiction Claude "may pick one arbitrarily" (memory.md).
- `AGENTS.md` is read directly only when no `CLAUDE.md` exists in the working directory or above (memory.md, "AGENTS.md").
- Adding IMPORTANT to an ignored line "probably won't fix it"; a must-always rule belongs in a hook (best-practices.md).
- An output style is sent as instructions with every request; `CLAUDE.md` arrives as a user message. Precedence between Concise and a `CLAUDE.md` request for fuller explanation is not documented (output-styles.md).
- A custom output style is a Markdown file in `~/.claude/output-styles/`.
- Multi-step procedures belong in skills; area rules in `.claude/rules/` with `paths:`.

## Open questions

- None. Owen agreed on 2026-11-08; applied the same day.

## Claude's own calls (Owen can veto)

- "Term" means a word from a domain, tool, library, or an acronym. General programming words (function, loop, class, variable) get no definition, even with an empty known list.
- When Owen says "I know X", I add X to the known list in the instruction source and say that I did.
- The gate rule lives in `prompts/owen.md` (generated block). The known list lives in the hand-written part of `CLAUDE.md`, so a new item needs no setup run.
- The output style keeps the Concise behaviors "lead with the result, no preamble, no recap", because Owen did not select "skips steps".
- The walk-through obeys the same limit: at most 3 new concepts, then a next-layer line.
- `workflows/development.md` step 1 changes to match "Work on the current branch".
- Coursework rules do not change. The layered shape applies there too, but tutor rules win on conflict.
