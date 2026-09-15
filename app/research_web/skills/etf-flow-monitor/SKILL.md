---
name: etf-flow-monitor
description: 根据已提供的 ETF 份额变化与 NAV 计算估算资金流，并按用户提供的类型、行业和主题分类汇总。
---
# ETF 资金流监控

运行 `scripts/calculate.py <relative-input.json>`。资金流口径固定为 `(本期份额 - 上期份额) × 本期 NAV`，同时透明保留价格字段。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、份额/NAV/价格/资金流单位、交易日期口径及不适用复权标记均须明确；未来日期和未审 provider 均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
输入文件必须是当前工作目录内的普通相对 JSON 文件，不接受文件或目录符号链接；份额差、资金流和分类汇总均经过有限数检查。全部记录参与汇总，最多内联 128 条；超出时由 `row_delivery` 明确省略计数和规范化数据集引用，sandbox stdout 上限为 64 KiB。
日期严格使用 `YYYY-MM-DD`，币种固定为 CNY；`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。
POSIX loader 从 cwd 目录描述符逐组件 no-follow 打开，Windows 校验打开句柄的最终路径和 reparse 属性。`dataset_refs` 与 `source_hashes` 各最多 32 项，输出文本单项最多 4096 字符；完整 JSON envelope 按 UTF-8 计不得超过 64 KiB，成功 stdout 不附加换行，无法表达时返回小型 `workload_too_large` 和 `reduce_scope`，不依赖 sandbox 截断。catalog 只接受严格 comparison evidence artifact 路径，分别重算当前版本 golden 与 comparison run 实际产物摘要，再以数值 `rtol=1e-6`/`atol=1e-8`、非数值严格一致做 JSON 业务比较；启用或回滚时再次验证 artifact 仍存在且绑定未变。

- 类型、行业、主题三类分类均必须由输入提供；缺失时失败关闭。
- NAV、份额或单位不等价时不得计算，也不得用证券代码猜分类。
- 输出仅供研究，不构成投资建议。
