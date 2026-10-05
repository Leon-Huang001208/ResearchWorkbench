# Native / Docker 双运行时：Task 12 文档与架构回执

## 范围

本任务只更新当前产品入口、安装/运行说明、架构清单、部署图及文档契约测试；Task 1–11 的实现、隔离分支和审查证据保留。没有安装依赖或运行时，没有修改全局 Hook、manifest、插件缓存和信任配置，也没有推送或发布。

README 把 Docker 列为新安装推荐入口，同时明确 `--runtime` 无参数继续选择 Native。安装指南分开记录模式切换、共用研究数据、分离状态/凭据、稳定 issue code、修复与非破坏性卸载。Windows `.cmd` 是接口说明，不是实机 Docker 生命周期验收。

## 文档契约与部署图

先增加两项文档/架构契约测试，再运行 RED：`node --test tests/javascript/documentation_governance.test.mjs tests/javascript/research_web_architecture.test.mjs`，71 项中 69 通过，两个新断言按预期失败（README 缺双运行时入口；map 缺新的运行合同）。文档和图源更新后同一套测试通过 71/71。

`01-deployment` 图源显示一个源码/锁定依赖合同、Native Web/DSH 两宿主进程、Docker 单容器、顺序共用研究数据及分离凭据/状态。Archify showcase validate 9/9、0 error、0 warning；deliver 图源 SHA-256 为 `94c6eaa9a365b3fee1d7a481742f21d0dd4c962311f18721e1118ae990c10def`，HTML 为 `400f75c7067b30c1fc5d284b65461787234a8071d45446cd8a2594e666cdd0c9`。首次受限环境的 visual-check 因 Chrome 在测量前退出而失败；对同一命令获窄范围许可后四视口包含性、明暗截图均通过。人工查看最终哈希的 1440 浅色与 2048 深色截图，未见遮挡、节点穿线或裁剪；图形不证明产品或 Docker 真实生命周期。

## Task 12 本地门禁

| 实际命令/范围 | 结果 |
| --- | --- |
| `node scripts/check_documentation_governance.mjs --project .` | 515 份 Markdown，0 violation |
| `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs` | 83/83 通过 |
| `/opt/homebrew/bin/python3.12 scripts/generate_py_file_index.py --check` | 生成索引已校验 |
| `node .agents/project-constraints.mjs`，传入 Git 对 HEAD 的全部 25 个本轮已改/新增文件 | 0 violation |
| `git diff --check` | 通过 |

任务书中仅传 `README.md`、安装文档、`Dockerfile`、`process_spec.py` 的示例命令并非完整 changed set，按门禁设计会因未列入已更新的 README receipt、模块文档和架构报告而报 7 项 `not_changed`/`review_invalid`；这不是文件内容失败。改用实际 25 文件集合后为 0 violation。只读规划器对此 25 文件集合给出 L4，因为 HTML/截图回执和两个测试路径在现有策略中归类 `unknown_path`；其本地 L0 与 L4 命令如上已执行，外部 `project-constraints` 尚未运行。Task 13 将基于原目标的完整分支 changed set 另行规划，不把本轮局部结果冒充整体验收。

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"新增模式路由、固定运行合同与 Docker 单容器部署，改变部署拓扑及数据/状态/凭据边界。","diagrams":["01-deployment"]} -->

## 未验证与后续门

- 本任务没有运行真实 Native/Docker 安装、镜像构建、服务切换、Windows 或外部 CI；不得据此宣称平台通过。Task 13/14 按完整 changed set 与实际授权单独执行必要验收和外部门。
- Docker 真实镜像构建此前受外部 APT 网络失败阻断；当前 Windows Docker 凭据 ACL 无可证安全路径时以 `docker_credentials_acl_unverified` 失败关闭。
- 本轮只读诊断确认 Harness runtime 后来已一致，但**更新执行者未知**；没有证据证明自动修复，本任务不追查更新者，除非再次出现异常写入或漂移。

## Task 13 分支级验收状态

当前计划以基线 `4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7`、Docker bind 首建修复/物理阻断报告 HEAD `8fbecabb384ff48ac91891642e98da3f749db461` 的 105 个已提交差异路径，加未提交的本任务 plan/receipt 两份 JSON，共 107 个交付路径。原 `.ai` Markdown 报告已包含在提交差异中；ignored `.superpowers` scratch 报告未计入。规划器判定 `full-delivery / L4`，18 项本地验证、4 项外部门，并保留 `validation_failure` 与 `unexpected_behavior` 两次升级信号。计划和机器回执为同名前缀 `-plan.json`、`-receipt.json`；完整 stdout 在本机 `/private/tmp`，逐项归因与生命周期详情见 `.superpowers/sdd/2026-09-29-native-docker-dual-runtime/task-13-report.md`。

修复前的本地失败、环境权限差异及 85/104/105/106 路径中间规划均保留在原始日志。当前 18 项所选本地门全部有通过证据：runtime contract、API、本机集成复用 Task14 `ff941a56` 的合并测试；installation 复用 `e043a497` 修复者的 controller+setup 合并测试；runtime-mode 原双模块命令在 `e043a497` 补验。bind 首建影响的 container-runtime 在 `8fbecabb` 补验 122/122，其余无改动测试按来源复用。完整 107 路径 Project Constraints 为 0 violation；文档治理检查 521 份 Markdown、0 violation。四个外部门未运行，机器回执仍为 `blocked`；真实 Native 干净安装受 DSH clone 超时阻断，Docker Goal image 容器生命周期未运行，目标机新 helper 首建探测被 Hook 拒绝。

主代理在隔离测试 home 以 `eeb530c8…` 源码运行 Native 公共入口：首次锁定依赖/CJPY 安装成功，DSH 网络 clone 超时；复用当前校验通过的固定 DSH 后，setup、start、status/doctor、restart、stop、再 start、拒绝未构建 Docker 切换且保留 Native 健康、最终 stop 与双端口释放均有真实日志 `logs/task13/native13*.log`。研究 fixture SHA-256 `ab2c660b144e3fcaee356695c4b9f30444cdbe34bb4e67d8b21c4e10566fbc62` 前后一致。该验证使用隔离文件凭据后端，未证明默认宿主 Keychain；修复提交后需复验受影响 Native 行为。Docker `--check-only` 通过，但 APT Packages 获取失败，未构建/运行容器；`logs/task13/docker-apt-check.log` 保留原失败。

`ff941a56` 源码导出的独立测试 home 后续又执行 Native 公共入口：setup 7.26s、start 9.41s（Runtime/Web PID 38457/39549）、status JSON 0.44s 与 doctor 2.56s 均 `ok=true`；`/api/research/runtime` 报 `connected=true`、`health_check_passed=true`，但 `credential_configured=false`，天软 `configured=false/callable=false`。restart 8.80s 后新 PID 为 64071/64086。原始回执 `logs/task13/native13post*.log`。读取 logs/stop 前，这两 PID 已退出，8088/3081 分别由非测试实例 PID 69730/68985 监听；只读路径/归属核验见 `logs/task13/native13lateaudit.log`，`rwb web logs` 安全拒绝 `native_logs_ownership_unknown`，stop 仅清理测试的陈旧状态，未终止外部实例。不能把当前默认端口说成已释放，或说这次修复后完成 stop→再次 start；旧 `eeb530c8` 的完整 stop/restart 与 fixture SHA 回执保留为旧源码证据。后续受外部实例占用约束，未触碰对方服务。
本地 L0→L4 实测回执（完整 stdout 留在本机 `/private/tmp`；复用项标明修复者来源）：

| 层级 | validation ID | 结果 | 秒 | 日志 |
| --- | --- | --- | ---: | --- |
| L0 | documentation-governance | passed | 1.503 | `/private/tmp/rwb-task13-documentation-governance-8fbecab.log` |
| L0 | python-file-index | passed | 2.633 | `/private/tmp/rwb-task13-python-file-index-8fbecab.log` |
| L1 | verification-policy-contracts | passed | 4.918 | `/private/tmp/rwb-task13-verification-policy-contracts-95180d.log` |
| L1 | verification-receipt-contracts | passed | 2.650 | `/private/tmp/rwb-task13-verification-receipt-contracts-95180d.log` |
| L1 | incremental-validation-skill-contracts | passed | 1.466 | `/private/tmp/rwb-task13-incremental-validation-skill-contracts-8fbecab.log` |
| L1 | research-web-architecture | passed | 3.833 | `/private/tmp/rwb-task13-research-web-architecture-8fbecab.log` |
| L1 | research-web-local-integrations | passed (复用) | 233.400 | `/private/tmp/rwb-task14-api-integrations-1.log` |
| L1 | research-web-runtime-contract | passed (复用) | 39.700 | `/private/tmp/rwb-task14-final-repair-closure.log` |
| L1 | research-web-installation | passed (复用) | 13.180 | `/private/tmp/rwb-task14-up-rollback-final.log` |
| L1 | research-web-api | passed (复用) | 233.400 | `/private/tmp/rwb-task14-api-integrations-1.log` |
| L1 | research-web-service-manager | passed | 2.236 | `/private/tmp/rwb-task13-research-web-service-manager-ff941.log` |
| L1 | research-web-runtime-mode | passed | 20.007 | `/private/tmp/rwb-task13-research-web-runtime-mode-e043a49.log` |
| L2 | research-web-docker-contract | passed | 1.552 | `/private/tmp/rwb-task13-research-web-docker-contract-e043a49.log` |
| L2 | research-web-container-runtime | passed | 26.483 | `/private/tmp/rwb-task13-research-web-container-runtime-8fbecab.log` |
| L2 | project-constraints-local | passed | 1.599 | `/private/tmp/rwb-task13-project-constraints-local-8fbecab.log` |
| L2 | research-web-credential-backend | passed | 2.886 | `/private/tmp/rwb-task13-research-web-credential-backend-11cdbcc.log` |
| L3 | research-web-critical-smoke | passed | 2.140 | `/private/tmp/rwb-task13-research-web-critical-smoke-95180d.log` |
| L4 | research-web-verification-full | passed | 3.666 | `/private/tmp/rwb-task13-research-web-verification-full-8fbecab.log` |

原始失败和权限差异复测分别保留：`/private/tmp/rwb-task13-research-web-local-integrations.log` 为系统 Python 缺 pytest；`/private/tmp/rwb-task13-research-web-local-integrations-2.log` 为现有 venv 下的 2 失败；`/private/tmp/rwb-task13-research-web-installation-escalated.log`、`/private/tmp/rwb-task13-research-web-runtime-mode-escalated.log`、`/private/tmp/rwb-task13-research-web-container-runtime-escalated.log` 为同命令窄范围复测通过证据。

### 修复者证据复用与当前 HEAD 补验

Task14 修复者在 `ff941a56fe9d115745eafeb0d22f051a19f4559d` 运行四模块合并测试，297 passed / 39.70s，日志 `/private/tmp/rwb-task14-final-repair-closure.log`；其中 `test_runtime_contract.py` 覆盖 `research-web-runtime-contract`。API 与本机集成两模块合并测试 78 passed、1 skipped / 233.40s，日志 `/private/tmp/rwb-task14-api-integrations-1.log`，覆盖 `research-web-api` 和 `research-web-local-integrations`。这些是修复者执行证据，Task13 没有重跑 233 秒的 API 门。

Compose 回滚修复者在 `e043a497529dd8fd710802249d118a931cc218b0` 对 `test_docker_runtime.py` 与 `test_setup_web.py` 的合并测试为 199 passed / 13.18s，日志 `/private/tmp/rwb-task14-up-rollback-final.log`，覆盖选中的 `research-web-installation`。Task13 执行者在同一 HEAD 跑原 `research-web-runtime-mode` 双模块命令 195/195（`/private/tmp/rwb-task13-research-web-runtime-mode-e043a49.log`）；不能把修复者的 199 项测试冒称为 Task13 执行。

从 `ff941a56` 到当前 HEAD，`git diff --name-only` 对 `test_runtime_contract.py`、`test_setup_web.py`、`test_cli_lazy.py`、`test_api.py`、`test_local_integrations.py`、`app/research_web/runtime_contract.py`、`app/research_web/service.py`、`scripts/setup_web.py` 与 `app/cli/main.py` 为零路径；这些复用输入未变。`test_runtime_contract.py`、`test_setup_web.py`、`test_api.py`、`test_local_integrations.py` 的 SHA-256 分别为 `994434292f479780019cab6fc26e5874ef3f8b4b3eff13fd0e40e759d1d99cc1`、`ed18f516cb7d05cc1f119419c0567b8af970a7dbb3edc08883bbc354fc7a4c75`、`2ac831013cbc504dd8f145db68ed9f954114a258e64b7e305296a834a228e1cb`、`7bfc7fcf2fcb78e1c273de7198f5319d31b02776d26d316f2be83756e1f9078d`。Docker controller 测试在 `e043a497` 已更新，因此 runtime-mode 使用新 HEAD 实测。

Task13 另在 `ff941a56` 补验 service-manager 110/110，在 `11cdbcc` 补验 credential-backend 58/58；该凭据门源码/测试在此后未变。首建修复 HEAD `8fbecabb` 的 container-runtime 原双模块命令 122/122 通过。Docker JS 合同 10/10、架构 63/63、L4 Node 83/83、skill 5/5、文档治理 521/0、Python 索引和完整 107 路径 Project Constraints 0 violation 均已实跑。完整 stdout、执行者与耗时见上表；共用命令的 39.70s、13.18s、233.40s 不可按 gate 重复相加为独立耗时。

当前 107 路径机器回执的 18 项本地门均为 passed，4 项远端 gate 为 `not_run`；`validate_verification_receipt.mjs` 结构校验为 `valid=true, result=blocked, executedCount=18`。此状态不证明 Docker Goal image 构建、健康、持久化或远端 CI。

### 物理挂载发现与回滚边界

主代理在目标机做实际 Docker Desktop bind mount 探测时，宿主挂载根在容器内表现为 UID 0（宿主 UID 501、mode 0700），而运行用户为 UID 10001；直接将该根当作 runtime state 触发真实 `runtime_state_unsafe`。由容器用户在挂载下自建 mode 0700 的 UID 10001 子目录，换新容器后持久化与现有私有目录校验仍通过。该探测只定位 Docker state/credentials leaf 布局问题，不是 Goal image 的 build、startup 或健康通过证据。窄修已提交至 `11cdbcc25f36427ac7a0c57a93166cbe2157b908`，保留 UID/ACL 强校验与 canonical 数据边界；本计划追加 `unexpected_behavior` signal（仍 L4）。修复后的真实 Docker Desktop 私有叶及 Goal image 生命周期结果仍待主代理物理回执。

随后 scoped 复审另发现独立 P2：Compose `up` 创建候选容器后若返回非零或超时，controller 未记录新容器 ID 并执行精确回滚，可能阻碍离线 repair 的旧 image 恢复。主代理窄复现后，controller 与对应测试/文档修复已提交至 `e043a497529dd8fd710802249d118a931cc218b0`；Task13 在新 HEAD 补验 runtime-mode 195/195、完整 106 路径约束 0 violation。模拟 runner 与单元测试证明代码路径，真实 Docker Engine 的故障注入/回滚仍未执行，故回执保留 `docker_compose_up_rollback_physical_validation_pending` 风险，不能据此宣称平台验收通过。

在真实 Python-stage base 的 Docker Desktop bind 探测中，首个容器创建私有凭据叶曾失败：`logs/task13/docker13createidentity.log` 记录同一 bind 父目录（dev 46、ino 4、mode 0700）在 `mkdir` 前后 UID/GID 从 0:0 转为 10001:10001，原 `runtime_state_directory` 因父目录身份变化拒绝为 `runtime_state_unsafe`。`logs/task13/docker13backendwrite.log` 是首次写入失败；`logs/task13/docker13backendpersist.log` 的 `persisted_readback_matches=false`，没有持久化成功证据。Docker-only 安全创建窄修已提交至 `32f4246f1a739ef3d355938da9237282379071df`，未放宽原 no-follow、FD、UID 验证；源码和对抗测试通过。主代理随后尝试在目标机执行新 helper 三目录的真实首建命令，PreToolUse Hook 拒绝该工具调用，命令未执行（`blocked_by_hook`，`logs/task13/docker-final-first-create-hook-block.log`）；未改 Hook、未换路线。故修复后首次写入、二容器持久化读回仍未认证，回执继续 `blocked`，也不把 base 镜像探测称为 Goal image 启动。

最终 scoped 复审 `.superpowers/sdd/2026-09-29-native-docker-dual-runtime/final-scoped.md` 对上一轮 Compose up P2 记为已处理，对新 helper 未发现新的 P1/P2；这是限定代码范围的结论，未复审全分支，整体 `ready-to-merge=false`。Goal image/APT、真实私有叶首建与凭据持久化、Windows 实机、四个本分支远端 CI 均保留为未完成。主代理最后只读 integration 预览相对当前远端基准 `4048c35` 发现 14 个冲突文件；没有合并权限，也未执行 merge 或集成验证。研究 fixture SHA-256 复核仍为 `ab2c660b144e3fcaee356695c4b9f30444cdbe34bb4e67d8b21c4e10566fbc62`。
