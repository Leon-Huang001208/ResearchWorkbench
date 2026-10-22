# 资产历史显式来源与近期不复权备用：本地交接

日期：2026-10-23。宿主：macOS。类型：Web功能开发。基线为`5d3927fae923d443a2c85431e4bc6ec33be7c9f6`，隔离worktree为asset-history-fallback-20261023。当前源码未提交；精确最终SHA、独立评审、远端三CI及Mac干净安装由主任务完成后另绑定。本报告不认证真实供应商或已部署。

## 行为与边界

HistoryJobRequest新增source，省略保持tinysoft；旧job读取时缺省tinysoft，不回填磁盘。非tinysoft仅recent/none，重试冻结source/adjustment/requested_as_of。auto冻结四来源真实配置映射，不hash空来源配置。底层raw调用实际DataHub.query/Broker，固定来源不fallback。

Wind股票history纯范围校验在Broker候选准入：auto两年请求跳过超过60自然日的Wind后继续AK/Bao；固定Wind为明确workload_too_large，Host区块为error且无伪造失败dataset，requested_range仍保存。index/ETF原Provider拒绝合同保持；未修改transient集合或拆块换源。

新asset-history-raw-2核验证券身份、日期/OHLC冲突和明确CNY/share/量额单位，turnover只按已声明CNY金额映射amount。未知完整响应可以停止历史发布，不声称已质量降级。没有上市日时listing_date:null、boundary_verified:false、full_history:false。实际输入provider/URL/manifest/hash/配置摘要保留，最终发布与缓存复用复验实际来源授权；规范快照授权指纹绑定实际provider。qfq/hfq仍执行Tinysoft全部因子/锚点门，不能用raw假扮复权。

UI新观察为auto概览及recent/none/source:auto历史，原观察不批量改源。历史来源选择显示固定来源与自动备用范围；更早/全部明确先选天软。重试用原任务冻结输入，失败仍保留旧图。取消与partial复用真实来源Future排空，迟到结果不发布。

## 已执行证据

- TDD请求/单位RED见logs/asset-history-contract-red.log、source-red.log；UI RED见logs/asset-history-ui-red.log。失败点分别为缺source、缺单位校验、旧tinysoft/qfq默认和缺来源控件。
- Broker/Wind RED→GREEN见logs/asset-history-broker-red.log和broker-wind-green.log，96项通过。
- 历史/Broker/Wind联合134项通过：logs/asset-history-combined-01.log。后续定点workspace57项通过：logs/asset-history-workspace-02.log；早期四失败保留workspace-01.log，修正不必要index/ETF提前行为，并将固定stock超范围断言同步真实Broker拒绝。
- HTTP真实路由→HistoryJobs→DataHub→Broker→AKShare线程执行器→规范快照六场景通过：logs/asset-history-http-04.log。仅供应商边界使用合成payload；受控天软失败/超范围Wind跳过/AK成功、固定天软零备用、未知单位/错证券/冲突/撤权不发布均覆盖。无真实vendor、模型或付费调用。
- 真实AK线程Future取消与旧job只读两项通过：logs/asset-history-more-01.log。Future结束前任务活动、无迟到发布，改来源retry拒绝。重试UI冻结截止/来源/复权由loading JS覆盖。
- 全asset JS158项通过：logs/asset-history-all-js-01.log；UI相关189项通过：logs/asset-history-ui-closure.log；Router L4通用112项通过：logs/asset-history-router-L4.log。
- 已执行八Python文件ruff、black --check通过；generated Python index已官方重生成，文档治理通过。最终格式与完整changed-set约束仍以最后复验记录为准。

## 隔离及剩余门

Host测试明确注入MemoryCredentials，System/Private凭据构造器和方法、keyring方法failclosed；唯一basetemp在本任务logs。没有安装依赖、触碰外盘/PG5432/真实凭据/常驻服务。旧snapshot与全部固定复权回归保留。公开三安装入口及锁定依赖没有变化，兼容性由最终同候选Mac Bootstrap、固定DSH/3081/8088/Doctor证明，当前NOT_RUN。

实际供应商、认证浏览器图表呈现、最终独立review及CI仍NOT_RUN；主任务另行取证。当前未提交/发布，不更新主checkout或部署，不把离线成功当真实供应商已通。

## 结构评审

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"来源选择仅在原历史图表工具栏新增select并透传冻结参数，仍调用原历史任务端点和当前账号AssetWorkspace；没有新增页面、导航或引擎，现模块与资料流图继续准确。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复用现有Broker候选准入、Provider执行器、worker_activity和快照发布；范围校验前移与真实来源元数据不增加数据流节点或数据库，原Host到Broker到Provider图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"HistoryJobs增加source参数与来源配置映射和原始日线发布校验，继续相同HTTP和会话快照CAS，不增加研究运行时或持久服务；旧任务和复权材料可读，原资料流图无需新节点。","diagrams":[]} -->

## 最后源码复验（未提交）

联合Python191项PASS（history/Broker/Wind/workspace；第三方Starlette弃用警告1项），见logs/asset-history-final-pytest-01.log。最终全部asset JS158项PASS，见logs/asset-history-final-assets-js-03.log；final-assets-js前两次失败记录保留，修正后的断言核对新请求明确固定Tinysoft来源，不削减复权或取消验收。9文件ruff/black/isort PASS，官方Python索引--check PASS，完整changed-set Project Constraints PASS见logs/asset-history-constraints-02.log，文档治理PASS见logs/asset-history-documentation-final.log。源码仍未commit，远端/真实验收状态不变。

最终自查追加原始行所有已返回证券/日期别名一致性门：两个RED为DID NOT RAISE，见logs/asset-history-alias-red.log；修复仅asset_history.py与已有history测试，最新history40项PASS见logs/asset-history-final-history-02.log。对应两文件black/ruff及官方索引--check再次PASS。其余模块无新修改；191联合检查点与最新40项历史证据按各自字节边界保留，不冒充最终同候选CI。完整changed-set doc-sync PASS见logs/asset-history-doc-sync-final.log。

## 集中SPEC三项修复

真实页面元数据漏source：从app.mjs实际assetTerminalMetadata和configureAssetTerminal函数组装到真实chart事件的RED→GREEN见logs/asset-history-app-source-red.log、app-source-green.log（84项）。来源按dataset.asset_history.source→request_parameters.source→observation.source→tinysoft，source进入签名且source-only变化同步chart state；auto/AK all不发请求，缺省旧源明确tinysoft。

raw2所有有值OHLC/volume/amount/turnover别名逐一核验声明单位及数值一致；相同数值不同/未知单位拒绝，Optional None保持缺失、必需价格None拒绝，旧Tinysoft normalize_rows未改。前台deadline下Hub ownedtask仍drain时job保持draining/childID和容量，复用同call的DataHub.cancel并shield等待真实执行器退出才失败/开放retry；排空期间create busy，取消仍等待，晚结果不发布。集中RED见logs/asset-history-review-red.log（7 failed、1既有turnover拒绝通过），GREEN见review-green.log。

最新history50项PASS见logs/asset-history-review-closure-01.log，包含真实AK线程与TOTAL_DEADLINE=.03、drain期间busy/cancel及正向别名/None。全部asset JS159项PASS见logs/asset-history-review-final-js.log；变动3Python文件ruff/black/isort PASS。最终源码尚待集中SPEC终态、质量评审与最后commit/CI绑定，不将旧冻结hash用于新字节。

## TS集中复审遗留来源兼容修复

app实际metadata与workspace初始HTML对无source的asset-history-1按原唯一Tinysoft合同识别，覆盖观察request.source=auto且section_sources.history=tinysoft的旧qfq图；all请求仍明确tinysoft/qfq，不要求先切源重建、不回填旧盘。raw2缺source为unknown，显示来源未知并禁用新历史操作；controller进入旧图时也不自动用无source请求推进。后者独立RED证实旧实现会发recent/none无source任务，现明确错误且零提交。

TDD日志legacy-source-red.log→legacy-source-green.log（85 chart+tabs）、raw2-auto-red.log→legacy-final-js.log（全部asset JS161 PASS）。实际测试从app源码抽取真实metadata/configure→真实chart事件，并同时核对workspace初始HTML，不仅手工metadata fixture。Python源码未变，最新history50项证据仍保持相同Python字节；无真实供应商或Git写操作。最终冻结manifest以本次更新后文件为准，旧hash不认证本轮。

## Root一次真实免费备用链验收（2026-10-23）

Root已完成且本次未重跑：`logs/asset-real-free-fallback.log`及`logs/asset-real-free-fallback/result.json`为PASS，记录的四个关键产品文件SHA-256与本次读取字节一致。实际AssetRouter→HistoryJobs→DataHub→Broker→原AKShare Provider/public_worker取得600000.SH不复权近期历史，请求2024-10-20至2026-10-20；HTTP 202后job completed，规范版本asset-history-raw-2，485行，实际日期2024-10-21至2026-10-20。listing_date仍null，boundary_verified=false、full_history=false，不升级为全历史或正式回测证明。

范围严格区分：Tinysoft OSError是受控注入且仅一次，不是实际天软供应商失败验收；Wind为人为配置的候选，真实Broker参数/范围准入以workload_too_large跳过，没有运行真实Wind SDK。AKShare真实SDK和public_worker未被替换，_invoke只加一次调用计数包装，实际免费公开数据由原执行路径返回。没有付费供应商、模型、生产凭据或PG调用；临时目录已删除。脚本`/tmp/rwb-asset-real-fallback-once.py`仅只读核查，本轮不重新执行。

此证据更新此前“真实供应商未执行”的阶段状态，仅认证上述一次真实AKShare备用闭环；真实天软/Wind、全市场/全历史、认证浏览器、最终CI与部署仍须分别取证，不能由该免费样例推定通过。

## 最终JS独立质量复审与功能检查点准备

Root转交的最终独立TypeScript/JavaScript reviewer结论为PASS，实际98项复核通过；本任务仅记录此评审来源，不冒称由实现者自评。四个受审源码SHA-256已在本worktree只读重新核对：app.mjs=55f0caa1167de1d63f769571f00dcb4c63c487a34fdc17fb18163380b0fe9ffa；asset-chart.mjs=93e82d97ba1a55be6afbadb0a17c21e77b0d72f3804794773d68df0c8cba9265；asset-controller.mjs=732aacc281e01bdfd9a83436f37e5e108cce5f906241214ac4966a467b88acdb；asset-workspace.mjs=8e4924cde907adc19dbdeab43c61c8bb7abeb01988da888484d89524f6df8b34。

本功能检查点包含此前一次真实AKShare免费闭环485行证据，受控Tinysoft故障和Wind范围跳过仍保持独立边界。实现者现获root独占Git窗口，仅提交本feature及后续阅读revision绑定，不prepare/push/部署；最终候选CI、认证浏览器及常驻实际状态仍由root分别留证，未部署不改判。

## Root真实隔离页面发现空历史来源回滚（提交前修复）

Root在18997隔离Host/CUA页面取得证据：初始观察auto且无history dataset，选择Tinysoft后唯一任务081151df-e66f-43fa-a190-f92c0dae19c5确为tinysoft/recent/none/provider_error，但DOM下拉回显auto；再选auto不触发change且无新job。该现场无模型/生产凭据，未发public供应商请求。原最终独立JS PASS98及四hash属于本修复前检查点，不用于认证此新chart字节。Root请求暂停commit，已立即归还Git窗口，未stage/commit/prepare/push。

根因为chart.configure在previousBars为空时每个queued/failed通知都完整初始化，抹掉用户choice并重置pendingserial。最小修复只在真正首次/identity变化时完整初始化；同identity空rows保持choice和请求serial，空→首批rows独立初始化视区/选中日。新增测试执行实际app metadata/configure→真实chart source事件→queued/failed→重选auto，并核对首160条行视区40..160、最新选中日和身份切换重置。RED见logs/asset-history-empty-poll-red.log，GREEN全部asset JS162项见logs/asset-history-empty-poll-green.log。无供应商重跑，Python源码不变；新源码待独立JS复审及新hash绑定后才能提交。

## 修补后真实完整Host页面闭环及最终独立复审

Root在18997隔离完整Host页面完成PASS：显式Tinysoft请求失败后下拉仍保持tinysoft，切回auto确实创建新任务；实际原AKShare/public_worker返回485行并真实绘图，最新9.76、2026-10-20，页面展示来源AKShare／不复权／上市边界未核验。证据为logs/asset-visible-host-final.log、logs/asset-visible-host/final-assessment.json、result.json、retired.json和final-visible-state.txt；截图位于`/Users/leon/.codex/visualizations/2026/10/23/asset-history/real-fallback-chart.jpg`。初次真实UI失败controller/source-selection-red证据保留，不用后续成功掩盖。

公开AK实际调用合计两次，分别用于此前API闭环和本次完整Host可视闭环；本UI进程最多一次public invocation。受控Tinysoft/Wind设置仍不构成真实厂商验收；模型、付费供应商、生产凭据、PG均未调用。最终UI临时Host graceful exit0、PID absent、临时root删除、CUA tab8关闭；最初server exit143无finalizer及ownroot只读capability copies导致首次清理拒绝亦保留。Root核实任务目录身份后仅为本任务目录增加owner-write后删除，没有变动宿主服务。端口plain bind仍errno48（TIME_WAIT），reuseaddr复查PASS，不能写plain PASS。

新chart源码eb5894165e19bf712d74624285da192c5d268a7745c7adbfdcbc62d7e66bab52已获Root转交的独立TS最终PASS99，其余三受审JS仍为前述55f0caa／732aacc／8e4924c。该结果替代旧chart的PASS98检查点，真实页面也绑定修补后字节。实现者未重跑vendor；本feature现在按Root重新授予的独占窗口提交功能检查点与reading绑定，仍不prepare/push/部署，常驻部署与最终CI另证。

## 源码检查点与阅读入口绑定

功能源码检查点已实际提交：`323da9ae60960dbe7f246f4686a54302bebbf819`（fix(assets): route recent raw history through equivalent fallback），包含34个本任务文件及真实AK/Host页面范围报告。reading.repository.revision固定到此源码提交，由官方build_research_web_api_atlas生成入口与API Atlas；生成物及本记录归第二文档提交，避免自指。检查点不代表已push、最终CI通过或常驻部署；实际平台与供应商范围仍按上文分别记录。

阅读绑定实际检查：官方build_research_web_api_atlas生成及--check通过，reading/architecture/documentation JavaScript91项PASS（logs/asset-history-reading-architecture-tests.log）；专项architecture-check及完整changed-set doc-sync包含约束、生成索引、文档治理PASS（logs/asset-history-reading-architecture-check.log、reading-doc-sync.log）。本次第二提交仅绑定map/阅读README/两项生成HTML与报告，不改变功能检查点产品字节。
