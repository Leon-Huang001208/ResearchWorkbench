---
name: style-rotation-research
description: 对两条显式风格指数序列执行均线乖离或相对强弱动量二选一的透明研究分类。
---
# 风格轮动研究

运行 `scripts/calculate.py <relative-input.json>`。每次仅比较两条、同一交易日历和同一前复权口径的风格指数；输入必须提供顺序固定的 A/B descriptor，字段严格为 `role`、identity、version、tenor。A/B role 分别固定为 `style_a_index` / `style_b_index`，version 固定 `close_v1`，tenor 固定 `spot`，identity 必须是两个不同的非空受限字符业务标识。synthetic provider 精确绑定提交 fixture；`user_input` 可提供真实业务 identity 并在输出中原样回传。Wind/DataHub 只接受 field mapping 的精确生产身份白名单；当前白名单为空。A/B descriptor 交换、重复 identity、角色、版本或期限变化均以 `data_not_equivalent` 失败关闭。方法必须明确选择 `moving_average_deviation` 或 `relative_strength_momentum`，两种方法分别有独立 golden 验证。前者在相对比值乖离低于阈值时按移动平均方向分类；后者以两指数窗口收益差及其滞后变化的同号关系分类。符号冲突为 `neutral`，不得猜测。

少于所选方法所需窗口返回 `insufficient_history`；未知方法返回 `ambiguous_rule`。provider、字段、单位、日期和复权不等价返回 `data_not_equivalent`。所有结果包含样本、条件、冲突反例、失效条件和截止日，是研究信号而非交易或下单指令。

参考工作簿只读核验且未执行公式；当前 DataHub 未提供经核验的两风格指数联合契约，因此 `callable=false`、catalog 初始 disabled。只有真实 macOS Wind/Excel 外部宿主登记器签发、绑定当前版本与独立 actual input 的 v2 HMAC receipt 才能启用。
