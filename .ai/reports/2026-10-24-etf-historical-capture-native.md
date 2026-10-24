# 华安历史验收 CI capture Native v2

宿主 macOS；任务类型为 Web Native 操作员功能开发，验收范围为本机离线合同。仅修改操作员、对应原测试矩阵及本报告；CI 和模块文档由主任务维护。

## 固定身份与边界

- `ETF_HISTORICAL_V2_MODE=reviewed-etf-historical-v2`，命令 `apply-etf-historical-v2`。
- `PREVIOUS=b438447071d08eec38902b2a50610644283885f9`。
- `PAYLOAD=99cf121fb55ab211bc1c66ade7b6cc9989a60d8b`，为本 PR 内完整产品与 CI capture 祖先。最终普通 merge 必须保留该祖先，并对完整候选重新独评及执行原三 CI；该祖先不具有单独产品 CI 回执。
- 原历史 v1、ASSET_V8 及其余旧身份不变；AST 比较确认全部 77 个原 literal 常量保持，仅新增三个 v2 常量。
- 只将 v2 纳入原 ASSET_MODES、previous_for、review_assets、64 MiB 严格业务 reader、固定 `5c3077b7…eebb` 完整证据 reader、恢复 source manifest、市场/后台空闲门与 CLI 分派。
- 原 version4 事务、维护锁、BirthFence、全账号和 dossier 保全、未知/活动拒绝、逐阶段恢复/回滚、latest 重验及 union/blob/mode 校验继续复用。controller/evidence 字节、8 MB/64 MiB 边界及白名单不改。

## 本机验证

统一解释器 `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python`，统一 `PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages`。未安装依赖。

- Red：`python -m pytest --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_model_provider_upgrade.py -k historical_v2_profile --junitxml=logs/ci-capture/native-v2-red.xml`，固定身份测试因缺少 v2 常量按预期失败，1 failed、1838 deselected、0.14 秒；保留 `native-v2-red.log/xml`。
- 完整操作员：`python -m pytest --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_model_provider_upgrade.py --junitxml=logs/ci-capture/native-v2-full.xml`，仅运行一次，exit 0，1965 passed，107.99 秒；一条 Starlette/AnyIO BlockingPortal 弃用提示。原真实 Git、错误前版、额外/回退产品、模式、忙碌/未知、恢复/dossier 和各阶段回滚矩阵已纳入 v2。
- Ruff：`python -m ruff check` 两个 Python 文件，exit 0，0.06 秒。
- Black：`python -m black --check` 同文件，exit 0，0.13 秒。
- isort：`python -m isort --check-only` 同文件，exit 0，0.09 秒。
- mypy：`python -m mypy` 同文件，使用上述主 Python 与 PYTHONPATH/Pydantic 插件，exit 0，1.89 秒；只有原有 unused-section 提示。
- `git diff --check` 通过；`logs/ci-capture/native-v2-invariants.json` 保留旧常量及保护文件字节核对结果。

证据与最终 SHA、CI 及候选评审绑定由主任务整合。本轮未执行实际 apply、常驻更新、Office、供应商、模型、凭据操作或其他 Native 大套件；真实切换、认证页面与报告质量均为 NOT_RUN，未宣称部署通过。

## SHA-256

- 操作员：`8895ec39b3f1af1521c900700f5ffc8eac8289115c2a625c049ad8e805de0c12`
- 测试：`7c196ae07a6c17774f875900376acf7b0574bbf1374dfe58143b20650ae2dd5d`
- `native-v2-full.log`：`5737621555dc6ea61477033e2625622f6aa1a67cf3e0f6127967e39a07342999`
- `native-v2-full.xml`：`968a66bbc2f3d4f0d89a943d49080fbfa1ba937063a35f594ffcf0c58e76b085`
