# 华安周报 Excel 有界传输窄修

日期：2026-10-23。宿主：macOS Mac mini。任务类型：Web 私有周报来源功能修复；本机仅验证离线传输和 Host 质量路径。真实 Office/Wind、模型、Windows/Linux、CI、部署均未执行。

## 实证与边界

- 原 `WindExcelClient._execute_wsd_once` 对 TDAYS 和单字段 WSD 均在预清理、每轮读取、结束清理使用 1000×20 单元格范围；`expected_columns` 只参与就绪判定。已记录的完整57取数预检于 16:19 开始，16:22:55 出现 `CommandError`，自有工作簿关闭到 16:23:55 仍超时，最终 `wind_cleanup_failed`。Mac 样本显示 Wind timer／公式缓存忙，未证明原始读取范围是供应商阻塞根因。
- 原始异常堆栈里的 `first_row_index.get` 出现在 `.value=None` 清理路径的 xlwings 转换器形状查询中；不能据此倒推原始读取阶段失败。本补丁只减少范围交互与区分阶段，不能宣称解除真实实例卡顿。
- 编辑前离线 RED：`_execute_wsd_once(..., max_rows=...)` 四项按预期因不接受此参数而失败；之后新增溢出、清理和阶段回归。没有真实 Excel、Wind、模型或网络调用。

## 改动

- 私有周报 TDAYS 传自然日窗口行数与1列，普通单字段 WSD 传自然日窗口行数与2列；印度 WSD 传该段官方已结束交易日数与2列。既有分段不超过366自然日，未知供应商结果仍只调用一次。
- 显式有界调用读取额外1行、1列。额外区域里 `0` 或 `False` 也视为数据并拒绝溢出。旧调用未传行界时仍读原 1000×20 范围。Host 的日期逐项核验和价格门未改。
- 当时自有范围以 `raw_value=None` 赋值作为清理尝试，避免 `.value=None` 的额外转换器形状查询。2026-10-23 后续原生数值对照已证实这一假设错误：旧值保持不变；当前 Mac 补丁已改用 `range.api.clear_contents()`，详见 `2026-10-23-etf-native-clear-semantics.md`。日志用请求 SHA-256、范围与 `preclear/anchor/read/cleanup/close` 阶段记录故障；有界清理失败保留所有权状态，后续关闭失败由 Provider 标记共享 worker poison。原始错误在客户端不被清理错误覆盖。

## 已执行验证

- 最初 RED：4项预期失败，报 `unexpected keyword argument 'max_rows'`。
- 离线近测：`tests/unit/test_wind_excel_instances.py`、`tests/unit/test_wind_adapter.py`、`tests/research_web/test_datahub_wind_excel_weekly.py`、`tests/research_web/test_report_weekly_gold_supplement.py`、`tests/research_web/test_report_weekly_data.py`，最终381 passed，22 warnings；日志 `logs/etf-excel/bounded-transport-near-tests-final.log`。测试进程在 `sys.modules` 预置空 `xlwings` 模块，并用 `--noconftest` 绕开该精简环境缺少 SQLAlchemy 的通用 fixture；未导入真实 Mac xlwings 原生实现。
- `ruff check`、`black --check`、`isort --check-only` 对4个近处 Python 文件通过；`mypy --follow-imports=silent` 对两个源码文件通过；`git diff --check` 通过。精简 pytest 环境的 `asyncio_mode` 配置警告及旧适配器 `utcnow` 弃用警告仍在，没有声称清零。

## 未完成与风险

- 挂起实例 Excel PID 68667 仍由主任务管理；本任务未查看、关闭、重启或重试真实 Wind。真实57项再次取数、Word投影、模型和正式报告质量门保持 `NOT_RUN`／原阻断状态。
- 当时的 `raw_value=None` 并未真正清空 Mac 单元格，后续清理语义修复独立记录。原始供应商繁忙仍可能在 Wind/Apple Event 阶段挂起；离线通过不认证供应商活性。
- 本子任务未提交、push、PR、CI或部署；交由主任务评审与整体验收。

主任务后续记录：用户已单独批准只重启旧PID68667，恢复后新PID20514的小样本两次查询及
自有工作簿关闭成功。此记录不改变上面的子任务“未操作Office”范围；原失败、恢复、后续
完整取数与正式验收分别见 `2026-10-23-etf-native-source-preflight.md`，不能据小样本认证稳定。
