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
