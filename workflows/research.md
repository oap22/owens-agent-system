# Research

1. Define the decision or scientific question. Distinguish a literature answer, an experiment, and a tutoring session. Use `research-question` when there is only an interest area, `research-survey` for a field, `paper-review` for one paper, and `research-loop` for experiments.
2. Read only the relevant vault/project notes and trace their original sources. Verify niche, unstable, or high-stakes claims against current primary sources. Record publication date and retrieval date separately.
3. Maintain a claim ledger: claim, exact source, evidence location, population/dataset/setup, limitations, and confidence label (**Label your confidence**). Seek counterevidence. Do not use benchmark results as proof of clinical usefulness or a paper abstract as proof of full-method details.
4. For experiments, apply **Hypothesis and falsifier first** and **Fair comparison**, then add dataset provenance/license, leakage controls, compute budget, stopping rule, and an executable verifier before running. For medical work, include clinical relevance and subgroup/external-validity limits without turning exploratory results into medical advice.
5. Run bounded experiments under **Log it or it did not happen**, failures included. Keep raw data and large artifacts out of this system repository. Use `rosie` only with confirmed target access and explicit resource scope.
6. At source-gathering, experiment-design, execution, and synthesis boundaries, checkpoint the claim ledger, source locations, data identity, raw-output paths, unresolved confounds, and next question. After compaction or resume, verify those artifacts and any changing external source before relying on them; a generated summary is not evidence.
7. Synthesize the answer with uncertainty and a concrete next experiment. Verify each material citation supports the sentence attached to it. Source-linked generated notes are not proof Owen learned the material.

Skill routing: `research-principles`, `research-question`, `research-survey`, `research-ingest`, `paper-review`, `research-loop`, `run-design`, `rosie`.
