# 研究组合包纯计算内核 v1

macOS / Mac mini 的 Web 功能开发，T3-A 限于 `scenarios/packs/`。
这是九包的限定确定性内核，尚未接 Host、Native Skill、DSH 或 UI；不是全部
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
