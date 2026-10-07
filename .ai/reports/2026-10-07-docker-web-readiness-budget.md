# Docker Web readiness 单轮预算修复

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅调整既有supervisor的Web单轮预算，保留同一ContainerHealth与三项页面判定，不新增部署节点、持久协议或数据格式。","diagrams":[]} -->

- hostPlatform: macOS；taskKind: 既有功能最小修复；base: `681e261c5dcb825f9d0120ea2b159a2b8d5ef276`。
- owner: `codex/docker-web-readiness-budget-20261007` 独立 worktree；未修改实际产品 checkout。
- hostAcceptance: BLOCKED（本地源码验证已完成，真实镜像重装/生命周期与 macOS CI 未运行）。
- aggregateAcceptance: BLOCKED；mergeReady=false；releaseReady=false。
- platformHandoffs: 真实 macOS Docker/Native 与 macOS bootstrap 留给主任务；Linux Docker CI、Project Constraints、Research Web Checks 为 NOT_RUN。他平台无本机验收主张。

## 根因与最小实现

supervisor 原本把 Runtime 与 Web 每轮都裁为 0.25 秒；ContainerHealth 为该轮所有 HTTP
请求建立同一总期限，而完整 Web 就绪需要 Runtime API、首页、主静态模块三次 GET。
只把 Web 每轮预算调整为既有独立健康检查默认的 3 秒，并继续 `min(budget, remaining)`。
Runtime 每轮 0.25 秒、每角色 startup35、shutdown8、认证/PID绑定、媒体类型、正文标记、
2 MiB 上限、原错误传播与精确子进程清理不变。EndpointStore 与模型凭据邻近警告不在本次范围。

测试使用既有真实子进程、真实回环 HTTP、真实 Runtime Cookie/session 校验；只在 HTTP
client send 完成后给 probe/supervisor 的单调时钟增加每 Web GET 0.14 秒。
没有 mock 健康返回或替换页面判定；0.42 秒完整路径在 0.25 秒预算下失败、3 秒下成功。
负面用例保留三个独立错误页面、剩余期限小于 3 秒、deadline 耗尽、失败退出与两角色精确清理。
同模块原有 SIGTERM/SIGINT、异常退出、错误 RPC、流式慢响应、auth/PID/目录负面测试保持。

## 实际验证

测试解释器 `P=/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`；
工具目录 `Q=/private/tmp/rwb-stage1-test-992c74ec/bin`（只读复用；未安装依赖）。
下列命令均在 owner worktree 执行，`P`/`Q` 是本报告缩写，不是环境变更。

| 检查 | 实际命令 | 结果 |
| --- | --- | --- |
| RED | `PYTHONPATH=. P -m pytest --confcutdir=tests/research_web tests/research_web/test_container_supervisor.py -k web_budget -q`（production修改前） | 1 failed / 83 deselected；8.66s；断言完整页面被单轮预算阻断 |
| GREEN | 同一命令（含四项负面用例） | 5 passed / 83 deselected；10.42s |
| 最终目标复查 | 同一命令（剩余启动期限 fixture 固定为0.25秒） | 5 passed / 83 deselected；5.23s |
| 最近闭包 | `PYTHONPATH=. P -m pytest --confcutdir=tests/research_web tests/research_web/test_container_supervisor.py tests/research_web/test_runtime_launch.py -q` | 221 passed；36.32s |
| JS合同与L4 | `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs tests/javascript/docker_runtime_contract.test.mjs` | 114 passed；7.49s；0 failed/skipped |
| 格式 | `Q/black --check docker/supervisor.py tests/research_web/test_container_supervisor.py` | 首次 FAIL；仅修正新增行格式；复查 PASS，0.56s |
| lint | `Q/ruff check docker/supervisor.py tests/research_web/test_container_supervisor.py` | PASS，0.12s |
| imports | `Q/isort --check-only docker/supervisor.py tests/research_web/test_container_supervisor.py` | PASS，0.20s |
| 类型 | `PYTHONPATH=<P的既有site-packages> Q/mypy --follow-imports=silent docker/supervisor.py` | FAIL；2个既有错误，3.55s；104 arg-type、624 var-annotated 两行与base逐字一致；不借本修复扩大类型整理 |
| 类型工具前提 | `Q/mypy --follow-imports=silent docker/supervisor.py` | 工具自身环境缺少 pydantic.mypy；随后仅只读复用已批准 P 的包路径，未安装包 |
| 文件索引 | `PYTHONPATH=. P scripts/generate_py_file_index.py --check` | PASS；1.09s；索引无需修改 |
| 文档治理 | `node scripts/check_documentation_governance.mjs --project .` | PASS；0.12s；violations=[] |
| 受管kernel | 按 `.agents/runtime/leon-engineering/manifest.json` 对全部 files 做 SHA-256 比对 | 11 / 11 一致；mismatches=[] |
| Project Constraints 初查 | 全changed set传入 `.agents/project-constraints.mjs` | FAIL；要求补齐既有03-data-files模块文档和architecture-review标记；已补齐，不修改策略 |
| Project Constraints 复查 | 同一命令，完整11文件changed set | PASS；0.05s；violations=[] |
| 最终文档治理 | `node scripts/check_documentation_governance.mjs --project .` | PASS；0.03s；571 files，violations=[] |
| 回执校验 | `node scripts/validate_verification_receipt.mjs --project . --plan .ai/reports/2026-10-07-docker-web-readiness-budget-plan.json --receipt .ai/reports/2026-10-07-docker-web-readiness-budget-receipt.json` | exit0；valid=true；result=BLOCKED；executedCount=7/externalCount=3 |

完整 changed set 的正常及 `validation_failure`/`unexpected_behavior` 重规划均保持 L4。
README.md 已审阅：公开入口、依赖与模式选择未变；用户说明已在安装指南同步，无需修改README。
本次源码与镜像真实运行是两层证据；未读取/输出私有 child raw 日志、认证值或请求正文。

## 冻结审查快照

自审：production 只在原 probe 调用处按角色取预算；测试仍使用原认证/页面判定及真实HTTP，
负面三页面与deadline均失败关闭并清理精确PID。没有新增配置、依赖、探测器或跨模式权限。
主任务的独立spec/quality review与真实安装仍待完成，不在本子任务声称通过。

- production SHA-256: `517556e73b1eabab98657c768eb2d327218f64a26e87537476c28881be86ee00`
- test SHA-256: `efbc18923acce2c37b911e350179716a9188c7b19cf64e5224d36e2f5ef1877c`
- production+test `git diff` SHA-256: `4e54ec4fba903bf0b05c3830f0ae197eec45db58dfd161f2b99c035712067682`
- 改动集之外的安装锁、ForeignLedger、App、RootGuards、healthcheck与runtime contract均无diff。

## 未运行与限制

四项 CI 均 NOT_RUN：Project Constraints、Research Web Checks、Linux Docker runtime、
额外适用 macOS bootstrap；本子任务不 push、dispatch、merge、清理或修改 CI。
真实 Docker 新source安装、启动/重复启动/会话行为以及 Native 切换由主任务接续。
源码测试不能证明原真实容器在新镜像内的故障已经消失；mypy基线错误仍保留。
