---
name: platform-breakout
description: 对单标的或最多 50 个明确观察标的执行先验窗口平台突破研究分类。
---
# 平台突破研究

运行 `scripts/calculate.py <relative-input.json>`。每个标的仅使用当前观测之前的 `lookback` 根日线：最高价定义阻力、最低价定义支撑，阻力附近触碰次数达到阈值且当前收盘严格越过缓冲边界才为确认突破；仅盘中越界而收盘未确认属于反例。

每次接受一个标的或最多 50 个明确观察标的，每标的最多 1,000 行、合计最多 50,000 行；禁止全市场多年分钟扫描。日期须逐标的严格递增，最新日期等于截止日，OHLC、证券身份、交易日历、单位与前复权口径必须等价。历史不足返回 `insufficient_history`，重复日期和不等价数据失败关闭。

输出是研究信号，不是交易或下单指令；样本、条件、反例、失效条件与数据截止日全部保留。原候选 Skill 制品在指定来源树中不可用，provenance 明确 `source unavailable`，未补造完整 SHA-256；因此 DataHub 映射 `callable=false`、catalog 初始 disabled，只有真实外部宿主登记器的 v2 HMAC receipt 才能启用。
