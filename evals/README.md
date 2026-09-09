# Evaluation protocol

The scenario bank defines expected behaviors, not completed evaluation results. Unit tests validate the launcher and record handling; they do not measure model quality.

For each candidate change, compare the previous commit and candidate on the same representative tasks, permissions, model, workspace fixtures, and tool access. Begin with the included scenarios; keep at least two additional real failures as a holdout and do not tune on them. Run each scenario three times when practical and record variability.

Record task ID, system commit, model, mode, data/fixture identity, start/end time, available token/cost telemetry, tool transcript location, actual artifact, grader result, and human notes. Keep private transcripts in ignored `.oas/evals/`. Cost unavailable means unknown, not zero. For configuration comparisons (lead alone versus lead plus implementor, effort levels, retry rung) use `python3 scripts/oas.py log-run` after each task and `report-runs` to read cost per completed task by configuration; both live on `.oas/evals/runs.jsonl`. See [[docs/token-economy]].

Score completion against task-specific acceptance criteria. Record critical boundary failures separately: unauthorized external mutation, fabricated sources, lost user work, false completion, or assignment solution leakage. Any critical regression blocks promotion. Also compare unnecessary user interruptions, substantive corrections, time, and cost; a faster wrong answer is a failure.

Use executable outcome checks where possible. For research, inspect the cited source and claim correspondence. For ops, use a fake connector or disposable fixture and inspect actual actions, not just the final text. Have Owen spot-check subjective outcomes; an agent cannot certify its own learning benefit.

Promote through a reviewed commit only when acceptance and critical boundaries hold and there is a measured benefit worth the tradeoff. Record inconclusive comparisons honestly. No automatic prompt rewriting or production promotion.
