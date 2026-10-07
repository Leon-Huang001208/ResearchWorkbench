# 设置与真实能力闭环：阶段 0 + 1A

本轮仅阶段 0 与 1A；未执行 1B、2、3、4、5、6。附件为范围参考，用户本轮授权优先。本报告持续更新；机器验收 plan/receipt 及原始日志置于 `logs/settings-model-loop/`，不另建任务报告。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"模型配置与显式测试复用现有Host/DSH会话路径；增加最小测试路由但没有新增执行器、组件节点或信任边界，API及运行文档已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"产品overlay通过固定DSH扩展点挂载模型provider，增加限定用途私有进程桥接和独立macOS Keychain边界；认证record保留原固定实现及独立文件。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"模型页收窄Provider并区分保存/应用/凭据/真实生成，继续使用现有设置、同源API及会话状态投影。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Automation仍复用相同ResearchService创建和提交原生会话；模型变更只应用新会话并在任务活跃时拒绝凭据变化，没有新增调度器、任务注册或图节点。","diagrams":[]} -->

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
