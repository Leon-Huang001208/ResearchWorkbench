---
name: portfolio-benchmark-deviation
description: 依据已提供组合与基准持仓，计算行业权重差及市值、估值、增速的基准标准差偏离。
---
# 组合基准偏离

运行 `scripts/calculate.py <relative-input.json>`。复写公式口径为：组合/基准分别归一化权重；行业偏离为两者行业权重差；市值、PE TTM、净利润同比增速用加权均值之差除以基准证券的非加权样本标准差。

样本限定每侧最多 50 个证券；截止日、持仓/因子日期、provider、mapping/version、CNY 亿元、倍数、百分比、权重单位及不适用复权均严格验证。基准样本少于 2 或标准差为 0 时失败关闭，不以 0 代替。仅读取安全相对 JSON，不读取或执行 Excel/VBA/公式；完整 UTF-8 输出上限 64 KiB且成功 stdout 无换行。

解释条件：指标必须同日、同报告期与同口径。反例是 PE 为负或极端值造成标准差放大，z-score 低不代表经济偏离小。失效条件包括行业映射版本变化、基准成分滞后、报告期错位、因子缺失/替换和样本分散度为零。结果是 research signal，不是交易建议；comparison receipt 未实际验证前保持 disabled。
