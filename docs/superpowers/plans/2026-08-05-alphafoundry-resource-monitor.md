# AlphaFoundry 资源监控页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 新增只监控当前 AlphaFoundry API 进程及递归子进程的实时资源监控页面，显示 CPU、内存、磁盘 I/O、网络连接数和进程归因。

**Architecture:** ResourceMonitoringService 以 os.getpid() 为唯一根，使用 psutil 枚举受限进程树并维护 5 分钟（150 点）的内存历史。两个只读系统端点提供快照与历史；独立的原生 JS 模块以可取消的 2 秒轮询驱动 ECharts 和高密度进程表。

**Tech Stack:** Python、FastAPI、Pydantic、psutil（既有依赖）、原生 HTML/CSS/ES modules、ECharts、pytest、Playwright。

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| services/resource_monitor_service.py | 受限进程树采集、CPU/I/O 差分、职责标签和固定长度历史。 |
| app/api/routes/system.py | 只读快照/历史端点与懒加载服务依赖。 |
| tests/unit/test_resource_monitor_service.py | 进程边界、预热、聚合、降级、历史的服务测试。 |
| tests/unit/app/api/routes/test_system_resource_usage.py | API 契约与窗口参数边界测试。 |
| app/web/static/js/resource-monitor.js | 轮询、图表、表格、排序、详情、降级状态。 |
| app/web/static/js/app.js、index.html、style.css | 导航、语义页面骨架和响应式样式。 |
| tests/unit/test_resource_monitor_frontend_static.py | DOM、轮询取消、可见性、历史上限和安全渲染静态测试。 |
| docs/modules/app_api.md、docs/modules/app_web.md、docs/FILE_GUIDE.md、docs/CHANGELOG.md、.ai/reports/2026-08-05-alphafoundry-resource-monitor.md | 文档、变更记录和实际验证证据。 |

### Task 1: 受限资源采集服务

**Files:**

- Create: services/resource_monitor_service.py
- Create: tests/unit/test_resource_monitor_service.py

- [ ] **Step 1: 写出失败测试，固定“仅根进程及递归子进程”边界。**

    def test_snapshot_only_contains_root_and_recursive_children(monkeypatch):
        root = fake_process(101, children=[fake_process(102)])
        unrelated = fake_process(999)
        monkeypatch.setattr(
            "services.resource_monitor_service.psutil.Process",
            lambda pid: {101: root, 999: unrelated}[pid],
        )
        snapshot = ResourceMonitoringService(root_pid=101).collect_snapshot()
        assert snapshot["status"] == "warming_up"
        assert [item["pid"] for item in snapshot["processes"]] == [101, 102]
        assert unrelated.method_calls == []

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/test_resource_monitor_service.py::test_snapshot_only_contains_root_and_recursive_children -q

Expected: FAIL，模块 services.resource_monitor_service 尚不存在。

- [ ] **Step 3: 创建服务，使用以下稳定接口。**

    class ResourceMonitoringService:
        def __init__(self, root_pid: int | None = None, history_size: int = 150) -> None:
            self._root_pid = root_pid or os.getpid()
            self._history = deque(maxlen=history_size)
        def collect_snapshot(self) -> dict[str, Any]:
            return {"root_pid": self._root_pid}
        def history(self, window_seconds: int) -> list[dict[str, Any]]:
            return list(self._history)

collect_snapshot() 必须只用 psutil.Process(self._root_pid) 和 .children(recursive=True) 作为进程来源。每项返回 pid、parent_pid、name、160 字符内的前三段命令摘要、create_time、status、role、cpu_percent、memory_bytes、thread_count、disk_read_bytes_per_second、disk_write_bytes_per_second、network_connection_count、unavailable_reason。根进程角色为 API，其他为 AlphaFoundry 子进程。

服务以第一次 cpu_percent(None) 与 I/O 计数建立基线，返回 warming_up；第二次及后续样本返回 ok 并以 time.monotonic() 计算 I/O 每秒速率。NoSuchProcess 或 AccessDenied 的根进程返回 unavailable、空进程数组及 root_process_unavailable 警告。单个子进程错误只跳过该进程，使用 get_logger(__name__) 记录 root PID、PID 与异常类别，绝不记录完整命令行。

- [ ] **Step 4: 补齐聚合、预热、速率、环形历史和降级测试。**

    def test_second_sample_exposes_cpu_and_disk_rates(monkeypatch):
        service = ResourceMonitoringService(root_pid=101)
        service.collect_snapshot()
        fake_process.io_counters.return_value.read_bytes = 300
        snapshot = service.collect_snapshot()
        assert snapshot["status"] == "ok"
        assert snapshot["summary"]["disk_read_bytes_per_second"] == 100.0

    def test_missing_root_returns_controlled_unavailable_snapshot(monkeypatch):
        monkeypatch.setattr("services.resource_monitor_service.psutil.Process", raise_no_such_process)
        assert ResourceMonitoringService(root_pid=101).collect_snapshot()["status"] == "unavailable"

    def test_history_is_bounded_to_configured_sample_count(monkeypatch):
        service = ResourceMonitoringService(root_pid=101, history_size=2)
        service.collect_snapshot(); service.collect_snapshot(); service.collect_snapshot()
        assert len(service.history(window_seconds=300)) == 2

Run: python -m pytest tests/unit/test_resource_monitor_service.py -q

Expected: PASS。

- [ ] **Step 5: 提交。**

    git add services/resource_monitor_service.py tests/unit/test_resource_monitor_service.py
    git commit -m "feat: collect AlphaFoundry process resources"

### Task 2: 系统资源 API

**Files:**

- Modify: app/api/routes/system.py
- Create: tests/unit/app/api/routes/test_system_resource_usage.py

- [ ] **Step 1: 写 API 失败测试。**

    def test_resource_usage_and_history_are_read_only(monkeypatch):
        monkeypatch.setattr(system, "get_resource_monitoring_service", lambda: stub_service)
        client = TestClient(app)
        assert client.get("/api/system/resource-usage").json()["root_pid"] == 10
        response = client.get("/api/system/resource-usage/history?window_seconds=300")
        assert response.status_code == 200
        assert response.json()["points"][0]["memory_bytes"] == 10

    def test_history_rejects_windows_outside_five_minutes():
        assert TestClient(app).get("/api/system/resource-usage/history?window_seconds=301").status_code == 422

- [ ] **Step 2: 运行失败测试。**

Run: python -m pytest tests/unit/app/api/routes/test_system_resource_usage.py -q

Expected: FAIL，端点为 404 或依赖不存在。

- [ ] **Step 3: 添加懒加载服务与端点。**

在 system.py 中定义模块单例 _resource_monitoring_service 和 get_resource_monitoring_service()；函数内部导入 ResourceMonitoringService，避免路由模块顶层加载。端点必须严格为：

    @router.get("/resource-usage")
    async def get_resource_usage():
        return get_resource_monitoring_service().collect_snapshot()

    @router.get("/resource-usage/history")
    async def get_resource_usage_history(
        window_seconds: int = Query(default=300, ge=2, le=300),
    ):
        return {
            "window_seconds": window_seconds,
            "points": get_resource_monitoring_service().history(window_seconds),
        }

- [ ] **Step 4: 运行 API 和现有系统路由测试。**

Run: python -m pytest tests/unit/app/api/routes/test_system_resource_usage.py tests/unit/app/api/routes/test_system_realtime.py -q

Expected: PASS。

- [ ] **Step 5: 提交。**

    git add app/api/routes/system.py tests/unit/app/api/routes/test_system_resource_usage.py
    git commit -m "feat: expose process resource usage API"

### Task 3: 前端页面、轮询与交互

**Files:**

- Create: app/web/static/js/resource-monitor.js
- Modify: app/web/static/js/app.js
- Modify: app/web/templates/index.html
- Modify: app/web/static/style.css
- Create: tests/unit/test_resource_monitor_frontend_static.py

- [ ] **Step 1: 写页面和生命周期的失败静态测试。**

    def test_resource_monitor_has_navigation_and_live_regions():
        template = read("app/web/templates/index.html")
        assert 'data-section="resource-monitor"' in template
        assert 'id="section-resource-monitor"' in template
        assert 'id="resource-monitor-summary"' in template
        assert 'id="resource-monitor-processes"' in template
        assert 'aria-live="polite"' in template

    def test_resource_monitor_cancels_work_when_not_visible():
        source = read("app/web/static/js/resource-monitor.js")
        assert "AbortController" in source
        assert "document.visibilitychange" in source
        assert "stopResourceMonitoring" in source
        assert "const MAX_POINTS = 150" in source
        assert ".slice(-MAX_POINTS)" in source

- [ ] **Step 2: 运行失败静态测试。**

Run: python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q

Expected: FAIL，入口、模块和页面骨架缺失。

- [ ] **Step 3: 增加导航和语义页面骨架。**

在工作区导航增加 data-section="resource-monitor" 的“系统监控”按钮。创建 section-resource-monitor，内部必须有：

- 状态标题区 resource-monitor-status，带 aria-live="polite"；
- 总览区 resource-monitor-summary；
- CPU 与内存容器 resource-monitor-cpu-chart、resource-monitor-memory-chart；
- 高密度表格 resource-monitor-processes；
- 右侧详情 resource-monitor-detail；
- 可点击并带 data-resource-sort 的 CPU、内存、磁盘 I/O 表头。

在 app.js 导入 startResourceMonitoring / stopResourceMonitoring。仅在 navigateTo("resource-monitor") 启动，所有其他区块均停止；保留现有管线监控的启动/停止语义。

- [ ] **Step 4: 实现 resource-monitor.js。**

模块导出：

    export function startResourceMonitoring() { poll(); }
    export function stopResourceMonitoring() { controller?.abort(); }

模块用 apiCall("GET", "/api/system/resource-usage", null, { signal }) 首次立即请求，之后每 2 秒使用 setTimeout 调度。每次请求前中止旧 AbortController；页面不可见中止请求且不再调度；重新可见后立刻采样。连续失败时延迟依次为 4、6、8、10 秒，成功后回到 2 秒。只保留 150 个 {sampled_at, cpu_percent, memory_bytes} 点，失败时保留上一帧并把状态改为“采样暂时不可用，保留上一帧数据”。

进程行使用 document.createElement 和 textContent 渲染，禁止将命令、角色或名称插入 innerHTML。按 CPU 降序为初始排序；CPU、内存、磁盘 I/O 表头可切换升降序。选择进程后在详情展示安全命令摘要、父 PID、启动时间、状态与近一分钟小趋势；进程消失则显示“PID N 已退出；保留最后一次采样信息”。

使用两个既有 ECharts 实例渲染 CPU 和内存线图；横轴取采样时间，CPU 单位 %，内存单位 MiB。无 ECharts 时保留数字与表格，并显示“图表组件尚未就绪”，不得阻断轮询。

- [ ] **Step 5: 增加最小样式和静态断言。**

样式要求：总览为六列自适应卡片；图表宽屏两列、900px 以下单列；表格最小宽度 900px 且外层横向滚动；数值右对齐和等宽字体；详情抽屉有隐藏与打开状态；深浅主题复用现有 CSS 变量。

在静态测试中断言：缓存版本 resource-monitor.js?v=20260805a、MAX_POINTS = 150、AbortController、visibilitychange、textContent、data-resource-sort、selectedProcessPid、已退出 全部存在。

Run: python -m pytest tests/unit/test_resource_monitor_frontend_static.py -q && node --check app/web/static/js/resource-monitor.js && node --check app/web/static/js/app.js

Expected: PASS。

- [ ] **Step 6: 提交。**

    git add app/web/static/js/resource-monitor.js app/web/static/js/app.js app/web/templates/index.html app/web/static/style.css tests/unit/test_resource_monitor_frontend_static.py
    git commit -m "feat: add live resource monitoring page"

### Task 4: 浏览器验收、文档与报告

**Files:**

- Modify: docs/modules/app_api.md
- Modify: docs/modules/app_web.md
- Modify: docs/FILE_GUIDE.md
- Modify: docs/CHANGELOG.md
- Create: .ai/reports/2026-08-05-alphafoundry-resource-monitor.md

- [ ] **Step 1: 启动应用并做真实浏览器验收。**

Run: python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000

在 Playwright 中打开 http://127.0.0.1:8000，进入“系统监控”。实际检查：

1. 初始状态显示预热，第二个样本后变为实时采样；
2. CPU、内存图表各有至少两个点；
3. 进程表只包含端点 JSON 返回的 PID；
4. CPU、内存、磁盘 I/O 排序生效；
5. 点击行能打开详情；
6. 切换到其他页面后不再每 2 秒请求资源端点；
7. 模拟 API 失败时状态保留上一帧数据。

- [ ] **Step 2: 同步文档。**

docs/modules/app_api.md 说明两个 GET 端点、2–300 秒窗口、仅 API 进程树且不返回整机/无关进程数据。  
docs/modules/app_web.md 说明模块、轮询生命周期、150 点限制和“网络连接数而非按进程网络字节数”。  
docs/FILE_GUIDE.md 索引服务、JS 和三个新测试；docs/CHANGELOG.md 顶部日期项说明该功能及降级语义。

- [ ] **Step 3: 写入只含实际证据的任务报告并运行完整检查。**

报告必须列出实际命令、通过/失败结果、浏览器截图路径、未验证项和 psutil 跨平台字段限制；不得写入尚未执行的结果。

Run: python scripts/check_doc_sync.py && python scripts/check_task_completion.py && python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/app/api/routes/test_system_resource_usage.py tests/unit/test_resource_monitor_frontend_static.py -q && git diff --check

Expected: 所有可用检查 PASS；环境前置条件导致的失败原样记录于报告。

- [ ] **Step 4: 提交文档和报告。**

    git add docs/modules/app_api.md docs/modules/app_web.md docs/FILE_GUIDE.md docs/CHANGELOG.md .ai/reports/2026-08-05-alphafoundry-resource-monitor.md
    git commit -m "docs: document resource monitoring"

## 计划自审

- 覆盖进程边界、CPU/内存/磁盘 I/O/网络连接数、150 点历史、进程归因、可取消实时轮询、排序、详情、降级、日志、API、浏览器验证、文档和任务报告。
- 不会使用整机网络字节数冒充 AlphaFoundry 数据；按进程网络字节数是明确非目标。
- 名称在所有任务中一致：ResourceMonitoringService、collect_snapshot()、history()、startResourceMonitoring()、stopResourceMonitoring()。
- 功能不改动 Tauri、sidecar、安装、自动更新或路径配置，不产生 Windows 桌面验证声明。
