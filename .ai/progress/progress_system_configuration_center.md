# 系统配置中心进度

- 任务 ID：`system-configuration-center`
- 状态：已完成（`done`）
- 开始日期：2026-07-12
- 影响子系统：`core/settings`、`services`、`app/api`、`app/web`、`data_layer/crawlers/zq`
- 已实现：运行时 `.env` 路径兼容、知秋 JSON/旧格式账号与轮询配置、五分区脱敏配置服务、加锁原子持久化、运行时刷新、数据库重启语义、严格配置 API 和系统配置 Web 页面。
- 安全与兼容：秘密三态、`original_name` 改名关联、安全 422、知秋 JSON 权威空账号语义、真实非持久化连接探针、线程/进程事务锁、严格 dotenv、Windows 权限兼容和客户端资源关闭均有回归覆盖。
- 文档：已同步 `.env.example`、API/Web/爬虫模块文档、架构、开发映射、文件指南、参考手册、更新日志和测试审计记录；Python 文件索引由脚本重新生成。
- 测试记录：配置、API、iFinD、知秋 fresh focused suite `78 passed`；配置前端 `14 passed`；Playwright 已验证真实保存、脱敏回显、改名保密、清除互斥、数据库重启提示及 1440/820 响应式布局。
- 全仓门禁：`ruff`、`black --check`、`isort --check-only`、全量 `mypy` 和全量 pytest 均已通过；任务、文档和 Python 索引检查通过。
- 最终安全修复：默认关闭 CORS、配置 API 进程级 CSRF、防止旧秘密发送到变化后的 Provider/iFinD 端点，并让冻结桌面启动优先加载持久 `.env`；状态继续保持 `doing`。
- 最终安全 focused：配置/API/runtime/frontend 与 desktop launcher 回归 `64 passed`。
- 安全复核加固：Provider 未提交 `original_name` 时仍按当前名称绑定旧秘密；默认 Trusted Host 仅允许本机地址和测试主机，配置 API 同时校验本地/Tauri/显式一致 Origin。关联 focused 回归 `92 passed`，状态继续保持 `doing`。
- 收尾：重复测试模块、数据库测试隔离、报告资产、类型债和格式债已完成清理；任务可安全整合。
