---
name: rate-ma-timing-research
description: 对单一资产与利率日频序列执行透明、滞后一日的利率均线研究信号计算。
---
# 利率均线择时研究

运行 `scripts/calculate.py <relative-input.json>`。本能力只处理一条最多 5,000 行的日频资产/利率序列：以给定窗口计算利率移动平均，只有当前利率相对均线的绝对乖离严格超过阈值时，均线下降产生 `rate_falling_above_deviation`，均线上升产生 `rate_rising_above_deviation`；相等或未越阈值不产生新信号。研究暴露使用上一观测的持久信号，避免同日数据前视。

输入必须严格符合 `references/input-schema.json`，并提供资产与利率两条序列各自的固定 identity、version 和 tenor；当前审核契约固定为 synthetic 资产现货指数与 10Y 政府债收益率。输出原样回传该 `series_identity` 以便追溯。日期严格递增且末日等于数据截止日；provider、字段、百分比/点位/小数单位、交易日语义和复权口径必须完全匹配。历史少于 `moving_average_window + 1` 返回 `insufficient_history`，身份、版本、期限、未来日期、未知字段、非有限数值或不等价来源均失败关闭。完整输出不超过 64 KiB，成功 stdout 无尾随换行。

结果是研究信号，不是交易、下单或个性化投资指令。样本、触发条件、未触发反例、失效条件和数据截止日均写入结果。失效条件包括利率定义或单位改变、交易日错配、融资成本缺失及利率制度切换。参考工作簿只读核验 SHA-256，未执行公式；当前 DataHub 无已核验的指数与宏观利率联合映射，因此保持 `callable=false` 和 catalog disabled。只有真实 macOS Wind/Excel 外部宿主登记器签发并绑定当前不可变版本的 v2 HMAC comparison receipt 才能启用。
