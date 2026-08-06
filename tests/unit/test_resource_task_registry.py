"""ResourceTaskRegistry 的安全快照与生命周期测试。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from core.contracts.monitoring import Subsystem
from services.resource_task_registry import ResourceTaskRegistry


def test_failed_task_is_retained_in_pid_snapshot_without_exception_text(tmp_path) -> None:
    """失败任务应保留安全归因，不能持久化异常原文。"""
    registry = ResourceTaskRegistry(runtime_dir=tmp_path, pid=321)

    with pytest.raises(ValueError):
        with registry.resource_task(
            task_kind="crawl",
            source_key="cls",
            label="财联社抓取",
        ):
            raise ValueError("token=secret must not be persisted")

    snapshot = registry.read_snapshot(321)
    failed = snapshot["recent_failures"][0]

    assert failed["task_kind"] == "crawl"
    assert failed["source_key"] == "cls"
    assert failed["error_type"] == "ValueError"
    assert "secret" not in str(failed)
    assert snapshot["active_tasks"] == []


def test_completed_task_is_removed_from_active_snapshot(tmp_path) -> None:
    """正常结束的任务不应停留在活动列表。"""
    registry = ResourceTaskRegistry(runtime_dir=tmp_path, pid=321)

    with registry.resource_task(
        task_kind="pdf_conversion",
        label="PDF 转换批次",
    ):
        assert registry.read_snapshot(321)["active_tasks"][0]["task_kind"] == "pdf_conversion"

    assert registry.read_snapshot(321)["active_tasks"] == []
    assert registry.read_snapshot(321)["recent_failures"] == []


def test_snapshot_write_is_safe_under_concurrent_scopes(tmp_path) -> None:
    """并发任务写入后快照必须仍是可读取的完整 JSON。"""
    registry = ResourceTaskRegistry(runtime_dir=tmp_path, pid=321)

    def execute(index: int) -> None:
        with registry.resource_task(
            task_kind="crawl",
            source_key=f"source-{index}",
            label=f"抓取 {index}",
        ):
            assert registry.read_snapshot(321)["pid"] == 321

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(execute, range(2)))

    snapshot = ResourceTaskRegistry.read_snapshot_file(tmp_path / "321.json")
    assert snapshot["pid"] == 321
    assert snapshot["active_tasks"] == []


def test_invalid_task_kind_is_rejected(tmp_path) -> None:
    """仅允许资源监控规格定义的任务类型。"""
    registry = ResourceTaskRegistry(runtime_dir=tmp_path, pid=321)

    with pytest.raises(ValueError, match="task_kind"):
        registry.resource_task(task_kind="shell", label="不允许")


def test_corrupt_snapshot_returns_empty_payload(tmp_path) -> None:
    """损坏的其他进程快照不能中断资源采集。"""
    snapshot_path = tmp_path / "654.json"
    snapshot_path.write_text("not-json", encoding="utf-8")

    assert ResourceTaskRegistry.read_snapshot_file(snapshot_path) == {
        "active_tasks": [],
        "recent_failures": [],
    }


def test_resource_monitoring_subsystem_is_serializable() -> None:
    """资源监控告警使用独立且稳定的监控子系统值。"""
    assert Subsystem.RESOURCE_MONITORING.value == "resource_monitoring"
