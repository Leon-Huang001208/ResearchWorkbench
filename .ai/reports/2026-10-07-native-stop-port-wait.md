# Native 停止端口释放等待

- hostPlatform: macOS；taskKind: 功能缺陷修复；base: `7b8ef041fa2fa90d1781aa733a52be67cd561e82`。
- 范围仅 bootstrap switch_runtime、近处 runtime_mode 测试及直接文档；原任务报告与失败日志保留。
- 初始真实 NativeRuntime 已验证运行、显式 stop-current、公开 stop 成功后，以停止前的 ports 元组和原 port_busy 等待最多45秒；每轮睡眠不超过0.1秒/剩余期限。超时 runtime_stop_failed，不提交 mode。
- 内部预算只接受精确有限 int/float，范围0至45；在停止前拒绝 bool/子类/NaN/inf/字符串/巨大整数/越界。无新公开参数、依赖、权限或持久格式。
- 等待不刷新 ForeignLedger，不重试 guard；原 switch_select lock/scope、两模式 fresh status 与 CAS 全保留。
- TDD RED：nearest `-k native_stop_switch` 11 FAIL/5 PASS，缺少等待与预算拒绝；`logs/native-stop-port-wait-red.log`。
- 首轮 GREEN 16 PASS；最终聚焦23 PASS/0.91秒，`logs/native-stop-port-wait-green-final.log`。
- fixture 仅隔离 Native bridge 报告；使用实际 NativeRuntime/public stop/port_busy 与真实临时绑定且未监听的 socket，后台线程延迟关闭。覆盖持久绑定超时、未授权/未知/失败stop/已停不等待、停止前端口冻结、等待期间 mode更改与runtime重启拒绝。该测试不证明真实产品健康或所有权。
- 完整 planner local gates 与 receipt 结果下方追加；CI与物理验收由主任务持有，当前 NOT_RUN/BLOCKED。无安装、远端、全局配置、Docker image、实测HOME或用户数据改动。
- 安装合同复核：requirements/web.in、requirements/web.lock、scripts/setup_web.py 和 bootstrap workflow 无依赖/入口/安装参数变化，兼容性仍需 macOS 干净安装CI证明。
- hostAcceptance: BLOCKED；aggregateAcceptance: BLOCKED；platformHandoffs: Windows/Linux 当前阶段暂缓，未验证；mergeReady/releaseReady: false。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Waits only for captured Native ports after authorized successful public stop; original lease, ownership scope, fresh statuses and mode CAS still execute unchanged. No deployment or persistent schema change.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Records the bounded wait and unchanged safety boundaries in existing authority documents; no diagram topology changes.","diagrams":[]} -->

## 本地验证回执

- 9文件 delta planner：L4/full-delivery；11个受管 kernel manifest SHA256 全匹配。计划 `logs/native-stop-port-wait-plan.json`。
- 完整原选 runtime-mode 命令 `python -m pytest tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py --confcutdir=tests/research_web`，最终生产/测试源码上一次完整执行：413 PASS/106.83秒；`logs/native-stop-port-wait-research-web-runtime-mode.log`。没有用聚焦23项替代该门，先前分支失败日志保留。
- critical smoke：`python -m pytest tests/research_web/test_protocol.py --confcutdir=tests/research_web`，20 PASS；`logs/native-stop-port-wait-research-web-critical-smoke.log`。
- research-web-architecture、Docker contract 与 verification-full 全通过；verification-full 是规划器原四模块命令，100 PASS；各门独立日志 `logs/native-stop-port-wait-<gate-id>.log`。
- 文档治理、Python生成索引、9文件完整 changed-set Project Constraints 全 PASS；全部8个 local gate均为本次实际执行。
- Ruff 0.16.10、Black 26.10.0、isort 9.0.2 对两个修改Python文件 PASS；Black/isort格式化未产生改动，`git diff --check` PASS。
- mypy 2.4.0 正常项目配置单文件目标 `mypy research_workbench_entrypoint/bootstrap.py --no-incremental --show-error-codes`：FAIL，57 errors/19 files/1 source目标。当前与确认干净的旧source worktree HEAD `3fbe2645e693d358779d19a40188be0722ce1583` 使用相同配置/工具、仅只读复用批准venv site-packages，两侧file+message+error-code多重集完全相等（忽略行号）；无新增/移除诊断。`logs/native-stop-port-wait-mypy-{current,baseline}.log`；不把既有类型债务认证为PASS。
- schema-v2 receipt `logs/native-stop-port-wait-receipt.json`，validator `logs/native-stop-port-wait-receipt-validation.json`：exit0/valid=true/result=BLOCKED、8 executed/4 external、mergeReady=false、releaseReady=false。
- 四个规划CI门 Project Constraints、Research Web Checks、macOS bootstrap与Docker都保留 NOT_RUN；本子任务不远端执行/不裁剪政策，主任务按当前阶段处理。真实Native/Docker完整公开生命周期及RAM秘密比较仍由主任务单独取证，单元fixture不冒充实机。
- 冻结SHA256：bootstrap.py `5058bf5cd3b5ca9a32221305c6dc24eefc649062240c28a3e0c93892fe750135`；test_runtime_mode.py `e141b7912a5a823522eb39d98376d79fdc7f14083b7469c62edb492e10197c0e`。
