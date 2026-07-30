# 测试套件恢复报告

## 范围

本次收尾恢复默认 `tests/` 套件的可重复执行性，并修正与当前产品行为不一致的测试契约。

## 修复内容

- 将摄入管理 `dry_run` 放在数据库访问之前，使离线预检不依赖 PostgreSQL。
- 避免治理结构化日志覆盖 Python 日志保留字段 `name`。
- 恢复三份内置产业链图谱，并纳入桌面 Python sidecar 打包输入。
- 将 PostgreSQL 集成用例改为仅在数据库健康时运行；本地未配置可用 PostgreSQL 时会明确跳过。
- 对齐桌面启动、配置持久化、前端资源版本和宏观敏感度测试与当前实现。

## 验证

- `python -m pytest tests/ -q`：通过（0 failed）。
- 目标回归测试：20 passed、3 skipped。
- 三份 `data/industry_graphs/*.json` 均可被 JSON 解析。

## 已知边界

- 本地全量 Python 测试不能替代 Windows 验证。由于修改了 desktop sidecar 打包输入，合并前仍须由原生 Windows CI runner 完成依赖安装、sidecar、Tauri 安装包和基础启动/健康检查；发版前还须在真实 Windows 环境完成安装级冒烟测试。
- 未配置可用 PostgreSQL 的环境不会执行依赖真实数据库的集成用例；这些用例会显示为 skipped，而不是伪造通过。
