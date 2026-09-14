---
name: earnings-preview-monitor
description: 计算业绩预告利润与增速区间中值，并仅汇总输入已提供的市值、估值、基金、北向与研究覆盖字段。
---
# 业绩预告监控

运行 `scripts/calculate.py <relative-input.json>`。区间中值使用上下限算术平均，增长中值按固定区间分桶。

- 利润和增速区间、证券、报告期、披露日为必填；区间倒置时失败关闭。
- 市值、估值、基金暴露、北向暴露和研究覆盖为可选；缺失保持 null 并列入 limitations。
- 不推断、插值或替换缺失字段；输出仅供研究。
