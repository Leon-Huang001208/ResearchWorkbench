# ETF Native 封闭 v2 离线实现

宿主 macOS；任务为功能开发（既有部署操作员的封闭分派）；本平台范围为离线操作员回归与静态检查。
基线 `56709a8dbb6e01d2ab17b64533319e199ebef86f`，独立 worktree `etf-native-profile-v2-20261023`。

旧 v1 固定产品 `988046d23f9951f889a3b9d02e355ed59fd6aa65` 及全部历史身份保留。
新 `reviewed-etf-weekly-v2` / `apply-etf-weekly-v2` 固定旧版
`5343e18d9f203a87f2d958218e4288afa527711f`、PR209 产品
`56709a8dbb6e01d2ab17b64533319e199ebef86f`。只增常量及原矩阵分派，复用 v4 事务、
维护锁、BirthFence、所有空闲门、严格全账号业务索引、PR209 dossier 摘要及恢复。
`controller.py`、`evidence.py` 和自动白名单未修改，完整日志 reader 仍固定 `5c3077…eebb`，
安装锁仍为 `7c631d4f…7102`。原日志/错误传播路径复用，没有新依赖、权限、HTTP或执行器。

此前用户仅批准旧 PR208 合并目标 `2e1ba701a0f33bf1dbeab79f1f9984f320d33a24`；
实际 apply 尚未执行、常驻仍为5343为主任务提供的现场事实，本子任务未再次探测服务。
master 已前进导致旧 payload/latest 门不能同时通过；不跳门，新组合目标尚待单独明确授权。
本轮未部署、未触碰 credentials、未调用 Office/厂商/模型、未启用日程、未安装依赖、未提交/push。

验证记录（`logs/etf-native-v2/`）：

- 先扩充测试，`red.log` 记录新固定身份用例因缺 `ETF_WEEKLY_V2_MODE` 的真实红灯。
- 主 Python `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python`；已批准 devtools
  `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages`
  通过 `PYTHONPATH` 使用。初次未加 PYTHONPATH 无 pytest；采用默认根 conftest 又缺无关 legacy SQLAlchemy，
  未安装依赖，按既有离线闭包使用 `--confcutdir=tests/research_web`。
- `python -m pytest --confcutdir=tests/research_web tests/research_web/test_model_provider_upgrade.py -q`：
  **1391 passed，1 条既有 Starlette/AnyIO 弃用警告，85.40秒**（operator-tests.log）。
  原真实 Git union/blob/mode/祖先/额外文件拒绝、wrong previous、全账号索引、空闲未知和阶段恢复
  矩阵均纳入 v2；新增主/私账号真实 dossier 成功与修改后拒绝恢复用例。
- 将 wrong previous 中 PR208 身份补为完整 SHA 后，目标回归 `-k 'weekly_v2 or etf_weekly or cannot_select_the_legacy_previous'`：66 passed，1325 deselected，2.83秒（final-target.log）。
- 两个 Python 文件 `ruff check`、`black --check`、`isort --check-only` 及 `git diff --check` 通过。
  日志分别为 ruff.log、black.log、isort.log；五文件完整闭包、完整 Router/完整性检查由主任务统一执行。

本机离线、旧 PR209 CI、v2 最终候选 CI、真实常驻切换与正式报告质量分开。

主任务补充：其余 gateway/resident/multiuser/API 四文件 473 passed，354.95秒，1条既有警告；
与操作员1391项组成五文件1864项的分段执行，日志 remaining-four-tests.log / operator-tests.log。
最终目标66项另验测试中的完整旧SHA。完整改动集索引、文档治理、架构及项目约束检查通过；
8个JS文件225 passed（6.32秒）。规格及独立Python质量审查均批准，质量审查另执行14项v2反例、
ruff/black/isort/mypy（既有配置、follow-imports=skip）。报告不将这些结果认证为尚未完成的最终CI。
用户解锁后原生读取恢复，浏览器自动控制仍超时；任务页截图实际为server_origin_denied，
私网/auth只读HTTP200，未关闭来源校验或改权限。共享Chrome临时由另一验收占用，保持避让。

v2 最终候选三 CI、macos-14 干净安装、独立评审及实际部署尚未由此子任务认证；
真实 Office/Wind/EDB/模型/正式 Run NOT_RUN，日程保持关闭。Windows/Linux 原生证据 NOT_RUN。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"v2仅固定PR209组合产品并复用既有Native主实例网关v4事务与dossier保全，无新拓扑权限依赖","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"v2复用既有全账号冻结保全恢复和PR209 dossier摘要，不增加账号通道拓扑权限或依赖","diagrams":[]} -->
