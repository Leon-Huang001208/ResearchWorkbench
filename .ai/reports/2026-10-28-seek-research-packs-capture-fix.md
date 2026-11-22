# C1/C2 SPEC P1修复：传输完整性与Host capture证明

base `c92bb9a582e96f81fe039b85f69b1892b28873a3`；task ID仍seek-packs-20261027-7bda5752。
宿主macOS Mac mini，Web修复；不开始C3/C6/QUALITY。无安装、来源网络、真实模型、供应商、
部署、秘密、新数据库或固定operator改动。源码仅本地提交交原SPEC复核。

## 缺陷与必要变更

SPEC实际反例：标准HTTPResponse定长read(16384)不会因提前EOF自动抛IncompleteRead；
Content-Length100只读hello5后length剩95，旧reader仍保存，字段结构被mapper误当完整证明。
c92局部PASS没有覆盖真实传输，不能作为交付通过。原review根只读，不修改或清理。

fetch_document保留有界读与原大小/时间/编码门，显式校验声明长度/累计bytes/剩余length；
提前EOF稳定research_source_incomplete，chunked实际stdlib不完整也拒绝，非法/未知framing
不猜。无长度close-delimited EOF的declared_length=None，仅证明本次协议读取结束，上游
完整性仍unverified。响应体bytes指HTTPResponse返回的传输解码后entity body，不含HTTP头
或chunk framing；与抽取后UTF8 bytes/hash分别绑定，非同一计数。

实际worker使用worker_document_bytes不删字段编码，fetch_owned_document父端解析后再次
校验版本化producer manifest。无实际公共worker运行；in-memory fake subprocess把真
HTTPResponse→真reader→实际worker JSON编码→真实父parser串起，缺manifest/错hash拒绝。
内部旧producer兼容输入没有manifest只能显式unverified，不能认证capture完整。

当前Host在retention fence中先exclusive/fsync并读回私有proof，再保存原文/原子发布source。
`.control/source-captures/<sid>/<webhash>.json`只含元数据/hash，不复制正文、无新密钥。
canonical source_record排除capture_proof引用避免循环，仍绑定schema/sid/id/url/path/
file_id/fetched_at/其他所有source字段及正文hash。mapper不再认字段数；Dossier._resolve在
当前两端鉴权及原文hash之后复验同proof，冻结/执行/结果再读/交接均过原链。
旧proofless缓存保持可读但完整性false+gap、不回填、不自动重抓；同SID URL缓存与proof
exclusive不可覆盖。新proof缺/坏、marker/正文/hash/时间改动拒绝，不降级legacy。

发布失败不会返回完整成功：私有proof先写，索引发布失败回滚record/files并移除本次
exclusive创建的正文；孤儿proof保留且在任何新fetch前使该cache unavailable，不能自动
替换或覆盖。proof写前失败而没有任何持久对象时，仅下一次显式请求可尝试首次保存。
普通撤权来源列表仅核metadata/privateproof并标revoked，不打开正文；用户正文仍先鉴权。

## 保全/恢复与删除

snapshot_dossiers schema1.files纳入source proof；proof-only不创建Dossier数据库。经批准的
显式admin保全从proof绑定的固定sid/filename安全读原文，只返回SHA元数据并验证实际正文
匹配原proof，不能把篡改值当新基线。真实multiuser.snapshot与resident.asset_index_snapshot
复用原消费者，proof缺/坏及body-only篡改均拒绝。原source记录、正文、proof原bytes共同
恢复后实际ResearchService/Dossier可读，未隐式fetch；其它source root仍可读。
Store.purge只增加该退休sid的固定proof子目录，原Dossier/handoff引用围栏和retention门先行；
其他sid数据保持。固定operator源码及SHA不改。旧proofless仅沿原保全范围，不能冒领新保护。

## 实测而非推断

- 全部新HTTP响应由same-process thin fetch_owned_document→真实fetch_document和标准库
  HTTPResponse处理，PublicConnection提供内存socket；socket/HTTP外连guard始终生效。
- RED：7 failed/2 passed，16.00s，真实100/5提前EOF、缺proof与非法CL；原stdlib两种
  incomplete chunked本已拒绝。`capture-red.log`。
- 初始GREEN：9 passed，15.44s；`capture-green-initial.log`。
- 第一邻近：50 passed、14 deselected、1 fixture failed，108.36s。失败为恢复目的误放在
  原Store子目录导致copytree递归，不是产品门失败；日志/receipt保留。恢复目的已改同opaque
  basetemp的sibling并机械拒绝dest==source或dest.is_relative_to(source)。第二次fixture
  .control默认755被私有门正确拒绝；恢复原700后单例1 passed/8.71s。
- 私有目录恢复/原始source index+body+proof、两真实consumer、仅正文篡改、缺坏proof、
  atomic publish失败、IPC producer保留/校验、老source质量和既有保全邻近：最终25 passed，
  19.64s，log SHA `5ff60354a7b2663de13aa2d858a1ffeafa1569f876629ab8c19d0635bcbe8595`。
  没有机械重跑此前50项。
- 格式后最终两真DSH ToolRuntime/Skill/guard→sandbox→Host独立读回，加核心提前EOF/
  三framing完整producer，共6 passed，55.79s；log SHA
  `15e283a68f7d787b87146309cc8b89af260f56335f36ee43963ebdd0d787e110`。
  final-native-proof-receipt逐9文件绑定SHA且source_unchanged_after_run=true。
- Ruff、Black八文件、isort、pyindex生成/check、diff check通过；首轮ruff异常类型/导入
  预检失败保留，修复后通过。Mypy本slice NOT_RUN，仍无安装或绕过已有缺librt状态。

测试时间已跨上海午夜：task/日志目录继续起始27不改。仅offline_http fixture冻结Host
capture clock为明确模拟2026-10-28 UTC instant（每登记微秒递增），as_of从捕获instant的
Asia/Shanghai日派生；producer/proof不另造一个issued_at。历史/future反例保留，生产时间/
日期/cutoff没有放宽。模拟捕获时点不是本轮实时上游取数证据。
真实Native例仍各自Darwin marker；portable reader/producer/资格/保全用例没有整体skip。

## 范围与剩余

kernel/旧八合同/Native输出/18比较门/140参数alias合同不变；source_coverage、语言/地域/
发表时刻/原创角色未知继续保留。上游完整性/全网覆盖、live-source、真实模型/供应商、
正式研究质量、部署、跨平台仍NOT_RUN。完整总清单/全7模块文档/API atlas、完整Router/
同候选Mac干净安装与CI仍由root统一，本修复不称完整性总门通过。
原SPEC→QUALITY仍待当前固定候选。必要原件和失败日志在
`logs/research-packs-capturefix-20261027/`，不删除或修改review保护根。

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"The fix binds existing Host web captures to bounded HTTP producer evidence and existing frozen Native input paths; no public API, engine, service or database is added.","diagrams":[]} -->
<!-- architecture-review {"group":"dossiers","structure":"unchanged","reason":"The existing Dossier read and retention fence now verify immutable capture metadata and original-body digests through their existing preservation consumers; fixed operator code remains unchanged.","diagrams":[]} -->

## 本人资源收尾

7个本轮opaque根在owner/PID/UID、dev/inode、无open复查后，将177份必要索引/source正文/
proof/Native产物/transcript归档并hash读回，回收1,499,103,735字节；
`capture-owned-closeout.json`保留原路径与逐归档/原件hash。误递归复制的失败子树此前另以
明确inode/owner和3份原始index/body/proof读回归档后移除19,365个再生重复文件，回收
597,621,782字节；restore-fixture-failure-cleanup.json单列，未归档递归副本。
没有清理review保护根、旧50、其他任务或worktree/Docker/常驻；这不代表全任务cleaned。
