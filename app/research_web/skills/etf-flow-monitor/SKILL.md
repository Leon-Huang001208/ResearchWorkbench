---
name: etf-flow-monitor
description: 根据已提供的 ETF 份额变化与 NAV 计算估算资金流，并按用户提供的类型、行业和主题分类汇总。
---
# ETF 资金流监控

运行 `scripts/calculate.py <relative-input.json>`。资金流口径固定为 `(本期份额 - 上期份额) × 本期 NAV`，同时透明保留价格字段。

- 类型、行业、主题三类分类均必须由输入提供；缺失时失败关闭。
- NAV、份额或单位不等价时不得计算，也不得用证券代码猜分类。
- 输出仅供研究，不构成投资建议。
