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
