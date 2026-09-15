---
name: portfolio-overlap
description: 对两个已提供组合的持仓权重归一化后计算确定性重合度与逐资产共同权重。
---
# 组合重合度

运行 `scripts/calculate.py <relative-input.json>`。先统一 percent/decimal，按组合和资产聚合重复行，再分别归一化；重合度固定为所有资产 `min(left_weight, right_weight)` 之和。

样本最多 5,000 条，且两个组合都必须有正权重；provider、mapping/version、披露日期、权重单位与不适用复权口径严格一致，否则返回 `data_not_equivalent`。输入使用安全相对 loader，所有记录参与计算，完整 UTF-8 输出超过 64 KiB 时返回 `workload_too_large`/`reduce_scope`，成功 stdout 无换行。

解释条件：适用于同一资产身份映射和同一截止口径。反例是名称相似但身份不同的资产，不能模糊合并。失效条件包括份额日期错位、衍生品名义敞口未展开、空组合、负权重或资产身份映射变化。重合度仅为 research signal，不是交易建议；真实对照 receipt 缺失时保持 disabled。
