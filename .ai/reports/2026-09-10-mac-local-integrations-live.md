# Mac 本机集成真实验证实现记录

## 已实现

- 保留本机软件发现探测的无副作用语义，新增显式、幂等、异步可查询的真实验证接口。
- Excel、Word、PowerPoint 和 Wind Excel 仅在用户点击后进入受管目录与可终止子进程；Office 临时文件使用各应用容器内由验证 UUID 决定的名称，并在子进程与监督进程两层精确清理。
- Excel 使用独立 `xlwings.App` 实例验证公式全量重算、保存、关闭、重新打开与读取，并在结束时退出本轮实例；Word/PPT 先生成安全种子文件，再使用 macOS AppleScript 完成真实修改、保存、关闭与重开读取。
- Wind 从已管理的 `huaan-etf-weekly` 当前发布版本选择 Wind 工作簿策略，先刷新最小策略副本，再刷新全部策略副本；两级都复用既有锁、策略超时、必需单元格与源文件哈希保护。
- 验证 worker 使用独立 POSIX 进程组，超时先 TERM 再 KILL 整个进程组；Wind 内层 Excel 实例在创建后、打开工作簿前即上报 PID，监督器只清理本轮上报实例。Windows 内部边界使用系统进程树终止命令。所有目标的业务预算为 180 秒，Wind 烟测与全量刷新共享该预算，每项策略超时会收窄到剩余时间；外层保留十秒清理协调宽限。
- iFinD HTTP 使用既有客户端契约执行登录、健康检查、最小只读基础数据查询与关闭，不持久化 Token；空数据、鉴权、权限和配额失败不会标记健康。
- 本机设置页按能力显示“真实验证”、运行中状态和独立的最近验证时间；未执行验证时不会把发现时间冒充验证时间，iFinD 继续链接数据源配置页。

## 自动化验证

- `tests/research_web/test_local_integrations.py`：验证接口、幂等、状态映射、安全投影、Excel 全量重算、Wind 双阶段与源哈希、进程身份核对及超时清理。
- `tests/research_web/test_connection_center.py`：iFinD SDK/HTTP 登录、健康检查、只读数据查询、空结果拒绝、失败关闭与 MockTransport 契约。
- `tests/javascript/research_web_local_integrations_ui.test.mjs`：按钮、加载、轮询、配置链接、ARIA 与 44px 操作目标。
- 任务分支相关 Python 回归：`129 passed, 1 skipped`，本机设置 JavaScript 契约：`17 passed`。与最新主分支 Tabbit 功能合并后，相关 Python 回归为 `131 passed, 1 skipped`，本机与设置页 JavaScript 契约为 `18 passed`；Ruff、Black、isort、架构/文档同步门禁，以及使用 `--follow-imports=silent` 限定四个改动模块的 mypy 检查通过。

## 2026-09-10 Mac 实机证据

- Research Web 隔离服务在 `127.0.0.1:8098` 启动并完成本机集成 API 生命周期；正式 `8088` 服务在发布后受控重启。
- Excel：真实验证 `86dfb58e-d6d3-4ee3-9c72-3d9f6e2b2b00` 完成并返回 `available`。工作簿写入 `19 + 23`、执行 full rebuild、保存、关闭、重开后读取为 `42`；验证前后无 Excel 残留进程。
- Word：真实验证 `a24255f0-41cf-4a60-90ee-b0ceedb7bef5` 完成并返回 `available`；验证文档已由 Word 精确按文件名打开、修改、保存、关闭并重开读取，沙箱文件随后删除。
- PowerPoint：真实验证 `6853f62a-8549-461e-8658-ae577af8397c` 完成并返回 `available`；验证演示文稿已由 PowerPoint 精确按文件名打开、修改、保存、关闭并重开读取，沙箱文件随后删除。
- Wind：终端已从登录窗口进入主窗口，WindAddin 与终端均已发现；登录后的真实验证 `5dba985e-a985-478f-9c09-5cb9155f6a73` 在约 170 秒后返回 `timeout`，因此保持不可调用。超时后未发现 Excel、osascript 或验证 worker 残留进程；发布源只读处理，未被写回。
- iFinD HTTP：当前未配置账号与 Base URL，未执行厂商登录；macOS 本地 SDK 为不适用，HTTP 路径保持待配置。
- 首轮 Wind 超时曾暴露 Excel PID 与 Office 容器文件清理缺口；本轮增加打开前 PID、启动时间与固定可执行命令组成的身份指纹上报，父进程只在身份复核匹配时兜底清理。重复超时验收未再出现残留，PID 被复用时也不会误杀其他进程。

## 验收边界

本记录仅声明 Excel、Word 与 PowerPoint 在当前 Mac 上通过真实调用。Wind 已登录但真实工作簿刷新仍超时，不能声明可用；当前终端账号的数据权限、插件会话与公式刷新链路仍需厂商侧排查。iFinD HTTP 因未配置而未验证。Windows/Linux 不运行 macOS 验证器，保持未验证或不适用状态。
