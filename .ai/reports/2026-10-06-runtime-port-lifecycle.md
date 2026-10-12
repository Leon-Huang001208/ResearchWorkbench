# Task 2 macOS 实际端点与双运行时生命周期

状态：NEEDS_WORK / BLOCKED，尚未完成完整设计验收；mergeReady=false，releaseReady=false。
宿主macOS，任务类型功能开发；仅隔离fixture与同宿主本地检查。
基线 `eee98236c8f7f30929a08ab4b9a0d5aa0eec19c9`。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"复用既有Native和单容器Docker部署节点；实际端点、同一生命周期锁、成对origin事务和临时guest准备仅扩充启动事务，不新增常驻产品节点或第二套研究引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"CLI端口和进程生命周期集成不改变HTTP路由、研究协议、DSH唯一引擎、框架或集成协调器拓扑；原PID、argv、启动时间、监听和认证事实链保留。","diagrams":[]} -->

## 已实现

- 安装器和Native start/restart公开Web/Runtime端口选项；Docker明确拒绝Runtime覆盖。
- 严格私有端点只读恢复、旧Native一致run-state非默认端口恢复；实际健康后CAS发布。
- Native/Docker/模式最终CAS共用原 `run/lifecycle.lock`。锁日志stdlib化，真实持锁对象
  `assert_held`供安装候选内部调用；无skip-lock开关，锁顺序lifecycle→metadata。
- Native和既有Docker成对controls仅改URL、保留tokens与额外字段；精确失败回滚。
- 单missing由无网络/无host发布端口/无真实凭据挂载的固定image临时guest调用原creator补齐；
  安装ID、nonce、image、command、mount和no-port全部核验。未知替换保留，不盲删。
- bind错误需明确证据且本次对象退出后才可重试，最大3次；非端口或归属/恢复失败不重试。
- Docker仅选择host Web端口，内部8088/3081固定；停止只以已拥有对象退出证明为准。
- EndpointStore.restore以本次发布快照CAS恢复逻辑端点，生成新revision防ABA，不覆盖另一模式。
- 安装候选origin事务保留至安装摘要/模式接受；失败精确清理并恢复旧端点/控制基线。

## TDD与阶段回归实测

全部Python命令使用已获准解释器
`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`，
cwd/PYTHONPATH均为当前隔离worktree，每次带 `--confcutdir=tests/research_web -q --tb=short`。

RED→GREEN日志位于logs/task-2-*：端点4、CLI3、锁导入1→原锁28、Native启动2、Docker锁/映射3、
Docker启动1、Dockerorigin2、bootstrap1、legacy1、switch1、guest原creator3、guestcontroller3、
Docker竞态1、Native竞态2、endpointrestore2、lease1、Dockerstop1、Nativestop1、Nativerestart1、logs1。
每轮RED为实际行为/缺失API断言失败，之后对应GREEN均通过；最初sandbox日志写/端口bind拒绝不计RED。
CLI首轮GREEN有不完整fake返回shape造成2失败，修正fixture后3通过。

阶段完整回归：task-2-progress-closure.log 为555通过/5失败；第二轮为615通过/113失败，
主要发现bootstrap不得eager导入app与缺失metadata旧state读取的兼容、最小checkout fixture依赖、
legacy私有状态重复读取掩盖瞬时替换及环境变量跨模块残留，已修复并保留负例。
task-2-bootstrap-closure-fixed.log：134通过/13.50s。
task-2-progress3-closure.log：640通过/5失败/46.15s；旧端口语义预期与supervisor main(argv)
兼容修复后 task-2-progress3-fixed.log：6通过。最终新增恢复闭包7通过，commit恢复/lease2通过。
这些阶段结果不等于最后完整changed-set验收；最终结果在后续追加。

## 尚未闭合与权限边界

- 既有停止Docker容器换host绑定仍返回 `docker_stopped_port_conflict`。为了保持已有
  no-recreate/停止容器保护合同，尚未执行自动exact-ID non-force disposition；该分支未达完整设计。
- 真macOS Native/Docker往返、guest UID映射、干净安装、镜像构建/真实Docker运行与所有CI均未执行。
- 无push/merge/tag/dispatch、依赖安装、真实用户controls/凭据修改或全局设置变更。
- 原main已通过外部PR79到1dbd7547（仅平台职责文档）；本agent未合并/重置，交付前需文档协调。
- requirements/web.in、web.lock、bootstrap workflow未改；兼容需真实macOS安装CI，不能以本机环境替代。
- parent批准额外lifecycle_lock.py stdlib化/持锁对象、supervisor准备入口与其测试；小型endpoint恢复
  API用于集成失败收尾，Task1严格身份/private/CAS语义保留。

完整交接另见 `.superpowers/sdd/2026-10-06-macos-runtime-port-allocation/task-2-report.md`。

## 最终所选本地闭包

完整37文件changed-set计划为L4，保留unknown_impact_boundary；受管内核11文件SHA全部匹配。
`logs/task-2-final-plan.json` 不运行测试或发布，以下是实际独立执行的结果：

- L0文档治理：543文件/79 current/零违规；Python索引生成和--check通过。
- L1 Python命名模块：service_manager、local_integrations、runtime_mode、docker_runtime、setup_web、
  cli_lazy、web_bootstrap、runtime_endpoints、control_origin：859 passed / 1 skipped / 58.29s，
  `logs/task-2-final-l1-python.log`。唯一skip是test_local_integrations.py的原生Windows检测，
  macOS未执行；另有Starlette anyio alias DeprecationWarning，负面路径warning/error日志如实保留。
- L1架构JS：63通过/2.047s；L2 Docker JS：12通过/0.120s。
- L2 Docker/supervisor/runtime_launch：287通过/35.60s，`logs/task-2-final-l2-python.log`。
- L3协议：19通过/0.11s，`logs/task-2-final-l3-protocol.log`。
- L4 JS完整所选四文件：91通过/2.038s，`logs/task-2-final-l4-js.log`。
- 最后setup参数验证/持锁guard权限修复后，安装与Docker整模块：231通过/22.47s，
  `logs/task-2-final-install-docker.log`；原锁和lease定点：29通过/0.35s，
  `logs/task-2-final-lock-regression.log`。guard mode篡改先有真实RED，再补strict检查。
- 同一私有数据根Native→Docker→Native控制文件往返：1通过/0.75s，
  `logs/task-2-roundtrip-fixture-final.log`。健康/外部runtime probe是fixture，不是真实服务验收。
- 候选健康后摘要写失败恢复原token/origin/endpoint/接受摘要：1通过/0.45s，
  `logs/task-2-installer-rollback.log`；Native发布后commit失败恢复与lease：2通过/0.54s。
- setup check-only Docker Runtime参数负例最初被capsys插件fixture错误阻塞，该错误不计RED；
  改用本模块既有StringIO后观察真实失败，再修复，最终安装整模块覆盖GREEN。
- 无site-package导入bootstrap、endpoint、lifecycle_lock、control_origin通过，未加载core.settings/store。
- black/ruff/isort/mypy在获准venv与PATH均不可用，NOT_RUN，未安装。

初次doc-sync指出3份owner文档缺项（REFERENCE、app_cli、scripts），已同步真实CLI/安装事务内容，
并按37文件重规划（另修复两处旧文档“尚未接入”陈述）。原失败保留于 `logs/task-2-final-doc-sync.log`；最终复核证据另存，未修改checker。
最终回执保存 `logs/task-2-receipt.json`，将所有5项所选CI标NOT_RUN，整体BLOCKED；Windows/Linux
门按现有计划保留，不归算为macOS已验收。真实macOS循环/UID/安装CI仍交回主任务。

末次自审补充RED/GREEN：新Docker启动不能把错误实际mapping当legacy认领；畸形controls必须
返回稳定code而不创建另一文件；Native status JSON需输出安全实际URL。最终Native/Docker整模块
472 passed / 13.86s（`logs/task-2-final-controls-lifecycle.log`），CLI整模块35 passed / 11.37s
（`logs/task-2-final-cli-url.log`）。这些修复不更改任务的NEEDS_WORK/BLOCKED结论。

## Task2 FIX ROUND1（7359157ce 上的五项 HIGH 修复）

Host macOS；功能开发；本轮只做隔离 fixture 和 Mac 本地证据。Mac 安装 CI/真实服务由主任务
接续；Windows/Linux 证据属于总体验收交接，不是本宿主任务前置。没有真实 Docker/image、
用户数据、Keychain、日常服务、全局设置、依赖安装、远端/Git发布或子代理操作。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"本轮修复失败尝试的清理顺序和发布CAS身份；沿用既有Native/Docker节点、生命周期锁与端点origin事务，不新增常驻节点。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"缺失账本改为核验监听者，控制首建先验证既有记录；复用原进程事实链和消费者接口，研究框架与协调器拓扑保持原合同。","diagrams":[]} -->

- `docker_runtime.py` 把真实 ControlOriginError 纳入失败清理；本次新建实例精确清理，本次启动的
  既有停止实例重核 ID/image/install/mount/launch 后仅 stop，证明停止后才恢复元数据。
- `service_manager.py` 在 creator 前只读校验既有两份 controls，MCP-only 动态 origin 可作为
  缺失 DataHub creator 输入；畸形 MCP 失败不留下 DataHub。缺失 ledger 仍检查监听者 argv/
  同数据根/进程事实；未知和同根 writer 拒绝分配，已证明的外来监听者可避让。
- `bootstrap.py` 的正常桥及无可用 venv 后备均不跳过既有数据根的占用监听风险。
- `setup_web.py` 接收原子写入 held-FD publication identity，回滚核对 exact bytes+identity，
  同内容不同 inode 保留并返回 `docker_install_summary_recovery_unverified`。
- 已读源文件、模块、设计和审查五项；没有扩大停止容器处置权限。既有停止容器改绑定仍是
  `docker_stopped_port_conflict`，待用户决定，不能称 Task2 完整完成。

实际 RED：`logs/task-2-fix1-red.log` 7 failed（origin 新建/既有两例、MCP-only 动态/畸形两例、
missing-ledger unknown/same-root 两例、manifest same-bytes replacement 一例）；
`logs/task-2-fix1-bridge-red.log` 1 failed（无 venv/账本但已有数据根监听）。实际 GREEN：
初始7 passed /2.42s；加 bridge 和 launch/image/install/mount 替换负例及摘要失败回归，
13 passed /1.99s（`logs/task-2-fix1-negative-green.log`）。
共享五模块闭包719 passed /51.38s（`logs/task-2-fix1-closure.log`）；后续边界变更后
protocol/runtime_endpoints/control_origin/docker_runtime/setup_web闭包334 passed /33.48s
（`logs/task-2-fix1-final-boundaries.log`）。JS所选完整闭包103 passed /3.521s
（`logs/task-2-fix1-js.log`）。文档治理543/79/零违规；首次生成索引 stale 后生成并复核通过。
首次 doc-sync 缺对应owner文档/本报告，已按实际边界补齐，不修改checker。
格式工具延续不可用 NOT_RUN；未安装。新 helper 和测试均留在原模块，没有新文件/公共API。

最终19文件L4计划 `logs/task-2-fix1-plan.json` 保留 validation_failure signal；共享内核11/11
SHA匹配。完整constraints首次缺README复核回执，按实际入口/限制复核后更新原回执，最终零违规
（`logs/task-2-fix1-constraints-final.log`）；doc-sync最终通过
（`logs/task-2-fix1-doc-sync-final.log`）。回执 `logs/task-2-fix1-receipt.json` 经原validator
认证 valid=true，10 local PASS/5 external NOT_RUN，BLOCKED，mergeReady/releaseReady=false。
这里是总体验收回执；foreign平台门由对应真机交接，不改变Mac宿主范围。未声称真实Mac或CI完成。

## Task2 FIX ROUND2（e21c7b5fe 的后备监听误拒修复）

独立复审批准fix1其余四HIGH，指出无Native环境时“数据根存在+端口忙”错误拒绝Docker-only
幂等start及无关宿主3081监听。本轮只修改bootstrap后备判断和closest Docker tests，复用
既有stdlib listener_pids/probe_process；不更改已批准的容器清理、controls首建或manifest CAS。
缺失Native环境+ledger时，对既有数据根核验alive PID、argv、启动身份并复查身份和监听集合；
未知/同数据根或当前checkout写者/身份变化拒绝，已证明外来监听允许继续。Docker仍独立核验
完整inspect/image/install/mount/mapping/health，错误mapping保留容器并拒绝。

实际RED `logs/task-2-fix2-red.log` 两例均runtime_ownership_unknown：真实8088监听下已验证
健康Docker容器复用；真实3081无关监听下Docker首启。NativeRuntime.status未被mock；真实端口
使用测试socket（空闲时）或保留当前已有监听，前后PID集合相同，没有停止既有68985/69730。
GREEN `logs/task-2-fix2-green.log` 六例/2.55s，额外保留unknown/same-root/PID-reused拒绝和
错误受管mapping负例。四模块docker_runtime/runtime_mode/web_bootstrap/setup_web共享闭包
407 passed /44.75s（`logs/task-2-fix2-boundary-closure.log`）。测试Docker inspect与健康是fixture，
真实socket/OS PID/argv事实不是mock；不构成真实Docker验收。后续mapping断言收紧为精确code。

本宿主macOS功能开发、本地隔离fixture；未执行真实服务/环境/镜像/用户数据/Keychain/全局
设置/依赖/远端/CI/子代理操作。真实验收由main持有，未改其detached checkout。
停止容器自动删除重建仍未授权，docker_stopped_port_conflict保持pending；MacCI/物理验收待主任务。

最终九文件L4计划 `logs/task-2-fix2-plan.json`；完整constraints和doc-sync PASS
（`logs/task-2-fix2-{constraints,doc-sync}.log`），索引生成后无diff且--check通过。
所选JS103 passed /2.752s（task-2-fix2-js.log）；protocol+最终六负例25 passed /1.88s
（task-2-fix2-final-smoke.log）。宿主Python -I -S导入bootstrap通过，无core.settings/Store导入。
回执task-2-fix2-receipt.json valid=true：8 local PASS/4 external NOT_RUN，BLOCKED，
mergeReady/releaseReady=false；foreign平台为全局交接，Mac物理/CI另由主任务负责。

## Task2 FIX ROUND3/5（efd1d37e 的产品写者数据根证明）

Review再次拒绝：其他checkout的uvicorn Web可通过RESEARCH_DATA_HOME使用当前数据根；稳定
PID/argv路径不同不证明不同数据根。直接依赖Native _absent_listener_safe/bind-race同样有洞；
显式新端口在缺Endpoint时还会漏旧默认8088/3081。parent明确批准在同HIGH内修复这些直接边界
和真正fresh-root一致性，不重开已批准的其他四HIGH。

源码仅bootstrap/service_manager及既有stdlib web_contract的共享纯predicate：可识别Web/DSH
无不同data-root证据时拒绝，不读取进程环境/配置/秘密、不新增探针框架；generic listener仍可
凭原进程事实证明不是产品写者。已有根缺Endpoint时观察选定端口与旧默认两端口，显式override
不能绕过。Native fresh仅本次verified lifecycle lease内成功mkdir并保留匹配inode，既有根/
替换根不认领；首个spawn前和start finally清除。其他controls/cleanup/manifest四HIGH源码未改。

实际RED：task-2-fix3-red.log 六failed/一passed；涵盖其他checkout+fixture共享env数据根、
显式新端口、bind retry、existing/replaced-root、无Native环境桥。fresh正例原本通过，保留。
额外task-2-fix3-default-bridge-red.log 一failed/一passed，证明桥显式端点漏旧默认。初GREEN7
/1.52s；原12失败闭包task-2-fix3-closure.log为12failed/828passed/46.21s，日志保留。
已将纯control/spawn事务fixture的监听事实明确隔离为closed，真实busy Web socket仍保留；
generic free-port Docker正例使用合法历史Native端点fixture+真实socket/OSPID，NativeRuntime.status
未mock；真实日常3081 DSH无数据根证明改为精确unknown拒绝并保持监听PID集合不变，未停止服务。
控制token往返仍是mock fixture，不冒充物理验收。stage32 passed/4.31s。

随后六模块闭包task-2-fix3-final-closure.log为2failed/839passed/46.07s，分别是stale/foreign
和temporaryHOME readonly旧预期；前者只补closed监听fixture，原foreign-before-stop负例不变，
后者在真实默认产品写者未知根时精确runtime_ownership_unknown，并继续断言HOME零写入。
两例定点task-2-fix3-readonly-green.log通过/1.02s，未削弱HIGH负例。

具体未闭合场景：正常setup --no-start/readonlyDoctor可能已创建canonical research-web/runtime
与buildlock；此根不是本次start创建，缺run/Endpoint时若8088/3081有其他checkout Web/DSH而
dataRoot不可证明，就真实返回runtime_ownership_unknown，显式其他端口也不逃逸。可由所属安装
明确授权后正常stop，或另验由startup创建的全新独立dataRoot；不删除/移动canonical根制造fresh。
后者不替代canonical同根Native/Docker往返、默认安装→自动start组合或MacCI，均须main分别留证。
停止容器删除重建/HTTPSsource仍未授权，pending保留。main拥有新增Task3验收报告，本提交不含它。

最后受影响源码闭包 service_manager/docker_runtime/runtime_mode/web_contract/protocol：682 passed
/24.48s（task-2-fix3-verified-closure.log）；当前源码此前setup_web/web_bootstrap模块的通过结果
保留在839passed阶段日志，不把该阶段的两failed改写为PASS。JS所选103 passed /3.124s；完整
20文件constraints/doc-sync/生成索引PASS；stdlib -I -S bootstrap导入不加载core.settings/Store；
managed kernel11/11 SHA匹配。L4计划保留validation_failure与unknown_impact_boundary。
回执task-2-fix3-receipt.json valid=true，9 local PASS/5 external NOT_RUN，整体BLOCKED，
mergeReady/releaseReady=false；未执行Mac物理/CI及其他平台门，源修复仍需独立复审。
Fresh capability只用于public start首次分配，不在constructor/readonly/stop/restart或失败重试认领。

## Task2 FIX ROUND4/5（dd9fec819 的 fresh 失败事务恢复）

Review指出首次spawn前清除fresh分配证明后，失败回滚又被旧默认未知产品监听阻断，留下新
origin/journal并掩盖原错误。只修本HIGH；上轮产品predicate、显式legacy观察及其他四HIGH
保留，未修改Docker/controller/controls/manifest实现。现将首次分配与本次事务恢复证明分开：
持有效fresh证明时捕获RAM-only原lease/根inode、选定+legacy监听集合与PID/argv/启动身份，
已观察身份不刷新；spawn前分配证明仍清除。恢复必须持续同一已验证lease/根、原监听事实
一致、所有本次PIDs精确消失。新增/未知writer、root/lease/listener/PID身份变化或活着的own
对象均拒绝。恢复证明只用于此事务CAS/origin回滚，不用于新分配/重试，finally清除。

PIDs在Popen后、state写入/健康等待前保留，内部cleanup不清空attempt；已证明退出的不重复
停止。未知恢复保留原始startup错误，附加稳定recovery_issues/异常note/日志，保留intent；
带恢复诊断的bind错误也不得重试。清理所有对象时每个失败单独记录固定code，不输出argv或秘密。

真正RED task-2-fix4-red.log：九failed（fresh+旧产品监听+health失败；root/listener/PID-start/
unknown/new writer/live own/lease七负例；failed-wait PID记录）。GREEN9 /0.75s。额外retry真实
RED1（task-2-fix4-retry-red.log）后最终10passed /0.62s。控制原字节/无journal/主错误保留
正例和负例都保留；测试安装ready/OS事实/子进程为隔离fixture，不是公开CLI/实机服务验收。
共享闭包首次1failed/628passed/26.16s（task-2-fix4-closure.log），发现内外层重复cleanup；
source跳过已证明missing的对象，pure fixture准确模拟已退出，旧“仅新对象stop一次”断言不变。
定点11passed /1.25s（task-2-fix4-cleanup-green.log）。次轮1failed/629passed/25.21s
（task-2-fix4-final-closure.log）：未改Docker三次bind预算在第三次read出现runtime_mode_changed，
单独复核1passed /0.20s；原失败保留，尚不认证根因，不将其改写为通过。

main补充公开可达性缺项：真实start在mkdir前要求installation-ready，build-lock一般已存在于
canonical data_root/runtime；“不存在customRoot可直接rwb start”尚未获得公开入口证明。
本轮组件fixture明确mock installation-ready，不能代表公开fresh实测。该独立缺口留作
NEEDS_CONTEXT（核对现成公开入口/真正installer创建witness），不混入本HIGH，不复制buildlock、
移动root或改daily环境/服务让验收变绿。main T3报告仍归main，未纳入提交。
停止容器删除重建、HTTPSsource权限仍pending；Mac物理/CI及跨平台交接未执行。

最后相同源共享closure真实630 passed /24.48s（task-2-fix4-verified-closure.log），包含原Docker
budget case；旧失败及交互原因未确认保留。恢复捕获再收紧为复核全部已捕获端口（含已不再
选用的preferred端口），最终service_manager整模块338 passed（task-2-fix4-final-service.log）。
所选JS91 passed、14文件doc-sync/constraints/index PASS；不修改checker。公开fresh可达性
须独立只读核对，不能把mock安装就绪的组件GREEN当作物理或公开入口证据。

最终service_manager338 passed /6.35s；14文件L4计划保留validation_failure，文档同步/约束/
索引/无site bootstrap导入PASS，managed kernel11/11匹配。回执task-2-fix4-receipt.json经原
validator valid=true，7 local PASS/4 external NOT_RUN，BLOCKED，mergeReady/releaseReady=false。
保留“公开fresh路径可达性需上下文”和“早前runtime_mode_changed交互未认证”风险，未执行
物理Mac/CI或修改其门；格式工具仍NOT_RUN且未安装。Task3报告保持main所有权。

## Task2 FIX ROUND5/5（24bb6df8d 的公开 Native fresh 可达性）

R4review已APPROVED。parent批准本目标内的最小衔接：正常Native auto-start在真实manager
LifecycleLock内实际创建canonical根，保留内存witness至DSH/runtime/build-lock/manifest与
安装就绪门，再借同一actual lease启动；bool/tuple不是lease，root/lease/old listener变化拒绝。
no-start保持原流程且结束后无fresh，既有根重装不认领。恢复复用R4，不序列化证明或新增flags。
脚本把原outer-home UID/0700校验提取前移，避免txn parents mkdir0755被真实lease拒绝；
canonical根仍只由scope实际创建。manager接口仅yield实际lease和两个private installer入口。

干净host导入manager曾只读观察到pydantic缺失：verify_web_import仅venv子进程，不改变host
依赖。parent独立批准公开main重执行方案：仅Native真正auto-start先按原prepare_environment
建立/复用标记owned `.venv`，校验精确executor/marker，用其Python -I执行同脚本原args；
精确sys.prefix+已有marker防重复，repair参数与原healthy-reuse/owned-broken/unknown拒绝规则
保留。HOME/Node/代理/测试credential-root保持，不改global包/sitepath，不新增private stage协议。
check-only/Docker/no-start仍hoststdlib路径，不在reexec前建canonical根或持proof。

实际RED task-2-fix5-valid-red.log六failed/一no-startPASS：DSH/buildlock前无真实scope。
最初task-2-fix5-red.log的no-start因不完整closure fixture失败不计行为RED，按固定closure计数
和manifest必需字段补全后得到上述真实RED。首GREEN六/一fail暴露outer-home0755，按原边界
前移准备后七PASS/1.15s。公开main hostexecutor/unknownmarker真正RED二failed/四PASS
（task-2-fix5-entry-red.log），实现后13PASS/1.00s；加bool/tuple/None伪lease拒绝和精确code/
失败origin恢复后16PASS/1.48s（task-2-fix5-final-focused.log）。真实lease、mkdir、marker、
buildlock/manifest原子写使用临时文件；deps/DSH网络/installation事实/子进程健康是明确fixture，
不代表干净宿主重exec或公开完整installer实机验收。legacy JSON输出seam仅模拟已在owned运行时。

共享七模块setup/service/Docker/mode/bootstrap/origin/protocol：824 passed/45.06s
（task-2-fix5-closure.log）。现有no-start/lease/privacy/unknown/alias/replacement/failure/旧Native
负例保留，未改其他HIGH source。main将在全新专属HOME从正常完整installer实测此入口；
不清空/移动既有canonical根、不复制buildlock、不让no-start跨调用继承fresh。无实际安装、
service/全局config/credentials/remote/新包动作由此agent执行，main Task3报告不提交。
停止容器处置与HTTPSsource仍未授权，不实现；物理Mac/CI、其他平台交接待main独立留证。

最后同scope自审补existing unknown-before-provision真实RED1/7PASS，before-provision复用
原Native事实预检，owned healthy仍按原归属复用；加该正例后17定点PASS/1.89s。root/lease/
observer一致性在DSH返回、写buildlock前等边界重复验证，替换root/变化listener不会留下新
build-lock，existing一致性inode不授fresh。最终定点17PASS/1.63s。其他模式静止也复用原
_other_runtime_quiescent，未修改Docker网络/environment。公开完整物理验收仍属main。

最终相同源码七模块825 passed /37.30s（task-2-fix5-final-closure.log）。18文件L4计划保留
validation_failure；所选JS91 passed /2.641s、doc-sync/constraints/index PASS，11/11共享
kernel SHA匹配。系统Python -I -S导入setup_web不加载manager/pydantic/core.settings，host
分支保持stdlib；实际重exec仍由main在新HOME验证。回执task-2-fix5-receipt.json valid=true，
8 local PASS/4 external NOT_RUN，BLOCKED、mergeReady/releaseReady=false，不宣称完整产品交付。
下步main独立review package与真实installer/健康/旧实例保持证据，格式工具仍NOT_RUN未安装。
