# 固定公开指数个人仓库桥本地实现

宿主macOS，功能开发；基线5d3927fae923d443a2c85431e4bc6ec33be7c9f6，任务market-warehouse-20261023。使用受管独立worktree，不部署、不安装依赖、不操作现有服务/5432/外盘，不调用真实来源、模型、付费接口或宿主凭据。

默认Host→POST indices→MarketReader→ResearchWarehouse/SnapshotSeries已实际接通；POST强制真实上游读取，仅受信内部允许缓存读可命中同源短时捕获。完整固定12指数响应入仓，失败/缺行/缺分时/partial不覆盖旧完整。仅数据库busy/unavailable/operation_failed降级为明确未持久化，授权/合同错误传播。profile id/owner/enabled/config摘要、来源合同/配置摘要及Host根/关闭状态读写前后复查，底层MarketStore授权保持。没有虚构sid、Broker注册、多源等价或公开来源grant；eastmoney公开访客无独立授权开关是明确范围限制。

TDD实际RED：新Reader不存在；默认Host HTTP POST后缺warehouse元数据；非有限响应未返回预期安全错误。相应GREEN及相关闭包128 PASS+12 subtests，4.30秒。已有批准venv执行：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_market_reader.py tests/research_web/test_market_service.py tests/research_web/test_market_provider.py tests/research_web/test_research_snapshot_store.py tests/research_web/test_research_warehouse_management.py tests/research_web/test_market_store_operation.py -q`，本地完整日志在`logs/market-warehouse-20261023/local-tests.log`。

已用既有socket-only临时PG helper执行默认Host/HTTP POST/真实Postgres/内部命中闭环，初次1 PASS，2.69秒；确认自有PG停止、数据根删除、TCP disabled、fsync on。真实凭据后端构造和读写方法在新测试中fail closed，MCP signing key仅来自测试内存backend。最终开启同一显式PG门并合并上述离线闭包与新PG模块运行：129 PASS、12 subtests，6.61秒；完整日志`logs/market-warehouse-20261023/local-final-tests.log`保留实际PG清理见证。Host测试最终调用完整Host.close，HTTP后台轮询受5秒测试时限约束。

独立SPEC提出P2：畸形时间、非对象分时或缺change_pct仍可能入仓。12种畸形完整封包用例实际先RED，修复后逐行/逐点校验真实Provider的完整ISO秒、同日严格递增、有限必需数值和身份/覆盖一致性，null必需字段保留上游展示但拒绝捕获。相应最新完整闭包含显式自有PG为141 PASS、12 subtests，6.92秒，日志`logs/market-warehouse-20261023/local-reviewed-tests.log`；本次使用本任务唯一basetemp，避免并发pytest共享临时目录清理。旧完整batch不增加/不被覆盖也有断言。

ruff、black、isort、三个修改仓库源码的mypy、生成pyindex、documentation治理、完整changed set的Project Constraints、架构门和doc-sync均PASS。完整changed set Router生成L4计划（`logs/market-warehouse-20261023/plan.log`）。所有命令返回码与实测秒数在`logs/market-warehouse-20261023/check-summary.json`；不把本机成功写成同候选CI已通过。

代码与文档未提交，独立spec/quality评审、同候选CI/Mac干净安装、常驻部署、Windows/Linux/Docker产品验收仍NOT_RUN。仅向既有Checks同一步骤追加两个新测试文件，真实PG缺显式环境保持skip。已核对requirements/web.in/web.lock、setup_web.py、安装文档与Bootstrap，本轮无新增依赖/参数；现有安装门保持，不能用批准venv冒充干净安装。

13市场图新增MarketReader/optionalWarehouse条件分支，纯静态Archify deliver真实9/9、0错误/0警告。首轮1300x900图由root实测1440x900纵向溢出1209，保留失败后修为1100x650三行；最终artifact为635bba7379adac04b70c187917727ee2d79f0d4958e41f9312313794b4bbb0c5。root通过cua_repl对四个desktop尺寸测得无溢出并实际查看1440/2048各深浅四张JPEG，已写同哈希visual-check及visual-review；未执行CLI visual-check。新图/root视觉证据由root负责，旧PNG不作为当前图证据。

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"默认Host注入indices-only无会话Reader并加入可选个人仓库条件分支；HTTP方法和原字段语义保持，13市场图对应新增读写路径。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"固定公开12指数原生响应接入既有ResearchWarehouse和StorageRunner，13市场图新增完整写仓与仅内部允许缓存读取边；其余Broker、研究会话和既有仓库节点保持。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service.py只注入市场Reader，自动化初始化、调度、执行和持久化逻辑完全保持；不增加自动采集或任务节点。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在原Checks同一pytest列表追加两个模块，无新job、runner、条件、timeout、依赖或权限，PG门未开启时仍skip；既有08交付流程节点准确。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"更新模块合同、源码索引和13市场图登记，不改变文档服务、首页生成器、API Atlas生成器或文档治理拓扑。","diagrams":[]} -->
