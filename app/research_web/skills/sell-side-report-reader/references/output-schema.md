# 结构化结果约定

JSON 根对象使用 `schemaVersion: 1`，并包含：

- `resultLevel`：固定为“重要”、“有限增量”、“框架价值”或“可跳过”之一。前两级必须至少有一项 `newEvidence`。
- `source`：`title`、`publishedAt`、`accessStatus`和 `locatorScheme`。只有完整正文可读时才使用 `full_text`。
- `baseline`：基线类型、截止日期与描述。
- `claimLayers`：`facts`、`sourceOpinions`、`newEvidence`和 `inferences` 四个字段必须都存在且为数组，但单个数组可以为空。非空项有 `text` 与 `citations`；推断还要有 `premises`。`facts` 和 `sourceOpinions` 不得同时为空，避免无任何来源信息的空壳结果。
- `noDeltaExplanation`：当 `newEvidence=[]` 时必填，说明比较基线、未发现增量的原因与仍保留的价值；`limitations` 同时记录证据范围限制。
- `counterEvidence`：反向证据、对主结论的影响与定位。
- `scenarios`：名称、触发条件、时间窗、验证指标与失效信号。
- `actionAssessment`：标签、归因（研报明示/研报隐含/无明确操作含义）、适用对象、时间窗、条件、关键假设 `keyAssumptions`、验证指标 `validationIndicators`、来源定位与失效信号。两个新字段都必须是非空文本列表。
- `limitations`：资料、工具、样本、口径和视觉证据限制。
- `knowledgeFramework`：`scope`、`nodes`和 `edges`，节点数必须在 2–12 之间。节点 `id` 必须非空且唯一；每条边的 `from` 和 `to` 必须指向已声明的不同节点，并带关系类型与至少一个含 `locator` 的引用。

`citations` 中每项至少有非空 `source` 和 `locator`。校验失败时修正结构或明确降级，不删除限制字段来换取通过。

所有文本必须是 XML 1.0 可表达字符；NUL、禁用控制码和非法 Unicode 码点会使校验失败，不会在绘图时静默删除。
