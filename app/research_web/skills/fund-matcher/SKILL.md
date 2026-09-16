---
name: fund-matcher
description: 按用户明确的基金类别、目标指标与权重，对已提供候选基金做确定性距离排序。
---
# 基金匹配

运行 `scripts/calculate.py <relative-input.json>`。本能力只比较输入中同类别基金，使用透明的加权归一化绝对距离生成 0–100 匹配分数；分数是 research signal，不是收益预测或交易建议。

输入必须严格匹配 `references/input-schema.json`：样本是最多 50 只候选基金；截止日、候选指标截止日、provider、mapping/version、百分比/年/分数单位及不适用复权口径均须明确。输入文件只能是当前工作目录下的安全相对 JSON；所有数值与派生算术必须有限，完整 UTF-8 输出不超过 64 KiB且成功 stdout 无换行，超限返回完整 `workload_too_large`/`reduce_scope`。

当前 `datahub_get_fund_data` 不能一次提供经核验且同口径的全部收益、回撤、波动、费率与任职年限字段，因此映射明确为 `callable=false`；运行时只接受 `synthetic` 或已由用户按完整契约提供的 `user_input`，provider 与每个 dataset ref 不一致时返回 `data_not_equivalent`。仓库 `fixtures/source-artifact.json` 是 synthetic golden 的真实可哈希输入制品，不代表真实 Wind/Excel 对照。

解释条件：仅在同一基金类别、相同指标定义与同一截止口径下比较。反例是费用更低但回撤/波动口径不同的基金，不能凭综合分替代分项判断。失效条件包括基金策略变更、指标样本期不同、幸存者偏差、缺失候选或来源日期晚于截止日。样本、截止日、参数和限制均保留在结果；只有宿主可信登记器签名且绑定 synthetic/actual 输入、独立执行器与两侧结果的真实 comparison receipt 才能启用，普通 JSON 自报无效。
