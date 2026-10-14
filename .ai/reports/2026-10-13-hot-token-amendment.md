# 原scope token修订与Native资料读取修复

macOS功能开发，隔离continuation worktree；父候选961177ed。用户批准两token上限100k，
调用次数20/USD1保持。迁移18只追加operation允许值，不改旧迁移checksum。
本地model-amend-tokens具备停机/Owner/同实例/明确授权/已有scope/单调增加/UUID重放/不可变审计。
核对安装依赖：无新Python/Node依赖，无launcher、固定DSH或安装协议变更；安装CI仍NOT_RUN。

原库停机备份15→17→18。原scope修订前4/1417/659microUSD；研究2五次真实模型回执后
9/41444/4160microUSD。第六次保守预留越100k，failed/incomplete，无报告。严格不重试或增额。
模型使用原主实例系统凭据引用，隔离Store/Runtime；控制-only PG不是正常安装服务验收。

脚本未获Hot快照读取准入导致多次工具失败，现按本会话run/instance/hash及完整bundle校验，
限定只读dataset。正常capability准入不变；改后原session Seatbelt真实读取PASS，无付费。
性能审查指出逐对象self.read重复全档hash，已改一次detail与安全FD读取，反例补齐并复核关闭。

实际检查：PG model-control.integration 1 PASS；Python关联64 PASS+6subtests，最终目标
15 PASS+6subtests；TS typecheck审查PASS、Python限定审查PASS。whitespace及治理另见最终日志。
Ruff/Black/isort未获安装授权，NOT_RUN。其它Goal完整交付门保留；无远端发布、CI或生产部署。

证据（logs/hot-resume）：goal-token-amend-receipt.json、original-study-migration-receipt.json、
native-study-2-result.json、native-study-2-failure-reconciled.json、native-snapshot-admission-proof.json、
token-amend-python.log、token-amend-python-final.log。秘密不在报告中；备份是行政快照，不认证联合恢复。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"现有预算管理与不可变审计新增token-only修订，冻结快照读取在现有Native脚本准入内，服务/队列/研究引擎及数据流不增；真实研究仍未生成报告。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅Native CLI管理及Host既有只读快照准入，无运行时拓扑或Docker/安装/凭据机制变更。","diagrams":[]} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "现有Host/会话快照只读准入增加所属Hot证据校验，原API/Provider/安全沙箱与组件关系不增；不认证报告生成。", "diagrams": []} -->

<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "现有Host/会话快照只读准入增加所属Hot证据校验，原API/Provider/安全沙箱与组件关系不增；不认证报告生成。", "diagrams": []} -->

<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"仅Hot冻结FinGPT会话选择同DSH的新轻量preset；Automation的调度/研究发送/恢复流程不变。","diagrams":[]} -->

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"在现有同DSH preset registry增加冻结FinGPT的本地composition，复用原脚本/文档工具、全局guard和预算流桥；不新增Runtime进程、调度器或执行器，普通研究及Claw保留原组合。","diagrams":[]} -->

2026-10-14续跑：143 runtime/Hot恢复PASS，helper4 PASS，必需Python525 PASS/1skip，
治理110 PASS。read_hot_evidence的UTF8/总字节边界补齐并复核关闭。
真实报告MD已核验、DOCX确定性转换重开PASS；delivery completed而Native预算收尾failed保留。
原scope累计17calls/76804tokens/10253microUSD；20/100k/USD1不变，无额外授权。
PG停机后恢复同容器卷，loopback新58154；控制/Native均停，PGpaused/角色NOLOGIN。
10-14价目已查官方原页，仍保守峰值记账，不能当厂商账单。全Goal剩余门见权威进度。

最终全41路径检查：项目约束、架构治理、文档治理、生成索引、whitespace和TS typecheck PASS。
初次文档CLI误传不支持的changed-file参数已纠正并按其全库模式通过，没有忽略失败。
所需远端CI及Mac干净安装保持NOT_RUN，mergeReady=false；本轮仅本地可审查提交。
