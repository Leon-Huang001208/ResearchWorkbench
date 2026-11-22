# 华安周报可信准入与提交账本实现

- 宿主：macOS，功能开发；仅本机离线 Host/Native 传输夹具与原生 Seatbelt 验收。
- Worktree：`/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-weekly-admission-20261024`。
- 基线：`85072764cccc869420095402888f3654f550cc72`。
- 状态：本地实现完成；必需独立评审、完整 Router、同候选 CI/干净安装由主会话继续，未宣称总体验收完成。

## 改动

`service.send` 的普通通用能力门保留。只有 Runtime 私有入口与 Host 冻结 scope 共同匹配的周报不再选择不相关公司 Workflow。每次 Native 准入重新核验 owner、已发布启用版本、用途、原合同/快照/上下文、模型与来源范围；限定 13 个既有工具。脚本只获得冻结逐文件路径，额外文件不进入 scope。

`weekly_execution.py` 同域保存 scope 与 Run 私有不可覆盖 attempt claim。claim 使用 O_EXCL/NOFOLLOW、文件类型/大小/私有权限读回、文件和目录 fsync；持久化失败不调用 prompt。`preflight/prepared/rpc_attempted/accepted/unknown` 分开，已有 claim 不重放。明确预检失败的显式继续复用同 Run/SID/key/冻结 context、现有 receipt/delivery/研究合同，不调用采集器。Prompt 保留锁定最低子 Agent 数与原一次有界修订/原质量门。

旧 Run 缺可信 Sender revision/阶段凭据时，空消息、空活动、空子 Agent 或空用量不能证明 RPC 前拒绝。显式 recheck 仅记录 `research_recovery_protocol` 和 `recovery_failure_code=weekly_legacy_sender_unproven`，不伪造原 `research_submission_protocol`，原失败/采集时间保持。普通 public send 也不能绕开。未实现任何强制重发或旧 SID 首次续发正路径。原 accepted 只恢复观察和交付。新 Run 的 sender 协议为 `weekly-admission-v2`；已知零 RPC 预检失败的原始时间和错误也单独保留，成功恢复不抹除。

底层新增 Host 专属 `input_policy=weekly-frozen-inputs-v1`，从 Native admission 经 JavaScript Tool 到独立 Python runner 传递，模型参数不能指定。JS 与 Python 都拒绝绝对/回退/反斜线/控制字符、符号链接、非 regular、nlink 非 1、超过 32 MiB 的文件。weekly 模式不再默认授予 inputs 子目录，只以 literal 授予冻结文件；SDK/resources 的原研究合同读取保持。旧 capability/dataset 目录 scope 保持兼容。后续已授权新闻仍经原 `research_read_source` 取正文，不自动把新增 inputs 或行情/数据库目录纳入冻结文件策略。

旧四个安全/恢复 fake-Sender 测试已迁移到真实 ResearchService、真实 capability catalog、真实完整合成 DataAssessment。只隔离 Native 传输与凭据；共享 keyring fixture 显式阻止 xlwings 导入。后续全部验收由真实 main 文件 `logs/weekly-admission/run_offline_tests.py` 在 pytest 导入前注入有 ModuleSpec 的离线 Office 哨兵，Mac spawn 可复用。

## 实际验证

环境前缀为 `PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages`，解释器为 `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python`。未安装依赖。

- RED：`python -m pytest --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_report_weekly_admission.py --junitxml=logs/weekly-admission/red.xml`，2 failed / 1 passed，4.60s。可信周报真实 send 复现 `capability_data_unavailable`；另一个失败是新 journal 模块尚未实现。日志 `red.log`。
- 离线闭包：`python logs/weekly-admission/run_offline_tests.py --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_report_weekly_admission.py tests/research_web/test_report_weekly_quality.py tests/research_web/test_report_workflow_integration.py tests/research_web/test_report_weekly_evidence.py --junitxml=logs/weekly-admission/closure.xml`，79 passed / 1 warning，88.66s。日志 `closure.log`。此记录早于新增真实脚本读取测试，不能认证脚本完整可用。
- 真实脚本 RED：同 runner 定点 `test_frozen_weekly_files_are_readable_in_real_script_sandbox`，1 failed，2.70s，`SandboxError: invalid script resource scope`，日志/XML `script-scope-red.*`。现存 JS 与 Python 两层只接受 capability/dataset 目录，Seatbelt 还会隐式允许非 dataset 输入目录；已向主会话报告必需的窄修复，不假报通过。
- 修复后真实脚本 GREEN：`script-scope-green.*`，1 passed，18.24s；包含真正 Native Tool → Python runner → macOS Seatbelt 的 parent 和同 cwd child 读取。其后增加中文/空格且 3,457,644 字节文件，`unicode-scope.*`，1 passed，4.91s；核 snapshot/context 原 SHA，未冻结/后加 inputs 和写冻结文件拒绝。
- 受影响完整闭包：前述 runner 加 `tests/research_web/test_sandbox.py`，输出 `final-closure.log/xml`，116 passed / 1 skipped / 1 warning，223.46s。SKIPPED 为 `test_native_tool_schemas_match_pinned_dsh_converter`，未设置 DSH_SOURCE_ROOT，不能声称该 schema 检查通过。
- 新协议/旧 Run 元数据语义修订后定点新增模块 `final-weekly.log/xml`：23 passed / 1 failed，45.34s；失败仅为新中文夹具对已存在 workbooks 目录执行 mkdir，修复后上述 unicode 定点通过。该失败不隐藏。
- `node --test tests/javascript/research_web_quality_tool.test.mjs tests/javascript/research_web_guard.test.mjs`：40 passed，2.23s，`node-scope-guard.log`。覆盖未知/缺失 Host 策略、路径逃逸、别名/类型/尺寸、模型参数不可透传，原 guard 保持。
- Ruff/Black/isort 八文件及 helper+sandbox 两文件 mypy 日志为 `ruff.log`、`black.log`、`isort.log`、`mypy.log`；最终状态与哈希见本报告后附。

初次未注入全局 Office 哨兵的旧闭包发现 xlwings 导入注册了枚举 Excel 的退出回调并报错；没有主动调用 Office。后续入口在导入 pytest 前明确替换 xlwings，避免重复触及此隐式行为。该首轮输出不是干净 Office 隔离证据。

## 未执行与边界

- 真实模型、供应商、Office、8088/3081、凭据读取、新数据采集：NOT_RUN，按授权禁止。
- 原历史 Run 模型/Word/下载：NOT_RUN；旧 Run 仍 unknown，不自动重发。
- 完整 Router、独立评审、GitHub CI、Mac 干净安装、部署、真实模型质量：主会话负责，当前 NOT_RUN。
- Windows/Linux 原生与 CI：NOT_RUN，交对应设备；无本机跨平台认证。
- 未 commit、push、创建 PR 或部署。
- 新模块真实完整合成输入测试耗时超过旧文档 15 秒模块预算；保留完整证据，未删测试降门。

## 最终补充证据与源码身份

- 最后恢复定点：`final-recovery.log/xml`，5 passed / 1 warning，16.46s；覆盖原预检失败留痕、同 Run 显式继续不采集、三种旧阶段无可信 Sender 均拒绝。
- 最终 Ruff/Black/isort 八文件、mypy 两文件均退出码 0；`git diff --check` 通过。
- 原 116 项闭包后仅追加旧 Sender/recovery 字段语义、预检错误留痕与中文/空格文件夹具，对应上述最终定点；不把较早闭包误称最终提交 SHA 的 CI。

## SPEC-1 恢复错误证据保全修复

显式 inspect 的旧 pending/unknown receipt 分支、已 accepted 后 detail 失败、启动恢复的等待及异常分支，统一仅写 recovery_failure_code；原 failure_code、sender protocol、unknown 阶段、admission/采集与冻结数据不覆盖。新协议 prepared/preflight_rejected 在启动后只转 needs_attention 等待显式继续，阶段保持，恢复原因 weekly_recovery_waiting_explicit_retry。周报恢复监控异常也记恢复错误，不冒称新的提交错误。未改生产 Run、idle、重叠门或部署逻辑。

定点命令：原离线 runner 选择 test_recovery_preserves_legacy_sender_failure_and_frozen_evidence、test_startup_keeps_known_preflight_stage_for_explicit_retry、test_pending_data_receipt_is_only_inspected_not_replayed；spec-1.log/xml：11 passed，8 warnings，22.76s。警告含既有 pytest 临时垃圾清理并发 DirectoryNotEmpty，无 Office/模型调用。Ruff/Black/isort 这两个变更文件及 diff check 均通过，spec-1-{ruff,black,isort}.log。未重跑116项大套。

以下哈希表及 source-hashes.json 为 SPEC-1 后更新，替代前版清单。

## 结束等待后的恢复防御

按主会话新增委派，仅对 monitoring_disposition=ended_by_user：retry 最前返回原 Run，不调用 inspect/重投影/提交；启动恢复显式过滤，即使 status 意外仍 needs_attention 也不恢复。未修改 cancel、idle、生产数据或维护操作。ended-wait-guard.log/xml 定点2 passed / 1 warning，4.05s；验证 cancelled 和 needs_attention 两种状态、Native.calls 为空、完整 Run 不变。最终两个文件 Ruff/Black/isort 与 diff check 通过。

## Python质量评审：并发成功状态防回退

复现首调用在claim之前暂停、第二调用通过外层attempt检查后等真实service.send锁的交错。首个accepted后，第二异常不得覆盖Run成功状态；_submit_weekly与_resume_weekly_submission异常边界均重读当前Run，已有research_started_at或accepted阶段时保留当前字段。直接调用仍抛出原重复错误，不把accepted receipt单独当Run保存成功证据，首次RPC丢ACK仍unknown。

RED：concurrent-state-red.log/xml，direct/background第二入口×首RPC accepted/lost_ack，2 failed（accepted被错误回退）/2 passed，11.45s。GREEN：concurrent-state-green.log/xml，4交错与ACK后Run写盘故障恢复共5 passed / 1 warning，16.19s；每交错prompt RPC恰1，accepted的status/rpc阶段/finalization/failure不回退，unknown路径保持blocked。Ruff/Black/isort两个改动文件及diffcheck通过，concurrent-state-{ruff,black,isort}.log。未重复116大套，未改模型/依赖/生产。

以下文件清单已按本修复刷新。

## 并发保护的交付观察边界补充

Python reviewer继续指出后台try还覆盖本次成功后的_wait_for_delivery；保护已收窄为仅_submit异常且当前已有持久accepted事实。本次_submit已成功、后续交付观察失败时仍转needs_attention/finalization blocked，保accepted阶段和receipt，以recovery_failure_code记录真实观察错误，不吞故障、不冒称RPC unknown。最终定点concurrent-state-green-final.log/xml：6 passed / 1 warning，16.55s，覆盖原4交错、ACK后Run写盘失败恢复、新增真实Sender成功后monitor故障。最终两文件Ruff/Black/isort及diffcheck通过。此最终文件表替代中间d222版本清单；其余源码未改。

| 文件 | SHA-256 |
| --- | --- |
| `app/research_web/service.py` | `258644ffaeda5b7c0bb5cf9e06349efe628ed3649e1811845de0a9e8890aa380` |
| `app/research_web/report_workflows/runtime.py` | `94ef8e8801ea055c502abaad6860f0b53bd92d287579a263acbc32ebee57e6fa` |
| `app/research_web/report_workflows/weekly_execution.py` | `80c02c83d254697c2160e942e18fd5a0df95e9b486720aaee91c1131e1f27c93` |
| `app/research_web/runtime/research-tools.mjs` | `f73b06abcb842257f79a1d96c64616553e90ed41070a297e3957de4bccd7e671` |
| `app/research_web/sandbox.py` | `5d452576b6a284a1dd6e5750cfb0d13a011e3dceb98fcd857b581df87c044a11` |
| `tests/research_web/test_report_weekly_admission.py` | `ed224f8594e6784a741b23e9f562e142395877e291290928aec7529214819888` |
| `tests/research_web/test_report_weekly_quality.py` | `0a85e6fdcb6bccafd52ae4770455f18aebdefb325f6f1528fc9f69310a2ecade` |
| `tests/research_web/test_report_workflow_integration.py` | `976fda685f2610133461049bf0424367f94203190eeae18352f8eae3ef29d080` |
| `tests/research_web/test_sandbox.py` | `53dc6b631c6988e6f99d662c19acbd36e5bdde8b435ff35b273a5dd83d673408` |
| `tests/javascript/research_web_quality_tool.test.mjs` | `bfe3a2789754f3aabc514e97c8a97f7e05f918903d7389ce1fa44bcc10b4627d` |
| `logs/weekly-admission/run_offline_tests.py` | `d0f28303d699be4018863ad22f2c391b32e1bb58c0f4c2023f03ab76109f8d1c` |
