---
name: industry-crowding-monitor
description: 用行业与全市场预聚合成交额计算滚动成交占比及历史经验分位数。
---
# 行业拥挤度

运行 `scripts/calculate.py <relative-input.json>`。拥挤度固定为滚动窗口行业成交额之和除以同窗口全市场成交额之和；分位数为当前拥挤度在最多 percentile days 个同方法历史值中的 `<=` 经验排名。不读取或执行 Excel/VBA/公式，不扫描个股。

样本最多 50 个行业×1,000 日、总计不超过 50,000 条；rolling days 上限 250。所有行业必须共享完全相同的规范交易日序列与最新日期，并各自至少提供 `rolling_days + 1` 条原始观测，确保至少形成两个同口径滚动值；单个滚动观测固定以 `insufficient_history` 失败关闭。输出 `percentile_observations` 不得小于 2。同日互斥行业成交额合计不得超过全市场成交额。当前 DataHub 预聚合表未建立已核验映射，标记 `callable=false`；只接受 synthetic/user_input，provider 与全部 dataset refs 必须一致。交易日、截止日、mapping/version、CNY 成交额、decimal 占比、分位数及不适用复权严格验证；历史不足时失败关闭。安全相对 loader、有限数、64 KiB 完整输出与成功 stdout 无换行复用共享合约。

解释条件：行业和全市场成交额必须来自同一交易日历与映射版本。反例是主题事件导致短期高分位但没有持仓集中证据，不能直接解释为反转；缺少某行业某日也不能按不完整序列计算。失效条件包括行业分类调整、成交口径变化、停牌结构、历史窗口不足和市场总额缺失。high crowding 是 research signal，不是交易建议；普通 JSON 不能伪造 comparison receipt，真实宿主签名证据缺失时保持 disabled。
