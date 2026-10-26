# 固定公开指数个人仓库桥本地实现

宿主macOS，功能开发；基线5d3927fae923d443a2c85431e4bc6ec33be7c9f6，任务market-warehouse-20261023。使用受管独立worktree，不部署、不安装依赖、不操作现有服务/5432/外盘。原实现与回归使用离线来源夹具；其后按单独明确授权，仅执行下述一次固定12指数真实免费上游及自有临时PG验收。全程无模型、付费接口或宿主凭据调用。

默认Host→POST indices→MarketReader→ResearchWarehouse/SnapshotSeries已实际接通；POST强制真实上游读取，仅受信内部允许缓存读可命中同源短时捕获。完整固定12指数响应入仓，失败/缺行/缺分时/partial不覆盖旧完整。仅数据库busy/unavailable/operation_failed降级为明确未持久化，授权/合同错误传播。profile id/owner/enabled/config摘要、来源合同/配置摘要及Host根/关闭状态读写前后复查，底层MarketStore授权保持。没有虚构sid、Broker注册、多源等价或公开来源grant；eastmoney公开访客无独立授权开关是明确范围限制。

TDD实际RED：新Reader不存在；默认Host HTTP POST后缺warehouse元数据；非有限响应未返回预期安全错误。相应GREEN及相关闭包128 PASS+12 subtests，4.30秒。已有批准venv执行：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_market_reader.py tests/research_web/test_market_service.py tests/research_web/test_market_provider.py tests/research_web/test_research_snapshot_store.py tests/research_web/test_research_warehouse_management.py tests/research_web/test_market_store_operation.py -q`，本地完整日志在`logs/market-warehouse-20261023/local-tests.log`。

已用既有socket-only临时PG helper执行默认Host/HTTP POST/真实Postgres/内部命中闭环，初次1 PASS，2.69秒；确认自有PG停止、数据根删除、TCP disabled、fsync on。真实凭据后端构造和读写方法在新测试中fail closed，MCP signing key仅来自测试内存backend。最终开启同一显式PG门并合并上述离线闭包与新PG模块运行：129 PASS、12 subtests，6.61秒；完整日志`logs/market-warehouse-20261023/local-final-tests.log`保留实际PG清理见证。Host测试最终调用完整Host.close，HTTP后台轮询受5秒测试时限约束。

独立SPEC提出P2：畸形时间、非对象分时或缺change_pct仍可能入仓。12种畸形完整封包用例实际先RED，修复后逐行/逐点校验真实Provider的完整ISO秒、同日严格递增、有限必需数值和身份/覆盖一致性，null必需字段保留上游展示但拒绝捕获。相应最新完整闭包含显式自有PG为141 PASS、12 subtests，6.92秒，日志`logs/market-warehouse-20261023/local-reviewed-tests.log`；本次使用本任务唯一basetemp，避免并发pytest共享临时目录清理。旧完整batch不增加/不被覆盖也有断言。

ruff、black、isort、三个修改仓库源码的mypy、生成pyindex、documentation治理、完整changed set的Project Constraints、架构门和doc-sync均PASS。完整changed set Router生成L4计划（`logs/market-warehouse-20261023/plan.log`）。所有命令返回码与实测秒数在`logs/market-warehouse-20261023/check-summary.json`；不把本机成功写成同候选CI已通过。

原Market源码检查点为14b1396f2e3984abf543f077176012076dc939f1，原文档检查点为1a5a497004f4056de0fafabf93e20dad52616ec4。现合流候选a6ab304aaad2fd1a3f35e2caa95c4041356052bd已包含最新master d693d750e1deab0bb25c67b746684260b372ca4a中的Plugin/Auth改动；本次架构reading绑定该已提交组合源码检查点。另四个Market源保持原字节，service.py保留主线Plugin的57行新增；相对最新master仅增加原MarketReader import及MarketService注入hunk，不能用旧五整文件摘要冒充组合版本。独立SPEC复核31例及原反例拒绝/旧原件保持已PASS，root确认第二级Python质量评审亦PASS；最终合流独评另由root安排。同候选CI/Mac干净安装、常驻部署、Windows/Linux/Docker产品验收仍NOT_RUN。仅向既有Checks同一步骤追加两个新测试文件，真实PG缺显式环境保持skip。已核对requirements/web.in/web.lock、setup_web.py、安装文档与Bootstrap，本轮无新增依赖/参数；现有安装门保持，不能用批准venv冒充干净安装。

单次真实免费来源验收绑定精确HEAD1a5a497004f4056de0fafabf93e20dad52616ec4：实际MarketProvider通过计数transport转交原真实HTTPTransport，没有Mock成功响应。仅固定indices分区发24次真实HTTP，全部200、覆盖12个固定指数，12行完整、分页完整、三项missing均0；Host POST返回202并进入completed，真实自有Postgres事实数0→1、batch=1、warehouse.persisted=True。第二次受信内部allow-cache读取hit=True且同样12行，vendor calls保持24→24，没有追加探测或重试。总实测3.135秒，低于90秒及32次HTTP边界；未运行quotes/sectors等其他分区。

上述真实验证使用已有批准venv、NoModelsStub和内存凭据后端；SystemKeyring/PrivateFile构造及读写方法、keyring入口均fail closed，模型RPC=0、研究会话=0，Host.start/自动probe/Framework/调度器均未启动。PG仅由既有helper创建本任务私有临时根与Unix socket，端口65473、TCP禁用、fsync=on；启动后核验data_directory/socket/数据库及postmaster PID85904的实际进程身份。结束等待自有PG停止、删除自有PGDATA，再用ps确认原postmaster不存在；Host已完整close。未连接或修改现有5432、业务库、现有服务或外盘。

旧feature真实验收回执为该feature worktree内`logs/market-warehouse-20261023/real-indices-receipt.json`，SHA-256为7afc7e17685702830f0af35218f2ce69f5044f902c84b34086638d1d9cd5f87b；同目录`real_indices_once.py`及`real-indices-run.log`保留实际脚本与日志，现另复制到组合worktree的`logs/market-final-real/old-feature-proof/`供收尾归档。回执保存旧HEAD的五源文件逐文件SHA，彼时只读复算全部一致；其排序规范JSON映射聚合SHA为498cf06af197a3f7932099e71410fd385fc2e3fb98464bfa55ba6bfbbcd7b534。首次仓版本abab3471222578fcec180625137183208fcdf2c6bf88c1b0bbccd1d4f04ef57a，命中冻结摘要a39899b910222d1d31d6fa9c1a086869cfdc2dbeefbe994bba918f875262854a。记录只含安全计数、公开身份样例、来源/缺口和摘要，不输出大表。

这份真实证据独立于前述Mock/内存闭包：capture是规范化MarketProvider响应封包，不是HTTP wire原字节；仅证明该次单源indices的Host→仓库→内部缓存链，不证明其他区块、双源等价、正式PIT/回测、研究质量或生产部署。quality_accepted/formal_backtest_eligible仍为False；临时库已删除，不把回执当成常驻仓库已启用。

新增Plugin后的最终组合由root单独执行第二次明确授权的有界真实复验，精确绑定a6ab304aaad2fd1a3f35e2caa95c4041356052bd；结果PASS，2.583秒、24次真实HTTP全部200、12行/12指数及分页完整/三项missing为0。Host POST202→completed→自有PG事实0→1、batch1；第二内部读取hit=True、same_rows=True、calls24→24。两次已授权真实来源验证合计48次HTTP，未扩大到其他区块、付费或认证源。模型/会话均0，Host后台/自动probe/Framework/调度器均未启动；System/PrivateFile/keyring fail closed和独立内存凭据保持。新service整文件SHA为fb832e578e02bbb67bab855ee6514d1a101b86b395e0514352eb8977e2b44c9d，组合五源排序JSON摘要为2a2addac850fedbaa9c8b583886e3f7e7d6113cadca52e8ee319c2d822b21682；本次只读复算五文件全部与组合回执一致。

组合回执`logs/market-final-real/receipt.json`的SHA为0d141b64e29af4158cabaf44d6601040ce306f7878a35859758ccb2bce504e10；`verify_once.py`/`run.log`保留实际验证，`retirement-recheck.json`保留资源复核。新仓版本154d0ee8de359e6f9d07e5bc5461692513ff0179a21a537669cf8738210f2a8c，命中冻结摘要832faac276141d216b9081e86a7afb7f9d1ecf01b817efc1b3319c5de2c28cca。仅自有PG65473/Unix socket/TCP禁/fsync=on；结束停PG、删PGDATA及验证专用临时HOME，原5432和生产服务不变。首次组合脚本因清理环境时遗漏locale造成PG启动FAILED且0vendor；其后两个诊断均为PG-only/0vendor，`pg-path-diagnostic`记录FATAL postmaster became multithreaded及LC_ALL提示。root只在验证脚本子进程设置LC_ALL=C/LANG=C后通过；`initial-receipt.json`/`initial-run.log`和诊断JSON/log完整保留，不改失败为成功、不改产品或系统环境。此次仍仅规范化Provider封包/first_observed，quality/PIT/回测和双源资格不提升。

13市场图新增MarketReader/optionalWarehouse条件分支，纯静态Archify deliver真实9/9、0错误/0警告。首轮1300x900图由root实测1440x900纵向溢出1209，保留失败后修为1100x650三行；最终artifact为635bba7379adac04b70c187917727ee2d79f0d4958e41f9312313794b4bbb0c5。root通过cua_repl对四个desktop尺寸测得无溢出并实际查看1440/2048各深浅四张JPEG，已写同哈希visual-check及visual-review；未执行CLI visual-check。新图/root视觉证据由root负责，旧PNG不作为当前图证据。

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"默认Host注入indices-only无会话Reader并加入可选个人仓库条件分支；HTTP方法和原字段语义保持，13市场图对应新增读写路径。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"固定公开12指数原生响应接入既有ResearchWarehouse和StorageRunner，13市场图新增完整写仓与仅内部允许缓存读取边；其余Broker、研究会话和既有仓库节点保持。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service.py只注入市场Reader，自动化初始化、调度、执行和持久化逻辑完全保持；不增加自动采集或任务节点。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在原Checks同一pytest列表追加两个模块，无新job、runner、条件、timeout、依赖或权限，PG门未开启时仍skip；既有08交付流程节点准确。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"更新模块合同、源码索引和13市场图登记，不改变文档服务、首页生成器、API Atlas生成器或文档治理拓扑。","diagrams":[]} -->
