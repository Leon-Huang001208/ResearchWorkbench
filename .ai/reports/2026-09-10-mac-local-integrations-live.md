# Mac 本机集成真实验证实现记录

## 已实现

- 保留本机软件发现探测的无副作用语义，新增显式、幂等、异步可查询的真实验证接口。
- Excel、Word、PowerPoint 和 Wind Excel 仅在用户点击后进入受管目录与可终止子进程。
- Excel 验证覆盖创建、公式全量重算、保存、关闭、重新打开与读取；Word/PPT 使用 macOS AppleScript 完成临时文档往返。
- Wind 从已管理的 `huaan-etf-weekly` 当前发布版本选择 Wind 工作簿策略，先刷新最小策略副本，再刷新全部策略副本；两级都复用既有锁、策略超时、必需单元格与源文件哈希保护。
- 验证 worker 使用独立 POSIX 进程组，超时先 TERM 再 KILL 整个进程组；Windows 内部边界使用系统进程树终止命令。所有目标的业务预算为 180 秒，Wind 烟测与全量刷新共享该预算，每项策略超时会收窄到剩余时间；外层只保留进程协调宽限。
- iFinD HTTP 使用既有客户端契约执行登录、健康检查、最小只读基础数据查询与关闭，不持久化 Token；空数据、鉴权、权限和配额失败不会标记健康。
- 本机设置页按能力显示“真实验证”、运行中状态和独立的最近验证时间；未执行验证时不会把发现时间冒充验证时间，iFinD 继续链接数据源配置页。

## 自动化验证

- `tests/research_web/test_local_integrations.py`：验证接口、幂等、状态映射、安全投影、Excel 全量重算、Wind 双阶段与源哈希、进程组超时清理。
- `tests/research_web/test_connection_center.py`：iFinD SDK/HTTP 登录、健康检查、只读数据查询、空结果拒绝、失败关闭与 MockTransport 契约。
- `tests/javascript/research_web_local_integrations_ui.test.mjs`：按钮、加载、轮询、配置链接、ARIA 与 44px 操作目标。

## 验收边界

本记录不声明真实 Office、Wind 或 iFinD 厂商账号已经通过。本线程未启动厂商应用、未读取账号，也未执行真实工作簿刷新；实际 macOS 自动化授权、Wind 登录与受管工作簿验证由交付主任务在审阅后执行。Windows/Linux 不运行 macOS 验证器，保持未验证或不适用状态。
