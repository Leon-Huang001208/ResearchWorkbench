---
name: earnings-preview-monitor
description: 计算业绩预告利润与增速区间中值，并仅汇总输入已提供的市值、估值、基金、北向与研究覆盖字段。
---
# 业绩预告监控

运行 `scripts/calculate.py <relative-input.json>`。区间中值使用上下限算术平均，增长中值按固定区间分桶。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、利润/增速/暴露等单位、披露日期口径及不适用复权标记均须明确；未来报告期、披露日或数据集引用均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
根、报告期、披露日和数据集日期严格使用 `YYYY-MM-DD`；`source_hashes` 存在时必须是 SHA-256，缺失时结果降级为 partial 并披露 limitation。

- 利润和增速区间、证券、报告期、披露日为必填；区间倒置时失败关闭。
- 市值、估值、基金暴露、北向暴露和研究覆盖为可选；缺失保持 null 并列入 limitations。
- 不推断、插值或替换缺失字段；输出仅供研究。
