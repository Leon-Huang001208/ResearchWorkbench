# 华安周报 Excel 助手范围清理语义窄修

日期：2026-10-23。宿主：macOS Mac mini。类型：私有周报来源功能修复。本子任务只编辑 integration worktree 并做离线验证；没有启动或操作 Office、Wind、模型、网络，也没有 Git 写、依赖安装或部署。

## 真实证据与失效模式

- 原生自有工作簿对照位于 `logs/etf-excel/native-clear-semantics-20261023.json`（feature worktree）：E1:E2 写入 11/22 后，`raw_value=None` 仍读出 11/22；`raw_value=''` 和 `clear_contents()` 均读出空字符串。对照结果为 `compared` 且自有资源清理完成。本子任务读取了该既有证据，没有重跑原生调用。
- 主任务观察的第35次 TDAYS 查询在环形助手地址复用后返回 `wind_spill_overflow`；末行哨兵内含旧日期。溢出拒绝正确，不能缩界、截断或跳过哨兵。这个清理缺陷不能解释原先 Wind/Excel CPU 99% 和 Apple Event 挂起；原始失败仍独立保留。
- 测试先用 Mac `raw_value=None` 不清空的 fake 复现相同地址第二轮夹带前轮行：RED `AssertionError`，旧日期 `2026-10-17` 遗留，见 `logs/etf-excel/clear-semantics-red.log`。
- 安装的 xlwings `main.Range.api` 直达 `_xlmac.Range.api` 的 appscript `self.xl`；其原生 `clear_contents()` 不查询形状。公开 `Range.clear_contents()` 包装会读写应用 `screen_updating` 且恢复未置于 `finally`，因此 Mac 直接调用 `range.api.clear_contents()`，其他平台沿用公开 `clear_contents()`。包装拒绝测试 RED 见 `logs/etf-excel/clear-semantics-native-red.log`。

## 改动与边界

- `WindExcelClient._execute_wsd_once` 预清理和 `finally` 清理共用原生清空路径。原有有界行列、额外一行一列哨兵、默认1000×20、两轮稳定、单次请求、原始异常优先、清理未知 poison 均保留。
- 既有 `wind_excel_spill_operation_failed` 只为 `WindFormulaError` 添加 `EXCEL_ERRORS` 或 `wind_spill_overflow` 白名单 `excel_error`；不打印任意异常全文或完整公式。
- 更新模块与 ETF 来源文档，修正此前 `raw_value=None` 可清空的错误假设，并在原有有界传输报告注明后续证伪与替代路径。

## 验证状态

离线 focused 47 passed，见 `logs/etf-excel/clear-semantics-focused-native.log`。最终近测对
`test_wind_excel_instances.py`、`test_wind_adapter.py`、`test_datahub_wind_excel_weekly.py`、
`test_report_weekly_gold_supplement.py`、`test_report_weekly_data.py` 共384 passed、21个既有
`utcnow` 弃用警告，见 `logs/etf-excel/clear-semantics-near-tests-final.log`。测试预置空
`xlwings` 模块，使用 `--noconftest`，未触碰原生应用。`ruff check`、`black --check`、
`isort --check-only` 对两个近处 Python 文件通过；`mypy --follow-imports=silent` 对客户端
源码通过；`git diff --check` 通过。测试中的57项为合成数据路径，不替代真实57项来源采集
或正式报告质量验收。Mac 原生命令在最终代码中的数值格复测由主任务单独执行。

## 质量评审 P2 修正

`test_native_clear_removes_stale_cells_when_helper_address_is_reused` 在测试作用域内显式将
`data_layer.adapters.wind.client.sys.platform` 固定为 `darwin`，因此 Ubuntu CI 也检查
Mac 原生命令路径，不会误走非 Mac 兼容分支。仅改该测试，生产客户端未改。
最终测试文件 SHA-256：`3ea9116de08bcab2439ea2b1bf0f47557d07139e4f8d4234d44d36771f742047`。
focused 47 passed；模块加载后先将外层平台模拟为 `linux`，目标测试内改为 `darwin`、
退出后恢复 `linux`，通过，日志分别为
`logs/etf-excel/clear-semantics-focused-platform-fix.log` 与
`logs/etf-excel/clear-semantics-linux-outer.log`。black、ruff、isort 和
`git diff --check` 均通过。第一次在 macOS Python 模块收集前全局改 `sys.platform` 的
模拟因缺少 `_sysconfigdata__linux_darwin` 失败，未作为测试结果；最终模拟只在已加载模块
的目标调用范围内设置外层平台。
