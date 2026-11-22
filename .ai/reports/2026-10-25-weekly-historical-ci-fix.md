# 历史周报 CI 回归修复（2026-10-25）

宿主：macOS；任务：离线历史生命周期测试修复；范围仅历史测试文件，不修改生产 Runtime、原共享 fixture、Native 操作员、权限或 CI。

## RED 与根因

编辑前用原三个 CI 节点重现 `3 failed`。日志为 `logs/weekly-admission/historical-ci-red.log`，JUnit 同名前缀 `.xml`。

首错路径：历史测试 → `test_report_weekly_quality._runtime_fixture` → 将整个 `weekly_data` 替换为只包含 build/materialize 的 SimpleNamespace → Runtime `_submit_weekly` 调用真实 `weekly_execution.projection` → `weekly_verified_evidence` 导入不存在的 `assess_weekly_snapshot`，产生 ImportError。因此尚未到达 Sender；原测试最后的 sent=0 和 owner recovery 原 failure 断言掩盖了这个首错。

这不是生产代码漏发，也不能将期望的一次提交改成零次。恢复错误应独立记录 `recovery_failure_code`，原失败字段应保留。

## 变更与 SourceSpec 绑定

唯一 Python 源文件：`tests/research_web/test_report_weekly_historical_acceptance.py`。

SHA-256：`f7b4d8e402db2e01a118a1f210991d57975898f2fbfa3f84af1f0daaba09645c`。

新增历史测试专用 helper，使用真实 ResearchService、catalog、WindExcelWeeklyProvider、可信 context/evidence、scope、native admission、send、持久 claim 和 receipt。Provider 外部响应使用原合成 Client，Native 仅传输隔离；凭据隔离沿原内存 keyring fixture。发布资源使用 catalog 现有 assets 根，所有 source/export/coverage/observation 引用与哈希同步绑定。

仅隔离 session 创建的模型配置、模型凭据、固定测试日期及工作簿 materialization。没有 mock trusted_weekly_context、weekly_verified_evidence、projection、native admission、实际 send 或 claim。原独立 Sender、script、渲染与质量测试保留。

断言先确认采集数据门 passed、历史 acquisition_kind、v2 scope、admission_at 和原 Run/SID/key 的持久 claim，再检查 unknown/accepted。断连重试与 accepted 重启均保持一次 session.prompt；撤权恢复只写 recovery_failure_code。恢复前后比较 SID、key、原 failure、快照原始字节/哈希、context 哈希及包含采集/冻结时间的原 assessment。

## 实际命令和证据

工作目录：`/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-weekly-admission-20261024`。

所有 pytest 命令均使用以下前缀（使用已批环境，不安装依赖）：

```bash
PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages /Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python logs/weekly-admission/run_offline_tests.py
```

RED 参数：

```bash
--confcutdir=tests/research_web -q -o addopts= tests/research_web/test_report_weekly_historical_acceptance.py::test_historical_runtime_deduplicates_and_preserves_unknown_submission tests/research_web/test_report_weekly_historical_acceptance.py::test_historical_startup_only_observes_accepted_work_and_rechecks_owner --junitxml=logs/weekly-admission/historical-ci-red.xml
```

同目标 GREEN 改用 `historical-ci-green.xml` / `.log`：`3 passed`，12.71 秒。补充证据保留断言后，完整相邻回归参数为：

```bash
--confcutdir=tests/research_web -q -o addopts= tests/research_web/test_report_weekly_historical_acceptance.py tests/research_web/test_report_weekly_quality.py tests/research_web/test_report_weekly_admission.py --junitxml=logs/weekly-admission/historical-ci-regression.xml
```

结果：`100 passed, 1 warning in 102.15s`。完整 stdout/stderr 在 `logs/weekly-admission/historical-ci-regression.log`；warning 是现有 Starlette BlockingPortal 弃用提示。runner 注入禁止 Office 访问的 xlwings，并使用默认 private 临时根。

静态命令使用相同 Python 与扩展 site-packages，分别执行 `-m ruff check`、`-m black --check`、`-m isort --check-only`，目标均为上述唯一 Python 文件；全部通过，日志 `historical-ci-{ruff,black,isort}.log`。`git diff --check` 通过。`node scripts/git_safety.mjs check --project /Users/leon/Desktop/Projects/ResearchWorkbench` 返回 fsck PASS、无锁、gc.auto=0、maintenance.auto=false。

## 未验证项与交接

这是历史生命周期离线回归，不认证真实 Wind、模型、Office、Word/图表质量、常驻部署或真实 dataRoot。未提交、push 或更改服务。新测试属于产品非豁免文件，P7 不涵盖此修改；主任务须冻结 P8、更新 Native pin，并将独立规格/质量评审、新 head CI 与最终安装证据绑定，不可扩大 tests 例外绕过。
