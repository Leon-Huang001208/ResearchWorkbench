---
name: portfolio-benchmark-deviation
description: 依据已提供组合与基准持仓，计算行业权重差及市值、估值、增速的基准标准差偏离。
---
# 组合基准偏离

运行 `scripts/calculate.py <relative-input.json>`。复写公式口径为：组合/基准分别归一化权重；行业偏离为两者行业权重差；市值、PE TTM、净利润同比增速用加权均值之差除以基准证券的非加权样本标准差。

样本限定每侧最多 50 个证券；parameters 必须显式给出报告截止期、因子截止日期和行业映射版本，每条记录也必须显式携带与顶层完全相同的 `report_period`、`factor_date` 和 `industry_mapping_version`。同一 canonical `asset_id` 在组合与基准中必须映射到完全一致的行业、因子值和上述三个截止口径，任一混合值固定返回 `data_not_equivalent`。全部记录必须属于同一快照且日期等于因子日期。转换后每行 `0 < weight <= 1`、每侧总权重不超过 1，不支持隐式杠杆。当前 DataHub 的指数成分、组合持仓、因子和行业映射未形成经核验的联合契约，相关工具均为 `callable=false`；只接受 provider 与全部 dataset refs 一致的 synthetic/user_input。基准样本少于 2 或标准差为 0 时失败关闭，不以 0 代替。仅读取安全相对 JSON，不读取或执行 Excel/VBA/公式；完整 UTF-8 输出上限 64 KiB且成功 stdout 无换行。

解释条件：指标必须同日、同报告期与同口径。反例是 PE 为负或极端值造成标准差放大，z-score 低不代表经济偏离小；不同持仓日不能混成一个组合。失效条件包括行业映射版本变化、基准成分滞后、报告期错位、因子缺失/替换、总权重超过 100% 和样本分散度为零。结果是 research signal，不是交易建议；普通 JSON 自报不构成 receipt，真实宿主签名对照未验证前保持 disabled。
