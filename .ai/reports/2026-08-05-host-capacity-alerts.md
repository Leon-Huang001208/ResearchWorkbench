# 整机容量告警交付报告

**日期：** 2026-08-05
**范围：** `ResourceMonitorAlertService` 的整机容量告警与单元测试。

## 变更

- 读取快照 `host.cpu_percent` 与 `host.memory_available_percent`，分别以 CPU 85%/95% 和可用内存 15%/8% 作为 warning/critical 阈值；各状态均需连续三个有效采样周期。
- 使用稳定去重键 `host_cpu_pressure` 与 `host_memory_pressure`。同一未解决 warning 在连续三个 critical 样本后通过带 `status != resolved` 条件的原子更新变为 critical，仅更新详情，保留 alert ID、确认与解决状态；关联 incident 不在升级时重写。
- 连续三个健康有效样本自动解决；缺失、`None`、布尔、NaN、无穷或不在 0–100 范围内的主机字段不触发压力或恢复，并会中断该指标的压力/恢复连续计数。
- 原有 API、任务、Worker 与受控进程事件统一标记 `source_scope=alphafoundry`；主机事件标记 `source_scope=host_capacity`，其元数据只保存事件类别、来源、两项容量百分比、阈值和内部去重键，不保存原始采集错误。

## 验证

| 命令 | 实际结果 |
| --- | --- |
| `python -m pytest tests/unit/test_resource_monitor_alert_service.py tests/unit/test_resource_monitor_runtime.py tests/unit/data_layer/repositories/test_monitoring_repository.py -q` | 27 passed |
| `ruff check services/resource_monitor_alert_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_monitor_alert_service.py tests/unit/data_layer/repositories/test_monitoring_repository.py` | passed |
| `black --check services/resource_monitor_alert_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_monitor_alert_service.py tests/unit/data_layer/repositories/test_monitoring_repository.py` | passed |
| `isort --check-only services/resource_monitor_alert_service.py data_layer/repositories/monitoring_repository.py tests/unit/test_resource_monitor_alert_service.py tests/unit/data_layer/repositories/test_monitoring_repository.py` | passed |
| `python scripts/check_doc_sync.py` | passed（无需要同步的源码文档） |
| `git diff --check` | passed |

## 风险

- 告警状态机使用内存伪仓储，条件更新另有 SQLite 单元测试；未连接真实 PostgreSQL 或进行跨进程并发压测。
- 主机读数由既有资源监控采集器提供；字段不可用时按设计保持当前未解决主机事件，等待后续有效健康采样。
