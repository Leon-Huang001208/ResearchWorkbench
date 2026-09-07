# Research Web 会话删除与 30 天保留期

## 范围

本改动在现有 Research Workbench 会话导航和历史接口上增加可恢复删除、恢复、显式永久删除与 30 天到期清理。原 DSH 仓库同步增加 `session.delete` 原生协议和第一方持久化删除能力；不把 Workspace 归档或仅隐藏产品索引描述为永久删除。

## 当前契约

- `DELETE /api/research/sessions/{id}` 只写入 `deleted_at`，默认会话列表不再返回该项。
- `POST /api/research/sessions/{id}/restore` 在 30 天窗口内恢复；原生删除已经开始后拒绝恢复。
- `DELETE /api/research/sessions/{id}/permanent` 调用 DSH `session.delete` 并要求 `deletedSessionIds` 明确包含根会话，然后删除 Workbench 会话目录及关联查询、交接、资产观察、报告运行、收据和审计索引。
- 服务启动时立即清理已过期墓碑；服务持续在线时，每 6 小时重试一次，因此不依赖用户打开“已删除”页面。
- DSH 删除会预检活动所有权和后代，会话运行中或归属不明时拒绝；原生失败时 Workbench 墓碑保留，后续可重试而不会误报成功。

## 数据边界

Workbench 的会话目录包含本产品上传附件、数据集和产物，永久删除时随会话清理。DSH 删除原生事件日志及其会话级衍生查询、投影缓存和 Workspace 引用；DSH 全局内容寻址附件存储不在本次无引用垃圾回收范围内，界面不会把它误称为已按会话删除。

## 验证

- Research Workbench：`tests/research_web` 431 passed、3 skipped；相关协议与删除 API 聚焦回归 32 passed；JavaScript 161 passed。
- DSH：原生持久层、JSONL、SQLite、API Proxy、查询索引、投影缓存和 Workspace 共 646 passed；Host/Client TypeScript 构建与 oxlint 通过。
- DSH 文档：28 项 `doc-sync` 门禁全部通过，英文／中文说明、RPC 目录和 Cordis 目录一致。
- 浏览器：导航壳 4 项、页面／视口 15 项及完整浅色／深色外观回归通过；覆盖 1440、1600、1920、820、390px，零模型写入、零横向溢出、零脚本错误。
- 独立 3181 DSH 真实进程完成 `session.create → session.delete(cascade=true) → session.list/history`：删除响应包含根 ID，列表为空，历史明确返回 `session-not-found`。
- 架构同步门禁零违规，Python／JavaScript 语法、ruff、black、isort 与两仓库差异检查通过。
