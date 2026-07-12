"""Background report-generation job service tests."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from reporting.projects.jobs import ReportGenerationJobService
from reporting.projects.project_manager import ReportProject
from reporting.projects.run import ReportProjectRunRequest, ReportProjectRunResult


def _project(slug: str = "weekly") -> ReportProject:
    root = Path("/tmp") / slug
    return ReportProject(
        name=slug,
        slug=slug,
        project_dir=root,
        word_template_path=root / "template.docx",
        excel_workbook_path=root / "data.xlsx",
        section_config_path=root / "sections.yaml",
        output_dir=root / "generated",
        run_log_dir=root / "runs",
    )


def _result(slug: str = "weekly") -> ReportProjectRunResult:
    root = Path("/tmp") / slug
    return ReportProjectRunResult(
        project_name=slug,
        slug=slug,
        file_name="weekly.docx",
        output_path=root / "weekly.docx",
        run_log_path=root / "weekly.json",
        generated_at=datetime(2026, 7, 12, 12, 0, 0),
        generated_placeholder_count=2,
        evidence_count=3,
        warnings=[],
    )


def _wait_for_status(
    service: ReportGenerationJobService,
    job_id: str,
    expected: str,
    timeout: float = 2.0,
):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = service.get(job_id)
        if job and job.status == expected:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {expected}")


def test_submit_returns_before_blocked_runner_finishes():
    release = threading.Event()

    def runner(project, request, progress_callback):
        assert request == ReportProjectRunRequest()
        progress_callback(
            {
                "phase": "generate",
                "message": "正在生成段落",
                "completed_sections": 0,
                "total_sections": 2,
            }
        )
        release.wait(timeout=2)
        return _result(project.slug)

    service = ReportGenerationJobService(runner=runner)
    job = service.submit(project=_project(), request=ReportProjectRunRequest())

    assert job.status in {"queued", "running"}
    running = _wait_for_status(service, job.job_id, "running")
    assert running.phase == "generate"
    assert running.total_sections == 2

    release.set()
    completed = _wait_for_status(service, job.job_id, "completed")
    assert completed.result is not None
    assert completed.result.file_name == "weekly.docx"
    service.shutdown()


def test_submit_deduplicates_active_job_for_same_project():
    release = threading.Event()
    calls = 0

    def runner(project, request, progress_callback):
        nonlocal calls
        calls += 1
        release.wait(timeout=2)
        return _result(project.slug)

    service = ReportGenerationJobService(runner=runner)
    first = service.submit(project=_project(), request=ReportProjectRunRequest())
    duplicate = service.submit(project=_project(), request=ReportProjectRunRequest())

    assert duplicate.job_id == first.job_id
    assert duplicate.deduplicated is True
    release.set()
    _wait_for_status(service, first.job_id, "completed")
    assert calls == 1
    service.shutdown()


def test_failed_job_keeps_real_error_and_enforces_project_ownership():
    def runner(project, request, progress_callback):
        raise RuntimeError("generation exploded")

    service = ReportGenerationJobService(runner=runner)
    submitted = service.submit(project=_project(), request=ReportProjectRunRequest())
    failed = _wait_for_status(service, submitted.job_id, "failed")

    assert failed.error == "generation exploded"
    assert service.get(submitted.job_id, project_slug="other") is None
    service.shutdown()


def test_local_report_models_load_once_under_concurrency(monkeypatch):
    import sentence_transformers

    from reporting.projects import generation

    calls = {"embedding": 0, "reranker": 0}

    class FakeEmbedding:
        def __init__(self, *args, **kwargs):
            calls["embedding"] += 1
            time.sleep(0.02)

    class FakeReranker:
        def __init__(self, *args, **kwargs):
            calls["reranker"] += 1
            time.sleep(0.02)

    monkeypatch.setattr(generation, "resolve_local_embedding_model", lambda _name: "/fake")
    monkeypatch.setattr(generation, "sentence_transformer_kwargs", lambda _name: {})
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", FakeEmbedding)
    monkeypatch.setattr(sentence_transformers, "CrossEncoder", FakeReranker)
    generation._LOCAL_EMBEDDING_MODELS.clear()
    generation._LOCAL_RERANKER_MODELS.clear()

    with ThreadPoolExecutor(max_workers=4) as executor:
        embeddings = list(executor.map(generation._load_local_embedding_model, ["m"] * 4))
        rerankers = list(executor.map(generation._load_local_reranker_model, ["m"] * 4))

    assert calls == {"embedding": 1, "reranker": 1}
    assert len({id(model) for model in embeddings}) == 1
    assert len({id(model) for model in rerankers}) == 1
    generation._LOCAL_EMBEDDING_MODELS.clear()
    generation._LOCAL_RERANKER_MODELS.clear()
