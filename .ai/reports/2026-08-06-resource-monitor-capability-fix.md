# 系统监控能力兼容修复报告

日期：2026-08-06

## 问题与原因

- macOS 当前 `psutil` 不提供进程级 `io_counters()`，此前被当作整体监控降级，页面仅显示 `--`。
- 当前 `psutil` 版本使用兼容接口 `connections()`，而前端数据采集只调用 `net_connections()`，导致网络连接数不可用。
- 整机内存摘要使用单行省略样式，导致“可用内存”被截断。

## 修复

- 网络连接统计按 `net_connections()`、`connections()` 的顺序兼容采集。
- 将进程磁盘 I/O 与网络连接这两项可选能力从整体健康状态判定中分离；其余字段不可用仍会使监控标记为 `degraded`。
- 前端将不可用磁盘 I/O 明确显示为“当前平台不支持”，并让整机内存摘要自动换行完整展示。
- 更新静态资源版本号，避免桌面 WebView 使用旧缓存。

## 验证证据

- `python -m pytest tests/unit/test_resource_monitor_service.py tests/unit/test_resource_monitor_frontend_static.py tests/unit/app/api/routes/test_resource_monitoring.py -q`：37 passed。
- `ruff check`、`black --check`、`isort --check-only` 及两个前端模块的 `node --check`：通过。
- 主桌面端重启后，`/api/system/resource-usage` 实测返回 `status: ok`、网络连接数为非空；系统监控页显示完整整机内存、网络数值及“当前平台不支持”的磁盘状态。
