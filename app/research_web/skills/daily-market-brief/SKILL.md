---
name: daily-market-brief
description: 将已取得的市场快照、涨跌成交、行业主题与新闻证据编排为固定结构简报；不做事件或政策分析。
---
# 每日市场简报

仅使用会话内 DataHub 数据集引用和结构化输入。先运行 `scripts/calculate.py <relative-input.json>`，再按结果中的市场快照、宽度、行业、主题、新闻证据顺序回答。

- 不补造缺失行情、分类、来源或时间。
- 新闻只作证据编排，不判断政策传导、事件归因或次日走势。
- `partial`、`insufficient_data` 与 limitations 必须原样披露。
- 结果仅供研究，不构成投资建议。
