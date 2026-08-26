# AlphaFoundry 资源监控第二期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让系统监控页将 AlphaFoundry 的受控 Worker 和任务归因到资源使用，并持久化、置顶和处置异常事件。

**Architecture:** 新的任务登记器在每个 AlphaFoundry 进程内维护任务上下文，并把安全的任务快照原子写入受控运行目录。资源服务只合并 API 进程树、现有 Worker PID 文件及该运行目录的快照；事件协调器复用既有 `alert_payload`/`incident_record` 状态机，前端通过系统 API 显示实时归因、未恢复置顶告警与 90 天事件历史。

**Tech Stack:** Python 3、FastAPI、Pydantic、SQLAlchemy、psutil、原生 ES module、现有 `core.observability` 日志。

---

## 修改清单

- 新建 `services/resource_task_registry.py`：跨线程安全的任务上下文与每 PID 原子 JSON 快照。
- 新建 `services/resource_monitor_alert_service.py`：资源异常的去重、恢复、持久化和查询。
- 修改 `services/resource_monitor_service.py`：受控 PID 合并、任务归因、压力状态输入。
- 修改 `core/contracts/monitoring.py`：增加 `Subsystem.RESOURCE_MONITORING`。
- 修改 `app/api/routes/system.py`：资源事件查询、确认、解决 API 与依赖装配。
- 修改 `services/crawl_scheduler.py`、`workers/knowledge_worker.py`、`services/wind_workbook_manager.py`、`app/api/routes/report_projects.py`：登记已确认范围内的任务上下文。
- 修改 `app/web/static/js/resource-monitor.js` 及其现有模板/CSS：异常置顶、归因和历史筛选。
- 新增/扩展资源服务、任务登记、系统路由和前端静态契约测试。
- 更新 `docs/modules/{app_api,app_web,core_contracts,data_layer_repositories,services}.md`、`docs/{ARCHITECTURE,FILE_GUIDE,REFERENCE,CHANGELOG}.md` 及 `.ai/reports/` 任务报告。

## Task 1：资源任务登记器与契约

**Files:**
- Create: `services/resource_task_registry.py`
- Create: `tests/unit/test_resource_task_registry.py`
- Modify: `core/contracts/monitoring.py`
- Modify: `tests/unit/test_monitoring.py`
- Modify: `docs/modules/core_contracts.md`

- [ ] **Step 1: 先写失败测试，锁定快照与失败任务不泄密的契约。**

```python
def test_failed_task_is_retained_in_pid_snapshot_without_exception_text(tmp_path):
    registry = ResourceTaskRegistry(runtime_dir=tmp_path, pid=321)
    with pytest.raises(ValueError):
        with registry.resource_task(
            task_kind="crawl", source_key="cls", label="财联社抓取"
        ):
            raise ValueError("token=secret must not be persisted")

    snapshot = registry.read_snapshot(321)
    failed = snapshot["recent_failures"][0]
    assert failed["task_kind"] == "crawl"
    assert failed["source_key"] == "cls"
    assert failed["error_type"] == "ValueError"
    assert "secret" not in str(failed)
```

- [ ] **Step 2: 运行测试，确认它因模块缺失而失败。**

Run: `python -m pytest tests/unit/test_resource_task_registry.py -q`

Expected: `ModuleNotFoundError: No module named 'services.resource_task_registry'`。

- [ ] **Step 3: 实现最小、安全的登记器。**

```python
class ResourceTaskRegistry:
    def resource_task(self, *, task_kind: str, label: str, source_key: str | None = None):
        self._validate_task(task_kind=task_kind, label=label, source_key=source_key)
        return _ResourceTaskScope(self, task_kind=task_kind, label=label, source_key=source_key)

    def _write_snapshot_locked(self) -> None:
        payload = {"pid": self._pid, "active_tasks": self._active_tasks(),
                   "recent_failures": self._recent_failures(), "updated_at": _utc_now()}
        temporary = self._snapshot_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self._snapshot_path)
```

实现要求：只允许设计规格列出的五个 `task_kind`；错误仅保存异常类型与最多 160 字的固定安全摘要，不保存异常消息、请求参数或文档正文；文件名固定为 `<pid>.json`；读损坏 JSON 时记录结构化 warning 并返回空快照；提供模块级 `get_resource_task_registry()`，运行目录从 `ALPHAFOUNDRY_RUNTIME_DIR` 或项目数据目录解析。

- [ ] **Step 4: 增加并运行并发、正常结束、损坏快照和子系统枚举测试。**

```python
def test_resource_monitoring_subsystem_is_serializable():
    assert Subsystem.RESOURCE_MONITORING.value == "resource_monitoring"

def test_snapshot_write_is_atomic_under_concurrent_scopes(tmp_path):
    registry = ResourceTaskRegistry(runtime_dir=tmp_path, pid=321)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: registry.record_active_task_for_test(), range(2)))
    assert ResourceTaskRegistry.read_snapshot_file(tmp_path / "321.json")["pid"] == 321
```

Run: `python -m pytest tests/unit/test_resource_task_registry.py tests/unit/test_monitoring.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: 记录核心契约变更并提交。**

Run: `git add services/resource_task_registry.py core/contracts/monitoring.py tests/unit/test_resource_task_registry.py tests/unit/test_monitoring.py docs/modules/core_contracts.md && git commit -m "feat: add resource task registry"`

## Task 2：受控进程采样与资源异常协调器

**Files:**
- Create: `services/resource_monitor_alert_service.py`
- Create: `tests/unit/test_resource_monitor_alert_service.py`
- Modify: `services/resource_monitor_service.py`
- Modify: `tests/unit/test_resource_monitor_service.py`
- Modify: `docs/modules/services.md`
- Modify: `docs/modules/data_layer_repositories.md`

- [ ] **Step 1: 写失败测试，覆盖受控 PID、任务置信度、告警去重与恢复。**

```python
def test_known_worker_pid_is_collected_without_global_process_scan(monkeypatch):
    service = ResourceMonitoringService(root_pid=101, managed_processes=lambda: [
        ManagedProcess(pid=202, role="Knowledge Worker", attribution_kind="worker")
    ])
    snapshot = service.collect_snapshot()
    assert {item["pid"] for item in snapshot["processes"]} == {101, 202}
    assert next(item for item in snapshot["processes"] if item["pid"] == 202)["confidence"] == "exact_process"

def test_pressure_opens_once_then_resolves_after_three_recovered_samples():
    coordinator = ResourceMonitorAlertService(repo=FakeRepository())
    for _ in range(3):
        coordinator.evaluate(snapshot_with_cpu(pid=101, cpu=95))
    assert coordinator.open_event_count == 1
    for _ in range(3):
        coordinator.evaluate(snapshot_with_cpu(pid=101, cpu=5))
    assert coordinator.resolved_event_count == 1
```

- [ ] **Step 2: 运行测试，确认新增类型/服务尚不存在。**

Run: `python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/test_resource_monitor_alert_service.py -q`

Expected: import 或属性失败，现有第一期测试不被修改为“通过”。

- [ ] **Step 3: 扩展受控采样器，但不放宽监控边界。**

```python
def _discover_managed_processes(self) -> list[ManagedProcess]:
    discovered = [ManagedProcess(pid=self._root_pid, role="API", attribution_kind="api")]
    discovered.extend(self._descendant_processes())
    discovered.extend(self._managed_pid_provider())
    return self._deduplicate_by_identity(discovered)

def _attach_task_attribution(self, sample: dict[str, Any]) -> None:
    tasks = self._task_snapshot_reader(sample["pid"])
    sample["active_tasks"] = tasks["active_tasks"]
    sample["confidence"] = "shared_process_estimate" if tasks["active_tasks"] and sample["role"] == "API" else "exact_process"
```

`_managed_pid_provider()` 只调用 `get_all_worker_statuses()` 与 `get_scheduler_process_status()`，并只接纳 `alive=True` 且正整数 PID。每次采样的输出须包含登记 Worker 的角色和精确 `confidence`；API 内任务只附加在 API 样本而不分摊 CPU。不可用 PID、坏任务快照和单字段 psutil 异常降级为 warning 与日志。

- [ ] **Step 4: 实现持久化事件协调器。**

```python
class ResourceMonitorAlertService:
    def evaluate(self, snapshot: dict[str, Any]) -> None:
        self._open_failed_task_alerts(snapshot.get("task_failures", []))
        self._evaluate_process_unavailable(snapshot.get("warnings", []))
        self._evaluate_pressure(snapshot.get("processes", []))

    def _upsert_open_event(self, *, dedupe_key: str, event_kind: str, severity: AlertSeverity, metadata: dict[str, Any]) -> AlertPayload:
        existing = self._find_open_event(dedupe_key)
        if existing is not None:
            return existing
        return self._repo.save_alert(AlertPayload(
            alert_id=f"resource-{uuid.uuid4().hex[:12]}",
            threshold_id=f"resource-{event_kind}", subsystem=Subsystem.RESOURCE_MONITORING,
            severity=severity, title=self._title_for(event_kind, metadata),
            triggered_at=datetime.now(timezone.utc), metadata={**metadata, "dedupe_key": dedupe_key},
        ))
```

协调器查询现有未恢复资源告警，确保同一 `event_kind + task_id/pid` 只开一个事件；失败任务创建 `critical` 事件，采样失败、受控 PID 消失和连续三次 CPU≥90% 或 RSS≥1GiB 创建 `warning`，后三者连续三次恢复后调用既有 `MonitoringService.resolve_alert()`。每次写入/恢复均保存 `IncidentRecord`，并使用结构化日志记录事件 ID 和归因键。

- [ ] **Step 5: 运行目标测试及资源回归测试。**

Run: `python -m pytest tests/unit/test_resource_task_registry.py tests/unit/test_resource_monitor_service.py tests/unit/test_resource_monitor_alert_service.py tests/unit/test_monitoring.py -q`

Expected: all selected tests pass, including Phase 1’s root-and-descendants restriction.

- [ ] **Step 6: 记录服务/仓储使用方式并提交。**

Run: `git add services/resource_monitor_service.py services/resource_monitor_alert_service.py tests/unit/test_resource_monitor_service.py tests/unit/test_resource_monitor_alert_service.py docs/modules/services.md docs/modules/data_layer_repositories.md && git commit -m "feat: attribute resource usage and alerts"`

## Task 3：任务上下文接入与系统 API

**Files:**
- Modify: `services/crawl_scheduler.py`
- Modify: `workers/knowledge_worker.py`
- Modify: `services/wind_workbook_manager.py`
- Modify: `app/api/routes/report_projects.py`
- Modify: `app/api/routes/system.py`
- Create: `tests/unit/app/api/routes/test_resource_monitoring.py`
- Modify: `tests/unit/workers/test_knowledge_worker.py`
- Modify: `docs/modules/app_api.md`

- [ ] **Step 1: 写失败测试，锁定 API 的数据库边界与任务接入。**

```python
def test_list_resource_events_always_includes_open_events_outside_window(client, monkeypatch):
    monkeypatch.setattr(system, "get_resource_monitor_alert_service", lambda: fake_events)
    response = client.get("/api/system/resource-events?days=90&status=resolved")
    assert response.status_code == 200
    assert {item["alert_id"] for item in response.json()["items"]} == {"old-open", "recent-resolved"}

def test_knowledge_item_processing_registers_resource_task(monkeypatch):
    entered = []
    monkeypatch.setattr(knowledge_worker, "resource_task", recording_scope(entered))
    asyncio.run(knowledge_worker._process_and_mark(item, semaphore, pipeline))
    assert entered[0]["task_kind"] == "knowledge_processing"
```

- [ ] **Step 2: 运行新增测试并确认失败。**

Run: `python -m pytest tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/workers/test_knowledge_worker.py -q`

Expected: 资源事件路由或任务上下文断言失败。

- [ ] **Step 3: 在已确认的执行点包裹任务上下文。**

```python
async def _run_crawl_job(self, source_type: SourceType) -> None:
    with resource_task(task_kind="crawl", source_key=source_type.value, label=f"{source_type.value} 抓取"):
        await self._run_crawl_job_inner(source_type)

async def _process_and_mark(...):
    with resource_task(task_kind="knowledge_processing", label="知识队列处理"):
        return await _process_and_mark_inner(...)
```

对 `CrawlScheduler` 的单源抓取、补数和 PDF 批处理、Knowledge Worker 的单队列项、Wind 工作簿准备/读取与报告渲染实施同样的窄包装。保留原有 `try/except` 和日志语义；包装器重新抛出异常以保持既有重试/状态机正确工作。

- [ ] **Step 4: 新增资源事件 API 并将实时采样接上协调器。**

```python
@router.get("/resource-events")
def list_resource_events(days: int = Query(90, ge=1, le=3650), ...):
    return event_service.list_events(since_days=days, filters=...)

@router.post("/resource-events/{alert_id}/acknowledge")
def acknowledge_resource_event(alert_id: str, ...):
    return event_service.acknowledge(alert_id)

@router.post("/resource-events/{alert_id}/resolve")
def resolve_resource_event(alert_id: str, body: ResourceEventResolveRequest, ...):
    return event_service.resolve(alert_id, notes=body.notes)
```

`GET /resource-usage` 在安全快照后调用协调器；协调器或数据库不可用时只记录 warning，仍返回资源数据。事件 API 每次请求独立取得/关闭数据库 Session，绝不复用跨请求 Session。`GET /resource-events` 合并近 90 天和任何未恢复事件；所有响应只返回已净化元数据。

- [ ] **Step 5: 运行 API、Worker 和系统路由测试。**

Run: `python -m pytest tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/workers/test_knowledge_worker.py tests/unit/test_resource_monitor_service.py tests/unit/test_monitoring.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: 更新 API 文档并提交。**

Run: `git add services/crawl_scheduler.py workers/knowledge_worker.py services/wind_workbook_manager.py app/api/routes/report_projects.py app/api/routes/system.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/workers/test_knowledge_worker.py docs/modules/app_api.md && git commit -m "feat: expose resource task events"`

## Task 4：监控页异常与归因体验

**Files:**
- Modify: `app/web/static/js/resource-monitor.js`
- Modify: `app/web/templates/index.html`（仅在缺少承载区时）
- Modify: `app/web/static/css/style.css`（仅在缺少样式时）
- Modify: `tests/unit/test_resource_monitor_frontend_static.py`
- Modify: `tests/unit/test_live_monitor_ui_static.py`
- Modify: `docs/modules/app_web.md`

- [ ] **Step 1: 写前端静态契约测试。**

```python
def test_resource_monitor_renders_open_events_before_realtime_tables():
    script = RESOURCE_MONITOR_JS.read_text(encoding="utf-8")
    assert "/api/system/resource-events" in script
    assert "renderPinnedEvents" in script
    assert "shared_process_estimate" in script
    assert "acknowledgeResourceEvent" in script
    assert "resolveResourceEvent" in script
```

- [ ] **Step 2: 运行静态测试，确认新增行为尚不存在。**

Run: `python -m pytest tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_live_monitor_ui_static.py -q`

Expected: 新增资源事件断言失败。

- [ ] **Step 3: 实现轮询、渲染与失败降级。**

```javascript
async function pollResourceEvents() {
    const response = await apiCall('/api/system/resource-events?days=90&status=all');
    if (!response) throw new Error('resource event response unavailable');
    renderPinnedEvents(response.items.filter((event) => event.status !== 'resolved'));
    renderResourceEventHistory(response.items);
}

function renderAttribution(process) {
    const confidence = process.confidence === 'shared_process_estimate'
        ? '共享 API 进程估算' : '独立进程精确值';
    return `${escapeHtml(process.role)} · ${confidence}`;
}
```

固定区按 `critical → warning → 发生时间` 排序，并提供确认/解决按钮。历史区提供状态、严重度、任务类型和数据源筛选；仍每两秒刷新实时快照，但事件历史使用独立、带退避的请求。任何事件 API 失败都保留最后成功的事件列表，并显示“历史暂不可用”，不会清空现有异常证据。图表文案明确标记“最近 5 分钟实时资源”。

- [ ] **Step 4: 运行前端静态测试和核心 API 回归。**

Run: `python -m pytest tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_live_monitor_ui_static.py tests/unit/app/api/routes/test_resource_monitoring.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: 更新 Web 文档并提交。**

Run: `git add app/web/static/js/resource-monitor.js app/web/templates/index.html app/web/static/css/style.css tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_live_monitor_ui_static.py docs/modules/app_web.md && git commit -m "feat: show resource incidents in monitor"`

## Task 5：质量检查、浏览器验收与交付记录

**Files:**
- Create: `.ai/reports/2026-08-05-resource-monitor-phase-2.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/REFERENCE.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 运行 Python 风格、完整性与针对性测试。**

Run:

```bash
python -m pytest tests/unit/test_resource_task_registry.py tests/unit/test_resource_monitor_alert_service.py tests/unit/test_resource_monitor_service.py tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_live_monitor_ui_static.py tests/unit/test_monitoring.py -q
ruff check services/resource_task_registry.py services/resource_monitor_alert_service.py services/resource_monitor_service.py app/api/routes/system.py workers/knowledge_worker.py services/crawl_scheduler.py
black --check services/resource_task_registry.py services/resource_monitor_alert_service.py services/resource_monitor_service.py app/api/routes/system.py workers/knowledge_worker.py services/crawl_scheduler.py
isort --check-only services/resource_task_registry.py services/resource_monitor_alert_service.py services/resource_monitor_service.py app/api/routes/system.py workers/knowledge_worker.py services/crawl_scheduler.py
python scripts/check_doc_sync.py
python scripts/check_task_completion.py
```

Expected: each command exits `0`; any unavailable checker is recorded in the task report with the real error.

- [ ] **Step 2: 在分支预览实例手工验收。**

Run: `npm run desktop:preview`

在预览桌面端打开“系统监控”，验证：无关本机进程不出现；活跃任务显示准确性标签；构造测试失败任务后出现置顶事件；确认、解决和刷新后历史状态一致；实时请求失败时上一帧仍保留。记录实际端口、浏览器/API 响应和未验证平台。

- [ ] **Step 3: 写入交付报告、更新索引文档并提交。**

报告必须列出修改范围、实际测试命令和结果、浏览器验收证据、未验证项（尤其 Windows 原生桌面端）和保留策略未自动删除历史的风险。

Run: `git add .ai/reports/2026-08-05-resource-monitor-phase-2.md docs/ARCHITECTURE.md docs/FILE_GUIDE.md docs/REFERENCE.md docs/CHANGELOG.md && git commit -m "docs: record resource monitor phase two verification"`

## 计划自检

- 规格中的受控 PID、共享估算、任务失败、压力恢复、90 天历史、置顶/确认/解决、失败降级和浏览器验收均对应 Task 1–5。
- 没有实现占位符；每个行为改动均指定文件、失败测试、实现边界、通过测试和提交步骤。
- 本计划不会增加 Python 包、扫描系统进程、持久化每个原始采样点，或接入桌面原生通知。
