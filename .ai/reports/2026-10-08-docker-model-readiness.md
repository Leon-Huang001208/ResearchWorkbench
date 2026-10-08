# Docker 最小文本研究闭环实施进度

任务 `docker-text-research-20261008-a1`；宿主 macOS/Darwin23.6.0 arm64；类型为Web功能开发与macOS Docker Desktop验收。实际基线/初始HEAD `b352ffa304c0b17c3260ed9417f083aac0fedf64`，分支 `codex/docker-text-research-20261008-a1-model-readiness`。新受管worktree，不回退主线，不重做旧Task1–14/c1，不改写历史receipt。

用户2026-10-08明确确认模型专用私有文件适配层、跨语言合同与现有隔离验收控制的最小设计并授权继续实施；不等于授权付费请求、读取日常Key、新依赖安装或扩大远端/平台操作。

## 已实际执行

- 完整读取新goal文件并定向检查Python/JS桥接、shared安全文件原语、owned启动器/Compose、Service不确定状态、平台能力和现有普通CI命令。
- 从最新origin/master建立新任务身份和分支，主工作树原有未跟踪报告不修改。无安装/真实Key/上游模型请求/日常服务操作。
- 现有Python模型桥接基线：4 PASS、2 SKIP/0.06秒。命令和JUnit在 `logs/model-readiness/initial-audit.md` 与 `baseline-model-credentials.xml`。两SKIP是既有显式opt-in真实Keychain/固定DSH，不声称实机通过。
- 现有JS模型/Docker打包合同：18 PASS/0 FAIL/0 SKIP/264.802416ms，实际Node命令在initial-audit。源码合同不等于容器或真实模型PASS。
- 设计和实施计划已写入本轮spec/plan；此前设计确认等待已由用户明确解除。

## 正在执行

Task1仅修改模型专用文件store、Python私有桥接和最近测试；实现代理先RED后GREEN，再规范/质量审查。Native直接Keychain无回退，DataHub backend默认行为不变。根、ID、来源仅由受管链绑定；先提交失败留旧值，提交后不确定不能删除已发布凭据或假报回滚。主代理负责docs/库存/报告和后续整合，不并行修改代理-owned文件。

## 未执行/不作完成声明

- 当前新代码的完整Python/JS桥接、设置页、Doctor、free研究恢复链及Router/工作流执行补齐仍待实现/验收。
- 新镜像构建、macOS Docker新实例canary、真实文本生成/重启续问/重建持久化、有限浏览器场景均 NOT_RUN。
- 真实Key只能由用户在独立设置页输入；付费模型请求次数/token/费用预算需另获明确授权。不能把替身或健康检查当作真实模型证据。
- 现有live控制拒绝内部3081且仅用于基金工具，本轮只在现有控制内增加已隔离安装绑定，保持普通实例拒绝和总预算；不建立第二框架。
- 远端PR/CI/合并/清理、Windows/Linux产品dispatch/认证及版本化镜像Registry发布未执行。脚本沙箱和Office/Wind/Tabbit Host Bridge不在本轮范围。

当前只认证已执行的基线与规划进度，不认证Task1已完成或整体文本研究闭环PASS。全量实际changed set的计划/回执、作用域完整性检查和后续源码冻结均随实现更新，不使用旧goal验收冒充本轮。

## Task A Python片段实际进展

模型专用store/Python桥接已经独立SPEC与Python QUALITY批准。实际近处测试75 PASS、
相邻原DataHub凭据58 PASS，2个既有实机opt-in SKIP；Ruff/Black/isort/diff检查PASS。
新增静态/实例override类型错误曾真实出现并最小改名修复；原mypy依赖缺失检查及
正确既有venv依赖环境下的16→15诊断都保留，未把全命令写成PASS。
相同基线Git树的旧模型桥接/共享凭据import closure也实际有15条相同未改模块诊断。
主代理随后以同配置重跑当前两份源码，15条诊断与该基线精确多重集相同，owned源码诊断为0；
`task1-mypy-baseline-comparison.json`记录整体FAIL而非PASS。
真实RED与初次未触达初始化而实际PASS的stdout fixture均在task1-evidence中分开记录，
不把误命名文件当RED。后续Type-repair freeze独立保存，不覆盖原freeze。

当前架构检查真实报告缺runtime文档、structure decision及新源码映射；已补相应说明和
inventory，生成索引与完整约束复核随后执行。Python基础与JS/launcher集成、新镜像、
真实模型/平台证据不同层，不认证后续链路已完成。

生成索引后，架构检查又真实发现新的inventory使图册index过期；用原Atlas生成器更新了
仅实际变化的index页面，复核为0 violation。文档治理与Python index复核PASS。
当前完整13路径slice经现有Git-bound planner（validation_failure signal）为L4，选中5本地、
2外部门。完整changed-set Project Constraints为0 violation；原四模块Node相关完整验证
实际104 PASS/0 FAIL/0 SKIP，含独立architecture模块的全部用例（同命令覆盖，不冒充另跑一遍）。
同平台安装、镜像、真实model及远端门尚无本轮结果；本片段可以本地checkpoint，不能发布为整体PASS。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"模型专用Python适配层复用既有私有凭据mount和描述符锁；新增模块列入inventory，但当前未由owned JS启动链选择，不新增部署节点、公共API、Host集成或第二DSH循环。图中既有Native模型平面与Docker未验证边界仍保持，真实Docker模型与生命周期留待后续独立验收。","diagrams":[]} -->

## 设置/Service/Doctor与免费恢复片段

Task3 SPEC、Python QUALITY、JS QUALITY均APPROVE。Service actualdescribe映射与设置来源/权限
说明保留active/uncertainty；临时真实DockerModelStore+原native transport/生成替身覆盖设置、
失败/取消/重复/冷读/历史恢复。完整API+caps77 PASS/413.16秒，两个后加用例各PASS，共覆盖79；
六源码Doctor追加前后冻结相同，复用不冒充重跑。UI42 PASS；Doctor/caps58 PASS，含27loopback。
HEAD对照RED25 FAIL与framing RED1 FAIL保留；warnings非核心hardgate。mypy57与HEADshadow
多重集相同，整体FAIL，格式/语法/diff PASS。镜像/Key/真实模型/浏览器/CI未执行。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"来源详情与权限文案复用设置卡片、列表、警示，不变更路由、密码、主题或框架；实际来源/未知和真实推理分开，真实浏览器另验。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"原runtime来源新增受控Docker枚举，不新增路由或取密；active/uncertainty/cancel/store保持，Doctor定向读取同一接口而非新状态框架。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Service自动化方法未修改，源码只增加模型来源；临时store与原transport替身验证既有恢复，Automation/MCP调度、目录、审批、索引和锁保持。","diagrams":[]} -->

## Task A 跨语言/受管绑定片段

### Task3完整门未解决项（后续实际记录）

完整controller+caps2 FAIL/417 PASS/217.03秒（task3-final-selected-controller.xml）：合法NO_PROXY
Doctor与darwin真实reservation停止预算，均先遇既有runtime_mode_changed后转data_home_unsafe。
不能认定模型探测为根因。精确两案例单次2 PASS/30.37秒，原序最小上下文11 PASS/52.24秒；
只读trace捕获0 changed事件，NOT_REPRODUCED而非已修复。原FAIL、八源码freeze不变；
未改guard/fixture/工具/预期，共享祖先metadata仅静态假设。完整门仍FAIL，不作为发布完成依据。
独立TaskC测试选择/普通CI执行补齐继续，不盲重复该全套。

live预算现有进程计数会重启清零，chars/4不是输入token硬界。固定DSH正常LOOP补齐并freeze
maxTokens，可拒绝超输出cap；usage仅数字审计，缺usage不退款。endpoint、累计token/费用
绑定仍待窄扩展及独立真实Key/预算授权，不把源码/替身或事后统计认证付费闭环。

## Task C 普通回归入口补齐

四文件补丁 SPEC / QUALITY 均 APPROVE，冻结 diff SHA-256
`937a3c3e213e7a710dc106f459c12d5272895826866f73730f1d56fbe255901c`。
实际 RED 91 PASS / 4 FAIL，GREEN 95 PASS；质量审查独立再跑 95 PASS。
负向合同验证删除 Python 模块、替换 pytest、修改 confcutdir 和删除显式 Docker Node 参数。
模型/共享后端实际 133 PASS / 2 既有 opt-in SKIP，模型/Docker JS 25 PASS；这些分项
复用冻结源证据，不冒充质量审查重跑。Task3 十个冻结项未改，原 controller 2 FAIL 未解决。
新增精确 catalog / security-high-coupling L4 路由，普通 Checks 真正执行十二个 Python 模块和
原 Node glob 加 Docker contract；未扩平台矩阵或 Bootstrap，未触发任何远端操作。

只读 GitHub API 当前 visibility PUBLIC；最近五个成功 Checks job 实际为224、225、222、220、221秒，
平均222.4秒。额度文档同步明确扩展范围、保留20分钟上限及完整 job 仍待远端实测。
完整基线规划初次因沿用 Task1 context 的旧 candidate SHA 被真实拒绝（PLAN_ERROR）；
不修改旧 context/receipt，新增当前 HEAD context 后重规划，保留初次拒绝日志事实。

Task4C 完整基线计划当前44路径、L4、21本地门、5外部门；unknown fallback保留。
文档同步后95合同再次PASS，其他 Router/receipt/platform/summary43合同实际PASS。
文档治理585文件0违规。完整constraints初次3违规（两模块文档与结构决定缺失），
补工作流/开发地图及以下审查说明后按完整集合复验；不修改已冻结的四文件补丁。

复验实际0违规（task4c-full-constraints-v2.json）；中间完整集合已包含并行顺序实施中的
Task4B新路径，48路径snapshot不作为最终冻结候选回执。最终交付须在所有源冻结后重新绑定。
预算/source核对另澄清：client.py 将llm.models/session.models映射到session/modelCatalog，
此前仅凭不同命名的疑点不是缺陷，未修改适配器。

普通JS治理完整四模块当前108 PASS / 0 FAIL / 0 SKIP（task4c-full-js-governance.log）；
新增workflow合同使数量较Task2的104增加，非重写旧证据。

## Task4B 准入片段（部分实现，尚未完成）

在现有control/guard内增加明确docker-text schema与已验证staged/model安装绑定，配置最多3次、
输出不超过4096；禁止全部工具与附件，并保持旧基金验收路径不变。当前在dispatch前一律
acceptance_budget_unverified，配置次数不是已授权次数，不能宣称已实现持久预算或真实调用。
实际RED Python1 FAIL/6 PASS、Node2 FAIL/1 PASS；完整launcher148 PASS、guard12 PASS。
Ruff/Black/isort/语法/diff PASS；mypy57/19files与actualHEADshadow诊断集合相同，整体仍FAIL。
四文件冻结 task4b-admission-freeze.sha256，片段报告 task4b-admission-summary.md；
SPEC随后审查。真实fixedDSH免费transport证明、私有持久预扣账本和独立预算授权仍待完成。

准入片段SPEC实际发现自定义AbortSignal reason被原样抛出，dispatch虽为0但错误脱敏未满足；
判NEEDS_WORK，不提前进入质量批准。实施者仅修Dockertext中止固定码与最近回归，legacy语义保持，
旧freeze/测试证据保留，v2另行审查。

v2实际RED2 FAIL后完整guard13 PASS，Dockertext固定acceptance_request_aborted，不读取reason，
legacy取消原样保持。SPEC复审APPROVE partial，独立敏感reason/拒读getter验证dispatch=0、
reasonReads=0、logs=[]；Python两文件hash未变，148PASS只复用旧执行。质量审查随后开展，
不将片段批准写成完整持久预算已实现。

v2 QUALITY局部APPROVE；独立freeze四项、guard13PASS、Node语法/局部diff均通过。
Python148PASS同hash复用，周边静态类型/错误/日志检查无新增重要问题；JS无canonical typecheck，
ESLint NOT_AVAILABLE，无安装或配置修改。完整预算/endpoint/真实模型及controller原FAIL仍未关闭。

因启动器实际变更补跑原container-runtime组合门：supervisor＋launcher 245 PASS /37.87秒，
task4b-current-container-runtime.xml/log。不是重跑完整controller，也不替代其两项原FAIL。

## 固定SDK免费transport与冷恢复证明

复用既有model_credentials_native.mjs的独立sdk-free分支，旧Native正文3126bytes与HEAD一致。
实际固定DSH runProfile、catalog、preset、create/selectModel/prompt成功；两个独立进程分别
首问和冷恢复，先前完成turn从0变1，当前持久会话有2个completed turn。
inprocess stub捕获official endpoint、deepseek-v4-flash、max_tokens512；每进程1次stub/0意外请求，
模拟usage11/4，非空正文与completed事件齐全。未访问真实供应商/Keychain/Docker private pipe。
settings禁用及global-default写UNAVAILABLE仅为本任务受限验收profile，不修改普通产品profile。
首次缺AbortSignal、下一次断言误用turn字段的失败均保留；修正依据fixedSDK源码，无依赖安装。

helper SHA84284012be6934ee093f163b5c5ba136b6982ae7520d8481cfd20c4111b4e1ab；
SPEC APPROVE，QUALITY随后核对。task4b-sdk-execution-metadata.json追溯提取原工具参数、
env-i白名单/冲突值、session48946/77170及exit0，不改变原first/resume输出或伪称新执行。
OS PID、总耗时和精确时间NOT_RECORDED；源码身份在运行后核对，不是原子冻结或独立签名receipt。
这些遗漏与SDK/替身证明层保留，真实镜像、TLS/供应商usage、公开设置/模型管道仍NOT_RUN。

QUALITY批准helper固定SHA的窄测试代码；执行receipt认证仍PARTIAL，不为metadata遗漏机械重跑。
loadLayeredEnv会读cwd.env（当前不存在），env-i不独自证明boot后的全部环境；未来调用先检查
隔离cwd/.env。PASS输出在dispose前，必须同时消费退出0；15秒只是prompt之后settlement期限，
不是整个boot/call过程期限。普通profile不变、旧Native正文不变和当前source/输出hash有独立复核。

后续真实镜像的只读环境准备：当前宿主Darwin/arm64，Docker server可达，Desktop4.94.0、
Engine29.8.2、Linux/arm64 guest。仅version读取，不构建、不停止服务、不改daemon/代理。
这不是新镜像、生命周期或Linux设备认证；公开setup-web.sh --runtime docker --no-start仍待
新任务专属测试目录锁定安装/构建授权，真实Key和付费预算另外授权。

## Task4B 持久账本 v2/v3 与剩余质量修复

代码在既有私有credentials bind内引入固定live-acceptance安装叶、不可重置控制与永久锁；
运行时不创建授权，显式init拒绝已有叶，reserve提交前预扣、取消/失败/冷恢复不退款。
使用固定日期官方价格合同和完整上下文输入预留，不使用字符/4估算；到期仅拒绝新准入，
不能宣称远端发送、结束或计费一定发生在validUntil之前。
v2 Python166 PASS，Node15 PASS、格式PASS；v3测试修复解释器变量与普通CI的RWB_TEST_PYTHON一致，
真实RWB-only RED14/1→GREEN15 PASS，production源码不变，SPEC复审批准。
JS QUALITY批准窄guard/test范围；PythonQUALITY BLOCK：公共/内部函数无注解且全局旧债配置
不检查函数体，因此配置内own0不能作为新模块类型认证；init锁fsync异常路径漏关FD。
正在仅补类型契约与锁finally/fault fixture，v4需独立审查，不提前宣称整体通过。

证据历史：worker曾覆盖v1的final-*日志，原始v1日志不可复用；只保留原工具观测165项及已知hash，
不伪称完整日志已恢复。task4b-budget-evidence-history-note.md如实记录；v2/v3独立回执未覆盖。
完整相关controller原2FAIL仍未解决；新预算tests/管道或mypy旧依赖57条均不把此门转PASS。

新budgethelper单独改动原会走generic低风险，因此另补精确security/high-coupling L4规则与
既有guard测试catalog：RED1FAIL→policy/quota96PASS。原4C冻结保留，新policy两文件另存
task4b-budget-policy-review.diff，SPEC/QUALITY随后审核，平台与未知风险门不降级。

## 实际固定SDK＋当前guard＋BudgetStore fixture

helper冻结SHAa3d0e8e65741553045459efe4a29549202cfb0abdfc0ee2f92043887cbd3fcd1，
SPEC批准。首问ticket1 PID16358/5.840秒，独立冷恢复ticket2 PID19422/2.708秒；
fixture手动reserve3（不算upstream请求）后，正常SDKprompt实际guard拒绝budget_exhausted、POST0，
PID24787/7.481秒；三进程exit0。实际NormalLoop tools absent，provider/model/output512符合，
observer不修改options。metadata记录UTC/PID/argv/env/cwd/source+helper前后hash，dispose后才输出结果。
初次project/logs fixture因0775祖先安全拒绝保留，一次改用规范私有临时根，没有放宽生产guard。
本层真实使用SDK、guard和BudgetStore，但wrapper只是测试根/时钟fixture，不证明Linux固定CLI根、
Docker私有model pipe、镜像或供应商。生产v2后续类型/FD修复会改变hash；不得将此证明伪写为v4重跑。

该helper当前冻结获QUALITY批准，三机械metadata齐全、55秒进程timer/60秒外部界限；
只认证budget冷重开和拒绝，不单凭新分支认证历史正文恢复（早期SDK层/Service替身证据另记）。
零供应商fetch不是OS全网络封锁或脚本沙箱证明。

预算v4 SPEC/QUALITY均批准：helper完整TypedDict/Clock/request/record/FD类型，无Any/cast/ignore，
函数体实际检查；init fsync finallyclose故障已闭环。168Python/15Node实际通过，guard/JS同v3hash。
新canonical导入闭包包含并行最小runtime_mode修复，独立当前/shadow仍同57依赖错误，strict509依赖错误，
own0；最新日志hash1f43c05d…/0328981e…与旧冻日志不同，仅旧runtime_mode诊断行号+3，不涂改旧hash。
解释器/依赖/全局mypy配置未变，整体类型检查仍FAIL并保留旧债。

## 共享父目录初始比较的确定性缺陷与最小修复

按systematic-debugging/bugfix-evidence只做一个私有临时根受控交错：普通兄弟文件写入使
st_nlink/size/mtime/ctime变化，dev/inode/mode/owner不变，原初始stat/open/fstat抛changed。
parent-metadata-experiment.receipt.json为OBSERVED；首次confstr准备不兼容未到交错阶段保留。
此构造原因确定，不证明原完整controller两项失败的原因，原NOT_PROVEN/NOT_REPRODUCED不改。

仅runtime_mode.py初始比较复用既有退出语义：shared/node_only用nodeidentity，!node_only即时私有父
仍fullidentity；no-follow/目录类型/FD/inode/mode/owner/record/lock及退出检查、Windows代码均保持。
最近测试扩展初始阶段真实inode/mode/symlink负例；正确RED-v2 4FAIL14PASS，首版hook误早匹配private
仅改ownedfixture且单独记录。完整runtime-mode114PASS，安全邻接185PASS；Ruff/Black/isortPASS，
mypy旧57条归一化集合不变仍FAIL。SPEC已批准，独立Python安全质量复核随后执行。
两文件冻SHA a0fa4596…/d4ebb61c…，报告parent-metadata-fix-20261008-summary.md。
只有该真实共享依赖变更及相应安全审查通过后，才为当前候选重验相关controller门；不盲重复旧失败。

预算policy两文件扩展SPEC/QUALITY均批准，独立96PASS；原4C workflow/quota源码hash未改。

当前v4＋已审共享父目录修复重新实跑：controller/mode/caps533PASS180.85秒，
private model/backend/contract/supervisor/launcher484PASS、2既有opt-in SKIP36.67秒，
API58PASS360.03秒、1既有warning；caps21已在controller组合执行。原2FAIL回执保留，
新PASS只对应当前源码，旧失败归因仍NOT_PROVEN。Node相关十四模块334PASS14.13秒。
完整基线计划52路径、22本地门、5外部门；约束0违规、文档治理0违规、Python索引已生成并复核。

另以新依赖影响为触发，既有helper在fresh fixture重跑CURRENT v4＋shared-parent修复：
ticket1 PID4598/3.122秒、ticket2 PID4778/2.094秒、耗尽拒绝POST0 PID4895/2.197秒均exit0；
helper与九依赖前后hash稳定，task4b-sdk-current-execution.json机械回执SHA
065a8f45a47a2bad141584153b95cd9822b319446675926953bb91e1c77ffd92，旧回执未改。

## 公开Docker启动链预算激活缺口（v5待实现）

核对现有Compose/minimal host env/supervisor后发现RESEARCH_ACCEPTANCE_CONTROL不会进入正常
受管Docker容器；因此自定义SDK overlay证明不能认证公开Docker启动会启用预算。
最小恢复使用已存在的显式init私有授权文件：仅已验证staged Docker模型/安装绑定发现固定预算叶，
startup只读，无授权叶保持普通profile，有有效授权才启用原docker-text guard/受限overlay。
不新转发环境、挂载、全局开关或控制框架。Native/legacy行为保持；partial/corrupt/unsafe/expired
已有授权拒绝而不能回退无预算模式。仅真正缺base/ns/installation叶、且已存在祖先验证稳定才可None。
固定目的缺失路径遍历复用现有no-follow/pinned FD/目录验证，先补真实反例和公共supervisor/prepare契约。
上述v4门与SDK证明不伪称已验证未来v5代码；镜像、生产Linux CLI、真实Key/供应商仍NOT_RUN。

v5 SPEC批准、PythonQUALITY附Medium资源警告：根open后fstat在ExitStack登记前失败可漏FD。
v6仅提前登记close并补fault回归，真实RED0close→GREEN1close、187PythonPASS；SPEC复核批准，
质量复核随后确认。发现/授权/native/ledger语义及launcher/guard/JS都不变，旧v5freeze未覆盖。
v5普通Supervisor/prepare command链为合成staged/model叶/Gitprobe，明确不是实际镜像/挂载。

另一次必需service/integration/protocol组合6FAIL401PASS1SKIP，六项均因旧裸词private隐私断言
误撞新增公开能力名；不作为真实秘密泄露或生产服务故障。test_service_manager.py仅改为全报告
检查四个既有准确payload/error canary，并给missing/wrong Content-Type加入独有canary。
所有readiness/warnings与失败分支保持。最近6PASS、SPEC/独立PythonQUALITY批准；原FAIL保存，
完整组合与当前v6私有runtime闭包另存新回执，不涂改第一次结果。

最终v6 SPEC/QUALITY批准根FD修复；完整当前private-runtime503PASS2opt-inSKIP35.85秒，
修正canary后的service/integration/protocol407PASS1WindowsSKIP26.48秒，均新XML/日志，
原6FAIL仍保存。启动发现初始化仅下一次启动生效，生产init/真实Key/供应商仍未执行。
最终整分支只读CODE REVIEW批准local checkpoint，无新Critical/Important，但非merge/goal完成。
readme-review旧“JS尚待接入”事实已修；历史reading pin确实不含新增模块，尚未认证当前导航ready。
将先以本地真实源码checkpoint固化代码，再用该真实提交重绑定图册链接，保留两阶段身份，不造未来SHA。

本地源码checkpoint已正常提交80ebd728c410cbf3eedab13b868f6d9a92c500db，工作树提交后干净。
随后reading pin绑定此真实源码提交；它包含新增两个模块，不是未来/假SHA。图册和报告收尾
将另提交，源码身份与收尾身份分开。未推送，因此远端blob链接可访问性仍未验证，不能称发布ready。

reading pin重绑定后，原四模块治理108PASS6.32秒；完整分支a1d2087/eeb530c仍为祖先，
primary/旧worktree/数据/旧回执未重置或清理。当前阶段只完成本地源码合同及审查，不完成整个goal。
现行缺门：新任务隔离公开安装与current-image build/生产Linux CLI、真实Key与付费文本/重启续问/
同image重建持久化、三浏览器场景及macOS Bootstrap均NOT_RUN；其他设备职责保持交接，不伪称支持。
任何push/PR/CI/merge/tag/release/cleanup均未在本goal执行；等待分别明确授权，预算到期不得绕过。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在既有verification policy/catalog和普通Checks命令补齐模型及受管runtime测试，复用原planner/receipt、单Ubuntu job、权限与20分钟上限；无新验证框架、宿主、部署组件、平台矩阵或自动Docker触发，原完整未知/安全/外部门不降级。测试执行合同与真实镜像、模型和macOS CI证据分开。","diagrams":[]} -->

源码绑定已贯通Compose非秘密安装ID、normal supervisor参数、staged overlay和私有JS桥接。
首次SPEC发现新增env要求使旧正确owned实例不能status/stop：保留真实初轮596 Python/24 JS。
最小兼容修复后，合法空ID投影只授予原完整归属守卫下的生命周期控制，derived flag为false；
缺字段/非list/错误/重复ID仍拒绝，精确ID必须全部inspect通过才true，输入伪造值被覆盖。
缺绑定时四种模型操作拒绝而Hostrecords保留；旗标不证明目录安全/Key配置/模型调用。
修复RED3Fail、focus17PASS后完整Python609PASS/188.26秒、JS25PASS；SPEC和独立Python/JS
QUALITY均APPROVE。mypy59条诊断与actualHEAD shadow基线精确normalized多重集一致，整体FAIL。
Ruff/Black/isort/diffchecks PASS；真实Docker Go-template、新镜像、Key、请求/CI未执行。

当前完整27路径计划经原Git-bound planner为L4，12本地门及5外部门保留。
相同冻结输入的609三模块覆盖container-runtime及Docker半边；另实际执行service-manager、
local-integrations、protocol、runtime-mode、platform-capabilities，523 PASS/1 Windows实机SKIP，
1个既有Starlette/AnyIO弃用warning保留，30.70秒。不是把fixture记作实机PASS。
四模块JS相关完整验证再次实际104 PASS（含architecture），全部27路径Project Constraints
0 violation，architecture/governance/index复核PASS。真实镜像与外部门没有因local checkpoint变PASS。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"在既有私有credentials bind内增加模型叶和非秘密安装身份/参数绑定；Native overlay不变，无新mount、Host服务或部署节点。旧实例空ID投影保留原完整生命周期守卫但无模型能力，新精确绑定只在实际完整inspect后派生，不改变DSH唯一引擎或数据根，实际镜像和真实研究另行验收。","diagrams":[]} -->

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"当前JS私有pipe已经接入稳定安装ID/source绑定，继续委派原Host浏览器record；Native默认overlay不变，模型秘密只落在既有Docker私有credentials信任区或Native Keychain，无新部署组件、公开取密API、宿主bridge或第二执行循环。当前按实现合同记录，实际镜像及真实模型状态未验收且不借静态图推导通过。","diagrams":[]} -->
