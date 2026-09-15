---
name: earnings-preview-monitor
description: 计算业绩预告利润与增速区间中值，并仅汇总输入已提供的市值、估值、基金、北向与研究覆盖字段。
---
# 业绩预告监控

运行 `scripts/calculate.py <relative-input.json>`。区间中值使用上下限算术平均，增长中值按固定区间分桶。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、利润/增速/暴露等单位、披露日期口径及不适用复权标记均须明确；未来报告期、披露日或数据集引用均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
输入文件必须是当前工作目录内的普通相对 JSON 文件，不接受文件或目录符号链接；区间中值和已提供暴露的均值均经过有限数检查。每条记录的 `report_period` 必须与参数完全相同；全部记录参与汇总，最多内联 128 条，超出时由 `row_delivery` 明确省略计数和规范化数据集引用，sandbox stdout 上限为 64 KiB。
根、报告期、披露日和数据集日期严格使用 `YYYY-MM-DD`；`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。

- 利润和增速区间、证券、报告期、披露日为必填；区间倒置时失败关闭。
- 市值、估值、基金暴露、北向暴露和研究覆盖为可选；缺失保持 null 并列入 limitations。
- 不推断、插值或替换缺失字段；输出仅供研究。
