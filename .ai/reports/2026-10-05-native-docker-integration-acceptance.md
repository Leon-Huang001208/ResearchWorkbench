# Native/Docker 本地集成验收（2026-10-05）

## 范围与绑定

- 工作树：`/Users/leon/.codex/worktrees/dual-runtime-integration/ResearchWorkbench`；分支：`codex/native-docker-local-integration-20261005`。
- 原共同基线：`4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7`；合并提交：`b6213f8173a5f92baee5f6f0d2827f2c0cc7c499`。两个父提交分别为 feature `5788e46956eb25649dd2832ddd9b84ce54cef8a4` 与 master `d17459edeff5696d2a2641c4072c2d08e9ae84d0`。
- 计划路径集为共同基线至合并提交的全部 142 个路径，加本次三个验收产物，共 145 个；不是只取合并冲突文件。master 父至合并提交的 delivery delta 为 111 个已提交路径（含本轮三份报告为 114）：`git diff --name-status d17459edeff5696d2a2641c4072c2d08e9ae84d0 b6213f8173a5f92baee5f6f0d2827f2c0cc7c499`。原始路径以 Git 提交为准。
- 测试与 Native archive 的源码固定为 `b6213f8`；本轮三份报告当前仅为未跟踪文档，由主代理校验后单独提交。后续文档提交不会改写本轮所测源码的身份。
- `.agents/runtime/leon-engineering/manifest.json` 的 11 个受管文件哈希由主代理核对无漂移；本验收没有修改框架、manifest 或旧 Task 13 回执。
- `node scripts/plan_verification.mjs` 使用完整路径集输出 schema 3、L4、145 路径，选中本地 L0 2 / L1 10 / L2 4 / L3 1 / L4 1，以及 5 个 CI merge gate；realMachine 数组为空。单独用 incoming master 父 delta 的 114 个路径复算，选中相同的 18 个本地和 5 个 CI gate；完整共同基线路径集另外识别 `schema-boundary` component，验收仍以完整集合为准。该机械集合不消除目标要求的 Windows 实机、Docker ACL、真实生命周期与模式切换验收。

## 已有可复用证据

- 集成执行者在同一 `b6213f8` 源树运行 1062 项 Python 测试，`logs/integration-final-python.log`，77.00 秒；明确测试文件与命令见 `.ai/reports/2026-10-05-native-docker-local-integration.md`。它覆盖计划中的 service manager、runtime contract、setup、runtime mode、container runtime，不覆盖未列入该命令的 API、本地集成或 credential gate。
- 同一集成源树的三份 JS 策略/skill/Docker 契约日志 `/private/tmp/rwb-policy-tests-green.log` 为 86 通过、5.480 秒；架构 `logs/integration-architecture.log` 为 63 通过、2.806 秒。两者只作为对应路径的已有证据。
- 独立只读审查 `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.superpowers/sdd/2026-09-29-native-docker-dual-runtime/integration-readonly-review.md`：未确认新增 P1/P2；不是运行测试、平台或发布回执。

## 本轮增量运行

- L1 JS 契约合并命令：`node --test tests/javascript/verification_policy.test.mjs tests/javascript/verification_receipt.test.mjs tests/javascript/incremental_validation_skill.test.mjs tests/javascript/research_web_architecture.test.mjs`；`logs/integration-acceptance-l1-js.log`：160 通过，5.360 秒。
- L1 Python：`PYTHONPATH=$PWD /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_local_integrations.py tests/research_web/test_api.py --confcutdir=tests/research_web -q --tb=short`；`logs/integration-acceptance-l1-python.log`：78 通过、1 跳过、266.19 秒。跳过的 `tests/research_web/test_local_integrations.py::test_native_windows_runner_uses_real_host_detection_without_claiming_vendor_access` 标有 `skipif(platform.system() != "Windows")`，原因是需原生 Windows runner。旧 feature 虚拟环境仅提供解释器/依赖，cwd 与 PYTHONPATH 指向本集成树。
- L2 credential：`PYTHONPATH=$PWD <feature-.venv>/bin/python -m pytest tests/research_web/test_credential_backend.py --confcutdir=tests/research_web -q --tb=short`；`logs/integration-acceptance-l2-credential.log`：58 通过、1.14 秒。
- L2 Docker JS contract：`node --test tests/javascript/docker_runtime_contract.test.mjs`；`logs/integration-acceptance-l2-docker-contract.log`：10 通过、0.093 秒。
- L2 Project Constraints 首次运行：`logs/integration-acceptance-l2-constraints.log`，因本报告写入前路径不存在而返回 `reference_missing`。保留原始失败并以 `--signal validation_failure` 重规划；L4 保持不降级，最终 plan 记录该 signal。文件建立后，对相同 145 路径重跑 `node .agents/project-constraints.mjs --project . --changed-file <每个完整路径>`，`logs/integration-acceptance-l2-constraints-rerun.log` 为 0 violations。
- L0 Python 索引：`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python scripts/generate_py_file_index.py --check`；`logs/integration-acceptance-l0-index.log` 为一致。
- L0 文档治理：`node scripts/check_documentation_governance.mjs --project .`；`logs/integration-acceptance-l0-documentation.log` 为 528 files / 0 violations，含本轮报告。
- L3 protocol：`PYTHONPATH=$PWD /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_protocol.py --confcutdir=tests/research_web -q --tb=short`；`logs/integration-acceptance-l3-protocol.log` 为 19 通过、1.31 秒。
- L4 相关 JS 完整组：`node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs`；`logs/integration-acceptance-l4-js.log` 为 84 通过、2.634 秒。

## Native 实进程与缺项

- 主代理将 `b6213f8` 以 `git archive` 导出到任务专属 `/private/tmp/rwb-dual-runtime-13.Gw6yqV/checkout`，复用此前已核验的锁定依赖、CJPY 与固定 DSH。公开 `./setup-web.sh --runtime native --no-start` 返回 exit 0，见 `/private/tmp/rwb-dual-runtime-13.Gw6yqV/native-integration-setup.log`。导出目录无 Git metadata，安装报告 `code_commit=null`；这不是 GitHub macOS 干净 checkout 或联网首次安装。
- 首次 Native lifecycle 使用动态 63990/63991 端口，但旧控制状态仍绑定 8088，安全归属校验给出 `runtime_process_exited`，见 `/private/tmp/rwb-dual-runtime-13.Gw6yqV/native-integration-lifecycle.log`；ownership cleanup 最终两服务均 missing。保留失败记录，未强停未知进程或改写旧可信控制。
- 在任务私有 sibling `research-web-integration` 数据目录、显式复用原任务安装 manifest、DSH 和 `runtime_state_root` 后，动态 64443/64444 上的现有 `WebServiceManager` API 完成 start 16.427s、status 0.123s、doctor 1.498s、restart 9.604s、stop 1.345s、start_again 8.038s、status_again 0.131s、stop_final 1.333s，见 `/private/tmp/rwb-dual-runtime-13.Gw6yqV/native-integration-lifecycle-fresh-data.log`。doctor 为 `installation_ok=true`、`product_ready=true`、`model_ready=false` / `model_credential_missing`；fixture SHA-256 `ab2c660b144e3fcaee356695c4b9f30444cdbe34bb4e67d8b21c4e10566fbc62` 未变，最终 owned services 均 missing，日志结果 PASS。默认端口 8088/3081 的公开 CLI 未运行，已有日常实例未停止。
- Docker 三目录真实测试在用户明确授权后的正常工具路径再次被 PreToolUse 拒绝，未执行任何凭据读写，原 feature 记录 `logs/task14/docker-authorized-test-hook-denied.log`。Docker 产品镜像 APT 阶段仍 exit 100，不能把 Node/Linux stage 当 final image；本轮没有无依据重试构建。
- ruff、black、isort、mypy 在指定测试环境不可用，未运行、未安装。runtime 后来虽观察到一致，更新执行者仍未确认，此项不追查为已验证行为。
- 5 个本次集成提交的 CI merge gate：Linux Project Constraints、Research Web Checks、Docker，macOS bootstrap、Windows Native 均未发起，receipt `external` 逐项 `NOT_RUN`，`mergeReady=false`。Windows 实机、Docker ACL、真实 Native↔Docker 切换、公开默认端口、干净 GitHub 安装仍无证据；planner 的 `realMachine=[]` 不代表目标要求已满足。受管 delivery controller 无 adopt/现成 receipt，App 本地 merge 不等于受管 publish-ready。

## 远端后续条件（只读观察）

主代理已读取 `docs/actions-budget.md` 并只读核验 GitHub：仓库当前为 public，远端默认 master 仍为 `d17459edeff5696d2a2641c4072c2d08e9ae84d0`。该 master 的 Project Constraints、Web Checks、macOS bootstrap 最近运行成功，均不是本集成分支证据；最近 5 次 macOS `macos-14` job 平均约 311 秒，Docker 两架构串行 job 各有 60 分钟上限。若后续获得远端操作授权，拟仅推送本地集成分支并建 PR，让 Linux Constraints/Web Checks、Docker amd64/arm64 和 macOS bootstrap 自动运行；Windows merge gate 与真实设备验收仍须单独处理。本轮未 push、dispatch、rerun、merge、tag 或 release。

`node scripts/validate_verification_receipt.mjs --project . --plan .ai/reports/2026-10-05-native-docker-integration-plan.json --receipt .ai/reports/2026-10-05-native-docker-integration-receipt.json` 返回 schema 2 valid、18 local / 5 external、`BLOCKED`、`mergeReady=false`、`releaseReady=false`。本地机械与隔离 Native 部分验收完成；完整 Goal 仍 BLOCKED。本轮不发布、不推送、不创建 PR。
