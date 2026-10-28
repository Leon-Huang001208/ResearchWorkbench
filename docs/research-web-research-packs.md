# 研究组合包纯计算内核 v1

macOS / Mac mini 的 Web 功能开发，T3-A 限于 `scenarios/packs/`。
这是九包的限定确定性内核；下述 A/A2 段描述纯核自身，后端接线另见文末 B1。不是全部
62 Skill／78 Tool 对齐完成，也不是供应商等价、真实来源或报告质量证明。
原18个 gated 计算方法没有 import、复制、重命名或解锁。

## API 与适配边界

`execute_atom(method, records_by_kind, parameters)` 执行一个公开方法。
`execute_pack(pack_id, records_by_kind, parameters, source_coverage=...)` 组合方法；
`parameters` 顶层包含严格时区 instant `as_of`，其余键为该包方法名，值为该方法参数。
未知对象字段、记录类型与参数拒绝，异常统一 `PackError.code`，日志仅记录稳定码、
方法和计数。`record_contracts.py` 冻结 v2 设计材料的规范记录结构；校验使用现有
web.lock 中 jsonschema，不增加依赖。`synthetic_vectors.json` 是22个明确无权限的
合成测试向量，risk 的旧 complete 字符串故意拒绝，测试另构造完整范围声明。

现有公开 scenario `subject={kind,identity,...}`、自然日 `as_of` 不变。
新内核 security 是 `{security_id,market,asset_class,currency}`；带时区 instant
必须由未来 Host 明确映射，不能将自然日偷偷转换为午夜／日终，或把 SYN 标识当真实证券。
内核只校验格式和计算，不读文件／网络，不判断 owner、来源许可或真实 hash。
`origin.locator` 只是引用，绝不解释为可打开的路径／URL。
caller 没有 `owner_id/rights/passed` 入口；这些未知字段被拒绝也不证明合法权限。

每份结果固定 `host_qualification=NOT_RUN`、`research_quality=NOT_RUN`，
`method_source_binding=host_required`。`result_sha256` 仅绑定未含自身的规范 JSON，
不是比较回执、签章或正式报告。`input_sha256` 绑定原始规范记录与参数；包另绑定来源
覆盖声明。结构参数中的列表以完整集合的 SHA256 和 item_count 投影，不内联证券全集；
scalar 参数原值保留。`parameter_delivery=collections_bound_by_input_digest` 明示这一点。
复算需要 Host 冻结的完整输入，不能从投影推造缺失行。来源 locator 全量返回；缺失／拒绝
清单不截断。B 必须从已认证账号的 Snapshot 原件读回并绑定实际 bytes/hash、权限、
用途、撤权、PIT、逐 method provider mapping、单位和截止策略，再冻结准确方法源代码hash。
JSON 的 provider/owner/hash 声明均不能自证 Host 资格。

## 方法与九包限定输出

| 包 ID | 方法与实际输出 | 保留的缺口 |
|---|---|---|
| position-risk | validate_positions + join_risk_windows：完整仓位、小数/百分比、未知权重、证券/类别/闭区间 join | risk/unlock/insider 必须全部覆盖；observed_no_match 只是声明范围内未命中，不能叫已核实无风险 |
| expectation-gap | compare_qualified_expectations：同证券/期间/口径/归属/币种/单位配对，取各consensus系列披露前最新 vintage，标量或区间绝对差 | 零负共识相对差 null；不造 surprise score；无合格预期保持不足 |
| short-sentiment | sentiment_counts：同market/date/universe/regime分层、真实分母与涨跌/限板/炸板ratio | 不合成总分；缺资金、席位或股票池覆盖保持 partial |
| research-prep | deduplicate_source_versions：原件 hash 精确去重、同URL不同hash保留版本、UTC时间线 | 不相似匹配、不编待问问题；DSH问题提炼未执行 |
| event-review | align_event_trading_day：首个 close_at 大于发布时间的session，目标/基准日期、单位、复权、停牌与缺口 | 只对齐不算收益；event_return_comparison_receipt_required 永久显式保留至原门满足 |
| global-opinion | 同一去重方法：语言/地区、原文关联与显式原源到转载时滞 | 海外来源缺授权仍 partial；不造舆情分 |
| valuation-check | compare_valuation_samples：正PE同口径历史样本、唯一日期、严格早于当前；区间 [count_less/n,count_less_or_equal/n] | 样本不足不报分位；forward缺vintage合同拒绝；不表示收益概率 |
| ownership-structure | disclosed_ownership：同证券/期间持股单位、float、逐holder变化；仅显式声明互斥holder子集合按期合计 | 声明互斥仍待Host核实；超float不报比例；基金穿透 blocked，不当全市场持股 |
| earnings-preview | earnings_calendar + 预期差：最新plan_version、历史引用、实际披露进度、合格预告区间比较 | 不造概率；原earnings monitor比较门仍 blocked |

仓位未知权重是目标权重减已知合计，不回填到缺失证券。重复仓位、超目标、负仓位拒绝。
风险覆盖参数是逐 security/category/window/source_ref/exhaustive 的严格列表，固定三个类别，
不能用删类别降门；来源声明无法通过 Host 权限。空事件只有范围声明完整才产生计算层
observed_no_match。包级 `source_coverage` 也只是来源范围声明，缺任一必需来源列入 missing。
空资料、空共识或缺日历不表示真实无信号。

财务 forecast 必须 vintage 严格早于实际／预告披露。同一vintage值冲突拒绝，独立共识系列
分别输出，不做跨provider平均；不换币种、期间、累计或单季。历史PE相同时间同值去重，
冲突拒绝，ties不四舍五入。日历不猜周末，收盘瞬间及之后归下一显式session；目标停牌
不挪事件日；未来close的price拒绝，缺窗口仅列缺口。alignment post=0合法，但绝不透传
原event-review（其pre/post>=1且要求volume）。CNY_per_share与points各依其真实合同检查。
筹码合计按证券/期间保留，不将跨期份数和当作当期股本覆盖率；disjoint_holder_ids只是
声明，Host还需真实证据。各包固定限定 scope，当前无Host资格时始终 partial/insufficient_data。

## 预算与版本冻结

全部输入≤50,000行／64MiB，严格有限数字与派生溢出检查。单估值序列、exchange-session交易所日历序列各≤5,000；report-calendar按security/report_period每序列≤5,000，
目标和基准各≤5,000；预期比较最多50证券、多证券每证券≤1,000，单证券≤5,000。
系列预算在分配计算结构前检查。完整派生 rows≤16MiB，输出含缺失、拒绝、来源、参数摘要、
所有子回执≤64KiB，超限 `workload_too_large`，不丢字段挤预算。仅最终 rows 最多128条，
完整 total/inline/omitted 与 processed_input_rows 可核；1000仓位尾行仍改变指标。
本模块不创建派生制品，原件 refs 也不冒充全量结果文件。输入按包整体预算，不因分方法
分片绕总行数；各子回执 count 允许重复引用，包 processed_input_rows 为唯一原输入行数。

单一权威源是整个本目录。后续 Native发布必须冻结这套源代码、记录schema与方法版本进入
版本化resources，并以实际字节hash绑定执行回执；历史资源禁止动态import可变Host算法。
当前没有新增执行器、数据库、队列、Skill/Tool注册、真实模型或供应商调用。

## 验证与后续

聚焦测试为 test_research_pack_calculations.py 与 test_research_pack_contracts.py：
手算golden、零负基数、未来披露、混币种/单位/期间/归属、未知/重复仓位、risk缺一类别、
同URL新hash、分位ties/重复日期/样本不足、原算法阻断、空源、预算和尾行验证。
项目完整changed-set Router、独立规格/Python质量评审、通用CI和同候选Mac干净安装由主控执行。
Windows/Linux真机与同平台CI保持 NOT_RUN 交接；浏览器、DSH、真实模型、供应商等价、
正式报告质量及常驻部署本子任务均 NOT_RUN。本层通过不能将组合包／cards 标为整体完成。

## SPEC round1 修正（2026-10-27）

持仓包的risk positions须与validate_positions.expected_universe规范身份全集严格一致，
少一证券、额外证券或删空均risk_universe_mismatch，缺失或未知权重证券也不得省略。
覆盖声明不能改变这个全集，固定三个风险类别仍逐证券核对。

预期差在取最新之前，校验全部financial-key/consensus_id/vintage的值一致性，旧vintage
冲突不能被更新值掩盖。所有actual到独立consensus的派生结果及拒绝项先按时点索引计数，
派生基数上限50,000；在构造笛卡尔结果前超过上限即拒绝。生成时共用DerivedBudget逐行
累计16MiB完整序列化字节，超过预算的行不保留，整个调用workload_too_large，不返回截断成功。
最终64KiB封包门保持。小预算哨兵测试证明大派生先于算术拒绝及字节预算中途停止。

持股期间只接受YYYYQ1–YYYYQ4或YYYYFY并按真实期间时间排序；未知格式或同一截止的
Q4/FY歧义组合拒绝。变化只计算请求序列中相邻且都有披露的期间，缺中间期不跨过计算。
逐已知证券/holder（含显式声明holder）检查全部请求期间，缺失列holder_period_missing，
保持partial；不补0股、不生成缺期持有记录。检查缺期网格同样先验派生基数并累计缺口字节，
防止证券×holder×期间的扩大分配。原22合成向量及72个旧断言不删改。

## Python QUALITY wave2 修正（2026-10-27）

财报report-calendar在挑选最新计划、建立history前先按规范security/report_period计数，
单序列5,000可接受、5,001即workload_too_large；不同证券的多个合法序列仍共享总输入50,000
上限，不用单序列上限误拒合计超过5,000的多序列。plan_version按该序列的set检查重复，
不再每行扫描整个history。5000/5001、两个2501序列、重复版本及计数型比较哨兵均有回归。
带时区instant转换UTC也在受控异常边界内，超出datetime最小/最大日期返回稳定instant_invalid，
不泄漏裸OverflowError；原严格时区格式、naive拒绝和其他日期语义保持。

## A2：单次计算的完整制品消费接口

新增 `execute_atom_bundle(...)`、`execute_pack_bundle(...)`，参数完全复用各自既有接口，
不能加owner/rights/passed、任意文件路径、sink或执行器参数。返回frozen dataclass：

```python
ExecutionBundle(receipt: dict, full_result: FullResultArtifact)
FullResultArtifact(
    canonical_json: bytes, sha256: str, byte_count: int,
    root_row_count: int, component_row_counts: tuple[tuple[str, int], ...],
)
```

既有execute_atom/execute_pack仍只返回dict。四个入口共用私有_calculate_atom/_calculate_pack；
每个registered方法在一次请求里恰好计算一次，捕获投影前的fullrows，receipt和完整制品只是
同一次结果的两种序列化。不调用旧18算法，不重跑来补行，不使用全局/线程缓存或上次结果。
模块不写文件、不输出结果到stdout、不启动Native，不接受IO回调；日志仅含方法/计数/size/hash。

完整canonical JSON固定为有限数、UTF-8、对象key排序、紧凑分隔符，schema名
`research_pack_full_result_v1`，顶层字段如下：

| 字段 | 合同 |
|---|---|
| schema/schema_version | 固定schema名/1 |
| root_rows_kind | atom为calculation_rows，pack为component_references |
| root | method/version、完整metrics/rows/missing/rejected_rows/source_refs/limitations、参数摘要、输入摘要与NOT_RUN状态 |
| components | 包的每个已执行方法的完整payload；atom为空数组；没有投影截断 |
| counts | root_output_rows与component_output_rows，后者以method为键 |

root及每个component另含counts：processed_input_rows、total_output_rows、missing_count、
rejected_count、source_ref_count。pack.root.rows每行仅`{component_id: method}`指向唯一完整组件，
其根行数不冒充子计算行数；例如持仓130/风险390行，对应根2行与两个明确组件计数。
缺数/阻断时也返回合法零/部分行制品及完整missing，不用空文件替代。未执行的方法没有假组件。

full payload的input_digest_kind为normalized_canonical_json_v1，input_sha256与
canonical_input_sha256均绑定规范内存输入；pack包含source_coverage声明。
它不同于未来封印输入文件或Host原件的原始bytes SHA256，不能当PIT/来源/权限证据。
legacy_normalized_input_sha256保留旧receipt输入摘要，receipt_sha256引用原有receipt结果hash。
旧receipt的input_sha256与result_sha256计算语义保留。完整制品不复制64MiB原文输入；
参数列表仍以完整集合hash/count引用，因此复算必须保留独立封印输入。
source_refs保留完整locator，code_version包含method_version与source_binding=host_required，
source_sha256/frozen_resource_version明确null，绝不自造实际发布版本/代码hash；
B需要在可信资源闭包及外层执行manifest绑定实际代码版本和原件hash。

full_result.sha256/byte_count均从实际canonical_json bytes计算，制品对象只持有不可变bytes与
不可变计数tuple，不持有caller可变records引用。Host资格及研究质量仍NOT_RUN，旧组件block和
包partial scope保持；类型对象本身不是任何授权。Host登记前还须重读真实发布文件、验证其实际
hash/size/schema、根和每个组件的完整计数、来源与代码闭包，不信客户端descriptor声明。

单个完整制品（含root、全部components及所有metadata）共用16MiB预算。包在保留下个组件前
累计完整组件字节，最后对整个canonical封包再核16MiB；不能每个child各16MiB后累计绕门。
原50k输入/派生基数、逐行派生字节、5k系列和64MiB输入门保持。receipt继续≤64KiB且逐级数据预览≤128行，
atom数据预览必要时缩小到64/32/.../0行；pack所有component审计wrapper固定保留，只缩component内部的数据预览。
total/inline/omitted真实；missing/rejected/source_refs/metrics不删。
若非rows metadata本身超64KiB则稳定workload_too_large；不把16MiB bytes/base64塞进receipt。
将来Native还需为自己的stdout manifest另行预留预算，原receipt可独立归档，不强塞更大envelope。

本步没有staging/fsync/atomic publish实现；B只能原样写完整bytes并重新核验，不能跑算法补行。
16MiB等号/+1及组合总额、64MiB拒绝路径使用受控小阈值验证，大内存实际压力仍NOT_RUN。

## A2 SPEC fix1：组件审计不可裁

pack.receipt.rows是组件审计wrapper，不能作为普通结果行删减。全部已执行component的方法、版本、
原atom receipt hash、metrics、source_refs、missing、rejected_rows、参数/输入摘要等均固定保留。
root.row_delivery的total/inline始终为全部component数，omitted=0；仅各result.rows数据预览可缩到0，
各自row_delivery准确保留底层总行数/omitted。若全体fixed metadata超过64KiB，整个调用稳定拒绝，
不把fullartifact当receipt审计信息的替代物，也不引入metadata单独artifact。

wrapper.receipt_sha256固定引用原atom receipt，和full.components[*].receipt_sha256对应；
wrapper.result是展示的有界投影，其result_sha256对该实际投影重新计算。这样缩预览不复用旧hash冒充
改变后的字节，原计算回执身份也不会丢失。所有hash均仅计算层绑定，Host资格与质量仍NOT_RUN。
原single-pass算法、完整artifact全部行/计数/bytes/hash与整个包16MiB预算保持。

## B1：Host／Native后端闭环

完成桥的task取消沿原service.lock与Delivery强判串行：只有当前服务器receipt accepted及同key/task/
marker的accepted cancel能阻止本execution新saved，状态复用cancelled并保留实际Native结果。已先保存的
成果不因后续cancel重写；未知/重复完成与新call重试仍拒。JS completion每await及dispatch前重验调用
signal并合并timeout；不把child close或客户端completed当作已提交，wire未知不自动重放。没有新引擎、
Store/schema或算法变化，SourceProof/完整制品与质量读回门保持。

`research-pack-<pack-id>` 是九个新增 Native Skill，不是原18算法的别名。`pack_resources.py`
从精确 allowlist 复制已审纯核及显式验证 profile、合成向量、记录 schema、固定 entry/writer 和
显式 stdlib logger adapter；源算法字节不重写、不 import 可变 Host 算法。全部资源逐文件
SHA256 和排序清单组成 closure，manifest 自身不参与自己的摘要。相对 import 必须在有限
`scripts/` 模块树内解析；动态 import、任意 app/宿主模块与未绑定第三方模块拒绝。
内置只读、copy 清空 reviewed_scripts，编辑／检查／审查／发布仍走原目录；旧用户版本和
原18回执门保留。用户副本不继承原内置包的受控执行身份。

运行依赖沿已安装 Web Python，不安装依赖、不接受 caller PYTHONPATH。包内 lock 投影
v2 绑定现有 whole web.lock SHA 和实际受管集合（当前七个已锁分发，含 jsonschema 可选导入的 idna）的精确版本；Native 版本另冻结实际每个分发的文件闭包、
origin、解释器真实字节、环境与 format checker 集合。Host 准入／完成重算，受管 JS 核对
其配置解释器与该环境；依赖变化拒绝旧资源，不能只比较版本字符串。真实 wheel 的
installed-like 读取不依赖 checkout 的 `requirements/`。

Checks 的开发依赖安装也遵守这个已有冻结集合：从未变 web.lock 的原哈希条目提取
全部七个 runtime 分发及原 renderer/workbook 三项，核对 whole-lock 摘要和投影版本后
先哈希安装，再向原 editable dev 安装传入不含 hash 的精确版本 constraints，最后核对
全部七项实装 metadata。这样避免 hashed constraints 与 editable 安装冲突，也防止
transitive 更新使 Catalog 在测试初始化时拒绝 runtime；不升级锁、改变产品依赖或放松
运行身份门。准备／核验错误写入 `logs/ci-pack-dependencies.log` 并终止原步骤。


运行指纹 schema v3 独立枚举受管分发的 import/data 根及版本元数据，不能由 RECORD 决定代码全集；
未列账簿的新代码也改变闭包。所有实际 `.py`、扩展、schema/data 和 `.pyc` 都参与摘要，外部
pycache prefix 拒绝。仅排除固定解释器／模块入口不执行的外部 console scripts 和四个安装账簿
RECORD、INSTALLER、direct_url.json、REQUESTED，排除路径／原因显式冻结；METADATA/WHEEL
保留。任意别名、越界或假版本元数据拒绝，后续入口不能切为被排除的 console。

复 Python 审核发现旧六分发指纹未覆盖 `_format` 实际导入的 idna，且当前 jsonschema 的
可选 `date-time` checker 原本缺失。本次明确授权的验证层修正新增 `format_profile.py`：
Host 和冻结 Native 用相同私有实例 checker 验证每处 date/date-time，不改全局 registry。
日期使用四位年严格 calendar；瞬时只接受显式 T/Z 或合法 offset、秒和至多六位小数，
拒绝 naive/date-only/basic-date/空格、闰秒、非法日期/offset 和换算 UTC 超出1..9999。
这是与既有 instant 同级的 RFC3339 严格子集，不宣称完整 RFC 闰秒支持。
`contracts.py` 仅校验层接入该 profile，并为参数 instant 复用合法 offset 检查；数学算法、原 record schema、baseline/contracts 冻结文件不变。
profile 和 import guard 自身 hash 进入资源与 runtime identity，旧 v2 不静默兼容或签等价证。

固定 record/output schema 禁止 $ref/$dynamicRef/$recursiveRef/$id/$schema 及未支持 format，
不接受动态 schema 或远程 resolver。导入策略从实际验证入口的递归 module-time imports 绑定
optional/相对/transitive 模块，检查当前搜索路径和所有已加载依赖子模块的真实 origin/cache；
标准库同名影子也拒绝；检查实际保留的模块／函数／类引用，不能靠恢复 module 表隐藏 shadow 对象。未锁 optional 出现不能只保持 checker 名称就认证。
Native 固定 launcher 在 calculate/jsonschema 导入前安装精确模块/origin MetaPath 门；原本不存在的
optional 仍不可用，但 date/date-time 已由冻结 profile 补齐。lazy/dynamic 中的 requests 等未绑定
导入实际触发即稳定拒绝，不将其静态存在解释为安全或支持。Host 不修改全局 sys.path/modules/hooks。
仅 pack literal policy 省去既有 report SDK 预载，普通/weekly bootstrap 仍保留；此处不扩大文件/输出权限。


仅九个明确 ID、source=builtin、全部元数据／工具／方法策略／指令／脚本／schema／golden／helper
与 curated seed 精确相同且无草稿时，允许实际闭包、锁、解释器 bytes/version/ABI/platform 全相同的
管理前缀 relocation 才可能生成新不可变版本。已启用／禁用原值保留；旧版本不写，用户 copy 不迁移。
代码、依赖或解释器变化以及未知额外文件明确 blocked；重建 pyc 即使只改变路径字节也会阻断，
不承诺任意重装自动兼容。发布新版本后旧封印继续 version_conflict，不自动发送；迁移器不写历史交接／结果／
质量归档。

B1 SPEC修波增加Dossier专用内部read adapter。只有已有snapshot的真实owner／manifest／query／provider
核验和原source授权成功后，才用Catalog事务内生成的直接old→current证书读取当前等价策略。
证书绑定每用户root、完整两端record/tree/manifest/runtime与当前实测运行环境；每次重算事实，
不是信JSON self-hash或passed。尚无receipt时由private sealed context补权威；原receipt refs先
查冲突／混合集合，不能被按ID去重吞掉。无ContextVar、无共享DataHub admission临时改写。
source-only与target均检查pack当前enabled／builtin／无draft／空bindings／未撤权，raw读回后
再检当前策略及source配置。旧8和普通源保持原三参callback；storage_read仓库查询不获豁免。

发证复用原pending→immutable publish→native activate→catalog终态save，在同一次提交中发布
证书，失败不留可用证。每个retained endpoint独立与当前target重验后才签直接证；v1→v2与
v2→v3不能拼成v1→v3。disabled／copy／代码或metadata改动／extra file／假证／跨owner／runtime
变动拒绝。历史读不执行旧runtime，不改原snapshot/query/context/receipt/质量状态；旧send/load
仍真正version_conflict，不自动重发。原NEEDS_WORK与失败证据保留在首版任务报告，当前修波
仍须独立SPEC／Python／TS复评，不将本地绿色直接称为正式研究质量通过。

输出审计独立合同为`research_pack_output_contracts_v1`，随每版resource冻结完整JSON schema。
receipt/full root/component所有必需字段、类型、版本、digest、计数、code信息、metrics、refs、
missing/rejected及限定语都由独立表检验，禁止额外字段；不从返回receipt反推required。
paired删字段并正确重hash仍拒绝；条件限定语与有限pack状态另检，输入参数投影与原完整封印
独立比对。原64KiB／16MiB／128 preview等预算不变。

`pack_catalog.py` 补九个 `pack-*` 场景；原八合同与140基线不改。准备只读；完整交接仍走原
request-key 幂等／durable intent／来源祖先保全。调用者只能选择材料身份、对象和研究范围，
不接收 records、owner、rights、provider、qualified、coverage 或 passed 声明。自然日 as_of
保持原合同；内部 instant 由显式带时区 cutoff_at 无损映射并核对上海自然日，不补午夜／收盘。
Host 通过原 `_resolve`／Snapshot read／当前 `_authorize_query(cached=True,storage_read=True)`
重验本人原件、公开副本与私有 raw 的实际 SHA／大小、来源许可和配置摘要。

当前唯一无损映射是 BaoStock 股票 daily/none 的 `daily-price`：证券来自已核 query／原行，
币种／单位来自真实 fields.close，交易状态和复权逐行核对，原 raw 的 code/date/close/
adjustflag/tradestatus 与规范行交叉读回。`retrieved_at` 仅作 observed_at，published_at 保持
null，不补历史 PIT。未知/缺 raw、语义版本、币种、单位或截止逐项拒绝；原分页完整不证明
日历／全集。真实财务披露时刻、交易时段、预期 vintage、全量风险、完整持有人等仍缺。
source_coverage 因没有可信全量范围证据保持空，不能将当前子集称为九包完整数据支持。

`inputs/scenarios/<handoff-id>/input.json` 保存完整规范输入与完整参数，另有只读 manifest。
私有 handoff 记录拥有封印／上下文／原件／代码身份；manifest 不自证权利，也不构造摘要循环。
读取、发送、Native 准入与质量均重读授权及摘要；全 blocked 或无完整可执行方法参数不发送。

`research_run_script` 的 `pack_execution` 与 code/report_plan 互斥，仅包含 capability_id、
version、context_sha256、input_manifest_sha256。guard 只读 preflight；受管工具体才通过同一
私有桥以真实 call_id 登记唯一 started。Host 分配固定 launcher、逐文件清单和本次输出根；
模型不能指定代码、输入／输出路径或通过状态。未知调用／Native 取消后的未知进程不重发，
Store 恢复后换 call_id 也不能重开同 task/context。没有新推理循环、数据库或队列。

`scenario-frozen-inputs-v1` 在 JS、Python supervisor 和固定 launcher 核对至多320个精确文件的
路径、单链接普通文件、大小、device/inode 与 SHA，并检查打开前后身份。Python importlib
仅取得这些脚本确切父目录的 literal 目录名读取，文件内容仍逐项授权，不开放整个 inputs／
capabilities 子树。普通 code/report_plan 不能读取 sealed scenario input，也不能写
`outputs/scenario-results`；受控调用只写 Host 分配的本次 execution 根，原 weekly policy 不改。

冻结 writer 仅调用 execute_pack_bundle 一次，把完整 bytes、独立 receipt 和 manifest 写入
staging，fsync／原子发布／读回，拒绝已有目标、链接及替换。输出为固定 full-result.json、
receipt.json、manifest.json；stdout 只给≤64KiB envelope，完整结果仍≤16MiB。原 atom
receipt_sha、展示投影 result_sha、实际完整文件 SHA 分开保留。Host 不使用 stdout 指定路径，
只重开自己分配的文件；独立核对规范 JSON、实际 hash/bytes、所有 root/component 行数、
输入行数、预览前缀和元数据，再登记 saved。私有完成回调来自受管 JS 的实际 supervisor 结果，
普通 HTTP／研究 Python 无控制凭据；假 stdout、预写同名文件、篡改和退出失败不能登记 saved。

schema2 沿原质量链继续区分 required/discovered/loaded、实际执行、文件保存、来源完整与报告
质量。计算的 partial/insufficient_data、来源缺口、未加载、缺文件、取消或非零退出保持
incomplete/invalid；saved 绝不改为研究 passed。纯核自身 NOT_RUN 字段不被改写。

本地验收包括真实 pinned DSH ToolRuntime、原 tool-skill／filesystem provider／guard、真实
Host 决策、默认 private-bridge 产品代码和真实 macOS Seatbelt；测试仅把 HTTP transport
用管道接到 TestClient，不模拟准入决定，不调用 LLM／供应商。256行完整子结果、真实文件与
独立摘要验证另有直接 writer／Native sandbox 测试。取消后恢复、未知不重发、跨来源撤权、
篡改、失败和旧版本保全分别测试。UI／140全执行映射、真实模型选择、真实供应商等价、正式
报告质量、常驻部署、跨平台仍是独立未完成项；本地通过不替代主控的完整 Router／独评／CI。

## C0：来源版本合同的最小增量

去重方法、research-prep与global-opinion方法版本为1.1.0；其余七包仍为1.0.0。
来源角色新增`unknown`，必须产生`source_role_unknown`缺口，输出每个版本明确保留角色；
没有把捕获到的原文等同于原创，没有推断转载时间差。既有original/reprint/translation的
数学语义保持。语言、地域和发表时刻的可信来源投影属于下一切片，本步没有来源mapper。

新资源manifest为`research_pack_code_manifest_v2`，明确绑定输出合同v2和记录合同版本2的
路径及SHA256；旧v1输出/记录合同按633原字节保存在受管包内JSON。Host从已冻结
resource manifest及file_bindings读回合同，验证closure、引用hash和封印输入；拒绝缺失
能力绑定、未知合同版本、替换schema与旧v1下的unknown角色。返回产物不能自选schema。

`fixtures/pack-633-v1/`来自633冻结package实际执行，保留package/input/execution及
原receipt/full-result/manifest和来源SHA核对；是合成资料的离线真实计算产物，未调用模型
或供应商，不是线上用户档案。旧v1可按原冻结合同只读检查，新v2须按新合同检查，彼此
不能互换。旧版本继续执行、跨语义版本迁移/只读等价均未被授权；已有prefix-relocation
政策和非pack档案门保持。新旧代码内容不同仍返回明确冲突，不伪造等价证书。

## C1/C2：静态绑定与本人原文的后端限定子集

`scenarios/execution-bindings-v1.json`逐项保留原62 Skill、78 Tool、284个原参数，绑定
固定baseline SHA；`execution_bindings.py`只读、校验闭合字段/固定主路由并按确切ID查询。
十八个九包关联有固定capability/builder身份，但不能从此表选择路径、模块、URL、Registry
或版本，也没有注册任何供应商同名alias。全部原参数当前显式unsupported，包括传None；
空参数仍拒绝未注册alias。参数required原资料不明，保持unknown，不补猜默认值。
原源与自有native的action、ready、callable、fixture/live_source、runtime、quality分别保存，
这是无会话的静态合同，动态运行真值仅来自实际Host回执，测试不把任何项升级为当前可调用。

`scenario_source_versions.py`只接受已由resolve_reference重读的本人source类型。当前
Host web reader明确拒绝超限/失败响应，将完整可读capture保存后才截断模型预览；
mapper核当前Host私有producer证明、UTF8/大小、hash/取得instant，full_text_available只表示该
冻结capture可读，始终保留upstream_completeness_unverified。旧记录、额外完整性声明、
真实落盘截断无法证明时保留false/缺口；模型返回truncated不表示落盘正文已截断。
语言/地域/原创角色固定unknown，只有自然日的发表证据保留原件定位并记缺口，不补造
发表时刻、事件时刻、转载父关系、历史PIT或国内/海外覆盖。未知类型及file别名不投影。

引用经现有workspace_material→版本化asset bundle→原source引用进入prepare，仍须显式
datahub/uploads/web三类scope；不新增八场景合同或API字段。现workbench只把source raw
复制到target的page-evidence文件，不注册target.web_evidence、也不替换原reference的sid。
因此同一原capture通过多个bundle选中时，原sid/web ID在逐ref权限/expected复验后显式
去重并记转换；同URL同hash、不同原始Host登记保持不同版本和取得时刻，字节分组不能
证明独立上游。原件更新不得替换旧sealed bytes；冻结、执行前与结果再读均重验原权限。

真实统计局正文fixture来自既有冻结归档，当前测试通过离线fetch替身走实际read_source
保存，再沿真实Host封印、DSH ToolRuntime/FileSystemSkill/guard、macOS sandbox和独立
产物读回。它证明有界后端资料链，当前上游live取数、真实模型、供应商等价和报告质量仍
NOT_RUN。source选择器及来源/结果可见的完整UI仍属C6；C3方法包、C4参数adapter、
C5真实MCP和T4/T5未被此实现完成。

## C1/C2 SPEC修复：传输完整性证明

旧c92候选只认source字段结构，不能证明HTTP传输完整，已由Content-Length100/实读5字节
的真HTTPResponse离线反例否定；旧局部测试不构成交付通过。reader现在显式核定长计数/
剩余length、stdlib chunked终止/异常及close-delimited EOF；非法/未知framing拒绝。无长度
EOF的declared_length为None，绝不捏造长度，仍不证明上游全文。大小/时间/编码原门保留。

真实worker保留版本化capture manifest，分别绑定HTTPResponse返回的响应体bytes（已由
stdlib去chunk，不含HTTP头/分块控制字节）与抽取后UTF8 bytes/hash；父端JSON解析后再
校验。Host在retention fence内exclusive/fsync私有proof后保存原文并原子发布source记录。
`capture_proof`引用从canonical source_record中排除，其他id/sid/url/时间/字段及正文hash
全部绑定，无新密钥、供应商签章或全文覆盖认证。proof在`.control/source-captures/<sid>/`，
不复制正文。新proof缺/坏、marker/字段/hash/正文改变均拒绝；旧proofless正文可读但
完整性false+gap、不回填、不重抓。内部兼容旧producer无manifest时只能明确unverified。

同SID的URL ID缓存只保存一次；proof exclusive不可覆盖。proof/index发布失败不返回
完整成功，已有私有孤儿proof阻止隐式fetch替代或降级旧缓存。权限先于用户正文读取，
普通撤权来源列表只校验metadata/privateproof并返回revoked，不打开正文。

source proof纳入原snapshot_dossiers.files，proof-only不创建Dossier DB；现multiuser
snapshot和resident @dossiers复用该结果。显式admin保全安全核对固定已证原文并只返回
SHA元数据，body-only篡改拒绝；恢复须原source记录、正文、proof原bytes一致。Store.purge
沿原引用/retention门仅删除该退休SID的proof目录。固定operator代码及SHA未改。

## SPEC二次修复：崩溃残留不降级为上传

proof之后的正文exclusive创建、写入、目录sync、读回及index发布全部进入同一异常回滚；
创建时保留文件/父目录dev+inode，即使中途抛错也只清本次同身份独立普通文件，不删已存在
或被替换对象。cleanup失败保留原异常和日志，私有proof不覆写、不自动发布或重抓。

安全性不依赖cleanup：metadata层将固定`inputs/web-24hex.txt`及原登记path识别为受管
来源，不依赖proof健康或web_evidence已发布状态。Store.files不把未发布对象自动登记/
展示为uploads；Dossier file alias与Claw generic file-copy固定拒绝受管源，须保持source
身份。Store.file_path/open_file为HTTP预览/下载和现共用消费者先核发布/当前web权限及
metadata/proof，再核实际正文hash；分类不读撤权body、不递归自身。即使旧files索引已
登记孤儿、proof缺/坏或进程崩溃，uploads-only与web-enabled均不能将未发布源当普通文件。
真实上传API的UUID前缀文件不匹配受管命名，普通上传/引用保留；已发布web源在原web权限
下HTTP/source读取保留，Dossier/source交接仍引用原sid，不建立新源身份系统。
