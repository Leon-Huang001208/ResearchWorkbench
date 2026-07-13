# Global Report Evidence Candidate Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every weekly-report paragraph considers relevant materials from all ingested sources before a global relevance ranking and rerank decide the final evidence.

**Architecture:** Replace the current newest-first candidate truncation with a bounded relevance scan that occurs before final filtering and ranking. No source whitelist, quota, or forced representation is introduced: all sources share one candidate pool and only relevant documents survive existing subject, driver, time-window, and reranker rules. Structured retrieval logs expose source distributions before and after filtering.

**Tech Stack:** Python, SQLAlchemy, PostgreSQL, pytest, YAML, structlog.

---

## File responsibilities

- `reporting/projects/generation.py`: database candidate scan limit, source-agnostic collection, logging, filtering and final evidence ranking.
- `report_projects/华安ETF周报/config/section_config.yaml`: default bounded relevance-scan limit for every report paragraph.
- `tests/unit/test_report_projects_api.py`: database retrieval candidate-pool and source-agnostic selection tests.
- `tests/unit/test_all_weekly_prompt_configs.py`: global retrieval-default contract and medical regression configuration checks.

### Task 1: Lock down global candidate-pool behavior

**Files:**
- Modify: `tests/unit/test_report_projects_api.py`
- Modify: `tests/unit/test_all_weekly_prompt_configs.py`

- [ ] **Step 1: Write a failing retrieval regression test**

Add a fake database query that contains forty recent generic documents followed by an older, subject-and-driver-matched document from `ingestion:zhiqiu_transcript`, plus an older matched document from `ingestion:cnstock_flash`. Configure a ten-item final limit and a relevance scan of at least 80. Assert that both older matched snippets reach `filter_and_rank_evidence`; assert that a generic document containing neither subject nor driver does not survive.

```python
def test_database_retriever_scans_before_final_ranking_across_all_sources():
    retrieval = build_retrieval_config(
        {"retrieval": {"subject_keywords": ["创新药"], "keywords": ["临床", "医保"]}},
        default_top_k=10,
    )
    snippets = newest_generic_snippets(40) + [
        EvidenceSnippet("ingestion:zhiqiu_transcript", "医药电话会", "创新药临床结果公布"),
        EvidenceSnippet("ingestion:cnstock_flash", "基本药物目录调整", "医保准入政策落地"),
    ]
    ranked = select_report_evidence_candidates(snippets, retrieval, final_limit=10)
    assert {item.source for item in ranked} >= {
        "ingestion:zhiqiu_transcript", "ingestion:cnstock_flash"
    }
```

- [ ] **Step 2: Run the targeted test and verify RED**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_report_projects_api.py -k "scans_before_final_ranking" -q
```

Expected: failure because the existing database query applies its candidate `limit()` before relevance filtering.

- [ ] **Step 3: Add default-configuration contracts**

Add exact assertions that `defaults.retrieval.relevance_scan_limit` is `400`, `defaults.retrieval.source_types` remains absent, and every section therefore retains full-source retrieval. Assert that `医药生物.retrieval.source_types` is absent as well.

- [ ] **Step 4: Run configuration RED tests**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py -k "relevance_scan or medical" -q
```

Expected: failure because the global scan limit is not yet configured.

### Task 2: Collect all-source relevance candidates before truncation

**Files:**
- Modify: `reporting/projects/generation.py`

- [ ] **Step 1: Add bounded scan-limit resolution**

Add `relevance_scan_limit` to `RetrievalConfig`, parse it from `retrieval.relevance_scan_limit`, and preserve the existing `candidate_k` as the pre-rerank target. Use this helper:

```python
def _relevance_scan_limit(limit: int, config: RetrievalConfig | None) -> int:
    configured = config.relevance_scan_limit if config else 0
    baseline = max(limit * 10, 400)
    return max(limit, min(1000, configured or baseline))
```

- [ ] **Step 2: Apply the scan before final filtering**

In `DatabaseEvidenceRetriever.retrieve`, request `scan_limit` matching ingestion candidates and a bounded event scan, deduplicate the merged list, then call the existing `filter_and_rank_evidence` exactly once. Do not filter by source name and do not create source quotas.

```python
scan_limit = _relevance_scan_limit(candidate_limit, retrieval_config)
snippets = self._retrieve_ingestion_items(..., limit=scan_limit, ...)
snippets.extend(self._retrieve_events(..., limit=max(candidate_limit, scan_limit // 4), ...))
snippets = _dedupe_snippets(snippets)
ranked = filter_and_rank_evidence(snippets, retrieval_config, query=query)
return ranked[:limit]
```

- [ ] **Step 3: Log candidate source distributions**

Add a small pure helper returning `{source: count}`. Emit one structured `logger.info` entry after database collection and one after filtering, including `title`, `scan_count`, `filtered_count`, and both source-count mappings. Do not include document text or URLs in logs.

- [ ] **Step 4: Run Task 1 regressions and verify GREEN**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_report_projects_api.py -k "scans_before_final_ranking" -q
```

Expected: PASS; the older China Securities/知丘-style matched snippets are retained while generic snippets are rejected.

### Task 3: Enable the global scan without source restrictions

**Files:**
- Modify: `report_projects/华安ETF周报/config/section_config.yaml`
- Test: `tests/unit/test_all_weekly_prompt_configs.py`

- [ ] **Step 1: Set the global relevance scan limit**

Under `defaults.retrieval`, add only:

```yaml
relevance_scan_limit: 400
```

Do not add `source_types` anywhere. Do not add a per-source quota, per-source minimum, or medical-specific source whitelist.

- [ ] **Step 2: Verify configuration GREEN**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py -k "relevance_scan or medical" -q
```

Expected: PASS.

### Task 4: Verify report-level source recall and regressions

**Files:**
- Verify: `report_projects/华安ETF周报/runs/`
- Verify: `logs/`

- [ ] **Step 1: Run static and regression tests**

Run:

```bash
ruff check reporting/projects/generation.py tests/unit/test_all_weekly_prompt_configs.py tests/unit/test_report_projects_api.py
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py tests/unit/test_gold_report_prompt_config.py tests/unit/test_oil_report_prompt_config.py tests/unit/test_report_projects_api.py -q
```

Expected: Ruff reports `All checks passed!`; pytest has zero failures.

- [ ] **Step 2: Generate cross-section real evidence samples**

Generate `医药生物` plus `中国宏观`、`人工智能`、`港股科技`、`美国新闻` for the same report window. For each section print evidence count, title, source, retrieval rank, rerank score, and output text. Confirm that all sections still reject out-of-scope materials and that the logs show a non-empty all-source candidate pool before final ranking.

- [ ] **Step 3: Restart and health-check the desktop app**

Run:

```bash
bash scripts/desktop/restart_app.sh
HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= https_proxy= http_proxy= all_proxy= curl --silent --show-error --fail --max-time 3 http://127.0.0.1:8765/health
```

Expected: health response contains `"status":"ok"`.
