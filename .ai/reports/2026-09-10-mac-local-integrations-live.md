# Mac 本机集成真实验证实现记录

## 已实现

- 保留本机软件发现探测的无副作用语义，新增显式、幂等、异步可查询的真实验证接口。
- Excel、Word、PowerPoint 和 Wind Excel 仅在用户点击后进入受管目录与可终止子进程；Office 临时文件使用各应用容器内由验证 UUID 决定的名称，并在子进程与监督进程两层精确清理。
- Excel 使用独立 `xlwings.App` 实例验证公式全量重算、保存、关闭、重新打开与读取，并在结束时退出本轮实例；正式 `.venv` 复用报告刷新器的 macOS `aeosa` 兼容入口，不依赖隐藏目录下会被 Python 跳过的 `.pth`。Word 使用安全种子文件；PowerPoint 由 AppleScript 直接创建演示文稿，两者都完成真实修改、保存、关闭与重开读取，PowerPoint 不依赖未声明的 `python-pptx`。
- Wind 从已管理的 `huaan-etf-weekly` 当前发布版本选择 Wind 工作簿策略，先刷新最小策略副本，再刷新全部策略副本；两级都复用既有锁、策略超时、必需单元格与源文件哈希保护。刷新运行目录放在 Excel 应用容器内并沿用 UUID、配额、保留期和精确清理规则，避免普通 Workbench 目录触发逐文件授权窗口。
- 验证 worker 使用独立 POSIX 进程组，超时先 TERM 再 KILL 整个进程组；Wind 内层 Excel 实例在创建后、打开工作簿前即上报 PID，监督器只清理本轮上报实例。Windows 内部边界使用系统进程树终止命令。所有目标的业务预算为 180 秒，Wind 烟测与全量刷新共享该预算，每项策略超时会收窄到剩余时间；外层保留十秒清理协调宽限。
- iFinD HTTP 使用既有客户端契约执行登录、健康检查、最小只读基础数据查询与关闭，不持久化 Token；空数据、鉴权、权限和配额失败不会标记健康。
- 本机设置页按能力显示“真实验证”、运行中状态和独立的最近验证时间；未执行验证时不会把发现时间冒充验证时间，iFinD 继续链接数据源配置页。
- 正式服务首次重启暴露 `data_layer.adapters` 父包会在导入 iFinD HTTP 时初始化全部适配器并错误要求 `psycopg2`；两级包入口已改为保留公开 API 的按需装载，未新增数据库或厂商依赖。

## 自动化验证

- `tests/research_web/test_local_integrations.py`：验证接口、幂等、状态映射、安全投影、Excel 全量重算、Wind 双阶段与源哈希、进程身份核对及超时清理。
- `tests/research_web/test_connection_center.py`：iFinD SDK/HTTP 登录、健康检查、只读数据查询、空结果拒绝、失败关闭与 MockTransport 契约。
- 同一测试文件用隔离子进程阻止 `psycopg2`，验证导入 iFinD HTTP 不会初始化 CNINFO、数据库仓储或 iFinD SDK；修复前该测试失败，惰性入口修复后通过。
- 同一文件增加隔离子进程回归，明确阻断 `psycopg2` 后导入 iFinD HTTP 不得初始化 CNINFO 或 iFinD SDK；项目 `.venv` 的服务管理器导入路径已实际通过。
- `tests/javascript/research_web_local_integrations_ui.test.mjs`：按钮、加载、轮询、配置链接、ARIA 与 44px 操作目标。
- 任务分支相关 Python 回归：`129 passed, 1 skipped`，本机设置 JavaScript 契约：`17 passed`。与最新主分支 Tabbit 功能合并后，相关 Python 回归为 `131 passed, 1 skipped`，本机与设置页 JavaScript 契约为 `18 passed`；Ruff、Black、isort、架构/文档同步门禁，以及使用 `--follow-imports=silent` 限定四个改动模块的 mypy 检查通过。
- 首次正式重启复现项目 `.venv` 缺少 `psycopg2` 时服务管理器导入失败；`data_layer.adapters` 与 `data_layer.adapters.ifind` 改为按符号惰性装载后，同一 `.venv` 导入路径输出 `WebServiceManager` 且不再加载数据库或 SDK。相邻回归更新为 `132 passed, 1 skipped`，iFinD/CNINFO 单元测试 `11 passed`，相关 Ruff、Black、isort 通过。
- 用户确认后，正式 `.venv` 安装项目既有 `excel` 可选组中的 `xlwings 0.37.2` 与 `appscript 1.3.0`；未改依赖声明或锁文件。新增回归在修复前分别复现 macOS 引擎未激活、PowerPoint 依赖未声明包以及 Wind 运行目录位于 Excel 沙箱之外，修复后 `test_local_integrations.py` 为 `42 passed, 1 skipped`。

## 2026-09-10 Mac 实机证据

- Research Web 隔离服务在 `127.0.0.1:8098` 启动并完成本机集成 API 生命周期；正式 `8088` 服务在发布后受控重启。
- Excel：真实验证 `86dfb58e-d6d3-4ee3-9c72-3d9f6e2b2b00` 完成并返回 `available`。工作簿写入 `19 + 23`、执行 full rebuild、保存、关闭、重开后读取为 `42`；验证前后无 Excel 残留进程。
- Word：真实验证 `a24255f0-41cf-4a60-90ee-b0ceedb7bef5` 完成并返回 `available`；验证文档已由 Word 精确按文件名打开、修改、保存、关闭并重开读取，沙箱文件随后删除。
- PowerPoint：真实验证 `6853f62a-8549-461e-8658-ae577af8397c` 完成并返回 `available`；验证演示文稿已由 PowerPoint 精确按文件名打开、修改、保存、关闭并重开读取，沙箱文件随后删除。
- Wind：终端已从登录窗口进入主窗口，WindAddin 与终端均已发现；登录后的真实验证 `5dba985e-a985-478f-9c09-5cb9155f6a73` 在约 170 秒后返回 `timeout`，因此保持不可调用。超时后未发现 Excel、osascript 或验证 worker 残留进程；发布源只读处理，未被写回。
- iFinD HTTP：当前未配置账号与 Base URL，未执行厂商登录；macOS 本地 SDK 为不适用，HTTP 路径保持待配置。
- 首轮 Wind 超时曾暴露 Excel PID 与 Office 容器文件清理缺口；本轮增加打开前 PID、启动时间与固定可执行命令组成的身份指纹上报，父进程只在身份复核匹配时兜底清理。重复超时验收未再出现残留，PID 被复用时也不会误杀其他进程。
- 正式 `8088` 首轮验证中 Word 返回 `available`；Excel 因验证器未激活项目已有 `aeosa` 兼容入口而失败，PowerPoint 因误用正式环境未声明的 `python-pptx` 而失败。两项均已由 RED/GREEN 回归覆盖；Excel 修正后的本机独立烟测返回 `available`，PowerPoint 的创建、写入、保存、按随机名称重新绑定、关闭和重开脚本已在本机返回预期文本。
- 正式 Wind 验证 `99ce4a97-a09a-4f20-b846-b37c6682b34c` 在用户批准 `.refreshing.xlsx` 文件访问后仍于约 171 秒返回 `timeout`；这证明登录与插件发现成立，但普通 Workbench 运行目录会消耗人工授权时间。本轮把 Wind 运行副本迁入 Excel 应用沙箱，需在修复发布并重启正式服务后重新形成最终调用证据。

## 验收边界

本记录仅声明 Excel、Word 与 PowerPoint 在当前 Mac 上通过真实调用。Wind 已登录但真实工作簿刷新仍超时，不能声明可用；当前终端账号的数据权限、插件会话与公式刷新链路仍需厂商侧排查。iFinD HTTP 因未配置而未验证。Windows/Linux 不运行 macOS 验证器，保持未验证或不适用状态。
