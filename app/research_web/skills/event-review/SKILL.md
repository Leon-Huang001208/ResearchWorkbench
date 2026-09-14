---
name: event-review
description: 对齐标的与基准日频序列，确定性计算事件窗收益、超额表现、成交变化及可用的 beta/alpha。
---
# 事件复盘

输入必须包含同一口径的标的和基准日频序列及事件日期。运行 `scripts/calculate.py <relative-input.json>` 后报告窗口、收益、超额和量能变化。

- 日期不对齐或事件窗不完整时失败关闭。
- beta/alpha 只用事件前配对日收益；少于 20 个观测或基准方差为零时返回 unavailable，绝不使用默认 beta。
- 不根据收益反推事件原因或投资建议。
