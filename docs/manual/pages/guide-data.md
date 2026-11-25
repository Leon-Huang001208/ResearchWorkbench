## 要完成什么

查看当前实例的数据能力和来源，判断某个来源是否真的可用于本次任务。这个任务只读目录，不执行供应商取数或模型调用。

## 前置条件

已登录 RWB。目录中的可用性属于当前账号和配置；换账号或修改来源配置后，需要重新检查。

## 最小可运行示例

在 **Research Web 主界面** 打开浏览器开发者工具的 Console，执行以下代码。不要在隔离文档页面的 Console 中执行，文档页不允许网络连接。

```javascript
const response = await fetch("/api/research/data/catalog");
if (!response.ok) throw new Error("HTTP " + response.status);
const catalog = await response.json();
console.table(catalog.sources.map(source => ({
  source: source.id,
  name: source.name,
  ...source.readiness
})));
```

## 预期结果

返回目录包含 sources。每个来源的 readiness 解释它的代码、配置、依赖、授权和可调用状态。重点看 callable、allowed、integration_state 和 limitations，而不是只看名称。

- callable 为 true：当前配置下具备调用条件，仍需检查本次数据质量。
- blocked_config / blocked_dependency：先完成配置或依赖；不要改用未声明的来源。
- untested：尚无健康验证记录，不等于可用，也不等于故障。

字段的完整定义见[数据目录与字段口径](../../../outputs/research-web-architecture/reference-data.html)。API 参数见 [DataHub 参考](../../../outputs/research-web-architecture/reference-api-datahub.html)。

## 从目录走向查询与快照

选择具体 capability、显式来源与业务参数后，再提交受支持的查询。研究台异步查询应保存返回记录的 id
（后续接口路径中的 query_id），读取状态，完成后检查冻结数据集。

任务 completed 只说明执行结束；还应检查数据状态、missing、limitations、实际覆盖范围和来源。既有快照与本次重新取数是不同操作。

## 常见错误

- 401：主界面会话过期，先重新登录。
- 有条目但没有实现绑定：目录只描述覆盖计划，不能提交未支持的组合。
- 日期、频率或复权超界：按该来源的 semantics 调整，不猜测支持范围。
- 空数据：保留空结果与原因，不补成 0，不自动认为来源没有相关事件。

## 相关参考

- [数据字段与金融语义](../../../outputs/research-web-architecture/reference-data.html)
- [API：DataHub 与交接](../../../outputs/research-web-architecture/reference-api-datahub.html)
- [API：资产观察](../../../outputs/research-web-architecture/reference-api-assets.html)
