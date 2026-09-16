---
name: portfolio-overlap
description: 对两个已提供组合的持仓权重归一化后计算确定性重合度与逐资产共同权重。
---
# 组合重合度

运行 `scripts/calculate.py <relative-input.json>`。先统一 percent/decimal，并要求转换后每行 `0 < weight <= 1`、每个组合总权重不超过 1；所有记录必须来自同一持仓快照，只在该快照内按组合和资产聚合重复行，再分别归一化。重合度固定为所有资产 `min(left_weight, right_weight)` 之和，不把杠杆隐式归一化掉。

样本最多 5,000 条，且两个组合都必须有正权重；快照截止日由输入 `as_of` 显式给出，所有记录必须与之相同。未核验的 DataHub 字段映射为 `callable=false`，只接受 synthetic/user_input。provider 必须与每个 dataset ref 一致，mapping/version、披露日期、权重单位与不适用复权口径严格一致，否则返回 `data_not_equivalent`。输入使用安全相对 loader，所有记录参与计算，完整 UTF-8 输出超过 64 KiB 时返回 `workload_too_large`/`reduce_scope`，成功 stdout 无换行。

解释条件：适用于同一资产身份映射和同一完整快照。反例是名称相似但身份不同的资产，不能模糊合并；跨日期持仓也不能聚合。失效条件包括份额日期错位、衍生品名义敞口未展开、空组合、负权重、总权重超过 100% 或资产身份映射变化。重合度仅为 research signal，不是交易建议；只有宿主可信登记器签名的独立对照 receipt 才能启用。
