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
  超过时模式为 `summary_with_dataset_refs`，并复用顶层规范化 `dataset_refs`，使 stdout 保持在
  64 KiB 内且不把有界投影冒充完整明细。

`partial` 不能冒充完整结果；发生预算超限时不返回截断计算结果。
所有 JSON 输出禁止 NaN/Infinity；数值转换和派生指标在序列化前必须验证为有限数。
