# 每日市场点评 Workflow Studio

## 交付范围

- 将每日市场点评从静态提示词升级为 `workflow_specs/daily_market_commentary.yaml` 驱动的 Workflow。
- 原生 Tool 负责市场、新闻和 ETF 映射数据；DSH 仅运行分析与叙事 Skill。
- 默认产物为可编辑 `ReportDocument`，包含三段正文与两张原生图表数据；Markdown/Word 是其投影。
- `/api/v2/workflows/daily-market-commentary` 支持读取与保存已校验配置；内容生产中心提供可视化编辑入口。
- 配置默认在 Asia/Shanghai 的工作日 16:15 调度；现有交易日历当前以工作日近似，交易所节假日历接入前需要人工暂停节假日任务。

## 验证证据

- `.venv/bin/python -m compileall -q core/contracts/runtime.py services/daily_market_commentary_spec.py services/market_commentary_workflow.py services/runtime_workflow_service.py services/daily_market_commentary_scheduler.py app/api/routes/runtime_workflows.py`
- `node --check app/web/static/js/commentary.js && node --check app/web/static/js/app.js`
- `.venv/bin/python -m pytest tests/unit/test_runtime_kernel.py tests/unit/test_dsh_adapter.py tests/unit/test_dsh_bundle.py -q`：14 passed。

## 未验证项

- 未以真实模型凭据自动触发定时任务；手动运行和 DSH Host 健康状态仍由部署环境决定。
- 本轮未在交易所节假日运行，因此调度器的工作日近似不等同于完整交易所日历。
