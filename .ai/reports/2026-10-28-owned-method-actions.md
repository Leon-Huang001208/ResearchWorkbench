# C3/C4 自有方法动作切片

宿主：Mac mini / macOS；任务：Web 功能开发。工作区基线
`397365b1c565636eb1b8c9955efecad5d18d627d`，沿主任务已启动 Harness，不重复初始化。

已实现三份 `kind=skill` 版本化方法包、冻结 stdlib 原件动作、严格 query/limit 与问题预置适配。
没有增加模型循环、引擎、供应商调用、依赖、秘密、部署或 schema 数据库迁移。

RED：新增参数测试先因模块缺失失败，证据 `/tmp/rwb-c3-actions-3V1xlNQt/red.log`。
首轮 GREEN：参数/原件 32 tests PASS，Catalog/冻结脚本 3 tests PASS，证据同目录
`green.log`、`packages.log`。该目录已登记 owner.json。
后续当前纯模块目标集 `target3.log`：43 tests PASS；Ruff、Black、isort 对本切片 Python 文件通过。
实际重开三份已有官方摘录的原 SHA（MSFT income/cashflows、FOMC September），不等于新抓取、完整文档
或 live 来源证明。未执行 mypy（现成环境 librt 不可用），不安装依赖补门。

## 当前集成切片

主任务已批准并实现固定三 CID 的 `method_execution={capability_id,version,context_sha256}`。
三份独立 owned-method 场景沿原 prepare/handoff/send/选材链运行，原八合同字节不变；来源选择使用
固定 registry 区分旧两 pack 与三方法，不产生伪 pack_seal、pack 资格或执行记录。

`scenario_method_sources.py` 从当前授权原件冻结 inputs/methods 私有副本，Host 固定 launcher、
真实 Native supervisor 与原私有桥 `kind=owned-method` 完成后，Host 重新授权、核文件身份、重读
原件与 ledger，并用已验证与冻结资源同字节的固定函数复算，再写原 receipts/index.json 的
method_executions.saved。普通 code 不能读内部原件或写 method-results，不能自造 ran。

私有输入明确由现 HTTP file、Dossier file 与 Claw reference 三入口按 path.parts[:2] 固定拒绝，
包括旧缓存 ID、.txt 半文件、撤权和回执缺损，不以扩展名当唯一边界。原 page-evidence、普通上传及
来源引用仍进入旧强核。仅已登记 scope.file_bindings 的生成副本从数字观察投影排除；未登记文件
仍可使真实 quality 返回 invalid。取消/未知不保存为成功，也不能换 callId 重跑。

## 实际验证

- `integration-final.log`：53 tests PASS。三方法各实际 source capture/read→固定 DSH SkillProvider/
  ToolRuntime/guard→原 sandbox→私有 completion→Host复算→原 report_plan/canonical/HTML/DOCX→
  research_check_quality。正例真实状态均 incomplete；公司原表 245122/211915 经系统计算为15.67，
  测试叙事为 scripted fixture，不是真实模型。覆盖取消、不可重试、完整性、普通 code 禁读写、
  receipt 丢失、撤权、半文件、未知输入触发 invalid。
- `regression-final.log`：25 tests 已通过后，旧 stage2 总 Skill 数30断言失败。前三十之外，397基线
  已有九 pack（实际39），本候选再加三方法为42。stage2/3/4 仅更新显式42与九 pack/三方法集合，
  六/七/五个旧算法的 disabled、receipt、selection 拒绝保持；不是新方法等价通过旧阶段。
- `gates-final.log`：修目录计数后，三阶段18禁用门与原零分母剩余目标共5 tests PASS。前25包含
  原八场景、原两pack实际 Native（含取消）、weekly 权限与普通 sandbox；不重复执行已过25项。
- `source-picker-js.log`：20 tests PASS，包含固定 owned flag、旧两pack、来源预览/冻结及 unknown。
  Ruff、Black、isort 对26个本切片 Python 文件 PASS，五个改动 JS 文件/Native helper 的 node --check PASS。
  mypy NOT_RUN（主任务已记录现成环境 librt 缺口），没有安装依赖。
- DataHub 财务正例使用实际 Sina HTTP MockTransport→原 provider parser→真实 snapshot manifest/query/rows：
  600600.SH、2026-06-30 与 CNY 保留，单位与累计 basis 未知保持 partial。没有 mock DataHub.query 或
  假造单位；也没有声称执行了真实供应商请求。

## 尚未实现的代码集成

1. C2 去重制品尚未绑定，新闻/调研明确 source_version_dedup_not_run；属于 CODE integration pending。
2. C4 仅严格纯参数函数，未接实际兼容工具入口；C1 全部相应参数仍 unsupported/pending，没有 mapped。
3. 原 report_plan percent_change 尚无 owned 方法对非正基数的独立准入硬门。现正基数示例与零分母
   回归不覆盖负基数；禁止升级为完整财务方法或正式映射。不改通用数学，下一窄集成处理。
4. 现 annual 解析器不认证实体/URI/通用币种。MSFT fixture 的 numeric/report_plan 链可跑，但来源动作
   保留 unclassified/financials 缺口，没有新增 MSFT URL 专用分类。非 UTF-8/PDF reader 自动接入未实现。

真实模型、外部来源网络、正式研究接受、部署与其他平台 NOT_RUN；当前候选不是整个 T3 完成。

## 本轮测试资源收尾

只归档并回收本轮登记的 `/tmp/rwb-c3-actions-3V1xlNQt` 下19个 pytest 子目录。510份必要原件、
Store index/执行回执、canonical/格式/ledger 与日志进入 `evidence/run-evidence.tar.gz`（2,369,573 bytes），
SHA-256 `721d4377e10f3193b97a3f0704b55c9e81760bcb5b3839237243a82445ebe14c`。
全部41,002,652原始字节逐文件恢复后按 manifest SHA-256 读回通过，详见
`evidence/retirement.json`。初次清理遇只读测试包目录失败，
仅给本轮已验证退休目录恢复 owner 写位后重试成功，回执 status=cleaned。未改任何服务、全局配置、
其他任务、Docker 或工作树。测试根1.7 GiB降为4.0 MiB，磁盘可用由5.9 GiB回到7.7 GiB。

模块合同与边界见 `docs/research-web-owned-methods.md`。独立 SPEC/QUALITY、完整 Router、
本地 CI、Mac 干净安装及发布交由主任务聚合，不由本切片自评替代。

## Python QUALITY 准备原子性修复

独立评审基7338仅发现准备阶段先写副本后检查资源/预算的问题；原SPEC与JS评审已通过，不以这些
评审代替本轮Python复评。仅修改owned来源模块、相关新测试、模块文档、报告与生成Python索引。

RED：`/tmp/rwb-method-atomic-62DCRqRZ/red.log` 在7338实际重现 `_file` 资源拒绝后私有副本残留。
修复将全部可预检资源/闭包、源身份、数量、总字节（含上下文/资源）、runtime和launcher上界移到写入前。
小准备事务记录本次exclusive出生的parent/dev/inode；只有身份一致的自有文件和自建空目录可以回滚。
已有/复用、替换文件及替换父目录一律保留，不清未知，不伪造saved/started掩盖orphan。

Store save异常通过原index读回判别：同一receipt明确没有新ID且原列表一致，才恢复内存旧列表并回滚；
新ID已提交则保留真实durable prepare intent（没有native_result），无法确认也保留未知并拒绝重复调用。
没有增加回执schema、恢复器、公开接口或新执行通道；普通来源/alias/Native与质量权限门均未放宽。

GREEN：`final2.log` 11 tests PASS（57.75s）：实际资源拒绝、真实源与资源字节sum的限额-1/精确限额边界、
write/fdopen/readback/save-before故障及显式重试、已有文件保护、文件/父inode替换保护、save-after真实
原子发布后的未知不可重试。首轮8通过；补测首轮仅测试把已有directory包装的StoreError误认OSError，
改为核验实际异常及cause，未放松产品拒绝。没有运行模型、来源child、供应商网络或安装依赖。

原7338的53/25与真实Native链没有机械重跑：`unchanged-abi.json`逐函数AST比较确认 launcher、_file、
source_context、_resources、_readback、complete_execution、quality_issues、validate_storage、
original_evidence_files 九函数不变；Native JS、sandbox、固定Skill资源/入口、权限和报告实现未改。
这仅说明可复用证据范围，不把旧SHA执行伪写成本候选执行。C2/C4/非正基数三个CODE pending保持。

本轮两文件 Ruff/Black/isort 与生成Python索引 --check PASS，diff --check PASS。新证据根独立登记
`/tmp/rwb-method-atomic-62DCRqRZ/owner.json`，未使用共享pytest根，也未写入独立评审的保护证据根。
243份必要原件/index/故障回执与日志、共2,642,106原始字节逐项恢复核SHA-256通过后，保存为
`evidence/preparation-evidence.tar.gz`（427,937 bytes，SHA-256
`7a7d0e1d7e52e0b449dfb3f53b5b50ae8e036042bdd6cda19a49db7fb30d99eb`）。
仅回收本轮四个登记pytest子目录，retirement.json status=cleaned，测试根从1.0 GiB降为1.2 MiB。

## C3b/C4实际完成接点（基线b84020549f5c8e23253aabba7474b6cdfbb7421b）

宿主macOS，Web功能开发，沿既有Harness与本任务独立worktree；无push/PR/merge、真实来源网络、
供应商、模型、收费、秘密配置、依赖安装、部署、正式数据库或系统配置操作。

1. 两owned场景显式timezone cutoff_at沿原输入冻结；严格上海日期一致，不从日期/当前时刻补值。
   Host当前resolve_reference→原project_source_version→公共execute_atom_bundle执行deduplicate_source_versions
   1.1.0，保存原receipt与完整canonical full_result字节。调用前canonical roundtrip稳定原legacy digest
   的对象顺序，不改C2算法/record schema。新wrapper绑定core/dependency/projector、完整SourceSet、
   owner/target/原hash/locator/发表与取得时间、输入digest和gaps，纳入原file_bindings/context hash/
   16MiB合计和b840准备原子事务。Native只消费Host固定声明的c2-dedup.bound；Host completion/quality
   重新授权、同投影、同atom复算。身份明确Host执行C2、Native消费。缺cutoff/unsupported/future/
   unknownrole/pub/上游完整性缺口保留，不冒充运行原source pack。
2. 公司Host-only policy owned-company-positive-base-v1由原handoff/冻结contract三元绑定重建；SDK和
   Host report_projection各传入原recipe与Summary实际resolved operands。非正基数硬拒，Summary
   derived/$step/abs基数拒绝；owned公司canonical必须system_plan，删policy/手写canonical不能绕过。
   245122/211915仍15.67，generic负基数原-300.00不变，difference必须显式选择。
3. 固定RWB wrapper rwb_query_latest_cls_news仅query/strict int limit=1..100；原datahub_search_news
   日期/通用schema不变。原private business-query新增严格owned union，实际adapt_query_news→真实
   DataHub.query/broker/CLS parser/snapshot/cancel；sourcecls、research、strict、allow_fallbackFalse固定。
   wrapper自身目录只在Host本地CLSready及scope允许时可见，拒绝只掩蔽该wrapper，实际调用重复准入。
   wrapper-only required_tools记录原datahub_search_news，不把CLS加成三原件方法强制依赖。
   三question preset在owned prepare/create_handoff/source-selection同helper执行，Host先核当前选择，
   冻结question后沿原handoff/send/Native方法/report/quality；冲突明确拒绝，不解析ticker取数、不改旧任务。
   C1仅4个实接入口的5参数标native_subset；supplier alias仍拒，其他参数/旧18gate不放宽。

证据根 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-c3b-completion-ozn6fz5b`，每轮显式basetemp，
owner登记task/slice/UID/PID/dev/inode/argv/candidate。首RED因dedup模块缺失失败；cutoff目标1PASS。
native1原atom原receipt对照暴露对象顺序依赖，native2随后被原sandbox exactfilename门拒绝；修后native3
两C2真实纵向PASS。未绕路径门，仅获准把固定c2-dedup.bound加入原METHOD_INPUT_POLICY两处regex。

实际验证：

- target.log：34 PASS/78.89s。C2未来取得、unsupported、完整SourceSet/版本/inputdigest变造；公司负零、
  Summary direct/$step/abs、SDK删policy与手写canonical经真实Host quality invalid(report_invalid)；
  wrapper严格Host参数、scope/CLS disabled、真实provider取消不落snapshot、C1原alias全拒。
- presets.log：6 PASS/50.74s。原三方法及3preset各真实capture/Hostfreeze/handoff/send/pinned Skill/
  ToolRuntime/guard/Native sandbox/completion/原report_plan/canonical/HTML/DOCX/research_check_quality。
  final-native.log再复验六正例通过；新增负基数例产品已正确runner failed/exit1，首轮测试误认transport
  isError，改按runnerstatus/stdout断言，final-neg.log 1PASS/8.26s，稳定owned错误且无canonical。
- compat2.log：1PASS/5.23s。真实Native wrapper→Hostadapter→DataHub.query→MockTransport真实CLS
  parser/snapshot；row_count[0,1,2]、真实rn[1,2,2]，验证limit先行/casefold/空query及原日期schema。
- ui-guard.log：50 PASS，原picker、owned cutoff/preset冲突/切换无泄漏，wrapper目录mask恢复/撤销。
- static.log：20个改动Python Ruff/Black/isort PASS；生成Python索引--check、改动JS/helper node--check、
  diff--check PASS。mypy NOT_RUN（现成librt缺失，不安装）。完整changedset文档/API Atlas/Router/CI/
  Mac干净安装与独立SPEC/Python/TS QUALITY由主任务继续，未以此自评替代。

真实quality正例仍incomplete，负基数未生成canonical保持incomplete/report_missing；叙事为scripted fixture，
HTTP仅离线输送边界，真实模型/来源网络/正式报告接受/部署/他平台均NOT_RUN。本切片不等于整个T3完成，
T4/T5及其后续门保留。

## 独立SPEC表单P2最小修复（基线c453d9da）

SPEC以真实Chrome复现：owned preset_query有效而原question为空时，控制器preview通过，但原textarea
无条件required导致formValid=false、submitEvents=0。新增目标render断言先在原源码RED失败；修复只在
当前owned场景的合法固定preset+有效query时移除原textarea的required，用同一窄谓词约束validInputs。
旧八场景、无有效preset/query仍保留required，冲突原题与query仍控制器拒绝；没有form novalidate或
绕过原生校验。产品源码仅ui/scenarios.mjs，其余变化为目标JS测试/浏览器helper及本module文档/报告。

本轮opaque证据根 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-preset-formfix-x5kg6pq4`，
owner事前登记task/slice/UID/PID/dev/inode/candidate/命令；未跑pytest或安装依赖。
green.log：控制器/render与原source-picker共27PASS。browser.log/browser-results.json：全新隔离Chrome
profile、file-only模块、禁DNS/后台网络，共9例实际renderer/controller PASS。三个合法preset-only均
formValid=true、submitEvents=1、handoffs=1；旧8空题、owned无preset、空query、错配preset、URLquery
均native form阻断；冲突题native可submit但控制器拒绝、handoffs=0。未使用个人Chrome或实际HTTP来源。
backend-unchanged.json逐git blob核对除该UI外全部app/research_web文件与c453一致，不机械重跑六条
后端Native/report链。目标JS/helper node--check及diff--check通过；本轮待主任务重新独立SPEC/QUALITY。

本轮1054个非该UI的app/research_web git blobs与c453逐个一致。九份必要DOM/结果/日志/owner及blob证明
归档为evidence/form-fix-evidence.tar.gz（47,374B，SHA-256
564cf6b980865d44f0e624fbc116d2d02b3450ee75557fd7209236f943c2a8fb），全部逐文件恢复核SHA通过。
确认无进程占用且dev/inode匹配后，仅退休本轮fresh Chrome profile（2,686,620B），retirement.json为
cleaned；保留全部必要证据，不触碰个人Chrome、metadata任务25个WIP或其他测试根。

## JS QUALITY测试合同补齐（基线e5363aa8）

仅修三个测试文件与本报告/module文档，不改产品源码。独立JS QUALITY发现public-data原15计数/子集
断言漏掉新增fixedwrapper；method_tool旧错误文案已由7338（b840已有）改为四closed modes，属于
existing-in-task测试欠账。主任务全JS诊断另发现capabilities UI旧39未计三owned方法，原诊断1528项
1524PASS/4FAIL不冒充最终候选通过；本轮保留所有原测试/硬门而补齐精确期望。

- public_data精确保留原15工具全集，加wrapper总16；enabledTools子集准确新增wrapper，未启用原news
  或尝试只启wrapper仍拒。新增精确closed query/strictlimit schema、12类非法参数零HTTP，保留原news
  start_date/end_date/source字段；真实guard在Host允许时可查询，scope/CLS local-ready撤销仅掩wrapper、
  pre-execute拒绝且business HTTP不增加，原15仍可见，恢复准入后目录恢复。
- method_tool精确断言四模式closed拒绝文案，空参数/code+plan/plan+method仍拒且spawn=0；原后续
  admitted/contract/limit拒绝与有效plan/code成功保留。没有为满足旧regex回退产品合同。
- capabilities UI用真实CapabilityCatalog固定旧39 ID全集加三owned CID总42，18个旧gated仍disabled；
  新三项方法版本1.0.0、当前catalog v1/按钮启用逐项断言，不改为>=或删原39/18门。

opaque根 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-js-contract-fix-6b6xl9sx` 事前owner登记
task/slice/UID/PID/dev/inode/argv/candidate；TMPDIR仅指本根runs，未用共享默认临时根，未跑pytest/大Py/
Native/model/source网络或安装依赖。red.log实际重现原两文件3FAIL，capability-red.log独立重现42!=39。
green-final.log：三改动测试加既有guard共100PASS/0FAIL/0skip（15.14s），目标node--check/diff--check PASS。
product-unchanged.json逐git blob证明1055个app/research_web文件均与e536一致。未宣称全JS通过；主任务
将按最终干净exactcandidate重跑完整union并由原JS reviewer复验及SPEC确认测试scope。

本轮115份regular证据与三份故意安全测试link元数据均不跟随外部目标，118项归档后逐文件恢复核SHA
通过。evidence/js-contract-evidence.tar.gz为47,401B，SHA-256
4931df7fd56b976ebb483edf68006848e5cbd707d5633391a3006532f841994b。重新核原文件身份/哈希及无进程占用后
只回收本轮TMPDIR runs，retirement.json status=cleaned；top-level日志/owner/产品blob证明继续保留。

## Python计数/互斥测试协调及固定SDK CI前提（基线60c65397）

只改tests/CI/docs，app/research_web产品字节保持。原root第一组535PASS/3FAIL不是本候选通过：
tools精确集合缺wrapper、非pack快照旧26未加owned3、mutex准备阶段误占原2秒Native握手预算。
新opaque根 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-python-contract-mutex-zdhltsdk` 的各pytest
均事前owner登记task/slice/UID/PID/dev/inode/argv/candidate，显式basetemp/confcutdir；未用原root3.4GiB。

原mutex单例孤立FAIL（7.93s），纯观察重复仍FAIL（8.29s）。独立diagnostic_only保留原2s FAIL：
真实snapshot_catalog同步完整冻结2.688986s，send到原Native prompt barrier为2.702541s；2s回调在
2.700642s返回Timeout，sending未done且无exception，await-chain是service.send→to_thread。
约2ms后到达真实barrier，changing未提前done、release后disable仍拒且能力enabled。不能据此声称性能
已修复或将诊断的迟到观测当原测试PASS。获准仅在测试用纯观察wrapper完整执行原snapshot_catalog，
实际完成后set ready；准备独立有界15秒并同时监视send exception，之后仍原2秒Native barrier与全部
互斥/未提前publish/disable拒绝断言。没有mock资源结果、跳I/O/准入或修改产品锁。

原两计数目标RED 2FAIL；修后工具全集保持baseline|added精确集合，加wrapper独立required_tools/
readonly/不可选/closed query+limit及native-policy conditions，原BUSINESS自动权限断言与完整集合保留。
auto-snapshot固定旧26 IDs+owned3=29，九pack、旧六排除及既有require-tools门保留；三owned当前v1的
SKILL.md及所有真实snapshot资源逐文件核SHA，不以count代替资源证明。target-green.log共5PASS/23.57s，
包含原mutex保持2秒、Node override/PATH/缺失明确失败以及真实Native wrapper。

root第二组39PASS/1FAIL属于旧epoch：专项硬取RWB_TEST_NODE导致KeyError，CI另无SDK。Node测试现在
复用可执行override或PATH且缺失明确fail；实际SDK专项移至独立test_owned_news_native_sdk.py，无skip，
硬验显式SDK、固定Git HEAD、compiled libs，调用原compat私有共享helper避免重复自动收集。旧compat
完整Host参数/权限/取消留原Checks；Mac Bootstrap已有固定DSH构建，所以专项由原Mac安装后步骤强制
承接，而非通用Checks重复安装DSH。sdk-extracted.log在现成环境显式unset Node override、使用Node24
PATH与真实fixedSDK，独立专项加完整Host compat共12PASS/51.90s；未运行真实供应商/模型/网络。

CI同一旧步骤先保留干净installed资源/Doctor/3081/8088/搜索证据，然后从pyproject原dev字符串仅取
pytest/pytest-asyncio，在CI临时venv准备两个已声明工具；不editable安装项目、不改依赖定义/锁、不本机
安装任何包。安装器实际Node24.19.0与已构建SDK pin/compiled libs强预检。-I导入记录installed app路径
及全部非再生包资源bytes，pip实际新增报告、既有distributions版本/替换前后不变为硬门。测试使用
checkout Host fixture+fixed SDK，与干净安装分别记；owner/显式basetemp/JUnit/log/失败默认receipt进入
原success/failure artifact，失败或skip仍令job失败。同步原trigger、架构测试inventory、安装文档与预算，
无新job/runner/timeout/产品依赖。真正CI及dev工具安装仍NOT_RUN，待主任务独立CI差异评审及exact SHA。

ci-governance-final.log 19PASS；workflow YAML解析、5段bash -n、4段Python heredoc AST PASS；四个改动
Python Ruff/Black/isort、生成索引--check、Node syntax/diff--check PASS，索引内容无需变化。未以本轮
目标通过冒充完整Python/JS union、Mac干净安装或正式研究质量通过。

本轮七个事前登记pytest根共665,183,652字节，17,668项逐文件完整恢复核SHA后重验原dev/inode/hash，
仅回收本次七根。evidence/python-contract-evidence.tar.gz 189,589,925B，SHA-256
13de2c310a2c49f5d41b805166186c90d6f706057e69c87da455a90af3427fb0，retirement.json=cleaned；恢复时每份
完整文件写出核验后只移除恢复副本，控制磁盘峰值。原失败日志、纯观察脚本/JSON、owner、static和产品
1055 blob不变证明另作metadata归档恢复核验，原top-level证据继续保留；不触root其他CAS/服务/SDK。

## CI QUALITY两项独立修复（基线e919077d；取消源码未开始）

e919不是Ready：HIGH为嵌入块误用不存在的WebInstaller，真实接口是SetupWebInstaller；MEDIUM为
FAILED默认receipt/try太晚，导入/Git/RUNNER_TEMP前提失败无回执。原e919实际嵌入程序已在独立子进程
复现非零ImportError且receipt不存在，不把AST通过或counterfactual下游分支当成e919成功。

真实只读probe已实际import与构造SetupWebInstaller(project_root=当前WT)，公开签名与node_executable/
dsh_source字段有效；实读Node24.19.0、SDK Git HEAD和三compiled文件均匹配，未调用安装/构建/服务/
网络。probe证据根rwb-ci-installer-probe-vfmbjrcj保持，非mock不存在类。

修复仅tests/CI/docs：最外层先用标准库在固定工作区绝对artifact路径写FAILED默认receipt，随后try
包住所有应用import/环境/Git/owner/preflight/install/pytest。真实SetupWebInstaller替换错类名；缺
RUNNER_TEMP明确失败，不借未登记临时目录。except记录稳定stage/code/error_type并原样重抛，finally
总写回执；若已有installed基线，最后仍强核包字节与旧distributions，主异常不被最后检查错误覆盖。
SDK pin/compiled、原dev两工具、pip替换/版本、installed bytes、pytest exit、JUnit exact1/0skip和
最后完整性等下游硬门保留，无产品依赖/锁/job/runner/timeout变化。

新增独立test_native_sdk_bootstrap_ci.py登记原Checks；真实构造与早期三失败共4PASS（0.19s），包括
缺RUNNER_TEMP、受控import失败、真实非Git cwd失败，均非零、FAILED回执、稳定stage/code且不写私有
sentinel。非Mac测试仅对平台门做明确counterfactual来验证回执，不认证Mac Native。CI governance19PASS，
新增Python Ruff/Black/isort、YAML/bash/PythonAST、索引/diff PASS。证据根
`/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-ci-early-receipt-fix-ntgmazxx`，各pytest事前opaque
owner及显式basetemp；真正CI/pip/SDK构建/服务/模型/网络均NOT_RUN。取消产品修复仍排队，未混入本提交。

最后原错误传播断言补齐后四例仍PASS（green-last.log，0.19s），原错误类型保留在stderr而不写私有正文
入receipt。25份日志/owner/实际失败回执及pytest current元数据归档后逐项恢复核SHA通过，
evidence/ci-early-failure-evidence.tar.gz为3,529B，SHA-256
84f524f58cf9d8ccac488f028a79ec2523225072335339d25760a5529671e6b7；仅本轮五个测试/反例子目录退休，
retirement.json=cleaned，必要top-level证据保留，未触其他任务资源。

## whole-review取消提交窗口单波修复（基线f76a2f30）

只在原Host/Native完成链及Delivery共享纯判据修复，不改Store/SourceProof/DB/依赖/固定算法或第二引擎。
原states仍saved/cancelled/failed/invalid；非started重复完成保持unknown_do_not_retry，已saved quality/
readback不改，不新建幂等API。JS桥入口、真实trustedDirectory/privateControl两个await后及dispatch前
均重验调用signal，合并exec.signal与原timeout；已wire中断仍未知，不自动换call重发。research-tools
在child close后两模式对称复验caller信号，不再仅在method较早一次转换。

Host在原service.lock内先核服务器当前key/receipt归属、本binding.task_id与delivery/contract一致，
身份不明在写状态前保unknown。accepted_task_cancel纯函数抽原reconcile accepted receipt+acceptedTrue+
key/task/marker强判并额外绑定本execution；reconcile的FINAL/ready与锁序保持。接受取消先于完成则
execution cancelled，真实Native completed原结果仍保留，不新saved；acceptedfalse/foreign/newtask不误
取消；不使用started_at时间比较放行早于start的同task已接受取消，无新status/binding/schema。

opaque根 `/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-completion-cancel-2doqoja6`，本轮各pytest
预建owner与显式basetemp，JS临时文件仅own TMPDIR。RED：桥true AbortController五阶段×两模式10例
失败；Host实际service.cancel接受后、真实Native制品提交两模式仍saved，native-red.log 2FAIL/28.31s，
pack取消特意早于execution start；method用真实锁acquire纯观察证实completion排在cancel接受之后。
pure新判据先因缺函数RED。没有mock DataHub.query/ledger/报告通过，也不把fetch-only桥反例替代Host。

GREEN：native-final.log 14PASS/101.10s，真实pack/method六矩阵、原SDK专项一例及pure七反例；六矩阵含
接受先完成前/RPC拒绝/保存先取消后三种顺序，Host真实cancel RPC路径与真实sandbox产物、method两锁
排队、pack取消早于start、foreign服务器task保持started未知且不改record、重复完成/newcall拒绝，旧saved
source/readback不变。js-final.log 70PASS/0skip：两模式入口/两await/dispatch/已dispatch的真实AbortController
（桥仅fetch mock），另前端fake-child close后零completion调用及原public/method/CI治理门。前端fake-child
测试不冒充Native；真实制品由六矩阵独立验收。regression.log原cancel/reconcile正例与四缺证、Delivery
unknown/idempotency、旧pack及method真实完成目标8PASS/90.21s，不机械重跑大组/原50PASS旧epoch。

原Mac Bootstrap同一步强制SDK一例加六矩阵：明确选中exact7、JUnit0skip/error/failure门不减，原f76
cleanDoctor/installed byte/version与FAILED最外层receipt保留；纯字段门登记原Checks，新Native文件无skip。
现成环境逐项通过不等于真正CI已运行；没有本机pip/SDK构建/服务/模型/供应商网络操作，其他平台NOT_RUN。
新增Python及产品目标Ruff/Black/isort、Node语法、YAML/bash/PythonAST、生成索引和diff检查PASS；mypy
保既有librt缺失NOT_RUN。待原whole finding复验、SPEC及Python/JS QUALITY独评，未自行认证完成。

本轮959MiB测试根中949,484,786原始字节/22,289项完整文件及link元数据逐项恢复核SHA，再核原dev/
inode/hash及进程使用后，只退休本轮JS与四个pytest子根，retirement.json=cleaned。完整artifact archive
322,871,617B，SHA-256 c79f88adfaedd5b0477eaa63d165411c82dab647a4f9916dea0d37e093f7935a；metadata
日志/owner另档恢复核验，必要top-level证据保留。逐文件恢复后释放恢复副本控制峰值；未动其他任务/
SDK/服务/Docker/工作树。无tmp_path的pure/collect未生成临时子树，不把不存在的root伪列为已清理。
