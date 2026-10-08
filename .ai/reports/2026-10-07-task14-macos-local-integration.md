# Task14 macOS 本地集成

宿主为 macOS；任务为既有 Native/Docker Web 功能的本地集成。基线 master
`ddcdd9784d8eda2918b8987ca8b679375e67291d`，待合入 feature
`dfd68e0d5f103852b825ee067a6913da00646088`。只在指定受管 feature worktree
解析冲突，不执行远端发布、CI、安装、真实服务、Docker 或 controller prepare。

## 结构决策

- 保留主线模型设置、隐私和 Node preload 私有认证交接完整单元；临时 bootstrap token
  绑定 authority、cwd 与固定 source commit，Docker supervisor 额外绑定 child PID，
  由既有 Cookie 交换消费。Native 的上游读取器未新增 PID 校验。
- 保留 Native/Docker 自动宿主端口、私有 EndpointStore CAS、共享 lifecycle lease、
  成对 control origin 事务及 token/额外字段保存；容器内部端口仍固定 8088/3081。
- 保留 Docker state tmpfs、独立 logs bind、严格 runtime_state guard、固定叶首建映射和
  prepare-controls-only 路径；主线认证测试与 feature 私有状态测试共同保留。
- research-tools 同时保留显式第三参数测试执行器和自有 data descriptor 替身；
  不读取未声明 Cordis getter 或 accessor。
- 两侧架构和产品文档合并维护；保留 master AGENTS 的当前阶段与平台证据归属。
  本报告不把旧报告的测试或物理验收冒充本次合并后的验证。

## 验证与未验证

共享 kernel manifest 的 11 个文件逐一 SHA-256 校验通过。当前基线到工作树完整 changed set
为 75 个路径（包含本报告，全部冲突、自动合并、生成文件及历史报告）；规划器选择 L4。
`logs/task14-local-plan.json` 保存实际 schema-v3 计划，`logs/task14-records.json` 保存各命令、
退出码、毫秒耗时和独立日志路径。15 项必需本地验证按 L0→L4 实际执行且均 PASS：

| 检查 | 实际结果 | 耗时（秒） |
| --- | --- | --- |
| documentation-governance | PASS，581 Markdown / 81 current / 0 violations | 0.140 |
| python-file-index | PASS，生成索引一致 | 1.034 |
| verification-policy-contracts | 72 JS PASS | 4.553 |
| verification-receipt-contracts | 23 JS PASS | 1.976 |
| incremental-validation-skill-contracts | 5 JS PASS | 0.081 |
| research-web-architecture | 63 JS PASS | 2.265 |
| research-web-service-manager | 342 Python PASS | 5.928 |
| research-web-local-integrations | 45 PASS / 1 SKIPPED / 1 warning | 20.580 |
| research-web-runtime-mode | 322 Python PASS | 21.109 |
| research-web-installation | 94 Python PASS | 12.366 |
| research-web-docker-contract | 14 JS PASS | 0.298 |
| research-web-container-runtime | 213 Python PASS，包含真实 fixture 子进程认证与清理 | 29.700 |
| project-constraints-local | PASS，完整 75 路径 | 0.169 |
| research-web-critical-smoke | 20 Python PASS | 0.715 |
| research-web-verification-full | 91 JS PASS（包含已列架构测试，不能重复算独立证据） | 2.370 |

Python 使用既有
`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`，
`PYTHONPATH` 指向本 Task14 worktree；pytest 全部指定 `--confcutdir=tests/research_web`。
命令分别为 plan 所列的 `python -m pytest <selected-files>`、`node --test <selected-files>`、
`node .agents/project-constraints.mjs --project . --changed-file <complete-set>`、
`node scripts/check_documentation_governance.mjs --project .` 和
`python scripts/generate_py_file_index.py --check`，完整展开保存在 records。

补充回归（本次实际执行，不复用历史结果）：

- `node --test tests/javascript/research_web_auth_output.test.mjs tests/javascript/research_web_method_tool.test.mjs tests/javascript/research_web_settings_ui.test.mjs`：18 PASS，0.262 秒，`logs/task14-auth-tools-js.log`。
- pytest 额外执行 runtime_endpoints、control_origin、staged_runtime、web_bootstrap、cli_lazy、
  runtime_auth、runtime_contract、credential_backend、docker_packaging、datahub、mcp_authorization、
  model_credentials 共 12 文件：499 PASS / 2 SKIPPED，45.98 秒，`logs/task14-related-python.log`。
  两项模型 Keychain/固定 DSH 实机测试要求显式 opt-in，未执行，不等于原生凭据验收。
- `runtime_state.py`、`docker/healthcheck.py`、统一 runtime 合同相对 feature 未变；
  master stage-scope / runner / matrix / expected_sha 保留，Docker CI 只增加 state/logs fixture 准备。

解析冲突未将冲突语法当成行为 RED；没有额外生产修复或依赖安装。首个 apply_patch 因相对路径
指向主 checkout 而找不到冲突内容，校验失败且未写入；之后所有 patch 使用指定 worktree 绝对路径。
初次整体 patch 输出被截断且被工具拒绝，改为逐文件生成/校验完整 patch。
现有解释器实际缺少 black、isort、ruff（`No module named`），相关格式工具为 NOT_RUN；
不通过安装依赖或降低必需验证门处理此限制。

因冲突集成与工具不可用，最终计划同时保留 `unexpected_behavior`、`validation_failure`
升级信号，仍为 L4；未减少本地或 CI 门。
`node scripts/validate_verification_receipt.mjs --project . --plan logs/task14-local-plan.json --receipt logs/task14-local-receipt.json`
实际通过：valid=true、executedCount=15、externalCount=4、realMachineCount=0。
首次回执因未运行风险键名不精确被严格拒绝；按既有 validator 要求更正为
`external_gate_not_run:<id>` 后通过，没有改 schema、kernel、policy 或 validator。
`node --check app/research_web/runtime/research-tools.mjs` 和 `git diff --check` 实际通过。

schema-v2 总回执保留四个选中 CI 为 NOT_RUN：project-constraints、research-web-checks、
research-web-docker、research-web-bootstrap；result=BLOCKED、mergeReady=false、releaseReady=false。
Ubuntu Docker CI 的 stage-scope 条件仍保留，未运行或被阶段禁用不能冒充 PASS。
本地 merge 提交只完成 source integration，不代表 controller prepare、Mac CI、真实安装/生命周期
重验或总体验收；这些由主任务处理。Windows/Linux 原生验收未运行；未扩大平台范围。
旧停止容器、原宿主状态和实际数据目录不处理。

## 75b9da6 后独立评审的最小诊断修复

上述 75b9da6 合并、计划、回执与 records 均保留其原始源码归属，不冒充后续 HEAD 结果。
Python 评审发现 supervisor 已设置 `control_preparation`，但 `_FAILURE_STAGES` 缺少该阶段，
导致原安全五字段诊断投影为 `unknown`。仅补充这个固定枚举值；认证、状态 guard、模式、
控制事务、失败关闭、异常类别、日志字段集合与清理行为均不改变。

扩展最近的 `test_failure_diagnostics_only_include_fixed_fields` 既有测试，参数覆盖
`logging_setup` 与 `control_preparation`，仍检查全部五字段与秘密省略。
实际 RED：`python -m pytest tests/research_web/test_container_supervisor.py -k failure_diagnostics_only_include_fixed_fields --confcutdir=tests/research_web`，
3 FAIL / 3 PASS / 77 deselected（0.25 秒），`logs/task14-control-stage-red.log`。
单枚举修复后同命令 GREEN：6 PASS / 77 deselected（0.18 秒），
`logs/task14-control-stage-green.log`。这属于合成诊断回归，不是 Docker 产品真机验收。
后续 delta 范围仅 supervisor、现有测试与本报告三个路径；完整基线 changed set 仍为 75。

delta 规划器选择 L4、7 本地门和 3 CI；完整基线另存 75 路径计划。实际本地结果：
supervisor 83 PASS（25.70 秒），launcher 133 PASS（0.78 秒），选中 container-runtime 闭包
共 216 PASS；分开执行的原命令、退出码与日志在
`logs/task14-control-stage-container-runtime-summary.log` 中明确记录，没有复用旧 Python 结果。
docker contract 14 JS、architecture 63 JS、full verification 91 JS 均 PASS；后两者含重复测试，
不重复计算独立证据。documentation-governance、生成 Python index 和完整 75 路径
project-constraints 均 PASS；各实际命令及耗时在 `logs/task14-control-stage-records.json`。
delta plan/receipt 在 `logs/task14-control-stage-delta-{plan,receipt}.json`；既有 schema-v2
validator 实际 valid=true、executedCount=7、externalCount=3、result=BLOCKED、
mergeReady=false、releaseReady=false，CI 未运行状态保留。原 75b9da6 的计划、回执和
records 没有重写；本次记录只认证这个最小 delta，最终仍需主任务控制器重新 prepare。

引用事实：受管 Task14 启动的远端基线为 `ddcdd978…`；主 checkout 的本地 master
`1dbd7547…` 在启动前已存在，两者是不同引用。没有本地 master 并发移动的证据。
controller prepare 应按其独立 refetch 与受管 receipt 判定实际集成基线。
