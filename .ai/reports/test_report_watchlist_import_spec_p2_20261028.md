# T5 SPEC P2：已有观察下的新建自选目标同步

原检查点 d246cbbceae6b00c57187d7c301196c9371cb74e、r9 与原handoff均保持原epoch，不改称本修复候选的通过。独立SPEC发现：原创建按钮之后的sameAsset路径不重读watchlists；局部Summary复用原importer也未同步data-lists，导致首建/后续新列表缺失。

## 最小修复

原createWatchlist请求成功后发账户绑定metadata事件，AssetWorkspace controller只重读原watchlists，带账户/读版本防迟到覆盖；不改app.mjs、sameAsset判断、Provider或模型。局部Summary移动原importer前同步新的data-lists；统一目标同步在仍存在时保留用户选择/File/预览，仅目标消失或显式改选才使冻结失效。既有HTTP/Store/DSH及目录/事务合同不改。

## 实际验收

Node沿真实createAPI→controller→sameAsset activateView链先RED：首建列表仍undefined（logs/watchlist-spec-create-red.log）。修复后新增同链及目标同步回归，新模块12项通过（watchlist-spec-create-green.log），不只断言静态attr。

新真实loopback Host/Chrome三旅程通过（watchlist-spec-lists-browser.log、watchlist-spec-lists-e2e/result.json）：服务启动前已有真实持久观察且0列表；原按钮首建A，保留先选File后freeze/confirm；A存在时原按钮新建B，A不乱切、B可选，改B必须重冻再confirm；直接实际updateAssetSummary partial更新同DOM节点/同授权File与新options。Session/observation数量保持，外部URL/Provider/模型为0。夹具只种本地已存在的合成观察缓存，不mock业务路由或返回假成功。截图current-observation-first-list-confirmed.png与second-list-confirmed.png留于同ignored输出目录，未覆盖r9。

本轮为macOS Web限定修复，不执行质量阶段、远端操作、部署、新依赖或真实供应商/模型。最终聚焦闭包、格式/完整性及源码pin在提交前追加；原SPEC须复核Approved后由协调者进入quality/Router/同候选CI。

## 旧fixture收尾（独立ignored回执）

按父任务明确授权，原8已登记fixture根及确切restore副本全部退役，原handoff与执行SHA未改。先在durable目录复制archive/manifest/receipt并readback，9根140091条目核对type/UID/dev/inode/nlink/bytes/mode/creatorPID/lsof/进程引用，无外部hardlink；30820只读Catalog目录仅在原mode已实际恢复对齐后补ownerwrite，并逐路径审计。逻辑文件922970782B、原唯一file block1138139136B移除；全盘free同时受其他任务写入影响，不以差值认证释放量。早期未登记108eRR/lnTzjo仍保护。状态仅registered_fixture_roots_reclaimed，不宣称整任务cleaned。回执logs/watchlist-fixture-closeout-e6258b25be0f/receipt.json SHA256 0130a67e961b3a992a299663b9a2bcf2e3a733f225c2c4a10fb4ddd12767eb63，旧archive durable SHA7742db67141104419661a4f79ed799e3324d7094c7ad8fe03739c4368fe6f92f保持。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"只用原创建API成功事件刷新原列表metadata，原资产组件局部props同步保留File与目标；无新HTTP、引擎、Provider、节点或依赖，原浏览器Host图拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"修复原观察sameAsset路径下的自选目标metadata投影，不改变sameAsset条件或Store事务，不新增API/数据根/服务；原工作台聚合节点与图准确。","diagrams":[]} -->

## 追加更正：旧浏览器fixture的外网边界

复核原Host raw日志发现，旧r9和早期SPEC夹具只拦浏览器URL/DataHub调用，未关闭默认Framework定时collector；不能认证整个Host外部尝试/成功为0。两份自有raw Host log实见218条完成HTTP响应日志（含redirect），200条2xx，GLD.json8条，UTC范围2026-10-28T09:41:05.772342Z至11:15:30.111459Z；尝试至少218，异常无响应部分不能反推精确总数。原日志/原r9结果/原handoff与SHA保留，不回填更强结论。

只读核对18个registered fixture或已验证archive内framework gold/dollar snapshot实际路径/字节hash；框架写入使用active Store.root/frameworks/{gold,dollar}/snapshot.json，HTTP helper原始响应在内存，派生数据落这些临时owner根。确切URL/时间/原log行号/hash与cache路径见ignored logs/watchlist-outbound-forensics/receipt.json；未读取生产数据或Keychain，早期未登记根未清理。此为已发生的公开网络访问，不是获准供应商实测或模型质量证据。

修正后，测试子进程使用既有RESEARCH_FRAMEWORK_COLLECTORS_ENABLED=0，且实际由/usr/bin/sandbox-exec执行tests/e2e/watchlist-loopback.sb（deny network*，仅localhost bind/inbound/outbound）；不改产品默认。Python audit只是补强，httpx/requests/urllib/curl_cffi同步/异步方法均计数拒绝；内核限制同时约束native C连接，不能以Python monkeypatch冒充。真实系统凭据后端入口fail-on-call，模型目录仅返回协议正确的空metadata。当前观察使用真实DataHub Snapshots.publish的empty Result/完整manifest/原件/当前配置摘要，明确合成空数据，不造成功行情。

新kernel-bound epoch原5+新增3旅程通过，result分别在logs/watchlist-import-e2e-kernel-bound/和watchlist-spec-lists-e2e-kernel-bound/；每个绑定13个实际执行源文件hash、profile hash、childPID与计数。旅程内受控客户端/Python socket的非loopback尝试、成功、Provider/模型和真实凭据调用均0；raw Host日志无外部HTTP、API异常或collector启动记录。独立6类HTTP负例均在客户端前置拒绝（各尝试1/成功0），2个手工sys.audit事件验证钩子；这些不是Host旅程的0计数。独立native curl负例返回7且Immediate connect fail Operation not permitted，未接收HTTP响应；正式回执logs/watchlist-native-kernel-negative.json，另保留先前两次ad-hoc内核拒绝。不能将网络封锁当作真实供应商可用性或授权。

## 最终SPEC修复本地闭包

新增“首建metadata在File读取中到达”的真实失败回归（watchlist-spec-file-metadata-red.log），File读取独立于预览目标版本并通知当前mount后GREEN。真实浏览器首建旅程刻意延迟原已授权File.arrayBuffer，到A选项出现后释放原字节，再预览确认；不替换业务API。既有目标与File保持，显式换B后重冻规则不变。最终Node聚焦88项通过；新受限进程8旅程和边界负例分别如上，不挪用d246的旧Host零外网claim。Python产品源文件未改；本轮仅测试fixture/probe及JS，原74不同Python结果属于d246 epoch，不伪称已对新完整候选重跑。Black/isort/Ruff两fixture文件、架构/Atlas/Constraints/文档治理/diff-check最终结果在提交前记录。SPEC复核尚待，不进入quality/发布。

最终本地闭包补充：Node88项通过（含首建metadata/File并发RED→GREEN），受Seatbelt真实Host的原5+新3旅程均以当前代码hash绑定通过；两份kernel-bound result共享12个源文件hash，独立运行器各自第13个hash。边界汇总logs/watchlist-spec-network-boundary.json SHA256 e17981ab80623a7254eb35b7e024e169d9c0c38ffffa61417d7db94b81f2961e；负例和旧epoch外网纠正不计入正常旅程的0尝试。Black/isort/Ruff两测试Python文件、架构/Atlas/Constraints/文档治理和diff-check通过；新增完整empty snapshot后截图无模型目录或研究资料API异常。原74不同Python结果仍属于d246且其产品Python字节未改，本轮不重复认证为新完整候选。未开始独立quality/发布，等待原SPEC复核。
