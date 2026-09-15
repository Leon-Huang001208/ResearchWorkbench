---
name: industry-crowding-monitor
description: 用行业与全市场预聚合成交额计算滚动成交占比及历史经验分位数。
---
# 行业拥挤度

运行 `scripts/calculate.py <relative-input.json>`。拥挤度固定为滚动窗口行业成交额之和除以同窗口全市场成交额之和；分位数为当前拥挤度在最多 percentile days 个同方法历史值中的 `<=` 经验排名。不读取或执行 Excel/VBA/公式，不扫描个股。

样本最多 50 个行业×1,000 日、总计不超过 50,000 条；rolling days 上限 250。交易日、截止日、provider、mapping/version、CNY 成交额、decimal 占比、分位数及不适用复权严格验证；同日市场总额不一致、历史不足或行业额超过市场额时失败关闭。安全相对 loader、有限数、64 KiB 完整输出与成功 stdout 无换行复用共享合约。

解释条件：行业和全市场成交额必须来自同一交易日历与映射版本。反例是主题事件导致短期高分位但没有持仓集中证据，不能直接解释为反转。失效条件包括行业分类调整、成交口径变化、停牌结构、历史窗口不足和市场总额缺失。high crowding 是 research signal，不是交易建议；真实 comparison receipt 缺失时保持 disabled。
