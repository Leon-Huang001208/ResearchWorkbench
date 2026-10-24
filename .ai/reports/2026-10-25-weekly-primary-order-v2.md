# ETF weekly Native 操作员 v2 准入顺序修复

宿主 macOS；任务为 Web 操作员功能修复；本子任务仅本机离线验收。独立 worktree 为 `etf-weekly-primary-order-20261025`，基础 `b0ebe1df301f9e660c5247af9a5b1526384a32f1`。未提交、未调用真实服务、Office、Native、供应商、模型、凭据或生产数据；未安装依赖。

## 根因和边界

首次非恢复 `operate` 在桥之前执行完整 `m.verify_primary → g.verify_primary`。真实 LegacyBinding 将持久旧 Workflow 等待计入 Host aggregate active，即使 Native 没有计算也会在桥前拒绝。旧 v1 的这项行为、常量、历史工件和身份全部保留。

新增唯一 `reviewed-etf-weekly-admission-v2` / `apply-etf-weekly-admission-v2`，要求原两个 paired flags；previous 固定 `36fd990ceed88d2fc595443926105c4b2601fbf6`，初始产品 payload 固定本轮基础 `b0ebe1df301f9e660c5247af9a5b1526384a32f1`，合入运维修复后的最终固定身份见下文。web.lock / evidence 继承 v9；action SHA、operation_id、领域 profile v1 不变。未修改通用 gateway verifier、领域业务、source 字段或恢复 schema。

v2 原三锁内先执行窄身份预检：原 `g.configured` / `clean`、真实 `LegacyBinding.discover().verify()`、同一 WebServiceManager Native 探针、原 automation index 检查。Host active 必须明确 bool，Native 必须真实 list 且为空；active=True 仅作为观测，不被宣称 idle。配置、原目录身份、owner、版本、服务归属错误照原 LegacyBinding 拒绝。

source/latest target/CI/恢复资格全部通过后才运行既有桥。桥释放 catalog 锁、GET 刷新成功后，立即调用完整原 `m.verify_primary → g.verify_primary`，再做 v2 新鲜严格复核，要求 Host active=False、Native 明确空 list，最后运行原完整 `Operations.idle`。任何其他活动或未知阻止服务切换；已经批准并提交的控制决定保留 unknown，不自动回退。恢复不添加新 live 要求，原 stopped 边界、纯磁盘恢复和不再 apply 的语义保留。

v2 已加入原 ASSET、background、market、完整保全、source-bound recovery artifact 和 version4 恢复集合。全产品业务、上游测试和 CI 按 payload 精确冻结；仅原两个生成 HTML 允许再生且必须 `100644`。

## 实际验证

- `logs/primary-order-v2/red.log`：初始新身份链 1 failed / 6 passed；真实 g 已证明旧链桥前拒绝，失败停在尚未实现的新窄预检。
- `order-regression-red.log`：有新 v2 身份但临时恢复原首处完整 verifier 顺序，实际 `operate` 的两条 v2 用例失败，旧 v1 两条通过；2 failed / 2 passed。两条失败均在领域提交前，证明本轮顺序根因。
- `operate-green.log`：恢复修复顺序后，实际 operate 四组合 4 passed。真实 LegacyBinding、真实 g verifier 和真实 Operations.idle 参与；OS / Git / HTTP / Native 传输隔离，服务 fence 入口以明确 sentinel 截止，无停机。
- `strict-final.log`：97 passed，包含真实身份否定对照、前后 Native None/False/0/空 dict/tuple 等未知、Host 非 bool/新活动、paired flags、旧 v1 保持拒绝；桥前零领域写，桥后保留已提交控制决定但无升级 journal/fence。
- Black、isort、Ruff 与 `git diff --check` 对两源通过；使用批准的根 `.venv` 解释器及旧离线 site-packages，没有安装软件。

最终两源冻结后的同进程完整联合矩阵 **2796 passed**，1 个既有 Starlette warning，353.77 秒，见 `logs/primary-order-v2/final-joint.log` / `final-joint.xml`。JUnit 无 failure/error/skipped。原 bridge 故障、claims 与纯磁盘恢复矩阵现分别参数化 v1/v2；上游精确冻结与两个生成 HTML 例外也同时覆盖两版。先前较早源码 `full.log` 为 2586 passed、304.20 秒，中间 `weekly-final.log` 为 833 passed；它们不替代最终联合证据。CLI 反例曾把 blocked 的既有退出码 1 误断言为 2，已修正测试并由 strict-final 通过；未为通过测试改产品退出码。

准入逻辑完整联合时的源 SHA256：operator `96448c9915fe9a1fe538f5bc119ba2eb2d2456018f64f714bd7820bdd6b0fabb`；test `4f1b053d828df0ae0d86adc79ab930636ddf8660d292c9d6f7c974de67a21e76`。

实际最终联合命令：

```bash
PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages /Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python /Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-weekly-admission-20261024/logs/weekly-admission/run_offline_tests.py --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_model_provider_upgrade.py tests/research_web/test_legacy_weekly_monitoring.py tests/research_web/test_report_weekly_historical_acceptance.py tests/research_web/test_report_weekly_quality.py tests/research_web/test_report_weekly_admission.py --junitxml=logs/primary-order-v2/final-joint.xml
```

静态日志为同目录 `black.log`、`isort.log`、`ruff.log`、`diffcheck.log`；源码哈希另存 `source-hashes.txt`。这证明本地离线实现与组合兼容，不替代真实准入或部署。

## 未验证

最终 candidate/executor 自身身份、独立评审、CI、真实准入及部署由主任务接续。本离线结果不认证现场未来空闲；真实维护/部署、模型、Word、下载和认证页面均未执行。Windows/Linux 产品验收 NOT_RUN。

## 合入 PR228 运维修复后的最终产品冻结

主任务普通合并后的基础为 `4ed5d11452eb52ddd5529a598da955cdfd3430a8`，最新完整上游为 `a8d58cb989ba6f556d597242f1afc51af8549b55`。本 delta 只把新 v2 payload 由临时 b0ebe 改为 a8d58；previous 36fd、action 7cbd、领域 profile、所有旧 mode/payload/哈希不变。对 a8d58 原源码 AST 逐项比对，86 个既有字面量常量均未改变，见 `final-pin-old-identities.txt`。

原 v2 scope 已使用与 v1 相同的严格精确分支；没有新增或放宽业务逻辑。除 operator、本测试、docs/reports 和两个精确生成 HTML `100644` 外，其余路径继续逐 blob/mode 匹配 payload。新增真实临时 Git 回归把 `research_workbench_entrypoint/iteration_resources.py`、`scripts/git_safety.mjs`、`tests/javascript/git_safety.test.mjs`、`tests/research_web/test_iteration_revalidation.py` 纳入原矩阵，分别拒绝 content/mode/deletion；正例证明完整产品包含四文件。没有 scripts/tests 宽例外。

pin RED：1 failed，见 `logs/primary-order-v2/final-pin-red.log`。最终 pin + scope + 两生成 HTML 的窄 delta **163 passed**，93.88 秒，见 `final-pin-delta.log/xml`。本轮只修改常量与 scope 测试；按主任务授权保留 2796 完整联合证据并组合此 delta，不重跑完整五模块。不得将旧完整结果写成新 pin 后完整重跑。

最终 pin 两源 SHA256：operator `f6390827e3480c77734beddf884dfea76899905655eb9def154069ecac39f906`；test `afbf62f33d7d5411a7b7908a4c0bb5a3b89b2dcea01f8f47217e3a719b90efe2`。Black/isort/Ruff/diffcheck 通过。未提交、未执行真实服务操作。
