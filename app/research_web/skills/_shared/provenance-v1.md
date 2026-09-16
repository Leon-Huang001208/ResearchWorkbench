# Provenance v1

公共来源对象只保存可审计引用：

- `dataset_refs`: 会话快照 ID、provider ID、查询 fingerprint 与 `as_of`。
- `source_hashes`: 输入文件、公共资源和方法文件的 SHA-256；不保存原始内容。
- `rights`: 公开数据使用 `public`；专业授权数据固定为 `internal-only`，不得进入公开制品。
- `transformations`: 有序方法步骤、参数和 `method_version`，不记录凭据或宿主路径。

任何来源哈希缺失、授权范围不清或字段单位/日期/复权不等价时，结果必须在 `limitations` 中降级，
必要时返回 `insufficient_data`，不能自行补造或转换口径。
