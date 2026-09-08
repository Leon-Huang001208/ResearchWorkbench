# 结构化结果约定

JSON 根对象使用 `schemaVersion: 1`，并包含：

- `source`：`title`、`publishedAt`、`accessStatus`和 `locatorScheme`。只有完整正文可读时才使用 `full_text`。
- `baseline`：基线类型、截止日期与描述。
- `claimLayers`：`facts`、`sourceOpinions`、`newEvidence`和 `inferences` 四组。每项有 `text` 与 `citations`；推断还要有 `premises`。
- `counterEvidence`：反向证据、对主结论的影响与定位。
- `scenarios`：名称、触发条件、时间窗、验证指标与失效信号。
- `actionAssessment`：标签、归因（研报明示/研报隐含/无明确操作含义）、适用对象、时间窗、条件、定位与失效信号。
- `limitations`：资料、工具、样本、口径和视觉证据限制。
- `knowledgeFramework`：`scope`、`nodes`和 `edges`。每条边使用已声明节点、关系类型与至少一个含 `locator` 的引用。

`citations` 中每项至少有非空 `source` 和 `locator`。校验失败时修正结构或明确降级，不删除限制字段来换取通过。
