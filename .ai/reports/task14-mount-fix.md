# Task14 Docker Desktop 私有叶修复

基线：`95180d825`。主代理提供实机发现：macOS Docker Desktop 29.8.1、固定 Python base、容器 UID/GID 10001:10001，宿主用户创建的0700 bind根在容器呈现UID0，即使可写也被严格私有叶检查拒绝；由容器在bind内创建的0700子目录呈现UID10001，另一新容器仍可通过同一检查。该物理实测由主代理执行，本代理不声称已运行Docker。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅区分既有state/credential bind根和容器创建的私有叶；单容器、挂载targets、canonical data-root、Native路径、进程与安全校验拓扑不变。","diagrams":["01-deployment"]} -->

## 修复

- Dockerfile与Compose显式设置 `RWB_RUNTIME_STATE=/state/runtime` 和 `RESEARCH_CREDENTIAL_HOME=/run/rwb-secrets/private`。原Compose未选择File backend的问题一并纠正；Native仍保持默认系统keyring。
- bind根继续为 `/state`、`/run/rwb-secrets`，controller/Inspector的source/target合同不变。entrypoint只检查父挂载可写，再exec supervisor。
- supervisor在auth/probe/child之前，用原 `runtime_state_directory(create=True)` 创建并验证两个私有叶。每次restart重验既有叶，不chmod/chown挂载根，不做root-init，不动态映射host UID，不放宽uid/mode/no-follow。
- healthcheck只读消费 `/state/runtime`。`LOG_DIR=/state/logs` 保持为独立兄弟路径，避免core.settings导入期mkdir提前把状态叶创建成755。
- canonical用户data-root与Native目录不改；File backend生产实现、安全模块及manifest事务均未修改。

## 实际验证

- RED：supervisor/入口/默认路径新回归7 failed / 0.35s；`/private/tmp/rwb-task14-mount-red.log`。JS静态合同1失败；`/private/tmp/rwb-task14-mount-static-red.log`。
- GREEN：新增目标8 passed / 0.25s，覆盖准备发生在ownership/children之前、相同inode/UID700跨run复用、state/credential alias与755拒绝、默认health/state一致、File backend新实例持久化。`/private/tmp/rwb-task14-mount-green.log`。
- `.venv/bin/python -m pytest tests/research_web/test_container_supervisor.py tests/research_web/test_credential_backend.py tests/research_web/test_docker_packaging.py --confcutdir=tests/research_web -q`：102 passed / 24.19s；`/private/tmp/rwb-task14-mount-closure-2.log`。仅pytest命令窄提升用于真实loopback/ps临时fixture；没有Docker或产品服务操作。
- `.venv/bin/python -m pytest tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web -k runtime_state -q`：原安全guards 6 passed / 0.41s；`/private/tmp/rwb-task14-mount-state-guards.log`。
- `node --test tests/javascript/docker_runtime_contract.test.mjs`：10 passed / 77.05ms；`/private/tmp/rwb-task14-mount-static-green.log`。
- 首次闭包命令误用了不存在的 `test_runtime_state.py`，没有执行测试；原日志 `/private/tmp/rwb-task14-mount-closure.log` 保留，不记为验收。随后查到真实guard所在test_runtime_launch.py并完成。
- Python compileall、生成索引check与git diff空白检查执行；未新增Python模块或修改已索引公开符号，索引无需变动。没有新依赖安装。
- 本波base `95180d825` 的architecture检查与documentation-governance均无violations；日志 `/private/tmp/rwb-task14-mount-architecture.log`、`/private/tmp/rwb-task14-mount-documentation.log`。

## 尚需主代理合并的证据

新叶布局在真实Docker Desktop上的完整supervisor/认证/凭据生命周期由主代理继续物理验证。此处单元/源代码闭包不等同真实镜像构建、两架构、Native↔Docker资料往返、远端CI或Windows验收；这些gate仍保留在整体验收回执。无全局配置、远端、真实用户数据或凭据操作。
