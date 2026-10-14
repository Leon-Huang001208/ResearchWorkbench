# Real Hot corpus v1

Run `node services/hot/scripts/evaluate-corpus.ts` from the repository root with the installed Node24 dependencies. This is offline: no PostgreSQL connection, credential lookup, task registration, model send or budget change.

The versioned JSON contains five real, immutable public feed materials and three already paid grouping packets/responses from the task-owned acceptance database. Corpus metadata includes material/version/content/raw-page hashes, acquisition/publication times and frozen source catalog/channel rules. Full material snapshot, packet and response digests are verified; scores are compared to the stated frozen rule contract. These are integrity/behavior checks, not independently calibrated labels.

Two primary occurrences are development samples; three are retrospective holdout samples. Target event/material IDs and URLs cannot cross partitions. Reference-document URLs also inherit partition constraints. Production candidate history is intentionally unchanged: the held EmbeddingGemma packet includes the development AI Jam candidate. The result therefore states `partitionScope: primary_occurrences_only`, `storedReceiptContextDisjoint: false` and lists the overlap. No blinded evaluation or independent accuracy is claimed (`independentAccuracy: null`).

Coverage includes both AI/macro domains, official sources from four operators, cross-channel unrelated content, low-heat important official items and an ambiguous ECB headline with empty excerpt. Its rule zero score does not establish low real-world importance. Materials are feed fragments, not full article copies; their actual input coverage is preserved.

The four separately reviewed relation references cover a report of the same release, multi-year BNP remediation followup, a multi-bank composite and insufficient-context review. They use verified public URLs, but have `modelStatus: NOT_RUN`; no new paid model result is manufactured. FDIC's listing returned403 and was not admitted via a mirror. This corpus does not prove current open-news accuracy, production ingestion of the external reference articles, or actual model coverage of every relationship.

References: [2022 joint review](https://www.federalreserve.gov/newsevents/pressreleases/bcreg20221216b.htm), [2026 followup](https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260929a.htm), [report tracing the primary release](https://thefile.news/story/fed-resolution-plans-15-banks-sept29).
