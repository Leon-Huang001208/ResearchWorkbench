# Runtime switch finalize 受控诊断

- hostPlatform: macOS; taskKind: 功能缺陷诊断补足；base: `3fbe2645e693d358779d19a40188be0722ce1583`。
- 独立 worktree: `/Users/leon/.codex/worktrees/switch-finalize-diagnostic/ResearchWorkbench`。
- 真实历史现象由主任务持有：Native→Docker 返回 `runtime_stop_failed`，随后两模式 status 均停止。历史具体 finalize 原因已丢失，本补丁不认证生命周期已修复。
- 唯一生产变化：原 finalize 拒绝分支补 warning，记录固定 mode、report_not_ok/still_running、受控 issue。原 JSON、错误优先级、短路、status 次数、严格 running 校验、lease、归属、CAS 和停止顺序保持。
- issue 显式 allowlist：runtime_ownership_unknown、native_probe_failed、docker_ownership_mismatch、docker_data_home_unsafe、docker_io、docker_cli_missing、runtime_command_timeout、runtime_output_limit、lifecycle_lock_ownership_lost。仅首个 list issue 且精确 str 匹配时输出；其他为 unknown，still_running 为 none。原 report/detail/路径/秘密不输出。
- TDD RED：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_runtime_mode.py -k finalize -q`，12 failed、62 deselected；失败只因缺受控 diagnostic message。证据 `/private/tmp/switch-finalize-red.log`。
- GREEN 与完整验证结果在下方追加；解释器为既有 native-docker-dual-runtime-20260929 `.venv/bin/python`，未安装依赖。
- 生成索引 `python scripts/generate_py_file_index.py --check` PASS，无须修改索引（entrypoint/tests 不在生成范围）。
- 安装合同核对：requirements/web.in、requirements/web.lock、scripts/setup_web.py、bootstrap workflow 无依赖/安装/公开参数变化；macOS 干净安装 CI 由主任务交付环取得。
- 当前实机 Native/Docker、GitHub CI、发布：本子任务 NOT_RUN，由主任务拥有；hostAcceptance 与 aggregateAcceptance 在完整 gate 回执前为 BLOCKED。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Adds fixed stderr diagnostics only at the existing finalize rejection; no guard, state machine, probe, retry, deployment or persistence change.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Records the unchanged switch safety and controlled diagnostic fields in existing authority documents; no diagram relationship changes.","diagrams":[]} -->

- 最近两 catalog：386 PASS / 1 FAIL /152.75s，既有 `test_up_created_then_failed_recovers_only_this_launch[timeout-image]` 当次归属探测失败；证据 `/private/tmp/switch-finalize-green.log`。保留该失败，不归因或修复无关生命周期。
- 定点重跑该单项 + runtime_mode + protocol：95 PASS /5.07s，含新增12诊断用例；证据 `/private/tmp/switch-finalize-target-rerun.log`。
- Node Docker contract、architecture、documentation、quota、cross-platform contract 联合114 PASS /6.14s，证据 `/private/tmp/switch-finalize-node.log`。
- Ruff、Black、isort 针对两变更 Python 文件 PASS；首轮 Black FAIL 后仅格式化新增测试，保留 escalation `validation_failure`。
- Managed runtime manifest SHA256 全匹配。完整 changed-set planner 为 L4；4 CI 门 constraints/checks/Mac bootstrap/Docker 均由主任务保留 NOT_RUN，不宣称 mergeReady。
- 完整9文件 changed set 的 project-constraints 与 documentation-governance 终次 PASS（分别0违反与572文件/85 current/0违反）；第一次 constraints 因必需模块文档和 README review 缺失而 FAIL，补足后通过。
- 最终文档改后 architecture/documentation Node 两门重跑80 PASS /5.65s；未复用3fbe历史 source-affinity证据，全部8本地门均亲自执行。runtime-mode gate 仍如实 FAIL（完整catalog未再次重跑）；critical-smoke 为本次95用例联合执行内 PASS。
- 主任务独立 SPEC 与 Python质量/安全评审 APPROVE；质量评审focused12 PASS，源/测试SHA与冻结值一致。
- 计划与 schema-v2 receipt 位于忽略目录 `logs/switch-finalize-plan.json` / `logs/switch-finalize-receipt.json`；validator exit0，valid=true、result=FAIL、mergeReady=false、releaseReady=false、8 executed/4 external。已保留完整catalog失败与CI NOT_RUN，不认证历史生命周期已修复。

## Native status 阶段补足（base 444e3cbb6）

- 主任务实测记录 finalize mode=native/report_not_ok/runtime_ownership_unknown；Native stop成功、端口关闭、模式保持Native；随后单次只读current stage均成功。仍没有稳定根因，不改变行为。
- 仅在 NativeRuntime._probe 原 precheck拒绝、postcheck拒绝及validated child not-ok原返回处追加固定 stderr日志；正常状态无新日志、失败报告原样返回、40秒预算与检查/runner次数保持，无重试/新探测/配置。
- 三个参数化 RED 用例仅缺阶段日志而3 FAIL（313 deselected/0.61s），`/private/tmp/native-stage-red.log`；Native bridge近处GREEN 10 PASS（380 deselected/1.22s），`/private/tmp/native-stage-green.log`。测试覆盖原JSON/子进程与安全检查次数/预算和秘密字符串不进入日志。
- 原完整Docker catalog 386 PASS/1 FAIL继续保留，本轮没有自动重复全量catalog。
- 本阶段runtime_mode/protocol 94 PASS/2.46s（`/private/tmp/native-stage-runtime-mode.log`）；Node5规划门114 PASS/6.28s（`/private/tmp/native-stage-node.log`）；Ruff/Black/isort与生成索引 PASS；9文件delta constraints/documentation 0 violations。
- delta planner/receipt为 `logs/native-stage-plan.json` / `logs/native-stage-receipt.json`，validator exit0/valid=true/result=BLOCKED/L4；完整runtime-mode gate本阶段 NOT_RUN（只有近处与runtime_mode/protocol），4 CI NOT_RUN；没有拿近处测试替代完整gate。原分支全范围门由主任务重新规划，仍保留先前catalog FAIL。
