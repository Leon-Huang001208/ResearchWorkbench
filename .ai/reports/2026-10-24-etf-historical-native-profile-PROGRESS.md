# ETF 历史验收 Native 封闭模式

宿主 macOS；功能开发，范围为既有 Native 操作员封闭身份及离线验收。
独立 worktree `etf-historical-acceptance-20261024`；未执行部署或真实产品运行。

## 固定身份与变更

- `ETF_HISTORICAL_MODE=reviewed-etf-historical-v1`，命令 `apply-etf-historical`。
- PREVIOUS 固定 `b438447071d08eec38902b2a50610644283885f9`；现场主实例/网关身份由主任务刚刚只读复核提供，本子任务未另访问生产服务。
- PAYLOAD 固定 `d5d5b456706fc02505ac1100353d46438c184556`，即本 PR 内已完整提交的历史产品 P；P 包含产品、CI、09/10 图与 API 文档。
- P 目前是该分支祖先，不伪称 P 单独已有 PR/CI。最终须普通 merge 保留 P 的真实祖先身份；最终 target 必须最新已合并 master，受管交付、完整候选独评及原三 CI 分别合格。
- 只增加常量及原分派：原 v4 事务/恢复、64MiB全账号严格业务索引、档案快照、Host/Native/私有池/市场 inflight 空闲门、恢复 source 绑定沿用。日志及明确错误传播复用原操作员设施。
- 旧 profile 身份、controller/evidence、自动白名单、latest 双重复验、差异路径并集及 blob/mode 门不修改；完整 CI reader 仍固定 `5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb`，依赖锁仍为 `7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`。

## 验证命令与证据

主 Python：`/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python`。
`PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages` 使用已批准现存 devtools，无依赖安装。
实际文件 runner 为 `logs/etf-historical/run_offline_tests.py`，支持 macOS spawn；导入测试前封闭 xlwings（App/Book 拒绝），不通过 stdin 运行。

1. 先增加测试，运行 `python logs/etf-historical/run_offline_tests.py --confcutdir=tests/research_web tests/research_web/test_model_provider_upgrade.py -k etf_historical_profile -q`，因缺 `ETF_HISTORICAL_MODE` 得到真实红灯：1 failed，1725 deselected（native-profile/red.log）。
2. 实现后运行 `python logs/etf-historical/run_offline_tests.py --confcutdir=tests/research_web tests/research_web/test_model_provider_upgrade.py -q`：**1727 passed，1 条既有 Starlette/AnyIO 弃用警告，100.88秒**；runner exit=0，101.008秒。完整结果见同目录 operator-tests.log。
3. 两个 Python 文件 `ruff check`、`black --check`、`isort --check-only` 通过，`git diff --check` 通过；日志在 `logs/etf-historical/native-profile/ruff.log`、black.log、isort.log。

新增模式直接复用原矩阵：真实 Git 接受精确 P，拒绝未知后端/额外产品/依赖/mode/祖先变化；P 修改过、最终回退旧值而从 previous→target 差异消失的路径仍由 union 拒绝；wrong previous 明确拒绝旧5343、fc96及产品P。
原全账号业务索引、大小限制、Host/Native/pool/市场未知、各事务阶段回滚/中断恢复、source manifest 错绑，以及主实例/私有账号真实 dossier 保全及变更后拒绝恢复均纳入新模式，无新增重复大全套。

## 未执行与边界

本子任务仅修改操作员、对应测试及本报告，文档/图/workflow由主任务负责。
未修改 Git、commit/push、依赖、Office、厂商、模型、凭据或生产服务。
新目标部署仍需单独明确授权；本机/旧产品 CI 不替代最终完整候选独评、三 CI 和同候选 macos-14 干净安装。
原真实历史模型/Word验收 NOT_RUN；不把离线测试当正式报告合格，日程保持关闭。
Windows/Linux原生及Docker产品验证 NOT_RUN。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"原封闭profile只绑定新的固定历史产品祖先并复用既有Native主实例网关v4事务和恢复，不新增部署节点拓扑权限或依赖","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"新固定profile沿用原64MiB全账号业务索引和dossier快照保全及BirthFence恢复，不增加账号通道部署节点权限或依赖","diagrams":[]} -->
