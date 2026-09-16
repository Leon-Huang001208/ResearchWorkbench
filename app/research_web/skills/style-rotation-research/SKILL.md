---
name: style-rotation-research
description: 对两条显式风格指数序列执行均线乖离或相对强弱动量二选一的透明研究分类。
---
# 风格轮动研究

运行 `scripts/calculate.py <relative-input.json>`。每次仅比较两条、同一交易日历和同一前复权口径的风格指数，方法必须明确选择 `moving_average_deviation` 或 `relative_strength_momentum`。前者在相对比值乖离低于阈值时按移动平均方向分类；后者以两指数窗口收益差及其滞后变化的同号关系分类。符号冲突为 `neutral`，不得猜测。

少于所选方法所需窗口返回 `insufficient_history`；未知方法返回 `ambiguous_rule`。provider、字段、单位、日期和复权不等价返回 `data_not_equivalent`。所有结果包含样本、条件、冲突反例、失效条件和截止日，是研究信号而非交易或下单指令。

参考工作簿只读核验且未执行公式；当前 DataHub 未提供经核验的两风格指数联合契约，因此 `callable=false`、catalog 初始 disabled。只有真实 macOS Wind/Excel 外部宿主登记器签发、绑定当前版本与独立 actual input 的 v2 HMAC receipt 才能启用。
