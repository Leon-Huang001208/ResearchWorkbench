# 设置与真实能力闭环：累计任务报告

## 当前状态（2026-10-08：Word/Excel/PowerPoint 六项闭环推进）

| 项目 | 当前结论与适用范围 |
|---|---|
| 原模型与公开研究 | 已有真实生成、受控公开净值工具、快照与最终回复证据；只覆盖声明的 NAV 范围。T6 已通过；B 供应商归因用户已豁免，归因事实仍未验证。 |
| 兼容文本 | 独立 Ollama/Qwen2.5 无Key文本生成、普通research-web会话与Host/DSH冷重启已验证；不认证工具、多模态、带Key商业服务或研究质量。 |
| 商业数据 | 用户确认Wind/iFinD有可用账户；最新反馈为iFinD只有终端账户、接口权限不确定，未提供接口Token。Wind插件心跳通过，但一次封闭业务查询deadline/0行；不影响原公开NAV。 |
| 三项FILE | Word、Excel、PowerPoint固定样例均已从正常Web页面生成、读取、修改、下载并独立检查；Excel文件模式明确未重算。详见最新分项证据，不冒充原生通过。 |
| 三项NATIVE | Excel6b4a5a33真实5→10→保存重开10及清理PASS；PPT8b79b55d保存重开读回与用户视觉确认PASS；Word20124实际原生新建A、736389修改B、7f8014修改3，均正式Web入口保存/关闭/重开/完整读回/清理PASS，下载9项独立核对PASS。旧超时及失败记录保留。 |
| Word清理 | 用户已关闭其确认的旧测试报告且不保存；3f单文件访问允许后实际保存A，精确HFS/saved/读回核对并关闭，文件作为恢复证据保留。20124/736389/7f8014三个成功任务文稿关闭、临时目录删除已独立确认。历史归属不明对象仍UNVERIFIED，不补造旧文件身份或删除记录。 |
| hostAcceptance | 当前冻结候选52b3b01788f0af2fe7f60c60b98003c3679836eb：本地闭包通过所列范围，Project Constraints37808948653与Web Checks37808948533已通过；Mac Bootstrap37808948541运行中，故当前回执BLOCKED，不能沿用旧2d的Mac CI宣称新候选通过。Office六项固定样例PASS；DeepSeek实际选择Office工具、生成与交付已PASS，测试Key已清除，独立实例已停止。 |
| aggregateAcceptance | NOT_READY；mergeReady=false/releaseReady=false。Windows/Linux/Docker由所属任务留未验证，本轮不执行、不改全局平台规则。 |

当前Goal仅Word/Excel/PowerPoint、macOS Native+Web，不扩展金融插件或其他Office应用；旧商业接口记录保留事实但不重启其验收。原各轮结果和失败历史完整保留；旧段落当时状态不覆盖本节与最新记录。plan/receipt及脱敏证据仍在 `logs/settings-model-loop/`，不另建总报告；不更新生产、不合并或发布，本轮供应商模型请求0，意外未隔离测试的背景请求UNKNOWN另行保留，不将其伪写为绝对0。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"模型配置与显式测试复用现有Host/DSH会话路径；增加最小测试路由但没有新增执行器、组件节点或信任边界，API及运行文档已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"产品overlay通过固定DSH扩展点挂载模型provider，增加限定用途私有进程桥接和独立macOS Keychain边界；认证record保留原固定实现及独立文件。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"模型页收窄Provider并区分保存/应用/凭据/真实生成，继续使用现有设置、同源API及会话状态投影。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Automation仍复用相同ResearchService创建和提交原生会话；模型变更只应用新会话并在任务活跃时拒绝凭据变化，没有新增调度器、任务注册或图节点。","diagrams":[]} -->
<!-- architecture-review {"group":"local-integrations","structure":"unchanged","reason":"Office验证仍由现有Host本机管理器、独立验证进程与原生Office应用执行；仅在原私有状态中增加有界run登记、步骤及清理诊断和冷恢复，不新增服务、Vault、HTTP执行器或信任边界。Wind继续复用既有独立Excel客户端与Broker，实际接口/清理证据单列。","diagrams":[]} -->

## 基线与复用

- repo root：`/Users/leon/Desktop/Projects/ResearchWorkbench`；branch `master`；HEAD `d17459edeff5696d2a2641c4072c2d08e9ae84d0`。这恰好等于附件参考，但未执行回退。
- 原工作区没有跟踪文件改动；保留全部历史未跟踪报告、`.codex/` 及旧 `.venv` 目录。已有 worktree 包含 Native/Docker、startup-stability、leon-verification-shared-runtime、platform-aware-minimal-acceptance。
- 隔离实现：`/Users/leon/.codex/worktrees/settings-model-loop/ResearchWorkbench`；branch `codex/settings-model-loop`；基线同上。
- Native/Docker 分支在 `e043a4975`，与 master 的 merge-base 为 `4d6a4eff6`；`a1d208776/eeb530c8c` 及后续 Task13/14 成果仍在独立分支。其文档回执明确真实 Docker、macOS干净安装、ACL/Windows实机门未全部通过。本轮复用已知边界，不合并旧分支、不修改安装体系、不重做旧任务。
- 固定 DSH：`c919b2a460753859665db3f60143d525fb9140cf`，产品 Runtime 版本 `0.1.3-alpha.2`；真实目录仅 `deepseek-official` 的 flash/pro/vision-exp 三个 ID。Web 8088/DSH 3081 为现有 Native 实例。
- 本地 Python 3.12；既有主 `.venv` 无 pytest，因此复用 Native/Docker worktree 的既有测试环境，未安装依赖。Runtime/浏览器验证使用现有 bundled Node 24.19.0，PATH 默认 Node25 不作为受支持Runtime证据。
- Harness：`task-20261005-7d1187616adb`，独立不透明session键。初始化写 `.git/leon-engineering` 需沙箱升级，获允许后成功；未修改 Hook/runtime。

## 阶段 0 最小故障矩阵

| 路径与步骤 | 实际结果 | 期望 | 错误码/断点 | 证据类型 | 根因置信度/分类 | 所属阶段 |
|---|---|---|---|---|---|---|
| 模型初载：runtime GET → 页面Provider → 保存 | 后端provider为DSH，页面把DSH填入可编辑Provider，API只允许deepseek-official | Runtime标识与模型Provider分开，界面只展示真实支持范围 | invalid_request/422；页面→ModelConfig | 真实GET、源码、RED JS测试 | 高；产品缺陷 | 1A |
| 非支持Provider openai → PUT model | 422且无供应商请求 | 明确拒绝、无秘密回显 | invalid_request；Pydantic | 真实HTTP与fixture | 高；预期拒绝 | 0/1A |
| 默认research-web创建 → 最小生成 | 会话创建503，未到模型生成 | 专属preset可挂载 | agent-preset/invalid；research-tools读取未inject的spawnProcess | 真实DSH错误定位、Proxy失败测试 | 高；产品缺陷 | 1A |
| 配置保存/父子任务运行/部分失败 | 原实现先写共享Key，再逐个切空闲旧会话；活动任务未禁止共享Key更新 | 运行时拒绝变更，已有会话保留选模，拒绝/未知提交不得假成功 | 原无防护；configure_model | RED Python测试与固定DSH源码 | 高；产品缺陷 | 1A |
| 数据：独立data home → Broker选择eastmoney_fund → 000001 nav limit1 →快照读取 | 真实1行、status=snapshot、as_of=2026-09-30，读回1行；不是完整历史 | 公共来源真实只读查询并保留限制 | 无失败；供应商→snapshot | 真实Provider/Broker，非fixture | 高；此指定能力通过；原生研究消费初始被preset挂载阻断 | 0；后续数据扩展属于2，未实施 |
| 本机：GET local-integrations → Excel/Wind/iFinD分层 | Excel/Wind已发现但callable=false、待授权/待验证；iFinD专业终端macOS不适用 | 发现不冒充授权/可调用，不隐式启动厂商软件 | 无失败；厂商授权与真实调用未执行 | 真实产品状态；平台事实 | 高；平台/权限未验证，不是已调用 | 0；Office/Wind真实验证属4，未实施 |
| 模型凭据后端describe | configured=true/source=file/writable=true；固定源码使用私有.credentials.yaml | 不将私有文件谎称系统Keychain；不回填、不复制秘密 | 文档保证与实际后端不一致 | 真实非秘密describe、固定DSH源码 | 高；安全保证缺口 | 1A风险；未迁移/更换固定DSH |

## 实施及证据

- Provider输入固定 `deepseek-official`，过滤实际目录；API/service再次验证ID，不放宽字符串来假装多Provider。
- 保存与测试共用串行边界；凭据动作前先原子保存旧默认和uncertain标记，成功后提交新默认并清标记。旧会话保留选模，新会话创建时应用。父/子任务运行时拒绝变更。写入前只读拒绝保留旧状态；RPC开始后的取消、拒绝、传输或最终持久化失败全部保留uncertain并阻断新请求。固定DSH会把提交后的observer错误也映射为credential/rejected，不能把该码当作回滚收据。
- API增加互斥 `clear_api_key`，沿固定DSH `credentials.unset`；清除后阻断新消息。秘密提交即清空，响应/普通索引不含值，不读取Codex/Claude/cc-switch配置。
- 显式最小生成沿create/send/native history，60秒总预算、最多3秒取消等待；完成事件+最终消息+非空文本齐全才通过。固定错误映射区分认证、权限、限流、网络超时；不自动重试。
- 研究工具 `apply` 的子进程测试替身由第三参数提供，移除对禁止注入字段的读取，保留既有沙箱/工具白名单。
- 初始JS：8 pass/1 fail（Provider）；新增preset Proxy测试：9 pass/1 fail；修复后10/10 pass。Python新增模型隔离/活动拒绝：2 fail/1 pass；未知模型基线200误成功；修复后6项模型测试pass。回执未知/最终文本测试RED两失败，再GREEN两通过。
- 真实基线模型smoke在preset创建处停止；修复后用自有临时preset和18088 Host复用现有产品DSH凭据通道：生成会话`ed335966-31b1-4cd8-be83-4416e5a4469b`收到最终文本且无工具；研究会话`671591a6-89e3-446c-a1e7-2c55cbf3a819`恰好一次`datahub_get_fund_data`完成并收到最终文本。未读取或复制Key、未改变生产默认preset、未迁移旧配置。
- 该临时Host是共享专属DSH的有界验收，不是干净独立模型凭据实例证据。另启动13081空data home用于无继承验证；直接launcher最初未生成Host认证回执，记录runtime_auth_unavailable。随后复用既有管理器认证交换并重启同一临时Runtime：configured=false，原生preset创建成功；显式生成在模型请求前以model_credentials_missing阻断，没有复制现有Key。
- Runtime已应用不能由可达性推断。新增RED证明原先保存后仅健康可达就错误置真；修复后须实际session.selectModel，并将非秘密应用记录绑定认证文件代际（只散列设备/inode/修改时间，不散列秘密）。真实原生应用会话`7e4ec64e-e137-46a8-8fe1-d14c22fb2337`证明当前选择已记录，未请求生成。
- 原生trace已归档：生成16事件，SHA-256 `87ff9932042628824f6a0c296daa23d987884d9c2a26213321c745945aa14840`；受控工具21事件，SHA-256 `5b894aa37a200be498b68546a54852d5bb6d1a0df984040f46ddfa3f346d2c0b`。原文仅保存在0600本地证据，不回填对话。

## 实际命令与日志

- 基线：`git rev-parse --show-toplevel HEAD --abbrev-ref HEAD`、`git status --short`、`git worktree list --porcelain`、分支log/merge-base；只读读取规则、模块文档及策略。
- `./rwb web status --json`实际exit2（当前基线不支持此参数）；更正为`./rwb web status`。沙箱内PID/回环不可达不是产品故障；获授权的窄范围回环GET证明真实Web/DSH可达且owned。
- 聚焦RED/GREEN：既有测试Python运行`-m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -q -k ...`；`node --test tests/javascript/research_web_settings_ui.test.mjs`；完整日志在`/private/tmp/rwb-settings-*.log`，累计验收将在下文更新。
- 真调用：`rwb-settings-live-smoke.py`初始8088、修复后`RWB_SMOKE_URL=http://127.0.0.1:18088`重跑；`rwb-settings-public-smoke.py`真实Broker查询；`rwb-settings-native-facts.py`仅非秘密后端描述；`rwb-settings-preset-repro.py`定位固定DSH拒绝原因。
- 浏览器脚本`rwb-settings-browser-smoke.mjs`使用已安装Playwright/Chrome，未安装依赖。首次未知模型错误检查超时，真实定点诊断证明目录重绘丢弃用户字段并提交旧模型；修复为保留用户当前dirty表单DOM，秘密不进入应用state或服务端回填。重跑Provider、留空保存、错误保存保留默认、刷新不泄密、显式真实生成全部通过。
- 临时DSH上游启动日志输出认证链接，已立即对自己创建的日志脱敏并设0600；该链接不进入本报告。剩余证据只保留状态/版本/自己的测试ID，不包含秘密。

## 最终累计验收与停止状态

阶段0完成；1A实际修复与可独立验收的部分已完成，整体验收为`BLOCKED`。改动保留在隔离工作树，未提交、合并或发布；生产8088仍运行基线代码。主工作区与隔离工作树HEAD最终均为d17459e，未覆盖并发工作。

完整changed set为29文件：7个产品源码、4个测试、16个权威/生成文档、根README和本报告。精确清单见`logs/settings-model-loop/changed-files.json`；计划风险`full-delivery`、等级L4，保留unexpected_behavior/validation_failure，未改政策或降低门禁。

| 验证 | 实际结果/证据 |
|---|---|
| API最终全文件 | 44 passed；`api-final.log`，324.08秒；包含只读拒绝、共享凭据结果未知、取消冷恢复、保存/测试竞态、真实应用证明与非空最终消息要求 |
| 认证/原生协议 | 20 passed；最终client变更后的`api-protocol-final.log`含协议20项与当时API43项共63 pass；后续service只读预检不改协议 |
| UI关键闭包 | 67/67；`research-web-ui.log`；首次4项失败为模型动作分派错误，基线67/67，修复后重跑67/67，旧失败保留 |
| 模型设置/preset回归 | 10/10；`settings-ui-final.log` |
| 服务管理 | 248 passed；`research-web-service-manager.log` |
| 本机集成合同 | 45 passed、1 native Windows skipped；`research-web-local-integrations.log`；不能冒充Windows验证 |
| macOS沙箱 | 19 passed、1 converter skipped；设置固定DSH_SOURCE_ROOT后仅补跑该缺项1 pass，合计20项已实际执行；保留临时目录清理告警，不自动清理历史测试目录 |
| 架构/治理/跨平台合同 | 架构62/62、L4组合81/81；两个组合包含重复测试，不合计为独立样本 |
| 完整性/文档 | 文档治理、生成索引、doc-sync、完整changed set Project Constraints通过；首轮缺关联owner文档/新API inventory，按原门补齐，未删检查 |
| 真实生成/工具 | 最小最终文本、恰好一次datahub_get_fund_data完成；独立Native trace如上 |
| 真实公开数据/探测 | 1行净值快照保存和读回；同一显式probe终态completed/healthy，461ms，无failure_code；仅证明指定public能力 |
| 浏览器/Host冷恢复 | Provider固定、留空保存、错误模型保存不破坏默认、刷新不泄密、显式真实生成通过；自有Host重启后回执与默认恢复 |
| 干净Runtime重启 | 自有13081重启后不继承Key，preset可创建，无Key明确阻断；不等于带Key真实推理重启验证 |

Python/JS只读复审发现的竞态、取消/崩溃窗口、partial冒充final、确定性拒绝标记残留、未知模型清除fallback和dirty下拉目录状态问题均已修复。复审代理曾在缺少confcutdir时遇到sqlalchemy收集错误；加边界后的独立命令返回10 fail/1 error但具体异常被工具截断，保留为原因未取得，不用旧错误替代。根会话随后独立完整最终API与协议通过；没有把代理失败伪报为通过。

模型秘密实际位于固定DSH专属私有文件：观察到文件为普通非symlink、mode0600，父目录mode0755；没有读取文件值，也不声称Keychain、静态加密或Windows ACL保证。真实Key留空保留已在浏览器/Native通道验证；替换、清除、失败/回执未知与冷恢复由fixture证明，未更改真实账户Key。缺少独立安全录入的真实Key，因此带Key的完整生命周期和DSH重启仍未验。

前置所有权与凭据RPC各有15秒传输上限；生成执行段create/send/history为60秒预算，取消最多3秒，因此端到端最坏上限93秒，无自动重试。真实测试内容无业务材料，费用只限显式最小模型请求。普通保存/列表/刷新/Doctor不会隐式生成。

requirements/web.in、web.lock、setup_web.py及bootstrap工作流已核对，未改变依赖、安装入口或固定版本；没有重做安装体系。当前验证环境缺Black/Ruff/isort/mypy，未安装、未宣称执行；CLI/现有计划未替代这些缺项。Native macOS有上述本地证据；Docker、Windows实机以及新diff的GitHub macOS干净安装均未执行。

现有规划器要求的外部门Project Constraints CI、Research Web Checks、macOS Bootstrap和Windows Verify全部`BLOCKED`：未获push/PR/dispatch授权，且Windows工作流当前仅显式触发。旧HEAD/旧分支CI不能替代新diff。本轮没有申请或伪造远端receipt。最终`plan.json/receipt.json`保留完整29文件、10本地PASS、4外部门BLOCKED及未覆盖风险；既有validator实际exit0、valid=true、result=BLOCKED，`mergeReady=false`、`releaseReady=false`。最终receipt没有新的失败需升级，escalation.required=false；原来的升级信号与失败原文保留在plan与attempt日志。

Harness已记录任务blocked/external；本地机械回执校验passed不等于目标completed。`harness-enforce`不应通过未完成的交付，不绕过该硬门。

`harness-enforce`实际exit1：latest outcome is not completed/passed，符合上述阻塞。首条Harness命令附带说明且耗时归因不精确，已通过受管CLI追加更正：最终命令取自executed.json，耗时为各选中命令实测秒数之和取整数，不代表整项任务墙钟，也不作为效率或Token节省结论。4轮收敛分别为首轮复审、定点复审、累计门失败修复和最终原生合同/状态检查；此前记录不删除。

清理：只停止自建18088 Host、13081 Runtime并删除独占创建的单文件测试preset；逐端口验证18088/13081关闭、8088/3081仍监听。保留工作树、全部证据、生产默认preset和真实凭据；没有清理历史分支/工作区。当前缓存数据与trace为自建临时资源，可供后续审阅，不迁移用户目录。

下一阶段唯一目标：通过产品本机安全录入，在独立实例补齐真实Key生命周期、带Key的DSH重启及现有CI证据，关闭1A验收缺口。本轮不自动继续。

## 1A收口续接：C0—C2（2026-10-05）

本节追加本轮事实，不覆盖上轮历史结论。不重做阶段0，不进入1B或2—6。原branch仍`codex/settings-model-loop`，HEAD仍d17459e，原29文件修改保留；Native/Docker分支已前进到5788e469且另有fbf1f871整合worktree，只读核对，未合并。生产管理器只读证明8088/3081各自进程alive/owned/ready，PID为69730/68985；不以监听端口代替归属，没有停止或修改生产实例。

### C0代码身份与证据复用

未获本地提交授权，未提交。输入完整tracked diff及29文件内容/权限清单保存于`logs/settings-model-loop/closeout/input-tracked.diff`和`input-snapshot.json`（0600）。baseline Git tree为`18c1963339bb7f16e62c47e3ed2afbe4e335a327`，输入overlay快照SHA-256为`81c94bcd7d509e6d319afebcc67612b6c973b4e4ebdafd5dbe691baa12ea5a1a`，tracked diff SHA-256为`c2ae097b2c1552036c3016bc280a661fd864d4c929cca6d0e04a9836d48620f4`。这不是新提交SHA；报告后续追加会改变整体树摘要，最终快照另存，代码身份不能仅用d17459e。

旧真实生成/受控工具/页面/Host重启作为历史有界证据保留；共享3081的18088成功不升级为独立凭据生命周期。旧无Key的13081重启不升级为带Key重启。旧日志没有完整源码树摘要，不能追溯认证它们恰好覆盖当前全部未提交差异；C2受影响API/协议重跑，未变的preset/沙箱/服务管理等历史证据按范围复用。旧plan/receipt不删，新的收口计划/回执保存于closeout目录。

### C1安全合同核对与最小补丁边界

总架构`docs/ARCHITECTURE.md`仍承诺密钥进入系统凭据库。上轮README/运行模块文档对模型实际文件后端的描述是事实澄清，不是用户接受安全降级；C1尚未关闭。

实际链路：设置密码输入→ModelConfig→configure_model→固定ref `RESEARCH_DSH_API_KEY` 的credentials.set/unset/describe→固定DSH `LocalCredentialProvider`→DeepSeek每次resolveApiKey。后端优先级是继承环境、DSH_HOME/.credentials.yaml、调用cwd/.env、DSH_HOME/.env；unset只删文件ref，不禁用低优先级fallback。正常启动器屏蔽工作目录/home的.env并清理子进程环境，但这不能把文件后端变成Keychain，也不能替代对整个旧回退链的证明。模型ref文件、Host认证Cookie/签名grant、DataHub keyring是不同平面。

固定c919b2a提供`CredentialProvider`扩展点，定义resolve/describe/set/unset及record接口；DeepSeek在存在credentials服务时只调用该服务，resolve返回空即MISSING_CREDENTIAL，不再转环境。没有服务时才走ambient环境。由产品现有overlay更换credentials实现，可不浮动升级固定DSH；目前未修改DSH源码或依赖闭包。

最小产品侧方案（等待修改范围授权，未实施）：新增`runtime/model-credentials.mjs`和限定用途的本机keyring桥接，修改launch_runtime的owned overlay/绑定、service的非秘密后端状态，配套fixtures与权威说明。仅通过私有进程通道提供模型ref，按规范化data home派生非秘密命名空间；严格接受macOS系统Keyring，不接受Null/未经批准的降级，不把Key复制进DSH文件，不迁移生产Key，不新增通用取密HTTP API/全局daemon/第二个Vault。当前已有库真实backend类为keyring.backends.macOS.Keyring、priority=5；此元数据不证明写入、读取或Runtime取值成功。

重要依赖边界：全局credentials服务还承载`client-connection/browser-session`签名grant，BrowserAuth初始化必须使用modifyRecord/readRecord。不能只实现模型ref并丢弃record接口，否则会破坏Host认证；最小补丁必须明确保留原认证平面的行为或获准单独接入，不能拿认证token后端证明模型Key后端。固定DSH的签名secret可跨进程持久化，launch token每进程随机；现有auth文件设备/inode/mtime标识本身不是DSH PID/start-time证明，C4必须用受管进程身份与新代际共同核实，未预先重建身份系统。

### C2实际修改与检查

- 新失败测试实证：掩码保存返回200且触发写入；无Key普通研究返回202并发送Native prompt。修复main的秘密字段校验及send的凭据准入，掩码/空白拒绝发生于写入前；新提交在reserve/Native prompt前确认configured严格为True。已有accepted幂等回执路径仍复用，未新建事务框架。
- 来源投影原先硬编码dsh_private_file，环境fixture也被误报文件。失败测试后按受控source映射file/env/project-env/user-env/system-keychain，未知来源显示unknown；只报告来源事实，不将configured或来源标签当作正确应用证明。
- 合成值测试直接断言保留不写、A替换为新值、实例B不变、RPC值已变但回执丢失后cold uncertain阻断、由正常clear恢复、旧/新会话下一次send阻断、重录恢复。只在受控进程比较合成值，不打印值/秘密哈希，也不冒充真实OS命名空间隔离。
- 定点RED两个admission失败，GREEN两通过；来源RED一失败、GREEN一通过；合成生命周期+admission三个通过。阶段API/协议累计命令67项通过（当时API47、协议20），其后新增来源投影轻量用例单独通过；最终对应差异与静态状态写入收口回执。
- 原复审10 fail/1 error诊断：对现有同任务日志做一次有界检索，没有找回匹配原文。保留“原因未取得”，不把sqlalchemy收集错误代入不同执行，也不无限追逐旧环境。本轮相关闭包有独立重跑证据。
- 当前Ruff实际可执行，检查全部6个已改Python文件通过。Black/isort/mypy包的版本元数据虽在旧环境，但实际运行分别因click._compat/mypy_extensions缺失而启动失败；这属于工具环境BLOCKED，不是代码格式/类型检查PASS，也不等同已发现格式违规。已询问仅隔离开发检查环境安装权限，未安装、未改系统或产品锁。原报告“缺工具”由本节实际探测补充，而非删除旧记录。

### C3—C5的当前边界

C1系统存储补丁范围/安全合同未获明确确认，故未创建真实凭据测试实例、未共享或复制生产3081 Key，也未给用户未经归属验证的录入地址。T0—T6的真正独立系统存储路径均BLOCKED；保留原来的无Key/fixture证据，不升级为真实生命周期。Host重启、无Key DSH重启的旧范围如上；带Key DSH重启仍BLOCKED。只有一个真实Key不能宣称A→B替换，录入/替换/清除权限仍需单独明确。

本轮不提交、不push、不开PR、不dispatch、不merge、不发布。当前diff CI仍缺授权及对应source SHA，保留所有原政策外部门；尚未修改policy、缩小changed set或删除门禁。生产仍基线，修复仍是原隔离分支成果。本轮没有需要关闭的新测试进程或需清理的真实测试Key。

### 收口小批次的最终回执

C0完成代码/证据身份核对；C1完成边界调查但安全合同实施BLOCKED；C2完成上述三个实际缺陷的修复和可执行检查，静态工具其余三项BLOCKED，不能写C2全部完成。C3/C4未启动。两个异步授权问题分别是最小Keychain补丁范围、隔离安装检查工具；没有收到确认，不把选项预选或时间流逝当授权。

本轮没有将文件后端改称安全系统后端，也没有改fixed DSH。拟议最小范围必须把模型ref和认证grant区分清楚再获准：仅系统存储模型Key、保留认证边界、不复制Key进旧文件；如涉及固定闭包或新的依赖，另行明确授权。拒绝/不可用Keychain后端不得回退到文件。

本轮当前差异：ModelConfig的掩码校验、普通send的缺失/未知凭据准入、Runtime来源映射、对应fixture测试与模块说明。其他上轮成果保持。Python定点只读复审确认这三处没有新增实际bug；没有复审代替测试。`closeout/api-protocol.log`67 passed与`storage-source-green.log`新轻量用例1 passed为分开执行的证据，不声称一次命令68 passed；`closeout/settings-ui.log`10/10，当前政策其他本地门均实际执行PASS（本机合同中的Windows skip仍不证明Windows）。Ruff真实PASS；Black/isort/mypy启动依赖失败保留原始日志，尚无格式/类型PASS。

完整29文件计划仍full-delivery/L4，10个catalog本地门PASS、4个CI外部门BLOCKED。安全合同、静态工具、真实T0—T6、带Key DSH重启、当前代码CI均是额外未关闭风险，不会被catalog或回执校验抵消。收口`closeout/plan.json`、`closeout/receipt.json`实际由现有validator读为valid=true/result=BLOCKED；`mergeReady=false`、`releaseReady=false`。上轮plan/receipt和失败记录不删。

旧失败检索仅一次且无法取回原异常，标记证据不完整。本轮不无限重跑旧环境、不做生产故障注入。唯一报告的最终内容与所有代码变化完整覆盖在输出snapshot/diff清单；快照不等同Git commit。未获本地提交权限，仍保留未提交成果。

下一步唯一目标：获准实施不含文件/环境回退的最小模型系统凭据库路径，先关闭C1安全合同。

## C1 macOS Native 授权实施（2026-10-06）

本节是当前结论；上节的授权缺口是历史事实，已由用户《C1最小系统凭据库路径——授权与执行指令》解除。本轮仅实施该最小补丁和本地检查，不重做阶段0、不进入1B或2—6；无push、PR、dispatch、merge、发布或供应商请求。原 `codex/settings-model-loop` 工作树及既有同任务修复保留；固定DSH c919b2a、产品依赖锁、安装体系和生产实例未改。

### 实施与安全合同

- 新增 `app/research_web/model_credentials.py`、`runtime/model-credentials.mjs`；`launch_runtime.py` 的 owned overlay 禁用旧 ref provider，再插入产品 provider。固定DSH patch 的 name 是匹配条件，不能用同id改name冒充替换。
- 实际模型后端为 macOS Security.framework 的系统Keychain：直接选择现有 `keyring.backends.macOS.Keyring`（产品锁25.7.0）读取/清除，桥接使用原生 `SecItemUpdate` 原位替换，仅NotFound才 `SecItemAdd`，duplicate竞争只重试update。审查发现原keyring set先删除再新增的HIGH后，先建立失败测试再修复；复审确认关闭。失败不读取旧秘密备份、不先删除旧值；结果未知仍保留既有uncertain状态。
- 模型固定ref的resolve/describe/set/unset从不委托旧解析器；无环境、`.credentials.yaml`、项目/DSH_HOME `.env` 回退，也不从Keychain复制到文件。只散列公开canonical data home形成命名空间，不打印或散列秘密。
- bridge使用产品受管解释器，`-I -B`独立进程，固定ref/操作白名单；秘密仅通过私有stdin/stdout，argv/env/URL/普通日志/报告无秘密。回执8KiB、20秒上限；异常只输出固定错误码，UTF-8管道不截坏多字节数据。
- Host 的 `client-connection/browser-session`、readRecord/modifyRecord及原锁/生命周期继承固定LocalCredentialProvider，独立文件 `.browser-credentials.yaml`。模型缺失/清除/bridge失败均不卸载credentials服务，因此DeepSeek不进入ambient环境分支。旧模型Key不迁移，旧浏览器认证需重新建立，本轮不改生产凭据。
- `service.runtime()` 增加非秘密 `credential_code`：后端查询失败保留成功的Host健康事实，credential_configured=null、storage=unknown、稳定model_credential_backend_unavailable。该缺陷先失败再通过；活动任务保护、留空保留、替换/清除、取消、未知与恢复继续沿原状态机。
- 非macOS后端只在操作时失败关闭，lazy import避免使Host/设置页启动崩溃；本轮没有其他平台原生支持证据，不使用文件回退。

### 实際本地证据

新日志统一位于 `logs/settings-model-loop/c1-native/`；旧失败记录和closeout回执未删除。全部实际argv/退出码/耗时见local-executed.json、api-executed.json及补充回执，原始DSH启动认证输出只在测试父进程内存过滤，未落盘。

| 验证 | 结果与范围 | 证据 |
| --- | --- | --- |
| 新ref/record边界 | Python初始3 FAIL、JS模块缺失FAIL；实施后通过 | model-red.log、adapter-red.log、native-final-code.log |
| 替换失败 | 缺原位更新函数FAIL；SecItemUpdate失败不add/delete回归通过 | atomic-red.log、native-final-code.log |
| Runtime/模型状态分离 | 旧实现误报Host不健康FAIL；新状态与来源2 PASS | status-red.log、status-green.log |
| 真实Keychain合成生命周期 | 空存储不继承受控同名env/旧文件；写入、替换、重复读取保留、两个独立home隔离、删除后新进程不恢复；finally清除测试account | native-final-code.log，测试test_real_keychain_cross_process_lifecycle |
| 固定Runtime实际消费 | 正常产品prepare/私有profile/owned overlay、正式research-web preset及sessionController创建；直接调用挂载DeepSeek adapter的实际resolveApiKey，与合成值仅进程内比较，不是只查来源标签 | native-final-code.log、model_credentials_native.mjs |
| DSH冷启动 | empty → restart-with-key → restart-cleared，三个真正独立Node进程；第四次仅临时overlay故障注入/usr/bin/false证明bridge不可用仍挂载credentials且Host record可读可modify | native-final-code.log |
| Host认证 | 上述每个实际DSH进程的browser-session初始化及readRecord/modifyRecord通过，独立record文件不含模型ref/值 | native-final-code.log |
| API/协议 | 68 PASS；随后状态变更追加2项定点PASS，完整suite不重复重跑 | research-web-api.log、status-green.log |
| 服务管理/集成/UI | 248 PASS；45 PASS/1平台SKIP；79 PASS，不将平台skip宣称通过 | research-web-service-manager.log、research-web-local-integrations.log、research-web-ui.log |
| 文档/架构/索引/约束 | 政策catalog通过；实际diff架构检查零violation，首次错误CLI参数记录保留后按help修正；doc-sync通过 | 对应log及architecture-current-diff-final.log |
| Python静态 | 修改的10个Python文件Ruff通过；Black/isort/mypy仍BLOCKED，见下 | ruff.log及black/isort/mypy.log |

核心实际命令：产品Python `-m pytest --confcutdir=tests/research_web tests/research_web/test_model_credentials.py tests/research_web/test_runtime_launch.py -q`，显式RWB_C1_KEYCHAIN_TEST/RWB_C1_RUNTIME_TEST=1；固定Node路径和DSH源码路径为公开测试绑定，无模型Key环境值。另执行API/协议、现有规划器返回的L0—L4本地catalog、完整changed set Project Constraints、`node scripts/check_research_architecture.mjs --project .`、py_file_index、doc-sync及Ruff。完整参数以执行JSON为准。

### C2检查环境与真正剩余阻塞

已创建获准专用环境 `/private/tmp/rwb-c1-checks-20261006`，未改变系统Python、生产或其他worktree环境。计划用途为Black格式、isort导入、mypy类型检查与仓库pydantic.mypy插件；来源PyPI，沿仓库dev约束black>=23.7/isort>=5.12/mypy>=1.5/pydantic>=2。

安装命令被宿主PreToolUse Hook拦截：`Manual confirmation required; this Codex PreToolUse hook cannot request approval`。用户已有明确授权，并非仍待授权；未修改/绕过Hook。已一次请求用户在终端人工执行该专用环境安装。一次环境审计与实际三项检查均显示No module named；因此没有实际安装版本可报告，不能声称格式或类型检查通过。Ruff使用现有0.16.6二进制。产品bridge依赖已有产品keyring25.7.0与标准库，不依赖检查环境或开发者全局库。

### 本轮边界、代码身份与交付

完整changed set目前46文件，包含既有同任务修改、新provider/bridge、launcher/service、必要测试/文档、直接相关部署图/同哈希回执；完整路径及文件摘要见本目录changed-files.json和output-snapshot.json。待交付源代码以未提交overlay摘要或后续检查点为准，不能仅引用旧HEAD d17459e。基准Git tree仍18c1963339bb7f16e62c47e3ed2afbe4e335a327；不重置、不自动合并历史Native/Docker分支。

部署图通过Archify showcase 9/9及四视口包含性/明暗截图；Codex直接查看1440浅色、2048深色同哈希截图，记录实际视觉检查者，不冒称用户人工审阅。图形证据不替代凭据或供应商验收。

生产3081/8088只读监听仍分别PID68985/69730；本轮只启动/停止test data home的13081，未修改生产。Host重新启动：本轮NOT_RUN，旧证据保留；无Key/合成Key的独立DSH冷启动：PASS；真实供应商Key的DSH冷启动：NOT_RUN。

真实账户生命周期、获准A→B真实替换、真实生成/受控工具及真实Key冷启动均本轮NOT_RUN；缺真实替换归因、当前代码CI、macOS干净安装与政策Windows门仍不能用旧成功替代。四个现有外部门保留BLOCKED，不修改policy或缩小changed set。C1 macOS Native最小实现与合成本地证据已完成；C2静态三工具外部阻塞，1A整体仍BLOCKED，mergeReady=false、releaseReady=false。回执结构校验通过只证明回执合法。

正常门禁本地检查点提交的实际结果将在本节追加；秘密、auth材料、原始trace、logs、专用临时环境均排除。本轮完成有界工作后停止。

最终源代码与测试overlay SHA-256为 `15f3fb3b98664fe0b42d44df9719c736d7f8243392cd09b82d2dfa4a5f14bb8c`；包含完整changed set中全部app/tests文件的路径、内容SHA和权限，不是旧HEAD的别名。最终Native代码34 PASS。`final-plan.json`覆盖46路径，十个政策本地catalog PASS、四个外部门BLOCKED；`receipt-validation.log`实际退出0。首次绝对plan路径被项目CLI拒绝，记录于receipt-validation-initial.log，随后按要求使用项目相对路径，未改变验收结果。正常门禁提交前stage-safety.json排除了秘密标记、认证、trace、日志和临时环境。

工具安装的最小解除动作（已授权但被Hook拦截，pip尚未运行）为用户本机终端执行：`/private/tmp/rwb-c1-checks-20261006/bin/python -m pip install 'black>=23.7.0' 'isort>=5.12.0' 'mypy>=1.5.0' 'pydantic>=2.0.0'`，然后提供完成回执。本轮不为此改Hook、系统Python或产品锁。

本地源码检查点已按普通 `git commit` 成功：`55a5fdb9aa2208afcef4932f74453d24c3e58b80`，46文件，源码/测试摘要与上述最终验收一致。没有使用--no-verify，也没有修改Hook；当时Git工作区干净。此检查点不是merge/release批准，不改变BLOCKED结果。本报告的提交结果补记随后单独保存，源代码检查点与完整交付46文件集合仍保持上述对应关系；当前代码CI尚无证据。

下一步唯一目标：解除检查工具安装的宿主Hook人工执行阻塞，补齐C2的Black/isort/mypy真实检查；不自动进入真实账户验收或后续阶段。

## C2 静态检查收口（2026-10-06，当前结论）

本轮仅C2。输入分支 `codex/settings-model-loop`、HEAD `f641b8420bd4248872bbcfa26acf68fb06f17b95`，工作区干净；未回退55a5fdb9/f641b842或重做C1。此前安装授权已明确；人工安装后的专用环境经过实际检查，旧“等待人工安装/静态工具阻塞”已解除。无依赖安装操作、产品锁/固定DSH/其他worktree环境/生产实例变化，也没有真实Keychain生命周期、供应商请求、浏览器或图形多视口重验。

### 环境与检查范围

使用 `/private/tmp/rwb-c1-checks-20261006/bin/python`（Python3.12.13）。实际版本：Black26.10.0、isort9.0.2、mypy2.4.0、Pydantic2.13.5、mypy_extensions1.1.0、typing_extensions4.16.0；Ruff沿用既有0.16.6。`pip check`退出0、No broken requirements found；pydantic.mypy导入退出0，真实mypy运行也加载了仓库插件。环境证据见 `logs/settings-model-loop/c2-static/environment-executed.json`、tool-versions.json、pip-check.log、plugin-load.log。

完整交付changed set是原d17459e→当前分支的46路径并合并后续工作区改动，存于complete-changed-files.json；没有只检查最后一次报告提交。格式/导入/Ruff范围为其中10个Python文件：client.py、launch_runtime.py、main.py、model_credentials.py、service.py，以及test_api.py、test_model_credentials.py、test_protocol.py、test_runtime_launch.py、test_sandbox.py。完整命令的路径列表见python-files.json和static-final-executed.json。

类型检查沿既有 `.github/workflows/research-web-tabbit.yml:44` 的 `--follow-imports=skip` Web源码边界，覆盖本交付的5个app源码文件；测试fixture不扩为新的类型检查范围。通过 `--python-executable /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python` 解析现有产品安装依赖，仅只读复用，不把专用工具环境缺少Web依赖当作产品类型错误。不新增ignore、skip配置、Any或忽略缺失导入开关，pyproject/tool规则及workflow未改。

### 分别归类实际诊断

1. 工具环境：启动、插件、依赖冲突检查均退出0，无当前缺项。pip的不可写缓存提示不会阻断pip check，没有使用sudo或改系统权限。
2. 本任务引入：首次Black退出1，7文件需格式化；同版本/配置检查原基准的8个已有Python文件全部通过（black-baseline.log），新model_credentials模块与其测试不存在于基准。仅格式化app/research_web/client.py、main.py、service.py以及tests/research_web/test_api.py、test_model_credentials.py、test_protocol.py、test_runtime_launch.py这7文件，完整路径见python-files.json。isort初次即退出0；正确源码边界的mypy初次即退出0，无本轮类型修复。
3. 既有文件诊断：初次mypy命令未沿CI边界、默认递归跟随导入，产生37条诊断于15个未改文件，退出1。import-closure-classification.json逐文件证明内容Git blob与d17459e相同；原始日志mypy-initial.log保留。它们是额外导入闭包中的既有代码静态诊断，不是环境缺依赖，也不认证为本任务新增缺陷或全仓已通过。按原有CI边界执行，不自行豁免/修改规则或扩大为全仓整改；这些诊断仍保留未处理。

### 最小修复及真正通过的检查

Black只改7个目标文件。format-equivalence.json记录每个文件格式前/后内容SHA及完整AST（含type_comments）相等；只读复审独立确认，运行逻辑、字符串内容、导入顺序、Keychain/provider/bridge、安全边界及状态机均未改变。py_file_index生成命令退出0但未产生索引差异。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| Black `--check`，10文件 | 退出0，10 files would be left unchanged | black-final.log |
| isort `--check-only`，10文件 | 退出0 | isort-final.log |
| mypy，5源码，既有CI边界 | 退出0，Success: no issues found in 5 source files；既有numpy/transformers override unused提示保留 | mypy-final.log |
| Ruff `check --no-cache`，10文件 | 退出0，All checks passed | ruff-final.log |
| 离线模型合同 | 4 PASS、2显式deselected（真实Keychain/owned Runtime不执行） | offline-model-contracts.log |
| 文档、索引、完整diff架构映射、Project Constraints、L4相关JS合同、doc-sync | 实际退出0 | policy-current-executed.json及对应日志 |

所有工具实际argv、退出码与耗时在initial-executed.json、static-final-executed.json；首次检查及失败记录不删除。mypy命令使用既有边界参数、产品解释器依赖解析和私有cache；没有借安装成功或工具能启动宣称C2完成。

完整46路径仍由既有规划器判L4。格式修复只改变文本，全部受影响AST相等，因此C1中API/协议、服务管理、本机集成和UI行为证据可复用；原生Keychain、供应商、浏览器与多视口验收没有重跑。回执中对复用项引用原日志，并在reuse-evidence.json列明AST依据；重跑项使用C2当前日志。四个CI外部门继续BLOCKED，不使用旧HEAD/旧分支CI替代当前代码。

### 当前代码身份、结论与停止

格式后完整app/tests交付overlay摘要为 `6c391caf8d9d621f6d22b033a0bfe6661f41131df6ac80a7382aea71cc8efcd7`，与C1原字节摘要不同；行为复用由AST相等证明，不把旧摘要冒充当前源码。输入/最终提交身份及完整文件SHA见c2-static下snapshot/commit-snapshot记录；正常本地提交必要格式修复和本报告，不使用--no-verify，不push/PR/dispatch/merge/发布。

**C2必要静态检查已全部通过，C2完成。** 本轮停止。真实供应商Key生命周期、真实替换归因、带真实Key的DSH冷重启及当前代码CI仍未执行，1A整体继续BLOCKED，mergeReady=false、releaseReady=false。15个未改文件的额外37条导入闭包静态诊断保留，未声称全仓mypy通过；不自动扩展任务处理这些诊断或后续阶段。

## C3/C4 独立真实验收准备（2026-10-06，当前阻塞）

本轮仅C3/C4，读取当前规则、附件与C1/C2记录；实际branch仍codex/settings-model-loop，输入HEAD为b4405a839e55ccd1097374a4f1f854561c7823e0，工作区干净。没有回退、架构重查、C1/C2全量重验、37条诊断整改、C5或远端操作。供应商请求预算6、公开只读工具预算1；实际均0。

### 已实际完成的无秘密准备

- 创建仅本任务拥有的0700独立目录 `/private/tmp/rwb-c3c4-u_4bgdb6` 与data home `/private/tmp/rwb-c3c4-u_4bgdb6/data`；按该canonical路径派生独立系统凭据命名空间。通过产品固定用途桥接的describe返回configured=false/source=system-keychain/writable=true；只保留布尔/来源元数据，未获取、打印、散列或复制任何真实Key。
- 候选18088/13081经socket连接检查均空闲，但仅是候选端口，**没有启动服务、没有经过归属核验的设置页地址**，不能作为用户录入URL。生产3081/8088只读监听仍是PID68985/69730，未改变或读取生产凭据。
- 通过正常WebServiceManager的安装诊断及_require_installation_ready留证，而不是覆盖/猴补启动门。既有Python3.12.13、Node24.19.0、CJPY0.5.2和固定DSH c919b2a构建可识别；当前工作树没有产品自有.venv，独立根没有install/manifest.json和data/runtime/build-lock.json。实际门返回installation_not_ready，issue列表为install_manifest_invalid、environment_not_owned、web_lock_mismatch、cjpy_not_ready、dsh_not_ready、dsh_runtime_lock_mismatch。这些含有缺少非秘密安装证据导致的派生失败，不能据此宣称现有固定构建或依赖损坏。
- 预检事实、目录、端口、固定构建closure与零请求计数见 `logs/settings-model-loop/c3-c4-live/preflight.json`。未复制生产Key/auth、未写虚假环境owner marker/installed清单或伪造build lock；未运行可能默认影响生产根的setup-web入口。

### 启动日志采集阻断的最小复现

现有manager._spawn将子进程stdout直接写runtime.log，_runtime_launch_token再从该日志解析启动认证链接。用合成公开fixture、假Popen和禁用状态写入的离线复现，确认标准日志会持久化含token的认证链接；没有真实token/Cookie/Authorization、真实子进程或供应商请求。只保存 observedAuthenticationLinkPersisted=true 等元数据于startup-log-reproduction.json；原始合成fixture随本任务TemporaryDirectory退出移除。

这不是C3真实用户流程通过，也不是已实施安全修复。仅事后擦除日志或过滤对话输出不能满足本轮“启动输出的采集不会记录认证链接”。现有认证交接依赖日志，彻底移除需限定地调整launcher/manager的认证交接通道并保留原受控auth record，不能只屏蔽stdout使正常认证失效；不得用临时替代preset、直接改状态、关闭认证、通用取密接口或新daemon绕开。本轮还受受管环境缺失阻断，未临时引入新的安全交接边界；附件要求涉及新增安全边界时先保留最小后续范围。

### T0—T6当前回执

| 步骤 | 状态 | 当前证据或未执行原因 |
| --- | --- | --- |
| T0 空实例 | BLOCKED | 独立命名空间未配置及端口空闲已确认；正常启动门拒绝，因此Host/设置页与产品准入阻断尚未验证，不能标T0 PASS |
| T1 录入A/生成 | NOT_RUN | 未给出未验证地址、未请求录入、未保存任何真实Key |
| T2 留空/刷新/旧会话新请求 | NOT_RUN | 依赖T1；未复用旧幂等回执 |
| T3 B替换及归因 | NOT_RUN | 未录入A/B，也未推断可用Key数量；真实替换/归因未验证 |
| T4 清除/无Key冷启动 | NOT_RUN | 没有已保存Key或所属产品进程，不能冒称清除/冷启动通过 |
| T5 重新录入/真实Key Host与DSH冷启 | NOT_RUN | 依赖正常受管实例，未直接启动候选绕开安装门 |
| T6 正式preset工具与最终回复 | NOT_RUN | 真实模型0/6、公开DataHub工具0/1；尚未启用模型或工具路径 |

C3生命周期BLOCKED、真实替换归因NOT_RUN、C4真实Key冷重启NOT_RUN、正常研究工具路径NOT_RUN，分别记录，不合成为“连接通过”。C1/C2成功证据仍有效；供应商401/限流/余额/网络并未测试，不能写为此轮失败原因。

### 最小解除条件与停止/清理

首先需为**当前工作树与独立实例根**通过现有安装/受支持复用流程建立真正受管产品环境、匹配非秘密安装清单及Runtime build lock。不能手写owner/installed状态来让Doctor变绿，也不能默认执行使用生产data home的公开安装命令。新产品依赖安装不同于此前仅Black/isort/mypy的检查环境授权，须明确限定用途与作用目录；不改安装器源码、产品锁、固定DSH版本或其他worktree环境。其次需在保留正常Host认证的前提下，完成启动认证链接不落普通日志的最小受控交接，才能提供录入页；若需新增安全边界则另行收窄批准范围。

遇到上述外部准备阻塞后停止，不要求用户提供Key或“A已保存”。没有实际Host/DSH测试进程，没有保存真实Key，因此产品清除和所属进程停止均不适用，不能说已经执行清除。临时合成复现资源已清理；独立空data home及脱敏证据保留以便续接。没有清理生产资源、撤销供应商Key或修改系统权限/Hook。C5仍未执行，四个现有外部门继续BLOCKED，mergeReady=false、releaseReady=false；本轮C3/C4未完成。

## 隔离环境获准后的续接与T0（2026-10-06）

用户明确批准原工作树.venv及独立根内的产品环境准备，旧环境阻塞已解除，未重复请求整个C3/C4授权。沿现有SetupWebInstaller.prepare_environment/install_python_dependencies/verify_web_import准备冻结依赖，verify_dsh_source只读验证既有固定构建，再由原安装器写真实manifest/build lock；没有重建或改动固定DSH、产品锁、安装器或其他worktree环境，也未由安装器自动启动。安装器常规目录为 `/private/tmp/rwb-c3c4-u_4bgdb6/research-web`，此处成为后续唯一data home；此前 `/data` 仅做空命名空间预检，从未保存Key，不能冒充后续持久化验证。环境证据environment-preparation.json。

启动日志阻断已按既有直接缺陷修复授权实施最小补丁。新auth-output/auth-bootstrap产品preload在原DSH进程内处理输出；临时token使用同一个既有私有auth.json，原manager仍完成原Cookie交换，不新增daemon/Vault/接口，不重构模型Keychain/provider/bridge。先留下缺模块与旧日志解析的失败测试，再实现；JS3项通过，相关manager/runtime_auth/launcher闭包282 PASS。首次新增绑定误置导致3个launcher用例失败，已纠正并保留auth-related-regression.log，最终通过见-final.log。Black/isort/Ruff对本轮相关Python通过；service_manager直接mypy检查有24条既有诊断，未修改基准同边界同样24条（其中包含原37条导入闭包诊断的该模块问题），不增加ignore，不声称该模块类型全绿。新launcher没有类型错误，未扩大旧债务整改。

正常WebServiceManager.start(open_browser=False)已经通过安装门并启动独立实例，未绕过门：Runtime PID21918/13081，Host PID22500/18088，均valid/alive/owned/listening/protocol passed/ready。子进程使用仅公共运行字段的环境，不继承模型Key；本实例MCP/Automation关闭，不建立额外研究任务。日志中认证链接和Cookie/Authorization标记计数均0；认证材料只由产品原受控认证文件/正常交换使用，不进入证据。实际启动证据managed-start.json、T0.json。

**T0 PASS**：页面与设置模块HTTP200，刷新后实际浏览器模型页显示Runtime可达、凭据否、受支持DeepSeek-V4-Flash；产品新提交503/model_credentials_missing，在供应商前阻断。证据helper首次漏必需Idempotency-Key而先被422拒绝，纠正后沿同一已有T0会话完成，没有供应商调用，保留T0-header-rejected.json。T0会话dbbbee52-cb4b-4c2b-9023-e731d3dbb21d，正式research-web preset。现有settings.mutate设置llm-deepseek retryPolicy normal/maxRetries=0，未新建预算系统；后续逐次触发，工具路径请求数仍须逐步核实，不以提示词当作硬预算证明。

Browser辅助初始化因本机组件签名失败，未修系统签名/权限；经现有CUA浏览器入口完成一次无Key页面与刷新确认，未填/读取密码值、剪贴板或个人开发配置。录入入口 `http://127.0.0.1:18088/#/settings/model` 无认证秘密，浏览器tab1保留为人工交接。开始录入后停止截图、DOM、HAR/trace或请求体采集。当前真实模型0/6、公开工具0/1；T1—T6仍NOT_RUN，替换归因和真实Key冷重启均未验证。现在仅等待用户在该页面录入测试Key A并回复“A已保存”，不轮询、不推断完成。

完整交付changed set包含本轮最小补丁、必要测试/文档及既有成果，后续身份以快照/正常本地检查点为准，不用旧HEAD代替新代码。C5及外部门仍未执行，mergeReady/releaseReady=false。本交接点保留所属测试进程用于人工录入；最终结束再走产品清除并停止所属进程，现在没有已保存的真实Key可清除。

交接代码/测试overlay SHA-256为cca944e639cb152cf59b4a11aa0a534ec83ebc5bc297cbd2409330f065dd1a41，完整交付51路径，快照auth-fix-snapshot.json。JS最终84 PASS（含新增3项），初次新增FS fixture因macOS系统临时目录别名被canonical检查拒绝，已规范化fixture路径，不削弱产品检查；首次失败日志保留。协议20 PASS。进程实际started_at与project_root/data_root绑定见instance-ownership.json，不以认证文件mtime独立证明重启。安装器提交标识记录其环境准备时的e5fb2a19；本轮新源码由该overlay与后续本地检查点识别，不能用安装清单旧code_commit替代当前代码。新认证修复的相关门与未变模块旧证据分别记录；service_manager基准类型诊断、真实生命周期和当前CI风险不删除。

## A已保存后的T1/T2真实验收（2026-10-06）

用户明确回复“A已保存”后续接，输入代码565d8fb930a8ce5a152525b5d500e5b81cd1e56c、原分支与干净工作区已核对。本轮没有代码改动，没有重新读取/操作浏览器、密码框、剪贴板、认证材料或个人配置，也没有重复C1/C2或启动额外研究任务。

T1保存状态：独立18088的非秘密Runtime元数据显示configuration_saved=true、credential_configured=true、system_keychain、owned=true、configuration_uncertain=false，实际选择deepseek-official/deepseek-v4-flash。这仅是保存事实，真实推理另验。通过现有POST /api/research/runtime/model/test执行一次无工具生成，1.685秒返回passed；原生会话fe786a12-dd9d-4c8a-8c52-9b5865315189含一个step/start、一个非空assistant/message、completed turn，无assistant/attempt和工具事件，消息来源为实际deepseek-official/deepseek-v4-flash。T1真实生成PASS，证据T1-save-metadata.json、T1-generation.json、T1-native-proof.json；不保存请求体、原始历史或最终文本。输入清空/不回填沿已验证UI合同保留，本轮未检查密码字段值，不伪称再次观察过该字段。

T2：通过同一正常产品PUT模型配置接口省略api_key（留空保留），保存HTTP200；刷新GET确认仍configured=true，然后向上述**已有**会话用新的Idempotency-Key ebd4b88d88574c9fb1c9b4062311c5e5发新请求。HTTP202只记受理；1.012秒后新的completed turn与最终非空消息证明真实生成通过，一次step/start、失败attempt0、工具0。T2 PASS见T2.json。留空保存按现有语义清除新会话应用证明，刷新时runtime_applied=false；这不冒充凭据不可用，也不能用该字段否定已有会话实际生成。两次原生消息来源分别为seq12/20，同一实际模型。T2的保存/刷新由产品API执行，不宣称进行了第二次浏览器表单视觉验收。

实际模型请求累计2/6，公开工具0/1；已有retryPolicy maxRetries=0，固定adapter调用原生fetch并将错误交给既有retry协调器，没有SDK隐式重试层；两次各一个原生step及最终消息、失败attempt0相互印证。非秘密计数及来源见live-ledger.json；没有把预留请求直接当完成。T3尚待用户人工录入不同B，只有A时将真实替换与归因标未验证而继续其他步骤；T4/T5/T6仍NOT_RUN。C3尚未收口、C4未执行、当前代码CI未执行，mergeReady/releaseReady=false。

现在在T3人工点暂停：当前同一安全设置页只由用户录入不同测试Key B并保存，回复“B已保存”；若只有A则回复“只有A”。不能重复保存A冒充B，替换后生成也不会自动算完整Key归因；没有供应商非秘密按Key关联证据时保留归因缺项。此时保留所属测试进程与已保存的测试Key用于后续生命周期，最终结束再通过产品清除/停止，不提前清除中断验收。

## B已保存后的T3/T4（2026-10-06）

用户回复“B已保存”后续接同一实例，输入HEAD9a13e329、原分支与干净工作区已核对；没有源码变化或重复C1/C2。只读取非秘密保存元数据：owned/configured/saved均true，system_keychain、uncertain=false，选择未改变。以现有无工具显式生成入口发起第三次真实请求，1.590秒passed；新会话22a7c022-b9db-4eba-9e06-3c55880c8e28有一步、非空最终消息、completed turn，失败attempt0/工具0。T3“用户确认不同B替换后生成”PASS，证据T3-save-metadata.json、T3-generation.json、T3-native-proof.json；**实际Key B供应商归因未独立验证**，不能把生成成功或用户确认合成完整归因PASS，未读取/比较/散列真实Key。

T4产品清除：通过独立18088正常PUT模型接口clear_api_key=true，HTTP200且刷新configured=false。对T1已有会话及新建正式research-web会话65a1f915-b697-4e24-834f-1513b5631c41，各用新的幂等头发请求，均503/model_credentials_missing；没有供应商调用，见T4-clear-block.json。之后正常manager.restart_runtime(force=False)，只停止21918并启动56820；旧PID最终missing，新started_at1791256190.8045282，owned/listening/protocol passed/ready，Host22500保持运行。首次即时证据断言未满足，随后仅一次只读核对确认退出/恢复，不重复重启、不改产品状态或认证。保持同一canonical data home，重启后configured=false，且新旧会话再次分别以新的请求标识503阻断。**T4 PASS**见T4-cold-diagnostic.json及T4.json，证明没有旧Key恢复/环境或文件回退，不只是端口健康。

累计实际模型3/6，公开工具0/1，自动失败重试0。现在仅在T5人工点等待重新录入同一专用B，用户在原安全设置页刷新、录入并保存后回复“已重新保存”；不会推断已录入、轮询页面或读取字段。T5带真实Key的Host/DSH完整冷启动和T6工具路径仍NOT_RUN。测试Key当前已通过产品清除；为续接保留独立Host/DSH，不停止生产、不撤销供应商Key。C3生命周期尚待重新录入恢复，替换归因仍缺；C4未完成、C5未执行，mergeReady/releaseReady=false。

## 已重新保存后的T5与T6预算交互点（2026-10-06）

用户明确回复“已重新保存”，输入代码db41fad2、原工作树与干净状态已核对；没有源码或政策变化。仅读取独立实例非秘密元数据确认saved/configured/owned=true、system_keychain、uncertain=false，未读取、比较或散列Key，未采集浏览器/密码框/认证信息。

正常manager.stop退出独立Host22500及DSH56820；**启动新进程之前**核验两个旧进程均退出、13081/18088均关闭，见T5-stop-proof.json。随后正常manager.start(open_browser=False)从同一canonical data home启动：DSH68527/started_at1791256781.965151，Host68674/started_at1791256787.5810418，均owned/ready；没有再次录入Key，见T5-start-proof.json。非秘密配置恢复后，现有最小无工具生成入口在1.616秒passed，新会话0708ba72-dc7a-4d45-b685-c1a90f3fd487含一步、completed turn和非空最终文本，失败attempt0、工具0。**T5 PASS，C4真实Key完整Host/DSH冷重启及实际生成PASS**；不是页面刷新、auth mtime或configured=true替代推理。证据T5-reentry.json、T5-generation.json、T5.json。

累计模型4/6、公开工具0/1。T6尚未发起。检查固定原生loop与既有设置：公开只读工具自动执行；approval/policy ask只作用于原本要求ask的动作，不强制所有公开工具停顿；tool runtime仅有并发控制，repeat-tool-reminder只是提示，不是硬门；session.prompt无请求数/步数限制，项目现有tool guard为48调用/4子任务。剩余2次模型和1次工具额度无法仅凭禁重试、低输出或提示词保证。未修改固定DSH/preset，未放宽预算，未新增预算系统，也没有调用额外研究代理。本轮在这个必要条件核对上停住，不声称正常工具路径通过。

按用户“不能约束次数则先人工逐次触发”的备选，只询问是否存在能在工具/下一次模型请求前暂停的人工单步方式；没有收到答案不推断方式可用，不自行触发整段循环。若没有可用方式，则保留T6未验证并按产品清除测试Key、停止所属进程结束；不得用Host直接取数或另一个preset冒充Web→DSH→真实模型→原生工具→最终响应。这个交互点暂保留已保存测试Key与所属进程，以便用户选择；未执行最终清理，不能说Key已清除。

当前C3实际保存/留空/替换后生成/清除阻断/无Key冷启动/重新保存恢复均有分项真实证据，实际B供应商归因仍未独立验证。C4冷重启PASS、T6正常工具路径NOT_RUN，C5当前代码CI仍未执行；1A整体未完成，mergeReady/releaseReady=false。现有37条边界外及service_manager基准类型诊断原样保留，不扩大整改。

## 用户选择保留T6缺项后的最终清理与交付（2026-10-06）

用户明确回复“没有，保留T6缺项并清理”。未再次发起模型、工具或额外代理任务，未扩大预算或实现新预算系统。累计实际模型请求**4/6**、公开只读工具**0/1**；四次均一个原生step、最终非空文本和completed turn，失败attempt0，不包含T0/T4的产品准入阻断或普通HTTP/RPC。T6最终NOT_RUN：在现有范围内缺少可安全限制为剩余两次模型/一次工具的自动路径，也没有用户可用人工单步方式；不以提示词保证次数，不以Host直接取数、旧共享生产工具记录或临时preset替代。

结束清理实际PASS：先核验无活动测试会话，通过独立18088正常模型PUT clear_api_key=true清除，HTTP200并刷新credential_configured=false、configuration_uncertain=false。未直接编辑Keychain/状态文件，也没有撤销供应商账户Key。随后正常manager.stop只停止当前owned Host68674和DSH68527，两个PID均退出、18088/13081均关闭。证据final-key-clear.json、final-process-cleanup.json及closed live-ledger.json。生产8088/3081只读监听仍为69730/68985，未修改或清理生产；保留任务分支、环境、独立研究目录和脱敏证据，认证/原始trace/真实Key不进入Git或交付证据。

| 验收项 | 最终结论 | 范围与缺项 |
| --- | --- | --- |
| T0 | PASS | 真正独立无Key、正常受管Host/DSH、产品准入阻断 |
| T1 | PASS | 用户录入A、系统存储状态、实际一次无工具生成及非空最终事件分别证明 |
| T2 | PASS | 产品API留空保存/刷新、同一旧会话新请求实际生成；不伪称密码字段视觉读取 |
| T3操作及随后生成 | PASS | 用户确认不同B保存后，第三次真实生成通过 |
| T3实际Key供应商归因 | 未验证 | 没有独立非秘密按Key请求关联证据，未读取/散列Key补证 |
| T4 | PASS | 产品清除后新旧会话阻断、真正无Key DSH冷启动仍无Key及继续阻断 |
| T5/C4真实Key冷重启 | PASS | 同一data home，旧Host/DSH退出、端口关闭后启动新owned进程，不再次录入即可第四次实际生成 |
| T6正常工具路径 | NOT_RUN | 用户选择保留预算/单步控制缺项，未消耗工具或剩余两次模型额度 |
| 最终Key/进程清理 | PASS | 产品清除确认无Key，所属两进程退出；没有供应商Key撤销或生产清理 |

C3生命周期的已执行操作链有真实证据，但真实替换归因缺项保留，不能写成两个Key完整归因全部通过。C4真实Key冷重启通过，正常研究工具路径未验证；C3/C4本轮按用户选择结束，不标为完整1A完成。C5当前代码CI仍未执行，四个原有外部门继续BLOCKED，mergeReady=false、releaseReady=false。37条边界外与service_manager基准类型诊断继续保留，不修改policy/Hook/固定DSH/依赖锁或其他worktree环境，不push/PR/dispatch/merge/发布，也不自动进入1B或2—6。

本段为当前结论，前面“等待B/重新保存/人工方式”的段落是历史交互记录，已结束，不再后台等待或轮询。当前报告输入HEAD0c71d122，运行源码仍565d8fb9/overlay cca944e6（本阶段仅报告变更）；最终报告提交身份与完整51路径摘要见final-closeout记录，不用旧HEAD冒充新代码CI。

## 2026-10-06 C5 当前候选送检（有界执行）

本轮仅C5，用户明确授权普通任务分支push、唯一草稿PR和缺少的必要dispatch；没有真实供应商请求（0），未重开T6、Keychain生命周期或生产实例。输入工作树/分支为原settings-model-loop/codex/settings-model-loop，HEAD28f0263764e56d24ac12e45182f5134299600e32，工作区干净；origin为原仓库git@github.com:Leon-Huang001208/ResearchWorkbench.git。用户提供的提交只作为线索，没有reset、rebase或覆盖。

### 范围、代码身份与现行政策

原任务基线d17459edeff5696d2a2641c4072c2d08e9ae84d0至候选实际完整差异51路径，包含565d8fb9启动认证交接补丁。候选app/tests与565d8fb930a8ce5a152525b5d500e5b81cd1e56c没有差异，因此既有C1/C2和相关行为回归按对应源码复用，本轮不全量重验。候选Git tree、每路径摘要及完整文件集见logs/settings-model-loop/c5-ci/candidate-preflight.json；这些是代码摘要，不是Key摘要。

实际fetch后的master为9e231b6c3be5279d24cac8d43453fbf9a626cca6，双方merge-base仍d17459e，候选领先9、master领先16。PR三点差异51路径；两棵树直接比较81路径，其中包含尚未集成的目标分支治理改动，不能把81都称为本任务新增。只读git merge-tree定位唯一文本冲突docs/architecture/research-web/readme-review.json：候选updated回执与master unchanged回执冲突。未自动合并目标分支或历史Native/Docker分支。系统Git不支持merge-tree --write-tree，初次exit128原文已记录；改用传统只读三参数merge-tree，未改变工作区或索引。

候选现有规划器按完整51路径输出L4、10本地门、4外部门，plan.json退出0。master现行policy/AGENTS/Actions与workflow另存不可变快照，并用同一现有规划器在专用临时policy快照目录评估相同完整changed set，target-policy-plan.json同样要求四个外部门。没有更改policy或缩小范围；master新增平台政策没有被暗中覆盖。master已要求Windows真机checkout exact SHA后发起Windows Verify，workflow新增required expected_sha；候选旧workflow尚无该参数，二者差异明确保留，不能使用旧分支工作流冒充已遵循现行Windows验收责任。

### 费用、安全与实际远端动作

GitHub当前API确认visibility=public、非archived、push权限true。当前标准runner预算状态public-standard，included分钟上限对这些公开标准runner不适用（N/A），没有修改预算、付款、visibility或保护。最近各5次成功macOS/Windows运行的run ID、实际job起止和runner labels保存于budget-preflight.json，内部保守权重仍macOS11/Windows2。当前两项新run已经在标准runner启动，不以旧billing-blocked或历史成功替代当前事实。

候选路径/标记预检未发现秘密标记或禁止artifact路径；补充所有9个提交71个更改blob的检查同样0命中（commit-artifact-safety.json）。扫描只保存计数/文件身份，不输出疑似值。既有bootstrap只白名单上传doctor/connections/root/app，失败另含安装日志；不采集data home、auth.json、Keychain、真实Key、HAR或raw trace。Desktop Release仅tag/manual，普通任务分支push/PR不会发布/部署。没有读取个人开发工具配置或生产凭据。

实际执行git push origin HEAD:refs/heads/codex/settings-model-loop，exit0，新建同名任务分支，非force；之前远端该ref为404、同head PR列表为空。gh pr create --base master --head codex/settings-model-loop --draft --body-file /private/tmp/rwb-c5-pr-body.md退出0，创建并附加唯一草稿PR https://github.com/Leon-Huang001208/ResearchWorkbench/pull/78 ，标题和正文明确“1A尚未完成，仅送检”。PR head=28f0263764e56d24ac12e45182f5134299600e32，base=9e231b6c3be5279d24cac8d43453fbf9a626cca6，mergeable=false/dirty，merge_commit_sha=null；没有PR合并结果或可用merge-ref源码证据。

PR冲突导致自动运行列表为空；仅对未覆盖独立门执行gh workflow run research-web-checks.yml及research-web-bootstrap.yml --repo Leon-Huang001208/ResearchWorkbench --ref codex/settings-model-loop，两命令均exit0。没有Windows dispatch、rerun或第二轮修复；没有实际CI失败需要修复的证据时，不预先修改产品。

| 外部门 | 本轮状态 | 精确送检范围与限制 |
| --- | --- | --- |
| Project Constraints/check | BLOCKED | 当前workflow仅PR/master push，无dispatch；PR冲突阻断自动触发，不能向master push或改workflow绕开 |
| Research Web Checks/checks | PASS | run37411987879、attempt1、workflow_dispatch、ubuntu-latest、head28f02637 |
| macOS Bootstrap/Clean Web install (macos-14) | IN_PROGRESS | run37411993900、attempt1、workflow_dispatch、macos-14、head28f02637；正在干净安装，尚不能标安装/启动PASS |
| Windows Verify/windows-local-integrations | MANUAL_REQUIRED | 现行master政策要求Windows真机发起exact SHA；本宿主macOS，旧候选workflow与新expected_sha合同差异保留 |

run/attempt/event/head、job ID/runner/steps及PR head/base完整记录见runs-snapshot.json、pr-snapshot.json。运行head_sha不独立证明最终实际checkout：Research Web Checks完成job日志已提取Checkout精确SHA28f02637并保存checks-checkout-evidence.json；Bootstrap未完成，该证据字段仍保持null，绝不把PR base、head、merge-ref混用。CI仍运行时有界交接run ID，不承诺后台继续轮询。

C5仅部分送检，未通过；1A仍未完成，mergeReady=false、releaseReady=false。B实际供应商Key归因仍未验证，T6仍用户选择NOT_RUN；37条边界外和service_manager既有类型诊断保留。本地报告收口提交若改变HEAD，只代表报告变化，不宣称两项旧run测试过该新HEAD；远端PR候选保持28f02637，源码等价另由最终身份记录证明，不制造报告提交触发重复CI的循环。

最小剩余条件：经明确整合授权处理master治理变更与README回执冲突，形成可触发Project Constraints的候选；在Windows真机按当前exact SHA合同发起Windows Verify；完成两项已启动run的结果与实际checkout证据。此处没有申请或执行合并、发布、真实Key验收及后续阶段。

本轮文档治理和完整51路径project-constraints-local实际exit0；不重跑未变源码的C1/C2与浏览器/Keychain。receipt首次校验因缺少精确external_gate_not_run:research-web-bootstrap字段exit1，初次日志保留receipt-validation-initial.log；补充真实未运行风险后同一现有validator退出0、valid=true/result=BLOCKED。回执NOT_RUN描述的是Bootstrap尚无完成验收证据，实际运行状态仍IN_PROGRESS；它不是未触发。校验通过不等于C5完成。收口仅提交本报告，本轮必要产品修复0、供应商请求0、复跑0；最终本地提交与远端候选对应关系保存在final-code-identity.json。

## 2026-10-06 C5 续接：固定目标整合与重新送检

用户明确批准master进入原任务分支，禁止反向合并PR/master发布。实际输入HEAD为b7da60b692f62a01e4c7f8db7d7f7dcda2b9ab82，工作区干净；一次fetch后固定目标9e231b6c3be5279d24cac8d43453fbf9a626cca6，远端任务head仍28f02637、PR78仍草稿。保持既有本地提交，正常merge --no-ff --no-commit固定SHA，没有reset/rebase/force或合入未进master历史分支。

目标自d17459e共同基线涉及16提交42路径，包括现行AGENTS、平台规划、Windows exact-SHA工作流及受控Windows停止修正；产品源码只有service_manager的非强制taskkill失败允许等待/升级条件变化。逐项核对自动合并后只有这一行app源码增量，模型ref/Keychain桥接、启动认证私有控制文件和其他安全修复均保留；变更受既有归属校验限制，没有新凭据合同或大迁移。

唯一文本冲突为readme-review.json。实际核对三边README和回执后，README仍保留模型支持/Keychain/no-fallback/其他平台限制及安装与Doctor入口；目标README相对共同基线未变。回执记录updated，因为README相对固定目标有模型说明变更，并明确Codex实际文本评审、不是人工或截图验收。现有schema严格只有schemaVersion/disposition/summary/reason，不支持readmeSourceSha256、readmeStatus或reviewedBy；未为附件字段扩造schema，实际README摘要和Codex身份保存在c5-sync/readme-review-evidence.json。无未合并路径或diff-check错误。图内容及图规则未变，复用已有视觉证据，不重新跑多视口截图。

三类完整集合保存scope.json：原任务基线→整合后81路径、新PR相对固定目标51路径、整合前→后42路径。整合后现有policy完整范围规划L4，15本地门、4外部门。没有固定旧51上限、缩小范围或改policy。新治理合同和workflow虽非本任务新增，仍在81路径交付/整合检查范围内。

本地真实检查：文档治理、生成索引、完整81路径Project Constraints退出0；治理/平台/架构/认证输出JS合计185 PASS、0skip；受影响Python（service_manager、runtime_launch、local_integrations、setup_web、protocol）退出0，详见affected-python.log。service_manager Black/isort/Ruff只读检查通过，未重做C2/全仓类型整改。37条边界外和既有manager类型诊断保留。未变的API/UI/模型凭据源码和对应测试证据按源码相等复用；没有重跑真实Keychain、供应商或浏览器生命周期。完整实际命令、退出码和耗时保存local-results.json及日志。

旧Research Web Checks37411987879和Bootstrap37411993900均completed/success，实际checkout28f0263764e56d24ac12e45182f5134299600e32已从完成job的Checkout日志提取。精确run/attempt/runner/结果保存c5-sync/old-run-*.json；旧证据不标成新候选通过。当前API visibility=public/push权限true，当前标准runner预算public-standard，最近各5次native成功job保存native-budget-history.json；不改付款/额度、policy、Hook、fixed DSH、产品锁或生产实例。

本轮集中合并提交后普通push同一任务分支，复用草稿PR78；后续自动CI按冻结候选记录，新候选完整SHA和Windows交接在送检证据/收口段填写。本段为送检前已发生事实，不预称CI通过。供应商请求0，B归因未验证，T6仍NOT_RUN，Windows未发起；C5/1A尚未完成，mergeReady=false、releaseReady=false。

### C5 续接送检身份与 Windows 交接（冻结候选）

正常merge提交/冻结候选H为**a4406b42d3b35635968941cf2b27990a4a71a96c**，父提交b7da60b692f62a01e4c7f8db7d7f7dcda2b9ab82、9e231b6c3be5279d24cac8d43453fbf9a626cca6；普通push原分支成功，旧报告提交保留。PR78仍草稿，head=H/base=固定目标，mergeable=true，文本冲突解除。新PR merge preview **24069c23e590258dc7b09935fcd7082bdb32e036** 的API父提交恰为固定base和H，不能把这个预览提交叫做已经合并master。只读API复核master未漂移。

| 本轮自动门 | 结果（收口观测） | 源码及证据 |
| --- | --- | --- |
| Project Constraints/check | PASS | run37414820417、attempt1、pull_request、ubuntu-latest，实际Checkout24069c23e590258dc7b09935fcd7082bdb32e036 |
| Research Web Checks/checks | PASS | run37414820502、attempt1、pull_request、ubuntu-latest，实际Checkout同一merge preview24069c23e590258dc7b09935fcd7082bdb32e036 |
| macOS Bootstrap/Clean Web install (macos-14) | PASS | run37414820465、attempt1、pull_request、macos-14，干净安装、固定DSH构建、服务启动/Doctor/资源/未配置数据源断言完成；实际Checkout24069c23e590258dc7b09935fcd7082bdb32e036 |
| Windows Verify | MANUAL_REQUIRED | 本轮Mac不代发；当前真实workflow要求expected_sha，交给Windows真机检出H后执行 |

元数据、steps、runner、checkout精确提取见c5-sync/runs.json和pr.json。全部新run由PR自动触发，无重复dispatch/rerun或第二轮修复。gh pr edit初次被GitHub classic Projects弃用查询拒绝，改用现有REST PATCH原PR正文成功；没有改规则或另建PR。旧两项成功仅属于28f02637，仍单独保存。新本地Python确切391 passed、1 skipped、1 warning/39.59s；唯一skip为已有test_local_integrations中requires a native Windows runner的测试，不作为Windows能力通过或政策豁免。

Windows可执行交接保存**logs/settings-model-loop/c5-sync/windows-handoff.ps1**，填入真实40位H，步骤为：在Windows真机的全新TEMP验收目录Git clone原仓库、fetch原任务分支、detach检出H；读取AGENTS、actions-budget和实际Windows workflow；验证本地HEAD=H、远端refs/heads/codex/settings-model-loop仍为H；记录非秘密OS、checkout和发起命令证据后执行：

```powershell
gh workflow run research-web-windows-verify.yml --repo Leon-Huang001208/ResearchWorkbench --ref codex/settings-model-loop -f expected_sha=a4406b42d3b35635968941cf2b27990a4a71a96c
```

命令必须从完成上述核对的Windows真机发起，不能单凭expected_sha宣称发起设备证明。脚本对远端漂移/clone/checkout/dispatch失败停止，不自动retry或换SHA，不覆盖生产目录，不安装依赖或索取Key。若无Windows机器保持MANUAL_REQUIRED。Windows runner CI成功仅证明workflow合同，不能代替Windows本地安装/升级/Office/Wind/企业网络验收，也不证明尚未实现的Windows模型系统凭据库后端。

报告收口仅本地提交；远端任务分支冻结H供Windows验收，不为报告再push/重跑。最终报告HEAD、H及source差异另存final-identity.json。受管manifest逐文件摘要0不匹配，完整81路径安全标记/禁止artifact路径0命中，见safety-and-manifest.json；没有真实认证资料上传。必要回归已完成，未修改产品锁/fixed DSH/Hook/policy来凑结果。图证据按内容与规则不变复用，其他未变API/UI证据按相同源码复用。

**C5仍部分完成，1A仍未完成；mergeReady=false、releaseReady=false。** 三个自动门已取得相同合并预览的精确PASS；尚缺Windows真机exact-SHA CI及B实际归因/T6（后两项本轮不重开）。供应商请求0，不合并PR，不发布、不修改生产，不自动进入后续阶段。本次按有界观测交接运行ID，不承诺后台持续执行；若Bootstrap继续运行，该状态不是PASS。

## 2026-10-06 macOS Native 优先：当前阶段结论（替代旧 Windows 交接要求）

用户明确决定本阶段只推进macOS Native，Windows/Linux产品验证暂缓，未验证事实保留但不再阻断Mac。AGENTS的Current Research Web delivery phase是唯一阶段权威；安装/工作流/费用说明引用它。本轮不执行旧windows-handoff.ps1或Windows dispatch，不索取Key/供应商请求（0），不重开T6、不进入后续阶段、不改生产。

输入HEADc0ac36f4ba2b4c7f4e9e972ccf35856740a78811、工作区干净。保留a4406b42d3b35635968941cf2b27990a4a71a96c及其实际CI merge preview24069c23e590258dc7b09935fcd7082bdb32e036；三个自动门已PASS，准确收口为**该候选C5 macOS范围自动门通过**。本轮治理修改产生新候选后，旧成功不冒称新HEAD成功；产品app源码完全未变，已匹配的C1/C2、T0—T5及图视觉证据复用，37条边界外与manager既有类型诊断保留。

现有schema/规划器没有任务目标平台开关；最小实现使用原policy规则ci选择，暂不选择Research Web Windows gate（包括共享依赖/Git平台相关路由），保留catalog、workflow、expected_sha、现有Windows代码及桌面独立边界。平台维度仍保留潜在跨平台影响，不误称其他平台已实现；风险/unknown fallback/L4/完整changed set和Ubuntu通用CI均不降级。未来用户重新开启Windows时恢复相关路由选择；直接fixture合同证明重新选择Windows会重新要求原门。本轮没有改全局Hook、受管kernel/manifest/schema或新增框架。

先新增Mac阶段合同取得实际RED，随后最小policy/直接期望调整；178条阶段、恢复Windows、回执防伪、费用、架构和文档合同实际PASS/0skip。首次旧Windows硬门期望的失败与定位脚本错误保留在macos-first日志；防伪回执测试仍针对实际必选Project Constraints，未删测试或放宽断言。没有产品源码变化、依赖安装、供应商或真实Keychain生命周期重验。完整范围和本轮增量另存scope.json，现有plan仍要求三项通用/Mac自动门，Windows不再是所选门；未执行的平台在说明/风险记为用户暂缓，未写成PASS。

Mac基础模型链路已有真实证据：设置保存、系统Keychain、留空保留、替换后生成、清除后新旧会话阻断、无Key冷重启及带Key Host/DSH冷重启恢复。B实际供应商Key归因仍未验证；T6正式Web→DSH→模型→公开只读原生工具→最终回复仍NOT_RUN，原预算/单步约束障碍保留。Mac基础能力可用不等于完整研究工具链、完整1A或正式发布完成，平台范围变更不豁免这些功能项。

### 已核对的独立 Mac 运行入口

工作目录 `/Users/leon/.codex/worktrees/settings-model-loop/ResearchWorkbench`；独立实例根 `/private/tmp/rwb-c3c4-u_4bgdb6`，data home为其research-web子目录，Host18088/DSH13081，固定DSH c919b2a460753859665db3f60143d525fb9140cf、原产品专属.venv和已有真实安装清单。现有公开./rwb web start/stop/status/doctor入口默认8088/3081，没有独立端口参数，因此本独立实例复用正常WebServiceManager的已有构造参数/归属与安装门；不运行默认入口去占用或改变生产。

任务专用启动薄入口 `/private/tmp/rwb-c3c4-u_4bgdb6/macos-instance.py` 仅调用现有manager，支持start/stop/status/doctor，不处理凭据，不绕过门禁，不是新产品启动系统。在上述工作目录可执行：

```bash
.venv/bin/python /private/tmp/rwb-c3c4-u_4bgdb6/macos-instance.py start
.venv/bin/python /private/tmp/rwb-c3c4-u_4bgdb6/macos-instance.py status
.venv/bin/python /private/tmp/rwb-c3c4-u_4bgdb6/macos-instance.py doctor
.venv/bin/python /private/tmp/rwb-c3c4-u_4bgdb6/macos-instance.py stop
```

正常启动且status显示两owned服务ready后，设置页为 `http://127.0.0.1:18088/#/settings/model`。本轮补一次无Key受管启动/Doctor/首页检查：产品ready、安装ready、首页200；model_ready=false是未配置Key的预期状态，未执行真实生成。一次错误GET /api/research/settings/model返回HTTPError，此路由不存在，记录保留，不标模型状态API通过；正式API为/api/research/models和/api/research/runtime/model。随后正常停止所属测试进程，最终status两服务missing/ports closed。独立实例当前未运行、Key仍未录入；重新启动后才访问上述页面。不要把旧ambient浏览器地址当成当前在线证明。

日常生产8088/3081没有修改/停止/升级/迁移，**生产仍未更新到本任务候选**。本轮只是可重复使用的独立Mac候选入口。原安装门、真实manifest/固定构建校验复用，不手写安装证明、复制生产凭据或读取个人工具配置。

### 本轮新候选与有界自动 CI

新候选**e917b1c8923dd9aeef3b542b22f42ffc60c53dc1**已正常提交并普通push；产品app、requirements和公开entrypoint相对已验证a4406b42完全无差异。完整历史差异82路径，本轮增量9路径（包含报告），相对固定PR目标58路径，scope/candidate记录保留；此前scope在报告追加前列8增量，最终身份按实际Git补记。本轮不另合master或改PR目标。当前stage规则/文档与直接合同产生新CI，不借旧成功替代。

自动新run：Project Constraints37418741494，Research Web Checks37418741436，macOS Bootstrap37418741358；均pull_request/attempt1，head=e917b1c89，PR仍草稿/MERGEABLE/base9e231b6c。当前Project Constraints已PASS，其余最新状态见macos-first/runs.json；完成项实际checkout与PR merge preview另存pr.json，不混用head/base。没有Windows/Linux产品运行或重复dispatch，旧windows-handoff.ps1仅为历史文件，不执行、不要求用户执行。

当前政策catalog的mergeReady/releaseReady只计算所选机械门，不能认证B归因/T6或代表合并/发布授权。原完整1A及正式研究工具链仍未完成；报告的整体交付判断保留mergeReady=false/releaseReady=false直到所需功能证据闭合，即使后续Mac catalog三个自动门变为PASS。Windows/Linux暂缓不属于该功能阻塞理由。新自动检查若交接时仍运行，仅保留精确run ID/状态，不承诺后台持续执行；已有H/M的Mac C5自动门PASS不受此报告变化抹除。

此次范围修改、无Key入口确认和Mac能力交接已完成；未发现本轮新增阻断Mac启动的产品缺陷。B归因需要非秘密的供应商请求归属证据，T6需要明确获准且可约束请求数/工具执行的人工单步或等效现有路径，不能拿提示词保证或用户暂缓平台替代。本轮不建设预算系统、不重开真实验收。后续报告仅本地补记、不为报告无限重跑CI；生产仍未更新，独立实例停机。

最终有界观测：新Project Constraints和Research Web Checks均PASS，实际checkout均8b3678d41483cf3520c5ae579632e5d820fddd9c（PR merge preview）；新macOS Bootstrap37418741358仍IN_PROGRESS，不标PASS、未dispatch。回执仍因该Mac自动门尚无完成证据而BLOCKED，external仅3项，Windows不参与阻塞。本轮无生产更新、供应商请求0、独立实例已停机。

### 2026-10-06 自动续接：Mac 当前候选三门最终证据

已复核原工作树HEADd0bf8207982c8a063b4c1d3475ccbc713b4f470b/干净，上一轮属于阶段规则落地及入口验证的实际进展。本轮只续接已存在Bootstrap run37418741358，现已completed/success；安装、服务启动/Doctor、资源读取、未配置数据源断言和正常停止各step均成功。实际checkout为8b3678d41483cf3520c5ae579632e5d820fddd9c，父提交由GitHub API核实为固定base9e231b6c3be5279d24cac8d43453fbf9a626cca6与候选e917b1c8923dd9aeef3b542b22f42ffc60c53dc1，保存tested-merge-parents.json。三项自动门37418741494/37418741436/37418741358均PASS，均对应本次Mac范围候选及其merge preview；没有重新dispatch、重跑或使用真实Key。此前“运行中”保留为当时历史观测，已由此最终结果替代。

**C5当前macOS范围自动门已全部通过。** 现有82路径plan所选15本地/3CI门齐全，policy catalog receipt结果PASS、mergeReady=true、releaseReady=true，表示该机械catalog的就绪范围；Windows/Linux在风险说明中为用户暂缓未验证、不参与本阶段阻塞，未写成PASS。这个catalog没有认证B归因或T6，因此完整1A/完整研究工具链的交付判断仍mergeReady=false、releaseReady=false；没有合并/发布授权或完成声明。回执合法及绿色CI不替代目标完成。

本轮真正剩余的目标证据是B实际供应商归因未验证、T6正式工具闭环NOT_RUN。最新用户范围明确供应商请求0、不重开T6/不索取A/B，不能通过自动goal续接擅自消费旧预算或读密补证。本轮无新增产品修改、无重新启动实例，原独立实例仍停机且生产未更新。报告收口提交只在本地，不改变已送检e917b1c89、不为报告重复CI。下一唯一目标为在另行明确授权且调用次数可控的条件下补齐1A剩余真实验收；本轮停止，不进入1B或2—6。

## 2026-10-06 续接1A剩余真实验收：新授权与最小控制补丁

用户明确授权新一轮最多6次模型请求（包括重试/工具返回后生成）、1次公开只读DataHub工具，以及为T6补齐最小必要控制。旧额度不续用；不新建预算系统、不修改固定DSH/生产/其他平台，不在对话接收Key。此前“本轮请求0/不重开T6”是前一有界轮次，本段明确替代该执行禁令；尚未执行任何新真实请求。B供应商归因不能靠读密/哈希或替换后成功推断。

本轮沿原guard和现有llm/stream seam实现实例级6次硬上限与1次精确公开日历工具，正常profile/preset和Keychain/provider不重构。仅非秘密实例绑定环境启用，拒绝生产默认端口3081、其他data home和非法参数；原llm-retry禁用/原DeepSeek策略maxRetries=0，纯文本限制阻断附件导致额外HTTP。全局计数跨session/turn不复位，拒绝子代理和其他工具；默认生产行为保持，进程重启不可补该轮额度。

RED：原guard无llm seam/次数和工具限制的三条失败测试，guard-red.log。新启动器测试首次遗漏fixture的固定Git返回，属于测试环境错误，launch-red.log/launch-green.log保留，不能称根因RED。修正fixture后用HEAD的原launcher源码在独立内存模块执行同一fixture，launch-red-corrected.log因“baseline ignores acceptance control”assert实际失败，未reset产品代码。

GREEN：guard7 PASS/0skip；启动器29 PASS。真实固定DSH在新独立合成profile、正式产品overlay/preset下6次native llm dispatch进入合成拒密适配器，第7次被guard拒绝；全局fetch预先拒绝、实际供应商网络0、没有Keychain读密。native-seam.log/preparation.log保存事实，ctx正常dispose。该证据是合同/合成，不是供应商验收；fixture临时根rwb-t6-contract-p6u7kb5g与真实实例隔离。Secret-bearing启动输出由既有auth-bootstrap截获，认证控制文件不进入证据或Git。

Black/isort修改文件通过；Ruff首次因沙箱缓存写失败退出2，不是产品错误，随后现有Ruff --no-cache通过。mypy沿现有follow-imports=skip并用产品.venv解析依赖，launcher1源文件通过，仅已有unused-section提示；没有新增ignore/Any/改依赖。Python索引按新增helper同步。37条边界外和manager既有诊断未整改。完整changed set阶段验收沿现有规划器，不因每小修改重跑全仓；完整1A仍需真实T6和B归因，机械回执不代替真实验收。

本阶段相关回归最终94 JS/300 Python PASS；launcher静态检查通过，完整84路径约束、文档及索引检查实际执行，未删除旧失败日志。尚无新的真实供应商请求/工具执行，专用Key将由用户只在产品页录入；预计先完成单次T6，然后按可获得的非秘密供应商记录判断B归因，不重复旧生命周期。控制补丁送检身份与真实实例PID/开始时间在t6-controlled目录绑定，不以历史e917b1c89 CI冒充新补丁通过。

### 安全人工录入断点

控制补丁正常提交并普通push为a558cd6f7db0c6337f979d08dacaf6899571b59f；PR78复用、新自动CI尚未收集，不把旧e917b1c89成功冒充此补丁通过。原独立实例经正常manager启动：DSH82351/13081、Host82491/18088，owned/ready；正常网页HTTP200、Runtime HTTP200显示credential_configured=false、configuration_uncertain=false、runtime_applied=false，公开akshare源callable=true。正式research-web preset、6模型/1公开日历工具、禁重试overlay已挂载，生产未改变。

自动审批曾拒绝把Runtime响应credentials对象保存为证据（可能持久化凭据材料）；改为完全排除该对象及嵌套配置，只保存明确布尔/PID/公开源状态，安全替代实际通过，不绕过审批。live-preflight.json及live-ledger.json绑定代码、PID、实例和新预算，供应商请求0/6、工具执行0/1。先前固定DSH合同6次是无网络合成调用，不计真实供应商额度，也不当作T6通过。

当前只等待用户在已核验 http://127.0.0.1:18088/#/settings/model 页面手动保存本轮专用测试Key后回复“已保存”；不读取密码框、剪贴板、Keychain值，不要求在对话/命令/截图提供Key。不要点击生成测试/发研究以免分散本轮计数。另仅询问供应商是否存在按该Key关联的非秘密请求记录；没有时B归因继续未验证。等待阶段保留归属明确的独立进程，未轮询人工录入或发供应商请求；结束后按产品清除Key并只停止所属进程。报告断点提交仅本地，不改变已推送控制候选，不重复CI。

### 第一条真实T6与工具选择修正

用户回复“已保存”后GET非秘密credential_configured=true/uncertain=false；DSH82351、Host82491仍owned/ready。经正常Web create/send触发正式research-web、纯公开日历提示，session3f402fe4-4635-4fb2-b059-3f49a984451b返回202；2次真实模型step、0失败attempt、1次datahub_get_trading_calendar原生调用，4.478秒completed且最终非空回复。但工具result.isError=true，HTTP400，故**T6本次FAILED，不因最终回复成功冒充工具通过**。只保存事件引用/计数/稳定错误摘要，不保存请求体、认证或原始trace。

只读能力元数据与源码证实：AKShare来源整体callable=true，但trading_calendar绑定implemented=false；公共fund_data/eastmoney_fund绑定implemented=true/callable=true/auth_type=none/fee=free，且阶段0已有000001/nav/limit1真实1行证据。我把来源可用误当能力可用，选错工具；不是Key故障，也不开发交易日历或扩进阶段2。最小修正仅将验收控制改为datahub_get_fund_data并在最终guard约束source=eastmoney_fund/dataset=nav/code=000001/limit1、不允许回退/刷新/其他参数或来源。正常生产默认guard不变。

已用模型2/6、工具1/1时没有再执行工具。用户明确追加仅1次工具额度，使本轮总工具上限2、模型仍6；批准为加载修正只重启原所属独立实例，新进程模型上限降为剩余4、工具上限1，总账不重置、Key不重新录入或复制。修正有public-tool-red.log及对应GREEN/启动/static/邻接回归，缺项不隐去。所有后续真实记录累加到原ledger，不将进程重启当补模型额度。

远端master已漂移到05326b6066f96a572db4ac87f3bdc041ff92003f；PR78当前CONFLICTING（API base仍旧9e231b6c缓存事实分别记录），自动新CI未触发，不能借旧CI成功。尚未自动合入新的master或历史分支，不为绿灯改policy/Hook。本轮工具修正和真实证据可独立推进，远端整合缺口保留。

### T6真实通过、结束清理与当前外部门

修正后正常受管重启产生DSH11301/Host11591，同一data home，用户未重新录入Key，configured=true/uncertain=false；新进程硬上限4模型/1工具按原总账扣减，未补模型额度。正式Web create/send的session cf1c2e6a-3e8a-4491-a5e7-bbc961a2f279实际调用datahub_get_fund_data一次、工具无错误，2模型step/0失败attempt，4.412秒completed且最终非空回复。只读快照验证provider=eastmoney_fund、source=fund_nav、row_count=1、cache_hit=false、as_of=2026-09-30、unit_nav=1.222；最终回复包含同一日期和1.2220，并准确保留1页1行/pagination_complete=false及非完整历史限制。

**T6正式Web→固定DSH→真实模型→一次成功公开工具→真实最终回复PASS。** 证据T6-public-nav-proof.json、T6-snapshot-readback.json、T6-public-row-readback.json。最初证据脚本误将dataset source=fund_nav与provider=eastmoney_fund比较，产生错误FAILED；T6-public-nav-proof-initial.json保留。只读现有快照纠正判定，没有重发任何模型或工具；前一条日历HTTP400仍是真实FAILED，不与此证据错误混淆。

全轮累计模型**4/6**、工具**2/2**（含首条失败，追加额度有用户明确回复），0自动重试，剩余2模型未使用且结束后不自动结转。固定DSH/产品锁/生产未修改，未新增预算系统、Provider或DataHub能力；最小控制与精确公共参数修正经8 guard/29 launcher/95邻接JS及既有300相关Python等证据验证。B实际供应商Key归因仍未验证：尚未收到按该Key关联的独立供应商记录；生成成功、Keychain configured及数据供应商eastmoney_fund都不是模型Key B的归属证明。不通过读密/散列补证，未为该缺项消耗剩余额度。

清理实际PASS：确认测试会话不活跃，通过正常产品PUT clear_api_key=true清除本测试Key，HTTP200；刷新credential_configured=false、configuration_uncertain=false，清除前runtime_applied=true与清除后false分别保存final-product-key-clear.json。正常manager.stop仅停止上述owned进程，最终两个process=missing/ports=closed，final-status.json及closed ledger保存。没有供应商Key撤销或生产8088/3081升级、停止、迁移。

当前修正候选fa452937a862d86983bc7e24a49c567c61c28b5e已普通push。PR78因目标迁移冲突未自动触发CI；按既有C5独立送检授权仅补发缺少的Web Checks37431032580与macOS Bootstrap37431037662，两项attempt1/workflow_dispatch/标准ubuntu-latest与macos-14最终PASS，actual checkout均为fa452937a，current-code-runs.json保存完整job/steps与Checkout精确SHA。一次run list空响应不是终止证据；随后直接读取同一两个run handle确认completed/success，没有重新发起运行。没有Windows/Docker dispatch、rerun或发布。

Project Constraints当前代码CI仍BLOCKED：PR78 CONFLICTING，actual remote master05326b6066f96a572db4ac87f3bdc041ff92003f相对9e231b6c含140路径Native/Docker状态/安装/凭据/控制器迁移和20文本冲突，target-drift-summary.json保存具体列表；含README、运行协议/数据/安全文档、architecture-map、图/回执/测试等，不能当作一份回执冲突。未自动合入这份大迁移，也未直接合入历史功能分支。现有policy完整84路径回执仍BLOCKED，mergeReady=false/releaseReady=false；Mac功能T6真实PASS不等于新目标整合、B归因或完整1A全部完成。

当前唯一剩余目标为在明确整合范围与非秘密归因证据条件下完成1A收口；不重做阶段0/C1/C2或已完成真实生命周期，不自动进入1B/2—6。报告最终本地提交与fa452937a代码身份分别保存；只报告补记不再push触发CI循环。本轮完成已授权控制/真实T6/清理，遇到超出当前边界的大迁移及缺B归因证据后停止。

## 2026-10-06 固定新目标整合收口（仍只Mac Native）

用户“执行”明确续接目标整合与B非秘密证据核对；实际输入HEAD2118b99d20cff8e1929bbd99e4961e1406792de1，分支/工作区核对无误，保留全部本地同任务报告提交。一次fetch固定目标1dbd7547f1c6062124ab3a7f1fbd4498058f38fa；它包含此前05326b60 Native/Docker迁移及其后的平台职责文档PR79，无额外产品源码迁移。正常merge --no-ff --no-commit进入原任务分支，未reset/rebase/force、未向master push或直接合历史功能分支，目标之后漂移只记事实，不追赶。

整合保留C1模型ref→系统Keychain/无ambient与旧文件回退、Host受控record、Provider/preset边界、保存事务/清除/活动任务/dirty状态、认证输出私有交接及T6精确调用控制。合并来的运行合同和独立state目录造成认证路径直接兼容缺陷：先增强现有分离state测试取得RED，再让launcher的RESEARCH_RUNTIME_AUTH指向已验证state，新增非秘密RESEARCH_RUNTIME_STATE_ROOT，Node preload验证同一state/auth.json绑定；私有原子写入和authority/cwd/source校验不降低。真实exec测试中的Python替身不能接受Node --import，仅在fixture剥离该Node专用选项，仍执行真实exec/环境清理，未让产品跳过preload。最终启动器65 PASS。

逐冲突合并README和模块文档：Native模型Keychain与非mac模型存储未验证说明保留，Docker通用业务凭据私有挂载实现保留且明确不泛化模型后端支持；同时修正旧数据文档曾遗留的“模型秘密私有文件”句子。架构清单合并两边源码/测试/映射。部署图拓扑确有变更，仅重做01-deployment：既有双部署结构加Native模型Keychain平面，showcase校验/交付及四viewport包含性/最小最大明暗截图真实通过；Codex已实际查看四图。用户结构化回复“我已查看四张截图并确认无问题”后才写same-hash reviewer=user记录，未将AI查看伪装人工。其他图同哈希既有评审复用。

用户此前Mac-only明确决定继续有效。自动审批首次拒绝阶段配置/工作流门变更，随后用户具体批准“新增显式阶段配置与前置判定，Mac-only暂缓Docker job，保留工作流/测试/恢复合同、不写PASS”。机器阶段文件.agents/research-web-stage.json只声明当前Native与暂缓平台；新Docker workflow先执行通用stage-scope，显式false时不启动docker-runtime，缺省/true恢复原路径，非法配置失败。直接合同覆盖false/true/缺省/非法，与原矩阵/构建/安全证据断言并存。再次审批拒绝从总体policy移除Docker/Windows门及提前人工review的组合操作后，没有删除总体门：现有全平台plan仍保留Docker选项，其未验按暂缓保留；当前Mac任务和总体验收按目标现有platform ownership规则分开记。用户“完全访问”仅解决访问权限，不等价人工看图；本次已有独立人工回复。没有改全局Hook/共享kernel/保护规则或预算，Ubuntu通用Project Constraints/Web Checks继续保留。

三类完整集合scope.json：原任务共同基线至当前整合内容182路径、相对固定目标新PR63路径、本轮前后145路径（最终Git再核对，不把旧数量固定）。现有L4计划20本地门/4总体CI门，Docker产品执行暂缓不冒充PASS；总体验收可能未就绪，不据此停止Mac工作。

实际本地证据：相关Native/协议/凭据/API Python645 PASS；剩余离线容器/安装/集成合同329 PASS/1既有非本平台skip；治理/认证/guard/UI邻接JS197 PASS；阶段/路由/保留Docker代码直接合同102 PASS。这些离线合同不等于实际Docker或Windows/Linux验收，没有启动Docker。触及launcher/test的Black/isort、launcher已有mypy边界通过；4个导入目标测试SIM117不是本任务行为缺陷，限定文件等价合并nested-with而非unsafe自动修复，复跑65 PASS与Ruff通过，未用ignore/降规则。旧37条和manager既有类型诊断保留，无全仓整改。

整合后在原获准独立data home补一次无Key受管启动：安装Doctor真实ok/installation_ok=true；正常页面200、Runtime connected/health/owned=true，credential_configured=false/uncertain=false，没有真实推理（预期）。随后正常stop并核对所属进程退出/端口关闭。没有更新/停止/迁移生产8088/3081、手写安装清单、安装新依赖或读取真实模型Key。早先T6真实PASS、4/6模型与2/2工具、产品清Key等证据原样保留，本轮真实供应商请求0，不消费已关闭轮次剩余额度。

用户同时明确“没有按Key记录，继续保留未验证”：B实际供应商归因仍UNVERIFIED，不以这一句当作豁免，也不靠读密/哈希、保存/HTTP200/生成成功补证。不能宣布完整1A完成。整合提交/CI候选SHA及本地报告身份分开记录，新CI不复用fa452937a或e917b1c89运行冒称新HEAD通过；只普通push同一分支、复用草稿PR78，不合并/发布。按现行政策分别交付当前Mac验收与总体mergeReady/releaseReady，不删除外部门来凑全绿。

### 同任务远端并发保护断点

本地固定目标整合正常merge提交9a19caf2d061ba474cdb3cbabf0dbf2c40fd965b（父2118b99d2、1dbd7547f），此前所有验证与无Key清理已完成。普通push遇non-fast-forward，未使用force/rebase/reset。只读fetch证实远端同任务PR78新增e533fb204/689463a00/38df5dbf5，作者为用户账户，内容是同目标整合及认证PID/监督器加固；不能覆盖，亦不能用其三个Mac/通用成功CI认证本地9a19。

在获准执行范围内正常merge固定38df5dbf5b37113111fa606c8a41d5e45bf42424，保留双方历史：复用其RWB_RUNTIME_STATE、bootstrap pid、监督器/Native读取加固，保留本地state canonical绑定、明确批准的阶段判定、原T6/清理报告及用户已经确认的部署图哈希。新测试冲突拼接曾造成triple-quoted fixture语法错误，保留concurrent-python.log；改为逐项核对后复用远端完整真实Node fixture，C1模型、调用控制及独立state测试全在，并发增量449 Python/43 JS PASS。独立Native无Key启动及正常停止已实测，不发真实请求，不动生产。

旧远端另有pr78-repair报告作为既有同任务记录保留；本代理仍只维护本唯一报告，不借其未执行/拟执行真实验收声明发模型或索取Key。本轮模型/工具请求0，B仍用户明确没有按Key记录、未验证；早先T6 PASS和关闭的4模型/2工具总账不重置。

准备收口时远端再次前进至677b9dc8eac227fa758a32bb34bba43204412337。此为持续同分支写入，而非缺访问权限；停止追赶、不覆盖、不自动混入未审阅版本，已向用户一次请求分支收口归属（暂停另一会话由本会话完成，或交由另一会话合入）。当前保存固定38df的已验证本地候选，等待归属明确后才推送。CI/目标提交仍分别记录，不修改工作流来冒称绿灯，不将B缺证据或暂缓平台标PASS。


### 收口归属确认与最后增量同步

用户明确暂停另一会话，由本会话继续收口。正常合入固定远端677b9dc8eac227fa758a32bb34bba43204412337，保留双方所有历史；最后两提交仅7路径，产品源码未变，因此复用13d2的449 Python/43 JS及无Key受管启动停止证据。Docker入口改为Linux真机expected_sha手动触发，保留已批准的显式stage-scope判定及原矩阵/测试/未来恢复合同。唯一文本冲突为额度合同测试，按实际手动触发加阶段前置两者更新。Docker未执行、未写PASS；Mac和通用自动门不受影响。用户人工四截图评审原哈希保留，B继续未验证，本增量供应商请求0。

最后增量102合同、71文档/架构测试通过；完整范围约束初次因远端documentation组错误引用01-deployment失败，保留初次日志。按实际治理拓扑修正单条评审记录（部署由runtime/dual-runtime评审），未改图/规则；完整规划、约束及文档治理重验exit0。原报告中另一会话的合并/真实Key意图不构成本会话授权，本会话不合并PR、不恢复真实请求。

PR78已由其他操作于2026-10-06T14:23:24Z合并677b9dc8，master合并提交211703cca660172b524eff804cc547458529858e。本代理未合并，b04812eb5普通push成功后无法恢复已关闭PR草稿。用户随后明确批准唯一后续草稿PR80，仅送检不合并；head b04812eb5/base211703cc，MERGEABLE。匹配初次CI：Web Checks37479735794 PASS、Mac Bootstrap37479735807 PASS、Constraints37479735956 FAIL（新PR实际24路径缺01-system/Tabbit模块同步）。保留失败日志；唯一集中修复只补认证canonical绑定的两段直接文档，不改代码/规则，按新PR差异及原完整范围双重验证后送检。

### 本轮冻结候选与有界CI交接

最终送检候选H=4e229e855f31dc7bba96f462ad8f40731a5f0fe2，普通push成功；后续唯一草稿PR80目标211703cca660172b524eff804cc547458529858e，MERGEABLE。唯一集中修复为模块说明，无源码/安全行为再变；源码等价b048，不能据此把b048旧CI说成H运行。完整原交付184路径、新PR26路径双规划/约束exit0，文档治理exit0；完整集合和plan见integration-final/original-plan-fix.json、pr80-plan-fix.json。原20本地门证据继续复用，回执durationSeconds=0表示本次复用登记，不伪造新运行耗时，原始实际耗时在原日志。

H自动运行attempt1/pull_request：Project Constraints37481022606已success；Research Web Checks37481022639与Mac Bootstrap37481022776采集时仍in_progress。当前head/base/mergePreview及runner元数据在current-ci.json；尚未完成的运行不能取得最终checkout日志，交接后再核对，不能以旧CI替代。本次没有额外dispatch、无限轮询或第二轮修复。Docker/Linux与Windows产品验收用户暂缓NOT_RUN，通用Ubuntu CI保留。旧b048两成功门脱敏checkout证据独立留存；不混用其SHA。

本轮不合并、不发布，生产8088/3081未修改；独立测试实例已停止且Key已按早先产品流程清除，本轮模型/工具请求0。T6真实PASS保留，B供应商归因仍UNVERIFIED，因此完整1A仍BLOCKED；H全部Mac自动门尚未完成，C5当前候选部分完成，mergeReady=false/releaseReady=false。用户查看四部署截图并确认的same-hash人工证据保留。仅本地报告提交不推送，避免“补报告→新HEAD→再CI”循环；H与后续报告提交身份明确分开。

### C5最终结果（Mac范围完成）

宿主macOS，任务类型功能收口/本平台验收；用户要求在已授权范围内持续完成，不另索确认。冻结候选H=4e229e855f31dc7bba96f462ad8f40731a5f0fe2，草稿PR80目标211703cca660172b524eff804cc547458529858e，实际CI checkout均为合并预览2df45889c8935007ec5b7c9b19aa6caa96fadde7（并非H本身或报告HEAD）。三个自动门attempt1/pull_request最终success：Project Constraints37481022606、Research Web Checks37481022639（Ubuntu通用/非macOS证据）、macOS Bootstrap37481022776（macos-14本平台证据）。run/job/runner/head/base/checkout证据见integration-final/current-ci.json、各run-final.json和checkout.txt。mac-final-artifact为现行workflow最小无凭据成功产物，Doctor installation_ok=true/product_ready=true、Runtime3081/Web8088 ready=true；天软configured=false/callable=false/restart_required=false，正常停止步骤success。不借开发机环境认证干净安装，不使用真实Key。

Mac基础模型链路与早先T6已有验证证据保持，本轮C5 macOS范围自动门完成；Ubuntu结果只记为通用门，不冒称Mac CI。Windows/Linux及Docker产品门用户暂缓，保留NOT_RUN并不作为当前Mac宿主完成前提。总体验收catalog仍选Docker，因此回执诚实BLOCKED、mergeReady=false/releaseReady=false；完整1A另有B实际供应商归因UNVERIFIED，不能因绿色CI或平台范围变化宣布完整1A/正式发布完成。当前Mac功能验收没有新增缺项，本轮供应商请求0。

实际动作：gh run view/api读取最终元数据与脱敏checkout、gh run download获取Mac最小成功artifact、现有receipt validator、完整范围project constraints/documentation治理核对；无重复dispatch、第二轮CI修复、平台验收、合并、发布或生产变更。独立实例仍保留停止状态与此前产品清Key证据。后续本地报告提交与H区分，仅报告变化不推送、不诱发重复CI；代码状态与tree身份保存在final-identity.json。下一唯一目标为取得B非秘密供应商归因证据；无现成按Key记录时保持未验证，不读取/散列Key、不自动发新请求。

### 用户明确豁免与Mac阶段最终收口

2026-10-06用户在获知无法提供B按Key供应商记录、豁免不得改为PASS后，明确回复“确认豁免”。豁免仅限B实际供应商归因验证；该项结果SKIPPED（用户明确豁免），证据仍UNVERIFIED，不能宣称请求实际使用B。此前失败/缺证据记录完整保留，不新增真实请求、不读取或散列Key、不修改验收policy/required checks。早先凭据替换、真实生成、清除/恢复、Host/DSH冷重启和受控T6证据独立保留，不由豁免补造任何生命周期结果。

hostPlatform=macOS；taskKind=功能收口/本平台验收；hostAcceptance=PASS（包含用户明确接受的B归因缺证据例外）。当前macOS Native阶段1A按用户修正的范围与明确豁免已收口；这不是全部验收项实测PASS，也不声称完整跨平台研究能力或正式发布通过。C1/C2、既有真实生命周期、T6及匹配候选的C5 Mac/通用自动门证据沿用。平台交接Windows/Linux/Docker保持用户暂缓、NOT_RUN，非本平台任务阻塞。aggregateAcceptance=BLOCKED；现有总体catalog仍含Docker未执行，mergeReady=false/releaseReady=false。豁免不改变该机械结论，不删门、不改规则或通过构造较小changed set求绿。

冻结CI候选仍为4e229e855f31dc7bba96f462ad8f40731a5f0fe2，合并预览2df45889c8935007ec5b7c9b19aa6caa96fadde7，PR80保持草稿；后续本地变更仅本唯一报告。本轮供应商请求0、未修改生产、未合并或发布，不重复已有验收或触发CI。原“下一目标取得B归因”已被此次明确豁免取代；本任务结束，不自动进入1B或其他阶段。下一阶段唯一可讨论目标为1B的模型支持范围，须另行明确开启。

### 阶段1B已开启：OpenAI兼容路径核对与当前边界

用户明确“执行下一阶段”，并选择OpenAI兼容API；随后说明当前没有购买其他模型，希望参考cc-switch的多服务接入。此为范围推进，不撤销1A的B归因豁免，也不授权阶段2—6或声称所有品牌已支持。宿主macOS，任务类型有界功能扩展；工作树codex/settings-model-loop，实际输入HEAD2c4ae592fa7dbf5f5ccaa9158b2e22e18788973f，工作区干净。PR80原候选和已通过CI保留，不reset/覆盖/合并，不读取个人cc-switch/Codex/Claude配置或秘密。

公开参考为farion1231/cc-switch的Add Provider文档（main，在线读取）：其可配置Provider与端点、显式协议、模型ID，模型列表接口失败可手填ID；某些客户端协议差异由本地代理转换，不等于所有模型原生可用。仅借鉴连接配置和能力分层，不复制个人配置投影、登录/OAuth或代理框架。参考链接：https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/2-providers/2.1-add.md。

本机固定DSH c919b2a的llm-pi-ai源代码与已构建lib真实存在；provider.ts支持openai-completions/openai-responses，config.ts支持按route配置api/baseURL/models/apiKeyEnv，index.ts支持现有settings热更新。新连接必须用独立自定义route和明确credential ref，禁止复用DeepSeek ref或依赖provider-native ambient授权；ctx.credentials缺失时仍有环境回退，因此产品绑定必须失败关闭，不能仅展示来源标签。当前产品ModelConfig/UI/configure_model只开放deepseek-official，系统桥接只允许RESEARCH_DSH_API_KEY，故尚不支持通用OpenAI服务。地址/重定向安全尚无新增产品验证，不能因底层支持协议就声称接入完成。代码引用及非秘密源文件哈希见phase1b/investigation.json。

最小实施边界已确定：保留原DeepSeek；只增加一条明确协议的OpenAI兼容连接配置（连接标识、base URL、模型ID、独立系统credential ref）；经现有owned overlay挂载固定llm-pi-ai，不修改固定DSH、不新增Agent loop或代理daemon；手填ID不冒充模型发现，文本/流式/工具能力分开记录。须先取得失败测试并验证非法URL、携密重定向、两个模型凭据隔离、保存失败/活动任务/冷恢复，再通过一条真实服务的生成/研究调用验证。不能凭预设品牌列表或fixture宣称全部模型已支持。

本轮新增服务名称、endpoint、model及账户均未确定；用户明确没有额外模型账户，当前未安装模型、不采购、不请求用户把Key贴入对话、不调用供应商、不消耗关闭的1A预算。原阶段1B要求选一种实际需要且可验证的服务，缺此条件时保留BLOCKED：只读支持范围核对已完成，新增产品路径实现NOT_RUN、合同/fixtureNOT_RUN、真实生成/工具/冷重启NOT_RUN，阶段1B未完成。不能以1A DeepSeek结果冒充第二服务验收。后续若用户选择实际已有服务（可包括另行录入的既有服务兼容协议路径），在独立实例设置页录入，并单独固定真实请求预算；不要求购买服务作为继续条件。

本次修改仅本唯一报告，复用1A源码/CI证据而不声称CI测试过报告HEAD；相关文档/完整changed set约束和回执校验实际结果随本轮日志保存。hostAcceptance=BLOCKED（1B服务选择/真实环境缺失），aggregateAcceptance保持BLOCKED，mergeReady=false/releaseReady=false。不自动进入后续阶段、不合并/发布或修改生产。下一唯一目标仍为取得一条实际可验证的OpenAI兼容服务路径。

### DSH Fork上游同步与自动检查（独立源码范围）

用户明确要求同步deepseek-ai/deepseek-harness与Leon-Huang001208/deepseek-harness，并要求后续自动检查，不再依赖主动询问。该指令授权Fork源码同步，不自动升级Research Workbench固定依赖、运行实例或发布产品；1B产品接入未因此变成已实现。本次宿主macOS，任务类型Fork源码同步/必要兼容修复。实际Fork public、push/admin可用；旧master=c389f96bf3a9b6807cb71ed6bdad5849be0df6d8，旧workbench-runtime=c919b2a460753859665db3f60143d525fb9140cf，比共同基线多一项永久删除会话补丁（49路径）。一次固定上游5badb15009ae1756c3afe0ae0cef1faafc290ccc，5077个新增提交、版本0.2.1-alpha.1。

master通过GitHub Git refs API force=false快进到固定上游，无改写历史；workbench-runtime不能覆盖，原普通服务端merge返回409。Git HTTPS连接失败、SSH下载无进展后停止所属下载；改用GitHub API取得源码归档、原commit/base/custom tree和必要blob，核对原上游commit SHA与tree=a9d30743edbe97adac9c8cb0811b648a0d9f6660完全一致。没有修改已安装Runtime目录。隔离源码目录/private/tmp/dsh-fork-sync-local-20261006，证据/private/tmp/dsh-fork-sync-evidence-20261006。三方合并原自有49路径，30文本无冲突、19冲突；保留新fork语义、生成目录和所有自有删除/索引/缓存/Workspace清理边界，处理新Agent setup/announce签名。旧fixture先实际RED，修正后相关回归403 PASS/8文件/6.55s。旧删除条款英文已移除“不可删除”，中文同条遗留已同步移除；两份直接模块说明按源代码和双语实际核对后更新记录，9对一致。旧功能Note的整blob回执格式已被新规则拒绝，按实际未改动双语语义迁移到段落格式，未改检查规则。

新锁定依赖仅安装于该隔离源码目录（pnpm11.19.0按frozen lock；锁未改），部分下载最初报错后安装完整结束。真实本机原生模块构建通过；先因未构建flock取得失败记录，构建后381相关测试PASS，API邻接27 PASS，最终统一8文件403 PASS。Host构建完成，正常pre-merge/pre-commit/pre-push门全部通过，pre-push包含完整Host及Client类型检查（90.47s）。Git Hook最初因系统x64 Node与安装的arm64 esbuild不一致失败，改用本次命令范围的受管arm64 Node PATH，未改系统环境/Hook、未no-verify。

正常合并提交48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0，实际parents为上游5badb150与自有c919b2a。本机历史因Git下载失败只取得上游边界原commit/tree，标记为浅历史，不伪造祖先；根据GitHub明确共同基线和核对后的三方tree准备正常merge元数据，由原Git Hook正常提交。经GitHub Git trees/commits API上传（未绕过任何失败Hook），远端原commit SHA、tree=ca060ccc35e2b1b55626258c60ae381dd1a4ead3与本机完全一致，delta39路径。随后force=false更新隔离候选与workbench-runtime；APIcompare证实相对上游ahead2/behind0，原自有c919提交仍为父节点。legacy分支b3e26660保留。不是将整个仓库选ours/theirs，也不是只更改ref标签冒称合并。

上游镜像push自然触发现有工作流。Release(dsh/vendor)仅无凭据打包演练success，Node Addon System success；CI master仍有无自托管Linux/Windows runner的queued job，Sandbox采集时运行中。E2E37486161026实际在Key为空的preflight失败，未发供应商请求；未读取/配置真实Key或扩大旧请求预算。不删/skip工作流求绿，未启用付费runner或部署凭据。上述CI属于master5bad，不认证运行候选48504f07；运行分支没有自动PR CI，不能宣称全CI、真实推理、Research Workbench依赖升级或发布通过。本次实际Fork源码同步完成，local acceptance PASS；远端/全平台发布证据仍部分未验证。

已通过Codex automation_update创建并更新自动检查dsh-fork，ACTIVE，每天北京时间09:00。监测上游/master/workbench-runtime，保留自有修改；快进正常同步，有冲突、版本/存储大迁移或检查失败时保留候选并通知。无变化/无新进展静默，只有完成或新阻塞通知。禁止force/reset、绕过Hook、改预算、供应商请求、产品固定DSH/锁升级、生产变更。自动化配置实际核对存在，不是只提出计划。

本轮实际供应商请求0；产品已安装DSH仍c919b2a，Research Workbench所有源码/锁及生产8088/3081未修改，PR80未合并/发布。唯一报告只本地提交，不为此重跑原C5或推送报告循环。总体mergeReady/releaseReady仍沿用既有BLOCKED，不能从Fork同步推导产品就绪；下一唯一目标为独立评估新DSH与Research Workbench适配及固定版本升级，尚未自动实施。

### DSH产品升级进行中（2026-10-07）

用户明确授权“升级并验收，完成前不要暂停”。本轮目标固定48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0，不浮动跟随分支；Mac Native开发/验收，Windows/Linux产品仍暂缓。每周一北京时间09:00自动检查已按最新用户要求更新并实际核对ACTIVE，先前“每天”是历史状态。

先保留旧合同拒绝新候选的RED；实际新app-boot移除healProfilesModuleFallback，先更新失败测试复现，再使用createRuntimeResolution原生解析表，检查每个packageDir只属于固定源码或两项受管供应包，不开放任意外部模块。四项模块归属合同PASS，真实固定新DSH解析579包通过。能力目录旧PIN也先真实RED，改为共享RuntimeContract来源；auth bootstrap同样读取唯一机器合同，避免认证source_commit残留旧版本。未放宽字符串校验或凭据/归属门。

新DSH完整build先因受管Node24缺开发头文件失败；创建隔离Node24副本，取得官方同版本headers及SHA校验后完整build成功，不改Codex共享运行时/系统Node/DSH源码。实际构建闭包16097项，文件数而非全局绝对目录摘要固定；Corepack0.34实际启动pnpm11.7.0版本核验通过。228安装/启动/共享合同PASS，7认证/凭据JS合同PASS；仍需所属实例、真实新协议、剩余本地门与当前代码CI。安装只调用既有SetupWebInstaller真实校验/发布/安装方法，不手写installed清单。当前代码由working-code-identity.json记录HEAD加完整diff，不仅旧HEAD。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力目录的固定来源提交改为共享RuntimeContract，未增删能力节点或执行器；Native工具注册与版本语义另行验证，不把来源标签当可调用证据。","diagrams":[]} -->

实际新版目录将默认项改为deepseek-flash（V4.1名称）；旧保存值与历史会话不自动重写，空实例默认才采用新项。先失败测试再修正默认/UI/overlay，一项兼容测试确认保留已保存旧ID。新preset体系改为原生声明式registry，旧.agent-presets文件不再自动发现；先实际agent-preset/not-found及失败合同，再在owned overlay声明research-web/framework-explain/framework-verify三个既有ID，默认registry显式research-web，未新增Agent loop。新版移除subagents/list，使用权威父投影subagentCatalog和session/list的实时running交叉验证；缺失、未知模式/活动或错误父属拒绝配置/提交，未返回空列表假装无活动。两项失败测试转绿。

真实Mac Keychain合成值链路已通过，新native provider确实消费该值（仅进程内比较），公共CLI/正式framework-explain在受控Messages回环fixture生成最终回复。fixture请求1、供应商请求0，产品清除后configured=false，所属fixture进程退出；此不冒充真实推理。只读热改设置被owned overlay拒绝后保留限制，fixture采用独立实际安装数据home与冷启动，未放宽模型端点或设置权限。其早期失败还包括未启动Host服务事件通道的测试器问题，全部日志保留，按正常lifespan后PASS。

原有21 Ruff诊断在HEAD基线全部存在；仅触及文件等价导入/字面量/with顺序修正，无新增ignore。698相关Python PASS（2既有平台skip）、50 API PASS、3实际native源码合同PASS、284 JS PASS。后续模型默认与协议适配的增量必须补回归。用户已在独立19088设置页保存测试Key，未读/打印/散列。当前真实预算4模型/1公开只读工具，旧轮额度不使用；计入重试/工具后的生成，跨重启保留总账，真实验证尚待执行。

### DSH升级真实验收与集中CI文档修复

实际候选9924fa7e22cb592095b755b19bfaab55ab8632db，目标ddcdd9784d8eda2918b8987ca8b679375e67291d，草稿PR81。独立19088/14081实例正式preset已完成真实生成、带Key Host/DSH冷退出重启后无需重新录入的生成，以及datahub_get_fund_data公开净值查询和最终回复。实际使用模型4次、工具1次；用户随后明确授权按任务必要次数继续，不继承旧轮余额，也不自动消耗额外请求。模型原生cap1的合成fixture证明第二次请求在出网前阻断，供应商请求0。所有失败及脱敏证据保留于logs/settings-model-loop/dsh-upgrade。

初次当前代码CI：Research Web Checks37510747168和macOS Bootstrap37510747272 success；Project Constraints37510747653 fail，原因是当前PR差异缺少直接模块文档与当前结构复核记录。完整原任务差异虽通过，不能替代当前PR差异。集中补齐实际协议变化对应文档，未修改规则/测试边界；当前升级结构与目标分支部署拓扑一致，旧Keychain图变更已经进入目标，因而不重复截图。新文档提交仍须取得匹配候选的必要自动门，不能沿用初次成功冒称新HEAD通过。

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "固定DSH升级迁移模块解析、preset注册和子任务协议；仍由现有Host、Runtime和Keychain私有桥接执行，部署节点与信任边界不变。", "diagrams": []} -->

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "仅升级共享固定来源及Native适配，保留原运行模式控制器和存储隔离；Docker仍用户暂缓，未新增容器或宿主桥接。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "以权威原生父投影和实时会话表实现既有子任务列表合同，保持HTTP入口和活动保护，没有新增执行器或信任边界。", "diagrams": []} -->

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "仅更新空实例模型默认值，保留已保存旧ID及现有设置状态、dirty表单和同源API，未改变布局组件或导航。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "已有自动任务继续经同一ResearchService和正式preset创建发送，preset声明方式迁移不新增调度器或任务注册中心。", "diagrams": []} -->

独立只读Python审查发现适配结果未包含既有kind=child，且空闲值idle不符合service所需inactive。新增参数化消费者回归先得到2个KeyError失败，再在单一client适配点固定kind和activity；原生DSHClient到ResearchService的归属、取消和空闲门通过，完整protocol+launch 88 PASS。实际固定上游源码仍提供subagents/interruptByParent与session/follow，审查核对地址/父属/mode兼容。Black/isort/Ruff与diff检查exit0；未改凭据、执行循环或拓扑，不重做真实生命周期。此次必要源码修复生成新候选，feb239e69的CI只属于旧候选，不能冒称修复后已过。用户最新授权继续所有阶段及必要模型/工具调用，不再以旧次数上限阻塞；供应商Key仍仅设置页接收。


### 用户开启后续全阶段：阶段2实例隔离与阶段6边界决策

最新授权为按任务需要使用模型/工具并持续推进后续阶段；旧10/5只是历史限制，不再作为授权阻塞。原阶段0/1A在Mac范围及B归因明确豁免下已收口，新的持续Goal保持active；不把升级或部分阶段成果宣称全部完成。Windows/Linux/Docker产品仍暂缓，通用CI保留。缺失账户、端点或系统权限不被“全部授权”补造。

阶段2实际RED：两个data home共享系统backend时，B留空保存后可读到A秘密，test_data_home_credentials_do_not_inherit_overwrite_or_clear_another_instance exit1。最小修复为原MySQLConnectionStore按canonical data home路径SHA-256后缀生成系统服务名，所有来源的读取/写入/回读/清除及补偿共同复用；账户ID、JSON和Provider不变。旧全局记录不回退、不读取、不复制、不删除；用户需在所属实例重新录入，旧记录保留供旧版本回滚。命名空间解析失败记录类型和稳定错误，不回显路径/秘密。

connection_center/mysql_configuration/datahub回归97 PASS，另命名空间失败关闭与双实例2 PASS；Black/isort/Ruff exit0，mypy连接模块无问题（已有37条边界外诊断不被豁免）。真实macOS Keychain新建两个专用临时data home，合成值保存、替换、留空、跨进程读取、清除后重建不恢复、另一实例保留全部PASS；最终两个命名空间清理PASS，供应商请求0。这只证明真实系统库合成合同，不冒称商业数据账户查询。

公开路径已有真实东方财富净值/快照/研究消费证据，并独立核对磁盘manifest及rows摘要一致：dataset f04d9a91-15de-4998-9f91-b6fcec2f0e07，provider=eastmoney_fund、source=fund_nav、cache_hit=false、row_count=1、pagination_complete=false；不宣称全历史或所有能力。数据隔离证据见dsh-upgrade/data-namespace-{red,regression,boundary}.log、data-keychain-lifecycle.json与public-dataset-proof.json。

阶段1B：新固定DSH源码确有llm-pi-ai，原生openai-completions/openai-responses/anthropic-messages协议与显式provider profile扩展点；但尚无用户实际需要且可验收的额外端点/模型，产品未放宽Provider字符串假装全品牌支持。阶段2商业源也尚无本测试实例账户；已询问非秘密可用资源，不要求在对话提供Key。相关真实验收保持未验证，其他独立工作继续。

阶段4使用现有产品Word真实验证入口，ID aabce313-3f97-43c7-a797-0e6283d42c40，创建/保存/重读/清理所属非敏感测试文档；等待真实完成或现有180秒加10秒协调上限，不把checking写PASS，不操作已有文档或退出用户应用。

阶段6短决策已写入现有05-security-validation：local owner不等于tenant、连接/秘密/缓存/快照/任务归属、公开/授权共享/商业私有数据和模型外发许可、远端API与本机Wind/Office区别、未来TLS/认证/DNS重定向/SSRF及独立设备桥接任务。没有公网监听、注册计费或多租户实现。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"连接系统凭据服务增加规范化实例路径后缀，继续由既有连接存储、Broker和快照消费；未新增Vault、服务节点或跨设备桥接。","diagrams":[]} -->

Word验证最终completed/outcome=timeout（现有180+10秒上限），未得到保存后重读成功证据；不重试、不绕过OS权限，阶段4A保持未通过。独立系统库合成值清理成功不改变该外部实机结果。

Office临时资源清理的独立目录读取未返回，终止本次所属审计Python/父shell（已核对PID、启动时间、cwd）；没有删除受保护文件或退出Word。清理独立证据UNVERIFIED，不将代码finally清理尝试当成实际成功；本项是外部OS/文件访问阻塞，后续不反复扫描。


### 持续Goal当前检查点（不代表全部阶段完成）

升级冻结候选72bb737ccbb5b1c71377af0be637ceb0d65622d0三个自动门attempt1/pull_request均success：Project Constraints37513507562、Research Web Checks37513507543、Mac Bootstrap37513507752；实际checkout均为PR合并预览aa61318c299c1ea960120eb0072b527b0ac9d650。对应run元数据、jobs/runner和checkout证据已分别存于dsh-upgrade/run-<id>.json及run-<id>-checkout.json。升级Mac功能/本平台安装证据通过，不代表已更新生产。

阶段2新候选7e31b012e5b58d9c02a97c019743366877400d99已普通push，草稿PR81仍OPEN/MERGEABLE，目标ddcdd9784d8eda2918b8987ca8b679375e67291d。新自动运行Project Constraints37514944642、Web Checks37514944639、Mac Bootstrap37514944641采集时in_progress，不使用旧候选成功代替。新增11路径，完整原任务差异188路径、PR差异37路径分别保留并通过规划/本地约束。生成Python索引首次过期后按原脚本重建，重验通过；phase2策略闭包91 JS PASS、文档治理/索引通过，schema2回执合法但外部门尚未取得时仍BLOCKED，mergeReady=false/releaseReady=false。

当前unique报告尾部是后续本地进度，区别于已送检候选；不为报告文字自动诱发重复CI。阶段2商业账户查询、1B额外端点仍缺真实外部资源。阶段3代表性Skill结构化准入与有限/缺失条件待继续实施验证；阶段4 Word超时及其资源独立清理证据未确认，不当作PASS；阶段5只推进Mac Native，其他平台/容器保持用户暂缓；阶段6仅设计决策已完成。持续Goal active，未宣称全部完成或以授权不足停止。

独立测试实例暂留以供连续任务需要，真实模型Key未读取/散列/复制，清理将在任务最终退出前通过产品流程完成；不能把早先其他实例清理当成此实例已清理。真实当前账为模型4、公开DataHub工具1，Keychain合成测试和Word验证不属于供应商模型请求。旧每轮额度由用户最新必要调用授权取代；不会为了消耗额度发无必要请求。生产8088/3081未更新、未停止，未合并PR、未发布。


### 阶段3实施中的真实边界与代码身份

基线7e31b012e5b58d9c02a97c019743366877400d99的三个自动门最终success；当前阶段3为该基线上的完整工作区改动，尚非已送检SHA，不能沿用旧CI说新代码通过。新增metadata严格data_requirements和dataset-specific语义，分别拒绝频率/复权/单位/历史时点不等价与未知；公开fund-evaluation仅NAV有限范围、industry-research公开快讯+可选财务、chanlun专业日线+独立HMAC门。只有精确未改旧builtin继任，保存历史/自定义草稿，不伪造比较回执。

先实际RED证明显式提交缺硬依赖仍202与省略范围未保存，再2 PASS；缓存同call/newcall在来源失效后仍返回也先2 FAIL，再53相关PASS。独立审查确认并修复实际参数与声明不一致、缺失的可选依赖仍能查询、Workflow绑定未传递、原生/skill用户注入绕过、preflight提前登记。原生工具最终result成功后才登记，未知登记阻断未来执行，历史注入不重新视为新授权。此处仍待完整实际DSH路径及剩余回归，不因纯测试PASS宣称阶段3完成。

进一步用冻结7e原sandbox实际macOS内核复现：disabled资源可读（kernel-resource-red.json），再以现有Seatbelt精确目录门关闭。模型不能传读授权路径；默认不开放旧resources/skills或全部capability/dataset；已准入版本与当前授权缓存通过同一私有响应传给现有supervisor。内核/监督回归20 PASS/1既有skip；guard/source schema实际新DSH 25 PASS/0skip；JS闭包316 PASS/1已有未设置source的skip。来源配置替换用非秘密原子文件身份修订，绝不散列Key；快照authorization_fingerprint不是秘密hash。历史材料仍可审计，不是新查询授权。

必要静态检查：修复新增tuple字面量推断后，focused九改动模块mypy PASS；normal十模块及其完整传递图57诊断，冻结7e源码同解释器/配置同为57诊断且逐项完全相同（mypy-comparison.json新增0/删除0），全部位于改变边界外，不改规则/ignore或自行豁免。skip导致dataclass stub丢失的4项构造器诊断另分类为检查边界效应；normal自身sandbox无诊断，转移到既有runtime_contract债务，不混为本次缺陷。

唯一报告继续累计；阶段3完整差异/PR差异/原任务完整范围均从真实git diff及untracked生成，保留每次失败。尚未运行的实际新guard/原生加载/受控完整Skill生成与本轮当前代码CI仍NOT_RUN；1B新增连接、阶段2商业账户、Word timeout/清理不可确认仍未消失。本次新增供应商请求0，既有供应商模型4/工具1总账保持；测试Key尚仅在所属独立实例系统库，生产不变。Goal active，不以原“未授权”停止，不宣称mergeReady/releaseReady。

<!-- architecture-review {"group": "capabilities", "structure": "unchanged", "reason": "仅三个精确builtin增加数据声明与继任版本；沿现有不可变包、比较回执和原生Skill发现，未引入第二注册中心。", "diagrams": []} -->

<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "在现有Broker和快照前增加当前授权、配置修订与语义准入；仍为Host内模块，未新增Vault或数据服务。", "diagrams": []} -->

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "复用固定DSH工具/预步骤/最终结果扩展与现有Seatbelt监督器，收窄读许可；既有Host与Runtime及私有DataHub通道拓扑不变。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "新增的内部scope检查复用同一受鉴权回环DataHub通道，不提供取密或执行器API；公开详情只增加诚实范围投影。", "diagrams": []} -->

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "数据范围说明复用能力详情的section/notice和既有目录，不修改主题token、导航或组件拓扑，不将可准备草稿当已执行。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "自动任务沿原create/send和同一工作流绑定准入，继承Scope与实时工具重检；未新增调度器或任务运行框架。", "diagrams": []} -->


### 阶段3集中闭包与真实Native验收（2026-10-07）

续接原7e31b012工作区，完整原任务206路径、相对固定ddcdd978目标60路径、阶段3增量45路径均实际规划/Project Constraints exit0；后续修正既有metadata合同测试后增量46路径，最终再核对，不固定沿用历史数量。原7e三个CI success仅属于原代码。

实际固定DSH公共CLI、owned overlay、research-web preset和独立Host 19089验证：用户/skill直接注入成功登记；模型原生skill工具成功结果后登记并继续生成；缺硬数据的直接注入在模型之前拒绝（fixture请求0）。前两组fixture请求分别1、2，供应商请求0；每组真实Mac系统库合成值均通过产品清除且configured=false，只停止所属fixture进程。旧合成实例私有DataHub origin=8088不可强改，新建admission-web数据根，复用原实际安装验证资产；prepare产出的新锁按安装私有0600权限收紧后Doctor installation_ok=true，未伪造manifest。测试器错误与失败尝试全部保留，不能当产品故障或删掉求绿。

独立真实实例正常stop/start后PID为Host57791/DSH57608、端口19088/14081，安装及product_ready=true；没有重新录入或读取Key。真实fund-evaluation按新声明：公开eastmoney_fund显式probe healthy、readiness available、消息HTTP202、最终completed；实际新快照be0840b1-147c-4b35-95f1-0dffa44be260来自fund_nav，row_count=1/as_of=2026-09-30/cache_hit=false，最终回复1。原生历史固定事件计数为step/start及delivery-accepted各2、tool/call/result各1，retryPolicy maxRetries=0：本次真实模型2次、公开工具1次，累计升级及后续模型6次/公开工具2次。完整公开净值Skill范围通过，不推导完整基金评级、财务、专业行情或其他模型工具能力。脱敏证据live-fund-skill.json、live-event-counts.json、native-{host,skill,tool-skill,denied}-fixture日志位于logs/settings-model-loop/data-admission。

本地真实命令：Black26.10.0/isort9.0.2/mypy2.4.0在原独立检查环境启动；完整新增/修改Python只读Black/isort及Ruff exit0。JS Research Web闭包318 PASS/1既有未设置DSH_SOURCE_ROOT的skip；必要policy JS、文档治理、生成索引exit0。能力/准入/数据声明/实际Mac sandbox集中回归97 PASS/1既有skip，唯一旧metadata全等合同缺新字段FAIL，保留失败后补明确行业/基金声明预期，单项1 PASS；原有其他字段未删除。API/protocol/local integrations118 PASS/1既有skip；service_manager305 PASS；此前DataHub/Runtime139 PASS和业务62 PASS仍对应未改变源码。mypy normal十数据/能力/sandbox模块17既有诊断，service/launch传递边界57既有诊断，两组均使用当前产品解释器解析依赖，与冻结7e逐项相同，新增0/删除0；不增加ignore、不自行豁免，既有37属于更窄历史边界，不能混称全仓通过。

供应商Key尚保留在所属测试实例，仅为连续任务使用，最终通过产品流程清除；生产8088/3081未更改。阶段1B仍没有可验证的实际额外服务，不能用同一DeepSeek换协议冒充新增服务；阶段2商业数据账户缺失、阶段4Word timeout和清理UNVERIFIED仍保留外部缺项。阶段6仅最小设计完成。目标master一次fetch固定c24a8a161674678d572bf9ac35fab30489b40605，新增架构阅读/文档生成改动导致PR81冲突；先保存已验阶段3检查点，再正常merge固定目标，不重写共享历史。当前外部门仍未测试这些新增源码，mergeReady=false/releaseReady=false，Goal仍active。


### 固定目标整合与送检范围

已按正常Hook提交阶段3检查点9f30d23de，再正常merge固定master c24a8a161674678d572bf9ac35fab30489b40605。五个冲突均为README/框架/协调器说明与README评审：合并目标分层阅读入口和治理，保留当前固定DSH、Mac Keychain、实例隔离和阶段3准入说明；目标已归档的日期型稳定性正文不重新堆入当前模块。没有整仓ours/theirs、重写历史或合入历史Native/Docker分支。README实际由Codex复核，回执保留当前schema1 disposition/summary/reason，不伪造人工截图。

目标新文档生成合同导致index/API atlas stale，按原build_research_web_api_atlas.mjs实际生成后复核；图源、节点/拓扑及其人工评审不改变，不重复架构多视口验收。本任务实际新增internal/skill-preflight inventory已在最终清单中；目标新增documentation.py只保留其受控导航/白名单，补直接documentation回归，来源已通过的图册浏览器证据不转述为本任务新的执行结果。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"合并固定目标已评审的分层架构入口，保留其图源和导航合同；本任务新增数据准入API由既有API Atlas生成，不新建服务或修改图节点。","diagrams":[]} -->


### 当前候选最终CI与安全收尾

冻结并已普通push的候选H=32cd546cc720731c801ab4fbeb03577291b0b64a，tree=c150f80ffc6593a6a104dc8480f1c5a62165dc4f；正常merge parents=9f30d23de/c24a8a161，PR81 OPEN/draft/MERGEABLE，base=c24a8a161674678d572bf9ac35fab30489b40605。本地原任务完整范围237路径、PR范围63路径、整合增量46路径，各自规划/Project Constraints exit0。后续仅报告检查点与H区分，不伪称CI测试该报告HEAD，不为报告制造bootstrap循环。

当前必要Mac阶段自动门均attempt1/pull_request SUCCESS：Project Constraints37578504746（Ubuntu check）、Research Web Checks37578504733（Ubuntu checks）、Research Web Bootstrap37578504755（macos-14 Clean Web install）。三者实际checkout均55f05daaafe4ddb737c204cd9406d055a1c10371；GitHub Git commit API实际parents为固定base c24a8a161和候选32cd546cc，合并预览与branch HEAD分别保留。Mac job runner=GitHub Actions 1000000537、label macos-14；真实干净安装、固定DSH构建、启动健康及Doctor通过，成功artifact research-web-bootstrap-macos-14-37578504755/id11464106161仅doctor.json/connections.json/root.html/app.mjs，Doctor ok/installation_ok/product_ready均true、issues=[]。run/json、日志checkout摘要、jobs/runner和artifact均在data-admission目录。未dispatch/rerun，未配置真实Key，标准公开runner，不提高预算。

现行完整changed set其余离线闭包补齐：563 Python PASS（container/runtime launch/credential/runtime contract/setup/runtime mode/Docker runtime的无容器合同），113 JS PASS（planner/receipt/skill/Docker合同）；实际Docker产品生命周期/CI仍未执行，不能从离线合同推导平台成功。整合直接documentation回归25 PASS，架构/policy JS PASS，实际生成index/API atlas和文档治理/索引PASS。已有图源及独立人工审查保留，不重新截全图或把目标图册证据当本轮新执行。

浏览器首选插件因本机原生库签名失败；使用既有CUA备用通道实际核对19088能力中心与基金v2详情，看到独立“数据准入：尚未验证/需完成最小数据探测”而不是将已启用提升为可运行（早前探测已过期）。此为AX语义验证，不声称全站截图/全部视觉验收。未查看设置密码框、剪贴板、认证链接或个人工具配置。

最后通过所属产品PUT runtime/model clear_api_key=true，HTTP200，随后GET runtime credential_configured=false；正常manager stop仅停止所属Host57791/DSH57608，状态PID=null、19088/14081无listener。合成19089/14181同样无listener，实际Keychain合成值每组已清除。真实测试Key不撤销供应商账户，只清除本测试实例；不访问生产Key，生产8088/3081仍未更新。累计真实请求为模型6次/公开只读DataHub2次，本轮新增2/1；其他fixture供应商0。

唯一plan/receipt继续为logs/settings-model-loop/{plan,receipt}.json，绑定完整237路径和L4闭包，validate_verification_receipt exit0/valid=true。完整历史changed set仍由未改政策选择research-web-docker gate，按用户暂缓如实MANUAL_REQUIRED，因此总体result=BLOCKED、mergeReady=false/releaseReady=false；没有删门或假PASS。Mac必要自动门与本机基础模型/公开Skill范围PASS，这个事实不因其他平台暂缓而停止推进，也不自动等于完整所有阶段交付。

最终剩余外部条件一次列明：阶段1B需要一个实际额外服务或本地推理端点的非秘密地址/模型及安全设置页录入条件（当前没有，不用同一服务换协议冒充新增）；阶段2商业源需要所属独立实例真实账户和一个获准dataset；阶段4需要真实Office/Word权限/可响应环境及所属测试资源清理证据（原timeout/UNVERIFIED保留，不重试受保护目录）。不要求把Key发到对话、不购买/管理供应商账户、不读取生产/个人开发工具凭据。阶段3当前数据准入实现与真实公开NAV链路PASS、阶段5Mac干净交付CI PASS、阶段6最小设计完成；1B/2自有账户/4实机不具备完成证据，全部阶段仍未完成。草稿PR不合并、不发布、不更新生产、不启动暂缓平台。

独立实例实际运行命令从工作目录/Users/leon/.codex/worktrees/settings-model-loop/ResearchWorkbench执行：.venv/bin/python /private/tmp/rwb-dsh-upgrade-acceptance-20261007/instance.py {start,status,doctor,stop}，start复用正常WebServiceManager安装门与受管入口，实例根/private/tmp/rwb-dsh-upgrade-acceptance-20261007/research-web，设置入口在start后核验为http://127.0.0.1:19088/#/settings/model。当前已停止且无Key，恢复运行不代表有推理能力。公开日常./rwb web start/status/doctor/stop默认8088/3081，本轮只核对--help，未以它们操作生产。


### 持续Goal逐项审计与1B可行性证据

上一Goal轮为实际progress：提交9f30/32cd、当前三门SUCCESS、产品清除与所属停止；不是等待或只重述计划。本轮本地HEAD e5fd7a486、工作区clean，重新比对原附件阶段3—6。阶段6六项边界及独立未来任务已在05-security-validation第175节覆盖；Mac原生与当前CI证据可复用，未执行的账户/Office/容器事实不改PASS。

为避免只因未购买其他服务便停止独立工作，实际窄查已安装本地资源：Ollama可执行文件/标准Application与LM Studio标准Application未发现，11434/1234无listener（不是全机扫描/没有读取个人配置）。官方Ollama文档确认本地OpenAI兼容API服务不要求Key。但固定485源码原生pi-ai实现并非无凭据传输：真实运行其catalog.spec.ts的“leaves an unauthenticated route”一项，PASS/70未选测试，明确结果No API key for provider: local-llm、请求0；来源默认catalog也没有可直接宣称可用的Ollama路径。这证明不能只加Provider字符串或让用户填假Key冒充无Key支持，fixture不等于真实模型验收。

核对官方Ollama v0.40.0 darwin archive167494179字节及发布digest；只向任务临时目录下载，180秒失败exit28，实收9623543字节，未校验为完整包、未解压、未执行、未下载模型、未系统安装。一次urllib release metadata读取也遇IncompleteRead，已有gh官方API完成固定release元数据，未连续重跑网络。当前仍没有可用额外真实端点，不将不完整下载或SDK文档计PASS。日志local-model-resource-audit.json/local-model-download-state.json/native-keyless-contract.log保留。

下一独立实施范围仍仅一种openai-compatible连接，固定协议openai-completions、显式base URL/model ID和auth mode。复用固定DSH LlmAdapter扩展与现有Agent循环，不能因原生SDK强制Key而伪造用户凭据；薄传输适配须拒绝重定向、有界超时/输出/错误处理，无Key模式完全不读取秘密，有Key模式只用与DeepSeek分开的固定系统ref；现有事务和活动任务保护沿用。先只认证实际文本/流式，未经真工具验证的连接只能承担明确不依赖工具的功能。产品/检查环境、全局DSH、生产、固定版本和锁不变；单一报告记录设计及实际失败，不额外建设模型管理框架或第二Vault。暂无真实端点仍阻断真实1B完成，但不阻断必要合同/最小连接实现的独立工作，Goal继续active。


1B当前切片实际RED：新增test_model_connections.py两个正向请求合同失败、6项既有/拒绝条件PASS；最小ModelConfig结构化校验后8 PASS。Black只读2文件PASS。新增字段不是Runtime支持标志：服务保留model_unavailable，UI仍只展示DeepSeek，尚未挂载新适配器/新增凭据ref/真实生成，不宣称1B完成。当前源码为本地2614ed4f1上的未提交main.py/新测试/直接模块文档及本报告；原候选32cd546cc的CI不认证该WIP。原API模型/凭据聚焦回归仍在执行handle23316，等待其真实终态；独立只读Python reviewer继续核对URL与模式边界。Goal保持active，下一切片实施薄适配及独立凭据事务，不因缺真实额外账户停止必要独立修复。


1B请求合同独立review发现DEL/C1未覆盖，新增两负例真实RED（2失败），最小补齐127—159字符拒绝后10 PASS，保留全部失败。原API模型/凭据聚焦回归handle23316已exit0，结果按compatible-config-original-regression.log记录；未消耗供应商请求。当前WIP还未公开新增服务或提交源码，后续继续adapter、独立系统ref与事务、Runtime恢复、对应本地闭包/当前候选CI。原32cd候选及其三门证据保持，不重复触发。


### 1B Runtime与独立凭据切片（持续实施，未交付）

先新增单次HTTP/SSE四失败合同与独立Keychain账户失败测试，再最小新增compatible-model.mjs文本/流式LlmAdapter。固定DSH公共CLI、owned overlay、正式research-web与私有Host回调实际挂载，合成OpenAI流真实通过原生turn/end，wire无Authorization/x-api-key、请求1、供应商0；不是只检查class/source标签，也不是真实供应商验收。fixture使用非秘密配置受控seed和直接Native提交，明确尚未证明页面保存闭环。

RESEARCH_COMPAT_API_KEY与原RESEARCH_DSH_API_KEY为仅两项固定系统ref，账号分开，环境/旧文件完全不读；两个ref拒绝Host record委托路径，browser-session读写保留。Python旧/新memory合同5 PASS/2既有opt-in skip；JSref/record合同先RED再PASS。新建专用真实Mac Keychain命名空间，原ref/兼容ref互不覆盖、另一data home不继承、替换、跨进程读取、清除后不恢复均PASS，最终四项命名空间/账户清理PASS，未打印/散列值；compatible-keychain-real.json/log是实际系统库合成证据，供应商0。

复用现有实例私有DataHub鉴权新增GET model-connection，只返回验证过的非秘密配置，不是取密HTTP接口/新Vault。列表不要求秘密，真正有Key请求只通过固定系统ref解析，无Key模式完全不查询凭据。HTTP不重定向、不自动重试，90秒超时、输入/输出/残流限制，不依据HTTP200生成PASS；工具/图片等仍未认证。必要Runtime launch65 PASS；PrivateChannel1 PASS，源URL污染2 PASS；本次目标JS24 PASS/1既有未设置固定source的skip，非全平台证明。

独立review发现三项真实问题，均留RED并修复：GET里污染的userinfo/query URL会返回秘密，现复用ModelConfig并固定异常、不回显input；prepared仅绑定地址会在切配置后用新Key访问旧地址，现捕获专属Key前后比对公共revision/连接，发送前再次检测，metadata查询不取Key；缓冲SSE取消后仍可能finish成功，现每次read、frame、yield恢复和terminal均检查融合signal。8 transport/factory/cancel合同PASS，修复后固定DSH合成路径再次1请求PASS/供应商0。后续保存必须每次配置/凭据变更更新公共revision并持久化uncertain；这项尚待实施，不将fixture默认无revision视为产品事务完成。

Black初次发现新测试格式，目标单文件修正后复查；isort/Ruff/diff exit0。Python/JS只读review继续定点复核，无真实Key访问或生产改动。当前工作区包含本切片源码、测试及直接文档，尚未提交/送CI；原32cd546cc的三门不认证当前WIP。下一步接通API保存/作用域状态/恢复与UI，再用完整 changed set规划当前代码本地闭包和必要CI，真实新增模型与商业账户、Word外部缺项保留，Goal active。


### 1B保存/状态/UI与真正冷重启切片

先两保存正例RED，再接通ModelConfig到configure_model参数。沿原model_test_lock/service.lock、活动父/子任务检查、持久化uncertain与失败恢复，不新建事务框架。ref/uncertain/cleared按仅两个固定provider独立，KEY2变化不影响KEY1已用配置；每次兼容配置/凭据保存或清除更新32hex公共revision，端点改变不许保留旧Key，旧会话下一次提交拒绝改变的地址/协议/mode。无Key模式明确required=false/configured=null/storage=not_required，完全不描述/解析模型秘密，保存/应用/推理分别投影。重录/清除、旧服务失败保护与旧会话改投拒绝4 PASS；随后清除后新旧请求阻断/活动任务保护2 PASS。原模型/凭据API20 PASS，原新连接合同17 PASS（新增两条安全回归另跑）。

真实固定DSH目录过滤empty group使首次保存503/model_unavailable，复现日志保留；使用已挂载适配器的固定sanitized catalog failure证明模块存在（非空假model）。同一个产品PUT保存和test API→正常create/send→research-web/framework-explain已通过合成SSE；真正退出再启动Host/DSH后GET恢复无需保存、test再次完成，合成2模型请求/供应商0，wire无Authentication。阶段1移除配置前state.configured=null是明确无需Key，阶段2清理配置后false；不是清除了真实vendor Key或模型真实账户PASS。两组owned进程均退出，只用原实际安装manifest/固定构建。

UI只读review指出dirty Provider选项未刷新、错误提交未清密码、保存期间新编辑会丢失三项P2，已分别修复并复审关闭：更新选项且保留用户provider，捕获FormData即清密码、所有路径移除FormData/提交对象秘密，busy锁定全部输入/select、成功才清dirty；clear载荷在busy禁用前捕获、provider切换即清密码，NoKey不访问密码。UI11+transport/ref组合23 PASS，语法检查PASS；此非真实浏览器验收，仍待阶段闭包。不会截图密码表单。

mypy四改动模块及其传递边界58诊断，冻结7e源码在同样产品解释器/配置同为58，逐项新增0/删除0；之前57/37属不同检查边界，均保留不自行豁免。Black/isort/Ruff按本切片执行，一项SIM102已最小改写，不改规则。唯一报告、原candidate32 CI证据保留；本次源码仍WIP未提交/推送，必须完整changed set规划、文档生成/相关本地闭包及新候选CI后才能交付。真实新增服务、商业数据账户和Word权限缺项仍不改PASS，Goal active，未更新生产/合并/发布。

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "单一兼容模型在现有Host/Runtime/系统桥接/私有通道及设置组件内实施，未增加服务节点、Agent loop、Vault或改变既有图源；实际API、冷重启与当前候选CI另留证。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "单一兼容模型在现有Host/Runtime/系统桥接/私有通道及设置组件内实施，未增加服务节点、Agent loop、Vault或改变既有图源；实际API、冷重启与当前候选CI另留证。", "diagrams": []} -->

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "单一兼容模型在现有Host/Runtime/系统桥接/私有通道及设置组件内实施，未增加服务节点、Agent loop、Vault或改变既有图源；实际API、冷重启与当前候选CI另留证。", "diagrams": []} -->

<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "单一兼容模型在现有Host/Runtime/系统桥接/私有通道及设置组件内实施，未增加服务节点、Agent loop、Vault或改变既有图源；实际API、冷重启与当前候选CI另留证。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "单一兼容模型在现有Host/Runtime/系统桥接/私有通道及设置组件内实施，未增加服务节点、Agent loop、Vault或改变既有图源；实际API、冷重启与当前候选CI另留证。", "diagrams": []} -->


### 1B当前候选前完整范围检查

当前完整Task240路径、PR73路径、增量36路径规划/Project Constraints均exit0；生成API atlas与Python索引真实更新，未缩小范围或改policy。JS闭包338 PASS/1既有未设置source skip；本次Python闭包仍在执行21258，先不写PASS。完整新增/修改Python7文件Black初发现追加测试格式，目标单文件修复；isort/Ruff exit0，mypy与冻结7e同边界58旧诊断、新增0。源码/独立合成Keychain/API保存/真正Host+DSH退出重启证据已复审，不重复真实生命周期或商业源请求。

一次fetch固定target master205d2a170d9ece9c2751e014b63abe326510ab9c，目标新增平台证据/能力投影与验收schema v4/v3、HTTPS Docker build传输及文档生成治理，导致PR81冲突；远端任务分支仍32cd546cc，没有并发覆盖。保留当前成果，本地检查点后只正常merge该固定目标，不rebase/force、不合历史分支，不执行暂缓平台。需按整合后真实政策重新生成闭包；旧schema2 receipt和旧CI不替代新候选证据。

Python累计闭包21258最终exit0：162 PASS/2既有显式opt-in skip，434.05秒；JS338 PASS/1已有source未设置skip。保存真实当前代码检查点后整合固定205d2a17，保留合成/真实系统库证据和失败日志。当前新增供应商请求0；合成固定DSH API与冷重启不冒称真实模型账户。


固定205d2a17整合的冲突按三方内容解决：模块文档保留当前平台支持/安全投影及本任务兼容模型/数据准入说明；架构map保留目标reading/source snapshot与新增platform源码，补回相对共同基线真实新增API/测试；README回执由Codex实际复核，index/atlas及Python索引按新生成器重建，不采用整仓ours/theirs。机器全局阶段随master保留已重开平台的项目事实，本聊天任务上下文仍严格macOS Native；不据项目文档的他任务授权推断可执行Windows/Linux/Docker验收，不改全局phase/config缩门。

整合后architecture/documentation检查exit0，目标新版验收按platform task与完整影响分别记hostAcceptance/platformHandoffs/aggregateAcceptance；使用正常merge commit并保持候选与报告身份分开，不把旧schema回执改字涂绿。新增source_manager只有capabilities投影，模型/系统桥接/协议源码无整合修改，已有受管合成冷启动与系统库证据可复用，目标直接platform/documentation/manager/bootstrap回归另实际执行。


整合候选d3f850e917fb8257adaf3543bb6bc02eaecb6e65已普通push。完整原任务256路径约束exit0，但PR对205d目标73路径发现dual-runtime新增权威docs/research-web-platform-support.md未更新（exit1）；执行脚本没有将这一FAIL作为后续push阻断，首轮送检已发出，不认定通过。保留失败证据，集中补写本兼容模型真实Mac Native/合成/他平台证据边界，复查完整Task/PR后正常补提交；不删门或伪造矩阵。后续用新候选CI，不继承d3f尚未完结的状态。


冻结修正候选93bc351c480d10609beb4dd7a98f148f9dc04beb已普通push，base205d2a170d9ece9c2751e014b63abe326510ab9c，PR81 OPEN/draft/MERGEABLE。原任务完整256路径和PR74路径约束均exit0；Git-bound plan v4绑定实际候选/基线和完整PR差异，另保留原任务全部影响，不用最后报告代替源码范围。

当前自动门Project Constraints37593249902、Research Web Checks37593249884已success，attempt1/pull_request，实际checkout均e3fac2c9c31ea73b9c9114948bbec535132c5114；Git对象实际parents=205d2a17+93bc351c。macOS Bootstrap37593249891仍活跃，不标通过。初次d3f的Constraints37592987727确实failure、Web37592987740 cancelled；旧Bootstrap37592988138在取消请求时已terminal，未重复取消，旧结果不替代新候选。后续只用当前run证据。

新政策保留Foreign Windows/Docker selected gates，当前Mac任务不dispatch、不修改global阶段或保护规则；按v4/v3区分hostAcceptance与aggregateAcceptance。当前未取得macOS新候选通过前host尚不PASS；未执行Foreign/真实账户事实保持NOT_RUN/NOT_READY，mergeReady/releaseReady不涂绿。没有真实模型Key配置进CI，供应商0，安装/工具Actor消耗只用标准public runner。


### 冻结兼容模型候选最终证据（93bc351c）

当前代码候选93bc351c480d10609beb4dd7a98f148f9dc04beb、base205d2a170d9ece9c2751e014b63abe326510ab9c，PR81 OPEN/draft/MERGEABLE。三个当前自动门37593249902 Project Constraints、37593249884 Research Web Checks、37593249891 Mac Bootstrap均attempt1/pull_request SUCCESS；实际checkout均e3fac2c9c31ea73b9c9114948bbec535132c5114，真实Git对象parents=205d+93bc，未把分支HEAD与merge preview混用。macOS artifact id11469811443/name research-web-bootstrap-macos-14-37593249891包含doctor/connections/root.html/app.mjs，Doctor ok/installation_ok/product_ready=true/issues=[]；只无供应商凭据标准public runner，不dispatch。

相关本地闭包162 Python PASS/2既有opt-in skip、338 JS PASS/1source未设置skip，整合448 Python/207治理JS PASS；补齐本平台未重复覆盖的local integrations/runtime contract/container supervisor/setup闭包287 PASS/1既有skip。Black/isort/Ruff/diff通过。最终整合源码mypy四模块及传递图58诊断，与冻结205d源码同解释器/规则58诊断逐项相同、新增0/删除0；先前读取仍运行的baseline25只是临时截断，未据其判定新增缺陷，terminal后比较才有效。

唯一plan/receipt已更新为logs/settings-model-loop/plan.json（Git-bound v4）/receipt.json（v3），当前PR全部74路径、task=Mac feature-development、完整平台门保留；原任务256路径完整影响和约束另保留，不只检查末尾报告。校验exit0/valid=true/result=PASS/hostAcceptance=PASS，aggregateAcceptance=NOT_READY、mergeReady=false/releaseReady=false；Linux handoff BLOCKED（通用Ubuntu CI通过、Docker NOT_RUN）、Windows NOT_RUN，未执行不能写PASS。只读delivery summary同样通过，runtimeUpdated=false、PR81；它不独立认证GitHub/实例，但这些另有当前API/checkout/进程证据。

本地后续报告提交仅报告，不再push触发bootstrap；该报告HEAD未被上述CI测试，实际源码差异将核对只含报告。当前候选适配器、事务、私有配置、系统ref、无Key/Key合同与合成正常入口/真正冷重启通过，仍没有新增真实供应商/本地LLM的真实推理账户证据，不宣布完整1B。Ollama v0.40.0官方archive下载180秒exit28/实收9623543而非167494179字节，未执行/安装；不得以模型名/源标签/fixture冒充真实模型能力。合成实例配置清理、所属Host/DSH/服务器退出，无模型Key留存，真实Mac系统库测试新命名空间也已清除；本轮真实供应商请求0。

剩余独立真实资源仍是：可用新增模型端点/模型（如需Key只通过产品安全设置页）、所属商业数据账户与一个获准dataset、Office/Word真实可响应环境及其原隔离临时资源清理证据（timeout/UNVERIFIED保留）。全授权不是这些资源存在的证据，不索取/复制个人工具或生产Key，不购买管理供应商账户、不重复TCC目录读取。已完成数据准入、兼容连接实现与Mac当前代码CI及最小未来部署决策；全部阶段尚未达到完整真实闭环，Goal保留active供持续任务，生产8088/3081不变、未合并/发布。

### 1B实际本地模型与产品冷重启收口（2026-10-07）

上述“新增真实端点缺失”已解除。官方 Ollama v0.40.0 darwin 资产616313466通过同一有界Range传输完成：167494179字节，SHA-256 b490b4925a95c5f3dfcd889e566cf3dcd727848d59057fb00b03f1d6630326dc，与官方发布digest相同；`codesign --verify --verbose=2` exit0。只解压到 `/private/tmp/rwb-ollama-1b-20261007/distribution`，不安装全局应用或产品依赖。进程HOME、OLLAMA_MODELS均在该任务目录，OLLAMA_HOST=127.0.0.1:19434、OLLAMA_NO_CLOUD=1；未登录云账户、未读取个人工具配置、未存供应商Key。正式模型拉取均exit0。最终Qwen2.5 0.5B身份a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67、397821319字节、GGUF/Q4_K_M；软件/模型digest是公开包身份，不是秘密hash。

沿原真实安装环境 `/private/tmp/rwb-dsh-upgrade-fixture-20261007/admission-web` 和固定48504f07源码，通过正常WebServiceManager启动Host19089/DSH14181。首次Web退出的原因是前序fixture创建的MCP控制记录绑定8088，而受管测试实例明确19089；按私有文件0600/owner/regular验证后，原记录仅在其所属测试home改名保留，正常启动自行生成正确记录。未修改MCP合同、产品源码、生产或安装manifest。Doctor installation_ok=true；修正后的公开受管启动product_ready=true。

实际页面 `http://127.0.0.1:19089/#/settings/model` 选择OpenAI兼容文本/流式、填写非秘密回环地址、选择本机无Key模式并保存。真实浏览器刷新恢复Provider/model/地址/模式；状态明确区分配置已保存、Runtime待应用、尚未测试。API credential_required=false/credential_configured=null/credential_storage=not_required。浏览器专用插件遭签名错误，保留环境失败，使用已开放CUA完成页面操作；只截取非秘密状态区域，不截取密码表单、请求体、Cookie或认证链接。

保留两次失败：smollm:135m真实HTTP200有文本但max-tokens结束，产品正确判incomplete，不计PASS；第一次Qwen调用在pull完成前错误发出，HTTP404/compatible_http_failed，不计PASS，不隐藏为网络成功。确认pull exit0及实际/api/tags身份后，产品model/test沿framework-explain、固定DSH和新适配器真实得到“模型生成测试完成。”，原生turn/end completed（session1715dcc8-24f9-4214-bb41-a467f35bbcbc）。随后正常stop实际退出Host92825/DSH92620，status两者pid=null/ready=false；正常start新Host22110/DSH21783，不再次保存即恢复qwen2.5:0.5b/noKey，并再次得到同一最终文本及completed（sessiond96d97df-aa7a-41ce-8e40-47be4245b2e0）。API runtime_applied=true；页面分别显示新会话默认模型、无需Key、已收到最终文本。

另通过正常POST sessions与messages创建普通fingpt会话，正式research-web preset完成文本回复（sessionb47ba098-727b-4850-98f6-2ec522cb0c93），不只是model/test快捷入口。原生completed/实际source=openai-compatible/qwen2.5:0.5b/toolEvents=0。回答冗长且有概念错误（误称分散投资降低系统性风险），因此只认证文本调用链，不认证研究质量；小模型不作为金融研究质量基准。兼容服务工具/多模态仍未验证且明确不支持相应任务，未放宽能力声明。

本切片总计5次本地模型HTTP请求，状态200/404/200/200/200；其中首个200不完整，后续3个200 completed。真实供应商请求0、工具0、自动重试0。实际命令包括产品解释器运行 `/private/tmp/rwb-ollama-1b-20261007/product_acceptance.py` 的doctor/start/state/test/stop/status；官方隔离CLI pull smollm:135m与qwen2.5:0.5b；普通研究经同源HTTP create/send及原生history终态校验。具体证据统一留在 `logs/settings-model-loop/data-admission/compatible-real-*`、ollama-range-state.json，官方传输/模型资源仅本机临时目录，不入Git或CI artifact。

最终正常受管stop已退出所属Host/DSH；Ollama PID5966在核对精确可执行路径、serve命令和专属process group后SIGTERM退出。19089/14181/19434均不再监听；compatible-real-final-cleanup-counts.json包含实际五次请求、清理与端口证据。该连接从未存Key，凭据清理为NOT_REQUIRED，不伪称清除了真实Key；保留非秘密连接、测试资源与脱敏证据供复现，不修改生产8088/3081。已有Word资源的UNVERIFIED不能由这次清理覆盖。

源码与固定候选93bc351c480d10609beb4dd7a98f148f9dc04beb一致，本切片只新增本地真实证据与本报告；既有完整256任务路径/74PR路径plan、receipt及三个匹配CI继续保留，不重跑全部C1/C2或真实旧服务生命周期、不冒称新报告HEAD已被CI测试。1B选定的一条macOS Native无Key文本路径已取得保存、测试、普通研究调用、真正Host/DSH冷重启证据，凭据隔离合同/真实系统库合成证据复用未变源码。带供应商专用Key的新增服务真实账户仍未验证，不承诺所有品牌、工具能力或研究质量。

独立可完成工作收口后仍缺：阶段2自有商业账户与具体获准dataset；阶段4选定Office/Word真实可响应环境，以及原超时隔离资源的清理确认（UNVERIFIED）。这些缺项此前已连续记录，不能由扩大授权、fixture、旧CI或本地模型替代。Windows/Linux/Docker由所属平台任务留NOT_RUN，非本Mac任务阻塞。现有候选机械hostAcceptance=PASS，aggregateAcceptance=NOT_READY、mergeReady=false/releaseReady=false；全部阶段整体不能标完成。不再自动重试相同Office/TCC失败，不购买账户，不索取Key。最小解除条件是通过产品安全入口配置一个真实可用且具dataset权限的数据账户，以及可实际响应的Office/Word授权环境与所属资源清理结果；不需要扩大Git/安装权限。

## macOS Word 有界收口：产品侧调查完成，旧资源仍待确认

### W0：当前基线

本轮开始HEAD=54f84900235bc2f63c069edd3821999093647230，工作区干净；PR81实际OPEN/draft/MERGEABLE，head93bc351c480d10609beb4dd7a98f148f9dc04beb、base205d2a170d9ece9c2751e014b63abe326510ab9c。不fetch整合新master、不reset、不覆盖后续成果。累计报告顶部现在明确当前状态，历史B缺证据与旧T6 NOT_RUN不再覆盖后续豁免/真实通过记录。当前旧源码、实际CI预览e3fac2c9与本地报告HEAD分别保存，不把报告HEAD说成CI测试过。

### W1：原对象与归属限制

原验证记录来自本任务 `logs/settings-model-loop/dsh-upgrade/word-verification.json`：ID aabce313-3f97-43c7-a797-0e6283d42c40、target=word、status=completed、outcome=timeout。创建2026-10-06T18:46:58.236133Z，结束18:50:08.418496Z，耗时190.182363秒；用户本地时间为2026-10-07 02:46:58—02:50:08。

实例归属为 `/private/tmp/rwb-dsh-upgrade-acceptance-20261007/research-web`。只核对其已知 `local-integrations/local-integrations.json` 和 `local-integrations/verification-runs`：持久记录有word/outcome=timeout、结束时间与上下文指纹，没有validation ID到文件run UUID的映射；任务run目录现为空。源码中验证文件应落在 `/Users/leon/Library/Containers/com.microsoft.Word/Data/Documents/research-workbench-<32位随机run UUID>.docx`，但该UUID由工作目录另行随机生成，不是验证ID移除连字符所得值，无法从现存记录推导确切文件名。

本轮没有对Office受保护目录做stat/list/read，没有切换工具绕过前次卡住的访问；没有扫描用户目录、Office容器或磁盘。旧清理仍UNVERIFIED：自己的run目录为空、finally尝试清理、工作进程退出均不足以独立证明Office文档不存在。文件是否实际创建、是否仍被Word打开、是否被用户接管均未知，未执行关闭或删除。

一次最小人工核对已提出：只在Word现有窗口或Finder“前往文件夹”上述已知Documents路径，确认该02:46—02:50测试时间窗内research-workbench-<32位字符>.docx的完整文件名及是否接管/保留；无需文档内容，归属不明时先不删除。不得把“访问曾未返回”归因为已证实TCC拒绝；没有请求重置隐私权限或扩大系统访问。本轮实机步骤停在旧对象确认处。

### W2—W3：链路、已证实症状与未知根因

现有链路为routes验证请求→manager建立验证ID/queued/checking→后台verify_target创建独立spawn工作进程与另一个随机run目录→Word验证器→结果归一/持久化/能力投影。父进程上限180秒加10秒协调宽限；原耗时和timeout结果符合该上限。已知日志仅有start、process_tree_kill_failed警告及最终completed，未保留分步骤、具体异常类型或文件run UUID。该警告不能单独证明仍有子进程，更不能授权杀共享Word。

| 链路段 | 当前源码行为 | 原真实证据 |
|---|---|---|
| 授权/Word响应 | osascript可归一明确的-1743/not authorized错误；外层统一有界停止 | 未取得授权结果或Word响应证据；不能断言TCC/登录/应用死锁 |
| 创建 | 先在Office sandbox生成python-docx种子，再由Word打开 | 不证明Word真实创建；种子是否生成也未知 |
| 写入/保存 | 仅对指定文件名的Word document改写并保存 | 没有步骤完成证据 |
| 关闭/重开/读回 | 关闭指定文档、重开同一文件、由Word读取并比对合成文本 | 没有成功证据；不能用DOCX可解析替代 |
| 工作进程清理 | POSIX专属进程组TERM/KILL及join；不退出共享Word | 原有一条kill警告，确切PID/异常类型未保存，存活情况未知 |
| 文档/目录清理 | 限定Office文件路径、检查普通文件/拒绝symlink；finally尝试移除文件和任务run目录 | 原独立目录审计未返回，旧文件清理UNVERIFIED |

`completed`表示作业结束，manager只将available提升为功能可调用；timeout仍callable=false。现有API与持久目标记录不保存分步骤或资源身份，这是原证据的诊断限制；未来诊断不能恢复已经丢失的旧随机ID。没有定位到足以解释此次190秒卡点的直接代码缺陷，也没有已复现的根因修复，不修改产品源码、脚本超时、安全判定或权限规则。若旧资源以后确认且环境条件实际改变，最多一次新实机调用前应为现有链路补最小run/步骤/清理诊断；本轮不为取得日志制造新的Office资源。

离线实际命令：`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q -k 'macos_document_verifiers_use_office_sandbox or verification_failure_outcomes_are_safely_mapped or posix_timeout_cleanup_terminates_the_worker_process_group or verify_target_timeout_uses_process_tree_cleanup_and_closes_queue'`，exit0、9 PASS/37 deselected，0.90秒，仅1条已有Starlette弃用警告。全部为离线隔离合同，不启动真实Word，不认证旧文件清理或macOS实机功能。证据 `logs/settings-model-loop/word-closeout/offline-contract-tests.log`；对象/源码与未知项为word-diagnosis.json、old-resource-ledger-audit.json、old-word-persisted-outcome.json。

### W4及验收范围

本轮新的真实Word验证NOT_RUN、新资源0；旧清理UNVERIFIED。旧对象未确认、前次超时条件也未证明改变，因此不启动新的Office实机调用。没有真实模型或商业数据请求，没有Office/Word关闭或删除动作，不改变生产8088/3081。商业账户仍是对应来源的独立验收缺项，不作为公开研究或模型使用前提。

完整原任务实际256路径、相对固定PR目标实际74路径已重新从git生成并用现有Git-bound v4规划器核对（full-pr-plan.json，exit0，L4及全部原有外部门保留）。这份完整范围核对不是最后报告提交的缩小版；本轮增量只为报告。未变源码继续复用93bc候选的本地/真实模型/公开NAV/Keychain/固定DSH及三门CI，不把报告新HEAD绑定到旧run。只对报告增量另生成L0计划/回执并检查文档治理、Python文件索引；不重新运行安装、供应商、截图或全仓类型整改。既有完整候选plan.json/receipt.json冻结证据保留，本轮Word条件与报告增量另附在word-closeout下；增量通过不改变总体mergeReady/releaseReady=false。

本轮属于附件完成条件B：可独立进行的产品侧调查及离线检查完成；Word超时具体原因和旧文档清理仍未确认，不称Word阶段完成。最小剩余条件是人工确认旧测试对象归属/不存在状态；处理旧对象后还需Word实际可响应或直接缺陷复现与修复，才满足一次真实重验条件。停止本轮，不自动启动商业账户或其他平台任务。

报告增量实际检查：`node scripts/check_documentation_governance.mjs --project .` exit0；`.venv/bin/python scripts/generate_py_file_index.py --check` exit0；`node scripts/validate_verification_receipt.mjs --project . --plan logs/settings-model-loop/word-closeout/report-plan.json --receipt logs/settings-model-loop/word-closeout/report-receipt.json` exit0/valid=true，L0两项PASS。该回执的增量就绪仅表示报告文档通过，不是Word功能/清理或整个候选就绪；整体状态另外记录于closeout-state.json并保持mergeReady=false/releaseReady=false。源码没有变化，未安装依赖、不运行Black/isort/mypy、供应商/Word实机或整套CI；未修改Hook、验收schema、required checks或全局平台规则。

### 旧Word对象人工反馈登记（2026-10-07）

本轮仅登记用户提供的人工核对，不重复上述离线调查、合同测试或CI。证据来源为用户本轮粘贴的终端输出；用户先执行 `cd /Users/leon/Library/Containers/com.microsoft.Word/Data/Documents/`，随后执行 `ls`。反馈提交日期为2026-10-07（Asia/Shanghai）；命令实际执行时间未提供，不以代理当前时间替代。

该次输出的两项完整候选名称为：

| 指定目录中的候选名称 | 本轮能确认的事实 | 不能确认的事实 |
|---|---|---|
| `~$search-workbench-ac1f792f764b405e8f8d8253d631b8f7.docx` | 用户该次ls输出列出了此名称 | 文件类型/正文文件存在、与验证aabce313的对应关系、创建步骤是否成功、用户是否接管 |
| `~$search-workbench-ffffffffffffffffffffffffffffffff.docx` | 用户该次ls输出列出了此名称 | 是否为本任务、其他任务或历史对象；全f标识不能独立证明来源或可删除 |

完整候选位置为上述指定Documents目录加各自名称。`~$`命名只能作为锁/所有者临时文件的候选解释，未经类型及应用状态核验，不宣称已确认文件类别。输出未列出相应 `research-workbench-<run UUID>.docx` 正文名称；这仅是该目录这一次普通ls输出的范围，不证明正文从未创建、已经删除、未在别处或全盘不存在。旧记录未保存文件run UUID，不能凭ac1…前缀、全f名称或时间补出旧验证身份。

用户未提供接管/明确保留或允许删除某个确切对象的反馈，因此不记录为“用户接管”，不记录为“已删除”。两项候选保留，旧清理继续UNVERIFIED；不再扫描该目录或其他位置，不重复要求确认同一核对结果，不关闭用户文档或退出Word。人工目录核对已完成，与旧资源归属及清理确认未完成是不同状态。

本轮没有源码修改、对象访问/删除/关闭、系统权限变更或新测试资源。Word原timeout及未知根因不变。未来再次实机验证前，仍必须沿原入口补齐验证ID与文件run UUID/目标路径映射、最后完成步骤、功能结果与清理结果；这些新增诊断只能记录新调用，不能反推旧文件身份或补造旧成功。本轮不实施新诊断或实机重验，不更新生产、不push/合并/发布；模型和商业数据请求0。原模型、公开NAV、兼容文本、Keychain及93bc候选匹配Mac CI均按原适用范围保留。

## 新授权：Office三件套与金融插件（2026-10-07）

用户随后明确要求打通本机Office及金融插件并授权必要操作，又确认Wind和iFinD均有可用账户。本轮重新进入原e13d6e09e工作树（开始干净），不回退、不合并历史分支、不改全局平台范围。当前实现/验收对象为产品目录已有的Excel、Word、PowerPoint、Wind Excel及iFinD数据接口；Outlook/OneNote/Teams安装不等于适配，不自动发送邮件、操作会议或个人笔记。沿feature-loop、最小失败证据和原验收规划器推进，唯一报告不另建。

### 最小产品修复及RED/GREEN

先证明现有API丢弃run/清理诊断（KeyError）、Word未原生创建、超时父进程仍尝试受保护Office文件I/O；保留office-diagnostics-red.log和word-native-diagnostics-red.log。修复仅manager/verifiers及相邻测试：预注册服务验证ID→32位run UUID→合成文件名，在原私有状态保留有界run记录，API只返回白名单非秘密字段；工作进程记录有限完成步骤、功能结果、清理结果。冷启动将queued/checking恢复为interrupted，不重新执行；完成结果与磁盘run状态原子写入，避免“完成但磁盘仍checking”。复审指出不可哈希诊断值以及冷恢复缺口，分别以失败测试修复并保留负例。

Word改为真实make new document，不再用python-docx种子假冒原生创建；save-as后重新按登记名称绑定对象。原错误码没有保留，不能把这次所有失败都确定归因为重命名；明确修正的是代码中缺少保存后绑定的引用风险，名称绑定的同资源关闭已取得实际成功证据。Excel仍沿原有合成种子→实际Excel计算/保存/重开值验证，功能与清理分别记录；PowerPoint沿原生演示文稿/幻灯片流程记录步骤。初始路径已存在时三目标均拒绝且不删除该未知文件。超时后只处理已登记工作进程/Excel PID，不重复Office受保护目录读写；未确认资源的私有进度目录不自动按年龄移除。

Wind验证器原先为不写文件的内存工作簿验证准备Excel Documents目录。Excel实机已出现文件准备阶段超时，因此先以失败合同证明这条额外受保护目录依赖，再改为现有任务私有状态目录；使用客户端已有isolated_app和isolated_workbook，不启动/选取用户现有Excel实例，不创建第二种验证器或Vault，不改依赖锁或固定DSH。

### 实际macOS产品入口与结果（失败完整保留）

使用真实既有安装证明与正常WebServiceManager：data home `/private/tmp/rwb-dsh-upgrade-fixture-20261007/admission-web`，Host19089/DSH14181，固定48504f07，产品.venv与受管Node24.19.0。每次源码加载需重启时只停止所属Host/DSH，Doctor安装门保持真实，不复制生产配置或Key。通过正式POST `/api/research/local-integrations/verifications`与GET结果，Office身份在调用前落盘；原生脚本osacompile成功仅作为语法检查，不计实机成功。

| 实际run ID | 最后完成步骤/实际结果 | 功能验收 | 清理 |
|---|---|---|---|
| Word212f1d02-c008-49d9-86ac-83ab10bfe4e6 | created/written/saved，约4.7秒后failed；不是190秒timeout | 创建、写入、保存有新证据；完整重开读回未通过 | UNVERIFIED |
| Excel283d2d51-859b-49c8-8fbe-febb5aa2a8cc | none，190秒timeout，未到准备完成或真实计算 | 未通过；只定位到文件准备前，具体OS/文件系统原因未知 | UNVERIFIED |
| PowerPoint13a4c00a-9b24-4eee-8e92-e8498ce98bbc | created/written，190秒timeout，保存未完成 | 未通过；未猜定为许可、保存弹窗或应用故障 | UNVERIFIED |
| Wind2cfe8b4b-29f4-444c-b0ed-c6d046e45339 | 独立应用心跳约31秒，outcome=available | 插件此次会话验证通过，不能代替数据集查询 | 验证器所属实例按既有客户端/登记PID清理合同结束，另核验实际停止 |

仅对本次明确登记Word212f文件做受控核对：完整路径与Word full name一致、正文在进程内精确匹配合成字符串、saved=true；不打印文档内容。首次元数据检查脚本和简化exists脚本有工具侧syntax error(-2741)，保留失败，不冒称Word故障。正确的名称查找返回open，严格归属比较返回owned_saved_unchanged；用同名重新绑定的文档引用关闭成功。随后仅重开这一个既有文件（未创建/改写新文档）在15秒超时，未继续关闭/删除，不把该维护当完整验证或清理成功。word-registered-close-reproduction.json与word-registered-continuation.json分别记成功/timeout；原Word作业failed仍保留。旧ac1…/全f两项用户候选没有访问或操作。

所有Office超时/失败不连续重试，未killall或退出共享Word/PowerPoint。用户需要确认Word是否出现文件访问/转换/激活提示；只请求提示类型，不要文档或秘密。未知资源不删除，本轮新Office计划文件名为research-workbench-<上述去连字符run ID>的对应.docx/.xlsx/.pptx，是否实际存在由步骤证据限定，不能从计划名称直接断言创建。

### Wind真实业务与iFinD协议事实

插件心跳通过后，经产品保存非秘密preferred_adapter=excel，创建一个不发送模型提示的正常fingpt会话e6c47116-21af-41aa-a92e-cc36c4e2bf1b，通过本实例既有私有认证通道发起一次market_bars查询：wind、000001.SZ、2026-09-30单日、1d、none、allow_fallback=false。HTTP200但数据status=failed、row_count=0、limitations=deadline；dataset3c135a65-d6f2-4882-9cce-a77e20ee46e0和失败快照保留，不自动重跑、不拿公开源替换，不宣称行情可用。模型请求0；Wind心跳与业务请求各一次显式顶层调用，客户端既有有限加载/心跳重试不伪称只有一次底层供应商请求。

iFinD当前目录本来是legacy/未完成DataHub查询边界，HTTPClient实际使用自定义网关/login、/health、Bearer协议。官方同花顺示例则为refresh_token请求https://quantapi.51ifind.com/api/v1/get_access_token，再用access_token调用业务服务；不能将终端用户名/密码直接发到猜测的官方/login地址。已有本地设置页19089已核验，但当前仍是旧表单，明确告知用户暂不录入，未读取密码字段、个人工具配置或生产凭据。已询问“是否有数据接口权限和现成HTTP refresh token”，仅要状态，不要Token；不自行重置Token或影响既有账户。资料：[官方HTTP示例](https://quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/example.html)、[权限与Token规则](https://quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/help-center/faq.html)。真实iFinD调用NOT_RUN，不能将账户存在当接口已通。

### 当前代码检查与未完成状态

Office本地合同最终56 PASS/1既有skip；4项文档/架构/额度/跨平台源码治理JS104 PASS，非其他平台产品证明。Word/PPT脚本真实编译exit0但没有替代应用验收。Black首次只读发现格式并按目标文件修正；isort/Ruff目标文件检查，不全仓格式化。mypy当前两个修改模块及传递图16诊断，与e13冻结源码同解释器/配置16诊断逐项相同、新增0/删除0；旧37/58不同边界保留，不增加ignore或改policy。Python索引已按新增私有函数重建，API atlas check通过。77路径完整PR规划L4，全部原外部门保留；约束初次缺local-integrations结构决策exit1，补真实“原节点内诊断/持久化扩展、结构不变”记录后exit0，不改规则求绿。其余实际闭包/新候选CI尚须完成，不把旧93bc CI认证当前修改。

当前只已修复诊断、归属及清理保护并取得上述部分真实步骤；所有Office/金融软件未全通。Word/Excel/PPT具体卡点、对应资源清理、Wind数据deadline、iFinD官方接口权限/Token仍各自单列。已通过的模型/公开NAV仍有效；不重做B归因/T6/Keychain/DSH升级，不改生产，不合并或发布。总mergeReady/releaseReady继续false，下一步仅补受影响工程闭包及匹配新候选CI，并在人工/接口条件真的改变后处理相应实机部分，不无限重复失败操作。

Office修复送检前，本机集成+协议+API累计相关回归实际129 PASS/1既有skip，307.79秒，office-local-regression-closure.log；治理JS104 PASS。最终目标Black/isort/Ruff及diff检查通过，文档治理violations=[]、Python索引check通过，mypy最终与冻结e13同边界16旧诊断逐项一致。Python只读复审确认两项P2闭合且未发现新增重要问题，未代替任何实机证据。当前仓库API为public，PR81 OPEN/draft/MERGEABLE、远端head仍93bc/base205d；只沿普通同任务分支送检，不合并、不提高预算、不dispatch他平台、不把Goal虚假标完成换权限。

### 本轮工程闭包、接口条件与停止状态

固定送检源码为 `0c5c967258e29ce35e9bdb28cbe218abfc073f46`；PR #81目标为 `205d2a170d9ece9c2751e014b63abe326510ab9c`，实际CI检出的合并预览为 `4ef494d0deab00304b80979e1ac4cf1c33eb5990`，父提交对应上述base/head。完整PR范围77路径，原任务范围与本轮增量分开保留。PR继续草稿、仅送检、不合并。

| 当前候选自动门 | Run / attempt / event | 实际结果与平台 |
|---|---|---|
| Project Constraints | 37645938961 / 1 / pull_request | success；Ubuntu通用合同，不计macOS实机 |
| Research Web Checks | 37645938981 / 1 / pull_request | success；Ubuntu通用合同，不计macOS实机 |
| Research Web Bootstrap | 37645938975 / 1 / pull_request；job112876575295 | success；macos-14标准runner，干净安装、启动与Doctor通过 |

三项metadata的head均为0c5，checkout均为4ef。Mac artifact11495050188的Doctor为ok=true、installation_ok=true、product_ready=true、issues=[]。证据在 `word-closeout/office-ci/`；只留metadata与脱敏checkout行，未上传供应商凭据。未手动dispatch、rerun或修改额度。原 `plan.json/receipt.json` 已对应完整0c5候选，校验valid=true、hostAcceptance=PASS；aggregateAcceptance=NOT_READY、mergeReady=false、releaseReady=false。这仅闭合工程门，真实Office/商业数据缺项保持原结果。未变模型/安装/运行边界的历史证据复用依据记录于office-evidence-reuse.json，并由当前相关API/协议129 PASS及新Mac安装CI补证。

用户最新明确iFinD只有终端账户、接口权限不确定。记录为接口许可/安全Token路径未确认，不等于没有账户，也不推断已经具有官方API权限。当前自定义网关表单不能直接承接官方Token；本轮没有iFinD请求、Token提取/重置或账号权限变更。接口真实验收须先有官方权限事实及匹配安全接入，不能通过终端登录或HTTP200替代。不要要求购买账户或发送秘密。

正常受管stop实际exit0：所属Host70793和DSH70648已停止；随后status exit0，两项pid均null、ready=false。证据office-owned-host-final-stop.json及office-owned-host-final-status.json。未停止生产8088/3081，未退出共享Word/Excel/PowerPoint。应用窗口元数据没有列出与登记ID匹配的授权/保存提示，但不据此断言无模态提示或应用可调用。旧Word候选及本轮未确认资源继续保留UNVERIFIED；停止Host不等于Office资源清理。

仍未闭合的实机条件分别为Word同文件重开超时、Excel文件准备超时、PowerPoint保存超时、Wind业务deadline，以及iFinD接口权限/接入。没有确定Office系统级根因；不能仅调大超时、连续重试或绕过受保护目录。已提出的Word提示类型反馈尚未取得，不重复询问同一问题。独立工程工作已完成，实机功能目标仍未全部完成。后续只有相应应用响应/权限条件改变或直接缺陷得到失败证据后才恢复受影响实机步骤。原模型、公开NAV、T6和B豁免不重新打开。

本节之后的本地提交仅更新报告，源码候选仍冻结0c5、CI对应4ef，不能说CI测试过报告新HEAD；不为报告追加反复推送/安装CI。最终报告增量按L0检查，完整交付范围和冻结验收证据保持不变。此次模型请求0，生产未更新、不合并、不发布。

### Office插件机制调研与确定性路径修正（2026-10-08）

用户将当前重点收窄为Office修复，并要求调研Claude/Codex插件机制。宿主macOS，任务为功能修复与只读方案调研，不推进金融插件，不改变其他平台规则。基线fe7df77de，开始工作区干净。已读取现行AGENTS、架构/开发地图及相关模块文档，沿bugfix-evidence与现有最小规划器，不安装依赖。

官方证据区分四层：Claude for Microsoft365是Office内的加载项，支持Excel/PowerPoint/Word等；Claude Plugin可打包Skills及本地/远端MCP，打包本身不增加Office对象权限；Codex公开文档明确当前ChatGPT for Excel直接工作簿控制只承诺Excel；文件生成Skill可产出DOCX/PPTX/XLSX，不能据此说调用了本机Office。微软Office Add-ins由manifest和Web应用构成，通过Office.js操作当前文档，可在Mac运行。厂商具体内部传输、实现源码及第三方可直接接管其账户通道未获得证据，不猜为通用可复用MCP。

来源：[Claude Microsoft365](https://claude.com/claude-for-microsoft-365)、[Claude插件/连接器](https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors)、[Codex Excel加载项](https://help.openai.com/en/articles/20001063-chatgpt-for-excel-and-google-sheets)、[微软Office Add-ins架构](https://learn.microsoft.com/en-us/office/dev/add-ins/overview/office-add-ins)。这些公开资料不证明用户实际使用的每条工具路径。当前Codex文档会话查询一次网络transport失败，未重复请求；Plugin目录查询只返回SharePoint/Outlook/Teams等，没有得到可直接供本项目使用的三件套原生桥接证据，不安装无关插件。

本项目实际是Host→私有Python验证进程→AppleScript/xlwings→原生Office，与绑定当前文档的加载项机制不同。已有脚本replace_huaan_word_charts_office.py会处理Grant File Access提示；不运行其点击授权逻辑、不访问业务文档、不复制此行为来绕过用户权限。本次Word AX显示在启动/最近文档页，没有当前文件访问提示，已登记212f测试文件在最近列表；不点击或重开、不认定文件存在/清理完成，不保留无关最近文件名。该观察不是此前卡点权限根因的证明。

发现确定性代码缺陷：PowerPoint sandbox映射为com.microsoft.PowerPoint，但本机/Applications/Microsoft PowerPoint.app/Contents/Info.plist实际CFBundleIdentifier为com.microsoft.Powerpoint（Office16.113.3）；微软官方sandbox文档同样如此。新增路径合同实际RED，修正一行后相关测试4 PASS/54 deselected，0.69秒，Black/isort只读通过。原产品.venv没有pytest的环境错误已记录；复用既有Native/Docker worktree测试解释器，不安装、不修改该环境。受保护目录未扫描，未知文件未操作。大小写不敏感卷可能将两路径解析为同对象，此修正不能证明旧PowerPoint保存timeout已解决，也不涉及Word/Excel卡点。

建议借鉴的方向为：在Office内部绑定当前文档与会话，按应用实际支持的API登记能力；Host沿现有认证/工具边界发送有限结构化操作并读回结果。优先使用微软OfficeDev公开样例与Office.js，而非复制Claude/OpenAI私有插件或给模型任意JS执行。MCP只是暴露此桥接的可选协议，不能修复底层未工作的驱动。打开/保存/关闭、权限与文件系统清理仍须分别验证，Office.js并非无条件替代应用生命周期和Wind加载项。此为调研建议，尚未新建加载项、桥接或MCP框架，不将方案写成已交付。

路径修正的新源码尚无匹配CI，旧0c5/4ef仅认证旧候选。本轮真实Office新验证0、供应商0、生产未更新。整体Office目标仍未完成；完整PR差异继续按当前规划器记录，不能只用这一条路径测试冒称全部验收。

本次增量工程证据补充：架构JS76 PASS，完整差异Project Constraints violations=[]，文档治理、Python索引、diff检查exit0；Python只读复审Approve，未发现新增重要风险。工具尝试错误保留：产品.venv缺pytest，旧task context绑定0c5与本次HEAD不匹配（后改用真实fe7及工作区摘要生成独立plan，未改策略），猜测check_project_constraints.mjs不存在（后按plan实际命令.agents/project-constraints.mjs执行完整changed set）。不将这些环境/工具错误称为产品缺陷。新源码未完成当前CI/实机，权威冻结0c5回执仍只描述旧候选；本次仅本地检查点，无push、无新Office资源。新功能机制只调研，不将Office.js建议实施成另一套框架。

## 当前有界Office Goal续接（2026-10-08）

已读取目标附件goal-objective.md及用户随后提供的RWB-Word-Excel-PowerPoint-Codex-Goal.md。最终范围为现有Mac Native+Web三件套文件业务和原生业务六项，六项均须实际闭合；不建设Office.js/Graph/MCP/新Harness，不扩展金融插件。固定本轮起点1653e304d029829d03213ea404cf19c819317733，不回退附件参考候选，不追赶主线漂移。此前PowerPoint路径合同修正及官方机制调研为进展，不能替代本Goal。当前Goal active、未完成。

现有链路定位：report_rendering.py通过原sandbox执行report_render_script.py；会话Store已允许docx/xlsx/pptx产物并提供身份绑定下载；report_workflows/runtime.py会在报告交付阶段调用渲染器。原普通研究上传接口和composer仅接受xlsx，docx/pptx输入被拒绝。渲染器支持模板投影，但没有三格式统一的精确读取/局部修改业务合同；本机验证入口仅为设置验证，不能当作正式文档业务交付。后续以现有会话文件身份和受约束报告执行器补结构化操作，再接现有Host原生执行边界，不复制第二套报告系统。

先修上传连线：main.py既有上传白名单增加docx/pptx，composer附件picker同步。不改脚本权限、认证、30MB/20文件限制、文件归属、下载sandbox或依赖锁。API新增会话创建→上传→下载字节一致→跨会话拒绝合同；中文/空格文件名按既有安全规则规范化，不泄露任意宿主路径。DOCX用已锁定python-docx生成合成输入；PPTX上传测试使用既有报告测试形态的标准库slide-package fixture，仅验证字节交付，不声称PowerPoint可编辑/打开成功。初版测试导入未锁定python-pptx导致环境失败，复审定位后移除该开发环境依赖，没有安装包或改变产品锁。API RED记录保留，其中DOCX实际不支持格式，初版PPTX环境缺模块不误记为产品拒绝；UI RED证明PPTX/DOCX均未出现在accept。

本轮真实Office操作0、模型请求0、供应商0；未知旧对象未访问、删除或反推清理成功。新文件业务和原生固定样例六项仍NOT_RUN，上传修复不记为Word_FILE或PowerPoint_FILE通过。当前代码新改动没有匹配CI，旧0c5/4ef只认证旧源码；完整交付计划与阶段末门禁继续保留，不因这一小步缩小原Goal。

上传连线实际命令与结果：既有隔离测试解释器 `python -m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -q -k 'office_document_upload or upload_ownership'`最终exit0、3 PASS/49 deselected、19.56秒；`node --test tests/javascript/research_web_ui.test.mjs` exit0、32 PASS。Black目标文件check、isort check-only、文档治理、Python索引与diff check均exit0。证据office-upload-green-final.log、office-upload-ui-green.log及office-goal-upload-{docs,index}.log，初始失败不删除。复审未发现上传实现安全/归属问题，指出的未锁定pptx测试依赖已移除；JS复审无发现。完整PR影响面使用Git-bound v4 office-goal-full-plan.json保留，当前增量为上传连线，不认证原生或六项业务完成。

后续实施定位保持明确：文件操作逻辑扩展现有report_render_script.py，Host侧受审查调用及结果投影扩展report_rendering.py，沿现有session文件身份和报告入口接入；原生执行扩展现有local_integrations，而非模型任意脚本。不修改sandbox权限或添加通用宿主路径。读取、生成、局部修改、输入指纹/输出冲突仍未实施，分阶段监督、固定三样例以及UI诚实能力呈现也仍待完成，不能通过本次上传检查缩减最终目标。

### Office文档操作执行器在途实现（2026-10-08）

在0ddcf7d58后扩展现有report_rendering.py/report_render_script.py和report_routes.py，没有新Office框架/依赖/文件执行系统。新增严格document-operations API：format、read/generate/modify、file/native、会话file_id、expected_sha256；任意path/script请求被拒绝。文件模式用已有sandbox，Word固定样例生成/读取/段落和表格修改，Excel独立表/数值/公式并明确未重算，PPT基于已登记模板读和改文本对象。默认新产物保留原件；原生暂返回unavailable，不能冒充已实现。Runtime工具注册、普通Web页面操作入口、完整PPT有效模板和真实三样例、原生分阶段执行尚待接通，六项验收保持未完成。

最初Word业务测试因函数缺失RED；实现后真实macOS sandbox执行器原报告+文档回归初次8 PASS，再补复杂Word对象拒绝、坏回执不发布、PPT真实展示关系页序/保留原始未改页/命名空间合同，当前11 PASS。这些ZIP夹具仅文件结构合同，不认证PowerPoint原生或有效可编辑产物。正常产品API测试通过：创建会话→生成Word→按原下载URL读取并用Document独立解析→再经API读取表格；native请求明确unavailable、path额外字段422，1 PASS/52 deselected。证据office-document-{red,regression-reviewed,api}.log。未发真实模型请求，未启动Office或生产。

只读复审指出3P1/1P2，均保留事实：Word嵌入对象可能被run.text删除、PPT页序错误、PPT命名空间损坏、失败产物提前可见。已分别加复杂目标拒绝/范围检查、presentation关系顺序、安全lxml保留命名空间且只改目标页、父进程独占暂存身份校验后不覆盖发布。新负例验证修正后的行为；不伪称四个复审问题都曾先运行失败测试，初次来源为静态确证。还需复审当前代码及补齐并发/取消/输出冲突等闭包。既有冷启动状态不得被同步文件操作替代；完整原生生命周期还未开始。

### Office业务继续推进与真实页面断点（2026-10-08）

继续原0ddcf7d58工作区。PR81当前API核实OPEN/draft，head0c5/base205d不变；没有远端整合/推送，保留完整交付范围。任务仍active，未完成六项功能。

复审3P1已关闭，新增失败分支分别处理：登记Store.files/StoreError失败先有registration_failure RED，修正为按published inode撤回自有输出；外部替换不删除。输入暂存也按inode清理。取消以shield等待原30秒受管worker终止后再清暂存，不发布，取消合同PASS。暂存硬链接须在登记前移除并确认输出nlink=1，避免Store拒绝下载而仍宣称成功。新回归14 PASS，office-document-reviewed-closure.log；完整capabilities/renderer首次32 PASS/1 FAIL，仅精确目录期望缺新增research_document_operation，更新明确目录31项与write标记后定点1 PASS，原失败保留不跳过。Runtime/UI/guard/method四项JS62 PASS/1既有skip，非真实模型工具调用证明。

research_document_operation沿现有能力注册及guard有限名单，Host内部/data/document-operation沿现有X-Research-Data-Key私有回环middleware，trustedDirectory派生会话，不接受模型path或session参数。POST公开document-operations仍复用会话文件身份。Runtime测试证明越界参数/未准入拒绝及session绑定；没有增加任意宿主文件/脚本权限。模型请求0，尚未用模型实测选择该工具。

UI在原文件列表增加读取与修改；按现有结构列出目标，保留原件生成新文件；Excel显式值类型保留文本编号000001和布尔，不能自动按文本转数值。失败/原生未就绪保留原读回结构及草稿，只在成功写入和再读回后换文件身份；执行中禁用编辑。复审指出的草稿丢失和类型转换问题已修正，相关渲染/type合同PASS，还需复核事件链路。

原独立实例正常受管启动exit0，Host84415/19089、DSH84117/14181、product_ready=true，未改生产。使用正常API创建会话7f0f58b6-fba9-4bf5-bc4c-aaad9c1c154a（未发模型提示），生成Word初稿8aaaa8e9a0cb0ccff57dd43a。真实浏览器初次能读结构，但保存点击没有POST/新产物：移动“活动与文件”遮罩覆盖了追加在shell之外的编辑区域，实际点击关闭遮罩。增加有限提交日志并据可见DOM/CSS定位，改为既有dialog-backdrop/session-dialog层后再次操作产生新版本；未把初次点击记为成功。保存完成后又观察到保留旧busy表单使按钮仍disabled，增加busy标记并避免复用busy DOM，修复后再次表格修改成功。未创建任何Office原生文档或处理旧对象。

通过正常Web文件页实际将第二段改为报告版本B，再在该新版本将表格值改3；最终下载id4ef803567c8de90f22b5c3b1，文件 `/Users/leon/Downloads/document-a428bbb2fb9145838aefc5c5f49f9cda.docx`。独立python-docx解析确认8项：页面下载与API同一字节、标题Title/加粗、未改段落、B段落、2×2结构、数值3、原输入指纹未变。证据office-goal-word-{api-live,download-check}.json。生成来自正常API、读取/两次修改/下载来自正常页面，尚缺页面生成操作和原生项，不把它合并为完整Word_FILE/Word_NATIVE通过。

独立实例继续运行供断点续接，浏览器验收tab标handoff，只有上述所属Host/DSH可管理；生产未更新。原生业务目前明确unavailable，三款原生本轮NOT_RUN。Excel/PPT页面固定样例、生成UI、原生分阶段诊断与业务执行、冷恢复和匹配CI仍需继续。新代码未提交，真实身份为0ddcf7d58加当前完整diff，不用旧0c5 CI证明新源码。

代码/实例证据精度：本轮Host启动早于最后的登记/单链接防护修正；已运行的Word正常成功路径证明页面业务连线，不将其冒称验证了所有最后新增失败分支。最终需正常受管重启加载冻结候选，再取得匹配的完整实机/CI闭包；当前失败分支证据来自受控回归。静态与地图/atlas增量尚须阶段末闭合，报告不能代替该门。

PPT固定中性模板资源计划：新增 `app/research_web/office-template.pptx`，仅两页固定可编辑标题/正文，作为现有报告模板处理器的缺省输入；现有源码模块不能承载二进制模板，因此单独保存资源，不新增执行框架。一次性构建使用Codex已捆绑python-pptx1.0.2，不安装依赖、不把它加入产品解释器或锁文件、不使产品桥接依赖开发者环境。产品复制此受管常量模板到任务私有输入后，仍用现有受约束处理器读/改/生成。真实PowerPoint打开、布局与编辑性仍需后续实机，不由静态模板有效性代替。

### 页面生成与两款文件样例（2026-10-08）

中断后核对HEAD仍0ddcf7d58及未提交完整diff，没有丢失或重做已有Word读回。Office generation测试初次RED为documentCreationPayload缺失；随后在现有文件面板加入Word/Excel生成表单，结构化字段不接收脚本/宿主路径；表格按制表符分列，Excel数值转换保留000001等文本编号，公式显示未重算。UI34 PASS，office-generation-ui-final.log。复审提出busy字段竞态时，当前新代码已用disabled fieldset包裹全部编辑字段，真实DOM随后确认字段全部disabled；不为重复发现改写保护。

Excel通过正常页面生成Inputs/ Summary、读取、A2改数字7、新版本保存及下载，输出8081b90177350d1c1d4e4d5f，`/Users/leon/Downloads/document-15cf753b078c461386b68756456da695.xlsx`。独立openpyxl检查8项均true：同下载字节、两工作表、A2数值/类型、A3保留、B1公式/类型、格式保留、原始样例内容仍2/3/公式、计算缓存为空。页面明确未重算，不能声称得到了Excel实际结果10。证据office-goal-excel-file-check.json；不伪称保存前后已采集Excel原始完整字节哈希，只认证实际原样例内容及版本合同。

Word也补齐了此前缺少的正常页面生成：标题/两段/2×2表格→读取→第二段精确改为“报告版本 B”→表格数值3→下载。最终5b9fdcd2102ec442df7eddac，`/Users/leon/Downloads/document-6cef609c05bb40dd94eafd68c248b480.docx`；7项独立读回检查均true，原始样例仍A和2。证据office-goal-word-all-page-check.json。这两款文件业务固定样例观察已通过，但源码仍待阶段末冻结与工程门，本轮Word_NATIVE/Excel_NATIVE均NOT_RUN。

原生错误分类另以6用例RED修正：只将标准错误号-1743映射自动化拒绝，-54/-61为文件访问拒绝、-1712为AppleEvent超时、-600为应用未运行（不冒充未安装）、-128为用户取消；单纯permission文字保持未知失败。可脱敏错误号仅整数白名单，日志不保留stderr内容，原管理器诊断保留有限错误号。又用2项RED证明未完成步骤会把原错误覆盖成verification_trace_incomplete，修正仅在“命令声称成功但缺步骤”时使用该码；实际失败理由保留。相关10 PASS，office-error-reason-green.log。Word/PPT命令设置AppleScript每个外部应用命令30秒等待，原总监督时限不增加；文件准备10秒、每阶段开始/结束/耗时和正式原生业务执行仍未完成，因此不运行新的Office实机操作。依据Apple公开with-timeout语义，未绕过TCC或权限，不推定旧卡点根因。

PPT模板已按计划生成office-template.pptx，29250字节、两页、每页可编辑文本对象ID2/3；产品默认生成复制受管常量资源到私有输入，源模板不改，结构化slides按有限对象映射。一次性构建的捆绑pptx1.0.2未进入运行依赖。模板生成/修改/第一页面原始字节/原输入保留合同通过，相关15 PASS；正常PowerPoint页面生成及真实应用打开仍待验证，不能以ZIP合同或生成库替代。UI已加入新建PowerPoint，Host当前进程先前加载版本缺此默认模板路径，须沿受管入口重新加载当前代码后再做实际页面验证，不借旧进程响应假称新版本已验。

### 三款文件业务样例已观察通过，原生仍未完成

为加载最新默认PPT模板和失败防护，正常受管停止Host84415/DSH84117（exit0，确认pid清空），再启动Host62020/19089与DSH61846/14181，product_ready=true。最新加载源码身份为0ddcf7d58加13个app源码/资源文件哈希，office-goal-loaded-source.json；不把HEAD当作未提交源码身份，不修改生产。正常页面从新建PowerPoint生成A稿，读取标题/正文对象，再将第二页标题B和正文3保存为新版本并下载。

最终PPT输出e6d2f8b7833f0fe199739ecd，原输入cec7f8264f5233b213d094a8，下载 `/Users/leon/Downloads/document-a5536d766fca4e429487e82f41b4c94f.pptx`。独立捆绑pptx解析/ZIP检查9项均true：同下载字节、两页、第一页标题/正文、第二页B/3、真实文本对象、第一页原始XML字节保持、原A稿仍存在。检查限定任务专用会话已登记的三个PPT版本，不扫描用户目录或Office容器。office-goal-ppt-file-check.json；该库只用于独立检查，不成为产品依赖。原生PowerPoint打开、视觉版式及编辑性仍须实机，所以这些结果只认证PowerPoint_FILE。

当前六项功能观察状态：Word_FILE、Excel_FILE、PowerPoint_FILE固定小样例通过正常Web页面并独立读回；Word_NATIVE、Excel_NATIVE、PowerPoint_NATIVE本Goal均NOT_RUN。Excel_FILE特意未重算，没有5/10真实计算证据；原生清理也未新执行，不反推旧资源清理。当前产品工程就绪还须完整changed set静态/本地闭包和匹配Mac CI，不能把文件项通过等同整个Goal或merge/releaseReady。PPT15项相关Python回归、生成UI34项JS、架构检查通过；待完成原生阶段监督及正式业务执行后，统一冻结送检，避免每个小改反复bootstrap。

本轮阶段末仍未提交/推送，所需完整静态及工程闭包正在累计，不用文件业务的通过替代Mac CI。Goal继续active，未出现须用户补授权的外部阻塞；下一项为完成文件准备/命令开始结束耗时监督和正式原生业务入口。已有独立Host62020/DSH61846继续运行供续接，不退出共享Office或扫描旧资源。三份最终文件分别保留于Downloads及所属会话outputs，不删除历史任务未知文件。

### 原生阶段监督在途实现（2026-10-08）

续接原0ddcf7d58加完整未提交diff，目标文件重新读取，未重新执行已通过文件样例。旧验证仅有最后完成step且总190秒等待；新增有限阶段JSONL存于原任务run目录，记录prepared/application_response/created/opened/read/written/saved/closed/reopened/read_back/document_closed/cleanup的started/completed及时间。Python与AppleScript同用整秒Unix时间，耗时精度1秒，不伪称毫秒精度。元数据不含文档内容/路径、Key、认证链接或stderr，仅白名单名称/时间；32观察/64事件/16KiB约束，FD拒绝symlink、非普通文件、非owner、多链接及过大文件，浮点/超大整数拒绝。

监督沿原spawn进程/进程组/登记Excel身份清理，准备默认10秒、其他活跃阶段30秒，原总限额不增加；真正phase超时返回office_phase_timed_out和timed_out_stage。Word/PPT现有静态脚本添加响应、创建、写入、保存、关闭、重开、读回和错误后本任务关闭的有限记录，既有recordStep接口保留；Excel记录实际既有调用及清理。阶段元数据经过原manager白名单进入诊断，保留冷恢复和未知资源保护，不新增Vault/Harness/预算系统或自动恢复编辑。

先有office_phase两项RED，后准备10/命令30边界与symlink拒绝GREEN；第一次邻接检查有1失败因为不必要替换recordStep名称，已保持原接口并扩展记录，未削弱原断言。完整本机集成67 PASS/1既有skip（office-phase-full-regression.log，25.80秒）；随后清理阶段补充和复审仅重跑邻接。Word/PPT受控捕获的静态脚本osacompile各exit0，office-phase-script-syntax.json；该操作不执行脚本、不打开/创建Office文档，不记作Native成功。

复审发现真实FIFO可让父监督器阻塞式open等待，继而所有deadline无效；用独立测试Python子进程2秒超时取得RED，修为O_NONBLOCK并保持FD类型/身份校验，7项邻接GREEN（office-phase-fifo-green.log，1.27秒）。同样保护progress读取与阶段写入，不能通过更换工具访问受保护目录。没有新的供应商/模型请求，也没有本轮新的Office原生任务；日常生产未更新。

此轮仍只补诊断与监督，正式业务native分支仍明确unavailable，不冒充已接通。下一步必须复用此监督接入受管业务Worker、当前会话文件身份及原manager记录，再串行取得Excel初始5→7后10→保存重开仍10、Word实际创建/表格/读回、PPT实际打开/修改/保存重开及各自清理证据。文件处理三项已有证据保留；原生三项仍NOT_RUN，Goal active，当前Mac工程门及完整changed set静态/匹配CI尚待统一闭合。

### Native Excel正式入口在途与测试隔离事故（2026-10-08）

本轮沿原manager.start_verification/_run_verification、verify_target spawn监督和XlwingsExcelProvider接Native XLSX read/modify：输入来自会话file_id/原件指纹的内存副本，工作文件位于本任务私有runRoot（不再依赖Office受保护Documents准备）；先重算读值、写指定cell、再重算保存、关本工作簿、同文件只读重开、比较值和原公式、关闭本任务新实例。原件不改，不执行refresh_all。进程基线和精确Excel身份通过才登记/quit，复用已有实例拒绝且不quit；归属未知保留unverified。父监督FD读保存文件、再清runRoot；文件bytes与readback仅在调用内存，不写现有状态账本。manager记录/冷中断继续复用，不增加新Vault或事务框架。Word/PPT及原生生成仍未接通，不能冒称完整native能力。

先有external formula缺函数RED；mock计算5→10/保存重开/公式保持/已有实例保护合同通过。复审随后指出拒绝黑名单不完整及普通cell.formula返回常量的误判。为新增IMAGE/WSET负例时，测试最初遗漏driver隔离，真实启动Excel45826；这次不是正式产品路径验收，不能记Native PASS，也不能继续写本轮绝对无外部请求。我们没有主动发商业数据接口请求，但未隔离测试可能触发Excel/插件后台或公式相关请求，实际次数未验证、保留UNKNOWN；不删除原事故记录。无供应商Key或账户修改。

立即对归属明确pytest45812先SIGINT再因SDK未及时返回而SIGTERM，未killall任何应用。对新Excel45826只查询该PID工作簿数量，确认0；再次核对启动时间Thu Oct8 12:43:29与精确程序路径后正常quit请求，随后因进程仍在沿既有精确身份清理函数停止该测试PID。最终独立ps确认45826不存在，原92919仍存在。没有关闭用户文档或其他Office实例；测试临时文件身份未取得完整目录证据，清理不扩大到其他位置，不宣称全部临时文件已删除。证据office-unintended-{excel-resource,excel-cleanup,excel-final-cleanup,excel-process-final}.json及原red日志，事故不作供应商/Office验收成功。

已把所有外部拒绝负例强制注入NeverLaunch，禁止触及真实driver；增加本地函数允许范围检查、外部OOXML关系/宏ContentType和定义名称入口拒绝；不支持的native高级公式明确失败，不静默file回退。只对原始以=开头的真公式保留检查，常量通过重开值比较。当前5项Native合同PASS，office-native-external-green.log，均mock/拒绝合同，非真实App通过。原文件业务15相关回归仍通过，UI34项通过；import只读发现两文件排序，沿目标文件最小修正，不改依赖锁。

Native返回明确mode/实际计算引擎/读回结果/verification_id/安全诊断，成功输出走同独占暂存/指纹复核/不覆盖发布。UI后续文件读结构不应把已实际计算的native结果显示成“未重算”，已用lastResult区分；尚待正式产品重启加载与真实验证。当前正式Excel_NATIVE仍NOT_RUN，事故单列；Word/PPT_NATIVE仍NOT_RUN，Goal active。Mac CI/完整静态/原生清理门仍未闭合，不用旧CI或fixture代替。不修改生产、不合并、不发布。

### 续接：Excel真实卡点与PPT受控业务路径（2026-10-08）

数组公式/局部定义名称两项RED确认旧准入将外部函数带至驱动边界；负例均强制NeverLaunch。现在拒绝非字符串公式对象，并检查workbook.xml全部definedName（包含localSheetId及保留名称）。另外3项目标RED确认不存在工作表/越界列会过晚失败；读取和修改均在启动前校验，缺省读取来自实际公式或首工作表A1，不再硬编码Summary。相关10项PASS：office-native-targets-green.log。

正常受管停止Host62020/DSH61846并启动Host74377/19089、DSH74177/14181，product_ready=true；office-native-loaded-{stop,start}.json实际退出码0。此启动加载公式防护版本，其后目标及PPT增量仍未加载。正式页面选择原件56675318a74b6b8caf8e85dc、Inputs!A2数字7、native保存，只执行一次。验证2fba53b5-dc1f-4d09-ade9-2d8c48711d5c：prepared完成；application_response耗时3秒；opened阶段30秒超时。页面明确office_phase_timed_out，没有产物或5→10证据。office-native-excel-first-live.json保留原账本诊断（页面码不冒充账本code字段），office-native-excel-first-resources.json独立核对登记资源。

只访问登记run目录：副本5378字节、普通文件0600、uid501仍存在，cleanup=UNVERIFIED，不强删。监督停止所属工作进程与独立Excel，ps仅保留原Excel92919。CUA返回noWindowsAvailable，没有可观察权限弹窗或错误号，不能猜为TCC。没有重复实机失败或扫描旧对象，根因未知。

PPT最小业务路径复用manager/监督/产物发布：OOXML ID映射同页唯一对象名称（安装SDEF没有shape ID属性），只支持有限简单shape_text，拒绝外部关系/宏/嵌入与复杂文本修改。固定AppleScript读取私有0600 JSON，不将内容嵌入命令行；只处理本任务副本，保存/关闭/重开并在App核对全部有限文本，绝不quit共享应用。缺执行器/产品路由unavailable的RED后，12项合同PASS（office-native-ppt-route-green.log）；osacompile退出0（office-native-ppt-syntax.json）。PPT仍未真实执行，编译/fixture不能记Native PASS。Word业务待补齐，Goal active，当前工程/匹配Mac CI未闭合，mergeReady/releaseReady仍false。


### 文件授权与原生业务增量（2026-10-08）

新PPT正式API验证527a482c-80fc-4e89-a12a-fe31af57be75完成prepared/application_response，但opened阶段超时；office-native-ppt-first-live.json保留原失败。用户随后明确确认该测试文稿的文件访问提示，人工允许后文稿实际打开。这是本次打开阻塞的直接外部条件证据，不将原失败改为PASS，不反推Excel必为同因。

自动界面读取仍超时，改以精确登记名称读取该文稿的name/full name/saved元数据，无文档内容或目录扫描。首次关闭的严格路径guard返回cleanup_identity_unverified；实际App给出/tmp路径，登记为/private/tmp。独立核对同设备/inode后，只允许这两个指向同一任务文件的路径且saved=true，关闭此文稿并确认不再exists，退出0、closed_confirmed；文件保留，不退出共享PPT。证据office-native-ppt-{app-identity,owned-close-confirmed,first-resources}.json。文稿关闭已确认，文件未删除，工作run保留；其他旧对象仍不操作。

Foundation桥接另有独立无Office复现：NSArray as list会转换为AppleScript records，objectForKey调用失败-1708。修为直接保留NSArray、objectAtIndex取NSDictionary；真实Foundation-only绿色回执及自动回归office-native-json-{contract-product-green,regression}.json/log，不把它视为App成功。PPT源通过正常/usr/bin/open -b受控单文件入口交接，再沿既有App读取/修改/保存/重开验证；不同于关闭沙箱或授权全盘。是否解除新文件提示仍须实机证明，当前不宣称通过。参考Apple官方Accessing files from the macOS App Sandbox / NSWorkspace（系统交互及隐式安全作用域；Launch Services方案效果为待实测推断）：https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox 、https://developer.apple.com/documentation/appkit/nsworkspace 。

Word增加原生generate/read/modify的私有结构化路径；公开API与生成表单file/native选择已连通，固定脚本按安装SDEF编译。缺执行器/路由/页面mode均有RED，相关绿色合同分别office-native-word-business-green.log、office-native-word-route-green.log、office-native-word-ui-green.log。脚本表格direct-parameter语法先-1723，修正targetTable变量后编译0。复审发现modify重写未选中内容P1；两个混合格式/单cell目标RED后，只写writes指定对象，目标混合run/复杂cell/合并拒绝，未选中内容只读回；不强行改变已有标题bold。3项preservation合同通过。当前Word未真实执行，此增量不标Native PASS。

目标Ruff已通过；mypy新诊断修复至本次三个模块零诊断，命令仍exit1、16条既有跨模块诊断（office-native-word-mypy-final.log），既有37条大范围诊断也继续保留，不自行豁免或扩仓整改。相邻完整回归曾96 PASS/1既有skip，后续Word/PPT增量按相关合同补验，最终闭包仍待冻结候选。完整changed set88路径已重规划L4，不缩小为本次局部测试范围；office-native-code-identity.json记录HEAD0ddcf7d58加脏工作树文件哈希，不拿旧HEAD/旧CI代表新实现。无提交、push、PR变更、生产变更、合并或发布。供应商模型主动请求0；事故外部请求UNKNOWN记录保留。


### 正常单文件打开后的真实PPT结果

受管实例以Host66948/DSH66792加载单文件OS打开与Foundation修正。正式API验证1348aae6-596d-4419-a997-fc54b8a4f3dd：opened约1秒成功，read/written/saved/closed/reopened均完成，read_back失败；document_closed与cleanup confirmed，不交付不正确输出。office-native-ppt-handoff-live.json保留原结果。该进展实测解除此前打开卡点，但不能标PPT_NATIVE通过。

补充仅含长度/布尔比较的诊断后，99683f9b-0e1d-45e2-b6cc-28662a7e6a15同样到达read_back；slide2实际/期望长度均6，trimmed_equal=false，错误-2700，明确native_document_readback_failed。这排除“仅尾随换行”的假设，未记录正文。清理仍confirmed。office-ppt-comparison-live.json。现增加写后立即校验及保存状态布尔值，用于区分写入与保存恢复；尚待一次带此诊断的观察，不以猜测放宽比较或吞失败。

Word/PPT脚本当前编译均0（office-native-current-scripts-syntax.json），19项native相关合同PASS/1既有skip（office-native-handoff-regression.log）；Word真实业务尚未执行，Excel打开超时仍待单独修复。三项FILE此前通过不受影响，三项NATIVE仍未完成，Goal active；本次诊断与工程门尚未冻结、未提交或送检，mergeReady/releaseReady=false。


保存诊断c1c568f8-95d4-445e-bfff-380d460cf531：修改后立即读回检查通过，但saved_before_close=false，重开后长度相同、文本不匹配；office-ppt-save-diagnostic-live.json，任务文稿关闭/临时清理confirmed。已证实保存命令返回不能证明写盘。安装SDEF/CocoaStandard定义提供save的as格式参数及Open XML枚举；最小修正为明确Open XML格式，并在原saved阶段30秒监督内等待saved=true，不设置saved标志来伪造成功、不加总时限。缺保存格式/同步合同RED已记录，绿色合同在office-ppt-save-contract-green.log；此修正尚待实际写盘验证。Word/Excel原生项仍未完成，Goal active，当前代码未冻结送检，不宣称完整1A或Office Goal完成。


### 续接保存调用根因（2026-10-08）

本轮核对branch/HEAD仍codex/settings-model-loop、0ddcf7d58加完整未提交diff；没有回退。上轮为实际进展，不是无进展等待。明确Open XML Save As修正经正式API仍在saved阶段30秒timeout：ac5756d7-13cb-4dc4-9ffd-007a597b296c，office-ppt-save-fix-live.json；故不认证该修正成功。精准App元数据确认该本任务文稿仍saved=false，源文件保留，没有退出共享应用。

在相同登记文稿上、完整/tmp路径与同inode任务文件核对后，将带路径Save As改为原地save诊断：退出0、saved=true（office-ppt-save-in-place-probe.json）。随后同文件关闭→正常OS打开→App核对4个目标文本（包含第一页保留及第二页B/3）→只关闭该文稿，退出0（office-ppt-save-in-place-reopen.json），文件保留。这是调用根因诊断，不冒充正式业务API验收。

实际产品最小修正为原地save加saved=true同步等待；原saved阶段30秒和总190秒监督不提高。新保存合同先RED后GREEN（office-ppt-inplace-contract-{red,green}.log），保留此前错误Save As尝试与绿色合同而不删失败历史。接下来沿正式产品API验证并独立核对产物，尚未标完整PPT_NATIVE/Goal通过。


### 正式产品PPT保存闭环通过，Word继续定位

8b79b55d-db16-4b12-9fac-200c48813cdb由正常公开文档业务API执行，真实Microsoft PowerPoint opened/read/written/saved/closed/reopened/read_back/document_closed均完成、cleanup confirmed；正确新版本235a8bbdc98b890e38faa771登记到原会话outputs。office-ppt-inplace-live.json记录完整阶段。第一页保留、第二页精确“结论版本 B”“样本数为 3”，App读回4目标；服务下载同产物33609字节，SHA256 a1a664b783a3365538ff239495d29d9a8f2774d8bee79c9dcdc58c5c970ecb19。独立已有捆绑pptx库检查5项均true（两页、第一页、新文本、可编辑文本对象、对象边界），不增加产品依赖；office-ppt-native-independent.json/final-native-powerpoint.pptx。视觉仍NOT_RUN，不能仅边界计算冒称实际无遮挡。

Word正常API原生生成1c069545-9dcb-45df-b408-9aa14f328bc8已真实created约2秒、read完成，written失败；只关闭本任务文稿、cleanup confirmed，无产物。office-word-native-generate-live.json。所属Host日志仅提取稳定错误号-1708（local_office_command_failed），不是TCC拒绝；本轮新Word写入卡点与旧保存/重开问题分开，尚需定位具体写入命令。没有重复同一Word失败。Excel仍保留打开超时。三项FILE证据复用，PPT_NATIVE保存重开读回通过但视觉仍待补；Word_NATIVE/Excel_NATIVE未完成。

Ruff目标检查exit0；Black只读先发现verifiers格式差异，已仅格式化该文件；源行为证据按同语义复用。完整88路径范围及工程/CI门仍保留，当前dirty代码无匹配新CI，不宣称mergeReady/releaseReady或Goal完成。独立实例运行，生产8088/3081未更新；无推送、PR合并、发布或供应商模型请求。


### Word表格命令断点

96d4e2ee-c2fa-4db6-a9a7-82e8a9954556正式API增加不含正文的write-step诊断：content与range已完成，convert-to-table失败-1708；document_closed/cleanup confirmed。office-word-write-diagnostic-live.json。不同于Word旧重开卡点，本次准确断在表格转换。不猜TCC/激活。

最小参数修正将Foundation数组count先明确coerce为AppleScript integer，再传Word声明为integer的number-of-rows/columns；对应contract RED/GREEN保留office-word-table-args-{red,green}.log。它是待实测的interop假设，尚未宣布修复成功；采用原30秒阶段/190秒总监督，无新权限或依赖。继续正式API验证，保留完整六项Goal与88路径交付范围。


### Word原生表格创建已推进至保存

ffecbaca-6577-4458-8fcf-336f2e4af7fe显示整数参数转换并未修复convert-to-table，仍range后-1708；排除该interop假设，不标其Native通过。改用安装SDEF已有table对象创建并逐格写入结构化值（不以docx库输出替代App），保留目标尺寸/内容后续核验。contract先RED后GREEN，脚本编译exit0。

57fd69f5-ea80-456f-a2cd-c204183f8d1e正式API实测created/read/written及table/style子步骤完成，saved开始后-1708；document_closed/cleanup confirmed，未交付错误产物。office-word-table-create-live.json。失败现在准确落在Word save-as命令，旧失败完整保留。最小标准文档save调用修正有office-word-save-{red,green}.log，实际保存/重开仍待验证，不扩大超时、权限或安装依赖。Word_NATIVE/Excel_NATIVE仍未完成，PPT已验保存重开但视觉缺项保持，Goal active。


### Word标准保存等待的当前断点

9796ac13-2a88-4103-bfba-92b659fe7849正式API已真实完成created/read/written（正文、原生2×2表格、样式），标准保存开始后超时，清理未确认；office-word-save-live.json。不把它写成保存通过或旧资源已清理。已一次询问用户当前是否为该9796目标文稿的保存/文件访问提示；不关闭未知/其他文档，不退出Word、不扩大授权或TCC。此前save-as -1708及convert-to-table -1708仍保留；原生对象make-table已通过实际written步骤，目标正文和表格未以库导出冒充App生成。

代码HEAD仍0ddcf7d58加未提交改动，Word生成合同及表格创建编译通过只作离线证据；三项FILE复用，PPT保存重开读回已通过但视觉待补，Word/Excel_NATIVE继续未完成。当前hostAcceptance新代码工程闭包/匹配CI未完成，mergeReady/releaseReady=false。Goal active，未push、合并、发布或改生产，供应商模型请求0。


### Excel单文件交接与进程归属修正

续接原worktree/HEAD0ddcf7d58，Word9796保存提示的单次人工状态问题仍待反馈，没有重跑该Word失败。独立推进Excel：只对已准入的私有run/精确xlsx单链接文件，正常/usr/bin/open -n -b com.microsoft.Excel交接到新实例，保留旧PID baseline、program/birth校验与既有xlwings执行器，不借共享生产或用户当前Excel。

最初唯一新增PID方案被只读复审判P1：并发用户新进程可误认归属。补“唯一新增但无任务工作簿”RED，旧实现错误地available；现在只读candidate实例中已由系统打开的精确任务book、要求仅1book且fullname命中任务路径/已知/tmp别名，之后才owned/登记PID；绝不books.open制造归属证据。未知不quit/kill、不登记且保留任务副本。14项相关合同PASS（office-excel-owned-book-green.log），复审确认原P1关闭。正常/歧义新增/旧PID/无任务book、5→10计算保存重开均为fixture合同，不算实机。

Ruff只读发现本次重抛异常处无效noqa，已删除；不改规则。mypy目标未增加诊断，原16跨模块错误仍exit1保留，不自行豁免。完整88路径与当前代码工程/CI缺口保留，未提交或push。下一项为归属严格绑定后的真实Excel验收；Word人工条件只阻断对应部分。Goal active，生产、供应商账号和凭据未改。


### Excel真实SDK就绪断点

26d06836-e062-4cca-ba40-3e83d8dc9594正式业务API因KeyError在SDK绑定阶段失败、cleanup unverified，未执行计算，不标Native通过。所属Host日志只记录error_type，不回显文档或请求体。独立只读元数据稍后确认新增PID17953、精确/tmp任务book、book_count=1；原92919未命中该任务book。这证明SDK注册存在启动时间窗。随后full-path/同inode别名/仅1book/program-birth身份守卫下只关闭任务26book、空实例正常quit，文件保留；office-excel-scoped-open-owned-cleanup.json。该维护不冒称业务API成功。

新增SDK首查KeyError后就绪的失败测试，旧代码2例RED；最多10秒只读等待，仍需精确book身份才owned/report，未知不制造book或quit/kill。office-excel-sdk-ready-green.log保留合成回归，不代替实机。等待不提高App30秒或总190秒监督。Word界面问题仍只保留原一次请求，不推断许可或重跑Word；Goal active、六项未全完成、当前CI/工程缺口继续保留，生产未改。


### Excel正式原生计算闭环通过

6b4a5a33-4dbb-4e43-b79c-a5742e58aad4正常公开文档API真实执行Microsoft Excel：初始Summary!B1=5、Inputs!A2=2；修改后10/7；保存关闭重开后仍10/7、formula_preserved=true，document_closed/cleanup confirmed。office-excel-sdk-ready-live.json保留阶段及实际引擎。输出1ccf71dac4d0a02425759f5c由Store登记，服务下载同产物9374字节、SHA256 761b9427213f372dde8d433cf94176e4448a13ea59f1f871b74f32b377c8b367。独立openpyxl的工作表、数值/类型、SUM公式、缓存10六项检查均true：office-excel-native-independent.json/final-native-excel.xlsx。没有手工写10或仅凭旧缓存认证计算，真实前后/重开值来自Excel。独立ps仅余原用户Excel92919，本任务实例已退出；不退出用户现有Excel。

此前未知任务26经精确任务book/path/仅1book/program-birth守卫只关闭该book和空新实例，文件保留，原失败不改为PASS。SDK就绪负例与真实时间窗修复使本次正式业务闭环通过。最新Ruff目标exit0；mypy仍16条既有跨模块diagnostics、命令exit1，不豁免；本Goal阶段末完整工程/匹配CI仍未完成。

当前六项功能观察：三项FILE已通过固定样例；Excel_NATIVE计算/保存重开/清理通过；PPT_NATIVE文本/保存重开/清理通过但视觉仍待补；Word_NATIVE已真实创建及写入，保存9796人工界面条件与清理缺项仍未确认，原单次问题待反馈，不重跑该失败。没有完成Goal/merge/release声明、push、合并或生产更新，供应商模型请求0。Goal继续active。


<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"有限Office文档路由与Runtime工具复用既有ResearchService、Store文件身份、报告执行器与Seatbelt文件投影；原生分支委托现有LocalIntegrationManager/受监督工作进程及已存在的Office应用边界，不新增服务、进程类型、通用脚本权限或存储边界。API、数据文件文档及source inventory已同步，现有部署组件与边界图不变；实际功能与清理独立验收，不把文件模式提升为原生成功。","diagrams":[]} -->

### 本地工程闭包的实际结果与修正

完整88路径L4规划保留。首次必要Python闭包815 PASS/1既有skip/1 FAIL（599.90秒），唯一失败为新增document API测试仍假定Native Word未实现；测试遗漏Office隔离，意外进入一次Word调用并-1708，cleanup记录未确认，不计正式实机成功、不删除原记录，也不扫描未知Office对象。现显式注入无Office的受控失败native回执，继续验证mode/code/禁止任意path，定点绿色office-api-native-fixture-green.log；不是将实机失败改成PASS。

首次JS闭包187 PASS/1 skip/2 FAIL；Office额外独立change/input监听器破坏了既有事件测试入口。已合并进原监听器而不改fixture规则，两条实际事件回归及Office邻接70 PASS（office-ui-event-integration-green.log），其余架构/治理/费用/跨平台静态合同104 PASS（office-goal-local-js-remaining.log）。这些合同不执行Docker/Windows/Linux产品或真机验收。docs治理与索引check退出0；Project Constraints首次review_invalid，缺report-workflows结构决定。补上基于实际代码/部署的评审记录与直接模块文档，不改policy/schema/required门或截图证据。Goal仍未完成，Word保存人工问题与PPT视觉缺项继续保留。


### 工程检查续接结果

本轮实际进展：Office监听器整合后70 UI/能力测试PASS，经只读JS复审确认；104架构/治理静态合同PASS；Python首次815 PASS/1 skip/1 FAIL的唯一API fixture缺陷已显式隔离Office，完整API套件53 PASS（371.10秒）及报告渲染17 PASS。不重跑其他已通过763项，不将fixture回执计为Office真机证据。保持意外未隔离Word调用的原失败与清理未知记录。

Black/isort只读发现测试API格式和render-script imports，仅修正该两处；随后Ruff查出本轮注入全局OFFICE_REQUEST静态未定义，改为显式读取globals变量，未新增ignore/Any/skip；对应渲染17项再次通过。Black/isort/Ruff本轮变更范围已通过；完整mypy检查6源码无本次目标模块错误，但17条既有跨模块错误（runtime_state、runtime_contract、tracer/metrics、Wind）导致exit1，office-goal-mypy-final.log。不自豁免，不扩仓整改，既有37条大范围诊断保留。

完整88路径L4已按validation_failure重新规划；Project Constraints缺report-workflows结构决定已依据既有Host/Store/报告sandbox/本机管理器实际边界补评审，复验exit0；docs治理、API atlas、Python index check均exit0。没有重做架构多视口截图或改平台规则。当前GitHub API确认PUBLIC、PR81仍OPEN/draft、head0c5c9672/base205d2a17；它的旧CI不覆盖本Goal脏代码，未push/dispatch/merge。

视觉工具只读清单请求20秒超时并重置会话，未重复失败调用；安装PPT脚本字典仅提供单shape save-as-picture、未证明整页导出，故不以其他库渲染/对象边界冒称Native视觉完成。Word9796的保存/访问界面问题原一次请求仍待用户实际反馈，本轮未重跑Word或操作未确认文稿。六项Goal、正式入口、必要清理和当前Mac CI仍未全部闭合，Goal active、mergeReady/releaseReady=false，生产未更新。

### 冻结Office候选与当前CI证据（2026-10-08）

正常本地检查点b66f9627d795131dad057d2dfa06fe6e6cc53408已提交28个同任务文件并普通push原分支；完整交付差异仍按固定base205d2a170d9ece9c2751e014b63abe326510ab9c规划88路径，不只检查最新28文件。提交/推送exit0，office-checkpoint-commit.log、office-candidate-push.log；安全预检未发现拟提交秘密材料，临时环境、原始日志、trace及实例data home未提交。后续报告修改与此冻结候选分别标识，不声称旧CI验证过新报告HEAD。

用户本次确认527a482c80fc4e89a12afe31af57be75测试PPT已获文件访问许可并打开。该反馈属于原登记对象，不反推Word权限或其他文件。已有后续精确关闭回执office-native-ppt-owned-close-confirmed.json：/tmp与/private/tmp经设备/inode核对为同对象，仅关闭该已保存文稿，文件保留；不退出共享应用、不重复创建该测试对象。随后正式8b79原生保存/重开/读回证据继续有效，视觉仍NOT_RUN。

当前远端PUBLIC，标准runner；PR81仍草稿。GitHub PR曾报告dirty/mergeable=false，但远端compare为ahead26/behind0、共同基线正是base205d，本地无replace且非shallow；没有据此reset、盲目merge或force-push。Project Constraints没有dispatch入口、自动PR检查尚未出现，保留NOT_RUN。首次gh pr edit因GitHub弃用Projects classic返回exit1；改用普通REST PATCH更新同一PR描述成功，未修改仓库规则或PR状态，显著保留“Goal未完成，仅送检，禁止合并/发布”。

仅补充未被自动触发覆盖的既有必要workflow_dispatch：Research Web Checks37756610557、Research Web Bootstrap37756622020。两项attempt1、event=workflow_dispatch、head/实际checkout均为b66f9627d795131dad057d2dfa06fe6e6cc53408，结论success；前者checks/ubuntu-latest归Linux通用CI，后者Clean Web install/macOS-14归Mac安装CI，不能混用平台。office-current-{checks,bootstrap}-{run,jobs}.json及对应ci.log保留源码、runner和步骤证据。Bootstrap安装记录code_commit亦为b66；未使用开发机已有环境替代干净安装，没有供应商凭据配置到CI。

现有receipt按同一绑定更新两项真实外部门PASS，validate_verification_receipt实际exit0；hostAcceptance=PASS只指规划的Mac工程门，aggregateAcceptance=NOT_READY，mergeReady=false/releaseReady=false，Linux交接BLOCKED、Windows NOT_RUN。Word9796仍保存超时/清理UNVERIFIED、原单次界面反馈待答；PPT视觉仍缺实际证据，mypy17条既有跨模块诊断继续保留，三项FILE/Excel原生/PPT文本读回不会因这些缺项被抹去。没有重新执行真实模型、Keychain、历史生命周期或其他平台产品验收，未更新生产8088/3081、未合并或发布。

### Runtime原生文档等待边界的最小修复

续接7c7b627bdcb2551974c32a980131d50248f73489（仅报告提交，源码仍匹配b66 CI）。发现Runtime私有文档调用对file/native统一35秒，而Host监督器verifiers.py为既有180秒+10秒协调；因此合法较长原生流程可能在Host最终结果之前被运输层中断。先新增有界合同测试，截获真实executeDocumentTool使用的AbortSignal.timeout而不启动Office、网络或模型：RED实际[35000,35000]，期望[35000,195000]，exit1；office-runtime-deadline-red.log。

仅将原生运输等待改195秒，覆盖既有Host190秒加5秒结果交付；file仍35秒。Host准备/单步/总限、exec取消信号、安全认证、私有端点、输出大小、无重试行为不变。不以此声称Word保存问题已修复。整文件合同14 PASS/1既有skip/0 FAIL，office-runtime-deadline-green.log；没有缩小原合同范围或新增skip。初次邻接命令误写不存在测试文件，exit1，office-runtime-deadline-neighbors.log保留；按实际文件名改用既有method-tool和capabilities-ui套件，不把工具定位错误记产品缺陷。文档治理exit0，office-runtime-deadline-docs.log。

本补丁源码不在b66 CI中，不复用该CI声称最新源码已过；既有plan/receipt继续明确绑定冻结候选b66。当前补丁另按完整交付差异规划、直接回归及只读复审后留本地检查点；不因为一个本地修复重复整个Office真机生命周期、Keychain或bootstrap。下一次最终源码送检再统一绑定，Word及PPT外部缺项保持原状。

实际邻接method-tool/capabilities-ui 38 PASS，office-runtime-deadline-neighbors-green.log；架构/文档治理套件、完整88路径Project Constraints、docs治理与git diff --check退出0。原规划首次拒绝旧task候选b66与当前7c HEAD不一致（PLAN_ERROR），按真实HEAD建立本增量任务上下文后完整规划成功，L4范围不缩小；office-runtime-deadline-full-plan.json记录提交加未提交树身份，旧冻结候选plan/receipt不覆盖。只读JS复审无问题。未受影响的Python/Office行为证据仍限原源码及已验证范围，未再调用Office/模型；当前增量需后续最终候选CI，不能写PASS。

### 最新候选送检中

2026-10-08普通push bd05b79c086cd0a957be616cdfc47d44ff2797af成功（office-deadline-candidate-push.log），PR81仍draft，head为bd05、base205d；远端分支预检仍b66，无并发覆盖。GitHub当前仍dirty且自动运行为空，补充两项既有必要dispatch：Research Web Checks37760324407/queued、macOS Bootstrap37760339730/in_progress，均event workflow_dispatch、headSHA为bd05。这些是已确认运行身份，不记录PASS，不重复dispatch。当前仓库PUBLIC、标准runner、费用政策无变更；不运行Windows/Docker、不配置供应商Key。

唯一现行office-goal-full-plan.json、office-goal-task.json及receipt已绑定bd05完整88路径，验证器exit0、hostAcceptance=BLOCKED、mergeReady/releaseReady=false；旧b66成功plan/receipt分别归档office-b66-full-plan.json/office-b66-ci-receipt.json，旧CI对应旧代码不被抹除或挪作新HEAD。本节报告修改不属于冻结送检源码，后续报告提交亦须单独标识。Word与PPT缺项没有因运输等待修复或送检自动变为PASS。

一次有界实时目标核对补充：ls-remote master实际d6f15c66d2d06d871fc59cc710af01eaacbd2f38，与PR API返回的base205d不同。GitHub compare bd05...d6为diverged，目标方向69提交/137路径、候选方向28提交，共同基线205d，office-live-master-drift.json。此前“固定205d为候选祖先”的证据仍正确，但不能据此断言相对实时master无冲突，也不能把PR dirty仅判定为服务器错误。保留固定候选与范围，不自动合入69提交或扩仓整合。最新有界运行快照两项均in_progress；不写PASS、不重发dispatch、不等待无归属后台任务。

本轮续接有界读取37760324407/37760339730：Web Checks37760324407已success，attempt1、workflow_dispatch、checks/ubuntu-latest；完整日志Checkout明确bd05b79c086cd0a957be616cdfc47d44ff2797af，office-deadline-checks-{run,jobs}.json及ci.log。该通用Linux CI不替代Mac实机。Bootstrap仍in_progress，实际job113254941458已完成checkout/setup，安装步骤在运行。未重发任何dispatch。回执第一次更新时因未提交报告使旧树绑定不匹配返回PLAN_ERROR，保留错误事实；重新规划当前完整88路径并绑定唯一报告的工作区身份，CI依然只声明推送的bd05候选、不声明未提交报告已被CI执行。

最终PowerPoint产物33609字节及SHA256再次精确匹配原原生业务输出；已一次提供该已交付文件供用户在PowerPoint人工视觉核对，未创建新的Office验证对象、未写入或自动退出应用；反馈未到前视觉仍NOT_RUN。Word9796原人工反馈仍待答，未重复询问同一问题或重跑未知资源。已确认活跃CI句柄支持继续等待，其余人工条件缺失不被推断为通过。

校验器随后明确拒绝“CI认证未提交候选”（RECEIPT_ERROR），不能只重绑含报告工作区后把CI标PASS。改在专用临时detached bd05 checkout校验冻结代码；未安装依赖、未启动产品、未改原工作树源码，只复制回执明确引用的既有脱敏证据。路径登记office-frozen-ci-checkout.json，完整88路径冻结plan及receipt验证exit0，office-bd05-frozen-receipt-validation.log；当前唯一plan/receipt采用这一冻结候选结果，报告工作区规划另存office-report-working-tree-plan.json。回执BLOCKED/aggregate NOT_READY/mergeReady=false/releaseReady=false，与Bootstrap尚未完成一致。初次临时规划使用绝对task-context路径触发PATH_ERROR，改为现有相对路径合同后通过，没有修改validator或schema。原报告未提交内容不计入冻结CI身份，也不据此再触发bootstrap。

### 当前候选CI完成与有界阻塞审计

Bootstrap37760339730最终success，attempt1/workflow_dispatch/job113254941458/macOS-14；完整日志Checkout为bd05b79c086cd0a957be616cdfc47d44ff2797af，office-deadline-bootstrap-ci.log及run/jobs记录。冻结bd05回执更新两项CI PASS后在其只读checkout实际校验exit0，hostAcceptance=PASS；aggregate NOT_READY、mergeReady/releaseReady=false继续由现有政策计算，Project Constraints远端未执行、实时master分叉与其他平台缺证据保留。没有用回执合法代替OfficeGoal完成，也没有为报告更新重复dispatch。

完成条件逐项核对仍不成立：

| 应用 | 文件业务闭环 | Mac原生闭环 | 原生重开读回 | 本轮临时资源清理 |
|---|---|---|---|---|
| Word | PASS，正常页面生成/读改/下载及原7项核对 | PASS，新20124原生创建及736389/7f8014原生修改B/3 | PASS，三个成功任务均真实Word读回 | PASS，新成功任务文稿及私有目录已清理；历史未知对象另列 |
| Excel | PASS，8项核对，文件模式未重算 | PASS，真实5→10及公式保留 | PASS，Microsoft Excel重开10，下载缓存10 | PASS，仅所属新实例及工作簿关闭，用户实例保留 |
| PowerPoint | PASS，正常页面生成/读改/下载及9项核对 | PASS，真实文本编辑/保存与用户最终视觉确认 | PASS，4目标真实App读回 | PASS，登记任务文稿关闭，交付文件保留 |

任务1正式UI及公开业务API、任务2步骤/错误/清理诊断已具证据，任务3Word原生仍缺保存后闭环，任务4Excel通过所列固定样例，任务5PPT仍缺视觉，任务6文件入口已验证、真实模型选工具本Goal未执行（不使用旧T6或fixture充当新Office模型证据），任务7本地相关闭包与匹配Mac CI通过所列范围、mypy既有错误及PR外部门缺项不豁免。已交付Word_FILE、Excel_NATIVE和PowerPoint_NATIVE最终合成产物，但不能用其中Word文件模式代替Word原生交付。

再次核对PPT文件精确文本时发现早期摘要“样本数为3缺空格”不准确：当前正常页面读取及已下载document-a5536d766fca4e429487e82f41b4c94f.pptx实际XML均为“样本数为 3”，因此未修改或另存该文件，没有新增Office资源。Browser插件初始化被classic-level原生库签名错误阻止；未改系统签名/插件依赖，既有CUA浏览器入口一次成功恢复原19089任务页，读取验证无模型请求。该浏览器恢复不能证明native AX恢复；仅对已运行Word96765做一次只读getApp，工具实际120秒超时，无法确认保存提示，未继续重试或关闭文稿。现有Word界面问题及PPT视觉反馈仍待用户实际回答，不能从用户对527旧PPT访问授权推断Word许可或最终视觉通过。

相同Word实机界面/保存与资源归属阻塞已连续多轮保留；本地修复、独立文件业务、Excel/PPT读回及当前候选CI均已尽可独立推进。此时无归属确认不能安全重启Word实机，原生视觉不能由库解析替代，目标分支69提交/137路径不能在固定范围内盲目整合。Goal须保持未完成并按阻塞审计停止自动重复；解除Word/视觉条件后从断点续接，不重跑已完成模型、Keychain、文件业务或整套CI。生产8088/3081仍未更新、PR未合并、未发布。

### 用户续接Word剩余问题与PPT查看入口

用户要求说明PowerPoint视觉入口并继续解决Word，当前HEAD90008ce0a8c70b3707b12eb7b0fd9859b84f41f8、工作区开始干净。提供已核对SHA的final-native-powerpoint.pptx由真实PowerPoint打开观察两页，不要求重新生成或另存。Word9796正式回执仍为saved阶段超时、last_completed_step written、cleanup unverified，未假定其已解除。

只读查看当前安装Word.sdef：提供save as命令，其file name参数为text、file format为WdSaveFormat；存在format document与format document default。此前save-as -1708及标准save等待超时均保留，字典存在命令不能证明调用成功，因此不凭猜测再换保存语句。最初检索测试data home的范围过宽并产生大量非相关会话索引输出，已停止该方式，后续仅定位已登记9796回执和实现；未复制凭据/索引到报告或执行新模型请求。

为寻求精确文稿控制，调用现有Codex Document Control只读list_document_sessions(surface=word)，实际返回executors空列表/No connected sessions。没有执行文档命令、安装插件、改变权限或扩为新的产品集成路径。当前仍无法确认Word前台是否为保存/访问对话框；用户本次仅要求解决问题，尚未提供Word实际状态。已给出一次当前步人工观察问题（只看、不保存/关闭，确认提示类型及任务身份），不重复整个任务授权、不重跑同一失败或创建Office资源；原native AX超时没有再次尝试。后续从这一反馈断点处理，不将外部条件未知写成代码已修复。

### PowerPoint最终人工视觉确认

2026-10-08 19:08（Asia/Shanghai记录时刻），用户针对已提供的final-native-powerpoint.pptx及“两页文字无裁剪、重叠”检查回复“PowerPoint 确认”。按当前明确上下文记人工视觉PASS，证据来源为用户实际确认，不伪造截图或自动视觉结果。文件SHA256仍须匹配a1a664b783a3365538ff239495d29d9a8f2774d8bee79c9dcdc58c5c970ecb19，对应正式原生8b79b55d任务产物；office-ppt-user-visual-confirmation.json保存该有限证据。结合已有真实保存/关闭/重开/4文本读回、可编辑对象核对及精确清理，PowerPoint_NATIVE现在PASS，早期视觉NOT_RUN记录保留历史，不能覆盖本条后续确认。

当前六项为Word_FILE/Excel_FILE/PowerPoint_FILE/Excel_NATIVE/PowerPoint_NATIVE通过，Word_NATIVE仍BLOCKED。未重跑Office、模型或CI，未创建新文稿、修改生产或合并PR。唯一现行工程回执中的PPT视觉风险可据此移除，Word保存/清理、PR整合/Project Constraints及真实Office模型工具选择缺证据仍分别保留，mergeReady/releaseReady仍false。

### Word无提示与旧测试文稿处理续接

用户实际反馈Word“正常没有提示”，继而确认当前可见文稿确为本任务Word验收报告，并明确允许只关闭该文稿且不保存。这是应用状态与资源归属的新证据，不再按先前“提示类型未知”等待；不等于保存或原生闭环已通过。

只检查9796登记私有目录及精确目标：目录存在、owner/mode0700正常，预定research-workbench-9796ac132a884103bfba92b659fe7849.docx当前不存在，office-word-9796-exact-resource-now.json。未查受保护Office目录，也不将当前不存在说成从未创建。新的只读CUA窗口清单请求20秒超时并重置；未重复同调用。通过Word原生AppleEvent做有限元数据诊断，不读其他文稿正文。第一次应用count返回missing value造成诊断解析ValueError；改为进程内列表计数曾得到1项/登记名称0匹配，但后续元数据求值也返回-1708，因此不能据此认证当前文稿数量。office-word-readonly-document-count.json及office-word-name-metadata-validity.json保留这一证据强度限制。

用户确认归属后，尝试只关闭其确认的测试报告；先在受控进程内验证已知合成段落，未打印正文，不退出共享Word。实际返回-1708、未取得closed_confirmed，office-word-user-owned-close.json；不能把处理授权改写成已经清理。已明确纠正先前“1份打开文稿”的过强解读，停止自动关闭重试。现需要用户仅手工关闭刚确认的测试报告，出现保存询问时选择不保存，并反馈实际结果；这不是再次请求授权。旧文稿处理未确认前不创建新的Office实机资源、不从当前未知应用状态猜定保存超时根因。模型/其他已通过Office/CI未重跑，生产未变。

### Word实际修复与正式B／3闭环（2026-10-08）

用户随后明确反馈已关闭其确认的旧测试文稿并选择不保存。此确认仅认证该可见测试对象的人工关闭，不补造旧UUID映射或全盘删除。只读get version实际返回16.113.3，Word可响应。开始代码身份为ce191f948d6d2e784b290224c189f058ee83cb6a加本轮Word源码差异；生产未变。

修复均由失败合同/真实最小复现驱动：

1. 专用DOCX保存及HFS路径。原通用save-in没有明确格式；路径转换放Word.tell内真实返回空值，放外返回正确HFS。先RED/再GREEN，改为在Word上下文之前转换、save-as显式format document；未延长10秒准备/30秒操作/190秒监督。初次2f0d saved -1708、cleanup confirmed；移出转换后3f525b6c saved timeout，用户确认其确有单文件访问提示。
2. 用户仅允许3f测试文件后，文件实际落盘13743字节、7项检查通过；精确fullname/saved/内容核对与关闭成功，office-word-3f52-owned-recovery.json。原timeout不改PASS。文件保留为recovered-native-word-A.docx等恢复证据，不能据此假称原同步业务已完成。
3. 单文件访问交接。复用PPT的正常LaunchServices模式，只打开私有受控文件；完整HFS/saved守卫通过才赋owned引用。生成的空DOCX只作交接、不含请求内容，先关闭它，再由Word make new document真正原生创建。read/modify及重开复用同一有限helper。没有通用取文件/执行接口、全局daemon或权限扩张。新增合同明确空交接不能冒充新建；初次GREEN因测试原预期单参helper、实际采用路径/名称/HFS三参而失败，补足身份参数合同后通过，原失败记录保留。
4. 标题读回。4f93真实完成创建/写入/保存/关闭/重开，在read_back -1728，cleanup confirmed。精确旧读回块在保留3f文稿只读复现，定位到style；range getter返回以paragraph为父的样式引用，无法正确比较。直接paragraph getter可与本文件内置Title的name local比较，另验证built-in=true。case-sensitive比较移到Word.tell外helper，避免Word.case属性与AppleScript consideration冲突；一次compile -2741保留，最终compile0、精确完整只读块PASS，bold/正文/表格校验不删除。
5. 多run预检。真实原生A版本段落被Word拆成2个rPr完全相同的run，原any-rPr规则误拒绝。新规则只允许C14N字节完全一致，不忽略字体/语言/其他属性；真正混合仍拒绝。段落/单元格uniform与mixed四例先RED后GREEN，复杂/合并/嵌套/宏/外链限制不变。
6. 段落位置。2cc及9fdd已写/保存/关闭/重开但read_back -2700。源A XML布局3p+2x2表+2empty p，原映射[1,2,3,8,9]。真实只读证明Word p8为末格值2，表后段落在10/11：每表格行末也占Word段落。映射现计数w:p与w:tr，共用于写入/读回；表格后段落目标10的合同先RED后GREEN。
7. 写入范围。受控A副本的旧整段范围替换连同结束标记改变结构，B出现在非顶层段落；saved=true不能证明目标内容正确。专用save-as与对象求值试验亦保留未通过结果，不能将问题仅归因通用save。另一新受控副本只替换start..end-1正文范围后，B实际落盘、表格2×2与未改段落均true；生产写入改为保留段落结束标记，end≤start拒绝。相关合同先RED后GREEN、复审通过。

每次实机复验均对应明确代码修复/权限变化，未在条件不变时反复创建；后续定位尽量用同一已登记3f文件只读探针，不改用户文稿或退出共享Word。Word实际产物、恢复副本及有限非秘密元数据作为本任务诊断证据保留；历史未知对象不扫描、不删除。此前误写ledger verifications而非verification_runs导致IndexError，以及一次apply_patch上下文不匹配未写入文件，均为诊断/编辑工具错误，不记产品PASS。

正式页面最终成功：

| 操作 | 真实验证ID | 结果 |
|---|---|---|
| Word真正新建A/2 | 20124fc2-7841-489e-8eca-ea1091cad04a | created/written/saved/closed/reopened/read_back/document_closed全部完成，cleanup confirmed，约3秒 |
| 原生段落A→B | 7363897e-7544-47e4-bc28-55fbd730f083 | 正常页面原生修改/保存/重开完整读回及清理通过 |
| 原生单元格2→3 | 7f8014ae-df7d-4a7a-963e-e42631bffa14 | 正常页面原生修改/保存/重开完整读回及清理通过 |

最终文件ID6d618e79355ce7dcb74adeb7、document-4341ce0777ee4b60be77fe2601544178.docx，13897字节、SHA256 d7da88574464e9c057c1804b35bb3860fc87361500657d30a92d32ed05102689。正常页面点击下载到/Users/leon/Downloads同名文件，和Store安全句柄读取字节一致；9项独立检查均true：标题、Title样式、加粗、未改段落、B、2×2、3、下载相同、原NativeA SHA70284b56…未改。三个成功run的私有目录均已独立确认不存在。office-word-final-independent.json及final-native-word.docx；office-word-final-page.png为正常产品页面脱敏证据，不冒充Word应用截图。

本轮实际最小回归：专用测试解释器执行python -m pytest --confcutdir=tests/research_web tests/research_web/test_local_integrations.py tests/research_web/test_report_rendering.py -q，113 PASS/1既有skip，23.58秒，office-word-complete-regression.log。Black/isort/Ruff本次两个Python文件exit0；mypy --python-executable本任务产品.venv app/research_web/local_integrations/verifiers.py命令exit1，16条既有4文件诊断，目标verifiers无新诊断；与先前17条对比new diagnostics空，不自行豁免。Python只读复审逐项确认路径/权限/真实创建/格式/范围/索引边界，未将静态Approve计实机PASS。

当前六项固定Office功能均有真实证据；新Word源码仍需完整changed-set规划与匹配工程门。本轮Office操作模型请求0、商业数据请求0；旧模型/T6/Keychain/Excel/PPT未重验，B归因豁免仍保持。当前旧bd05 CI仅认证旧代码，PR/master分叉、外部门与新代码送检状态须另行收口，不宣称已合并、发布或更新生产。

### Word收口：当前源码CI与冻结回执

冻结并已普通push源码候选 `2d2630ec94e3e7063dcf800b4f99c9dd9b7bd492`，完整交付差异88路径；本次实现提交4文件。之后只追加本报告，不改变产品源码，不能宣称CI检出了后续报告提交。

- Research Web Checks：run37793973081，attempt1，workflow_dispatch，checks成功，Ubuntu runner；checkout日志实际SHA为2d2630ec94e3e7063dcf800b4f99c9dd9b7bd492。
- macOS Bootstrap：run37793989953，attempt1，workflow_dispatch，Clean Web install (macos-14)成功；实际checkout同2d，干净安装与启动/Doctor步骤完成。本机Word实机证据独立于CI，不声称CI安装Office。
- 原PR #81保持草稿，head2d，API base205d2a170d9ece9c2751e014b63abe326510ab9c，mergeable=false/dirty。没有merge-ref验收；目标master漂移与69提交/137路径整合未执行。Project Constraints远端NOT_RUN，不以本地成功代替。

实际执行gh run view --json、gh api actions/runs、gh run view --log，成功回执及实际checkout保存在office-word-complete-{checks,bootstrap}-ci.{json,log}。完整计划office-goal-full-plan.json与receipt.json在干净冻结2d验证exit0：hostAcceptance=PASS、aggregateAcceptance=NOT_READY、mergeReady=false、releaseReady=false。中间一次回执Linux状态未随新增PASS调整导致校验失败，已依政策改为BLOCKED重新验证成功；未修改schema/政策。

两个受控诊断副本已先确认Word未打开，再保留失败/成功样本证据并精确删除原登记文件及空目录；office-word-probe-cleanup.json独立确认。3f历史恢复文件作为明确诊断证据保留，不写成删除；未知旧对象UNVERIFIED。本轮Word功能问题已解决，Word/Excel/PPT的FILE/NATIVE固定样例六项均PASS；模型自动选择Office工具未执行、商业接口与其他平台独立缺项保留。生产8088/3081未修改、PR未合并、未发布。

### 2026-10-09：按用户“解决问题”续接PR整合与模型工具缺项

宿主macOS，功能收口任务，不执行其他平台产品验收、不更新生产、不合并PR。起点c4581293376aa74713d6319744fa03722084f129干净；一次fetch固定master4a5e7523d7407525d108757727c64f10783203f4，远端任务head2d2630ec。正常merge进入原任务分支，保留本地报告和Word修复，不rebase/reset/force。实际11个冲突文件：五份模块说明、平台支持说明、README评审回执、两份生成HTML、工具与安装测试。文档合并双方适用事实；测试同时保留Office准入拒绝与Cordis getter合同、主线受控Docker fixture；生成HTML复用当前builder重新生成，不拼接旧生成页面。

当前原任务base205d2a到合并工作树完整差异200路径；相对固定master候选差异88路径，二者分别保留。完整计划L4及200路径Project Constraints本地exit0；runtime manifest文件hash全部匹配。文档/架构/index检查exit0，工具注册与架构86项通过。产品.venv没有pytest属检查环境错误，未安装包或改产品依赖；改用既有独立检查解释器执行本轮回归。

模型Office实机缺项：19089独立实例状态正常、已保存provider=openai-compatible/model=qwen2.5:0.5b/credential_required=false。既有compatible-model.mjs明确text-only：不发送工具定义、拒绝tool_calls。因此当前模型无法验证自动选择Office；不发无意义请求、不把文本输出/fixture或旧NAV T6冒称Office模型验收。真正解除需本实例通过设置页配置已有受支持且具工具能力的模型及可用凭据，秘密不得进对话；当前Office文件/原生六项功能PASS不受此条件影响。没有扩展兼容适配器或使用个人开发工具凭据。

整合回归补充：86项工具/架构、230项治理/UI合同PASS；启动/安装/Service Manager/Office组691 PASS/1既有skip。邻接组666 PASS/1 FAIL：test_staged_flag_is_exact_and_reaches_only_runtime_child[0]清理runtime返回cleanup_failed；单项独立复现随后1 PASS/2.75秒，首次失败不删除、不概括全绿。Supervisor产品源码与固定master相同，fixture差异主要绑定已升级DSH源码；未证明该瞬态由本轮整合引入，根因仍未知，不扩展Docker产品验收或放宽断言。

实际管理入口正常停止原Host49479/DSH49323；立即start在19089无listener但bind errno48时拒绝endpoint_port_in_use，记录真实失败。端口释放后唯一后续start成功：Host88512/DSH86982、19089/14181双ready，root HTML200。未杀其他进程、绕过安装/归属或更新生产。用户确认有DeepSeek测试Key并将仅在核验的19089设置页录入；尚未收到保存反馈，不推断已录入，不读取表单/凭据。

当前收口候选与远端：正常merge提交52b3b01788f0af2fe7f60c60b98003c3679836eb已普通push；PR #81草稿，head52b3，base4a5e，GitHub MERGEABLE，冲突已解除。本轮原完整交付200路径与整合增量138路径均保留；绑定当前PR差异88路径的office-sync-bound-plan.json已生成并校验，未固定沿用历史路径数。以原base205d与task base4a混用时规划器真实拒绝candidate mismatch，纠正为固定PR base4a，不修改规则。

当前自动CI（未dispatch）：Project Constraints37808948653 PASS，Research Web Checks37808948533 PASS，均attempt1/pull_request/Ubuntu，实际checkout77f53da6c277bf8ee2826a91d088c4a2859e9ed0，父提交实核4a5e7523d7407525d108757727c64f10783203f4与52b3b01788f0af2fe7f60c60b98003c3679836eb。macOS Bootstrap37808948541仍in_progress/安装步骤，不能写PASS。元数据/checkout日志统一office-sync-*-ci.{json,log}，没有Windows/Docker产品dispatch或付费预算变化。

API53 PASS/408.96秒，691组214.10秒、邻接666PASS/1首次FAIL/231.28秒及Supervisor确认88PASS/38.32秒均保留。本地200路径约束/文档/index补录实测耗时，不凭估计填回执。office-sync-receipt.json在干净52b3验证exit0，当前hostAcceptance=BLOCKED、aggregateAcceptance=NOT_READY、mergeReady=false/releaseReady=false；回执合法不等于Goal完成。

用户已确认有可用DeepSeek测试Key，核验后的独立录入入口http://127.0.0.1:19089/#/settings/model，等待“已保存”事实后才请求模型。当前不读取密码框、剪贴板或个人配置；本次模型请求0、Office新增业务0。完整验收不由当前纯文本兼容路径代替。后续报告提交仅记录冻结候选的证据，不触发“报告→Bootstrap→再报告”循环；生产不变、PR未合并、未发布。

### 用户保存后的真实Office模型验收与精确清理

用户明确回复“已保存”后，仅读取非秘密状态：deepseek-official/deepseek-flash、credential_configured=true、system_keychain。没有读取秘密、掩码、剪贴板或供应商配置。正常产品API创建独立fingpt会话a107a3e2-6872-4cd7-9045-1782ed7373bb，唯一消息显式选择research_document_operation并要求一次DOCX/file/generate。请求有唯一幂等标识；没有客户端重试，没有重新执行三款原生Office验证。

正式执行已completed：工具活动call_00_aJWoTWnTLYnv0lyMxvuX8062、research_document_operation、completed/410ms；没有其他工具或subagent。两条已完成assistant输出包括调用前说明与最终回执/下载入口，不据此伪称掌握底层HTTP重试总数。工具与最终生成真实完成；usage tokens14531、input6209/output514为原生投影，不换算请求次数。真实供应商已调用，本轮不再宣称0请求。

交付task25519ef905cb2e3d05e528c0完成，无missing_formats；文件1d2430fa37f47e38d6dce9d9/office_tool_acceptance.docx，36755字节。正常download字节独立检查标题、正文、run acfb15a2c12d4c4bb84f6a546703181b全true，SHA256 fa194c643a6ad2d3e55f3eccdce9c272b41ee04c11dea3edda3d1876d0c35501。工具结果和下载均真实，文件核对不冒充新增Word原生自动化；之前三个原生闭环证据继续保持。证据office-sync-model-{submission,result,file-check}.json、office-model-generated.docx。

结束经现有产品PUT model clear_api_key=true清除测试Key，HTTP200并独立runtime非秘密状态credential_configured=false/system_keychain，office-sync-test-key-cleared.json。仅正常stop所属Host88512/DSH86982，正式状态均ready=false/pid=null，office-sync-final-stop.json；交付文件保留，不关闭用户Office文稿、退出共享Office或清理未知对象。生产8088/3081未操作。

此次三个原缺项：PR #81文本冲突已解除；当前候选Project Constraints自动PASS；真实模型选择Office工具并交付PASS。仍运行中的Mac Bootstrap37808948541（macos-14安装步骤）作为有界CI交接保留，不无限轮询、不重复dispatch。完整Mac工程结果暂仍BLOCKED，mergeReady/releaseReady继续false；Windows/Linux/Docker缺项由对应任务保留，不扩张本轮。冻结源码52b3、真实执行工作树产品源码一致；后续仅报告提交不能冒称被旧CI检出。

### 2026-10-09 原Goal逐项审计发现的任务6展示遗漏

自动续接读取原goal-objective.md后，确认52b3三个自动门已全部PASS，Mac Bootstrap37808948541实际checkout77f53da6合并预览，不宣称检出了后续报告75216e9。原六项文件/原生证据与真实模型Office工具证据复核有效；但设置页未分别显示三Office文件处理与本机操作，未呈现最近安全步骤/清理，业务结果缺少清理标签，故未先标Goal完成。

最小新增补丁：既有capabilities中仅增加固定文件前置条件标记，无新schema/依赖锁；现有detail显示有效Office安全诊断和过期说明，Wind行为不变；Office行标签与业务清理状态分别呈现，产物仍可下载。Mac文件依赖就绪不代替逐文档业务成功，其他平台仍未验证。

RED/GREEN证据office-state-python-corrected-red.log、office-state-ui-corrected-red.log、office-cleanup-ui-red.log。初次测试分类fixture没有登记Word、fingerprint错误地填原值，已明确修正；仅把本轮自有实现暂存并恢复原HEAD源码，正确fixture在原实现失败后重新应用补丁，未reset或覆盖其他改动。最新115PASS/1既有skip，47UI合同PASS。真实设置页确认三App分别显示文件/本机、最近时间、最后阶段及已清理；首次页面截图暴露旧CSS隐藏label，局部Office CSS修复后的office-state-settings-fixed.png标签可见。

Black/isort PASS；mypy目标manager无诊断，16条既有4文件错误继续保留，不新增ignore。现有检查与产品环境均无Ruff，离线uvx也无缓存，工具环境错误独立记录。按本会话依赖安装授权，仅在/private/tmp/rwb-c1-checks-20261006补Ruff0.16.10，实际uv pip记录office-state-ruff-install.log；Ruff检查PASS，未改系统Python、产品环境或产品锁。浏览器插件因原生库签名失败，未修系统签名；备用CUA首次在已停止服务打开产生连接拒绝/错误页策略阻断，受管启动后新的正确回环页面验证成功，未绕过安全页面。

本次新增只影响状态投影/渲染，复用匹配的Office真实读回、清理与真实模型工具交付；不再调用供应商、Office、Keychain生命周期或架构多视口。新候选须重新绑定完整计划并等待自动CI，不拿52b3通过冒称新增源码通过。

状态补丁最终补证：复审指出安全native_error_number尚未解释，新增四case先3FAIL/1PASS，再仅投影macOS白名单-1743自动化明确拒绝、-54/-61文件访问拒绝；-1712超时不推断权限。明确authorization_required回执提示等待用户操作、处理真实提示后再显式验证，不宣称Office仍在执行。Wind投影保持原行为。Python/JS复审Approve只算静态审查。最终119PASS/1既有skip/28.47秒，47UI合同PASS，90文档/架构合同PASS；Black/isort/Ruff0.16.10 PASS。

另试既有follow-imports=skip边界时出现manager原dataclass构造器7条诊断；在原HEAD源码上同命令同7条，属于既有边界/工具行为，不冒称新增缺陷或PASS。正常导入检查仍16条边界外4文件诊断、manager无诊断；两种命令真实退出1均保留，不新增ignore、Any或改政策。完整91路径计划L4及约束/文档/index已通过；原基线203路径另存，不缩小交付。

新展示代码通过现有受管入口启动独立无Key实例（Host31681/DSH31057）。设置页实际呈现三Office文件/本机能力、最近时间、最后阶段与清理；没有点真实验证、模型、供应商或业务按钮。截图office-state-settings-fixed.png与初次隐藏标签的office-state-settings-page.png分别留存。当前源码相对52b3仅状态投影/UI、测试和直接文档，不改变原生执行器、报告sandbox/文件处理、供应商协议、凭据、启动/安装锁，故此前六项真机与模型工具证据按模块差异复用，CI须新候选匹配。
