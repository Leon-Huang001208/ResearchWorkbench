---
name: etf-flow-monitor
description: 根据已提供的 ETF 份额变化与 NAV 计算估算资金流，并按用户提供的类型、行业和主题分类汇总。
---
# ETF 资金流监控

运行 `scripts/calculate.py <relative-input.json>`。资金流口径固定为 `(本期份额 - 上期份额) × 本期 NAV`，同时透明保留价格字段。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、份额/NAV/价格/资金流单位、交易日期口径及不适用复权标记均须明确；未来日期和未审 provider 均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
日期严格使用 `YYYY-MM-DD`，币种固定为 CNY；`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。

- 类型、行业、主题三类分类均必须由输入提供；缺失时失败关闭。
- NAV、份额或单位不等价时不得计算，也不得用证券代码猜分类。
- 输出仅供研究，不构成投资建议。
