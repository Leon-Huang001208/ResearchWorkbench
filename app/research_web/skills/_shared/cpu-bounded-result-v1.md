# CPU-bounded result v1

每个 calculator 返回一个 JSON 对象，至少包含以下字段：

- `protocol`: 固定为 `cpu_bounded_v1`。
- `as_of`: 数据截止时间或日期；未知时为 `null` 并在 limitations 说明。
- `parameters`: 实际采用的非秘密、规范化参数，不含路径、凭据或原始正文。
- `dataset_refs`: 本会话 DataHub/输入数据集引用及哈希，不嵌入数据内容。
- `status`: `complete`、`partial`、`insufficient_data` 或 `failed`。
- `limitations`: 口径、缺失、覆盖与降级说明数组。
- `method_version`: calculator 的固定方法版本。
- `provenance`: 遵循 `provenance-v1.md` 的对象。
- `row_delivery`: 记录完整处理的输入行数、内联输出行数、省略行数和交付模式；最多内联 128 条。
  超过时模式为 `summary_with_dataset_refs`，`dataset_refs_reused=true` 指向顶层规范化引用而不复制。

`dataset_refs` 与 `source_hashes` 各最多 32 项，复制到输出的单项文本最多 4096 字符。最终完整 JSON
envelope（含成功或错误结构）按 UTF-8 计不得超过 64 KiB；无法表达时返回小型、完整的
`workload_too_large`，metadata 仅含安全的 limit/actual/resource/reduce_scope，不依赖 sandbox 截断。

`partial` 不能冒充完整结果；发生预算超限时不返回截断计算结果。
所有 JSON 输出禁止 NaN/Infinity；数值转换和派生指标在序列化前必须验证为有限数。
