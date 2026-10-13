# Hot / 研究情报接续记录

宿主 macOS，任务类型功能开发。目标仍为原 Goal 的阶段 0–5，未完成任何门不降级。

## 断点与保全

- 原 worktree：`/Users/leon/.codex/worktrees/hot-events-system/ResearchWorkbench`。
- 原分支：`codex/hot-events-system-20261007`；候选 `fc60414f6c38a0a9e677a8d137c397a0c1895373`。
- 原权威记录：`2026-10-07-hot-events-PROGRESS.md`，完整历史保留；本文件接管后续动作与状态。
- 应用重新绑定被拒绝：原 worktree 属于另一个聊天。未修改原目录或向原聊天发消息。
- 本次 worktree：`/Users/leon/.codex/worktrees/hot-intel-continuation/ResearchWorkbench`。
- 本次分支：`codex/hot-intel-continuation-20261012`。
- 原 5 个已跟踪改动及 3 个新增文件已通过 Git binary patch 恢复，8 文件逐字节一致；原 Git 状态未变化。
- 保全证据：`logs/hot-resume/resume-receipt.json`；补丁 SHA256 `b8103eecebb5d4865420231338f71c5f2e4cb1136860d70422117a74dea3662c`。
- 恢复后使用当前 Mac 主项目已有 `.venv/bin/python` 执行 DOCX unittest：5/5 PASS，未安装依赖。仅验证旧 WIP 的局部行为，不认证完整导出路径。

## 最新主线与融合决策

- GitHub API 核对：PUBLIC；最新 master `8a2d4ba75294b3fbe2aa90aa802dfd25a1296a2b`。
- PR #92 已合并：只读资讯雷达，固定 Golddata GET API，8 栏目；没有本地材料库、worker 或模型执行。
- Hot：Node/TS + PostgreSQL + pg-boss，独立版本材料/事件/频道/简报，受控 FastAPI 桥；现有真实两材料/两简报证据保留。
- 用户明确选择统一入口，并要求命名。采用名称建议“研究情报”：本地热点与事件 + 现有外部资讯栏目。
- 页面共用入口与主题；本地/外部数据始终标明来源，保留独立事件身份与覆盖边界。外部列表不直接写入 Hot 或冒充本地材料证据。
- 原 Hot API/CLI、唯一队列和数据库所有权保留；外部 GET 不创建采集任务/模型调用。
- `#/workbench/hot` 与现有 `#/intel/*` 旧链接继续可解析；新导航归研究情报。
- 实现顺序：保全 WIP → 合入最新 master → 路由/导航融合 → 本地相关回归 → 继续原阶段四及其余验收。
- merge-tree 三方预览提示 26 冲突文件，以 UI 路由、文档与生成物为主；日志 `logs/hot-resume/merge-preview.log`。预览不是实际合并完成。

## 未完成与授权边界

本平台验收仍 NOT_RUN/BLOCKED，整体 NOT_READY。DOCX 正式导出/跟踪/研究交接、真实 DSH、持续采集重验、留出样本、联合恢复、Mac Docker、干净安装与 exact-SHA Mac CI 均未由本次认证。Windows/Linux 为设备交接。无生产部署或合并主线。

旧记录中的累计付费预算不得重置；本次尚未读取权威预算或验证授权，不发付费调用。后续先核对原授权、账本与有效状态，再使用剩余额度。无外部发送。

下一步：合并最新主线并实现统一导航，保留 Hot 的业务合同和外部雷达只读边界。

<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"恢复的DOCX切片复用既有报告生成器，将纯数据函数抽出供原沙箱内嵌及Hot显式导出调用，不新增执行引擎、队列或会话归属。Hot原件与报告会话分别保留，相关文档和新源码映射同步，产品/恢复验收未冒充通过。","diagrams":[]} -->

## 2026-10-12 本地融合实施

- 主线已合入工作区，全部文本冲突解决，最新模型设置、Office编辑、Mac mini部署基座与Hot代码保留。原 worktree 未变，接续补丁仍在本地日志。
- 统一入口“研究情报”：本地 `#/intel/hot` + 外部8栏目，共用栏目导航；旧Hot深链接保留查询参数。外部GET不入Hot库、不创建任务/模型执行。
- RED：新统一路由/导航测试因旧链接无目标失败；GREEN：Hot/Intel 17/17。Research Web JS 385 PASS / 1 SKIPPED / 0 FAIL；治理/策略/Docker静态合同223/223 PASS。
- 用户允许本worktree隔离测试依赖。`.validation-tools` 安装 pytest9.1.1 / pytest-asyncio1.4.0，仅测试工具，不改变产品锁或全局环境。运行依赖复用当前Mac主项目受管解释器，Node用已有24.19.0；Hot依照原package-lock执行npm ci --ignore-scripts，未改版本。
- Hot类型检查与40/40 TS单元PASS。Python Hot/Intel/报告等103 PASS，6子用例PASS。首轮隔离解释器沙箱导入失败后改用既有受管解释器加载隔离pytest，不放宽sandbox。
- 旧定价夹具固定10月9日与严格当日校验冲突；测试的合成价格改用当前日期，增加昨日价格拒绝/不落盘反例，7/7 PASS。生产价表/账本/付费授权未改。
- 文档治理、完整191文件约束、架构清单/API检查、Python索引和API图册检查PASS；01部署图按实际合并源码重新deliver9/9与四视口容纳PASS，Codex查看1440浅色/2048深色最终截图。02/11沿用原分支完全相同字节的历史review，不冒充新产品验收。
- 实际浏览器本地18096预览PASS：单一入口、本地未配置状态、真实外部事件页面、旧链接sources参数保留、规划中栏目及无JS错误。截图和固定边界在 `logs/hot-resume/browser-receipt.json`；预览是内存凭据+离线研究，无Hot模型/研究/DB验收。原框架后台仅写独立预览目录，不计Hot来源采集。
- 内置browser-client因classic-level原生模块加载失败，保留事实；使用已提供的CUA浏览器通道完成浏览验证。首预览fixture不保存临时凭据导致MCP key-race，改为实例内存dict后启动，未读取宿主秘密。
- 首轮所有失败日志保留在 `logs/hot-resume/`；未发远端push/PR/CI、未部署生产、未改变预算。后续仍需完整Hot链和本平台验收。

下一步：完成本次候选本地运行门并保存合并检查点；随后核对原PG资源/模型授权账本，继续DOCX正式导出、跟踪和冻结原文研究交接。当前Goal ACTIVE，hostAcceptance BLOCKED（候选CI/产品验收未执行），aggregateAcceptance NOT_READY。

## 候选本地门收束

- Router保持L4，失败后使用validation_failure重规划，未降级。运行模式/Docker控制/协议/平台能力/API闭包546/546 PASS（250.74s），与Hot/Intel/报告103项为重叠目录的两个闭包，不相加宣称独立覆盖。
- 当前改变的20个Python源码/测试编译PASS。新Hot/融合相对origin/master的完整diff whitespace PASS；相对旧Hot HEAD的merge diff会看到主线已跟踪的Claw原始失败日志行尾空白，保留上游真实日志未修改，并且当前变更范围不包含这些日志的新编辑。
- preview服务通过原TTY session Ctrl-C退出0，独立浏览器tab已关闭；未停生产Web/DSH、未删资料或PG卷。
- 本地检查点可提交；这不是完整Goal、本平台最终验收或合并/发布就绪。尚无候选GitHubCI、干净Hot安装、真实Hot/DSH研究或Docker切换回执。

## 阶段四：完整存储原件读取与DOCX证据（2026-10-12）

上一goal turn为实质进展（接续/主线/入口/候选）；本turn继续原完整目标，无缩小完成标准。

- 原PG容器 `rwb-hot-probe-6a5d3231` 初始exited255。先核对probe标签、固定image digest、指定volume及127.0.0.1动态绑定，启动同一容器/卷。原回执端口59705仅为旧观测；当前端口63670另记 `logs/hot-resume/pg-current.json`，没有篡改旧回执。
- 首就绪检查在启动窗口返回2，随后同一容器pg_isready接受连接；第一次只读audit误查events.title返回42703，改查实际schema后通过，失败输出保留。
- 原schema15仍有2事件/2原页/2简报，旧简报hash全部核对通过。只读账本仍为4calls/1417tokens/659microUSD（保守费用上界），max20/20000/1000000未变。
- 在原聊天 `01a11684-d6a3-7a82-9c8f-3d84849a7dd0` 的2026-10-08直接用户回复找到累计上限明确授权；未发送消息给该聊天，也未创建新scope/重置额度。当前新付费调用0，正式模型仍需当前核价及安装级路径。
- 新 `research-evidence.ts` 在只读一致事务中绑定逻辑实例、正简报版本、截止与1–20个已选材料，读取完整已存储文本/原始响应及来源/版本/未知时间。后续更正不回填；未选原件和hash/owner变化拒绝。RSS完整响应不等于其文章URL的HTML全文，清单明确这个局限。
- 签名reader RPC `research.evidence`/`research.original` 分别按32KiB重建生产者规范JSON字节和原件字节。Host校验清单哈希、另读的简报锚、实例、对象选择、文件名、偏移/总字节数/最终SHA，15秒整体重建期限，清单700000B/单对象8MiB/总32MiB；失败不发布部分文件。
- 初版Host重序列化JSON来验hash的潜在跨语言小数拼写问题已修正为原规范字节分块，新增1e-7/多页清单反例，不改付费/凭据逻辑。生产API仍不向页面交付读key。
- RED：缺失Node模块/Host方法；初版typecheck因日志白名单/测试可选undefined失败，按真实接口修正。当前类型检查及新单元/真实PG+签名/Host重建待最终收束日志。新PG测试仅在随机schema/角色中写合成数据并精确清理；不修改原模型scope。
- 实际HTTP→HotWebService→Manager→签名Node/PG→DOCX及私有保留文件验证通过。第一次helper stdout被项目日志污染而JSON解析失败，日志转stderr后通过；没有忽略错误或换成假响应。凭据是fixture，不是SystemKeychain/完整安装证明。
- 原两份真实AI/宏观简报在只读连接下分别完成完整存储原件清单、字节/哈希核对和原件保存。final-core清单见 `logs/hot-resume/real-evidence-receipt-v2.json`；之前v1目录保留。原两份DOCX已通过python-docx打开、ZIP完整性、简报/材料版本哈希和原文说明核验，`logs/hot-resume/real-docx-receipt.json`记录真实产物。桌面预览打开请求返回queued，不宣称已在编辑器中渲染。
- 原容器/卷保留，原worktree源码未变；无新研究会话、模型调用、外部发送、远端发布、生产部署。DataHub会话发布、PG research-run→session/report映射、未知受理恢复尚未接入，所以不把原件读取/DOCX解释为研究闭环完成。

下一步可直接执行：在真实目标会话上接入DataHub冻结快照发布与hash校验，并追加PG research-run/session映射，随后沿既有ResearchService/DSH在同一剩余额度内完成真实研究。跟踪/周期简报、源覆盖重验/留出关系样本、联合恢复、安装/Docker/同候选MacCI等原Goal门仍保留，Goal ACTIVE。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"在既有Node/PG reader投影内加入固定简报版本的完整存储原件清单/分块读取，不新增数据库schema、队列、服务或研究引擎；来源/时间/哈希边界和未装配研究状态同步文档。未来DataHub会话及run映射未提前绘制为已实现。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Native HotManager新增有界reader重建，仍复用原私有状态/凭据/签名协议和实例代次；不改Native/Docker生命周期、安装版本、Keychain或跨模式切换，实际使用的PG验证容器与产品Docker证据分开。","diagrams":[]} -->

### 原件读取切片最终本地检查

- TypeScript typecheck PASS，Hot单元42/42 PASS，真实随机schema的签名Node/PG→Host原件重建与DOCX HTTP/保留/解析1/1 PASS，Python相关stdlib60/60 PASS；四个必需治理目录110/110 PASS。
- 本切片21文件的项目约束、架构、文档治理、生成索引/图册与whitespace PASS。初约束缺README复核回执被拒；先在错误组件cwd定位README导致断言失败（无文件写入），再修正根目录定位并同步真实阶段说明/回执，未降低规则。
- 原库最终只读预算审计PASS：4/1417/659microUSD及20/20000/$1上限未变，原runtime仍paused，测试research随机角色已全部移除，PG容器/卷保留。证据 `logs/hot-resume/evidence-final-ledger.json`。
- 当前完整目标仍ACTIVE：冻结输入已可用，但尚未发布到真实研究会话、未持久化hot_run→session/report映射，尚无本轮正式DSH研究/联合恢复/连续采集重验/留出样本/Hot安装与Docker切换/候选CI。不能以本切片通过替代那些门。

### 当前提交及机器回执

原件读取源码候选 `45e012cef65a97b58cd8ca6752881c56c43dc4ba`，继承融合候选503af9edf；分支/worktree不变。当前源码检查点已提交，后续报告提交仅记录状态。

Git绑定plan4/receipt3在 `logs/hot-resume/evidence-candidate-*.json`。最初手写平台回执漏掉cross-platform影响的Windows空门交接，validator拒绝；按正式内核的完整平台推导补齐，未改内核、状态或验收门。Mac Bootstrap作为已登记补充门保留NOT_RUN。最终validator valid=true、hostAcceptance=BLOCKED、aggregateAcceptance=NOT_READY、mergeReady/releaseReady=false。失败回执与输出均保留initial/second副本；未发CI/远端操作。

## 阶段四续跑：持久交接与会话快照（macOS 功能开发）

- 新增 migration16：不可变选材与预留 session UUID、CAS revision/state、唯一请求回放和控制者审计。controller 列级写权限、worker 只读；真实随机 PG schema 测试后精确清理，原 schema15 未迁移。执行未知态不能回到重新发送状态，尚未接入实际付费执行。
- ResearchService 在 native create 前持久化预留身份；丢失回执先 session.list 核对同 ID/同 cwd，缺失或异源目录拒绝。DataHub 发布完整原件字节、来源时间和截止，public 原件先落盘，private UUID 是提交标记；同一交接重放保持一个快照。没有伪造 Provider 查询或重新标记旧资料的新鲜度。
- POST handoffs / GET research runs 已接入受控 Web 边界，准备态返回 executionStarted=false。UI 付费研究动作与真实研究结果尚未交付，不能把准备成功当成 Goal 完成。
- 模拟 native 的 Python/Store/API/DataHub 回归分别98及58 PASS；相关集合重叠，不宣称156个独立行为。真实签名 Node/PG→Host→HTTP→DataHub 组合1 PASS，但 native 回复为fixture。保留首轮错误文件路径与隔离解释器依赖失败，不降低沙箱。
- 按 requesting-code-review 与受限 code-reviewer 模板进行独立只读审查，发现三项：预存冲突暂存目录误删、private commit 后错误回滚、native cwd 缺失仍被接纳。修复后保留冲突/恢复暂存内容与已提交目录，要求明确目录证据；新增反例后10 PASS。审查没有运行测试，不把静态意见当运行证据。
- 固定 DSH 源码 HTTPS clone 因连接超时失败；沿既有 GitHub SSH wrapper 成功取得并 checkout48504。另发现 PR92 隔离安装已有同固定版本构建，后续只读核对后复用，不重装全局依赖或影响生产3081/8088。
- 图11更新 PG研究映射与会话/快照适配，真实研究仍标待验。结构9/9及四视口容纳通过，controller 已查看1440浅色与2048深色截图；图文不代替原生产品验收。

下一步：核验固定 DSH 的真实预留 ID/目录回执及冻结副本，再接入同一剩余付费预算的实际研究受理/未知结果恢复。持续来源重验、跟踪/计划简报、留出样本、联合恢复、干净安装、Mac Docker 切换及同候选 Mac CI 仍未完成；Goal ACTIVE，未发布/合并/生产部署。

<!-- architecture-review {"group":"hot","structure":"changed","reason":"新增PG schema16持久研究映射与受控交接准备接口，图11展示已实现适配而保留真实研究待验。","diagrams":["11-hot-events"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"受控Hot交接与状态读取API复用ResearchService，新增关系在图11与API图册记录；不新增研究引擎。","diagrams":["11-hot-events"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"DataHub接收完整冻结Hot原件并在同一会话目录发布不可变快照，图11记录该适配边界。","diagrams":["11-hot-events"]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"冻结原件仍使用既有会话inputs/datasets与私有catalog提交边界，新增格式及恢复校验不改变文件所有权拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Manager控制投影新增research run操作，复用既有私有签名实例/模式/代次与生命周期；未改变Native/Docker装配。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"ResearchService新增Hot会话预留恢复，不修改既有Automation调度/任务或报告执行路径；周期Hot简报适配仍待实现。","diagrams":[]} -->

### 真实 Native 会话证据及本地审查修复

固定 DSH48504 的真实 session.create/list/selectModel/rename 与两份冻结原件副本及重放通过；目标sid/cwd与原件SHA逐项核对，付费发送0，未宣称完整研究或原生产PG run映射。隔离数据在 `logs/hot-resume/native-handoff-home`，回执 `native-handoff-proof.json`。首次读取bootstrap-token记录作为cookie被严格客户端拒绝；沿既有Manager交换并原子写认证记录后通过。运行时Tabbit报告 `ctx.settings.register is not a function`，因此不认证Tabbit/工具或完整安装。复用PR92隔离构建的官方verifier也已PASS：同commit、干净源码、pnpm11.7、16097文件closure，sha cf4867dfb1236d07021afab0181399089ef258694e7326942198c91e94e6d33f；没有重新安装运行依赖。

独立只读复核确认三项发现已解决。TypeScript最终typecheck及真实PG/签名/HTTP/DataHub组合重跑PASS；首重跑遗漏fixture路径被拒后显式复用原fixture及当前端口，错误日志保留。本机black/ruff模块均不存在，检查真实失败/NOT_RUN，没有擅自安装新Python依赖。架构首检查发现跨组图11登记缺失及Automation模块说明遗漏，已补充真实映射和不改变调度的说明，未降低门。

最终针对DataHub/Hot/协议/研究台及新增恢复反例的Python回归101 PASS；Hot TS单元43 PASS，四项治理/策略测试180 PASS。正式Router保持L4，所选完整治理命令及API门另留执行回执；不会把未执行候选CI算PASS。48文件项目约束、文档治理和修正后的架构检查PASS。原预算再次只读核对4calls/1417tokens/659microUSD、20/20000/$1上限未变，原runtime仍暂停，随机研究测试角色为零。

真实Native验证子进程已按明确PID/完整命令身份核验后SIGTERM退出0；生产3081/8088未触碰，冻结资料和PG卷保留。检查工具Ruff/Black/isort的隔离安装申请尚待回复，不自动把此前pytest授权扩展为其他依赖授权。当前工作保持可续跑状态，完整Goal及正式研究/安装/恢复/模式切换/CI门未完成。

Router选取的完整四项治理命令110/110 PASS，最终API门53/53 PASS（163.39s），生成Python索引检查及10个本切片Python文件编译PASS，whitespace PASS。同一旧schema模型账本与本轮随机schema权限测试分别留证。该本地切片可保存源码检查点；工具安装待回复与远端/平台/全Goal门保留真实未完成状态。

源码检查点 `c3a29fdd4b26fd9d0349686e79429c0308835d75`（48文件）已提交。绑定该SHA的plan4/receipt3在 `logs/hot-resume/handoff-candidate-*.json`；首回执缺少逐个未执行外部门的风险条目被validator拒绝，补齐明确NOT_RUN风险后valid=true。hostAcceptance=BLOCKED、aggregateAcceptance=NOT_READY、mergeReady/releaseReady=false；Linux/Windows设备交接保留NOT_RUN，Mac Bootstrap NOT_RUN。修正未改变验证内核或任何门，没有push/PR/CI/merge/部署。下一步仍为实际研究执行预算登记及未知受理查询恢复，而不是重新创建会话或重置累计付费scope。

## 阶段四：共享研究调用预算与当前 Native 适配

前一goal turn分类为PROGRESS：源码/报告已提交，并得到真实Native会话目录及完整资料副本证据。本turn继续完整目标，先复核d97637c21/干净续跑worktree和目标原文；宿主macOS，任务为功能开发，本平台范围保留Native/Mac Docker与同SHA Mac CI。

- 发现Hot native-dsh.mjs仍硬编码旧c919且挂载旧协议模块，正常Manager却已从共用合同选择48504，构成真实装配缺陷。RED新真实构建测试拒绝当前固定源码；修复为读取共用runtime合同、拒绝不同提交/alias/modified tracked checkout并挂载新版llm-deepseek-api-key。真实目录、零重试/512 output prepared call和正常factory就绪1 PASS；凭据/预算为describe-only synthetic，未解析密钥/未发送，不等同真实推理或Keychain验收。
- 今日官方定价页实际读取，deepseek-flash/DeepSeek-V4.1-Flash及峰值$0.30/$0.006/$1.20每百万uncached/cache-hit/output核对，来源 https://api-docs.deepseek.com/quick_start/pricing/ 。新增非自动授权的2026-10-12价目，旧记录保持；validator支持当前正式名称和旧兼容名称，拒绝其他型号/低价/错误来源。
- migration17新增不可变research_model_calls。research-model内核把run/session/call UUID、请求哈希、固定价目和attempt关联，与既有model预算预留放在同一owner事务；不复制scope、不新建队列、不发provider请求。新的call须活动run/Native/当前价目/既有授权。worker不能插入映射，原子插入失败回滚预算及attempt。
- 真实随机PG测试证明普通Hot调用与研究共用2次总额度，重复callId为busy、冲突请求/异session/超额/非control/终态新增调用拒绝；保存synthetic回执后复用，映射不可改，取消旧callId不产生新attempt。该证明不认证实际LLM请求input bound或完整研究费用。
- 独立TypeScript审查发现已存回执在终态/跨日不能复用，按Goal要求修复：先按不含日期价目的不可变请求身份读取原attempt，再验证新调用。终态/跨日RED→GREEN；取消状态及cache attempt归属明确拒绝。异步callback类型收窄错误被typecheck发现后捕获数值并复制冻结参数，最终typecheck PASS。独立最终静态复核未发现新阻断；其未执行PG/native付费验证。
- Hot TS单元43/43 PASS，实际随机PG共享预算/旧累计账本竞争及签名HTTP/DataHub组合2/2 PASS。首组合预算fixture未支持本worktree路径被拒，显式fixture/current port接入后通过；失败日志保留，未改原旧端口回执。
- 审计发现旧model-budget回归夹具不清理其随机schema/role。本turn五次测试遗留资源用17迁移checksum、明确五次日志窗口、synthetic授权、空产品表、唯一role ACL、无活跃连接及外部依赖核对，再按精确列表事务删除并逐个确认。原Hot schema/卷保留，4/1417/659microUSD及paused状态未变。fixture已加入仅本次创建标记与精确清理，实际新回归PASS；历史或未知资源未清理。证据budget-resource-audit/cleanup.json。

下一步仍须把该内核接入私有Host/DSH llm/stream，先登记每次实际发送、实际request input上界、回执与unknown，再沿既有ResearchService/DSH完成真实研究与产物；当前尚未发正式研究。原schema仍15，不以随机schema17替代安装/迁移。原累计授权继续20calls/20000tokens/$1，未重置/扩额。跟踪/定时简报、持续公开来源重验/留出样本、联合恢复、Mac Docker、干净安装及同SHA CI仍未完成，Goal ACTIVE。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"同一PG预算/owner事务内增加研究call映射，并修复既有最小Native模型适配以共用固定DSH合同；不增加服务/队列/执行器，流级研究桥尚未装配，图11既有PG审计/研究映射边界保持。","diagrams":[]} -->

### 本切片收束

最终typecheck、43项Hot单元、两项真实PG集成、真实固定DSH目录/prepare1项及Router所选完整治理110项PASS；21文件项目约束、架构/文档治理、Python索引和whitespace检查PASS。旧授权scope与运行暂停态未变，精确测试清理回执已核对。没有发送provider调用、发外部消息、发布远端或迁移原库。其他平台与当前候选Mac安装CI仍NOT_RUN，完整Goal ACTIVE；这份本地进展不等于研究闭环完成。

预算/目录内核源码检查点 `b85be5079` 已提交，三项选定local gates再由monotonic计时runner记录命令、状态与时长；冻结plan4/receipt3在 `logs/hot-resume/research-quota-candidate-*.json`，validator valid=true、hostAcceptance BLOCKED、aggregate NOT_READY，Mac Bootstrap及其他外部门仍NOT_RUN。

目录准备之后继续核查wire层，发现旧baseURL会令新版SDK请求https://api.deepseek.com/v1/messages而不是/anthropic/v1/messages。新增完全替换fetch的不出网探针，URL反例RED；使用相同固定SDK的PUBLIC_BASE_URL后两项native集成GREEN，核对synthetic x-api-key和唯一发送尝试。首测试错误地期待throw/error chunk，实际SDK源码将adapter异常映射为finish.reason.kind=error；按源码修正，保留这些失败日志，没有吞掉provider失败或放宽断言。fake key不来自Keychain，实际vendor请求仍0。正式DSH研究及其私有预算桥未提前认证。

最终wire修复源码候选 `dba28e843`，继承预算候选b85。独立TypeScript限定复核及typecheck PASS；两项真实SDK目录/离线wire探针PASS，文档/架构/whitespace检查PASS。全切片冻结plan/receipt在 `research-quota-final-*.json`，validator valid=true，host/aggregate继续BLOCKED/NOT_READY、外部门NOT_RUN。报告提交仅保存续跑事实，不表示Goal、付费研究或远端交付完成。

## 2026-10-13 用户指定 AIHOT 开源复刻

用户明确指定 reverse-engineering / reverse-engineer-anything 与 aihot.news，并提供开源仓库。
这作为原完整Goal的产品方向补充：按开源实现复刻阅读体验，当前“研究情报”品牌和八栏目保留。
宿主macOS，功能开发；Mac mini主开发/Docker及同平台CI范围遵守新版AGENTS，其他平台未验证。
前一turn为PROGRESS（共享研究预算/新版native wire源码与证据已提交），本turn从41a1e5d8d干净续跑。

只读取得上游最新652bd6b，读MIT/NOTICE，不复制名字/Logo。已按源码梳理首页/全部/热点/日报/
详情、筛选分页、已读/收藏机制；模型榜、重置监控及运营数据未开源。完整参考/Design Read与
证据机制表在 `2026-10-13-aihot-replica-reference.md`。没有新增依赖或运行上游后台。

RWB新增hot-reader纯JS/CSS，沿源码暖纸面/青绿、日期轨道、紧凑热度条和来源理由；本地及外部
共用阅读主题。保留现有详情、修正、来源、简报、Origin和控制边界。日期标为观察记录；未知
不造时间；指标分开；本页热度条明确非全榜，不造趋势。重要性排序不被日期分组重新打乱。

独立TypeScript审查以内存mock复现两项P2：新筛选失败混合旧页；离开视图后旧拒绝污染新错误。
已先RED后修复共享reloadEvents（快捷按钮与原高级筛选共用），清空旧分页、限定current(ticket)
错误，more要求hasMore；补充分页迟到错误反例。最终Hot/Reader/Intel23项PASS，不把mock当完整后端证明。

原站 CUA 创建的标签存在，但AX/截图观察超时；REA受控Chrome成功加载却返回blocked/567，
原站视觉比较 NOT_RUN，没有绕过拦截。REA本地工作台截图/外部真实Golddata总览均成功、page-error
为零；样式资料预览用只读PG真实宏观事件，原实例仍暂停、无模型/修改调用。桌面1440与手机390
实际查看，手机标题/操作进一步压紧；首次18198导航启动窗口失败，HTTP200后仅原场景重试成功。
上述证明本地布局/资料读取，不认证正式DSH研究、完整安装或实时采集。源/截图/证据ID详参考报告。

最终全量Web JavaScript回归392项：391 PASS、1 SKIP、0 FAIL（7338ms）。20个变更文件的
项目约束、架构与文档治理PASS，Python文件索引PASS。没有Python源码、依赖或安装器变更；
pyproject现有app打包范围覆盖静态目录，干净macOS安装/候选CI仍NOT_RUN，不能用本地预览代替。
最终1440×1000和390×844只读真实资料预览均完成，page-error为零；独立预览favicon返回404，
保留为非产品页面的控制台记录。独立TypeScript复核已覆盖筛选及分页迟到错误，未发现新阻断。

原后台阶段零至五、两域持续来源、真实模型/研究、关注/计划简报、联合恢复、Docker与候选CI等
全部目标仍保留，Goal ACTIVE。下一步继续实现开源精选/关注/日报与既有Hot/研究预算闭环的适配；
不将这次布局复刻重定义为完整Goal结束。无push/PR/merge/部署或新付费调用。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有研究情报页面内复用原事件/频道GET和控制器，新增纸面阅读组件与主题不新增API、服务或执行器；保留工作台路由、八栏目与原有写边界，框架画布不受局部CSS影响。","diagrams":[]} -->
<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"该轮仅记录前端开源适配许可和现有数据/运行边界；原schema/模型scope/唯一队列/Owner未改，真实宏观资料为只读样式预览，不把预览绘成新增产品运行路径。","diagrams":[]} -->
