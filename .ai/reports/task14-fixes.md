# Task 14 集中修复证据

范围：以 `eeb530c8c` 为基线，关闭 Task14 审查的四项 P1/P2，并按主代理补充指示修复 Native `web status --json` 与 API/local_integrations 宿主凭据隔离。未改验证策略、框架、Task13 回执、依赖或远端；未执行 Docker build、产品服务启停或真实凭据读取。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"收紧现有controller的接受镜像与健康成功语义，保留单容器、双服务、端口、数据和凭据部署拓扑；没有增加运行节点或数据存储。","diagrams":["01-deployment"]} -->

## 改动与边界

- Docker 启动默认以120秒健康等待预算轮询；每次 Docker 命令另有超时。starting 超时、unhealthy、退出与归属不明均不成功；失败回滚只重新验证并删除本次创建的精确容器ID，数据/凭据和当时既有容器保留。
- 独立候选build tag + 私有安全摘要读取 + 不可变 image ID；检查 Web锁、Compose、Python/Node、CJPY/DSH 合同，缺失/损坏失败关闭。安装私有候选入口不影响公共 start 的接受摘要要求。候选或发布失败保留接受镜像；模式提交失败恢复旧摘要。显式 no-start 保持只接受构建、不声称实际ready。
- 默认安装遇到不同image ID旧容器拒绝发布；主代理明确授权的显式离线 `--repair` 在验证归属、停止、端口空闲后再次检查并仅非force删除旧容器，保留旧接受摘要/image/data/secrets。候选或publication失败后旧image可重新start；并发变running时复核拒绝或Docker非force rm失败。若checkout锁/Compose已改，旧image回退仍要求恢复旧合同，不能假称任意跨合同回退。
- Doctor 保留真实 `dsh` ready/build_verified/commit/host_applicable；Native `status --json` 输出稳定安全投影，不输出日志路径，普通文本不变。
- 祖先比较节点identity，直接合同父目录保留完整metadata，因此祖先无关sibling活动不误报且现有瞬时alias/restore攻击门保持。直接父目录内容活动仍保守失败关闭，这是主代理明确接受的窄边界。
- API与local_integrations 每例内存keyring fixture，不接触宿主Keychain，不修改生产Keyring错误处理。

## 实际验证

- 最终代码闭包（含显式repair及rm前竞态复核）：四模块297 passed / 39.70s，命令同下方四模块聚焦命令；`/private/tmp/rwb-task14-final-repair-closure.log`。此后只补证据文本，代码未再改。

- RED：将 `git show eeb530c8c:<module>` 读取的原模块源码仅在隔离测试进程中加载，运行四个新回归，4 failed；`/private/tmp/rwb-task14-baseline-red.log`。早期两次环境探测未进入收集（根conftest需要本环境无的sqlalchemy、main venv路径不存在），原日志保留，不作为有效RED。
- Native JSON RED：`test_cli_lazy.py -k native_status_json --confcutdir=tests/research_web`，1 failed（exit2无json选项）；`/private/tmp/rwb-task14-status-red.log`。
- 四模块聚焦：`.venv/bin/python -m pytest tests/research_web/test_runtime_contract.py tests/research_web/test_docker_runtime.py tests/research_web/test_setup_web.py tests/research_web/test_cli_lazy.py --confcutdir=tests/research_web -q`，290 passed / 23.51s；`/private/tmp/rwb-task14-final-focused.log`。沙箱原运行出现socket/ps EPERM，已用仅此pytest命令的窄提升复测。追加发布锁内摘要校验与失败日志后再次运行，见最终补充日志。
- API与本机集成：`.venv/bin/python -m pytest tests/research_web/test_api.py tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q`，78 passed / 1 skipped / 1 warning / 233.40s；`/private/tmp/rwb-task14-api-integrations-1.log`。skip为现有平台条件，warning为第三方starlette弃用提示；未留下独立API失败。
- 四项安装事务补充：4 passed / 0.66s；`/private/tmp/rwb-task14-transactions.log`。
- 发布锁内摘要校验后四模块复测290 passed / 37.88s；`/private/tmp/rwb-task14-final-focused-2.log`。no-start保护后controller/setup复测177 passed / 12.07s；`/private/tmp/rwb-task14-upgrade-guard.log`。
- 离线repair补充先5 RED / 0.86s，再5 GREEN / 0.88s（普通repair、候选不健康、发布失败后旧镜像重建、no-start、并发启动非force rm拒绝）；`/private/tmp/rwb-task14-repair-red.log`、`/private/tmp/rwb-task14-repair-green.log`。另补rm前复核发现running不调用rm回归，最终套另记。
- `compileall`目标源码/测试成功；`git diff --check`成功；Python索引已重新生成。
- `ruff`、`black`、`isort`、`mypy`未安装且无新增依赖授权，未执行、不声称通过。

## 未认证项

原审查真实Docker build/health/持久化往返、GitHub macOS干净安装、Docker平台gate、Windows实机证据仍未获得，本波模拟测试不替代这些证据。完整分支历史文档/图门由主代理安排串行closeout。本波以eeb530c8c为base的architecture第二次检查及documentation-governance均无violations；日志为 `/private/tmp/rwb-task14-architecture-2.log`、`/private/tmp/rwb-task14-documentation.log`，不能替代完整分支base的检查。不声称ready-to-merge。
