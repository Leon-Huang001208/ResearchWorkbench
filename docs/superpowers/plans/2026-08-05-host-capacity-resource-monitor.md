# AlphaFoundry 主机容量资源监控第三期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在系统监控页并列显示 AlphaFoundry 归因与整机 CPU/内存容量；页面关闭后仍每分钟采样、保存 24 小时并产生可处置事件。

**Architecture:** ResourceMonitoringService 继续限制在 AlphaFoundry 进程树，并只调用操作系统 CPU/内存总量 API。新增 ResourceMonitorRuntime 在数据库就绪后每分钟采集、写入现有 HealthMetrics.extra，并用一个共享状态评估告警。API 只返回白名单，前端显示 5 分钟应用曲线和 24 小时主机曲线。

**Tech Stack:** Python、psutil、FastAPI、SQLAlchemy、Pydantic、ECharts、pytest、ruff、black、isort。

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| services/resource_monitor_service.py | 当前 AlphaFoundry 快照和无全局进程枚举的主机汇总。 |
| services/resource_host_history_service.py（新增） | 分钟去重、历史写入、读取与过期清理。 |
| services/resource_monitor_runtime.py（新增） | API 生命周期中的单一后台线程。 |
| services/resource_monitor_alert_service.py | 主机/AlphaFoundry 分来源事件、升级和恢复。 |
| data_layer/repositories/monitoring_repository.py | 按精确 ID 删除过期指标。 |
| app/api/main.py、app/api/routes/system.py | runtime 生命周期和 API 白名单。 |
| app/web/templates/index.html、app/web/static/js/resource-monitor.js、app/web/static/style.css | 双范围卡片、图表与来源标签。 |
| tests/unit/test_resource_*.py | 采样、历史、runtime、告警、API、UI 契约。 |

### Task 1: 主机汇总采集和比例换算

**Files:**
- Modify: services/resource_monitor_service.py
- Modify: tests/unit/test_resource_monitor_service.py

- [ ] **Step 1: 写失败测试。**

    def test_snapshot_adds_host_capacity_without_global_process_scan(scoped_process_tree, monkeypatch):
        root, _ = scoped_process_tree
        monkeypatch.setattr(resource_monitor_service.psutil, "cpu_count", lambda logical=True: 8)
        monkeypatch.setattr(resource_monitor_service.psutil, "cpu_percent", lambda interval=None: 40.0)
        monkeypatch.setattr(
            resource_monitor_service.psutil, "virtual_memory",
            lambda: SimpleNamespace(total=16 * 2**30, used=8 * 2**30, available=8 * 2**30),
        )
        monkeypatch.setattr(
            resource_monitor_service.psutil, "process_iter",
            lambda: (_ for _ in ()).throw(AssertionError("global scan forbidden")),
            raising=False,
        )
        service = ResourceMonitoringService(root_pid=root.pid)
        service.collect_snapshot()
        snapshot = service.collect_snapshot()
        assert snapshot["host"]["logical_cpu_count"] == 8
        assert snapshot["host"]["memory_available_percent"] == 50.0
        assert snapshot["summary"]["cpu_host_percent"] == pytest.approx(18.5 / 8)

补充 cpu_count 返回 None、virtual_memory 抛 psutil.Error 和第一次 CPU 读数不可用的测试；字段必须为 None 且产生 host_field_unavailable 警告，不能填零。

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/test_resource_monitor_service.py -q
Expected: FAIL，因为快照尚无 host 和整机比例。

- [ ] **Step 3: 实现只读总量采集。**

在现有 root PID 与其递归子进程逻辑之外增加 _collect_host_summary()，只调用 psutil.cpu_percent(interval=None)、psutil.cpu_count(logical=True)、psutil.virtual_memory()。不得添加 process_iter、pids 或其他 PID 访问。

    return {
        "cpu_percent": cpu_percent,
        "cpu_idle_percent": 100.0 - cpu_percent if isinstance(cpu_percent, (int, float)) else None,
        "logical_cpu_count": cpu_count if isinstance(cpu_count, int) and cpu_count > 0 else None,
        "memory_total_bytes": total,
        "memory_used_bytes": used,
        "memory_available_bytes": available,
        "memory_available_percent": available / total * 100 if total and available is not None else None,
    }

以逻辑核心数和总内存计算 summary.cpu_host_percent、summary.memory_host_percent。所有主机采样异常写结构化 error_type 日志。

- [ ] **Step 4: 验证并提交。**

Run: python -m pytest tests/unit/test_resource_monitor_service.py -q
Expected: PASS.

    git add services/resource_monitor_service.py tests/unit/test_resource_monitor_service.py
    git commit -m "feat: collect host capacity with resource snapshots"

### Task 2: 24 小时分钟级持久化

**Files:**
- Create: services/resource_host_history_service.py
- Modify: data_layer/repositories/monitoring_repository.py
- Create: tests/unit/test_resource_host_history_service.py
- Modify: tests/unit/test_monitoring.py

- [ ] **Step 1: 写分钟去重与清理失败测试。**

    def test_record_once_per_minute_and_prune_only_expired_host_capacity_metrics():
        repo = FakeMetricsRepository()
        service = ResourceHostHistoryService(repo, now=fixed_now)
        snapshot = {"summary": {"cpu_percent": 12.5, "memory_bytes": 200}, "host": HOST}
        assert service.record_if_due(snapshot) is True
        assert service.record_if_due(snapshot) is False
        assert repo.saved[0].extra["metric_type"] == "host_capacity"
        assert repo.deleted_metric_ids == ["expired-host-point"]

再测 history(hours=24) 仅返回 metric_type 为 host_capacity 的点、按时间升序；任何事件或其他健康指标不得删除。

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/test_resource_host_history_service.py tests/unit/test_monitoring.py -q
Expected: FAIL，因为历史服务和删除接口不存在。

- [ ] **Step 3: 实现仓储和历史服务。**

在 MonitoringRepositoryImpl 增加按指标 ID 删除的方法；空列表直接返回 0。

    def delete_health_metrics(self, metric_ids: list[str]) -> int:
        safe_ids = [item for item in metric_ids if isinstance(item, str) and item]
        if not safe_ids:
            return 0
        deleted = self.db.query(HealthMetricsDB).filter(
            HealthMetricsDB.metric_id.in_(safe_ids)
        ).delete(synchronize_session=False)
        self.db.flush()
        logger.info("health metrics deleted", count=deleted)
        return int(deleted)

新增历史服务，跨 UTC 分钟才保存一个 HealthMetrics；extra 只能含 metric_type=host_capacity、host 七个安全字段和 alpha 的 cpu_percent、memory_bytes、cpu_host_percent、memory_host_percent。列出超过 24 小时的 RESOURCE_MONITORING 指标后，先筛 metric_type 再按精确 ID 删除。使用既有 JSON extra 列，不加表或迁移。

- [ ] **Step 4: 验证并提交。**

Run: python -m pytest tests/unit/test_resource_host_history_service.py tests/unit/test_monitoring.py -q
Expected: PASS.

    git add services/resource_host_history_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_host_history_service.py tests/unit/test_monitoring.py
    git commit -m "feat: persist host capacity history"

### Task 3: 页面关闭后仍持续监控

**Files:**
- Create: services/resource_monitor_runtime.py
- Modify: app/api/main.py
- Create: tests/unit/test_resource_monitor_runtime.py

- [ ] **Step 1: 写 runtime 生命周期失败测试。**

    def test_runtime_run_once_collects_persists_and_evaluates_with_shared_state():
        monitor, history, alerts = FakeMonitor(HOST_SNAPSHOT), FakeHistory(), FakeAlerts()
        runtime = ResourceMonitorRuntime(
            monitor, history_factory=lambda repo: history,
            alert_factory=lambda repo, state: alerts,
        )
        runtime.run_once()
        assert monitor.calls == history.calls == alerts.calls == 1

    def test_runtime_keeps_next_cycle_available_after_persistence_error():
        runtime = ResourceMonitorRuntime(FakeMonitor(), history_factory=FailingHistory, alert_factory=FakeAlerts)
        runtime.run_once()
        assert runtime.last_error_type == "RuntimeError"

补充 start 幂等、stop 设置 Event 并 join，以及预览模式不会 start 的 API 生命周期测试。

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/test_resource_monitor_runtime.py -q
Expected: FAIL，因为 runtime 尚不存在。

- [ ] **Step 3: 实现单线程 runtime。**

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            self.run_once()
            self._stop_event.wait(max(0.0, self._interval_seconds - (time.monotonic() - started)))

    def run_once(self) -> None:
        snapshot = self._monitor.collect_snapshot()
        try:
            with db_session() as session:
                repo = MonitoringRepositoryImpl(session)
                self._history_factory(repo).record_if_due(snapshot)
                self._alert_factory(repo, self._alert_state).evaluate(snapshot)
        except Exception as exc:
            self.last_error_type = type(exc).__name__
            logger.warning("resource monitor runtime cycle failed", error_type=self.last_error_type)

在 app/api/main.py 的 ensure_schema 后启动；shutdown 时最先停止。使用延迟导入和单例防止重复 startup。ALPHAFOUNDRY_PREVIEW=1 保持不启动后台线程。

- [ ] **Step 4: 验证并提交。**

Run: python -m pytest tests/unit/test_resource_monitor_runtime.py tests/unit/app/api/routes/test_resource_monitoring.py -q
Expected: PASS.

    git add services/resource_monitor_runtime.py app/api/main.py tests/unit/test_resource_monitor_runtime.py
    git commit -m "feat: run resource monitoring continuously"

### Task 4: 整机容量告警与来源标签

**Files:**
- Modify: services/resource_monitor_alert_service.py
- Modify: tests/unit/test_resource_monitor_alert_service.py

- [ ] **Step 1: 写连续阈值、升级、恢复失败测试。**

    def test_host_cpu_warning_upgrades_to_critical_then_resolves():
        repo, state = FakeRepository(), ResourceAlertState()
        service = ResourceMonitorAlertService(repo, state=state)
        for _ in range(3):
            service.evaluate(_snapshot_with_host(cpu_percent=86.0, memory_available_percent=50.0))
        assert repo.alerts[0].severity is AlertSeverity.WARNING
        assert repo.alerts[0].metadata["source_scope"] == "host_capacity"
        for _ in range(3):
            service.evaluate(_snapshot_with_host(cpu_percent=96.0, memory_available_percent=50.0))
        assert repo.alerts[0].severity is AlertSeverity.CRITICAL
        for _ in range(3):
            service.evaluate(_snapshot_with_host(cpu_percent=20.0, memory_available_percent=50.0))
        assert repo.alerts[0].status is AlertStatus.RESOLVED

覆盖可用内存 15%/8%、主机字段不可用不触发、同一未解决事件去重，以及现有应用事件 source_scope 为 alphafoundry。

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/test_resource_monitor_alert_service.py -q
Expected: FAIL，服务尚不读取 snapshot 中的 host。

- [ ] **Step 3: 实现共享状态与主机规则。**

新增不持有仓储的 ResourceAlertState，runtime 跨会话保留连续计数。规则为 CPU 85/95%、可用内存 15/8%，连续三次触发/连续三次恢复；键为 host_cpu_pressure、host_memory_pressure。

    def _host_severity(value, warning, critical, *, lower_is_worse):
        if value <= critical if lower_is_worse else value >= critical:
            return AlertSeverity.CRITICAL
        if value <= warning if lower_is_worse else value >= warning:
            return AlertSeverity.WARNING
        return None

同一 warning 达到 critical 时原地更新 severity、title、description、threshold，不新建事件。metadata 仅增加 source_scope、host_cpu_percent、host_memory_available_percent、threshold_percent，不保存原始系统错误。

- [ ] **Step 4: 验证并提交。**

Run: python -m pytest tests/unit/test_resource_monitor_alert_service.py -q
Expected: PASS.

    git add services/resource_monitor_alert_service.py tests/unit/test_resource_monitor_alert_service.py
    git commit -m "feat: alert on host capacity pressure"

### Task 5: API 白名单与主机历史端点

**Files:**
- Modify: app/api/routes/system.py
- Modify: tests/unit/app/api/routes/test_resource_monitoring.py

- [ ] **Step 1: 写 API 失败测试。**

    def test_resource_usage_exposes_only_host_capacity_summary(monkeypatch):
        monkeypatch.setattr(system, "get_resource_monitoring_service", lambda: FakeMonitor(HOST_SNAPSHOT))
        response = _client().get("/api/system/resource-usage")
        assert response.status_code == 200
        assert set(response.json()["host"]) == {
            "cpu_percent", "cpu_idle_percent", "logical_cpu_count",
            "memory_total_bytes", "memory_used_bytes", "memory_available_bytes",
            "memory_available_percent",
        }
        assert "processes" not in response.json()["host"]

测试 host-history?hours=24 为 200，hours=25 为 422，存储失败为稳定 503；事件只能公开来源标签和安全主机指标。

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/app/api/routes/test_resource_monitoring.py -q
Expected: FAIL，因为 endpoint 和 sanitizer 不存在。

- [ ] **Step 3: 实现白名单响应。**

当前 resource-usage 只采样并返回；不再在每次页面请求中创建告警服务，连续事件由 runtime 评估。增加 resource-usage/host-history，hours 范围 1 到 24；host sanitizer 仅输出七个主机字段及数字/None；事件 serializer 仅增加 source_scope 与三项主机阈值字段。

    @router.get("/resource-usage/host-history")
    def get_host_resource_history(hours: int = Query(24, ge=1, le=24)) -> Dict[str, Any]:
        points = _resource_host_history_call(lambda service: service.history(hours=hours))
        return {"hours": hours, "points": [_sanitize_host_history_point(point) for point in points]}

- [ ] **Step 4: 验证并提交。**

Run: python -m pytest tests/unit/app/api/routes/test_resource_monitoring.py -q
Expected: PASS.

    git add app/api/routes/system.py tests/unit/app/api/routes/test_resource_monitoring.py
    git commit -m "feat: expose host capacity monitoring APIs"

### Task 6: 双范围页面与 24 小时图表

**Files:**
- Modify: app/web/templates/index.html
- Modify: app/web/static/js/resource-monitor.js
- Modify: app/web/static/style.css
- Modify: app/web/static/js/app.js
- Modify: tests/unit/test_resource_monitor_frontend_static.py

- [ ] **Step 1: 写 UI 静态契约失败测试。**

    def test_resource_monitor_has_dual_scope_cards_and_host_history_contract():
        html = Path("app/web/templates/index.html").read_text()
        script = Path("app/web/static/js/resource-monitor.js").read_text()
        for key in ("alpha-cpu", "host-cpu", "alpha-memory", "host-memory"):
            assert f'data-resource-summary="{key}"' in html
        assert "/api/system/resource-usage/host-history?hours=24" in script
        assert "source_scope" in script
        assert "整机进程" not in html

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q
Expected: FAIL，双范围 DOM 与主机历史请求不存在。

- [ ] **Step 3: 实现四卡、四图和安全渲染。**

顶部改为 alpha-cpu、host-cpu、alpha-memory、host-memory 四卡；磁盘、网络、采样时间移入辅助行。保留两张 5 分钟 AlphaFoundry 图，再加两张 24 小时整机 CPU/可用内存图。

JS 新增 hostHistoryController、hostHistoryPoints 与两张 chart；首次进入、从隐藏恢复、之后每 60 秒请求：

    const result = await apiCall(
        "GET",
        "/api/system/resource-usage/host-history?hours=24",
        null,
        { signal: controller.signal, retries: 0 },
    )
    hostHistoryPoints = Array.isArray(result?.points) ? result.points : []

主机字段为 null 显示“暂不可用”。事件根据 metadata.source_scope 显示“整机容量”或“AlphaFoundry”。所有动态文本使用 textContent。更新 app.js 中资源脚本的 cache version。

- [ ] **Step 4: 验证并提交。**

Run: node --check app/web/static/js/resource-monitor.js && python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q
Expected: PASS.

    git add app/web/templates/index.html app/web/static/js/resource-monitor.js app/web/static/style.css app/web/static/js/app.js tests/unit/test_resource_monitor_frontend_static.py
    git commit -m "feat: compare AlphaFoundry and host capacity"

### Task 7: 文档、质量链和隔离预览

**Files:**
- Modify: docs/ARCHITECTURE.md, docs/REFERENCE.md, docs/FILE_GUIDE.md, docs/CHANGELOG.md
- Modify: docs/modules/app_api.md, docs/modules/app_web.md, docs/modules/core_services.md, docs/modules/data_layer_repositories.md
- Modify: docs/generated/py_file_index.md
- Create: .ai/reports/2026-08-05-host-capacity-resource-monitor.md

- [ ] **Step 1: 更新文档和索引。**

记录两条路径：页面请求的 5 分钟 AlphaFoundry 原始快照，以及 runtime 持续写入的主机 24 小时分钟汇总。明确剩余内存取 available，不展示其他进程，本期无原生通知。

Run: python scripts/generate_py_file_index.py
Expected: exit 0，索引更新。

- [ ] **Step 2: 运行质量链。**

    python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/test_resource_host_history_service.py tests/unit/test_resource_monitor_runtime.py tests/unit/test_resource_monitor_alert_service.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_monitoring.py -q
    ruff check services/resource_monitor_service.py services/resource_host_history_service.py services/resource_monitor_runtime.py services/resource_monitor_alert_service.py data_layer/repositories/monitoring_repository.py app/api/main.py app/api/routes/system.py
    black --check services/resource_monitor_service.py services/resource_host_history_service.py services/resource_monitor_runtime.py services/resource_monitor_alert_service.py data_layer/repositories/monitoring_repository.py app/api/main.py app/api/routes/system.py
    isort --check-only services/resource_monitor_service.py services/resource_host_history_service.py services/resource_monitor_runtime.py services/resource_monitor_alert_service.py data_layer/repositories/monitoring_repository.py app/api/main.py app/api/routes/system.py
    python scripts/check_doc_sync.py
    python scripts/check_task_completion.py
    git diff --check

Expected: 全部 exit 0；若格式化工具改动文件，格式化后重跑同一质量链。

- [ ] **Step 3: 验证分支预览并提交记录。**

验证 API 启动/关闭只创建/停止一个 runtime；关闭页面后跨过分钟边界，host-history 仍出现新点。再打开独立桌面预览，检查四卡、四图、来源标签、事件置顶与当前接口。不得改动或停止 master；不可将 macOS 验证表述为 Windows 验证。

    git add docs/ARCHITECTURE.md docs/REFERENCE.md docs/FILE_GUIDE.md docs/CHANGELOG.md docs/modules/app_api.md docs/modules/app_web.md docs/modules/core_services.md docs/modules/data_layer_repositories.md docs/generated/py_file_index.md .ai/reports/2026-08-05-host-capacity-resource-monitor.md
    git commit -m "docs: record host capacity monitoring verification"

## 计划自检

- 规格覆盖：Task 1 指标、Task 2 历史、Task 3 常驻、Task 4 告警、Task 5 API、Task 6 UI、Task 7 交付。
- 无占位符：每项均给出目标文件、失败测试、实现行为、命令、提交边界。
- 一致性：host_capacity 历史与其他指标隔离；runtime 是连续评估者；不枚举其他进程；预览不启动 runtime。

