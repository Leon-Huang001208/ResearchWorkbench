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
