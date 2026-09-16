---
name: industry-quadrant-monitor
description: 用显式景气水平阈值与动量阈值，对预聚合行业分数划分四象限。
---
# 行业象限监控

运行 `scripts/calculate.py <relative-input.json>`。横向状态由 current score 与 level threshold 比较，动量由 current-prior 与 momentum threshold 比较，固定输出 high/low × improving/weakening 四象限；不扫描行业成分，也不推断阈值。

单次最多 50 个行业；每个行业只有一条指定观察日记录。当前 DataHub 预聚合表未建立已核验映射，标记 `callable=false`；只接受 synthetic/user_input，data contract provider 必须与每个 dataset ref 相同。截止日、观察日、mapping/version、分数/变化单位和不适用复权严格验证，重复行业或日期错位失败关闭。安全相对 JSON、有限数、完整 64 KiB 输出和成功 stdout 无换行均复用 `cpu_bounded_v1`。

解释条件：current/prior 来自同一预聚合方法版本。反例是高位轻微回落落入 high-but-weakening，不等于趋势反转。失效条件包括阈值漂移、指标方法变化、观察日期不齐、横截面样本变化和结构性断点。象限是 research signal，不是交易建议；仅宿主可信登记器签发并可复核的 comparison receipt 能解除 disabled。
