# Research

1. Define the decision or scientific question. Distinguish a literature answer, an experiment, and a tutoring session. Use `research-interview` for an ambiguous project and `research-loop` for experiments.
2. Read only the relevant vault/project notes and trace their original sources. Verify niche, unstable, or high-stakes claims against current primary sources. Record publication date and retrieval date separately.
3. Maintain a claim ledger: claim, exact source, evidence location, population/dataset/setup, limitations, and observation versus inference. Seek counterevidence. Do not use benchmark results as proof of clinical usefulness or a paper abstract as proof of full-method details.
4. For experiments, specify hypothesis, baseline, dataset provenance/license, splits, leakage controls, seeds, metric, compute budget, stopping rule, and an executable verifier before running. For medical work, include clinical relevance and subgroup/external-validity limits without turning exploratory results into medical advice.
5. Run bounded experiments with environment, commit, parameters, data identity, raw outputs, and failure records. Keep raw data and large artifacts out of this system repository. Use `rosie-run` only with confirmed target access and explicit resource scope.
6. At source-gathering, experiment-design, execution, and synthesis boundaries, checkpoint the claim ledger, source locations, data identity, raw-output paths, unresolved confounds, and next question. After compaction or resume, verify those artifacts and any changing external source before relying on them; a generated summary is not evidence.
7. Synthesize the answer with uncertainty and a concrete next experiment. Verify each material citation supports the sentence attached to it. Source-linked generated notes are not proof Owen learned the material.

Skill routing: `research-interview`, `research-ingest`, `research-loop`, `rosie-run`, `professor`, `spaced-recall`.
