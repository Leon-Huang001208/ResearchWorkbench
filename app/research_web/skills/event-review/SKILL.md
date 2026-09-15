---
name: event-review
description: 对齐标的与基准日频序列，确定性计算事件窗收益、超额表现、成交变化及可用的 beta/alpha。
---
# 事件复盘

输入必须包含同一口径的标的和基准日频序列及事件日期。运行 `scripts/calculate.py <relative-input.json>` 后报告窗口、收益、超额和量能变化。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、标的/基准单位、交易日期口径及 `forward` 复权均须明确；缺失或错误复权、未来行情或未来数据集引用返回稳定错误。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
输入文件必须是当前工作目录内的普通相对 JSON 文件，不接受文件或目录符号链接；所有收益、成交变化、方差、beta 与 alpha 派生值都经过有限数检查。全部序列参与计算，结果窗最多内联 128 条；超出时由 `row_delivery` 明确省略计数和规范化数据集引用，sandbox stdout 上限为 64 KiB。
根、事件、行情记录和数据集日期严格使用 `YYYY-MM-DD`；`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。

- 日期不对齐或事件窗不完整时失败关闭。
- beta/alpha 只用事件前配对日收益；少于 20 个观测或基准方差为零时返回 unavailable，绝不使用默认 beta。
- 不根据收益反推事件原因或投资建议。
