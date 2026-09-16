# Research Method Eval Summary

- Run: `method-eval-20260916-r6`
- Status: `completed`
- Dataset SHA-256: `69c3336f9b26f3e7b83344a5541a642e7f3fad46f6cbff2bb1ba6d016bba6af9`
- Calls: 63/63
- Promotion candidates are review inputs only; default recommendations were not changed.

| Method | Baseline quality | Single quality | Tokens gate | Latency gate | Candidate |
| --- | ---: | ---: | --- | --- | --- |
| socratic-clarification | 0.933 | 0.967 | pass | fail | no |
| dual-layer-explanation | 0.933 | 1.000 | pass | pass | yes |
| reverse-engineering | 0.933 | 0.867 | pass | fail | no |
| horizontal-vertical-analysis | 0.933 | 0.933 | pass | pass | no |
| fact-checking | 0.933 | 0.900 | pass | pass | no |
| expert-perspectives | 0.933 | 0.967 | pass | fail | no |
| first-principles | 0.933 | 0.800 | pass | pass | no |
| cross-domain-transfer | 0.933 | 0.900 | pass | fail | no |
| steelman-comparison | 0.933 | 0.900 | pass | pass | no |
| minimal-experiment | 0.933 | 0.967 | pass | fail | no |
