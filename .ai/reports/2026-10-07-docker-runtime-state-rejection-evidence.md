# Docker runtime state 拒绝证据日志

宿主 macOS；任务为 Web 诊断取证开发；本轮范围为本机确定性测试、文档与静态门禁。
基线 `655ab87d00db23abaeed76ce85171e07f2b971f7`。本报告不认证 Docker 生命周期或整体 Goal。

只在既有 guard 拒绝处记录固定 reason、phase、ancestor/leaf 与变化字段名。
owner、mode、no-follow、FD/path身份、只读/创建和 Native legacy 语义不变。
日志不包含路径、数值身份、Cookie、token、内容或异常正文；handler抛异常时放弃日志，
继续安全拒绝。公开异常仍 `RuntimeStateError`、`runtime_state_unsafe`；外层原异常链保留。
supervisor、公开五字段诊断与 artifact scanner 未改。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Only add fixed private rejection diagnostics at existing runtime state guard branches; existing deployment, authentication, directory layout, public startup schema, dependency graph and lifecycle remain unchanged.","diagrams":[]} -->

## TDD 与验证

解释器为既有批准的
`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`；
Node 为 `/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。
所有 pytest 均 `PYTHONPATH=.` 且 `--confcutdir=tests/research_web`。

- RED：`python -m pytest tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web -k 'rejection_reason_is_private or identity_rejection_evidence or logging_failure_preserves_rejection or valid_guard_emits_no_rejection' -q --tb=no`：23 failed / 2 passed / 63 deselected，0.41s；缺固定日志字段。
- 首轮 GREEN：该模块全量 88 passed，0.70s。
- 补 FD/ancestor/same-inode ownership 负面用例后：95 passed，0.72s。
- 后续完整 changed-set 门禁结果将补充；上述为各次 pytest 自报耗时，不能当作总执行耗时。
- 初次六路径 Constraints exit 1：缺安装、01/02/03模块说明及 meaningful architecture-review；按现有门补齐，不降低门禁。初次文档治理 PASS（551 files、79 current），索引检查 PASS；L4 JS闭包91 passed、0 failed（自报2488.605875ms）。
- 完整六模块 Python 闭包：`python -m pytest tests/research_web/test_runtime_launch.py tests/research_web/test_runtime_auth.py tests/research_web/test_credential_backend.py tests/research_web/test_container_supervisor.py tests/research_web/test_staged_runtime.py tests/research_web/test_docker_packaging.py --confcutdir=tests/research_web -q --tb=short`：304 passed / exit0，自报26.53s。测试内均为独立临时 fixture，不执行 Docker Engine 或实际数据目录操作。
- 最终新增外层guard handler失败用例后，launch模块96 passed / exit0，自报0.74s；未把旧304计数重写成305。
- 完整十路径 plan带两个 signals：exit0 / L4 / `unknown_impact_boundary`；选中本地 architecture、constraints、verification-full、governance、file-index；CI为 Linux `project-constraints` 与 `research-web-checks`，均 NOT_RUN，mergeReady=false / releaseReady=false。Mac干净安装仍额外NOT_RUN，不能误把Linux runner计为Mac。
- 十路径 Constraints exit0 / violations=[]（本次独立工具命令0.011575333s）；文档治理exit0 / violations=[]（551 files、79 current，独立命令0.0422855s）。file-index检查exit0（独立命令0.942609125s）。各工具计时仅属于对应独立命令，跨命令总耗时 unknown；L1 architecture为L4复合JS命令的组成部分，单项耗时unknown。
- `git diff --check` PASS。现有解释器 `importlib.util.find_spec` 确认ruff、black、isort、mypy均不可用：格式/lint/type检查NOT_RUN，未安装依赖。
- 最终文档同步后的L4 JS重验：`node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs`：91 passed / exit0，自报2122.467083ms；复合耗时不分摊给单个门。

完整 changed set：`app/research_web/runtime_state.py`、`tests/research_web/test_runtime_launch.py`、
`docs/architecture/research-web/{01-system,02-research-runtime,03-data-files,05-security-validation}.md`、
`docs/architecture/research-web/readme-review.json`、`docs/research-web-installation.md`、
`docs/generated/py_file_index.md`、本报告。未触及主任务的三个macos-port-allocation产物或scratch。

Planner 保留 `validation_failure` 与 `unexpected_behavior` signals；现有 test路径未分类触发
L4/unknown_impact_boundary，未更改 Router 政策。必需外部门未运行时保留 NOT_RUN/BLOCKED。
安装核对覆盖 requirements/web.in、web.lock、setup_web.py、安装说明与bootstrap workflow；
无依赖/安装流程变化，干净安装CI仍须验证，不能以本机已有环境替代。

## 未执行与风险

Docker build/start、真实状态/fixture目录操作、网络/安装、全局配置、Harness、远端操作均未执行。
新日志尚未在实际容器中获取，不知道实际拒绝 reason/phase；这不是根因修复。
macOS 干净安装/真实生命周期与 GitHub CI 为 NOT_RUN；Windows/Linux 原生验收 NOT_RUN。
日志延续既有 logger、输出与轮转配置，不增加独立日志文件或新的保留策略。

## 第二轮：方向与相对位置分类

基线 `0b7c801cf47ee69a8cc4878c8a1d7111684a986a`，仍为macOS Web logging-only取证。
主会话提供新镜像公开build/install成功、实际start失败证据：`post_yield/ancestor/changed=uid,gid`。
该事实来自主会话，本执行者没有运行Docker，也没有重新读取实际状态；变化方向和具体祖先未知。
本轮只追加私有 `ownership_transition=root_pair_to_runtime_pair/reverse/other` 与
`position=leaf/parent/other_ancestor`。前者精确比较完整before/current所有权对；后者只传
component与叶/直接父的布尔关系，不硬编码Docker路径、不增加公开API、marker或异常属性。
无法分类只记录other；所有校验/异常链保持原状，不能把拒绝定位到具体Cookie writer层。

- RED：`python -m pytest tests/research_web/test_runtime_launch.py --confcutdir=tests/research_web -k 'private_ownership_classification or ownership_classification_keeps_rejecting' -q --tb=no`，30 failed / 96 deselected，exit1，自报0.74s。
- 初次GREEN全量launch：126 passed / exit0，自报0.77s。
- 补mixed-root组、runtime/root对重合与分类getter失败后：131 passed / exit0，自报4.22s；仍使用首轮批准Python、`PYTHONPATH=.`和confcutdir。方向/相对位置断言无路径/数值/秘密；path与FD变化仍抛原异常。
- 本轮完整changed set为runtime_state.py、test_runtime_launch.py、01/02/03/05模块文档、安装说明、README review及本报告（九路径）；没有新函数名或inventory变化，旧index只检查不制造diff。
- 首轮304结果是历史执行，未作为本轮完整闭包计数；本轮后续本地门结果另补。总体CI/真实Docker取证/format/type仍NOT_RUN，非整个Goal PASS。
- 本轮六模块闭包实际重验（与首轮相同六模块完整命令，session39376）：340 passed / exit0，自报26.53s；不将历史304倒算为本轮结果。最终类型注解与POSIX测试标注后launch再验131 passed / exit0，自报0.78s。
- 本轮L4既有JS闭包完整命令：91 passed / exit0，自报2440.990375ms；architecture单项耗时unknown，不从复合命令摊分。
- 完整九路径planner保留validation_failure/unexpected_behavior：exit0 / L4 / unknown_impact_boundary；local为既有五门，CI为project-constraints/research-web-checks，均NOT_RUN；mergeReady=false/releaseReady=false。
- 九路径Constraints exit0 / violations=[]，独立工具命令0.158062375s；governance exit0 / 551 files / 79 current / violations=[]，独立命令0.121811583s；index --check exit0，独立命令0.975117042s。git diff --check PASS；总耗时unknown。
- parent仅是相对位置，不能单独证明具体固定Docker挂载根。只有另行确证固定state bind完整root-pair→runtime-pair事实才满足下一步初始化修复设计触发；本补丁不做修复。本执行者仍未运行Docker/网络/安装/Harness/远端或改实际状态/目录权限；格式/type工具仍NOT_RUN。
