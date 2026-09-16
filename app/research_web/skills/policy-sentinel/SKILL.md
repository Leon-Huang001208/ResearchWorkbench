---
name: policy-sentinel
description: 按关键词与日期筛选政策证据，输出可审计时间线、命中规则和来源已给出的潜在影响对象；不生成投资建议。
---
# 政策哨兵

只处理会话内已取得的政策记录。运行 `scripts/calculate.py <relative-input.json>`，逐条保留 evidence ID、来源引用、日期和命中关键词。

输入必须逐项匹配 `references/input-schema.json` 的 `data_contract`：provider、mapping/version、文档单位、发布日期口径和不适用复权标记均须明确；未来记录或未来数据集引用一律拒绝。该内置能力初始为 disabled，只有取得并登记 macOS Wind 对照 receipt 后才可启用。
输入文件必须是当前工作目录内的普通相对 JSON 文件，不接受文件或目录符号链接。计算会遍历全部证据，但最多内联 128 条命中；超出部分由 `row_delivery=summary_with_dataset_refs` 明确计数并引用规范化数据集，保证 sandbox stdout 低于 64 KiB，不会静默截断。
根、参数、政策记录和数据集日期严格使用 `YYYY-MM-DD`；`source_hashes` 存在时必须是对象，key 须为非空、首尾无空白且不含 CR/LF 或 Unicode 行/段分隔符的规范名称，value 须为 SHA-256；显式 null 或非规范 key 会被拒绝，字段缺失时结果降级为 partial 并披露 limitation。
输出 schema 同样严格约束 parameters、最多 32 项的 dataset refs 和 provenance：必填字段不可删除、类型/provider/日期/SHA-256 必须匹配且不允许额外字段。
POSIX loader 从 cwd 目录描述符逐组件 no-follow 打开，Windows 校验打开句柄的最终路径和 reparse 属性。`dataset_refs` 与 `source_hashes` 各最多 32 项，输出文本单项最多 4096 字符；完整 JSON envelope 按 UTF-8 计不得超过 64 KiB，成功 stdout 不附加换行，无法表达时返回小型 `workload_too_large` 和 `reduce_scope`，不依赖 sandbox 截断。catalog 只接受严格 comparison evidence artifact 路径，分别重算当前版本 golden 与 comparison run 实际产物摘要，再以数值 `rtol=1e-6`/`atol=1e-8`、非数值严格一致做 JSON 业务比较；启用或回滚时再次验证 artifact 仍存在且绑定未变。

- 缺少来源引用或证据 ID 时失败关闭。
- 潜在影响对象必须来自输入，不从标题猜测。
- 不把关键词命中解释为真实影响，不给出买卖或配置建议。
- 输出仅供研究。
