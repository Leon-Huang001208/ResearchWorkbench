---
name: earnings-report-monitor
description: 按证券、报告期、披露日及营收净利同比环比记录，计算披露进度与变化分布。
---
# 财报披露监控

运行 `scripts/calculate.py <relative-input.json>`。计算已披露数量、用户给定预期样本数对应的进度，以及四项增长率的固定分桶。

- 任一必填字段缺失、类型错误或记录重复时失败关闭。
- 不补算未提供同比、环比或披露日期。
- 未全部披露时状态为 partial；输出仅供研究。
