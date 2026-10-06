# Task14 Desktop固定bind私有叶首次创建

基线 `e043a4975`。主代理实机 `logs/task13/docker13createidentity.log` 显示原runtime_state_directory(create=True)在首建后比较固定mount父identity时，owner由0:0变10001:10001导致失败；原目录权限/类型检查均通过。这纠正前波“子叶布局足够首建”的判断。先前backend write/persist失败不能当成持久化成功。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只修复既有supervisor固定bind缺失叶的准备顺序；保留挂载、data-root、单容器与原validator/backend安全规则，不新增进程或存储。","diagrams":["01-deployment"]} -->

## 最小修复与安全约束

supervisor `_prepare_private_leaf` 只对 `/state/runtime`、`/run/rwb-secrets/private`、`/data/research-web/logs` 的不存在叶走两阶段。逐级 no-follow 打开并保留祖先/固定父FD，在受验证的700固定mount父下mkdir700并pin新叶。父dev/inode/mode及路径/FD一致性不得变；仅首建阶段允许固定mount父root:root→当前进程UID:GID。随后原runtime_state_directory完整重新pin，并核对新叶仍是创建后保留FD对应的对象，才进入auth/probe/spawn。

已有叶不进入映射分支，alias/755/foreign owner继续失败；自定义路径使用原严格create边界。没有捕获RuntimeStateError无条件重试，没有root-init、host chown或canonical data-root变更。data-root/logs同类首建也覆盖。runtime_state.py、credential_backend.py源保持未改。

## 验证

- 确定性RED：8 failed / 0.54s；`/private/tmp/rwb-task14-first-create-red.log`。三类叶的测试还先直接调用原validator并确认创建时映射确实失败。
- 首次GREEN：14 passed / 0.29s（含已有私有叶门）；`/private/tmp/rwb-task14-first-create-green.log`。
- 增补矩阵23 passed / 0.75s：runtime/private/logs各覆盖合法映射、foreign UID/GID、mode/inode变化、自定义路径不豁免；另有parent alias/755/foreign owner、parent或leaf在重pin前替换。`/private/tmp/rwb-task14-first-create-adversarial.log`。
- 完整目标命令为 `.venv/bin/python -m pytest tests/research_web/test_container_supervisor.py tests/research_web/test_credential_backend.py tests/research_web/test_docker_packaging.py --confcutdir=tests/research_web -q`；仅本地fixture需要loopback/ps窄提升，不运行真实Docker。
- 完整目标125 passed / 20.42s；`/private/tmp/rwb-task14-first-create-closure.log`。原runtime_state guards另6 passed / 0.34s；`/private/tmp/rwb-task14-first-create-original-guards.log`。
- compileall、diff空白检查、生成索引check通过；base e043a4975 的architecture与documentation-governance均无violations（`/private/tmp/rwb-task14-first-create-architecture.log`、`/private/tmp/rwb-task14-first-create-documentation.log`）。`git diff --numstat e043a4975 -- app/research_web/runtime_state.py app/research_web/credential_backend.py` 为空，证明原安全源码未改。

## 物理证据边界

此代理没有执行DockerDesktop。全新独立bind source上的固定private首建、File backend写读及另一新container重读由主代理继续验证；源码测试不能替代这些物理证据，也不能替代完整镜像/DSH/Web/平台/CI门。历史失败日志不覆盖、不改写Task13并发回执。

主代理后续回执：新helper三目录的目标机实测命令被PreToolUse Hook拒绝，**未执行，blocked_by_hook**。
不修改Hook、不换工具路线或重新调查一致性。新helper的真实首建、File backend首次写读及第二
container持久化重读仍未验证；此前 `docker13backendwrite.log`、`docker13backendpersist.log`
中的物理失败没有变为pass。本报告只认证已执行的本地单元/adversarial证据。
