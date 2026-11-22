# T3-B1 Native／Host 后端候选：NEEDS_WORK

任务 `seek-packs-20261027-7bda5752`；macOS Mac mini，Web功能开发；隔离worktree。
本次消费基线为已独立SPEC／Python QUALITY批准的纯核
`a6cffb9af5fbc5300a5e69e7e4aeb10cbed455fb`；任务集成基线`1317968e`。
仅本地scope commit交root评审，不push／merge／部署，不操作常驻服务。

## 必须补完的阻断

**B1未闭合：合法运行前缀relocation后的历史只读等价授权尚未实现。**
已观测旧handoff引用在新version激活后经Dossier目标DataAdmission触发linked_version_conflict，
被包装为dossier_evidence_missing。原FAIL保留于归档日志，不将后来仅验证原字节／状态不变的
断言称为只读修复。root要求后续SPEC设计仅九个新pack的read-operation／受审old→new等价
证书；真实来源当前授权/hash、active disabled、代码变化及旧version执行门不得放松。

为避免当前候选隐式破坏旧研究，生产自动relocation一律
`pack_runtime_read_equivalence_pending`，不创建新version，不改原enabled/disabled/native投影。
没有用户设置／API可开启；单元测试override私有未实现门只证明不可变发布机制。
原八场景／通用DataHub gate未为抢绿修改。

独立SPEC、Python／TS QUALITY、完整changed-set Router／通用CI／同候选Mac干净安装仍交root；
本报告及局部测试通过不表示B1研究质量、九包完整来源、UI／140完整映射或整批完成。

## 当前代码

- 九个`research-pack-*`新增Native资源，精确复制六个纯核Python、合成向量、记录schema，
  加固定entry／writer／显式stdlib logger adapter。逐文件hash及closure绑定；不修改A6纯核、
  baseline.json／contracts.json，不引入第二引擎，不解锁原18receipt-gated算法。
- Catalog仅支持有限scripts模块树，相对import需在清单解析；pack禁止动态import／执行、
  任意Host/app／非白名单第三方。copy清审查hash、版本发布／旧用户版本保全沿原链。
- Host资格器复用真实`_resolve`／Snapshots／`_authorize_query(storage_read=True)`及私有raw
  字节检查；唯一当前无损子集是BaoStock daily/none→daily-price。逐行原始code/date/close/
  adjustflag/tradestatus交叉验证；币种单位来自fields，证券大小写按明确合同无损规范化。
  observed取实际retrieved_at；published保持null；不补披露时刻／PIT／市场全集。
- 其他kind/provider／财务时刻／日历open-close／历史预期／完整risk等明确gap。caller只选材料
  ID和研究范围，不收records/owner/rights/provider/qualified/passed/coverage；category_coverage
  不能自报。自然日不改，cutoff_at须显式时区且匹配上海自然日，完整参数／原始规范输入封印。
- `pack-*`九合同分支与只读prepare API沿原hand-off幂等／祖先保全。输入写只读普通文件，
  private handoff是authority，无hash自循环；读／send／Native／quality重验。全blocked／缺完整
  方法参数、直接选pack却无seal均在模型RPC前拒绝。seal IO失败保留已创建sid和原key，只观察。
- `research_run_script.pack_execution`与code/report_plan互斥。guard仅纯preflight，实际工具体
  唯一pack_start登记真实call/task/context/input/closure，输出根／固定launcher由Host生成。
  受管JS实际supervisor完成经原private bridge回报；普通HTTP／Python无控制凭据。
- `scenario-frozen-inputs-v1`三方逐文件path/hash/size/inode复验，原320上限不增。拒链接、越界、
  替换及未列文件，importlib只读确切脚本目录名，不授予内容子树。普通脚本不能读sealed输入
  或写受管pack输出根；weekly原策略不改。
- 单次bundle写full-result／receipt／manifest，fsync／原子发布／读回；stdout≤64KiB并有真实
  相对artifact路径，full≤16MiB，原128 preview／50k输入等门保持。Host独立计数全部component、
  原始输入、参数摘要、preview和实际file hashes；存实际Native value／rendered内容及hash。
  文件saved与计算partial／来源不全／研究质量分别记录，schema2沿原质量核验强制不足或无效。
- 运行指纹v2独立枚举六个已知import/data roots与非账簿版本metadata，包含pyc／未列RECORD
  的新代码。仅排未执行console和固定4安装账簿；排除项／原因冻结，METADATA/WHEEL保留。
  外部pycache prefix／symlink／越界／假metadata拒绝。pyc重建会阻断，未承诺所有重装可迁移。
  当前prefix迁移mechanics严格比较全部curated用户可改内容、6闭包、锁、解释器bytes/version/
  ABI/platform；生产read-equivalence门恒关闭。
- 包内`pack-runtime-lock.json`是现有whole web.lock SHA＋6精确version受测投影，无新依赖；
  真wheel包含JSON，installed-like进程从candidate app/core/runtimes加载，不依赖requirements
  checkout。原setup入口／lock／pyproject／CI无需改变，但干净Mac CI仍NOT_RUN。

## 真实执行边界

无真实LLM、供应商查询、MCP安装／付费、个人profile、常驻服务或业务数据操作。
actual DSH测试使用pinned7ec的真实Cordis ToolRuntime、filesystem Skill provider、原tool-skill、
产品guard／research_run_script／默认private bridge代码及真实macOS Seatbelt。
只有HTTP transport用管道接TestClient；Host决策、账号snapshot读／hash／权限／seal／实际
supervisor／文件读回均真实。会话图／session.prompt为离线fixture，不证明生产模型选择工具、
子Agent推理或生产网络可用；`model_tools_verified`只用了真实静态pin＋flash白名单，未mock提升。
真实Native value/content与私有回执rendered hash对比，并保存脱敏transcript。

256行完整子结果经writer和Host独立artifact reader核对，计数／尾行／完整hash保留；负例在改
文件并重算文件hash后仍因真实counts不符拒绝。真实Native取消后未saved，恢复Store换call仍
unknown_do_not_retry。Fake stdout／预写同名文件／输出篡改／非0退出／撤权均不能成为完成证明。

## 验证与事实保留

最终local receipt／逐argv、PID/UID、duration、log SHA及自有temp清理状态见
`logs/research-packs-b1-20261027-7bda5752/final-python-receipt.json`；最终结果追加于下方。

前轮实际结果（不是全部绑定最终source）：
- 近新链20 PASS；随后Host／实际Native／取消等8 PASS。
- 旧sandbox／scenario／catalog：80 PASS、1原skip、16 subtests、1原Starlette warning，74.11s。
- 旧compatibility 97项初次93 PASS／4 FAIL，248.51s。前2是新增9 seed的精确name／26+9 snapshot
  断言；后2fixture只patch catalog，但实际query gate用admission_catalog。相同严格离线fixture
  加在真实调用路径；生产`_data_query_admission`／data_readiness／admission_catalog三函数AST与
  a6完全一致。四项定点修后4 PASS，11.31s；未将AST证明冒充已执行完整a6基线。
- 近JS 37 PASS（含pinned schema），145.44ms。
- runtime closure 7个正反例＋2身份检查9 PASS；原wheel内容／无checkout加载3 PASS。
- relocation初次14 FAIL/1旧copy不迁移PASS；mechanics 15 PASS。增加默认安全阻断后17 PASS，
  49.13s；其中发布正例明确fixture override未实现只读门，不是生产只读迁移通过。
- 历史只读旧FAIL真实保留：post-relocation.log 1 FAIL/20 PASS/1 skip，61.91s。
  后续“记录字节不变／执行冲突”只证明保全，不替代历史读取验收。
- Ruff／Black／isort／pyindex有实际检查。Mypy在现Web venv不存在，既有缓存mypy因缺librt无法
  启动；未安装，记NOT_RUN，不宣称零type errors。

Windows/Linux原生、Mac Docker、浏览器／UI、140项完整execution mapping、真实源等价／历史PIT、
真实模型质量、正式报告质量、常驻部署、远端CI均NOT_RUN或待root后续，不作为本候选通过声明。

## 资源

仅本任务opaque pytest目录／test wheel／脱敏日志与产物。最终runner记录本人PID/UID，结束后
先归档hash核对再只调整本人owner目录权限并清理本人temp；未触碰业务会话、报告／凭据、原外盘、
驻留服务、Docker、未知归属文件或其他任务worktree。review worktree／日志保留给root，整任务
不标cleaned。此前未带PID的探索run仍如实保留log，不伪造receipt；收尾清单另归档。

## 最终本地验证（候选仍NEEDS_WORK）

最终Python总检：**249 passed、16 subtests passed、1原Starlette/anyio warning**，248.40s；
runner PID89079／pytest PID89081／UID501。runner实测248.665s，exit0；完整argv/env在receipt。
日志SHA256 `9bdb7f7cca39d5805aac906a68557e00b50e2f195581cb300f8e5e874c6ad42b`。
前次同闭包3FAIL/246PASS的日志与receipt另存attempt1，没有覆盖。3FAIL后两项修测试定位实际
manifest原件；另一项补真实pinned ask-user注册后暴露目录漏Native既有as_of/purpose/quality，
最小同步真实公共schema投影；不改Broker/PIT授权。已分别定点复核，再完整249通过。

最终JS **37 passed**／132.27ms；最新真实wheel再构建与installed-like独立复核 **3 passed**。
Ruff、29文件Black check、isort check-only、pyindex check及git diff --check实际通过。
纯核目录及baseline/contracts相对a6字节diff为空。精确source／wheel hashes见
`verification-source-manifest.json`，后续若代码变化须重新绑定相关验证。

最终验证opaque temp在归档10份Native transcript／结果fixture并重新核hash后，由原runner
逐owner目录检查清理，temp_cleaned=true。较早探索目录／首次失败opaque目录保留：
**50个、6,535,829,787 bytes，cleanup blocked**；只读lsof占用核验不可用，未强删／未终止
未知进程。详见`exploration-temp-cleanup-blocked.json`。61份探索日志／proof已归档并核hash。
本地wheel、review worktree与必要日志保留给root；不把局部验收通过代替整任务资源cleaned。

唯一仍需SPEC必须修复的功能阻断是历史等价只读证书／read-operation边界；当前生产auto迁移
严格blocked，其机制单测与保全正例不构成历史读取通过。所有前述模型／供应商／UI／140映射／
跨平台／CI／部署NOT_RUN边界保持。此scope commit只供独立SPEC→Python／TS QUALITY评审。
