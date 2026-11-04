# RWB MCP 私网只读首版实施记录

任务：`rwb-mcp-readonly-oauth-20261104`。宿主 macOS / Mac mini；类型为 Web 功能开发，验收范围为本机隔离验证及适用同平台安装 CI。Windows/Linux 产品验证、常驻服务、真实账户授权和生产数据迁移不属于本次自动执行范围。

## 身份与状态

- 基线：GitHub 与共享 Git 对象均确认 `87b6cd99653d9f8160dc7eb0b3bea8d5d9ea93db`。
- 工作区：Codex 原生登记的独立 `codex/mcp-readonly-oauth-stage` 分支；原工作区未修改。正式 GitSafety start 因 GitHub SSH 认证失败而未创建交付回执。不能以原生工作区替代正式发布流程。
- 授权存储已提交 `0c00e6bd14a6bb0e57d383d90b6cdb06c78b6900`；独立 Python/规格评审 Approved。OAuth ec425b5→d494a1b→c911b3b、工具8b8a012→ea530f3已独评 Approved；Task3源码 c615b8b63498619adc173901f70bf45518b5f870 已提交，最终全量Router/评审、同候选CI与发布尚待完成。
- 常驻更新、Codex 私网双设备实链、官方 DSH 与 WorkBuddy 原生 OAuth：`NOT_RUN`；本地通过不提升这些状态。

## 已冻结合同

见 [入站 MCP 合同](../../docs/research-web-mcp-facade.md) 及 [实施计划](../../docs/superpowers/plans/2026-11-04-rwb-mcp-readonly-oauth.md)。仅开放四项批准冻结材料的读取工具；固定原生公开客户端、PKCE、持久摘要授权和逐对象权限。保留 DSH/DataHub/Provider/质量门，FinGPT/Claw 的通用执行能力停止扩建，既有入口不退役。

## 只读与 SDK 核验

源码定点核验表明，普通文件列表会写入文件索引，来源读取在缺档时可能抓网；新 facade 必须避开两者。原 manifest 字节摘要、行文件摘要和文本片段摘要分别表达，不将 URL 增补后的 JSON 当作原 manifest。

锁定 SDK 为现有 `mcp==2.2.0` / `mcp-types==2.2.0`。原生 `MCPServer` 可用，FastMCP 不适用；SDK 的 token resource、公开客户端元数据和授权响应 issuer 需要薄适配及真实 HTTP 负例。没有升级或修改 SDK。

## 测试环境与事故保留

首个环境存在 SDK 但没有 pytest，`store-red` 实际退出 1；该结果是环境失败，不能当行为 RED 或 PASS。未安装依赖。随后验证另一已有环境同时具备锁定 SDK、pytest 和检查工具；通过显式 `PYTHONPATH` 验证 app/core 源码指向本任务工作区，不执行历史产品源码。

初次没有生成业务夹具的临时根按原 lease/nonce/批次/节点恢复：容量检查、真实 pytest、输出哈希及正式 retire 完整执行。`store-red-recovery-01` 得到一个明确预期的 `XFAIL`，只证明尚无授权存储实现，不能当业务验收。原环境失败输出和结果保留，没有伪造退出码、删除未知临时根或覆盖回执。后续 GREEN 必须去除预期失败标记。

Task1 WIP：16 项授权存储测试、17 项既有账户回归和 3 项后补边界测试通过；Ruff、Black、isort、Mypy 和 diff 检查通过。独立评审复核规格、事务和日志边界，没有重跑行为测试。这些回执不代表 exact-SHA、HTTP 或 CI 验收。

任务日志位于 `logs/rwb-mcp-readonly-oauth-20261104/`，最终须生成逐文件保留清单。最终候选认证将在完成后补入，不预填结果。

## Task3 集成与证据

Doctor 使用标准库环境开关和 distribution metadata，不初始化 SDK/AccountStore/授权表，不读取凭据或历史正文；安装版本与连接状态明确分离。离线升级在临时账号库验证原 accounts/sessions 行、cookie 和 history 不变；授权跨重启，关闭入口＋显式撤权＋重开不复活旧 token，logout 独立而 reset/disable 撤权。固定图15阅读只增一项名称，不放宽路径。

Task3最初3个 strict XFAIL 受日志夹具污染，不能作为有效行为RED。首轮实际10项为3FAIL/7PASS，因账户创建日志混入测试stdout导致JSON解析失败；修夹具后沿同一lease/nonce/root恢复10PASS，原失败输出保留，正式retired。随后在finally逐字节恢复保护下以旧Doctor基线补做1个strict KeyError XFAIL：这是事后基线回归，不是先写测试的证据。最终focused14项PASS（1.81秒；既有Starlette/AnyIO弃用警告1项），root retired；其中含6 Doctor、4生命周期、1固定图及3既有只读合同。记录在doctor-lifecycle-green-fixture-repair-01和task3-focused-final。

新增L4 Router测试初次因非法文件prefix失败，改成六个精确test路径后1PASS（三类路径均保留全部门）。Doctor文本输出的dict推导导致一次mypy错误，改成本地已知dict后2文件mypy通过。Ruff、Black、isort和diff检查通过；完整本机Router、全分支独评和同候选CI由主任务完成，不预填。

CI不增加job/runner/deps/timeout；MacBootstrap新增SDK导入与enabled Doctor无创建目录断言。requirements/web.in、web.lock、setup_web.py与安装workflow已核对，锁内SDK2.2/multipart0.0.32/Starlette1.6，本机不安装依赖；干净安装兼容NOT_RUN。原生Codex/DSH/WorkBuddy/privateTLS、真实用户授权/报告、Provider/model、常驻更新与部署全部NOT_RUN。源代码与示例均不等于外部已启用。

<!-- architecture-review {"group": "inbound-mcp-readonly", "structure": "changed", "diagrams": ["15-inbound-mcp"], "reason": "新增可选入站OAuth与四项读取边界，原账户授权表和存活后端调用在专用图15完整表达。"} -->
<!-- architecture-review {"group": "private-multiuser", "structure": "changed", "diagrams": ["15-inbound-mcp"], "reason": "私网网关可选挂载OAuth和MCP，独立授权及存活账户后端分支连接原账户与RuntimePool；原登录及生命周期保留。"} -->
<!-- architecture-review {"group": "datahub", "structure": "changed", "diagrams": ["15-inbound-mcp"], "reason": "既有GET增加受信只读探测和严格交接拒绝分支，在图15体现固定冻结读取，原DataHub数据拓扑与Provider保持。"} -->
<!-- architecture-review {"group": "ui", "structure": "unchanged", "diagrams": [], "reason": "现有账号菜单按服务器开关增加应用入口，登录回跳和同意页仍属原网关；研究工作台和主题拓扑保持。"} -->
<!-- architecture-review {"group": "research-api", "structure": "unchanged", "diagrams": [], "reason": "原Host GET内部新增严格只读早拒绝和协议探测，保留原路径与浏览器语义，外部网关新边界由专用组图15表达。"} -->
<!-- architecture-review {"group": "workbench", "structure": "unchanged", "diagrams": [], "reason": "trusted_context只读参数在既有交接入口提前拒绝副作用链，不增加研究工作台节点或更换原场景执行器。"} -->
<!-- architecture-review {"group": "documentation", "structure": "unchanged", "diagrams": [], "reason": "阅读器固定白名单追加已审图15，原受限目录读取及CSP不变，入口与Atlas仍由同一生成器维护。"} -->
<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "diagrams": [], "reason": "既有Checks和Bootstrap步骤扩充离线测试与元数据断言，L4保留原全部门，不改变runner或交付生命周期。"} -->

补充 stdlib 独立检查：`RWB_MCP_READONLY_ENABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /opt/homebrew/bin/python3.12 -S -m app.research_web.multiuser doctor --root <本任务日志下不存在的doctor-no-create> --json` 实际退出0，JSON可解析、SDK未安装状态明确，目标根仍不存在；未接触真实服务或用户配置。

## 条件路由与合成浏览器补证

文档门发现原decorator扫描漏掉Gateway新增add_api_route条件块。没有删原6项catchall；新受限collector只接受该网关、唯一6-method literal及完整off/on块，动态路径／别名／额外方法／分支漂移失败关闭。新增12项条件代理，SDK机器和RWB浏览器8项单列libraryRouteContract，不伪称静态扫描事实。实际锁定SDK构造路由集合与声明精确比对1PASS（task3-sdk-routes，root retired），无网络或真实后端。独立源码检查点 222049521ddbb91199c494382d354bed78b3f24e。

Parser新增测试先实际2FAIL（缺collector），实现后2PASS；完整architecture JS最终88PASS/6.68秒，随后新增Atlas分层标签合同1PASS。原baseline图、未知语法负例、源码映射完整性和静态API数量语义保持；这89项不是native业务验收。文档与架构检查0 violations，Atlas生成427条静态声明/424个操作，另列SDK条件合同。

父会话补充实际Chromium Gateway合成链：authorize→真实auth网页登录→唯一synthetic选材同意→loopback callback→SDK token交换及subject→modern initialize counteroffer2025-11-25→四工具列表，cap/source-list零backendlookup；source_read原件hash验证、1次readonlylookup/2个固定GET，应用页一次撤权后token失效且真实MCP401。证据gateway-browser-result-01.json与apps-revoked.png；source ea530f3，gateway/tools字节未改变。一次精确locator因listitem含button未匹配而timeout，未重复点击，随后DOM“已撤销”和401独立确认。两个临时server及任务tabs已关闭。Backend为MockTransport，此证据只认证wholeGateway syntheticbrowser；privateTLS、CodexDesktop、DSH、WorkBuddy、真实Pool/Provider/model/常驻仍NOT_RUN。

## 最终审查统一修复（基线 e47f0e8）

Important1：持久 GET SSE 与完整响应缓冲不兼容，真实 HTTP 复现 ReadTimeout。现在使用公开 Starlette Route 与 SDK RequireAuthMiddleware/TransportSecurityMiddleware 组合，仅拒绝 GET；保留 SDK 全局 bearer 验证、401/403 challenge、Host/Origin 和原 POST 分派。合法 GET 返回 405/Allow POST；8项路由注册与 methods=null 保持，文档明确注册方法与允许方法的差别，后端调用计数为零。

Important2：永久领域错误采用明确白名单。兑换／刷新事务的临时故障交原 HTTP guard 返回503；authorize 因 SDK 自带 catch-all，使用其公开 AuthorizeError temporarily_unavailable 返回合法回调＋state＋issuer，避免永久 access_denied 和 SDK 意外异常日志。真实写入后分别注入安全拒绝、SQLite忙碌和I/O故障，验证原授权码、refresh、access及grant状态与行数回滚保全；未自动重试未知结果。

Minor3 与两项 exact-check 发现：UI文档开关改为 mcp_readonly_enabled===true；Node仅更新focused catalog19及DataHub routes明确入站MCP规则的预期，同时保留L4/full-delivery/所有平台门和其余unknown fallback；原FIFO测试仅增加自身创建FIFO的finally unlink，原子进程、2秒超时和断言保持。原exact-local-integrations批次04为20PASS而cleanup初次blocked，父会话已完成窄范围缺失teardown恢复；不能把该事件描述为业务测试失败。

本轮WIP证据：final-fix-red初次4FAIL中GET断言错把Gateway Host403当421，另外3项是有效错误映射RED；仅修正测试后同root red-get-01实际4FAIL（GET超时、兑换400、刷新400、authorize302 access_denied）。green-01为3PASS/1FAIL，揭示SDK authorize catch-all；改用SDK temporary错误后同root green-02为4PASS并正式retired。原各次失败与结果哈希保持。后续final-fix-focused-01/02/03明确20/20/5个展开node IDs，完整HTTP/OAuth＋FIFO＋8路由合同共45PASS，三root均retired；manifest及所有controller/stdout/JUnit/result在任务logs。Node final-fix-node-L1为75PASS，Ruff/Black/isort/Mypy（3源码文件）和diff检查通过。以上不是最终exact candidate、全Router、独评、CI或生产验收；剩余闭包由父会话绑定最终HEAD完成。

统一修复源码已本地提交 `aea209e8790b6f5a7c6c34de6ea361438ced8515`；阅读检查点与既有生成器的Atlas/Python索引随此提交同步，独立文档提交另记，不构造自引用SHA。完整feature基线87b6cd9的文档与架构检查通过；e47仅为本次fixdiff评审基线，其要求重改六份模块文档的结果保留，不据此机械扩大修改范围。冻结图15保持原source/HTML哈希。最终独评、完整local/Router、CI、正式交付及真实原生验收仍待主任务完成。
