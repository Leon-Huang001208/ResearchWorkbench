# Mac 本机集成真实验证实现记录

## 已实现

- 保留本机软件发现探测的无副作用语义，新增显式、幂等、异步可查询的真实验证接口。
- Excel、Word、PowerPoint 和 Wind Excel 仅在用户点击后进入受管目录与可终止子进程；Office 临时文件使用各应用容器内由验证 UUID 决定的名称，并在子进程与监督进程两层精确清理。
- Excel 使用独立 `xlwings.App` 实例验证公式全量重算、保存、关闭、重新打开与读取，并在结束时退出本轮实例；正式 `.venv` 复用报告刷新器的 macOS `aeosa` 兼容入口，不依赖隐藏目录下会被 Python 跳过的 `.pth`。Word 使用安全种子文件；PowerPoint 由 AppleScript 直接创建演示文稿，两者都完成真实修改、保存、关闭与重开读取，PowerPoint 不依赖未声明的 `python-pptx`。
- Wind 本机集成不再用某一份报告工作簿代表插件状态，而是复用生产 `WindExcelClient`，在当前已登录的 Excel 应用中创建独占空白工作簿并执行一条最小公式心跳。该工作簿在结束时关闭，用户已有工作簿与 Excel 应用不由验证器清理；具体报告工作簿继续由各自 Workflow 单独判断。
- 验证 worker 使用独立 POSIX 进程组，超时先 TERM 再 KILL 整个进程组。监督器只接收并清理验证器真正拥有的 Excel 进程身份；复用既有 Excel 时不再上报 PID，避免误关用户应用。Windows 内部边界使用系统进程树终止命令，所有目标保留 180 秒业务预算与十秒清理协调宽限。
- macOS Wind 验证通过 LaunchServices 正常启动 Excel，检测 Wind 插件独立的“安全验证”窗口；二维码授权未完成时返回 `authorization_required` 并投影为“待授权”，不会误报成终端未登录或通用异常。
- iFinD HTTP 使用既有客户端契约执行登录、健康检查、最小只读基础数据查询与关闭，不持久化 Token；空数据、鉴权、权限和配额失败不会标记健康。
- 本机设置页按能力显示“真实验证”、运行中状态和独立的最近验证时间；未执行验证时不会把发现时间冒充验证时间，iFinD 继续链接数据源配置页。
- 正式服务首次重启暴露 `data_layer.adapters` 父包会在导入 iFinD HTTP 时初始化全部适配器并错误要求 `psycopg2`；两级包入口已改为保留公开 API 的按需装载，未新增数据库或厂商依赖。

## 自动化验证

- `tests/research_web/test_local_integrations.py`：验证接口、幂等、状态映射、安全投影、Excel 全量重算、Wind 隔离公式工作簿、安全验证窗口识别、进程所有权核对及超时清理。
- `tests/unit/test_wind_adapter.py`：Wind 客户端复用登录中的 Excel 应用，但验证时新建并独占工作簿；关闭验证工作簿不得退出用户已有 Excel。
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
- Wind：终端与 WindAddin 均已发现。生产公式客户端曾两次真实返回 `贵州茅台酒股份有限公司`，一次正式 API 验证 `796fccae-78a0-4c25-b2d2-8513dc4b0f55` 返回 `available`；随后冷启动 Excel 时厂商弹出独立“安全验证”窗口，验证 `49fd1b5d-ecf8-435e-bc1e-063259a638aa` 被准确投影为 `authorization_required`。最终复验 `15ebc756-4525-4d64-b3f9-1e0ddaa38146` 返回 `available`，Wind 终端与 Excel 插件均标记为可用。
- iFinD HTTP：当前未配置账号与 Base URL，未执行厂商登录；macOS 本地 SDK 为不适用，HTTP 路径保持待配置。
- 首轮 Wind 超时曾暴露 Excel PID 与 Office 容器文件清理缺口；本轮增加 PID、启动时间与固定可执行命令组成的身份指纹，并进一步只上报验证器拥有的 Excel 进程。复用用户 Excel 时只关闭隔离验证工作簿，失败与超时均不得退出用户应用。
- 正式 `8088` 首轮验证中 Word 返回 `available`；Excel 因验证器未激活项目已有 `aeosa` 兼容入口而失败，PowerPoint 因误用正式环境未声明的 `python-pptx` 而失败。两项均已由 RED/GREEN 回归覆盖；Excel 修正后的本机独立烟测返回 `available`，PowerPoint 的创建、写入、保存、按随机名称重新绑定、关闭和重开脚本已在本机返回预期文本。
- `huaan-etf-weekly` 完整工作簿副本多次在 180 秒预算内未完成；macOS 路径已跳过不适用的 `RefreshAll` 并改用应用级计算，但报告仍保持独立的超时结论。该结果不再覆盖最小 Wind 插件公式验证，也未修改发布源。

## 验收边界

本记录声明 Excel、Word 与 PowerPoint 在当前 Mac 上通过真实调用；Wind 终端与 Excel 插件已完成最小公式心跳真实验证并返回 `available`。`huaan-etf-weekly` 完整工作簿刷新仍超时，是独立的报告 Workflow 结论。iFinD HTTP 因未配置而未验证。Windows/Linux 不运行 macOS 验证器，保持未验证或不适用状态。

## 2026-09-11 最终复验

- 正式 `8088` 依次完成 Excel `4a611f32-ec38-4d19-aecf-75978b0396ff`、Word、PowerPoint `cdbff5e8-442d-4107-8a8d-f45232547663` 与 Wind `446f708c-9183-456a-a229-c9a9510d0373` 真实验证，四个目标均返回 `available`；最终 Wind 再验证 `b629a6a5-9e54-47ca-a0ad-d7d2ef8fcde3` 也返回 `available`。
- 设置页汇总为 7 项可用、5 项需处理；Excel、Excel 自动化桥、Word、PowerPoint、Wind 终端与 Wind Excel 插件均显示已发现、已授权、已验证和可调用。浏览器控制台为 0 error、0 warning，截图保存在本机脱敏证据目录 `~/.research-workbench/evidence/`。
- `huaan-etf-weekly` 当前版本 3 包含 2 个 Wind 工作簿；隔离副本刷新再次在 180 秒内返回 `verification_timed_out`，两个发布源文件前后哈希一致。该结论没有覆盖 Wind 插件的最小公式验证。
- Wind 页面状态一度回落是五分钟真实验证 TTL 自然到期；持久化指纹与当前上下文指纹一致。重新验证后页面恢复 7 项可用，无需代码层状态补丁。
- Excel 验证前后保持同一用户进程，Office/Wind 临时文件与验证子进程均已清理。Windows 原生 Research Web 验证运行 `34570016688` 通过，最新项目约束运行 `34571399909` 通过；不据此宣称 Windows 厂商软件已完成真实安装与登录验证。
