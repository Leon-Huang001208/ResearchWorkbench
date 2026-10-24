# 华安周报封闭 Native 后继与旧等待衔接

宿主：macOS。任务：Web 功能的 Native 操作员候选实现；只做本机离线验收。未执行真实维护、部署、Office、模型、凭据读取、安装依赖、Windows/Linux 产品 dispatch。

## 变更边界

- 仅修改 `research_workbench_entrypoint/resident/model_provider_upgrade.py`、原操作员测试和本报告；其他产品、依赖、CI、旧 profile 常量与恢复哈希均不由本子任务修改。
- 新封闭命令 `apply-etf-weekly-admission`，mode `reviewed-etf-weekly-admission-v1`；前版固定 `36fd990ceed88d2fc595443926105c4b2601fbf6`。当前完整产品祖先固定普通 merge P7 `63583746e6bccc201e29f622063307f8d4333bc1`，包含上游 PR227 数据出处/单位核验及用户明确批准的 PR229 Wind 字段顺序/单位/均价红绿。历史 P5 `82151bc2708d60c7abb1d38b686a3e368e42f812`、P6 `88b2f96d449085cae01912393a416b0e90a21083` 及其旧证据保留。保留 v9 完整 16MiB job reader 哈希与 web.lock 身份；PREVIOUS、action 封印及旧 modes 不变。
- 同时要求 `--end-weekly-waiting` 与 `--weekly-monitoring-action`；旧命令收到任一新 flag 明确拒绝。封印只含固定 canonical SHA256，不写入真实 owner 或运行身份。
- 在原三把 EX 锁、source/latest master/CI/controller/current revision/恢复工件门之后、第一次原 `Operations.idle` 之前，单独执行领域维护。原 background/market/asset、全账号保全、BirthFence 和 version4 恢复门全部保留。

## 控制决定与恢复

通过无 reconcile 的 maintenance catalog 和实时主管理员 resolver，先校验固定 action、目录身份、旧 Run 与冻结字节，再只读验证 Native 完整 session 清单及所有非子会话的 child catalog 闭包。直接使用真实 `DSHClient` 的 async context、`session.list` 和 `subagent.list(activityOnly=True)`；拒绝 active、非 bool running、缺 catalog/live、duplicate、orphan 和错误 parent/origin。既有历史 child `mode=unknown` 仍可由 live/parent/origin 严格证明 inactive。

独立私有 intent/receipt 使用 no-follow、owner、0600、单链接、256KiB 上限、inode/metadata 比对、文件及目录 fsync。只允许 Workflow 控制态改为 cancelled、ended_by_user 并保存领域 receipt，unknown、原失败、SID、数据、采集、合同、用途及其他事实保持。

目录提交后释放 catalog 锁但保留原三锁，单 Run GET 刷新旧 Host 并比对完整公共投影，随后继续完整原 `Operations.idle`。GET 失败或其他活动不会回滚已明确授权的控制决定，也不会继续部署。

提交后独立 receipt 未完成时使用稳定码 `weekly_monitoring_action_committed_receipt_pending`。显式同一 action 的 apply 重入以精确 before/after 验证补 receipt，已提交后的领域调用只 dry-run，不再次更改目录。`recovering=True` 要求 intent、receipt 和磁盘 after 精确匹配，不 apply，不调用 Native 或 GET；原恢复继续允许 Host 已停止。无升级 journal 但新 intent 存在时，缺 receipt 返回 pending；已有记录也必须完成纯磁盘核验，不能仅凭升级 `not_required` 认证维护。

## 离线证据

- 最小 RED：2 failed，见 `logs/weekly-admission/native-bridge-red.log`；最小 GREEN：2 passed，见 `native-bridge-green.log`。
- 完整操作员与领域矩阵基线：2285 passed，1 个既有 Starlette DeprecationWarning，116.85 秒；见 `logs/weekly-admission/native-bridge-final-matrix.log`。
- 规格评审 P2 修复：无升级 journal 时对 intent/receipt 对称检查，receipt-only 拒绝；任一 symlink 或 broken symlink 在启动 bridge 前拒绝。两文件皆无的旧路径原样返回 `not_required`。窄 RED 为 5 failed / 2 passed，见 `native-bridge-spec-delta-red.log`；修后全部 weekly 定点 149 passed，见 `logs/weekly-admission/native-bridge-spec-delta-green.log`。该固定恢复状态 delta 依主任务要求定点重跑，未重跑完整 2285 矩阵。
- Black、Ruff、isort 和 `git diff --check` 对本子任务两文件通过。

质量评审发现同根因的 apply 分支 P2：receipt 为 broken link 时，原前置 `exists()` 漏检；合法 before intent 加一个 0600 `{}` receipt 也会在 CAS 后才拒绝。修复抽出 apply/recover 共用的对称 record presence 门，任意 intent/receipt 链接在入口拒绝；existing receipt 必须在重发布 intent、Native 检查及领域 CAS 前精确匹配当前已提交 after 行、领域 receipt、绑定与 unknown。before 行带 existing receipt 立即拒绝。新增 helper 所有安全 `exists()` 门均核对 `is_symlink()`，临时文件清理也处理 broken link；未修改旧 profile 的历史门。

该质量 delta 的 7 例 RED 为 5 failed / 2 passed，见 `logs/weekly-admission/native-bridge-quality-delta-red.log`；修后 156 weekly 定点 passed，见 `logs/weekly-admission/native-bridge-quality-delta-green.log`。全部新增反例明确断言 catalog 字节不变、无新 intent、Native 不启动。Black/Ruff/isort/diffcheck 通过；依主任务要求不重跑 2285 完整基线。

质量 P2 修复冻结文件 SHA256：operator `3bca508c987673820cb67cf41c691f7f4b6127cacbce7c29f19ab52a750c5c71`；test `1eaa91496d5cc2025d60b49d69fea0b07f03dacb8c581ce39f3c6e2115bee58a`。规格与质量复核由主任务接续。

## P6 完整冻结与最终复验

P6 上游 `providers_akshare.py`、`providers_reference_evidence.py`、`research_snapshot_store.py`、原 `research-web-checks.yml` 和五个上游测试均属于非豁免完整产品字节。新增真实临时 Git 回归证明这些文件被纳入部署 review，逐文件内容、模式、删除均拒绝；只允许既有 operator、原 operator test、文档和报告例外，没有放宽 CI 或其他测试例外。P6 pin RED 为 1 failed；修后定点 31 passed，日志分别为 `native-bridge-p6-red.log`、`native-bridge-p6-green.log`。P5 及两轮 P2 旧证据完整保留。

最终 P6 冻结文件 SHA256：operator `40ee0823cd39fec227e2c727e51c2e26f2a66555a106bf015d2f1ae3fa80dfd1`；test `546a049cc2eae36081eab137062e7defd256c71e2ab27e3328a7b721b628c40b`。Black/Ruff/isort/diffcheck 通过。P6 pin 与两轮 P2 的完整操作员＋领域矩阵 **2329 passed**，1 个既有 Starlette DeprecationWarning，159.40 秒，见 `logs/weekly-admission/native-bridge-p6-full-matrix.log`。本轮没有重跑 API 或操作生产环境。

## 最后生成文档例外修复

prepared integration `462ea81495648268e7360382e7e0ae4621d5779b` 的实际 scope review 复现 `asset_upgrade_payload_changed`，原因是 new mode 的精确业务冻结分支先于历史两个生成 HTML 例外。仅为新 mode 显式允许 `outputs/research-web-architecture/index.html` 与 `outputs/research-web-architecture/api-atlas.html` 再生，且两文件必须为 Git `100644`。第三 output、品牌/SVG、PNG 等仍逐 blob 和 mode 冻结，不增加 `outputs/` 宽例外，不变更 P6、源 renderer、业务门或部署。

真实旧 candidate 的失败和修后同 target scope review 通过（106 个文件）分别保存为 `logs/weekly-admission/native-bridge-generated-docs-real-red.log`、`native-bridge-generated-docs-real-green.log`。修后读取 feature 新操作员代码对旧 candidate 执行的仅是 scope review，不代表该旧 candidate 已满足 executor 自身代码资格，也没有执行 apply。

真实 Git 回归新增两文件一起或分别再生的正例，以及第三 output 内容/模式、两 HTML 可执行模式、链接和删除的拒绝反例；RED 为 3 failed / 6 passed。修后 weekly 窄闭包 **195 passed**，见 `logs/weekly-admission/native-bridge-generated-docs-green.log`。Black/Ruff/isort/diffcheck 通过；主任务要求本 delta 不重跑 2329 完整基线，旧完整日志保留，最终 CI 另证。

此 delta 最终冻结 SHA256：operator `be2e2e070dab9ebc04c3072bc8135c229decbe4d473bca46a8aabd2738c5268d`；test `ba913e4e677ec0bf6e23b882d9a3365b022a0f421071c4aa81e2ba3659ceb6d3`。未提交、未更改 prepared candidate，由主会话负责 managed 整合及原规格/质量复核。

运行命令使用已批准环境：`PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages /Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python logs/weekly-admission/run_offline_tests.py --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_model_provider_upgrade.py tests/research_web/test_legacy_weekly_monitoring.py`。该入口隔离 xlwings；无 pip、Office 或真实 Native 访问。

覆盖包含：封印 schema/hash/权限/链接/大小/重复 JSON、所有旧 mode flags、原 profile 实际 Git/事务矩阵、新协议与 claim 拒绝、parent/child strict RPC 正反例、CAS 前后及 intent/receipt 前后故障、replace/fsync 边界、精确补 receipt、恢复篡改与根更换、GET 失败，以及领域维护后真实原 Operations.idle 的其他活动拒绝。

## 待主任务完成

完整 changed-set Router、独立规格/质量评审、最终 SHA 的原三 CI 与 macOS 干净安装，由主任务汇总。真实维护和部署仍须单独明确批准并实时重做全部准入；未来模型、Word、下载及认证页面均 NOT_RUN。本离线候选不证明现场未来空闲或部署成功。

## 最终prepared候选自身验证

主会话从候选519458a6725d029757fb845b15cdedc3d70e5958自身源码运行完整操作员及领域测试：2338 passed、1既有warning、134.96秒，integration日志final-candidate-native.log/xml；该源码已包含最终生成文档精确例外。其自身真实Git范围审查106路径通过，源码operator be2e2e07…匹配候选。仅源范围与离线测试，不是executor/CI/生产维护或部署通过；最终发布身份另由私有交付回执绑定。

## P7 最终批准范围

主任务普通合并用户明确批准的 PR229 后，冻结 P7 `63583746e6bccc201e29f622063307f8d4333bc1`。本子任务仅修改新 mode 的产品 pin，不改 previous、action SHA、旧 modes、两生成 HTML 精确 `100644` 例外或两轮 P2 修复。新增三个 UI 模块、Root README 和五个上游 JS 测试进入真实 Git 冻结矩阵：逐文件 content/mode/deletion 均须拒绝，其他 README/tests 不获宽豁免。原 P6 后端和 CI 冻结用例继续保留。

P7 pin RED：1 failed，见 `logs/weekly-admission/native-bridge-p7-red.log`。最终源 SHA256：operator `18a846bb1eb8ebb053c9cb6a384f2d053ce7d2a4dd585793219f9977c74eb754`；test `f1cbc8419863198d0c7b2684c621c5611d11245033a72b594f56163e079f90d8`。Black/Ruff/isort/diffcheck 通过。P7 冻结定点 **58 passed**，40.50 秒，见 `logs/weekly-admission/native-bridge-p7-green.log`；包含 P7、两轮 P2 与两个生成 HTML 精确例外的最终完整 operator＋领域矩阵 **2365 passed**，1 个既有 Starlette DeprecationWarning，167.90 秒，见 `logs/weekly-admission/native-bridge-p7-full-matrix.log`。上游五 JS、后端字节与最终规格/质量重绑由主任务分别取证；本轮未重复 API、未提交、未触生产。
