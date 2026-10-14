# Claw 全页面调查与复刻

日期：2026-10-14。宿主：macOS；任务：Web 功能开发；本平台验收：macOS Native、适用通用门。Windows/Linux 产品原生验收不在本宿主执行。

基线：`de0fc4e30b47545d33081662be4994bc5cd5a870`，现有隔离 worktree `claw-interaction-redo`。原 PR 与候选保留；本轮未授权合并、部署、清理。状态：进行中，不能据本报告宣称全量调查或真实验收通过。

## 证据边界

- **实际观察**：登录 Chrome 的原日程对话、创建/修改参数、两次试跑报告、日程表；本轮技能页与 IM/连接器设置弹窗。
- **源码确认**：本产品全部 Claw 前端处理链路、Automation Run 定义快照、DSH 准入和数据桥接。
- **未知**：AlphaEngine 服务端实现，尚未获取的请求结构和事件、隐藏及错误状态。
- Chrome 只有原生窗口通道，未出现在标签页连接目录。辅助功能可读，但截图一度全灰，滚动/坐标输入返回无可用窗口。用户恢复窗口后技能页和设置可读；后续输入再次失联。未修改浏览器配置、安装扩展、开放端口或读取 Cookie/凭据。
- 参考证据在 `.codex/acceptance/claw-full-20261014/alpha-*`，既有完整对话证据沿用上一候选 evidence；只读源码调查不证明运行。

## 元素调查账本

| 元素族 | 参考状态 | 本产品链路/接口 | 差距与后续证据 |
| --- | --- | --- | --- |
| 全局模块轨、侧栏展开/收起 | 外观已观察；本轮状态部分调查 | shell / 本地 sidebar 状态、焦点恢复 | 需实测参考展开、键盘、窄屏 |
| 会话/工作区、搜索、新建 | 入口已观察；内部部分调查 | app/core / POST sessions、GET session、项目 GET | 参考搜索与工作区弹窗待调查 |
| 分组、会话更多操作 | 入口已观察 | app / 项目 POST/PATCH、会话 PATCH/DELETE/restore、归属 PUT | 参考菜单和归档状态待调查；不得为取证删除原记录 |
| 首页分类、案例与回放 | 既有首页截图 | claw-workspace / 本地案例填草稿 | 参考回放内部待调查；不伪造本产品回放 |
| 技能·专家 | 本轮目录实际观察 | capability workspace、composer / capabilities | 参考用户分享/官方/我的技能、分类/隐藏已安装/排序；详情与添加确认待调查，不安装 |
| IM | 本轮弹窗实际观察 | 不增加远程 IM | 微信/飞书、扫码绑定、配置引导、已接入 0；不生成或保存绑定 |
| 连接器 | 本轮空态实际观察 | 能力中心 connections/MCP | iFind、IMA 配置入口、已安装 0；配置表单与接口待调查，不保存凭据 |
| 模型、记忆、积分 | 共用设置入口实际观察；内部未知 | settings / 现有模型配置 | 页面切换受原生输入失联影响，不扩展秘密权限 |
| 输入、附件、能力、工具 | 参考入口已观察 | composer / uploads、message、Tabbit scope | 弹出菜单、拖放、禁用状态须补实测 |
| 提问、回答、工具执行卡 | 原日程完整历史实际观察 | views + projection / questions、原生 tool/call/result | 本产品缺主对话工具卡；调用参数被结果覆盖 |
| 创建/修改日程 | 完整原对话实际观察 | drafts / prepare、confirm、dismiss | 保留显式点击批准，与参考自动创建差异明确 |
| Agent 日程 | 既有真实表格证据 | automation / list、run、enable、disable、delete | 周一至周五不照搬参考仅周一/周五摘要；手动运行不可显示未执行 |
| 试跑报告、活动、来源、文件 | 参考 9/6 工具摘要、报告、引用实际观察 | run snapshot + execution detail/files | 本产品报告原为纯文本；活动只在侧栏；执行格式误显示无需文件 |
| 复制、导出 PDF | 参考按钮已观察 | 新增本地回复复制；真实导出机制待确认 | 不能以按钮存在证明 PDF 文件成功 |
| 停止、断线、错误、重试 | 参考未知 | cancel、SSE、错误提示、幂等受理 | 独立测试，不触发参考故障或扩大权限 |

## 接口与实现映射

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"显式格式使用现有文件助手与交付校验，默认调用仍兼容，内联预览沿已有会话文件端点和沙箱，不引入文件复制或另一个生成引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"模式记录初始共享祖先验证与既有后置身份契约对齐，私有父目录和文件验证不变；没有新增生命周期进程、端口或权限。","diagrams":[]} -->

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"复用现有消息、Markdown和活动渲染，在同一详情投影内穿插原生证据与不可变运行快照；没有新页面服务或渲染引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"现有会话详情增加安全证据与执行快照字段，续答沿同一DSH受理；没有新增请求执行循环或进程边界。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"在原生guard已有pre-step边界使用固定DSH会话级工具目录限制，保留执行veto与原私有认证通道，无新runtime或全局授权。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"只读取现有Run不可变定义快照并约束执行续答，Automation仍负责所有调度和Run，不新增定义持久模型。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"原生桥补manifest身份和受限错误码，Provider和Broker校验路径不变，不增加数据源或调用权限。","diagrams":[]} -->

本产品统一前缀 `/api/research`。下列是源码确认，非 AlphaEngine 同名接口：

- 会话：`POST /sessions`；`GET/PATCH/DELETE /sessions/{sid}`；恢复与永久删除独立入口。发送 `POST /sessions/{sid}/messages` 携幂等键，停止 `POST .../cancel`，`GET .../events` 使用真实 snapshot/runtime_error SSE，断线不重发请求。
- 项目：`GET/POST /claw/projects`、`GET/PATCH /claw/projects/{id}`；`PUT /sessions/{sid}/project`；文件引用 `POST /sessions/{receiver}/file-references` 校验来源会话、文件身份和期望哈希，复制后仅加入草稿。
- 对话确认：原生 questions/approvals 各自 POST；日程 drafts confirm/dismiss，确认创建并启用不试跑，启用失败重试不重复建任务。
- 日程：`GET /automations`、`GET /automation-runs`；任务 run/enable/disable 独立 POST，删除独立 DELETE。Run 保存定义快照、版本、trigger 和 execution session，修改后旧 Run 不变。
- 文件与数据：上传 multipart；files/preview/download 受当前会话路由约束；datasets 保存实际查询、来源、日期、字段、缺口和哈希。
- 工具桥：原生目录→guard→会话级准入→DataHub 内部 business-query/cancel。受控 loopback 认证值不记录；公开数据错误需返回稳定安全原因，不透传原始秘密或整个响应。
- AlphaEngine 已观察的是原生工具名 `scheduled_task_list/create/update`、`AskUserQuestion` 及其历史参数/结果；HTTP 方法/路径、流式事件、重试协议尚未捕获，不推断为上述本产品接口。

## 已修复与实现映射

| 源码 | 改动与约束 | 对应测试 |
| --- | --- | --- |
| runtime/guard.mjs、research.cordis.yml、service.py | 固定 DSH 会话级 tools.restrict 收窄目录，保留执行 veto；运行续答绑定不可变快照；原生提问绑定当前任务与版本 | guard、API、automation_research_task |
| runtime/public-data.mjs | quote/quotes、日期契约、安全错误码及 query/provider_query/coverage；注册不等于可调用 | public_data |
| projection.py | 真实序号、参数/结果/错误/耗时分开投影；递归脱敏并按 UTF-8 字节限制 | protocol |
| ui/app、core、views、claw-workspace、composer、styles | 原生回合穿插、真实 Run ID 定位、Markdown 沙箱报告、复制、不可变执行格式、确认回执、草稿受理清除 | claw_redo、UI、capabilities_ui |
| resources/research_helpers.py | write_deliverables 显式 formats，只选 MD 不生成其他格式；默认四格式仍兼容 | artifacts |
| runtime/research-tools.mjs | research_task 输入一致性预检；仅真实 PermissionError 增加已知相对路径恢复提示，不改权限或 stderr | automation_draft_tool、method_tool |
| automation/drafts.py、automation/service.py | 历史确认快照；启用重试在同一定义锁内 CAS，旧确认不得启用新版本；缺回执 409 | automation_research_task、drafts、service、routes |
| runtime_mode.py | 共享祖先身份校验容忍合法兄弟目录变化；私有父目录、文件、FD、链接与归属检查保留 | runtime_mode、docker_runtime |
| test_delivery.py、test_docker_runtime.py | 夹具使用正式 DSH 会话契约；健康轮询计时隔离，避免全局 time.sleep 捕获无关等待 | delivery、docker_runtime |

## 真实候选验收

候选 Web/DSH 为 18190/13190，固定 DSH 为 48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0。正式服务未改动。证据根为本 worktree 的 `.codex/acceptance/claw-full-20261014/`。

- 普通研究会话 `dfd59944-ce1e-4065-ab6d-fe911823d2fe`：实际原生澄清、公开文档比较表与来源、修改续答；原生完成序号 67/82。修改文件 pandas-polars-review-v2.md 为 22779 字节，SHA-256 b5ef519ebd8493a2a7e2dbbe02b226c3c689c8b95904a2bc310c751af89fdcfd。首次助手默认生成额外格式及 Path 序列化失败保留，不能称首次流畅通过。
- MD-only 会话 `f353ce8c-6278-4567-9c68-a6243bbb2485`：真实 turn/end 序号 41、reason completed；delivery completed、required_formats=[md]、只有一个 MD 文件，2469 字节，SHA-256 209f500ec85c0ad1b27c0970e066fe2e39dca049cb5091efe311068a333a3e32。验收提示错误使用不存在的 build_report_package，造成一次失败；模型查询后改用真实 write_deliverables 成功，错误未掩盖。
- 新验收任务 `automation-cf9a3168709567b328eedaac76e0105956b4917026f91c8683d05bd7ae256ba9`：名称“每日收盘点评·全页面验收”，创建并启用后运行数为 0；修改保持同 ID，从 v1 到 v2，名称、模型、时间、权限、格式与下次时间均不变。原有“每日收盘点评”任务未修改。
- v1 手动 Run `automation-run-51f1cbba165645e9b3a0030690a00ff1`，执行会话 `255e6980-86be-487d-a213-82cd73386fd3`：真实完成事件序号 51；5 项活动，其中 1 项目录探测失败、后续恢复；MD 12555 字节，SHA-256 a8629afccf43c10a12f626129f5c8990aa291c26e9fa601346b0299e271aa200。
- v2 手动 Run `automation-run-fecf1e903b45438f9059653b9bb56517`，执行会话 `e74f7bca-0aec-460b-b9b2-20da9172a9d4`：真实完成事件序号 70；8 项活动，其中 3 项重复目录探测失败、最终恢复；MD 18000 字节，SHA-256 a1edfb30c697f318d97808b74d08a91ad225e3d3534ae3d4906ddbfbb707c3c2。
- 两次运行均未调用未批准 Skill、子 Agent 或 datahub。两张 Run 卡刷新后保留 v1/v2，按实际工具结果定位；完整 MD 预览为独立执行会话来源、空 sandbox iframe；执行会话明确显示 MD 和批准范围。
- “增加”首次仍为普通文字澄清，后续原生提问通过；“需要”第二次试跑前仍需要额外人工提示才形成原生问题。已补提示并保留实际引导；不能宣称自然简短续答无引导全程通过。
- 研究内容 **LIMITED**：搜索只取得标题/摘要，未逐页核验；T-1 报告把 2026-10-10（周六）写成前一交易日，日期口径验收不通过。指数点位、全市场资金及专业行情缺口独立保留，运行与文件完成不等于收盘研究合格。
- 桌面侧栏收起后 Enter 展开；1050px drawer Escape 关闭；390px 移动关闭后焦点返回，documentWidth=viewport=390，无横向溢出。深色执行定义/工具状态实测并恢复原主题。响应截图与 responsive-proof.json 已保存。首页草稿跳过存储的缺陷已修复，真实即时刷新恢复“草稿保留验收：尚未发送”；授权、能力等不随草稿恢复。
- 两次试跑后仅停用本轮新增验收任务，避免后续定时模型调用；记录、定义与文件保留，原有任务仍启用且未改动。

## 全量调查缺口

参考已捕获 99 个技能/设置控件，保存角色、标签、来源行与状态，**不是全页面调查完成**。本产品候选 OpenAPI 目录包含 80 路径、95 方法及请求/响应 schema 引用，仅证明本产品接口，不能冒充 AlphaEngine 接口。

AlphaEngine 公开 HTML 实际取得，业务脚本 chunk-common/index 返回 403；匿名 vendor 包取得并做 REA，语义阶段耗尽堆预算，结果为 partial，未发现业务模块。Chrome 仍未出现在支持的标签页连接目录；原生窗口输入失联。内置浏览器与 Chrome 登录态不共享且 AlphaEngine 单处登录，保留 Chrome，不要求内置登录、不复制 Cookie、不调整调试端口。隐藏弹窗、请求、流式事件及新普通研究完整流程仍 **BLOCKED**，恢复条件是现有登录 Chrome 的受支持标签页观察连接可用。

## 验证状态与交付边界

最终 Router 为 L4，全变更集规划。485 项 JS 全部通过，无跳过；文档治理 89 份当前文档/610 文件、Python 索引与完整性检查通过。Python API/协议/日程/产物/交付/模式/生命周期/本机集成共 836 PASS、1 Windows 原生专属 SKIP，耗时 762.29 秒；冻结后版本原子保护与模式/平台增量 203 PASS，耗时 3.16 秒。旧全 Python 3361 PASS/10 SKIP/2 FAIL，两个失败分别由 delivery 夹具和共享目录身份校验闭合，保留原记录。最新 Docker 375 PASS/1 FAIL 为全局计时器捕获 Native/SQLite 等待；隔离后完整 Docker 模块 358 PASS，耗时 210.66 秒，不删除原失败记录。

实际最终命令（证据文件保留完整输出，后续新增修复以聚焦增量闭合，不将旧全套重新标为无失败）：

```sh
DSH_SOURCE_ROOT=/Users/leon/.research-workbench/acceptance/claw-redo-20261013/runtime/dsh/48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0 node --test tests/javascript/research_web*.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs tests/javascript/docker_runtime_contract.test.mjs
PYTHONPATH=/tmp/rwb-claw-redo-tests-20261013/lib/python3.12/site-packages .venv/bin/python -m pytest tests/research_web/test_api.py tests/research_web/test_protocol.py tests/research_web/test_automation_research_task.py tests/research_web/test_artifacts.py tests/research_web/test_delivery.py tests/research_web/test_runtime_mode.py tests/research_web/test_service_manager.py tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q
PYTHONPATH=/tmp/rwb-claw-redo-tests-20261013/lib/python3.12/site-packages .venv/bin/python -m pytest tests/research_web/test_runtime_mode.py tests/research_web/test_platform_capabilities.py tests/research_web/test_automation_research_task.py tests/research_web/test_automation_drafts.py tests/research_web/test_automation_service.py tests/research_web/test_automation_routes.py --confcutdir=tests/research_web -q
```

Ruff、Black、isort 核对全部变更 Python 文件；mypy 核对 5 个研究源码文件及 runtime_mode。后者使用证据目录内配置，仅关闭 stdlib stub 的 follow_imports_for_stubs，保持标准库类型分析与原产品配置不变，避免已有 dataclass stub 错报；不能称全仓库 mypy 通过。

启用版本漏洞由独立评审真实复现，3 RED→GREEN，4 个相关模块 83 PASS；线程竞争、旧版本及缺回执拒绝、正常重试、停用后重放与删除后重放保留。其余独立 Python、JS、安全边界评审无重要缺陷。

本轮尚未发布新候选、执行新 SHA CI、合并、正式部署或清理。旧 PR103 与旧 SHA CI 保留，不能用于证明本轮新源通过。macOS/通用新 CI 待独立发布授权；Windows/Linux 产品 dispatch 仍交对应设备。整体调查状态保持 BLOCKED，局部修复与文件验收逐项记录，不登记“全部完成”。
