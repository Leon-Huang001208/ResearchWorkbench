# DataHub、研究资料与实际文件

Goldar 快照位于产品数据根的框架子目录，采用严格 V1 schema、内容 revision、2 MiB 上限和同目录原子替换。识别到旧 V0 结构时先保留单份 `snapshot.legacy-v0.json` 再安装确定性 seed；框架快照不进入 Automation 事实索引、会话正文或资产数据集。

Phase 2A 另在 `<RESEARCH_DATA_HOME>/mcp-registry/` 保存非敏感 Registry 索引以及按 Registry
隔离的原子缓存。官方 `/v0.1` 的不透明游标、ETag 与同步时间只随成功结果提交；网络或上游失败
只把最后成功缓存标记为 `stale`，不会用空结果覆盖。缓存目录元数据经过 schema 校验和长度限制，
以 Unicode plain text 保存名称、描述、包/远程元数据，拒绝控制字符和 surrogate，不保存 HTML entity
编码。Bearer/OAuth 秘密不进入这些 JSON、会话、资料快照或日志，而由系统凭据库服务
`ResearchWorkbench.MCPRegistry` 持有。

Phase 2B 在 `<RESEARCH_DATA_HOME>/mcp-runtime/` 保存不可变安装清单、安装状态、启用清单、
工具 schema/风险策略、会话授权快照和人工审批元数据。短期确认令牌绑定完整规范摘要并防重放；
本地包只从已验证 staging 原子发布到独立安装目录，远程目标只保存规范化端点。环境变量值、
OAuth token、清单完整性密钥和 loopback 控制密钥分别由 `ResearchWorkbench.MCPRuntime` 系统凭据
或私有控制文件持有，不进入清单、会话快照、浏览器响应或日志。删除安装前必须停用 Runtime；
健康失败保留安装记录并原子恢复上一份启用清单。
staging、安装 payload、清单与确认令牌重放目录在 Windows 上以目录类型、符号链接和重解析点
作为结构证据，不使用 POSIX mode 投影代替 ACL；POSIX 仍要求 group/other 无权限且目录属于当前用户。

Phase 2C 在同一本地数据根中原子保存 Automation、AutomationRun 和非敏感投递渠道投影。任务记录
锁定目标种类、ID、版本、内容 SHA、输入模板、工作空间、输出格式、允许的 MCP 工具快照、日程与
投递引用；Run 只保存计划时间、触发类型、会话 ID、研究/投递状态、稳定失败码和重试关联。渠道
URL、SMTP 密码与 Webhook 签名秘密由 `ResearchWorkbench.Delivery` 系统凭据库持有，不进入 JSON、
浏览器响应、会话或日志。默认外发仅含状态、摘要和本机会话链接；产物引用须逐任务显式开启。

## 一个数据服务，两种消费者

DataHub 是 FastAPI 进程内的后台“数据总机”，不是用户直接运行的第四种能力，也不是新服务。Web 通过“能力中心 → 数据”浏览 15 项业务数据能力、22 个登记来源及其绑定矩阵；DSH 通过品牌无关的 `datahub_*` 业务 Tool 取数。通用 MySQL 配置与会话文件位于当前设备数据根，密码由系统凭据库隔离；Research Runtime 启动时只注册至少有一个可调用来源的工具。

统一连接中心由 `datahub/connection_center.py` 汇总来源声明、非秘密配置、系统凭据存在性、平台能力、最近探测和 Runtime 适配状态；`datahub/connections.py` 仅原子保存 `<RESEARCH_DATA_HOME>/connections/` 下的非秘密 JSON，秘密通过系统凭据库按来源/账号键隔离。`datahub/probes.py` 执行有界诊断：Wind 沿用本机登录会话，iFinD SDK 探测登录后在 `finally` 登出，Excel 与插件只有实际心跳或工作簿探测才能标记可用。保存配置或检测成功都不自动等价为 Provider 可调用。

旧环境变量迁移先返回只含“是否存在、冲突、目标来源”的预览；执行时要求来源白名单与二次确认，先写入并回读系统凭据库，再原子清理 `.env` 对应项。配置文件、凭据或 `.env` 任一步失败时恢复原始字节、权限和旧凭据；DSH 模型密钥不进入该流程。

会话软删除不改写任何资料或文件，墓碑保留期为 30 天。永久删除必须先由 DSH 确认原生根会话及其级联子会话已删除，随后 Workbench 才删除该产品会话目录中的附件副本、数据集快照、产物、`.control/calls/<session>`、`.control/snapshots/<session>` 和索引记录；若原生确认失败则保留全部文件与墓碑供后台重试。会话内已发布能力快照保持只读封装；清理时仅为产品根目录内的真实目录恢复所有者写权限，不跟随符号链接。文件系统清理失败会保留带 `native_deleted_at` 的墓碑，后续重试不会重复调用 DSH。DSH 内容寻址的全局附件对象可能被多个会话共享，不在单会话删除中误删。

目录读取只访问 `datahub/catalog.py` 的静态声明，不实例化旧 Connector、不联网、不启动 Excel，也不产生供应商费用。目录分别展示代码存在、完成适配、配置齐备、依赖齐备、允许调用和最近健康状态；只有完成 Provider 适配且满足条件的绑定才进入自动路由。东方财富基金和财联社可直接调用；天软 CJPY 已实现证券目录、交易日历、历史行情和实时快照 Provider，但本机缺依赖或授权时保持 `blocked_dependency` / `blocked_config`，其他登记能力不会借来源级状态冒充已实现。

上游仅接受注册来源 ID 和能力限定参数，不接受任意 URL、模块、路径、请求头或凭据。`datahub/broker.py` 先按能力绑定、启用状态和覆盖条件筛选，再选择单一 Provider；显式来源默认不静默换源。访问边界限制域名、重定向、体积、时长及取消；请求失败与空数据不同，返回状态、原因、尝试来源和实际覆盖。原始响应留在私有区域，解析数据以 JSON/CSV 和 Manifest 保存至当前研究可读资源目录。

桥接上限为 22 秒；AKShare 与天软同步 Provider 在 15 秒内返回终态。超时写出 `failed/deadline` 快照而不是顶层活动异常；第三方同步调用若仍在运行，每个 Provider 的单线程门闩让新请求快速返回 `failed/provider_busy`，避免排队和线程累积。Python 不能强制终止已经进入 SDK 的线程，因此该线程仍会运行到供应商调用自行结束。

主任务准备资料后，子 Agent 读取同一组数据集引用。升级 FinGPT → Claw 时复制并验证目标会话资料，保留 origin dataset / manifest hash 与新 ID 映射，避免让新会话访问旧路径。

## Report Workflow 的 Excel 与文件链

具体报告的 Word/PPT 模板、Excel 底稿、映射、校验规则和交付格式属于不可变 Workflow 版本。运行先复制母版到独立 Run 目录，再由 `report_workflows/workbook.py` 串行控制本机 Excel：检查声明的 Wind/iFinD Provider，刷新、完整重算、等待稳定、保存并产生刷新 manifest。插件未登录、公式错误、日期或必填项不合格、异常零值和超时均进入 `blocked_data`；没有显式字段及口径等价映射时不使用 DataHub 或旧缓存替代。

`report_workflows/tooling.py` 只从刷新后的运行副本提取有界内容，并一次性生成 `report-data.json` 共享快照及 SHA-256。Claw 父任务和至少两个真实子 Agent 读取同一快照，不重复刷新。模型只负责生成会话自有的 `report_payload.json`；即使 Claw 提前创建了同名 Office 文件，Report Workflow 也必须经 `report_rendering.py` 与 `report_render_script.py` 做确定性模板组装，再由独立交付检查重开文件、检查 HTML 非空、占位符、数据日期和文件哈希。PPTX 占位符按段落合并 `<a:t>` 文本片段后替换和检查，跨文本片段的残留同样会被拒绝。Payload 可按 `*_blocks` 家族组织，但显式 `missing` 始终优先于解释文字：缺失区块可显示原因，不能因此通过完整交付门禁。Claw 回合结束只进入交付检查，缺 Payload、投影失败、必需区块或约定格式时保持 `delivery_incomplete`。

本机集成的 Wind 真实验证不读取报告 Workflow 母版，而是在独占空白工作簿中执行最小厂商公式；报告刷新由各 Workflow 按自身资源、校验和时限独立判断。iFinD HTTP 探测继续读取 DataHub 的非秘密配置与系统凭据库秘密，按登录、健康、最小只读查询、登出的顺序执行，响应和日志均不包含令牌。

如果 Payload 晚于父回合结束才写入，重试仅在当前会话和当前 Run 的文件边界内查找新建或更新文件，直接恢复确定性组装，不再刷新 Excel 或重启 Claw。旧历史产物、附件和运行前已有文件均不计入本次交付。

## 研究台查询与交接

`workbench.py` 为市场、基金、产业链和资料等研究台入口，以及独立资产观察提供产品 API。页面打开只读取目录、历史查询、资产个人观察与实际产物；用户提交后才创建源会话并调用 DataHub。查询状态与幂等键写入产品索引，最终数据仍以 DataHub manifest 和文件为准。

“交给 FinGPT / Claw”先验证所选 dataset 确实属于来源会话，再新建目标会话，将选定 dataset 逐文件复制并复核 SHA-256，最后把页面筛选、来源、截止时间和 dataset 映射写入 `inputs/page-context/`。页面上下文上限为 64 KiB；查询与交接分别通过幂等键及准入锁防止并发重复创建。交接不重新联网，不创建符号链接，也不让目标会话读取源会话路径。

资产观察通过 `ui/asset-workspace.mjs` 恢复为独立产品入口。概览、历史行情、财务、资金与交易事件、公告、新闻、研究资料、同类比较、主题暴露和来源口径逐块保留真实状态；历史行情有数据时显示 OHLC K 线、MA/BOLL、成交量、成交额、MACD、KDJ、RSI、换手率和细行情栏，技术指标仅在浏览器内由当前 DataHub 快照确定性派生，不写回或伪装为来源字段。DataHub 标准行的 `turnover` 是成交额，`turnover_rate_pct` 是换手率；UI 分别映射并对缺失值保持未知，不在两个口径间回填。自选、观察笔记和提醒仍存放在 Research Web 数据根，不依赖旧 PostgreSQL，也不恢复旧 Agent 委员会、信号、情景或回测链。

## 报告 Workflow 资源与迁移

具体报告不再放入研究台的通用“报告页”。`report_workflows/` 管理每篇报告的不可变版本、资源、运行和日程，`report_workflow_routes.py` 提供产品 API，Claw/DSH 是唯一研究执行引擎。Word/PPT 模板、Excel 底稿、映射、素材和交付规则属于该 Workflow 版本；每次运行复制到独立 Run 目录，不能修改母版。

启动迁移优先读取 `~/.research-workbench/research-web/report-projects/` 中已经管理的原项目；只有该目录无项目时才回退仓库旧目录。迁移对每个文件核验类型、路径和 SHA-256，拒绝链接与越界，支持 dry-run 和幂等重复执行。当前实际目录包含创业板50周报、华安ETF周报、华安ETF投资风向标和 AI 周报；前三者已发布 v1，AI 周报因资源不完整保持 `needs_attention`。历史产物只建立只读索引，不伪装成新 DSH 运行。

Excel 刷新由受控 `workbook_refresh` 逻辑在运行副本上串行执行。Provider、登录态、公式错误、数据日期和必填单元格校验失败时进入 `blocked_data`；只有 Workflow 明确声明等价映射时才允许 DataHub 备用，不能按文件名猜测公式来源或静默切换口径。

详细已实现来源和口径见 [DataHub 模块](../../research-web-datahub.md)。来源截止时间、报告期、抓取时间、请求与实际范围、分页结束和覆盖不足必须分别保留。数据集存在不代表资料完整。

## 文件安全边界

上传支持 PDF、图片、Markdown、CSV、XLSX，单文件 30 MiB，每批最多 20；模型图片内容另有单张 8 MiB / 合计 16 MiB 限制。上传成功不是模型已阅读证明。

文件 ID 和会话归属由索引解析，不接受浏览器传入任意磁盘路径。服务通过不跟随符号链接的目录描述符安全读取；跨会话、路径穿越、链接风险应拒绝。

研究脚本只在当前会话 outputs 写入，在 inputs/resources 读取。使用本机已验证的内核限制及环境白名单，不能因创建/import Skill 获得更多宿主、Shell、网络或依赖安装权限。

HTML 产物使用无同源权限的 sandbox 预览与限制 CSP。下载不执行文件。应用凭据不得暴露给生成页面。

## 独立交付状态

`delivery` 是会话详情中的独立字段；不是 DSH 的运行状态。

| delivery.status | 条件 |
|---|---|
| `pending` | 已受理但父/子任务未结束，或尚无完整确认条件 |
| `admission_unknown` | 受理收据 pending/unknown，等待原生日志关联 |
| `not_required` | 本任务未要求文件 |
| `completed` | 所有要求格式都有本次新增/更新且验证有效的文件 |
| `incomplete` | 有要求格式缺失或文件无效；保留有效部分及缺失原因 |
| `verification_failed` | 沙箱检查失败、文件太多、文件变化、响应无法验证，或明确停止且父子任务已确认空闲但缺少原生终止事件 |

提交前记录 outputs 哈希基线。只检查本任务新建或哈希改变的输出，不把附件、历史文件或聊天文字当作交付。候选解析限单文件 16 MiB、每会话 100 个输出；Office 文件须实际重开且包含内容，XLSX 须有表头和数据行。解析在严格沙箱完成，发布前再次核对文件大小/哈希，防止检查后被替换。

`required_formats`、`missing_formats`、`files`、`reasons` 和 `checked_at` 支撑界面展示。格式检查不能证明数值、引文或研究结论正确；研究质量仍需使用者复核。

停止异常复核直接记录失败原因，不解析文件；只有完整原生结束证据才进入实际文件校验。收据内部的停止意图不暴露给模型或浏览器，错误码与解释可见。详见 [交付实现](../../research-web-delivery.md)。

来源：`delivery.py`、`delivery_validation.py`、`store.py`、`sandbox.py` 和 `datahub/`。既有协议、文件安全、取消、自动工具过滤、数据快照与真实文件验收在本次 UI/能力改动后需要重跑。

产品索引和 Report Workflow 目录的文本元数据固定使用 UTF-8 读取与原子写入；Windows 默认代码页不得改变中文内容。文件归属、目录结构、原子替换和单 worker 边界均保持不变。

DataHub 控制文件、调用收据和会话快照在 POSIX 继续使用目录描述符和 `NOFOLLOW`；Windows 使用规范化路径回退，并拒绝重解析点、非普通文件、硬链接、越界路径、超限内容及打开前后身份变化。Windows 快照继续以同目录临时目录和原子改名发布，目录 `fsync` 明确跳过；此修正不改变会话快照格式。

DSH 认证控制文件在 POSIX 继续要求私有 mode；Windows 不把 POSIX mode bit 当作 ACL 证据，而是校验普通文件、单硬链接、大小、重解析点及打开前后身份。下载采用相同的 Windows 身份核验。永久删除只在产品根内恢复真实目录和普通文件的所有者写权限，不跟随链接或重解析点。

连接配置仍先刷新临时文件、关闭句柄并原子替换。POSIX 随后刷新父目录；Windows 明确跳过不支持的目录 `fsync`，不把跳过记录伪装成持久化成功证据。

三个 Phase 2 功能默认开启只改变服务装配条件，不创建虚假目录记录、安装清单、授权、Automation 或交付渠道；对应事实仍只在用户显式操作成功后原子持久化，环境变量设为 `0` 时保持原数据不变。
