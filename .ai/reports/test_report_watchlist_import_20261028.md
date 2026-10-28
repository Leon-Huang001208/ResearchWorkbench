# T5 股票 CSV 自选导入本地实施

宿主 macOS，任务为 Web 功能开发。基线 1be480183187f181dbcee486d943aabb3559c9d5。本报告只认证下述实际本地证据；独立评审、完整Router、同候选远端CI/Mac干净安装和最终合并由协调任务另证，常驻部署不在本轮执行。

源码阅读检查点 `137fafb58376da83cd3bc715463e872e0d32aaad` 已在本地提交；后续仅固定文档/Atlas的源码链接，不把阅读pin视为独立评审或远端验收。

## 变更与约束

原资产观察自选入口增加严格 CSV → 全行预览 → 显式消歧/跳过 → 重新冻结 → 确认追加，支持既有本地已获准SH/SZ/BJ股票目录。ETFs、fund/index/industry/theme明确unsupported，不猜身份，不取数或模型。原导航、唯一DSH、观察/场景/报告/调度保持。

新增两端点与同index有界导入namespace（8MiB / 20活动预览 / TTL30min），提交与幂等回执一次save。已提交记录压缩正文，预算不能删除幂等回执。Store实例共享RLock覆盖批次读取/CAS/stage/save/rollback与完整Store.save，旧create/add共用；失败只恢复本批引用，不覆盖非目标业务。

实际发现旧Host后台线程 `service.business_prompt_index → Store.files → save` 可偷发布失败批次，因此在批准最小范围内补共享锁。无全Store生命周期lease/DB/跨进程改造，不承诺共享root多Host或任意业务方法线程事务。Automation全Store快照回退仍按原事件循环同步入口；Store无父目录fsync，断电保证NOT_RUN。目录资格沿原本地配置/凭据状态检查，不接收新秘密或读取查询token，测试用内存边界。

## 已执行证据

- 首个真实Store/Workspace测试：RED缺preview方法 → GREEN1项，logs/watchlist-red.log及watchlist-green.log。
- 新导入后端33项此前分组均通过；旧目录/自选16项通过，logs/watchlist-backend-b1-r2.log、b2、b3与watchlist-original-regression.log。最终共享锁后完整分组结果待下节更新。
- 真实线程屏障RED：logs/watchlist-thread-red2.log：失败导入内存0项、磁盘3项且1个幂等回执，background stole_publish=True。GREEN4→6项：watchlist-thread-green.log/green2.log，真实后台files/save、相反序列化顺序、两个Workspace共Store及create/preview/confirm失败/成功；无测试私造互斥或伪造save成功。
- Node新增9+原自选30=39项通过（watchlist-node-b1.log），文案/同File改善后新9再次通过（watchlist-node-b2.log）。最终Node闭包另更新。
- 真实临时Host/Chrome桌面3旅程通过。r5收紧实际可见性后390px真实失败，r5-result.json/r5-failed.png及watchlist-browser-r5.log保留，未沿用允许0宽的错误断言。原More通过既有disclosure key恢复，长文本grid最小宽度修正后r9五旅程通过：完整预览、键盘选择/skip/refreeze/3项追加并原列表刷新、旧writer介入冲突、390px中文错误/原File无重选重试、浅深色/长文件名/120字字段/键盘跳过再冻结。日志watchlist-browser-r9.log及watchlist-import-e2e/result.json；pageerror/外部URL/提供方模型调用均0。
- 最新两张截图已直接查看：narrow-error-input-retained.png显示原生非法.csv与中文公式行动提示一致；narrow-dark-long-text-keyboard.png长文本与按钮可见。未知错误不回显后端异常/路径，API/日志code保持。

## 待完成的最终本地汇总

最终本地结果：新导入模块45项全部覆盖，分组19+20+7通过（confirm_success重叠1项）；Store回归13项、原目录/自选16项通过，共74个不同Python用例。分组driver的实际argv/PID/UID/不透明根/dev/inode/基线与时长在logs/watchlist-final-{b1,b2,b3,store,original}.json，时间分别24.677/28.092/10.388/0.382/2.694秒。包含真实新进程读取响应丢失后的原回执、同root完整index备份恢复、字节/权限与后台文件登记保全。

Node聚焦闭包85项通过（watchlist-node-final2.log）；原测试的More精确HTML断言同步增加disclosure key，仍要求菜单初始关闭。Chrome r9五旅程通过；r8长文本撑宽失败保留，修复仅约束导入grid最小宽度/独立表格滚动，未退回0宽检查。

七个相关Python文件的Black --check、isort --check-only与Ruff均通过；mypy原pyproject配置针对5个产品源文件通过（watchlist-mypy-final.log，保留原untyped-body/unused-override提示，不宣称全仓零债务）。初版缺工具cache依赖和首次类型缺NoReturn的失败日志仍保留；无安装或ignore配置变更。架构全changed-set检查、API Atlas生成一致性、Project Constraints和文档治理均无violations；git diff --check通过。未执行root最终Router/独评/远端检查、macOS干净安装、常驻、真实供应商/模型、Windows/Linux原生、跨Host或断电验收。

未安装依赖，复用已存在Python/Node/工具缓存；本轮测试没有供应商、模型、真实凭据读取或远端操作。

## 架构复核

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"在已有浏览器到Host资产工作区、原AssetDirectory与Store聚合节点连线上加入离线预览/确认，API和additive namespace已单独登记；不增加运行节点、数据根、Provider、DB或研究引擎，现有聚合图拓扑仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"导入组件挂接原资产自选抽屉和controller列表刷新，继续原主题及disclosure状态机制，不增主导航或运行时依赖，原浏览器到Host图拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"只在原Store实例和index.json内增加有界导入记录及线程共享写锁，批次不另落回执文件、不新增数据库或跨Host租约；原文件节点和聚合流向保持，schema及保存语义已在模块合同说明。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅在现有Research Web Checks合同名单和Mac Bootstrap静态文件/模块校验扩登记，不增加job、runner、触发器、timeout或依赖，原验证路由和交付图保持，真实模型/供应商与远端门另证。","diagrams":[]} -->

## 自有资源保全

8个已登记自有fixture根无活动lsof持有者，经归档后在新不透明临时根实际恢复，70,045条目逐项验证regular字节SHA256、原mode、符号链接目标及硬链接数；归档138,771,355字节，SHA256 `7742db67141104419661a4f79ed799e3324d7094c7ad8fe03739c4368fe6f92f`，恢复耗时27.634秒。完整manifest/receipt位于logs/watchlist-evidence-archive/。原fixture根、验证恢复根、必要日志/截图和恢复归档均保留；合并前不清理，不返回cleaned。最初两次未进入追加ledger的浏览器fixture根继续保护，不按目录名/时间推断退休。父协调任务在最终验收/合并后负责精确归属、日志归档与安全收尾；本工作树ignored证据必须先保全再回收。

## 追加更正：旧浏览器fixture的外网边界

复核原Host raw日志发现，旧r9和早期SPEC夹具只拦浏览器URL/DataHub调用，未关闭默认Framework定时collector；不能认证整个Host外部尝试/成功为0。两份自有raw Host log实见218条完成HTTP响应日志（含redirect），200条2xx，GLD.json8条，UTC范围2026-10-28T09:41:05.772342Z至11:15:30.111459Z；尝试至少218，异常无响应部分不能反推精确总数。原日志/原r9结果/原handoff与SHA保留，不回填更强结论。

只读核对18个registered fixture或已验证archive内framework gold/dollar snapshot实际路径/字节hash；框架写入使用active Store.root/frameworks/{gold,dollar}/snapshot.json，HTTP helper原始响应在内存，派生数据落这些临时owner根。确切URL/时间/原log行号/hash与cache路径见ignored logs/watchlist-outbound-forensics/receipt.json；未读取生产数据或Keychain，早期未登记根未清理。此为已发生的公开网络访问，不是获准供应商实测或模型质量证据。

修正后，测试子进程使用既有RESEARCH_FRAMEWORK_COLLECTORS_ENABLED=0，且实际由/usr/bin/sandbox-exec执行tests/e2e/watchlist-loopback.sb（deny network*，仅localhost bind/inbound/outbound）；不改产品默认。Python audit只是补强，httpx/requests/urllib/curl_cffi同步/异步方法均计数拒绝；内核限制同时约束native C连接，不能以Python monkeypatch冒充。真实系统凭据后端入口fail-on-call，模型目录仅返回协议正确的空metadata。当前观察使用真实DataHub Snapshots.publish的empty Result/完整manifest/原件/当前配置摘要，明确合成空数据，不造成功行情。

新kernel-bound epoch原5+新增3旅程通过，result分别在logs/watchlist-import-e2e-kernel-bound/和watchlist-spec-lists-e2e-kernel-bound/；每个绑定13个实际执行源文件hash、profile hash、childPID与计数。旅程内受控客户端/Python socket的非loopback尝试、成功、Provider/模型和真实凭据调用均0；raw Host日志无外部HTTP、API异常或collector启动记录。独立6类HTTP负例均在客户端前置拒绝（各尝试1/成功0），2个手工sys.audit事件验证钩子；这些不是Host旅程的0计数。独立native curl负例返回7且Immediate connect fail Operation not permitted，未接收HTTP响应；正式回执logs/watchlist-native-kernel-negative.json，另保留先前两次ad-hoc内核拒绝。不能将网络封锁当作真实供应商可用性或授权。
