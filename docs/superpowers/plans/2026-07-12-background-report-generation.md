# Background Report Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the desktop workbench's timeout-prone synchronous report request with a deduplicated background job API, observable progress polling, and thread-safe local model reuse.

**Architecture:** Add a framework-independent in-memory `ReportGenerationJobService` backed by a single-worker executor. FastAPI submits jobs and exposes status, while the existing `ReportProjectRunService` remains the rendering seam and gains an optional progress callback. The browser polls short requests; local embedding and reranker construction/inference are protected by locks.

**Tech Stack:** Python 3.9+, FastAPI, Pydantic, `concurrent.futures`, vanilla JavaScript, pytest.

---

## File map

- Create `reporting/projects/jobs.py`: job record, bounded in-memory registry, deduplication, executor lifecycle, progress and result conversion.
- Create `tests/unit/test_report_generation_jobs.py`: deterministic job-service state, failure, deduplication, and bounded-history tests.
- Modify `reporting/projects/run.py`: optional structured progress callback around prepare/generate/render/save phases.
- Modify `reporting/projects/generation.py`: per-section progress callback plus thread-safe local model loading and inference.
- Modify `app/api/routes/report_projects.py`: 202 submit endpoint, status endpoint, response models, shared render-result conversion.
- Modify `app/web/static/js/templates.js`: submit and poll jobs, map server phases to the progress card, tolerate transient polling errors.
- Modify `tests/unit/test_report_projects_api.py`: API contract, progress compatibility, and model locking regression tests.
- Modify `tests/unit/test_report_template_workbench_frontend.py`: assert job submission/polling behavior.
- Modify `docs/modules/reporting.md` and `报告生成设计.md`: document background execution and restart boundary.

### Task 1: Build the report-generation job service

**Files:**
- Create: `reporting/projects/jobs.py`
- Create: `tests/unit/test_report_generation_jobs.py`

- [ ] **Step 1: Write the failing immediate-return and completion test**

```python
def test_submit_returns_before_blocked_runner_finishes():
    release = threading.Event()
    service = ReportGenerationJobService(runner=lambda *_args, **_kwargs: (release.wait(), _result())[1])
    job = service.submit(project=_project(), request=ReportProjectRunRequest())
    assert job.status in {"queued", "running"}
    release.set()
    completed = wait_for_status(service, job.job_id, "completed")
    assert completed.result.file_name == "weekly.docx"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_generation_jobs.py::test_submit_returns_before_blocked_runner_finishes -q
```

Expected: FAIL with `ModuleNotFoundError: reporting.projects.jobs`.

- [ ] **Step 3: Implement the minimal job types and executor**

Implement immutable snapshots with these public fields:

```python
@dataclass(frozen=True)
class ReportGenerationJob:
    job_id: str
    project_slug: str
    status: str
    phase: str
    message: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completed_sections: int = 0
    total_sections: int = 0
    result: ReportProjectRunResult | None = None
    error: str | None = None
    deduplicated: bool = False
```

`ReportGenerationJobService.submit()` stores `queued`, submits `_run_job`, and returns a copied snapshot. `_run_job` moves to `running`, invokes the injected runner, then records `completed` or `failed` with `logger.exception`. Protect all registry mutations with `threading.RLock`; default executor is `ThreadPoolExecutor(max_workers=1, thread_name_prefix="report-generation")`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Add failing deduplication, failure, ownership, and bounded-history tests**

Cover:

```python
assert service.submit(project=project, request=request).job_id == first.job_id
assert service.get(first.job_id, project_slug="other") is None
assert wait_for_status(service, failed.job_id, "failed").error == "generation exploded"
assert len(service.list_jobs()) <= 100
```

- [ ] **Step 6: Implement active-slug lookup and bounded cleanup**

Reuse active jobs only for `queued`/`running`. Remove the active slug mapping on terminal transition. Prune oldest terminal jobs after insert/update without deleting active jobs.

- [ ] **Step 7: Run all job-service tests**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_generation_jobs.py -q
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add reporting/projects/jobs.py tests/unit/test_report_generation_jobs.py
git commit -m "feat: add background report generation jobs"
```

### Task 2: Add structured run and section progress

**Files:**
- Modify: `reporting/projects/run.py`
- Modify: `reporting/projects/generation.py`
- Modify: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Write failing progress callback tests**

Add a run-service test that collects callback payloads and asserts ordered phases:

```python
events = []
service.execute(..., progress_callback=lambda event: events.append(event))
assert [event["phase"] for event in events] == ["prepare", "generate", "render", "save"]
```

Add a generation-service test with two configured sections and assert the last generation event is:

```python
assert events[-1] == {
    "phase": "generate",
    "message": "已生成 2/2 个段落",
    "completed_sections": 2,
    "total_sections": 2,
}
```

- [ ] **Step 2: Run both tests and verify RED**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q -k "progress_callback"
```

Expected: FAIL because `execute()` and `generate_placeholders()` do not accept the callbacks.

- [ ] **Step 3: Add optional callback plumbing**

Define `ProgressCallback = Callable[[Dict[str, Any]], None]`. Add `progress_callback: ProgressCallback | None = None` to the public execute/generate methods. Emit `prepare` before resolving scope, `generate` before/through placeholder generation, `render` before projections, and `save` before the run-log write. Callback exceptions must be caught and logged so UI instrumentation cannot fail report generation.

- [ ] **Step 4: Emit monotonic section progress**

In the future collection loop, increment a completed counter after each successful future and emit the exact total. Preserve output ordering through `results_by_placeholder` and `ordered_placeholders`.

- [ ] **Step 5: Run progress and existing concurrency tests**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q -k "progress_callback or independent_prompt_sections_concurrently or report_project_run_service"
```

Expected: all selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add reporting/projects/run.py reporting/projects/generation.py tests/unit/test_report_projects_api.py
git commit -m "feat: expose report generation progress"
```

### Task 3: Expose background job APIs

**Files:**
- Modify: `app/api/routes/report_projects.py`
- Modify: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Write failing API contract tests**

Patch the module-level job service with a deterministic fake and verify:

```python
response = client.post("/api/report-projects/demo/render-jobs", json={})
assert response.status_code == 202
assert response.json()["status"] == "queued"
assert response.json()["status_url"].endswith(f"/render-jobs/{job_id}")

status = client.get(f"/api/report-projects/demo/render-jobs/{job_id}")
assert status.status_code == 200
assert status.json()["result"]["download_url"].endswith("weekly.docx")
```

Also assert unknown/wrong-project jobs return 404 and duplicate submit returns `deduplicated: true`.

- [ ] **Step 2: Run API tests and verify RED**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q -k "render_job_api"
```

Expected: FAIL with HTTP 404 for the new routes.

- [ ] **Step 3: Add response models and shared result conversion**

Add `RenderReportJobResponse` containing job fields, `status_url`, optional `RenderReportProjectResponse result`, and optional `error`. Extract `_to_render_response(run_result)` so synchronous and background endpoints produce identical artifact URLs and metadata.

- [ ] **Step 4: Add submit and status endpoints**

Submit validates/loads the project and config before enqueueing, constructs a runner that calls `ReportProjectRunService.execute(..., progress_callback=...)`, and returns `status_code=202`. Status uses `job_service.get(job_id, project_slug=slug)` and returns 404 when ownership fails.

- [ ] **Step 5: Run route tests**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q -k "render_job_api or render_report_project"
```

Expected: all selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/api/routes/report_projects.py tests/unit/test_report_projects_api.py
git commit -m "feat: expose report generation job API"
```

### Task 4: Make local embedding and reranker use thread-safe

**Files:**
- Modify: `reporting/projects/generation.py`
- Modify: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Write failing concurrent-load tests**

Patch `SentenceTransformer`/`CrossEncoder` constructors with counters and a barrier, call each loader from four threads, and assert:

```python
assert constructor_calls == 1
assert len({id(model) for model in results}) == 1
```

- [ ] **Step 2: Run and verify RED**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q -k "local_model_load_is_singleton"
```

Expected: FAIL because constructors run more than once.

- [ ] **Step 3: Add load and inference locks**

Add module-level embedding/reranker `RLock` instances. Use lock-internal cache rechecks around constructors. Wrap `model.encode(...)` and `model.predict(...)` in their respective inference locks. Keep all existing fallback logging and return values.

- [ ] **Step 4: Write and pass non-overlapping inference tests**

Use fake models that count simultaneous calls and sleep briefly; invoke from multiple threads and assert `max_active == 1` for encode and predict.

- [ ] **Step 5: Run relevant generation tests**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_projects_api.py -q -k "embedding or rerank or independent_prompt_sections_concurrently"
```

Expected: all selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add reporting/projects/generation.py tests/unit/test_report_projects_api.py
git commit -m "fix: serialize local report model access"
```

### Task 5: Switch the workbench to submit-and-poll

**Files:**
- Modify: `app/web/static/js/templates.js`
- Modify: `tests/unit/test_report_template_workbench_frontend.py`

- [ ] **Step 1: Write failing frontend source-contract test**

```python
assert "/render-jobs`" in source
assert "pollReportGenerationJob" in source
assert "job.status === 'completed'" in source
assert "job.status === 'failed'" in source
assert "completed_sections" in source
```

- [ ] **Step 2: Run and verify RED**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_template_workbench_frontend.py -q -k "background_job"
```

Expected: FAIL because the workbench still calls `/render`.

- [ ] **Step 3: Implement job submission and polling**

Change `renderReportProject(project)` to POST `/render-jobs`, then call `pollReportGenerationJob(statusUrl)`. Poll every 1500 ms for at most 40 minutes. Map `queued/prepare` to `check`, `generate` to `generate`, and `render/save` to `refresh`. On completion return `job.result`; on failure throw `Error(job.error)`.

- [ ] **Step 4: Add bounded transient network retry**

Retry up to three consecutive polling network failures with backoff, resetting the counter after any successful status response. If the client deadline expires, throw an error that says the backend job may still be running and includes the job ID.

- [ ] **Step 5: Run frontend tests**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_template_workbench_frontend.py tests/unit/test_desktop_shell_scaffold.py -q
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/web/static/js/templates.js tests/unit/test_report_template_workbench_frontend.py
git commit -m "fix: poll background report generation"
```

### Task 6: Documentation and full verification

**Files:**
- Modify: `docs/modules/reporting.md`
- Modify: `报告生成设计.md`

- [ ] **Step 1: Update report-generation documentation**

Document the render-job endpoints, lifecycle, same-project deduplication, single-worker resource policy, model locks, polling behavior, and the fact that running jobs do not survive an app restart.

- [ ] **Step 2: Run formatting and focused tests**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_generation_jobs.py tests/unit/test_report_projects_api.py tests/unit/test_report_template_workbench_frontend.py tests/unit/test_desktop_shell_scaffold.py -q
ruff check reporting/projects/jobs.py reporting/projects/run.py reporting/projects/generation.py app/api/routes/report_projects.py tests/unit/test_report_generation_jobs.py tests/unit/test_report_projects_api.py
```

Expected: zero test failures and zero ruff errors.

- [ ] **Step 3: Run regression verification**

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_report_project_manager.py tests/unit/test_report_project_chart_generation.py tests/unit/test_report_project_table_generation.py tests/unit/test_ppt_template_projection.py tests/unit/test_word_projection.py -q
```

Expected: all PASS.

- [ ] **Step 4: Verify the original failure mode with a slow fake runner**

Run the integration test that blocks the runner longer than one polling interval and assert the submit response is already 202 while the job remains running, then release it and assert terminal completion. This proves the browser no longer owns the lifetime of the report render.

- [ ] **Step 5: Check diffs and debug cleanup**

```bash
git diff --check
rg -n "\[DEBUG-" reporting app tests || true
git status --short
```

Expected: no whitespace errors, no temporary debug logs, and only scoped implementation/docs plus pre-existing user changes.

- [ ] **Step 6: Commit documentation**

```bash
git add docs/modules/reporting.md 报告生成设计.md
git commit -m "docs: explain background report generation"
```
