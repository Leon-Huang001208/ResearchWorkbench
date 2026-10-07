# Docker fresh-root transaction

hostPlatform=macos；taskKind=Web 功能修复；hostAcceptance=BLOCKED（本地源码验收与物理/CI 分开）；aggregateAcceptance=BLOCKED。Windows/Linux 适配与真机/CI NOT_RUN，Docker 物理操作由主任务负责。本任务未执行 Docker、产品服务、依赖安装、远端操作或全局配置，未修改 primary、旧功能分支、managed feature、主任务 HOME/checkouts 或三个历史报告。

基线 e6f282eaf：修复 valid Native 环境存在时，全新私有 HOME 的 Docker no-start 被默认其他产品监听阻断的事务缺口。批准方案采用 controller 外层实际 lifecycle lease 下的调用内 ExitStack：缺失观察与真实 mkdir/根 FD 的权限分离，up 前失去分配权限，失败恢复仅保留严格本次观察。不序列化、不迁移、不删除产品根以假造 fresh。普通已有根/未知 writer 严格拒绝及原 bind-race 路径保留。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Repairs the existing Docker controller and installer lifecycle transaction with retained parent/root descriptors and call-local witnesses; no deployment nodes, persistent schema or Native authentication component change.","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The existing single DSH and Web topology and authentication implementation are byte-identical; only host installation/first-creation authority changes inside the current lifecycle boundary.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Updates existing authoritative installation/runtime/data/security modules and records evidence, without adding competing workflow or documentation authority.","diagrams":[]} -->

实际 RED（生产修改前）：`logs/docker-fresh-root/red.log` 2 failed、94 deselected，2.26s，原因均为原 runtime_stop_current_required。Fixture 的 installer-marker/classification 通过真实 validator，执行真实 NativeRuntime 子进程桥；测试自有 socket 子进程提供真实 PID/argv/start 事实，观察端口为临时端口。它是分类/桥/事务 unit fixture，不代表真实 Native 安装或实际 8088/3081/镜像生命周期；没有把 Native.status mock 为 idle。实际 default-port/valid Native checkout 的产品复现归主任务。

初步正向 2 passed，8.92s；hostile/transfer 19 passed，36.60s。首次 core 353 passed、19 failed，105.83s：既有容器 fixture 缺少实际 bind 数据根，现显式建私有根并为健康/浏览器用例使用原 EndpointStore 的已停止 Native 端点 fixture；不提供 fresh 权限、不改变原断言。一个环境失败由测试命令 PATH 排除 Docker 时同时排除了 Node 引起，恢复原 PATH；setup 测试增加实际 Docker Popen 拒绝边界，缺失 fake 不接触真实 Engine。后续 setup catalog 112 passed，48.32s；保留路径 26 passed 后健康/浏览器 4 passed，0.91s。

晚期恢复 RED：6 failed、1 passed，38.68s，证明旧 recovery 覆盖原发布错误。Root/lease/PID/listener/mode/container 改变时不恢复未知内容，fresh 调用保留原错误并加稳定 note/related issue；普通原路径保留原恢复语义。后续 6 passed、1 fixture failure，36.15s：mode 负面 fixture 错误重入已持元数据锁；改为未知私有文件替换，定点 1 passed，5.03s。此测试不伪造可接受 manifest/PID 或 fresh 标记。

完整 changed set 为 14 个拥有路径，11 个受管 kernel manifest SHA PASS；计划为 L4，保留 unexpected_behavior/validation_failure。文档门首次仅缺 scripts/ 既有 owner 文档，按主任务授权只修正 docs/modules/scripts.md 的 setup_web 边界并添加 bounded Docker 说明；无策略/路由扩展。

最终冻结生产源码的相关 Python 命令：`PYTHONPATH=. /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest --confcutdir=tests/research_web -q`，指定 `tests/research_web/` 下 `test_setup_web.py test_docker_runtime.py test_runtime_mode.py test_protocol.py test_runtime_endpoints.py test_control_origin.py`；536 passed，146.43s，`logs/docker-fresh-root/python-final-source.log`。此前扩展闭包另含 `test_web_bootstrap.py test_web_contract.py test_cli_lazy.py test_container_supervisor.py test_runtime_launch.py test_runtime_auth.py test_runtime_contract.py`，1078 passed，179.20s，`python-closure.log`；该快照发生在最后的提前拒绝 unknown control directory 五行检查前，不冒充最终全套结果，改变组件已按最终源重跑。

`node --test` 指定 `tests/javascript/` 下 Docker runtime contract、research web architecture、documentation governance、actions quota governance、repository cross-platform contract 五模块，105 passed，2.6640015s，`logs/docker-fresh-root/js-closure.log`。完整 changed-set `check_doc_sync.py` 组合 governance/architecture/generated index PASS（1.280544s）；Project Constraints PASS（0.090530917s），`doc-gates-final.log`。Index 无 diff；py_compile 与 git diff --check PASS。

`logs/docker-fresh-root/plan.json` 与 `receipt.json` 的现有 schema-v3/v2 validator 实际退出 0：9 local PASS、4 external NOT_RUN、valid=true、result BLOCKED、mergeReady/releaseReady false。各 gate 复用对应真实组合命令总时长，不是单 gate 独立计时，不能求和。旧 785/203 不冒充本源结果；不能以模拟 Engine 或实际 OS 临时 listener 冒充真实 Docker 首装/临时 guest 通过。

源字节边界：生产仅 `research_workbench_entrypoint/docker_runtime.py` 与 `scripts/setup_web.py`；app/research_web、Native bootstrap、runtime_mode/web_contract、通用 runtime_state/lifecycle guard、Dockerfile/Compose、依赖、CI、policy/kernel 与 merged master auth unit 相对 e6f282eaf 无 diff。源/测试四文件 binary diff SHA-256 `821f153cb8fe45abed69d78d864715fc2ec0a8214062fc9075f88ec48dbb939a`。本实现命令只在新隔离 worktree 写入；primary HEAD 1dbd7547f1c6062124ab3a7f1fbd4498058f38fa 与旧功能 worktree HEAD dfd68e0d5f103852b825ee067a6913da00646088 只读复核，无修改。

风险与交接：已有根在未知 Native/default writer 状态下仍严格拒绝，不能借本次成功获得未来 fresh 权限；新根失败保留，重试需正常已有根证据而非删除数据。真实新 HOME public no-start/install/start、原端口观察及后续双模式行为由主任务评审后对不可变提交实测。本任务 hostAcceptance/aggregateAcceptance 仍 BLOCKED 外部门/物理层，不宣称跨平台支持。

正式 spec/Python/security 评审无 Critical/Important，追加精确边界说明：mkdir→首次 open/fstat 捕获非原子，沿用 Native/Supervisor 模型；拒绝目录替换的声明从首次 inode 捕获后成立，不承诺防同 UID、可写 HOME 且不遵守 lease 的任意捕获前替换。mode witness 沿用 RuntimeModeRecord 值/逻辑 CAS；同内容换 inode 本身不必使跨读取的证明失效。安装摘要的既有 FD/字节恢复检查是另一边界，不受本说明改变。该补充仅为文档，代码/测试与 f5cf1b9cb 字节相同，不重写上述历史证据或扩大原语调查；本 doc changed set 的门和回执另存 `logs/docker-fresh-root/review-boundary-*`。
四文档 changed set 的 L0 governance/index、既有架构/doc-sync/Project Constraints 与 diff 检查 PASS；doc-only schema-v2 receipt validator 退出 0、valid=true、2 local PASS、无外部门。该 doc-only PASS 不覆盖前述源码任务的 L4/真实 Docker/CI BLOCKED；没有重跑或重新归属源码测试结果。
