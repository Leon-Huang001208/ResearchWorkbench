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
