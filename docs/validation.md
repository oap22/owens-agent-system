# Validation scope

Run `python3 scripts/oas.py check`, `python3 -m unittest discover -s tests -v`, and `git diff --check`. Tests use disposable fixtures and no model calls.

`check` validates source configuration, role paths, workflows, evaluation scenarios, guidance size, and that the retrospective template keeps its sections and placeholders. The suite covers native argument construction, permission boundaries, immutable concurrent role snapshots, read-only previews, exact doctor options, task evidence and compaction state, telemetry accounting, installer rollback, runtime selection, retrospective verification and issue filing with a stubbed `gh`, and UI state transitions. Historical tokenizer calibration is an estimate, not a new-model benchmark.

`doctor MODE --workspace PATH` accepts the same model, lead effort, worker model/effort, and retry effort options as a Codex launch. It materializes the same role snapshots and reports the selected executable. Use `OAS_CODEX_BIN` to select an installed runtime explicitly. Doctor can report inherited connector, terminal, and host warnings; inspect the individual categories. A successful parse is not proof that the TUI starts or a model request succeeds.

After changes to launch settings, start the native client once and verify the selected model, effort, mode, and absence of config errors. Stop without inference when only startup is under test. For permission changes, exercise negative paths as well as the intended operation.

UI tests exercise navigation, disabled choices, typed model IDs, directory selection, launch/return behavior, and layout helpers. They do not prove a real terminal rendering or a provider's model entitlement. The source supports native controls per adapter; shared instructions do not imply permission parity.

The skill routing check compares `Skill routing:` names with the canonical skill directories and warns about missing entries; it does not validate a skill's reasoning or connected services. `--skills-root` chooses a fixture or alternate directory.

Current audit evidence and limits are in [[docs/audit-2026-09-15]]. Initial adoption evidence remains in [[docs/build-report]]. Hosted CI is checked at release. Live delegated tasks, connector operations, and comparative model-quality/cost evaluations require separate evidence.
