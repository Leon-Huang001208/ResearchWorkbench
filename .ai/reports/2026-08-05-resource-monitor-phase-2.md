# 资源监控第二期交付报告

日期：2026-08-05

## 变更范围

- 新增每 PID 资源任务登记器，记录抓取、PDF、知识处理、Wind 与报告渲染的安全上下文；失败记录不含异常原文。
- 资源采样仅合并 API 进程树、现有调度器 PID、知识 Worker PID 与受控任务快照；不扫描系统其他进程。
- 新增资源异常协调器，复用既有 `alert_payload` / `incident_record` 持久化状态机，支持任务失败、受控 PID 不可用、采样失败与持续资源压力的去重、确认、自动恢复或人工解决。
- 新增资源事件查询、确认、解决 API；系统监控页新增异常置顶、活跃归因与默认 90 天历史筛选。实时曲线仍为 5 分钟、150 点内存窗口。

## 已执行验证

- `python -m pytest tests/unit/test_resource_task_registry.py tests/unit/test_monitoring.py -q`：47 passed。
- `python -m pytest tests/unit/test_resource_monitor_alert_service.py tests/unit/test_resource_monitor_service.py tests/unit/test_resource_task_registry.py -q`：27 passed。
- `python -m pytest tests/unit/app/api/routes/test_resource_monitoring.py tests/unit/workers/test_knowledge_worker.py tests/unit/test_resource_monitor_service.py tests/unit/test_resource_monitor_alert_service.py -q`：37 passed。
- `python -m pytest tests/unit/workers/test_knowledge_worker.py tests/unit/test_report_projects_api.py tests/unit/workers/test_watchdog.py -q`：84 passed，4 个既有 FastAPI 生命周期弃用警告。
- `node --check app/web/static/js/resource-monitor.js`：通过。
- `python -m pytest tests/unit/test_resource_monitor_frontend_static.py tests/unit/test_live_monitor_ui_static.py tests/unit/app/api/routes/test_resource_monitoring.py -q`：16 passed。
- 最终针对性质量链：`python -m pytest ... -q`：85 passed；`ruff check`、`black --check`、`isort --check-only`、`python scripts/check_doc_sync.py`、`python scripts/check_task_completion.py` 和 `git diff --check` 均通过。
- 分支桌面预览：重启 `npm run desktop:preview -- --use-stable-data` 后，Tauri 壳加载 `resource-monitor.js?v=20260805c` 并持续请求资源快照与资源事件接口；`GET /api/system/resource-usage` 与 `GET /api/system/resource-events?days=90&status=all` 均返回 200。实测样本包含 `confidence` 与 `active_tasks`，事件接口返回 `days/items`；当时无持久化异常。预览快照状态为 `degraded`，原因是本机 psutil 个别字段受限，资源数据仍正常返回。

## 未验证项与风险

- 尚未在真实 Windows 桌面环境验证；本次没有修改 Tauri 安装、sidecar 或平台特定代码，因此不宣称 Windows 已验证。
- 资源事件当前不自动删除；默认查询窗口为 90 天，但未恢复事件始终返回。长期保留策略应由后续运维配置单独决定。
- 桌面原生通知不在本期范围；异常先在系统监控页置顶，后续若启用 Tauri 通知需处理权限、去重与用户偏好。
