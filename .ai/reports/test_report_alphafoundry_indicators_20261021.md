# AF 连续资产指标区迁移：验证与架构报告

宿主为macOS，任务类型为Web功能开发，本平台范围为本地macOS检查、真实CJPY和同候选Mac安装CI；Windows／Linux原生产品验收由对应设备交接。实现与完整交付尚在进行，不据本报告宣布通过。

## 变更与边界

原AF指标区连续展示基本行情、五图行情终端、估算筹码、资金流及财务／前十股东／行业／事件／宏观五卡；补充资料在其后，旧view定位区域。六MA及BOLL／MACD／KDJ／RSI公式、预热、缺失、周月重算与筹码估算见UI合同。新增asset-indicators.mjs与asset-projection.mjs分别负责纯计算和真实字段投影；chart／workspace／controller沿原应用生命周期。

原ObservationRequest新增section_sources／section_ranges和valuation区块；原HTTP路径、AssetWorkspace→Broker→Provider、Store及会话快照不变。显式来源不隐式回退，Wind60天硬门保留，旧记录沿原source／全局日期。ECharts5.5.0／Chart.js4.4.7采用用户已独立批准的固定本地资源，须验许可／摘要、wheel与安装物一致性。

不迁移AF Agent委员会、数据库、协调器或新Provider；缺数据卡片保留未知，不补假名单、行业或宏观。DSH仍为唯一研究引擎，账号权限、研究质量、凭据及常驻部署边界保持。

## 实际证据与未验证项

| 检查 | 状态 | 证据与限制 |
| --- | --- | --- |
| 后端聚焦回归 | PASS | `test_asset_workspace.py` 57项；与本机集成、协议组合回归244通过／1原生Windows跳过，`logs/af-local-gates/summary.json` |
| 独立Python评审 | APPROVE | `/root/af_backend_review`，绑定routes／workspace／tests三文件摘要；无供应商／模型调用 |
| 图表／页面聚焦JS测试 | PASS | 资产套件67项（含实际固定ECharts SSR回归与原函数黄金值），兼容workbench18项；`runtime-assets-suite.log`、`logs/af-final-workbench.log` |
| 图文／文档治理／Python索引 | PASS | 本文下列实际命令均通过，架构与治理0 violations；源码并发变化后须最终复查 |
| 独立JS评审／完整Router | APPROVE／L4待外部CI | `/root/af_js_review`最终规格及质量均APPROVE，独立85／85；完整53路径Router为L4，保留失败升级信号及Windows交接 |
| 同输入原AF对照／多宽度明暗／生命周期浏览器验证 | PASS | 原模板／JS与迁移页使用同一320条标记夹具，25／25；5宽度×明暗、五图联动、原生缩放／拖动／滑块、迟到响应和实例释放；`logs/alphafoundry-indicators-20261021/summary.json` |
| 真实CJPY冷启动首次查询与冻结读回 | PASS | 真实AssetWorkspace→Broker→tinysoft，无回退；报价1条、日线243条；冻结数据浏览器4／4，无额外供应商或模型调用。原始授权数据仅保存在私有日志，不进入源码或CI |
| wheel资源 | PASS | 本机公开构建后核对10个新增模块／vendor资源逐字节相同；`logs/af-wheel-contents.json`。无新Python依赖 |
| 同候选macos-14干净安装／Doctor／3081与8088健康 | NOT_RUN（源码检查点） | 随最终候选PR取得外部CI证据，记录到Git绑定Router回执；本机已有环境不替代安装CI |
| Windows／Linux原生产品验收 | NOT_RUN | 对应设备接手，不从Mac派发产品CI |
| 常驻部署 | NOT_RUN | 仍需单独明确授权 |

Python新增SectionRange和请求模型结构改变，因此运行生成索引检查；首次检查发现stale后按原生成器更新docs/generated/py_file_index.md，不手改生成内容。API Method／Path未变，Atlas和部署／数据／执行拓扑仍准确，不制造图源变化。最终候选SHA、CI／Router回执及主代理实际日志尚待绑定，当前不能宣称mergeReady或releaseReady。

公式证据直接执行AlphaFoundry实际Python指标方法和原JS筹码函数取得；完整窗口与展示预热另按批准方案校正。日／周／月成熟值和五个180桶筹码窗口均对齐，图源摘要及测试输入保存在`tests/fixtures/alphafoundry_indicators_golden.json`；不把原版的预热不足、净额拆流入流出或持仓当流量问题带入。

最终交互曾稳定失败22／25：副图配置显式`axisPointer: undefined`在ECharts完整重建时覆盖默认嵌套配置，留下series model而缺少view，后续缩放报`incrementalPrepareRender`。仅省略未配置属性；真实固定库SSR先红后绿、真实Chrome强断言保留并25／25通过。原失败日志仍保留；新增断言要求实际series view和连接到ZRender的可见K线／成交量图元，不能只证明有model。源代码检查点之后的CI与归并、收尾证据由私有交付回执补充，报告不自称在未来SHA运行。

文档子任务于2026-10-21实际执行：

- `node scripts/check_research_architecture.mjs --project .`：PASS，0 violations；初次发现ui组08-research-frameworks.md须同步，修正其旧资产说明后复验通过。日志 `logs/alphafoundry-indicators-doc-architecture.json`。
- `node scripts/check_documentation_governance.mjs --project .`：PASS，778份文档、98份current，0 violations。日志 `logs/alphafoundry-indicators-doc-governance.json`。
- `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/ai-news-live-deploy-20261019/.venv/bin/python scripts/generate_py_file_index.py --check`：更新后PASS；同一解释器执行 `scripts/check_doc_sync.py --project .`：PASS。日志 `logs/alphafoundry-indicators-doc-sync.log`。
- `node --test tests/javascript/documentation_governance.test.mjs tests/javascript/research_architecture.test.mjs`：8／8 PASS，无skip。日志 `logs/alphafoundry-indicators-doc-tests.log`。

未改批准计划、Actions预算、vendor notices或源代码；docs/architecture/research-web/readme-review.json记录unchanged及根README仍适用的具体理由。独立文档检查只证明当前变更集一致性，未认证并发实现的最终SHA或真实功能验收。

## 架构复核

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"只在既有资产页面内替换连续指标呈现与浏览器图表资源，未增部署节点或改变Host和DSH数据箭头。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"原AssetWorkspace观察、取消和刷新生命周期保留，增加请求分区参数与valuation快照，原会话交接和路径保持。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"请求body及封闭区块枚举扩展，Method与Path、Host认证和唯一DSH执行协议保持，Atlas路径无需重建。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api-contract","structure":"unchanged","reason":"既有观察创建和刷新接口增加严格分区来源日期校验，未增加HTTP端点或安全信任节点。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"分区参数和valuation仍经现有Broker及market_snapshot，既有来源硬门、会话快照和Provider集合不变。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在原Web静态包增加已批准本地图表资源，Native和Docker部署、DSH、数据根及凭据边界均保持。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"资产读取与快照继续使用认证用户原数据根和Host，未增加账号路由、池或权限，主私有实例拓扑不变。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"公式范围及离线库安装检查复用原Checks和Mac Bootstrap，真实厂商和同候选安装仍独立，不新增CI拓扑或平台派发。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"浏览器指标不是新的Skill或Tool，能力目录、原DSH准入及质量门保持，不迁AF委员会。","diagrams":[]} -->
<!-- architecture-review {"group":"ai-news","structure":"unchanged","reason":"资产个股资讯只沿原Golddata只读路径定位，未改AI资讯worker、预算、来源、数据库或模型授权。","diagrams":[]} -->
