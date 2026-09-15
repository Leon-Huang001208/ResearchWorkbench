---
name: daily-market-brief
description: 将已取得的市场快照、涨跌成交、行业主题与新闻证据编排为固定结构简报；不做事件或政策分析。
---
# 每日市场简报

仅使用会话内 DataHub 数据集引用和结构化输入。先运行 `scripts/calculate.py <relative-input.json>`，再按结果中的市场快照、宽度、行业、主题、新闻证据顺序回答。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、单位、交易日期口径和不适用复权标记均须明确；任何记录或数据集日期晚于 `as_of` 均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
日期严格使用 `YYYY-MM-DD`；市场快照、宽度、行业、主题和新闻集合均为必填，宽度计数只能是非负整数，币种固定为 CNY。`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。

- 不补造缺失行情、分类、来源或时间。
- 新闻只作证据编排，不判断政策传导、事件归因或次日走势。
- `partial`、`insufficient_data` 与 limitations 必须原样披露。
- 结果仅供研究，不构成投资建议。
