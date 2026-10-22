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

## 合流前CJPY最小字段字典增量

Root单独授权的旧CJ_KEY仅由独立CjClient完成一次markettable_columns；HTTP200、SDK0.5.2、53字段、0行情/财务/模型、0配置写和token持久化，临时HOME已删除。证据logs/cjpy-field-metadata/result.json和field-dictionary.json；字典600权限且凭据扫描false，字典SHA27df9e431be417c522e65151179dcc476822f38e792f8ea497bd19733ac4d829。vol规则明确股票为股，amount仅元；OHLC单位与币种没有声明，不能恢复规范研究仓桥。实现者本轮没有调用SDK或处理凭据。

最小补齐只修改CJPY同步结果投影和既有测试：实际SDK.__version__精确0.5.2、显式market_bars/stock/daily并经cn_stock_identity时，实际返回vol标share、amount标原生元/currencyNone；OHLC仍None/None，volume别名保持未知。新Result增加field_dictionary_evidence合同tinysoft-stock-daily-fields-v1、字典方法/hash/版本及applied判定，不重取字典或行情，不改rows/raw或旧快照。其他SDK、缺类型/频率、weekly、ETF/index及stocklabel却index身份均无单位升级。

TDD：logs/cjpy-dictionary-red.log（8失败、1既有bridge排除通过）→green.log；新增负向与凭据failclosed隔离后，test_datahub_cjpy+test_asset_history合计95项PASS，见logs/cjpy-dictionary-closure.log。所有新字段在SDK线程内只读本次已有响应与__version__，没有新的厂商调用；ResearchWarehouse._bridge仍拒绝Tinysoft，normalize_raw_rows仍因价格单位unknown拒绝。增量待独立Python复审，四JS源码保持既有最终受审hash，后续合流/Router/CI/组合UI另证。

## CJPY增量集中SPEC修复与显式raw单位策略

SPEC实证请求stock但行代码SH510050仍获股票单位。TDD新增5返回身份分支，冲突/missing/null所有别名无证明时保unknown，匹配SH600000才applied；保持rows/raw。SnapshotSeries明确静态field_dictionary_evidence键纳入白名单，离线freeze/export_restore证据对象/hash/fields/raw保持，外部metadata/token继续丢弃，质量/PIT仍false。RED5失败1既有匹配通过→GREEN6项见cjpy-identity-native-{red,green}.log。

另SPEC确认CJPY成功731行但价格单位unknown，旧auto会后置失败而AK零调用。经Root同意，新增typed Host合同required_semantics=cn_stock_daily_cny_share_v1，仅market_bars/沪深stock/daily/none有效；默认None不入旧fingerprint，通用native/fixedTinysoft不变。Broker按现已声明单位候选收窄，Tinysoft以price_units_unverified跳过而非调SDK后改complete状态；HistoryJobs新非Tinysoft近期raw冻结合同，查询/manifest/块缓存/canonical皆绑定。retry保原策略，缺字段旧job保None，无隐式升级。原生SnapshotSeries不接受该合同，旧native缓存不能满足规范请求。证券/日期/数值冲突后置门仍拒绝，不盲retry；deadline/Future容量不变。

TDD契约RED见raw-semantics-red.log、history-semantics-red.log、native-policy-red.log；GREEN对应日志。真实Hub/Broker/Provider离线案例先CJPY成功731行native+未知单位，再新合同AK成功且不复用旧native缓存，新合同第二请求命中其AK缓存；generic仍可读旧native缓存，通用执行失败仍Tinysoft→AK，fixedTinysoft失败零备用。新history策略完成规范AK快照，旧retry缺策略保持None。原HTTP受控OSError测试现在明确auto在准入price_units_unverified跳过，不再宣称执行了天软故障；通用执行失败fallback由同Hub案例保留。新增越界日期/证券/单位/冲突负例均只1候选且不发布。

最新集中闭包174项PASS见logs/asset-three-fixes-closure.log（CJPY/native snapshot/Broker/history）；所有测试仅离线边界，无新Vendor/凭据/模型/DB/依赖操作。此前真实API/Host485行属于旧策略源码阶段，不可替代本新合同的最终组合实际UI；后续由Root在合流候选另验。Runtime普通工具白名单schema维持，不把Host内部required_semantics偷传厂商参数，Pydantic schema与API文档同步。

三项修复收尾：9增量Python文件Ruff/Black/isort PASS，完整changed-set doc-sync包含constraints/index/governance PASS（logs/asset-three-fixes-doc-sync.log）；通用QueryPolicyTests/ExecutionTests10项PASS（logs/raw-policy-reliability.log）。产品源码冻结交SPEC集中复核，尚未commit/prepare/publish；真实组合UI、最终质量/集成/CI仍待后续。

## Root/SPEC最终身份澄清与运行失败备用补证

Root/SPEC确认CJPY实际默认markettable形状完全无identity列，封闭单一精确code+沪深stock/daily/exactSDK0.5.2请求本身可作局部vol/amount依据：metadata明确identity_basis=single_security_request、response_identity_observed=False，不向rows/raw补asset。这替代上一检查点“完全缺身份列一律unknown”的保守实现；存在任何空/ETF/指数/矛盾身份别名仍applied=False，全部匹配为row_aliases。请求身份澄清TDD见cjpy-request-identity-{red,green}.log；原生冻存/恢复用例同步保留身份依据对象。

新增真实HTTP→HistoryJobs→Hub/Broker→执行器离线链：CJPY按已知价格单位缺口skip、Wind范围skip，AK受控vendor_unreachable执行失败，再FakeBao可信CNY/share原始日线成功。实际executions仅AK/Bao且call计数精确，双方executor路径仍保留原deadline/容量；所有输入策略字段随chunk/evidence/query/manifest冻结。缓存同策略_reuse成功，改顶层策略None拒绝，伪改evidence query策略也被_authorize_inputs拒绝（history_cache_version_changed），不复用不满足合同的缓存。RED→GREEN见http-ak-bao-policy-{red,green}.log。

最终集中闭包175项PASS见logs/asset-three-fixes-closure-02.log，覆盖CJPY/nativeSnapshot/Broker/history。无Vendor、模型、生产凭据、数据库配置或依赖操作；本轮所有成功取数都为离线受控SDK/Provider边界，不能复用旧真实UI作为新政策验收。

三项修复最终冻结：176项集中测试PASS（logs/asset-three-fixes-final.log），typed Host schema及厂商parameters不能携内部策略均覆盖；9 Python文件Ruff/Black/isort PASS，完整changed-set doc-sync/constraints/index/governance PASS（logs/asset-three-fixes-final-doc-sync.log）。产品源码与测试冻结交SPEC集中复核，未commit/prepare/publish，未追加供应商请求。

## 独立质量复核与最小类型注解修复

独立review_asset_three_quality对c7beb冻结版未发现P1/P2，执行176项PASS并记录新增两项mypy dict-item错误：CJPY局部fields初值被推断为None-only。仅将局部变量显式注解为dict[str,dict[str,str|None]]，不改行为。CJPY50项再次PASS见logs/cjpy-annotation-only.log；该文件Ruff/Black/isort PASS。五源文件同范围mypy --follow-imports=skip由原6项变为4项（logs/asset-three-mypy-annotation-skip.log）：providers_cjpy:477 arg-type与broker:68/161/374 Resolution call-arg保持旧债，本任务不改、不写全mypy通过。无follow-imports筛选的诊断也保留logs/asset-three-mypy-annotation-fix.log，含跨模块旧错误，不隐藏。

实际缓存边界：Asset新job refresh=True显式刷新整个请求区间，不先查仓补缺；DataHub普通refresh=False逐来源精确复用完整缓存，但Wind>60天缓存仍被当前fetch准入guard拒绝。跨来源部分覆盖不拼接，warehouse prepare交易日历可能联网；以上未完成能力不由本次成功降级/冻结/完整缓存测试推定完成。此处仅如实交接边界，不扩大本次修复。

Root补充的普通仓只读核查：DataHub refresh=False已实现仓候选AK miss后Bao完整命中且0 fetch；这不改变History新job refresh=True显式整段强刷边界。Wind storage_read仍无条件经过validate_wind_query的>60自然日限制，导致该类完整缓存受挡，本轮只记录、不扩源码修复。

Root已转交独立质量最终PASS，注解后0a6dc冻结九文件精确匹配；CJPY50及Ruff/Black通过，同范围mypy新增两项消失、原四项债保留。仅局部类型注解，无行为改动，176项此前行为闭包按源码差异映射保留，不伪称重跑。现按授权提交本feature源码/文档检查点并managedprepare最新master，未发布、未部署；组合实际Host/Bao验证和最终全门随后由Root协调。

新源码检查点实际提交`f3149a578ab3d86c96651ef25d42725c7de25a01`，包含本次typed raw语义/缓存边界及CJPY原生字段证据完整保存。此处reading.repository.revision更新到该源码检查点，官方生成物归随后的docs commit，避免自指；与最新master的组合源码另由managedprepare及其精确候选说明，源门/实际组合UI/最终CI不混写。

## 受管最新主线组合源码准备

实际合并源码检查点`4675525d211b30050d31b75279b157e21f3d9e3d`，父提交71ce8519ae3cf8542e21ff77373a861c873423c1与87abc999c3274e2e98b597eb1600c8b0ad2226e3。首次managedprepare报告integration_conflict但仅生成干净base-only WT，无MERGE_HEAD；按Root授权在自有integration显式正常merge，12项冲突均文档/生成物，逐块保留Plugin/Auth/Market与Asset说明，readme-review合并双方审核理由，HTML官方重生成。产品源码无需手工冲突修复；SnapshotSeries保留已审Market indices完整性代码与本任务field evidence/raw语义门，app.mjs保留主线Plugin接线和资产回调。

组合SnapshotSeries目标回归36项PASS（logs/combined-native-snapshot.log），未提前重跑长门。reading现绑定上述真实合并source，避免用不含主线Plugin文件的feature checkpoint冒充组合代码；当前docs-only提交之后再由managedprepare认证精确candidate。Root尚将对组合候选进行一次真实Bao可视闭环，再补sourceaudit与最终一次全门；未push/部署。

## 最终组合真实BaoStock Host/UI与独立审查

Root在精确候选5cdaee4f06677cea948070dbe45675a265a1fba4运行完整Host和浏览器，最终PASS。CJPY因price_units_unverified候选跳过，Wind因workload_too_large跳过；AK为受控executor vendor_unreachable失败，然后真实BaoStock public worker单次调用约1.409秒成功，485行，实际2024-10-21至2026-10-20、最新9.76。required_semantics、来源配置摘要、raw2与CNY/share声明随结果冻结，listing_date:null、boundary_verified:false、full_history:false。canonical顶层attempted_sources为[]，完整候选及两条执行记录保留在asset_history.inputs[0].manifest/provider_metadata.execution_attempts，不能写成审计记录缺失。

固定Tinysoft先受控失败后DOM保持tinysoft，切auto生成新job；初始快照的受控CJ也失败，此验收只认证上述历史/图表链，不宣称整页其他区块全部成功。模型0，无PG、生产凭据或常驻更新。临时Host exit0、PID6678 absent、任务root删除、18997 reuseaddr复查PASS、tab9关闭。证据logs/asset-final-bao-host.log和logs/asset-final-bao-host/{controller.json,result.json,final-assessment.json,retired.json,final-visible-state.txt,verify_visible_host.py}；final-assessment SHA256=2b8525a237ada3da075738aecbea5b809b22f13a8d041d73b2b1ff960614073d，result SHA256=ddfbbc6502f4b988c1cb23e137859b45c03f1c955b62f8c90d5712fd9cc67d70。截图/Users/leon/.codex/visualizations/2026/10/23/asset-history/final-bao-fallback.jpg由Root实际检查并提供用户。此前真实AK的API/页面共两轮各485行仍分别保留，不与此次Bao单次混称只有一次调用。

独立Python最终review精确5cda PASS91、Ruff/Black且无P1/P2，logs/asset-combined-quality-review.json SHA256=94a97c1e0b69dc329c263f696f89423c0aba1b2ff9355ac0e4dc3dec7313c9b0。最终JS独评同5cda PASS99及Plugin UI8项，无P1/P2；logs/final-combined-js-review-20261023.log和final-combined-plugin-ui-review-20261023.log。ESLint不可用且未安装，保持未执行，不冒充PASS。受审四JS为组合app0ee7f9f42cda802f815fbcd72c9e16fce6240b591170fd7963768c91d4ced13a/chart eb5894165e19bf712d74624285da192c5d268a7745c7adbfdcbc62d7e66bab52/controller732aacc281e01bdfd9a83436f37e5e108cce5f906241214ac4966a467b88acdb/workspace8e4924cde907adc19dbdeab43c61c8bb7abeb01988da888484d89524f6df8b34。后续只改report/新64源ledger等文档，通过相同app tree映射沿用此产品证据，未再调用Vendor或模型。

新的逐源证据快照为.ai/reports/2026-10-23-datahub-source-verification.json，保留2026-10-22旧快照；报告只引用路径，不与ledger互嵌hash以避免自指。准备回执已认证5cda；同base status=prepared不支持再次prepare刷新docs-only HEAD，受管规则禁止replace-prepared及手工改回执。按Root确认保留原prepared和新文档HEAD的产品tree映射，完整Router绑定实际最终HEAD，Root正常publish入口届时合法读取clean HEAD更新integrationCommit；本轮不写二次prepare成功、不push/部署。
