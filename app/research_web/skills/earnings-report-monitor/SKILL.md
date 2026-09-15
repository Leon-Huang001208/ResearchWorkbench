---
name: earnings-report-monitor
description: 按证券、报告期、披露日及营收净利同比环比记录，计算披露进度与变化分布。
---
# 财报披露监控

运行 `scripts/calculate.py <relative-input.json>`。计算已披露数量、用户给定预期样本数对应的进度，以及四项增长率的固定分桶。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、金额/增速单位、披露日期口径及不适用复权标记均须明确；未来报告期、披露日或数据集引用均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
根、报告期、披露日和数据集日期严格使用 `YYYY-MM-DD`；`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。

- 任一必填字段缺失、类型错误或记录重复时失败关闭。
- 不补算未提供同比、环比或披露日期。
- 未全部披露时状态为 partial；输出仅供研究。
