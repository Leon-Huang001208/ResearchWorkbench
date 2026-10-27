# T3-A 研究组合包确定性内核

任务 seek-packs-20261027-7bda5752；macOS Mac mini，Web功能开发。
基线 1317968ea7e5e7227adbe9451882b381307438c2；独立受管 worktree 的本地子任务，
主控负责后续SPEC/PythonQUALITY、接线、完整Router、通用CI、同候选Mac安装及远端交付。
本报告不表示九包整体、62Skill/78Tool、真实研究或跨平台完成。

## 改动

新增 scenarios/packs 单一权威纯计算包：严格规范记录、稳定PackError、有限数/时区/日期/
输入输出预算、六个独立公开方法、三个限定计数/披露方法与九包组合。
JSON schema冻结自已读v2规格，22合成向量标synthetic-test-only/authority=none；
并非Host资格或生产provider mapping。risk字符串complete明确拒绝，另有完整范围声明测试。

仓位校验保留未知权重；风险固定risk/unlock/insider与规范证券/闭区间join；原件hash去重和
同URL新hash版本/UTC时间线；披露前最新独立共识系列的标量/区间差；正PE经验分位ties区间；
公告相对显式交易所收盘的交易日定位、价格单位/复权/日期/停牌/未来价格覆盖。
另实现同日同universe计数比例、分期持股/float/显式互斥子集合合计与变化、最新财报计划/实际披露进度。

结果总含host_qualification=NOT_RUN、research_quality=NOT_RUN、method_source_binding=host_required。
六原子可计算complete；九包现阶段保守partial/insufficient_data且明确限定scope。
风险范围、股东互斥和包source_coverage全是声明，不能认证已核实无风险或合法全市场覆盖。
旧event收益/基金穿透/财报monitor继续blocked_components，没有复制或import原18算法。

输入SHA、完整参数集合SHA/count、scalar参数、来源locator、处理/投影计数和结果SHA均保留。
列表参数摘要避免把1000证券universe塞进64KiB结果，但不能独立重建输入；B必须冻结原始完整输入。
不读写文件/网络/权限/数据库，不注册Skill/Tool，不建执行器，不执行DSH/模型/供应商。

## 实际验证

TDD证据日志位于该worktree logs/：
- research-packs-red.log：缺API ImportError，符合初始不存在实现的RED。
- research-packs-red2.log：4个新增receipt/持股合计/同日未来close/batch预算失败；之后补实现。
- research-packs-red3.log：空源complete误报与预分配系列预算两项失败；之后补实现。
- research-packs-red4.log：空事件完整范围组合与严格instant三项失败；之后补实现。
- 最终 research-packs-final.log：72 passed in 0.34s。
- 最终日志SHA256 c5b6faf6ac5a3cd14fb0b4d0c38831baca4acb5d39112cb20878a3526943df6e。
- test receipt: logs/research-packs-test-receipt.json；runner PID41586、pytest PID41587、UID501。
- basetemp /var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-seek-packs-7bda5752-6qfnx6iz；
  归属与非symlink复核后，仅本树已清理。

命令：已批准生产venv Python执行 `-m pytest --confcutdir=tests/research_web
 tests/research_web/test_research_pack_calculations.py tests/research_web/test_research_pack_contracts.py
 --basetemp=<上述新opaque路径> -q`，PYTHONDONTWRITEBYTECODE=1；pytest使用主控给定已有uv缓存。
未安装依赖。Black/isort初次给定缓存缺模块，查明并改用已有缓存FQQ72jBxaQcBTJLL、
fu_DcTWXLXpDLR60及既有mypy_extensions/pathspec/pytokens/platformdirs缓存；不修改环境或锁文件。
最终 scoped `ruff check`、`black --check`、`isort --check-only`均通过；7个Python文件。

测试覆盖22设计向量（risk两个旧声明负例）、手算、同URL新hash、未知/未来披露、证券/期间/
口径/币种/单位错配、零负基数、重复仓位/日期、PE ties/不足、风险缺类别/完整空查询、
未知字段/自报rights、NaN/Inf、1000仓位尾行影响指标与128投影、50001总行拒绝、系列预分配、
完整missing清单64KiB拒绝、九包实际子计算与旧门。
64MiB输入/16MiB完整派生rows硬上限存在；没有另做这两个大内存等号/+1压力测试。

## 尚未执行和交接

- Root须完成独立SPEC/PythonQUALITY、模块图文与安装合同核对、完整changed-set Router、通用CI和同候选Mac安装。
- B须将public subject/date显式适配到规范security/instant；真实Snapshot bytes/hash/locator/
  权限/用途/撤权/PIT/逐method provider及单位核对；不得把纯输出和caller声明当Host通过。
- Native必须冻结整套权威源码/schema/版本并绑定真实代码hash；历史版本禁止动态import可变Host。
- DSH/Native/UI接线、真实模型、真实供应商与比较回执、原件权限、报告质量、浏览器、常驻更新均NOT_RUN。
- Windows/Linux适配、真机和同平台CI保持NOT_RUN交接。
- 不能因为本层72测试或卡片存在，宣称九包整体或全部140项完成。没有push、PR、merge、部署、新依赖或业务数据操作。

## SPEC round1：5 Important修复（2026-10-27）

在初始8c1ac39上接受全部5项发现，没有改变Host/Native接口、原18算法门、来源资格或九包范围。
先新增12个参数化回归，`logs/research-packs-spec-r1-red.log`实际12 failed（36 deselected）：
1. 持仓包风险positions严格与完整expected_universe相等；删空、缺失仓位、未知权重证券遗漏均
   risk_universe_mismatch；不能靠四份exhaustive声明减少待核风险证券。
2. 预期差先用financial-key时点索引和bisect计数派生结果/拒绝项，50,000派生基数门在展开前执行。
   DerivedBudget生成中对保留结果/拒绝/缺口共用16MiB字节账，超过即workload_too_large无截断成功。
   50输入→625结果的小预算哨兵证明基数拒绝时没有执行算术；512-byte哨兵证明中途及时停止。
3. 持股期间严格YYYYQ1–Q4或YYYYFY，按实际时间排序；未知格式、Q0及同截止Q4/FY歧义拒绝。
   不再使用caller列表顺序计算反向变化，且不跨缺失的请求中间期间。
4. 每个已知证券/holder及声明holder的全部请求期都要检查；缺披露明确holder_period_missing、partial，
   不补0、不造缺期持有行。缺期网格也在分配交叉集合前检查基数、逐项登记缺口字节。
5. 全部financial-key/series/vintage先验值一致性，旧vintage冲突不再被更新合法vintage掩盖。

旧72断言和22向量保留不动；新增12项后聚焦84 passed。
最终相邻回归实际命令为相同已批准venv、PYTHONDONTWRITEBYTECODE=1和已有pytest缓存执行：
`python -m pytest --confcutdir=tests/research_web tests/research_web/test_research_pack_contracts.py
 tests/research_web/test_research_pack_calculations.py tests/research_web/test_cpu_budget.py
 tests/research_web/test_research_scenarios_catalog.py tests/research_web/test_scenario_handoffs.py
 --basetemp=<下述新opaque目录> -q`。
最终137 passed、16 subtests passed、1现有Starlette/anyio DeprecationWarning，32.61s。
scoped Ruff、Black --check、isort --check-only及git diff --check均通过。

最终日志 `logs/research-packs-spec-r1-verified.log`，SHA256
`8c881e84e2c9c3736dcee175dd240e95a47102fdb8f9df1be372d73f3c22dd84`；
`logs/research-packs-spec-r1-verified-receipt.json`保存完整命令、runner PID65196、pytest PID65197、UID501。
临时目录 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-packs-spec-r1-verified-7bda5752-4ft9l43s`，
因相邻场景夹具冻结目录为只读，逐目录验证本UID/非symlink后仅加本树owner权限并清理，receipt cleaned=true。
此前相同137项首次通过后rmtree遭只读目录PermissionError，已如实保留初次日志；本任务精确临时树在
cleanup PID64260复查归属并恢复owner目录权限后清理，见research-packs-spec-r1-cleanup-recovery.json。
为补齐运行PID与成功清理回执，才执行上述最终一次相邻回归；未缩减测试或省略错误。

本轮仍未执行CI/Mac安装、Host/Native/UI/DSH、真实模型/供应商/PIT/质量/部署；其他平台NOT_RUN。
16MiB哨兵验证的是提前累计机制；没有生成625万行或做真实16MiB等号/+1大内存压力。

## Python QUALITY fix wave2：2项修复（2026-10-27）

接受HIGH财报日历单序列预算/O(n²)与MEDIUM UTC转换溢出两项，不改已Approved的SPEC五项。
新增7 case，先运行 `test_research_pack_contracts.py -k test_quality_`：
`logs/research-packs-quality-w2-red.log`记录4 failed、3 passed、48 deselected（2.24s）。
真实失败为5001计划仍complete、300版本比较计数超线性上限，以及UTC日期上下界裸OverflowError；
5000通过、两个合法2501序列合计5002通过、同序列重复版本拒绝三项原行为保留。

实现：report-calendar先按规范security/report_period遍历计数≤5000再选最新计划/建立history，
每序列set检查plan_version重复，expected universe membership亦用set，处理从历史扫描二次方
恢复到线性；不同series合计沿原50000总输入门，不以5000总量误伤。instant解析和astimezone(UTC)
共同捕获ValueError/OverflowError，稳定instant_invalid；PackError原码、严格时区格式与naive拒绝保持。
模块文档明确exchange-session与report-calendar每series的不同预算范围。

原84测试保持，新增7后的91聚焦包含在目标+相邻最终回归：144 passed、16 subtests passed、
1原Starlette/anyio DeprecationWarning，33.45s。scoped Ruff、Black --check、isort --check-only、
git diff --check通过，未安装依赖。
实际命令沿上一波的相同五个测试文件、已批准venv/pytest缓存/PYTHONDONTWRITEBYTECODE=1，
仍使用 `--confcutdir=tests/research_web` 与新opaque `--basetemp`；完整argv保存在receipt中。
`logs/research-packs-quality-w2-verified.log` SHA256
`d0959329fd6f87d84a2acb48f5e2aefb1a63231204e7f1bec310d8e2cd8c27ab`。
`logs/research-packs-quality-w2-verified-receipt.json`：runner PID82061、pytest PID82062、UID501。
本任务精确临时树 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-packs-quality-w2-verified-7bda5752-ml8km5o0`
在进程终止后逐目录复核UID与非symlink，仅调整本树owner目录权限，已清理，cleaned=true。

本轮无push、Host/Native/UI接口变动、模型/供应商/业务数据/部署；CI/Mac安装和真实来源/质量仍NOT_RUN。
等待Root对新scope commit做Python QUALITY复评，不能将测试通过称为九包整体完成。

## A2：IO-free完整制品接口（基于双Approved 4f357f2）

新增execute_atom_bundle/execute_pack_bundle与frozen ExecutionBundle/FullResultArtifact；
四个入口共用私有_calculate_atom/_calculate_pack，一次registered方法调用捕获投影前完整rows，
没有重算、复制算法、旧18调用或全局缓存。旧公开接口仍返回dict且保留原receipt digest语义。
包完整制品root.rows采用component_id引用，components包含各方法的全部rows/metrics/缺口/拒绝/
source_refs、参数摘要、输入digest、NOT_RUN与明确计数；不会从128投影补行。
完整canonical bytes为UTF-8/有限数/sort_keys/紧凑JSON，schema research_pack_full_result_v1，
实际bytes计算sha256/byte_count，descriptor保存根和各component输出行数。

full artifact总16MiB含完整root/components/metadata；每个component入闭包前累计全量字节，
最终整个payload再核预算。原派生基数/生成中字节/输入及series门保留。receipt仅rows可自适应
128→64→...→0以守64KiB，真实total/inline/omitted不变；missing/rejected/source_refs/metrics不删。
metadata自身超64KiB仍拒绝。immutable artifact不含caller records引用，不写文件/不输出结果stdout，
不接受路径、sink、passed、owner或rights。日志只计数/bytes/hash。

full input_digest_kind明确normalized_canonical_json_v1；其SHA仅对规范内存输入，不是Host原件或
未来封印文件SHA。旧receipt输入摘要另保留legacy_normalized_input_sha256，receipt_sha256单独引用。
code_version保留method_version/source_binding=host_required，实际source_sha256和frozen_resource_version
为null，留B绑定可信实际资源闭包；不自造已发布代码证明，不提升资格或质量。完整输入仍须独立封印保存。

TDD：logs/research-packs-a2-red.log实际8 failed（缺新增接口）；后续捕获全量测试首次98通过、
1失败源于测试fixture首个事件本为unlock而测试误写risk索引，核实原JSON后将期望定位到正确的
unlock行，不改变原事件/算法/golden。原91断言不删改，A2新增11项，总聚焦102项。
覆盖1000仓位尾项、128/872投影，包130仓位/390风险完整组件及根2行计数、每method spy恰一次，
实际bytes/hash/canonical一致、immutable bytes、各child独立可用而整体超预算拒绝、完整artifact
阈值等号/减1、>64KiB单行0预览且完整行保存、缺失/拒绝/source refs不丢、旧facade一致、
canonical输入顺序不变性、非有限数/小输入阈值拒绝、不可信权限字段拒绝。

最终同既有venv/pytest缓存/PYTHONDONTWRITEBYTECODE=1执行目标及相邻五文件：
`python -m pytest --confcutdir=tests/research_web tests/research_web/test_research_pack_contracts.py
 tests/research_web/test_research_pack_calculations.py tests/research_web/test_cpu_budget.py
 tests/research_web/test_research_scenarios_catalog.py tests/research_web/test_scenario_handoffs.py
 --basetemp=<新opaque目录> -q`。
155 passed、16 subtests、1原Starlette/anyio弃用warning，33.54s；Ruff、Black --check、
isort --check-only及git diff --check通过，8个Python文件。未安装新依赖。
日志logs/research-packs-a2-verified.log SHA256
`1722ebb22e645e177c94c30e87733cd944a83cec89f8a1c63153faddd43ebb35`。
receipt logs/research-packs-a2-verified-receipt.json记录完整argv/runner PID4219/pytest PID4220/UID501。
精确tempRoot `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-packs-a2-verified-7bda5752-mu9s5c5s`
已在子进程终止后验证本UID/非symlink，仅调整本树owner目录权限并清理，cleaned=true。

64MiB输入/16MiB真实大内存等号/+1压力仍NOT_RUN；受控小阈值覆盖实际预算路径。
B的versioned staging/fsync/atomic publish、Host实际文件读回/hash/schema/count登记、Native运行、
DSH/UI、CI/Mac安装、模型/供应商/真实来源/PIT/报告质量与部署均未执行。A2待独立SPEC/Python
增量审查；不表示B或九包整体已完成，不push。

## A2 SPEC fix1 / overall wave3：组件审计元数据不可裁

接受1e6b39的Important：原pack把整个child receipt当root.rows预览裁掉，可能丢组件审计。
先新增真实RED：logs/research-packs-a2fix1-red.log实际2 failed（66 deselected，0.39s）。
第一例两仓位/三个风险事件，每记录四locator字段4050字符，各atom单独合法，组合旧路径却漏掉
risk方法；第二例calendar history约40KB、forecast IDs约50KB的合法child预览，旧包只保留一个component。

修复后pack root.rows的全部component审计wrapper固定，不可删减（root omitted=0）；仅各child内部
result.rows可降至0。method/version、metrics、参数/输入摘要、source_refs、missing/rejected等均保留；
固定metadata合计仍>64KiB直接workload_too_large，不引入metadata单独artifact，也不以fullartifact替代审计。
wrapper.receipt_sha256固定绑定原atom receipt并对应full.component.receipt_sha256；
wrapper.result.result_sha256对实际展示的child投影重新计算，避免改变rows后继续冒用原hash。
一次计算、完整制品所有组件/行数/hash/bytes与组合16MiB预算未改变，NOT_RUN/旧18门保持。

旧102聚焦断言保留，新增两项验证metadata overflow明确拒绝、所有component metadata在0行预览时
仍逐字段存在、原/展示两种hash各自绑定正确、full rows不丢。最终同venv/既有缓存、
PYTHONDONTWRITEBYTECODE=1和前述相同五测试文件及--confcutdir=tests/research_web执行：
157 passed、16 subtests passed、1原Starlette/anyio warning，37.72s。
Ruff、Black --check、isort --check-only、git diff --check通过，未装依赖。
日志logs/research-packs-a2fix1-verified.log SHA256
`78a3c7d869c6509160fa8d6026028cb39d51a31b598813942e3ae8b3e9eb9442`。
receipt logs/research-packs-a2fix1-verified-receipt.json保留完整argv/runner PID32303/pytest PID32304/UID501。
精确tempRoot `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-packs-a2fix1-verified-7bda5752-q8ii7698`
在子进程结束后逐目录核实owner/非symlink，仅调整本任务树owner目录权限并清理，cleaned=true。

待SPEC/Python QUALITY复评；无push、Host/UI/Native接线、外部模型/供应商/业务数据/部署操作。
其他NOT_RUN边界和完整制品消费/Host真实读回资格保持，不表示B或整批完成。
