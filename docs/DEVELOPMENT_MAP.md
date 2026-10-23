# Research Workbench Development Map

华安 Excel 主源为 datahub/providers_wind_excel_weekly.py，weekly_sources.py 校验锁定合同，weekly_data.py 独立复算日历、端点及采集时间，evidence.py 输出冻结事实。runtime.py/weekly-production.mjs 禁止本轮 Excel 日程并区分历史验收。近测试 test_datahub_wind_excel_weekly.py、test_report_weekly_acceptance.py 和 JS weekly production；连接兼容修复自身无新拓扑，完整来源分支已更新09/10图。

2026-10-23 华安周报 Excel 预检发现 macOS `lsappinfo` PID 输出与 xlwings 解析不兼容。
`data_layer/adapters/wind/excel_instances.py` 只在已复现的 Mac 整数解析失败后规范化该私有模块的
PID 读取；无法确认实例身份时不另开 Excel。`client.py` 同时识别 Mac 溢出区域的空字符串，保留零值。
未新增 HTTP、数据源、执行引擎、持久格式或依赖，既有架构图拓扑保持；详见
[Wind Excel 模块](modules/data_layer_adapters_wind.md)。实采覆盖、生产源切换与成稿验收分别记录，
不能由这项连接修复替代。
