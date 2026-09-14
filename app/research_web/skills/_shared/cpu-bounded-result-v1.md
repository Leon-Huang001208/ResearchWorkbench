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

`partial` 不能冒充完整结果；发生预算超限时不返回截断计算结果。
