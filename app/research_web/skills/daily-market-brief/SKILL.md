---
name: daily-market-brief
description: 将已取得的市场快照、涨跌成交、行业主题与新闻证据编排为固定结构简报；不做事件或政策分析。
---
# 每日市场简报

仅使用会话内 DataHub 数据集引用和结构化输入。先运行 `scripts/calculate.py <relative-input.json>`，再按结果中的市场快照、宽度、行业、主题、新闻证据顺序回答。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、单位、交易日期口径和不适用复权标记均须明确；任何记录或数据集日期晚于 `as_of` 均拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
输入文件必须是当前工作目录内的普通相对 JSON 文件，不接受文件或目录符号链接；数值转换、聚合和派生值均经过有限数检查。计算会遍历全部输入，但最多内联 128 条结果；超出部分通过 `row_delivery=summary_with_dataset_refs` 明确计数并引用规范化数据集，保证 sandbox stdout 低于 64 KiB，不会静默截断。
日期严格使用 `YYYY-MM-DD`；市场快照、宽度、行业、主题和新闻集合均为必填，宽度计数只能是非负整数，币种固定为 CNY。`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。
输出 schema 同样严格约束 parameters、最多 32 项的 dataset refs 和 provenance：必填字段不可删除、类型/provider/日期/SHA-256 必须匹配且不允许额外字段。
POSIX loader 从 cwd 目录描述符逐组件 no-follow 打开，Windows 校验打开句柄的最终路径和 reparse 属性。`dataset_refs` 与 `source_hashes` 各最多 32 项，输出文本单项最多 4096 字符；完整 JSON envelope 按 UTF-8 计不得超过 64 KiB，成功 stdout 不附加换行，无法表达时返回小型 `workload_too_large` 和 `reduce_scope`，不依赖 sandbox 截断。catalog 只接受严格 comparison evidence artifact 路径，分别重算当前版本 golden 与 comparison run 实际产物摘要，再以数值 `rtol=1e-6`/`atol=1e-8`、非数值严格一致做 JSON 业务比较；启用或回滚时再次验证 artifact 仍存在且绑定未变。

- 不补造缺失行情、分类、来源或时间。
- 新闻只作证据编排，不判断政策传导、事件归因或次日走势。
- `partial`、`insufficient_data` 与 limitations 必须原样披露。
- 结果仅供研究，不构成投资建议。
