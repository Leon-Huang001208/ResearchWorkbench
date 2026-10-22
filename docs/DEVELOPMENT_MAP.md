# Research Workbench Development Map

资产v5部署大索引修复只在 `model_provider_upgrade.verify_primary` 的v5分支复用既有64 MiB业务读取器；原元数据1 MB上限和旧profile不变。回归位于 `test_model_provider_upgrade.py`，覆盖大索引绑定及五种旧profile无变化；原完整事务、恢复和安全读取矩阵继续执行。无新节点、API、格式或依赖，现有图准确，部署合同见[网关升级](research-web-gateway-upgrade.md)。

2026-10-22资产交互v5部署定位在`resident/model_provider_upgrade.py`的ASSET_V5_MODE／PREVIOUS／PAYLOAD、原ASSET_MODES、previous_for、review_assets和CLI分派；近处回归为`test_model_provider_upgrade.py`。固定旧51f09、产品PR185真实merge9bc4，禁止运行时任意版本；原controller／evidence、恢复、保全、产品源码、依赖及CI配置不改。无新架构节点或数据流，原图仍准确；完整验证及未部署状态见[任务报告](../.ai/reports/test_report_asset_interaction_v5_deploy_20261022.md)和[部署合同](research-web-gateway-upgrade.md#资产交互与数据-v5-2026-10-22)。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

市场部署的 read_business_index 复用原64MiB业务上限；retention、idle及市场profile的verify_primary统一使用该读取器，gateway_upgrade.py仅增加默认仍为原元数据读取器的显式参数。市场profile单独固定该模块SHA-256，旧profiles不接受新增例外；大索引及网关额外字节/模式/删除拒绝由同一操作员测试覆盖。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 资产交互与数据定位：`asset_directory.py`负责账号目录索引、代码／名称／GB2312简拼排序、24小时缓存、授权指纹与有界原子文件；DataHub `directory_fingerprint/asset_directory`负责显式天软授权和同namespace凭据读取前后的复核，`providers_cjpy.fetch_directory`沿原SDK容量分批取得完整目录。`asset_routes.py`新增搜索与区块load端点，`asset_workspace.py`负责旧观察缺块补建、15分钟缓存、成功受理签名、来源／区间409、统一区块锁、失败原位回滚和旧快照保留；活动目录／区块任务进入原resident活动投影及关闭边界。

`datahub/providers_cjpy_assets.py`保存固定表／字段／因子合同；`providers_cjpy.py`继续拥有真实SDK Future、容量与关闭，Broker按dataset选择实际支持的来源。AKShare标准字段与原中文列并存，不派生流出或资金构成。前端 `asset-search.mjs`提供单A股搜索与账号／代次取消，`asset-controller.mjs`按专题激活和初次overview→recent qfq加载，`asset-workspace.mjs/css`保留图表／指标并局部替换专题；`asset-projection.mjs`按真实估值、报告期、股东和行业字段投影，独立新闻／公告控制器保留60秒缓存。新回归为 `test_asset_directory.py`、`test_asset_loading.py`、`test_cjpy_asset_data.py`、`test_asset_provider_normalization.py`及资产搜索／专题JS和E2E；原资产、历史、Provider、安装门均保留。合同见[UI](research-web-ui.md#资产观察工作台)、[DataHub](research-web-datahub.md#资产目录与结构化区块)、架构03／04／05章；源码与本机夹具通过不代替同候选CI、真实浏览器或部署。

2026-10-22 v4 profile在`resident/model_provider_upgrade.py`的ASSET_V4_MODE/PREVIOUS/PAYLOAD、封闭previous_for/review_assets和CLI分派中维护，近处回归为test_model_provider_upgrade.py；操作员/测试由独立实现者负责。旧5495固定，产品固定PR180真实merge `9b436613aad9136f4959c992c89dd72fc7354ed5`；654fa6只保留在历史候选证据中。旧v1/v2/v3/controller/evidence/保全门及依赖/CI不变，既有图准确，不改HTML/PNG。产品三CI不替代v4最终本机/评审/CI/部署证据，见[部署合同](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

华安ETF周报新合同由`report_workflows/weekly_data.py`、`weekly_sources.py`和`weekly_workbooks.py`
负责封闭来源、期间复算及运行副本，`datahub/providers_wind_api.py`提供惰性SDK适配；`evidence.py`、
`owner.py`和`weekly_quality.py`接既有研究质量、主管理员与同版本定稿。`ui/weekly-production.mjs`只投影
四类状态和显式版本操作。近处测试为`test_report_weekly_*.py`、`test_datahub_wind_api.py`及
`research_web_weekly_production.test.mjs`，仍须全量Router选择的闭包。合同见[周报生产](research-web-etf-weekly-production.md)；
SDK可导入、离线合成通过与真实连续运行分别取证。

2026-10-22 启动保全修复位于`app/research_web/store.py`：记录磁盘原有的三项可选资产键，save时只省略“原来缺失且仍精确默认”的键，成功原子替换后更新持久键集合；失败沿原日志/异常处理，不误记已持久化。相关回归在`tests/research_web/test_store.py`，覆盖旧索引启动/重复save、首次修改、原有空值及写失败。Automation仍可按原合同save，修复不绕过调用方、不修改保全比对、控制器、依赖或安装流程。存储真源见[文件合同](architecture/research-web/03-data-files.md#资产历史与图表偏好存储)；部署恢复、本机结果和同候选Mac安装CI由主任务分别取证。

2026-10-22 Wind工作区部署工具独立于PR177产品：`resident/model_provider_upgrade.py`新增ASSET_V3_MODE/PREVIOUS/PAYLOAD、previous_for/review_assets及CLI封闭分支，固定旧5495与产品a0ff3ae2，`test_model_provider_upgrade.py`覆盖精确范围、拒绝额外变化、索引保全及v1/v2/v3恢复。controller/evidence、产品、依赖和workflow字节不变；原v4部署拓扑不变，无需改现有图或生成HTML/PNG。真源见[部署合同](research-web-gateway-upgrade.md#资产观察固定版本联合部署)，v3候选CI、真实切换/认证页面与保全另取证，产品通过不能复用成profile通过。

最后核对：2026-10-22。Wind工作区：`asset_history.py` 负责日线规范化/重叠校验/固定锚点复权；`asset_history_jobs.py` 负责持久任务/分块缓存/显式重试/取消排空/规范快照CAS发布；`asset_routes.py` 声明6个历史任务与账号偏好API；`asset_workspace.py`、`store.py`、`service.py` 负责观察投影、旧索引缺省、任务清理和服务关闭。DataHub `adjustment_contract.py`、`contracts.py`、`catalog.py`、`providers_cjpy.py`、`broker.py`、`__init__.py`、`snapshots.py` 负责封闭三种复权查询、真实Future占用、metadata和自包含交接；`main.py`与`resident/model_provider_upgrade.py`合并任务/真实Future空闲证明。UI仍在`app.mjs`、`core.mjs`及`asset-controller/chart/workspace`模块，动态副图偏好、历史任务轮询及日线前缀筹码互相独立。权威文档为[UI](research-web-ui.md#资产观察工作台)、[DataHub](research-web-datahub.md#资产历史任务与固定复权)、架构03/04章和[批准计划](plans/2026-10-22-wind-asset-workspace.md)。定点回归新增`test_asset_history.py`，扩展原DataHub/catalog/CJPY/broker模块，保留原资产/Provider/空闲/JS/E2E测试；真实厂商、几何浏览器与同候选Mac安装CI分别取证，不能用预检替代最终验收。

全市场概览由 `market_service.py` 管无会话缓存、合并刷新、取消和关闭，`market_routes.py` 管固定 HTTP 参数；`datahub/providers_market.py` 管沪深北分页、来源字段与完整性。前端 `ui/market.mjs`／`market.css` 负责三页签和可见页刷新。定点回归为 `test_market_provider.py`、`test_market_service.py` 和 `research_web_market*.test.mjs`；数据流见[市场概览](../outputs/research-web-architecture/13-market-overview.html)。

真实源及正式登录验收入口为 `tests/e2e/market_authenticated.py` 与 `research_web_market_authenticated.mjs`：临时私有根、合成测试账号、正式网关与候选用户实例，不注入cookie或替换Provider。连接路径、官网范围及未来上市排除由provider回归固定；独立源调查在[任务报告](../.ai/reports/2026-10-22-market-data-sources.md)中分开记录可达、覆盖与授权状态。

`resident/model_provider_upgrade.py` 的 `ASSET_V2_MODE/ASSET_V2_PREVIOUS/ASSET_V2_PAYLOAD` 与 `previous_for/review_assets` 增加封闭 v2 身份：`apply-assets-v2` 固定旧版 `9bc12355` 与 PR175 产品 `93d62be6`；v1 和模型常量保持。两资产 mode 共享原索引冻结、空闲、状态校验及 v4 恢复，动态读取所选固定常量而不接受运行时任意版本。近处 `test_model_provider_upgrade.py` 覆盖真实 Git 范围、完整恢复与错误 previous 拒绝；执行合同见[部署说明](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。无新服务、HTTP 字段、数据迁移或依赖。

资产摘要重排由 `ui/asset-workspace.mjs/css` 形成紧凑页头、交易／估值分组、嵌套查询和图后默认收起的来源表；`asset-projection.mjs` 输出仅用于前端的 `valuation`／`coverageRows`，保留真实零值、来源、已载入行和缺口，Wind 未核验股本不派生市值。`app.mjs` 在同资产重绘中恢复原生 details，跨证券／类型重置。`asset-chart.mjs/css` 从主题变量同步透明画布、文字、网格与 tooltip，原比例、公式和联动保持；资金图沿原 Chart.js 实例读取主题。相关纯投影回归为 `tests/javascript/research_web_asset_projection.test.mjs`，页面、主题与联动沿 `research_web_asset_workspace.test.mjs`／`research_web_asset_chart.test.mjs` 及资产 E2E 分别验证。本轮不改 HTTP、观察存储、Provider 或安装依赖，浏览器／厂商读回／同候选 Mac CI／常驻部署仍须各自真实证据。

`resident/evidence.py:GitHubEvidence.qualify` 仅对CI日志下载传120秒时限，普通命令仍30秒；`model_provider_upgrade.py:ASSET_EVIDENCE_SHA256` 将读取器绑定为受审工具内容。邻近 `test_resident.py` 与 `test_model_provider_upgrade.py` 覆盖超时、实际树不符及文件内容/模式/缺失拒绝。

资产观察显式部署仍在 `resident/model_provider_upgrade.py`：`ASSET_MODE/previous_for/review_assets` 绑定固定旧版与已审产品，`asset_queries_idle` 补齐异步行情任务空闲证明。近处 `test_model_provider_upgrade.py` 以真实临时Git、真实操作方法与固定旧控制器夹具覆盖原始/资产两种profile的准入及恢复；没有第二部署执行器或自动白名单扩展。

联合升级中的 `repository_identity/verify_release_repository` 分别验证主实例和网关的既有 GitHub origin、common directory 与 inode；独立 clone、来源变更及目录替换由 `test_model_provider_upgrade.py` 的真实临时 Git 仓库回归覆盖。

`resident/model_provider_upgrade.py:review` 对 PR168 五个导航文件使用独立固定 Git 身份，其余产品保持原模型基线；近处测试 `test_navigation_payload_is_exact_and_does_not_expand_backend_scope` 覆盖接受精确导航、拒绝未知 UI/后端/依赖/模式及非祖先。修改该范围须正式交付，不修改现场自动白名单。

业务模块导航重分组由 `ui/core.mjs` 规范化新旧 Hash 路由、`ui/shell.mjs` 组织主导航、`ui/workbench.mjs` 复用资产双视图/主题检索/ETF 模拟、`ui/intel.mjs` 增加主题检索栏目、`ui/app.mjs` 绑定页面归属与查询/交接异步结果。规范入口为 `#/assets`、`#/assets/funds`、`#/intel/search?kind=news|research|announcements`、`#/simulation/etf`；旧 `workbench` 地址保留映射，历史 section/API/持久化/DSH 均不变。近处回归为 `research_web_workbench.test.mjs`、`research_web_intel.test.mjs` 与 `tests/e2e/research_web_business_navigation.mjs`；行为归属见[UI 合同](research-web-ui.md#业务模块与导航-2026-10-21)。

资产观察的原 AF 五图终端与实例生命周期位于 `ui/asset-chart.mjs/css`，纯计算在 `asset-indicators.mjs`，真实字段／空态投影在 `asset-projection.mjs`，连续页面在 `asset-workspace.mjs/css`；观察控制、兼容导航、证券资讯和外层生命周期继续由 `asset-controller.mjs`、`asset-navigation.mjs`、`asset-news.mjs` 与 `app.mjs` 负责。保留 `renderMarketTerminal(rows,state,metadata)`、`enrichMarketBars`、`createAssetChartController` 导出；controller 提供 configure／getState／mount／dispose／cancel／handle，内部更新图表与读数。后端 `asset_routes.py` / `asset_workspace.py` 新增 section_sources／section_ranges 和 valuation，仍由 Broker 取数、原 Store 恢复并保存会话快照。相关回归为 `test_asset_workspace.py`、`test_datahub_wind.py`、`research_web_asset_chart.test.mjs`、`research_web_asset_workspace.test.mjs`、原 workbench/intel 测试及 `tests/e2e/research_web_asset_workspace.mjs`。公式黄金值、分区范围、真实厂商和离线安装分别验收；页面／数据／刷新合同见 UI、DataHub 和架构03–05章。

`research_workbench_entrypoint/resident/model_provider_upgrade.py` 是模型服务商专项联合部署入口，复用 supervisor/admission 锁、BirthFence、服务管理器、保全摘要和独立恢复包；测试为 `test_model_provider_upgrade.py`，合同见 `research-web-gateway-upgrade.md`。不改变自动部署白名单或 DSH 协议。

恢复环境回归使用真实Git LFS post-checkout钩子、受限launchd PATH和冻结恢复包，在临时Git仓库重现失败并验证恢复；部署前工具缺失须先失败，优雅排空预算为90秒。

网关升级器 `resident/gateway_upgrade.py` 的 `--preserve-primary` 走 v3 静态事务；相邻 `test_gateway_upgrade.py` 与冻结恢复 runner 覆盖受限差异、双资格、空闲排空和离线六阶段回滚。旧菜单适配继续由 `ui/server/account-menu.mjs` 维护，隔离浏览器使用真实旧版模块验证身份入口。

账号UI位于 `ui/server/account-menu.mjs`、`account-workspace.mjs` 与共用 `account-api.mjs`：身份顶部进资料、admin设置管理、保留DOM表单与旧primary适配。`accounts.mjs`只负责登录及旧/account跳转；相邻account_workspace/menu/session/settings JS测试与隔离浏览器证据分别验证行为。

网关`apply-ui`与version 2恢复合同在`gateway_upgrade.py`；`test_gateway_upgrade.py`及两个冻结恢复fixture覆盖新旧helper、工具/产品隔离、资格失败和六阶段恢复。操作合同见[网关升级](research-web-gateway-upgrade.md)。

供应商参数根object回归位于test_sandbox.py::test_native_tool_schemas_match_pinned_dsh_converter：固定DSH转换、真实pi-ai序列化及fake fetch一并验证；research-tools.mjs保留执行时code/report_plan互斥和全部预算。

自由分析绑定位于resources/research_report_plan.py（fact/formula模板、中文长度、审计core）与research_evidence.py（Host重建及真实产物核对）；resources/research_report.py生成去重中文表、独立审计附件和确定性PDF；research_quality_service.py冻结新轮次policy。test_bound_analysis.py回放真实两篇公报及错误平减指数，覆盖完整绑定、绕过拒绝、附件损坏与恢复；UI报告正文用presentation，原笔记保留底稿。

Claw 统一添加/斜杠菜单定位 `ui/composer-menu.mjs`（目录行、键盘与格式纯函数）、`composer.mjs`（渲染）及 `app.mjs`（原控制器接线）；回归 `tests/javascript/research_web_composer_menu.test.mjs`。FinGPT 保持原布局，无后端/依赖/DSH协议变更。

系统报告流程：resources/research_report_calculations.py 只接收原始观测引用/操作/展示位数，SDK 与 research_evidence.py 的 Host 输入重建分别执行；research_report_plan.py 串起派生选择、claims/notes/coverage、暂存与归档。report.py 从冻结要求确定格式并以已评分声明生成真实HTML/Word表。test_report_calculations/formats/system_flow 覆盖成功、拒绝、写入回滚及原 macOS 沙箱；service/source/tool 保持统一 plan 指导。

网关退休与大保全摘要合同定位 `gateway_upgrade.py:wait_retired/read_upgrade_journal/journal_preflight`；近处回归覆盖真实延迟reap、正式recover、不可变artifact读取及读取替换/短读/边界。Mac安装CI在原step跑临时夹具，业务数据与全局reader不改。

Mac网关Python映像定位在 `resident/gateway_upgrade.py:native_image`，由原网关回归和Mac Bootstrap原生只读探针验证；配置venv、内核映像、完整argv与listener是共同条件，不能按进程名或路径子串放宽。

`resident/gateway_fence.py` 与 `gateway_upgrade.py` 是显式 Mac 空池网关更新器；`multiuser/resident.py` 绑定持久冻结路径，`gateway.py` 在认证及实例创建前阻断全请求。近处回归为 `test_gateway_upgrade.py`、`test_multiuser_resident.py`；合同见 `research-web-gateway-upgrade.md`。不得以改 baseline 或清理未知 owner 解锁部署。

网页日期在 research_web_sources 的出版 meta/header 合并；数值闭合布局在 research_web_numeric，quality_service 刷新同一 SDK 快照并独立重读字节。test_fingpt_evidence_contract 覆盖错期、否定、冲突、20上传加网页及声明篡改；UI/fusion 与 report_delivery_links 覆盖误拼 URL 和当前/历史投影。

service.py 按当前合法业务观测选择一致的报告提示；runtime/research-tools.mjs 在既有一次补查内提示同一 report_plan 路径。test_fingpt_dsh_fusion.py 覆盖真实 CPI 上传后的提示及一般研究兼容；test_report_revision.py 固定真实 FOMC 错字段/错误基点负例，quality_tool JS 覆盖补查不续授权。

FinGPT 显式算式审计位于 research_arithmetic.py，接入 research_quality.py；报告链接投影位于 research_quality_service.report_delivery，detail 与 check_quality 共享。近处回归 test_research_arithmetic.py、test_report_delivery_links.py 和 research_web_ui.test.mjs 覆盖真实GDP错算、别名偏离、直接API绕过、附件保留及归档损坏。

sandbox._report_sdk_scope 精确列出当前包的四个只读 SDK/字体文件，并在 bootstrap 注入 session root；resources/research_report.render_pdf 保持原输出定位。test_sandbox 覆盖只读、未列文件和链接拒绝，test_report_revision 的 new/legacy-session 两参数覆盖原资源不改的生成及修订。

research_web_sources.upload_evidence_files 依据 _stored_records 的会话登记分类 Host 网页，service.detail 和 quality_service 的来源上下文/观测/评分均复用；fusion_api 端到端及 source_reading 跨会话/损坏登记回归防止来源别名丢失 scope/日期。正文与原文件不迁移。

本轮数据配方位于 resources/research_report_plan.py，经 runtime/research-tools.mjs 原 script 工具执行；service/quality_service 提供冻结绑定及有界实际观测索引。test_report_revision 覆盖旧 CPI 声明、NIST 真父来源、独立算术及双重恢复失败。research_quality.py 仅调整已核验原句与期间的删除顺序，判据保持。

fingpt_compare.py/worker.py/node.mjs/html属于有限的隔离验收控制面：一次预约、受管凭据seam、48工具/6检索/900秒、逐组原始产物审计。测试test_fingpt_comparison.py及research_web_fingpt_comparison.test.mjs；不接入生产入口。iteration_resources只对有原回收证明、匹配tracked源码的真实pyc或空目录补登记新身份，保存旧新绑定及已验证manifest，未知内容阻止删除。

公开正文入口为 research_web_sources.py、datahub/routes.py 的私有 research-source/list/read/cancel 与 runtime/research-tools.mjs；Markdown 检索身份解析在 research_evidence.py，真实输入字节观测和逐版本回执在 research_quality_service.py。定点回归 test_research_source_reading.py、test_research_report_binding.py 及 research_web_quality_tool.test.mjs 覆盖来源、取消、沙箱修订和旧版质量错绑；完整合同见 02–05 章。

脚本故障回归：report_revision覆盖重复父来源、观测ID误用、完整斜杠来源与原子Summary写入；select_business_evidence将选择与映射合并且拒绝歧义。business_evidence覆盖CPI真实月列/百分点及完整肯定同比段落，NIST原文走原source_quote；service按冻结要求限定治理提示。research_quality.py规则未改。

Git安全备份：`scripts/git_safety.mjs`保持原Git交付、完整恢复及v1读取边界，`scripts/git_backup_store.mjs`提供独立v2共享pack/文件载荷、元数据seal、备份锁及原子迁移。普通恢复点按7天和最新2个有效点轮转，未归并/未提交/活动/隔离及独有锚点保留；不维护活动Git对象。恢复、复用、损坏拒绝、迁移中断与轮转回归位于`tests/javascript/git_safety.test.mjs`，仍由原Project Constraints步骤执行。入口与保留合同见[Agent任务指南](AGENT_WORKFLOW.md#去重备份迁移与自动轮转2026-10-19)。

报告恢复：quality_service在冻结要求时由实际允许上传字节生成resources/research_evidence.json，SDK load_business_evidence按task/contract读取；它不参与Host评分。source_references核对规范ID、准确Host标题及明确定位；Decimal算术和claim操作数保持精确JSON字符串。近处原两个测试模块覆盖伪造副本仍拒绝。

research_business_evidence.py是原Host观测路径内的受限业务摘录规范化与复算；quality_service读取实际输入/重验SHA与缓存身份，research_evidence校验所有父来源，resources/research_report.py只序列化实际返回观测。近处test_research_business_evidence.py覆盖肯定句、表头结构、精确解析、真Store链与隔离负例；质量算法仍在原research_quality.py，不以规范句自动认证中文推断。

实际业务报告的来源解析、claim算术预检查、同节笔记/coverage、对账和利率单位工具仍在 resources/research_report.py；numeric_summary只修独立验收器的展示舍入及尾部空列误报，不参与Host判定。test_report_revision.py覆盖原四用户故障类别与伪造观测仍被Host拒绝；service.py只引导唯一DSH循环使用这些工具。

报告二次写入由 resources/research_report.py 在原输出能力内创建排他临时目录并归档；research_evidence.py 从 Store 的规范 outputs/research-report.json 映射核验当前报告。test_report_revision.py 覆盖真实 macOS 沙箱二次写入、getcwd 拒绝、同名备份及非规范/重复身份拒绝。

多用户常驻入口在 app/research_web/multiuser/resident.py；resident_binding 保留 primary 原实例，preservation 生成内容摘要，resident_boot 只恢复已证明跨 boot 的控制元数据。测试 test_multiuser_resident.py 沿现有 Python 合同检查。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](research-web-ai-news.md)。

AI资讯采用固定原版AIHOT API与worker、独立PostgreSQL和Host私有桥；默认关闭采集、推理和付费源，从自主库重新起刊。隔离验收不导入线上历史，不更新常驻内容；DSH继续是唯一研究执行引擎，Hot宏观及研究证据保留，重叠AI信源在未来真实闭环验收后的显式切换事务中交接。详见[自主资讯合同](research-web-ai-news.md)。

私网邀请制入口为 `research_workbench_entrypoint/server.py` → `app/research_web/multiuser/__main__.py`；accounts 管 SQLite 账号/登录态，gateway 管固定 origin、鉴权及逐用户代理，runtime 管独立 Web/DSH pair 和两实例上限。`tenant_policy.py` 在后端执行入口拒绝宿主能力；`ui/server/` 管登录、账号和页面身份，浏览器草稿/导航偏好按账号 UUID 命名空间恢复。近处测试为 `test_multiuser_accounts/gateway/runtime/cli.py`、`research_web_multiuser_storage/policy.test.mjs`。安装、安全/API和部署图映射至架构清单的 private-multiuser 组；不改变原单用户数据或依赖锁。

Git基线恢复由git_safety.mjs的remote_moved原位prepare认证，保留原PR/工作树和旧回执，重置CI/验证并推进已发布tip绑定。近处git_safety.test.mjs覆盖所有权、祖先、并发变化、重复准备、发布后回退及锁保护；共享框架不修改。
已发布PR等待/失败状态也通过同一原位prepare恢复真实前进的主线，保留修补计数；新回归覆盖计数耗尽、主线未变、脏目录与外来PR head，不修改全局控制器或发布配额。

AI资讯：aihot_routes.py管理v1兼容和完整site报刊/热点合同、LRU/ETag/限流；aihot_media.py
只读取上游已签发图片。ui/aihot.mjs负责代次/取消/归档状态，aihot-report/hot/common.mjs
负责原页面完整阅读结构、趋势几何与安全渲染。aihot_content.py将上游HTML转为惰性阅读树；aihot-reading.mjs渲染文章、事件和主题。
独立路由#/aihot/{daily,weekly,monthly,archive,hot}及item/{id}、story/{uuid}、topic/{slug}。
近处测试test_aihot.py和research_web_aihot.test.mjs覆盖完整字段、图片边界及交互竞态。

FinGPT 单引擎融合由 research_quality.py 完成确定性验收，research_quality_service.py 绑定既有任务回执、附件/快照和一次补查，resources/research_report.py 保存报告版本。原生质量工具仍走 runtime/research-tools.mjs 私有桥。近处测试为 test_research_quality.py、test_fingpt_dsh_fusion.py、research_web_fingpt_dsh_fusion.test.mjs。未独立验证的陈述保持缺口，不能以模型自评认证。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

Codex式导航为ui/conversation-navigation.mjs/css，逐题问答为ui/questionnaire.mjs/css；app/core/shell/views只做既有协议接线。Host navigation.py与claw_projects/claw_routes管理模式隔离的导航revision/项目，旧Claw API兼容；近处回归为test_navigation.py、research_web_navigation/questionnaire.test.mjs与research_web_codex_navigation.mjs。

固定 DSH 搜索覆盖字段由 session-controller 显式 report 返回，Web service 求产品 scope 并校验计数，session-search/shell 显示受限状态；macOS Bootstrap 原空搜索步骤核对 unavailable_count，仍使用既有 workflow。

`research_workbench_entrypoint/resident/` 为 macOS 登录监督器：controller 管 LaunchAgent、
暂存/回滚；evidence 绑定本地交付与 GitHub 实际 checkout tree；admission 为 HTTP、send/approve/answer
及 Automation 共享栅栏。`test_resident.py` 覆盖跨进程锁、排队延后、故障恢复、CI 与来源绑定。
`main.py` 的只读 resident 投影核对实际进程 revision；Doctor 只读本地状态，不发起网络或更新。

Claw执行流定位为`ui/claw-flow.mjs`、`disclosures.mjs`、`uploads.mjs`及原`core/app/views/shell`；正文搜索为`service.search_sessions`、`main`的严格JSON POST和`client`固定`session.search`映射，UI由`session-search.mjs`串行消费。近处测试为`research_web_claw_flow/send_races/disclosures/uploads/session_search.test.mjs`、`test_session_search.py`与`test_automation_research_task.py`。不新增正文库、调度器或依赖；搜索与长试跑句的权限/失败契约同步UI、API、安全及原生文档，安装CI仍须绑定新候选。

`main.py:local_boundary` 的 `entry_navigation` 仅允许用户触发的根路径 GET 顶层文档导航。
`test_api.py` 的 `clicked_entry` 覆盖本机/私网链接、哈希路由、API/资源/iframe/Origin
拒绝及 Host/HTTPS 保留；权威合同见接口清单、安全清单与安装文档。

Native Tailscale 私网 opt-in 在 `main.py:create_app/local_boundary` 校验精确 HTTPS
origin/Host，`service_manager.py` Doctor 读取运行中 `web_access` 投影。
近处回归为 `test_api.py` 的 tailscale/invalid_private_origin 与 `test_service_manager.py`
的 doctor_web_access。配置步骤、默认回环与多用户边界见安装文档、04-api 和安全清单。

Hot关注位于follows.ts/migration0019；周期计划位于periodic-briefs.ts/migration0020和brief-control的内部租约准入。Host hot_routes/hot_manager与Automation routes管理适配；UI为hot-follows/hot-brief-plans。近处测试覆盖PG最小角色、回放、截止、慢写回滚及Host真实白名单。

schema21的periodic_report_executions保存周期一次性报告原件和回执；periodic-report.ts通过
私有bootstrap的产品Python执行hot_periodic_report.py，复用hot_documents/report_documents，
不启动DSH。periodic handler先保存可复用产物，再在hot.brief的controller队列事务完成。
periodic.report签名读取32KiB块，Manager复验全部hash；GET和UI只下载既存字节。
测试为periodic-report.test.ts、periodic-briefs.integration.ts及test_hot_documents/manager/web。

Hot零重试准备位于launch_runtime.hot_zero_retry，私有同项目启用配置只影响本实例官方route。
正式执行为hot_handoff.execute_hot_handoff/hot_routes execute，复用send及原生marker恢复；
test_hot_execution覆盖丢失/重启/失败真值，test_hot_retry_policy/runtime_launch覆盖配置与overlay。
model-control.ts取消明确未发送reserved，hot_model_controls.py复验knownUnsent回执，真实PG测试
精确清理本次资源，未知或历史资源保留。

`app/research_web/live_acceptance_budget.py` 是实例私有验收账本；入口为 launcher/guard，近处测试为 `test_live_acceptance_budget.py`、`test_runtime_launch.py`、`research_web_guard.test.mjs`。费用、期限、持久扣票或绑定变化须同步预算设计与安全合同。

## FinGPT 深入研究定位

原生计划由 projection.py、runtime/research.cordis.yml 和 guard.mjs 处理；research_evidence.py 管理会话来源与底稿质量投影；resources/research_report.py 管理确定性中文报告。UI 的 research-report.mjs 复用当前研究空间与草稿控制器。近处用例为 test_fingpt_research.py、test_research_report.py 与 research_web_fingpt.test.mjs；改变引用/格式合同须同步 API、文件、UI、安装文档和架构清单。

CSV证据的显式格式辅助函数 `resources/research_report.py:calculation_evidence` 只组装章节/claim/notes/coverage；service.py 提示模型使用实际Host观测及冻结要求映射。真伪仍由 research_quality.py 独立判断，缺口与409门不变。回归复用 test_research_calculations.py，涵盖行数章节、逐字引用、真实缺口与外来观测拒绝。


本文件只回答四个问题：改哪片源码、先读哪份权威文档、跑哪些测试、什么变化需要同步文档。文件和公开符号的机械清单由 [生成索引](generated/py_file_index.md) 负责。

每轮资源收尾由`iteration_resources.py`/`iteration_cache.py`复用`docker_resources.py`及`git_safety.mjs`：任务归属/证据保存、全项目20GiB受管缓存预算、合并后自动清理与修补feature身份认证。权威规则见AGENTS、AGENT_WORKFLOW和Docker手册；近处测试为`test_iteration_resources.py`、`test_docker_resources.py`、`iteration_closeout.test.mjs`及`git_safety.test.mjs`。不新增产品API或调度器，风险为管理平面与安全清理。

## 当前 Research Web

Hot 的阶段一入口位于 `research_workbench_entrypoint/hot.py`（配置、诊断与 Native 生命周期），
`hot_manager.py`（签名进程管理）、`hot_postgres.py`（实例归属与受管 PG）和
`services/hot/`（PostgreSQL、私有签名回环协议与独立 Node 服务）。对应文档为
`services/hot/README.md` 与安装指南 Hot 小节；测试为 `test_hot_entrypoint.py`、`test_hot_manager.py` 及
`services/hot/tests/`。Web 生命周期、Settings、研究交接与结果页已装配；实现入口和
真实链路验收仍分别取证。新增入口属于 dual-runtime 清单；它不创建第二个研究引擎。

归档核心为 `services/hot/src/archive.ts`，受控命令为 `scripts/archive.ts`；对应真实测试
`archive.integration.ts`、`managed-archive.integration.ts`。Native CLI 经 HotManager 管理
私有归档、恢复目标和未知结果日志。hot_joint_archive.py 追加选定会话快照的签名联合恢复，
不恢复 Native 执行历史。新 inventory 直接哈希 PostgreSQL JSONB 文本，旧未标记编码要求
从原库重备份；研究 ZIP 的 payload（含 metadata）及实际 ZIP 各受 64 MiB 上限约束。
Hot 持久采集位于 `services/hot/src/collection.ts`，共享源目录为
`app/research_web/datahub/hot_public_sources.json`。migration 5 的原文/inbox/水位提交、
分批解析、限定来源调度、重领与取消由 `collection.integration.ts` 验证；
`scripts/collection-proof.ts` 对四个官方来源做真实双轮后台验证。
来源控制在 `src/source-control.ts`、migration 6、`rwb hot source-configure`；配置版本、
不可变审计、签名权限、重复请求、取消窗口与暂停 inbox 恢复由 source-control/source-cancel
及真实 service integration 测试负责。
模型累计预算核心为 `services/hot/src/model-budget.ts` 与 migration 7，测试为
`model-budget.integration.ts`。migration17 / `research-model.ts` 在相同 owner 事务中预留
研究预算和不可变 call/attempt 映射，已存结果终态/跨日复用。实际 DSH 流经
runtime/hot-model.mjs 的私有预算桥发送；内核测试和真实研究回执分别认证。
模型接入契约为 `services/hot/src/dsh-text.ts`，使用固定 DSH prepared-call API，
对应 `dsh-text.test.ts` / `dsh-receipt.test.ts`；正常 worker 经 native-model.ts 装配。
固定 Native 验收入口为 `scripts/model-live-proof.ts`，其 `src/native-dsh.mjs` 复用固定
DSH 服务与现有 Keychain bridge；版本来自共用 runtime 合同，新官方路由为
`llm-deepseek-api-key`，真实目录/零重试prepared-call见 `native-dsh.integration.ts`。
migration 9 做每日准入/跨日重验，credential-safety
测试覆盖转义后的秘密反射。Hot 处理与正式研究共用授权 scope，装配入口见后文。
事件与频道持久层为 `services/hot/src/events.ts` 与 migration 10，测试为
`events.integration.ts`。共享身份、不可变材料关联、直接后续图、第三频道配置、
合并/拆分/重新归属/标题/频道人工纠错、历史投影和人工判断继承在此验证。
模型评分须绑定已有回执；正向测试为 synthetic，不等于真实归组/规则质量验收。
普通 worker、签名产品 RPC、Web 页面和正式研究使用此持久层。
材料归组工作流为 `services/hot/src/processing.ts` / `dsh-grouping.ts` 与 migration 11；
采集 parse 事务注册不可变版本的处理项，可选模型能力接入同一 worker 的 `hot.process`。
`processing.integration.ts` / `dsh-grouping.test.ts` 验证冻结输入、跨语言候选、回执复用、
迟到/拒绝/预算终态和精确版本投影。`model-live-proof.ts group` 沿用固定验收 scope，
不增加新额度。Native bootstrap、领域规则和产品读取入口见以下各项。
领域规则为 `services/hot/src/channel-rules.ts`、migration 12 与 `channels.example.json`；
同一 worker heartbeat 有界轮询并持久保存评分依据、覆盖状态、独立运营主体和时点。
`channel-rules.test.ts` / `.integration.ts` 覆盖旧文/未知时间不增热、官方低热度重要政策、
来源变更/旧历史及人工评分优先。真实样本入口 `scripts/channel-live-proof.ts` 不调用模型；
公开频道配置、读写 RPC/CLI/UI 和研究交接均复用此领域合同。
内部签名事件/频道 RPC 在 `services/hot/src/projections.ts`、`channel-control.ts` 与
`service.ts`，migration 13 保存频道条件配置审计。`event-rpc.integration.ts` 通过真实
service/PG/scoped roles 验证历史投影、固定 cutoff 分页、字面筛选、继承评分、权限和UUID重放。
这些读取不调度或调用模型；Python CLI/Host/UI、关注与研究交接使用此签名接口。
Native CLI projections/control 在 `hot.py` / `hot_manager.py`，新命令为 channels/events/event/
channel-configure/event-correct；Python stdlib 测试验证参数映射、读写key分离、回执/输入门
与outcome_unknown UUID保留。event-rpc integration 中真实 Python dispatch/owned Node/PG
往返隔离凭据backend和解释器选择，并验证父进程消失后的独立回收；不是系统Keychain证明。
Web Host/UI、正式模型激活与研究快照交接由下列模块连接。
Hot Host为 `app/research_web/hot_service.py` / `hot_routes.py`，前端为 `ui/hot-workspace.mjs`；
main挂载惰性有界桥，core/app/shell/settings保留既有路由并新增工作区/设置。对应std测试
`test_hot_web.py`与`research_web_hot.test.mjs`验证关闭竞态、超时容量、明确动作、UUID重试、
安全文本/链接及跨页材料选择/cutoff。实际浏览器未配置旅程使用离线研究runtime fixture，
不等于真实事件/研究或干净安装。Hot图与API清单为同一文档事实源。

原生计划：`runtime/research.cordis.yml` / `runtime/guard.mjs` 仅装配固定 Todo 与精确授权；
`projection.py` 恢复同会话回合/写入版本，`ui/views.mjs` / `shell.mjs` 在研究空间呈现。
合同见 `architecture/research-web/02-research-runtime.md`、`04-api.md` 和 `research-web-ui.md`；
验证为 `test_protocol.py`、`test_event_recovery.py`、`test_runtime_launch.py`、
`research_web_guard.test.mjs`、`research_web_ui.test.mjs`。原生插件集成证据独立于模型 live、
浏览器、干净安装和 macOS CI；文件交付与 Todo 完成分别判定。

`app/research_web/portfolio_decisions/` 与 `ui/etf-paper.mjs` 提供工程ETF模拟。
权威合同为 `architecture/research-web/03-data-files.md`，API为 `04-api.md`；
测试为 `test_etf_decisions.py`、`test_etf_decision_routes.py`、`research_web_etf_paper.test.mjs`。
时间因果、资金事务、恢复、数据准入或执行假设变化须同步合同与测试，不认证真实收益。


`rwb-docker`、`docker/manage.py`、`docker/Dockerfile.control`、`docker/Dockerfile.dev`
及 `docker/buildkitd.toml` 是 Mac mini 管理平面与开发基座，权威说明为
`docs/research-web-docker.md`，近处测试为 `tests/research_web/test_docker_manager.py`。
生命周期/配额/镜像/挂载变化须同步该手册；真实镜像、实例健康与开发重建另保留本次证据。

异根 Native 私有 pair 认证共享 `web_bootstrap.py` 的现有 bounded reader；OS 用户标准根
发现、调用内根/父/record FD 与真实 lease 复查由 Docker 和 Native manager 同路径消费。
`test_docker_runtime.py` 覆盖重复 start、restart 预拒绝、stop/start、正常 Native bridge、
安装 preflight 拒绝及 root/record/process/lease/scope/controller 变化；其他近处 catalog
以临时 locator 隔离真实用户记录。fixture 不证明物理 Docker 或安装后 Native 切换。

| 双运行时源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `runtimes/research_web.json`、`app/research_web/runtime_contract.py` | Native/Docker 共用 Python、Node、CJPY、DSH、pnpm 事实 | `research-web-installation.md`、`architecture/research-web/01-system.md` | `test_runtime_contract.py`、`docker_runtime_contract.test.mjs` | 固定版本、闭包或镜像事实变化 |
| `research_workbench_entrypoint/runtime_mode.py`、`bootstrap.py`、`docker_runtime.py` | 无 `.venv` 的模式路由、安全切换、Compose 归属 | `research-web-installation.md`、`architecture/research-web/02-research-runtime.md` | `test_runtime_mode.py`、`test_docker_runtime.py` | mode schema、CLI、归属或错误码变化 |
| `research_workbench_entrypoint/docker_resources.py` | 精确资源预览/清理、卷归档恢复、测试任务收尾 | `research-web-installation.md`、`architecture/research-web/02-research-runtime.md` | `test_docker_resources.py`；Mac Docker Desktop 真实资源验证 | 命名、保留、删除授权、引用或备份合同变化 |
| `app/research_web/process_spec.py`、`runtime_state.py`、`staged_runtime.py`、`launch_runtime.py`、`service_manager.py` | 共用进程规范，分离认证状态和镜像内已验证 DSH 资产 | `architecture/research-web/01-system.md`、`02-research-runtime.md` | `test_service_manager.py`、`test_runtime_launch.py`、`test_staged_runtime.py` | 生命周期、挂载或 DSH 资产合同变化 |
| `app/research_web/credential_backend.py`、连接/MCP/Automation 调用点 | Native 系统 keyring 与 Docker 私有文件凭据后端的明确选择 | `architecture/research-web/03-data-files.md`、`05-security-validation.md` | `test_credential_backend.py`、相关连接/MCP/Automation 测试 | 凭据存储、ACL 或跨模式边界变化 |
| `Dockerfile`、`compose.yaml`、`.dockerignore`、`docker/` | 非 root 单容器镜像、DSH/Web 监督、认证健康检查 | `research-web-installation.md`、`architecture/research-web/01-system.md` | `test_docker_packaging.py`、`test_container_supervisor.py`、`docker_runtime_contract.test.mjs` | 基础镜像、构建、挂载、端口或健康变化 |

以下原有表继续映射产品模块；上表只添加部署与运行边界，不创建第二套 Web/DSH 引擎。

端点基础 helper 为 `research_workbench_entrypoint/runtime_endpoints.py`，成对内部 origin
事务为 `app/research_web/control_origin.py`；对应 `test_runtime_endpoints.py` 与
`test_control_origin.py`。前者保存私有端点 CAS 快照并生成回环候选，后者保留控制 token、只重绑
既有 URL；二者由公开启动器消费，只有真实健康后发布端点。`EndpointStore.restore` 用本次发布
快照 CAS 恢复旧端口并生成新 revision，避免恢复旧 CAS 代际。复用 `runtime_mode.py` 的私有读写/锁，修改该边界须保留
`test_runtime_mode.py`、`test_runtime_auth.py`、`test_datahub.py`、`test_mcp_authorization.py`
负面测试；接口合同见运行时与安全模块文档。

Docker fresh-root 事务只在 `docker_runtime.py` 与 `setup_web.py` 内借外层真实 lease 保留父/根 FD 和调用内观察。`test_setup_web.py` 覆盖 owned-classification fixture 的真实 Native 子进程桥、真实临时监听身份、no-start 无产品根、后续真实 mkdir、晚期发布/恢复拒绝与 controller/lease 替换；既有 container/bind-race 测试明确使用已存在的受管数据根。Native/auth、通用 guard、依赖与验证策略不变。

生命周期集成由 service_manager、bootstrap、docker_runtime、setup_web、web_bootstrap
共同覆盖；`lifecycle_lock.py` 改用 stdlib logging，`assert_held` 验证本进程实际持有的锁对象，
用于安装候选内部调用而不增加 skip-lock 开关。`docker/supervisor.py` 的 prepare-only 入口
只用原 creator 补齐缺失控制文件；controller 通过无发布端口/无凭据挂载的固定镜像临时 guest
执行，精确核对一次性归属并确认清理。新增用例在原有 service_manager/runtime_endpoints/
runtime_mode/docker_runtime/setup_web/cli_lazy/web_bootstrap/container_supervisor 测试模块内。

Docker bind 根与私有叶布局由 Dockerfile/Compose 配置、entrypoint 父目录检查、supervisor
严格创建与 healthcheck 只读消费共同维护；测试闭包为 `test_container_supervisor.py`、
`test_credential_backend.py`、`test_runtime_launch.py`、`test_docker_packaging.py` 与
`docker_runtime_contract.test.mjs`。不得通过放宽 owner、mode 或 no-follow 来适配 bind 映射。
固定凭据与产品日志 bind 缺失叶的两阶段首建在supervisor内实现；其确定性测试模拟root→当前UID/GID并覆盖
foreign owner/group、mode/inode变化、alias/替换与自定义路径不豁免，原validator不修改。
Docker `/state` 为私有 tmpfs，状态叶不采用 bind 映射例外或写初始化；宿主 state/logs 在受管
生命周期私有创建后单独绑定。controller 测试覆盖必需 tmpfs、实际 RW、严格选项语义及
旧 host runtime 原样保留；CI 直接 Compose fixture 同步准备 logs，平台门范围不扩展。
同一 Engine HostConfig.Tmpfs 投影由正常与临时 control-preparer inspect 共用；后者仍只挂载
唯一产品 data bind 与原四个私有 tmpfs，测试同时覆盖省略重复 Mounts、严格选项与未知替换不清理。

`test_docker_runtime.py` 还覆盖Compose创建后返回非零/超时的恢复：本次launch标签识别、
精确容器清理、未知实例保留、既有停止容器保护，以及离线repair失败后旧接受image重建。

| 源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `app/research_web/main.py`、`service.py`、`client.py` | HTTP/SSE、会话和 DSH 投影；按运行模式注入凭据后端 | `architecture/research-web/01-system.md`、`02-research-runtime.md`、`04-api.md` | `tests/research_web/test_api.py`、`test_protocol.py` | 路由、状态、恢复或认证变化 |

| `model_credentials.py`、`runtime/model-credentials.mjs`、`launch_runtime.py` | Native Keychain 与显式 Docker 加密模型文件的私有桥接、owned overlay；Host record 保留原实现 | `architecture/research-web/05-security-validation.md`、`02-research-runtime.md`、`research-web-installation.md` | `test_model_credentials.py`、`test_runtime_launch.py`、`research_web_model_credentials.test.mjs`；真实 Keychain/固定 DSH 仅显式 opt-in 合成验收，真实模型另验 | 后端、命名空间、凭据回退、记录委托或受管解释器变化 |
| `rwb`、`rwb.cmd`、`research_workbench_entrypoint/web_*.py`、`app/research_web/service_manager.py`、`service_diagnostics.py`、`lifecycle_lock.py` | 环境后备诊断、服务事实、排他锁、启动恢复与 Web ready | `research-web-installation.md`、`architecture/research-web/01-system.md`、`02-research-runtime.md`、`05-security-validation.md` | `test_web_contract.py`、`test_web_bootstrap.py`、`test_service_manager.py`、`test_cli_lazy.py` | 公开 CLI、PID/端口归属、健康、错误码、恢复或浏览器时机变化 |
| `app/research_web/ui/`、`app/research_web/asset_workspace.py`、`app/research_web/asset_routes.py` | 当前产品原生 UI 与 Asset Workbench backend | `research-web-ui.md`、`research-web-appearance.md` | 验证策略 focused closure：`ui/asset-workspace.mjs` → `tests/javascript/research_web_workbench.test.mjs`；`asset_workspace.py` / `asset_routes.py` → `tests/javascript/research_web_workbench.test.mjs` + `tests/research_web/test_asset_workspace.py`，并累积架构与 Project Constraints 检查；其他 UI 运行相关测试和 E2E | 导航、DOM、可访问性、交互或 Asset Workbench API 合同变化 |
| `app/research_web/datahub/` | 目录、Provider、Broker、快照 | `research-web-datahub.md`、`architecture/research-web/03-data-files.md` | `providers_akshare.py` → `tests/research_web/test_datahub_catalog.py` + `tests/research_web/test_datahub.py`；其他已登记 DataHub 测试 | 能力、来源、字段、路由或快照合同变化 |
| `app/research_web/integrations/` | 五阶段集成状态和探测编排 | `architecture/research-web/09-integration-coordinator.md` | `tests/research_web/test_integration*.py` | 状态、归因、授权或探测变化 |
| `app/research_web/frameworks/`、`ui/frameworks*` | Gold／Dollar 专用框架 | `architecture/research-web/08-research-frameworks.md` | `test_frameworks*.py`、`research_web_frameworks*.test.mjs` | 方法版本、快照、评分、renderer 或会话绑定变化 |
| `app/research_web/capabilities/`、`skills/` | Skill、Method、Tool、Workflow | `research-web-capabilities.md`、`architecture/research-web/07-capabilities.md` | `test_capabilities*.py`、能力 UI 测试 | 目录、包版本、资源、权限或发现变化 |
| `mcp_registry/`、`mcp_runtime/` | MCP 目录、安装、Host 和授权 | `research-web-capabilities.md`、Research Web 架构模块文档 | `test_mcp_*.py`、marketplace 测试 | Registry、安装、OAuth、策略或调用边界变化 |
| `automation/` | 定时任务、Run 和投递 | Research Web 架构模块文档 | `test_automation*.py`、计划 UI 测试 | 调度、重叠、恢复、投递或秘密边界变化 |
| `report_workflows/` | 报告模板、底稿、运行和交付 | `architecture/research-web/03-data-files.md`、`04-api.md` | `test_report_workflow*.py` | 模板、资源、运行、Excel 或交付变化 |
| `documentation.py`、`build_research_web_api_atlas.mjs`、文档检查脚本 | 安全只读文档入口和离线门禁 | `research-web-documentation.md`、`architecture/research-web/06-documentation-contract.md` | 文档治理、架构和路由测试 | 文档 schema、索引、图文或检查策略变化 |

`architecture/research-web/architecture-map.json` 是 Research Web 架构 source/document/test/diagram inventory 的机器真源；`.agents/verification-policy.json` 是 changed-file → impact → validation route 的唯一机器真源。图册首页与 API Atlas 同时从该清单生成；`--check` 只读检查集合和完整内容，不写工作区。`reading.modules` 复用 `groups`，只为研究框架与集成协调器补充集中阅读定位。两者互补且不互相推导：新增 Research Web 源文件仍须进入架构清单，而本表的测试闭包说明不能替代 verification policy。

Docker CI 由 Linux 真机在指定提交完成本机验收后，通过 `.github/workflows/research-web-docker.yml` 的 `workflow_dispatch` 和必填 `expected_sha` 发起；Mac PR/push 不自动触发，checkout 与 dispatch SHA 不一致时失败关闭。本机 Docker 构建、Native/macOS 安装门及真实 Windows 回执必须分别记录，源码测试不替代平台生命周期。仅 docs 变化按 changed set 的规划器结果验收，不能因旧任务已验收而虚写回执。

Docker 启动/安装修复的目标闭包还覆盖 `test_setup_web.py` 的候选失败与摘要恢复、
`test_cli_lazy.py` 的 Native `status --json` 安全投影。`test_docker_runtime.py` 检查延迟健康、
失败回滚归属、不可变镜像选择及 Doctor 的 `dsh` 公共字段；`test_runtime_contract.py` 成对检查
无关祖先目录活动和合同父目录瞬时 alias。API 与本机集成测试使用每例独立的内存 keyring，
不读取宿主凭据；生产凭据错误仍失败关闭。

本地集成回归另覆盖 `test_web_bootstrap.py` 的工作树环境归属、`test_runtime_mode.py` 的
坏 Native 环境与 PID 重用拒绝，以及 `test_container_supervisor.py` 的完整页面探测总时限。
容器 supervisor 的 Web 预算回归在原测试模块使用真实 loopback HTTP/认证和确定性耗时钟，
覆盖三项 GET 完整就绪、剩余期限裁剪、各页面错误与精确子进程清理；不替代镜像真机验收。
Docker 控制测试使用临时端口，真实端口冲突断言继续执行，不要求停止开发者正在运行的服务。

上述 DataHub 专项映射仅登记策略中明确允许的路径。未登记 DataHub 路径继续 fallback / fail closed，不能仅凭目录位置推断为低风险。`asset_workspace.py` / `asset_routes.py` → `research_web_workbench.test.mjs` + `test_asset_workspace.py` 只说明验证策略的 focused closure，不表示本次修改了 `architecture-map.json` 或从架构 inventory 推导了验收路由。

## 兼容平台

下列代码仍受维护，但不是当前 Research Web 的默认依赖：

| 源码区域 | 权威参考 | 更新触发 |
| --- | --- | --- |
| `app/api/`、`app/cli/commands/`、`app/web/` | `docs/modules/app_*.md`、`REFERENCE.md` | 兼容路由、命令或旧 UI 合同变化 |
| `core/`、`services/` | `docs/modules/core_*.md`、`docs/modules/services.md` | 领域契约、服务边界或模型网关变化 |
| `connectors/`、`data_layer/`、`ingestion/`、`cron_jobs/` | `DATA_SOURCES.md`、对应 `docs/modules/` | Connector 生命周期、来源或持久化变化 |
| `storage/`、`data_layer/repositories/` | `DATA_STORAGE.md`、仓储模块文档 | schema、迁移、Repository 或事务变化 |
| `knowledge_layer/`、`reasoning/`、`cognitive_agents/` | 对应 `docs/modules/` | 提取、证据、推理或旧 Agent 合同变化 |
| `signal_lab/`、`timing_engine/`、`memory_learning/`、`reporting/` | 对应 `docs/modules/` | 计算、回测、记忆或报告投影变化 |
| `src-tauri/`、`desktop/`、`scripts/desktop/` | `desktop_packaging.md` | 任何桌面运行、安装、更新或平台行为变化 |

兼容模块文档不应把自身描述成 Research Web 现役入口。文件增删或公开符号变化时更新生成索引；纯内部行为变化不需要制造索引 diff。

## 规则与交付

- `AGENTS.md`：共享工程规则真身；`CLAUDE.md` 只保留 Claude 专属差异。
- `docs/AGENT_WORKFLOW.md`：选择本地快环、worktree 或后台／远程执行。
- `.agents/project-constraints.json`：架构、平台和文档治理门禁配置。
- `.agents/verification-policy.json`：改动路径到 Component × Risk(L0-L4) × Platform、local/CI/real-machine lane 和 merge/release gate 的唯一机器真源。
- `scripts/plan_verification.mjs`：受管共享内核的只读薄入口，保留 changed-files 模式；显式 `--base --task-context` 输出 Git 绑定 plan v4，保留完整 changed set 和总门，按实际宿主落实 RWB 功能开发/macOS 与平台适配职责，不执行计划中的命令。
- `scripts/validate_verification_receipt.mjs`：受管共享内核的只读薄入口，receipt v3 分别推导 `hostAcceptance`、完整 `platformHandoffs` 与 `aggregateAcceptance`，同时保留总 `mergeReady`/`releaseReady`。CI 的实际 runner/checkout 和真机平台独立核对，不能用单宿主证据证明所有原生平台；继续只读兼容历史 plan v2/receipt v1、plan v3/receipt v2。
- `scripts/summarize_verification_delivery.mjs`：只读复核 plan v4 / receipt v3 后输出任务/平台验收及交付 metadata。候选必须一致，未知 metadata 拒绝；metadata 不能改写机械结果，PR/合并/实例及图形身份只是记录，不由摘要认证实际交付。
- `tests/javascript/verification_policy.test.mjs`、`verification_receipt.test.mjs`、`verification_platform_task_entry.test.mjs`：规划、升级、平台、状态、安全与证据合同；新薄入口 fixture 只证明参数/职责路由，受管内核集成和真实平台证据分别验收。
- `scripts/git_safety.mjs`、`tests/javascript/git_safety.test.mjs`：RWB macOS 受管 Git 入口、共用目录锁、仓库本地维护配置、可恢复备份与清理保留合同；临时仓库恢复测试不代表其他宿主启用。操作和限制见 `docs/AGENT_WORKFLOW.md`，不修改共享框架安装副本或产品运行时。
- `tests/javascript/verification_delivery_summary.test.mjs`：正式受管 validator 的交付摘要合同，使用临时 Git 与明确 synthetic 证据；覆盖候选、未知 metadata、路径及旧/未绑定回执拒绝，不证明原生或远端验收。
- `tests/javascript/repository_cross_platform_contract.test.mjs`：Git 换行、vendor 字节稳定和本机状态忽略合同。
- `.agents/runtime/leon-engineering/manifest.json`：共享验收内核固定版本、source commit、协议和受管文件哈希；不拥有项目策略。
- `.agents/skills/incremental-validation/`：Codex/Claude 共用的项目增量验收流程；只引用策略和脚本，不复制路由表。
- `docs/actions-budget.md`：GitHub Actions 免费额度、冻结状态、平台路由与保留策略。
- `.ai/reports/`：每个实现任务的真实证据及 `architecture-review` 标记。
- 源码结构或导入发生变化时运行 `python scripts/generate_py_file_index.py --check`；需要更新时先生成再复核。
- `Research Web Tabbit Verify` 当前仅手动触发；Tabbit 契约变化或平台支持声明必须显式运行双平台工作流，自动 Project Constraints 继续检查其触发器契约。
- 普通 Research Web 改动由 Ubuntu `Research Web Checks` 承担；Bootstrap 和 Desktop Verify 必须依路径命中，不能由 docs-only 提交触发。Windows Verify 由 policy changed-set 条件选择，但只能从 Windows 真机以 exact SHA `workflow_dispatch`，不能由 Mac PR/push 自动触发。

## 最小验证

双运行时 Python 质量检查限定于当前 changed set。格式化先核对非导入 AST 与导入集合；
内部端口 TypedDict、已验证记录的类型说明和显式 `check=False` 不改变参数省略、拒绝或返回码合同。
Ruff/Black/isort 与 mypy 使用的实际版本、参数和同版本基线必须记录，历史 PASS 不替代当前诊断。

```bash
node scripts/plan_verification.mjs --project . --changed-file <path>
node scripts/plan_verification.mjs --project . --base <base-sha> --task-context <project-relative-json>
node scripts/validate_verification_receipt.mjs --project . --plan <plan-json> --receipt <receipt-json>
node scripts/summarize_verification_delivery.mjs --project . --plan <project-relative-plan-json> --receipt <project-relative-receipt-json> --delivery <project-relative-delivery-json>
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node scripts/check_research_architecture.mjs --project . --base <base>
python scripts/check_doc_sync.py --project . --base <base>
node .agents/project-constraints.mjs --project . --changed-file <path>
```

先对完整 changed set 重复传入 `--changed-file`，再按 `validationsByLevel` 从 L0 执行到 `requiredLevel`；多文件取最高风险并合并去重。局部失败或非预期行为必须带 signal 重新规划。receipt 保存摘要、组件、平台、local/CI/real-machine 实际状态、`mergeReady`、`releaseReady`、未覆盖风险和升级判断，并通过 validator 才能交接。选中 gate 未运行时记录 `NOT_RUN` 或 `MANUAL_REQUIRED`，绝不写成 `PASS`。Project Constraints 保持独立的架构/平台/文档门，不复制策略内容。

平台任务由 Git 绑定模式自动发现完整变更；task 固定候选/base、目标与本宿主范围，并只能补选已登记的 `supplementalGateIds`。本宿主 PASS 不提升其他平台状态，也不推导总体验收 READY；说明源码、图源/生成物、候选、CI 实际 checkout 与报告所属提交分开记录。受管内核只由正式 source→preview/apply/verify 更新，不手工维护副本或 manifest。

已知组件可以在策略中映射不同等级的候选验证：低等级只选择局部项，耦合或 signal 升级后才纳入依赖/smoke/full 项。未登记测试仍按 `unknown_path` 升级 L4/`full-delivery`，不得仅凭位于 `tests/` 目录推断低风险。

Docker staging 的包发布载荷与过滤合同归 docker/stage_dsh.py、test_staged_runtime.py；改目录筛选须同时验证真实 Node 导入及容器 DSH 健康，不能仅靠镜像构建或资产哈希。

Hot 正常 Native 模型装配：services/hot/src/native-model.ts 由 service.ts owner 建立后加载，读取已有预算和当日定价并复用 native-dsh.mjs。默认停用、缺凭据/权限、跨日 guard 及跨价格缓存兼容分别在 native-model.test.ts、dsh-cache-compat.test.ts 与 model-budget.integration.ts 验证；实际 readiness/cache 脚本为 native-model-readiness-proof.ts。

研究共享预算私有接口为 `services/hot/src/research-model-rpc.ts`，service注册五项签名控制操作；
DSH流消费者为 `app/research_web/runtime/hot-model.mjs` / `hot-model-stream.mjs`，由launch_runtime
overlay装配；private hot-model HTTP路由经HotWebService/HotManager转入签名RPC。完整请求
冻结/预算、一次prepared发送、回执先存后输出和取消反例见research_web_hot_model_stream.test.mjs，
签名大帧/归属见test_hot_model_bridge.py；真实SDK离线SSE见native-research-stream.integration.mjs。
`model-budget.ts` 的事务内dispatch helper与run/价目校验共享owner fence。标准流usage由服务计算
费用并保存完整回放；transport只为回执/缓存开放有界大帧。测试为research-model-rpc/transport
单元及research-evidence真实PG/RPC。正式研究执行复用hot_handoff与已有DSH send。

Hot 模型管理由 hot_model_controls.py / scripts/model-control.ts 连接 model-control.ts；0014-model-controls.sql 添加不可变审计和状态保护。model-control.integration.ts 覆盖普通角色拒绝、活动归属拒绝迁移、迟到回执和真实三条 CLI；test_hot_model_controls.py 覆盖 pre-key、UUID、记录失败与冷库恢复。

Hot 用户定价：hot_pricing.py 经 check-pricing.ts/ pricing.ts 校验并保存私有日期记录；native-model.ts 在 run/reserve/dispatch 验证日期与指纹。pricing.test.ts/test_hot_pricing.py 覆盖新模拟日期、变化阻断、私有文件、真实CLI及fsync故障。

browser-dataset-proof.ts 是有界真实事件读取验收准备/恢复脚本：固定原授权schema/ledger、验证probe与identity、临时暂停来源并新建隔离控制角色；不调用模型，恢复时保留原quota。Web浏览器读取截图和失败/独立清理证据在任务报告。

Hot简报冻结核心为 `services/hot/src/briefs.ts`，验收为 `briefs.test.ts` 和
`briefs.integration.ts`；同一只读事务冻结全部关联版本、频道配置、原判断与覆盖依据，
校验规范JSON哈希并导出安全Markdown。该内核只负责冻结；持久记录、公开入口、
DOCX、原文副本和调度映射由下列适配负责。合同见 `services/hot/README.md` 简报小节。

持久简报为 `services/hot/src/brief-control.ts` / migration15，service签名接口brief.create/get/list；controller条件版本发布与UUID重放，读取复验冻结哈希。`event-rpc.integration.ts`真实Node/PG验证旧版保持、重启重放、权限与不可变性。公开Host/UI/CLI、DOCX及调度研究映射复用固定版本。

Hot简报Host为hot_routes/hot_service与HotManager，网页core/hot-workspace新增briefs视图和详情显式生成；brief.export按32KiB UTF8分块，Host固定版本并校验完整哈希。相关test_hot_manager/test_hot_web、research_web_hot与event-rpc integration覆盖只读权限、未知UUID、晚到预览和真实HTTP→Node/PG。浏览器/MD-DOCX真实验收另存任务报告。

早期浏览器简报验收使用原hot_acceptance_model schema15，保存真实AI/宏观两份version1简报并从浏览器下载；browser-dataset-proof.ts使用独立proofId写一次基线，恢复失败也独立禁用已绑定临时角色，失败/权限清理状态分开记录。当前schema20，真实Keychain/DSH报告及联合恢复的后续证据不由该旧证明替代。

Hot token限额修订为migration18/model-control.ts `amend-tokens`及Native
`model-amend-tokens`，仅停机migration-owner增加已有scope的两个token列并保留原费用审计。
冻结Hot快照的脚本准入在Snapshots.admit_hot_script与ResearchService.native_admission；
既有capability准入后验证本会话Hot归属和所有原件哈希，仅返回该dataset只读目录。
初期研究曾因预留上限无报告；后续已生成并核验真实报告，执行最终因预算终止。
hot_results分别显示执行failed与交付completed；读资料的Seatbelt验收不等于报告完成。

Hot研究结果读取/原回合核对为hot_results.py与hot_routes，测试test_hot_results/test_delivery及research_web_hot；Delivery.refresh新增可选不可变key，旧调用默认保持。结果按Delivery原合同完整流式SHA核验，100文件/每文件16MiB，超限明确不可核验，不以展示截断写入failed。

报告质量的全量 CSV 复算由 research_calculations.py 提供，研究质量服务绑定来源、文件 SHA 与当前回合；test_research_calculations.py、test_delivery_cache.py、test_research_quality_scope.py 复用现有 Research Web Checks Python 步骤，新增测试预算 15 秒，不新增 job/runner。Mac 干净安装及真实模型并发交付单独验收。

模型服务多连接：`model_profile_registry.py` 校验公开身份及固定 ref→物理账号映射，`model_profiles.py` 复用服务锁、活动/受理/交付保护与原配置提交，`ui/model-settings.mjs/css` 管独立 DOM 表单与服务商目录。`automation/service.py` 保存连接身份，`service.create` 在同一锁内核对日程期望绑定。近处回归 `test_model_profiles.py`、`research_web_model_profiles.test.mjs`，原 Keychain、Docker 密文、兼容适配与设置回归保留。


资产 CJPY 实际回读补充：providers_cjpy.py 映射业务周期/复权到已安装 SDK；asset-chart.mjs 与 asset-workspace.mjs 读取供应商原字段“时间/简称/vol”。test_asset_workspace.py 对单通道来源调度和 SDK 参数做离线回归；真实取数只在显式授权的隔离目录中验收，不修改已有实例凭据。
