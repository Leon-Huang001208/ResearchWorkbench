# 安全边界与验证方法

## 当前部署的信任模型

这是单人、本机回环部署，不是公网认证或多租户隔离方案。浏览器请求由同源与 Host 检查限制；BFF 确认自己管理的 DSH 实例与会话归属。3080 不是产品执行端，模型凭据只由专属 DSH 管理，研究脚本没有凭据环境变量。

| 边界 | 实际约束 | 核对位置 / 测试 |
|---|---|---|
| Web → FastAPI | 本地 Host、同源、输入 schema；不开放任意代理 URL | `main.py` / `test_api.py` |
| FastAPI → MCP Registry | 官方端点固定 `/v0.1`，私有 Registry 仅显式配置；认证 Registry 只允许 HTTPS，无认证 HTTP 仅限 `127.0.0.1` / `localhost` / `::1`，OAuth 端点始终为 HTTPS，客户端不跟随重定向；同名身份隔离、游标不解释、ETag 与最后成功缓存原子提交 | `mcp_registry/` / `test_mcp_registry.py`、MCP 市场 JS/E2E |
| Registry 凭据 → 系统凭据库 | Bearer/OAuth 秘密只存 Keyring `ResearchWorkbench.MCPRegistry`；索引、缓存、日志和响应不含秘密 | `mcp_registry/credentials.py` / `test_mcp_registry.py` |
| Registry 文本 → 浏览器 | schema 校验与长度限制后保存 Unicode plain text，拒绝 control/surrogate；数据层不做 entity escape，最终 HTML sink 单次转义且不热链图标 | `mcp_registry/models.py`、`ui/mcp-marketplace.mjs` / Python、JS、E2E |
| Registry 版本 → 本地安装 | 只接受固定 npm/PyPI/MCPB 目标；完整依赖与哈希、直接 argv、`--ignore-scripts`、隔离目录、最小环境、安全解包和短期摘要确认；禁止 shell、范围/latest、钩子、隐式环境和链接越界 | `mcp_runtime/package_resolver.py`、`package_planner.py`、`package_installer.py` / `test_mcp_installation.py` |
| Research Web Host → 远程 MCP | 仅 HTTPS 或字面 loopback HTTP；无自动跨源重定向；OAuth 使用 PKCE/state/元数据发现/受众校验，token 只进 `ResearchWorkbench.MCPRuntime` 凭据库且不 passthrough | `mcp_runtime/transport.py`、`oauth.py`、`sdk_host.py` / `test_mcp_transport.py` |
| DSH → MCP Host → Server | DSH 只加载命名空间化声明并经私有 loopback 控制令牌代理；每次调用重核安装版本、schema 哈希、会话快照、风险和一次性审批；参数正文不进日志或审批列表 | `runtime/mcp-adapter.mjs`、`mcp_runtime/authorization.py`、`service.py` / Python 与 JavaScript MCP 回归 |
| 本机诊断 → 宿主 | 发现只读取标准位置/注册项/模块；真实验证须显式触发并限制目标、Office 容器内确定名称的临时文件、独立进程组和超时；Excel 使用本轮独立实例，Wind 在打开工作簿前上报本轮 Excel PID供精确清理；投影排除绝对路径、秘密、命令与环境变量 | `local_integrations/`、`report_workflows/workbook.py` / `test_local_integrations.py`、`test_report_workflows.py` |
| FastAPI → DSH | 固定回环 RPC、共享有界认证控制读取、文件身份/别名检查、方法白名单、双事件通道 | `runtime_auth.py`、`client.py` / `test_runtime_auth.py`、`test_protocol.py`、`test_event_recovery.py` |
| 服务管理 → 私有目录 | 拒绝非目录、符号链接和 Windows 重解析点；POSIX 检查 group/other mode 位，Windows 不将 mode 投影当作 ACL | `service_manager.py` / `test_service_manager.py` |
| 用户 → 会话文件 | 会话归属、规范路径、安全文件描述符、有限上传体积和类型 | `store.py`、`main.py` / `test_store.py`、`test_artifacts.py` |
| DSH → 工具 | 精确注册工具集合，子 Agent 深度、并发和步骤限制 | `runtime/guard.mjs` / `research_web_guard.test.mjs` |
| 会话 → Tabbit 标签页 | 当前 Runtime 生命周期内的会话授权；发送前按所选实例实时重验可 claim 的 HTTP(S) 标签；正文仅进入绑定会话、单次消费、10 分钟过期的 DSH 内存 token | `tabbit.py`、`runtime/tabbit-adapter.mjs` / `test_tabbit.py`、`research_web_tabbit_adapter.test.mjs` |
| DSH → 公开数据 | 原生审批；私有认证 BFF 入口，固定来源/参数，无任意 URL、重定向或自动安装 | `runtime/public-data.mjs`、`datahub/` / `research_web_public_data.test.mjs`、`test_datahub.py` |
| 脚本 → 宿主 | macOS Seatbelt 内核约束，环境变量白名单；只读 inputs/resources，仅 outputs/tmp 可写，无网络和子进程 | `sandbox.py` / `test_sandbox.py` |
| HTML → 浏览器凭据 | 隔离 iframe，后端 sandbox CSP，无同源权限；模型 Markdown 先转义 | `main.py`、`ui/markdown.mjs`、`ui/views.mjs` / UI 安全测试 |
| 研究结束 → 交付完成 | 本任务输出基线、哈希复核、沙箱解析与重开；旧产物、附件和正文不补文件格式 | `delivery.py`、`delivery_validation.py` / `test_delivery.py` |
| 导入包 → 本地存储 | 有界读取，不 extractall、不执行；拒绝穿越、链接、祖先路径冲突、嵌套压缩及伪装可执行；图片/PDF 容器证据检查 | `capabilities/packages.py` / `test_capabilities_safety.py`、`test_capabilities_review.py` |
| 草稿 → 原生发现 | 检查元数据、调用方式、脚本哈希、已安装依赖与精确工具名；活动任务阻止发布/停用/回滚 | `capabilities/catalog.py`、`routes.py` / `test_capabilities.py`、`test_capabilities_admission.py` |
| 原生能力 → 当前研究 | 仅专属 Skill root；所有启用包检查依赖与关联版本，再复制只读资源；失效包不能在自主发现时绕过 | `capabilities/catalog.py`、`runtime/research.cordis.yml` / `test_capabilities_native.py`、`test_capabilities_review.py` |

包管理后端最近完成 233 项完整 research_web 回归与两轮限定修复复审。真实 UI 已完成对话产物创建/审查/发布/新研究调用/HTML 下载，以及手动导入/编辑两版/停用/回滚/导出；Workflow 与全轮交付检查另行记录，不由这些结果推定。媒体容器检查不是恶意内容证明，静态 Python 检查不授予额外宿主访问或网络权限。发布暂存失败保留草稿与旧版；无法确认恢复时维持 pending 并拒绝继续，不悄悄抹去失败。

Tabbit 页面访问授权不持久化到 Research Web 会话文件；拒绝授权会撤销适配器内的本会话 grant。`read_only: true` 只是调用方声明，不能静态证明任意 Playwright 代码无副作用；缺失或为 `false` 的调用必须逐次经过原生审批，系统提示禁止把写操作伪装成只读。claim、DOM 提取或 `finishTask(..., {keep:true})` 任一失败都会阻止消息提交，且标题、URL、正文和执行代码不进入日志。

供应包校验使用 tar 原生 POSIX 路径语义，拒绝反斜杠、链接、绝对路径和 `..`；解包阶段才建立宿主路径。Tabbit 配置异常路径始终关闭仍由调用方持有的描述符，二次清理失败只记安全日志并保留原始异常。

Windows 不使用 POSIX mode bit 证明 DSH 认证文件或 DataHub 私有文件安全；路径回退要求规范化后仍位于产品根内，拒绝链接与重解析点，并验证普通文件、硬链接数、大小和打开前后身份。快照的创建、原子发布与失败清理通过同一受限路径层完成。POSIX 的目录描述符、`NOFOLLOW`、私有 mode 与目录 `fsync` 保持不变。

创建会话从产物导入时只读取当前安全文件清单。已改名旧 ledger 不作附件来源；仍实际存在但不安全的固定伴随路径、读取时消失或创建类型冲突均拒绝。显式 ZIP 不吸收会话中无关 JSON。真实修复后同名包按名称冲突拒绝，未覆盖现有已发布能力。

## 验证层次

1. 协议与渲染测试验证确定性契约，不要求消耗模型。
2. 原生沙箱与 DSH schema converter 测试要求本机环境以及 `DSH_SOURCE_ROOT`；缺失时明确 skipped，不能当作通过。
3. 独立浏览器回归验证实际页面与响应式布局，不写会话或调用模型；截图必须另行人工检查。
4. 真正研究旅程由本机 Web、专属 DSH 和真实模型完成，保留会话、版本、工具事件及文件；单元测试和旧验收不能替代新功能验收。
5. 图文一致性检查只核对路径、接口、字节哈希及更新记录。人工仍需审查语义、权限和实现是否相符。
6. 本机集成“已发现”不能替代真实调用验证；只有创建/刷新、保存、关闭、重开与必需结果校验全部成功才可投影为可调用。超时、权限、登录或厂商异常均关闭失败。

## 当前可复跑命令

```bash
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs
python -m pytest -q tests/research_web/test_mcp_registry.py
node tests/e2e/research_web_mcp_marketplace.mjs
node --check app/research_web/ui/app.mjs
git diff --check
```

UI 布局验收：`node tests/e2e/research_web_layout.mjs`，可用 `RESEARCH_PLAYWRIGHT_MODULE` 指定已经安装的本地 Playwright 模块入口；该脚本不安装依赖、不改变当前浏览器会话、不提交研究。证据输出至 `outputs/research-web-ui-acceptance/`，日志为 `logs/research-web-layout.jsonl`。它不把截图自动标为视觉优良。

## 未覆盖的部署保证

不声称 Windows/Linux 原生研究沙箱、桌面安装、公网访问、多个 FastAPI worker 或多人协作已经验证。停止后如有内核退出异常，仅报告并保留证据，不自动重启系统。真实文件解析检查也不能自动证明财务结论正确或资料覆盖充分。
