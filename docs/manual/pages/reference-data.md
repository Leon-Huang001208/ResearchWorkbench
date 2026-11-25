## 数据能力、来源与绑定

数据能力说明能查什么；来源描述由谁提供；绑定声明某个来源已实现哪些能力和数据集。账户可调用性还受配置、依赖和授权影响。

GET /api/research/data/catalog 是当前实例的目录入口。先按[数据指南](../../../outputs/research-web-architecture/guide-data.html)读取，再解释以下元信息。

## 来源状态字段

| 字段 | 含义 |
| --- | --- |
| id / name | 来源标识与名称。 |
| markets | 声明覆盖的市场，不等于每个标的都已有结果。 |
| fee | free、account、possibly_metered 或 unknown；没有已确认信息时不推定免费。 |
| limitations | 当前来源的已知限制。 |
| readiness.code_exists | 来源代码是否存在。 |
| readiness.integration_completed | 适配接线是否完成。 |
| readiness.configured / dependency_ready | 当前配置与依赖是否就绪。 |
| readiness.allowed / callable | 当前账号是否允许、当前条件下是否具备调用条件。 |
| readiness.integration_state | ready、blocked_config、blocked_dependency、disabled 或 error。 |
| readiness.health | 最近健康检查状态；untested 不是成功证据。 |

## 数据集语义

ProviderBinding 的 capability_id、source_id、datasets、implemented 和 semantics 用于描述实现范围。
具体数据集的频率、调整方式、查询默认值及单位，优先使用该绑定的声明和本次 manifest。

| 必须核对的口径 | 阅读方式 |
| --- | --- |
| 类型与字段 | 使用对应数据集字段定义；额外字段不能只按名称猜含义。 |
| 单位与币种 | 检查 units、currency 及来源说明；未知保持未知，不自行把手/股、元/万元互换。 |
| 频率与日期范围 | 检查请求范围和 actual_range；日期覆盖不足不能标成全量完成。 |
| 复权与调整 | 只使用该来源已声明支持的组合；不混用前复权、后复权和不复权。 |
| 数据时点与获取时间 | 区分 as_of 与 retrieved_at；拿到文件的时间不等于经济事件发生时间。 |
| 时区与交易日历 | 以来源和数据集的明确声明为准；未声明时保持未确认，不默认 UTC，也不把自然日当作交易日。 |
| 历史修订与 PIT | 查限制、版本与历史可得性证据；当前值不能直接当作历史时点已知值。 |
| 缺失与空值 | 保留 missing、limitations 与空结果；null、0 和未覆盖不是同一种状态。 |

## 查询完成与数据成功

研究台查询的 completed 只表示执行流程结束。数据结果自身可能为 complete、partial 或其他状态。
经 MCP 查询时还要检查 data_success。冻结快照记录一次查询的真实结果，不自动修正缺口或授予回测资格。

## 数据字段字典的范围

本页先定义当前目录与快照的阅读口径。各业务域字段表在 [API 参考](../../../outputs/research-web-architecture/reference-api.html) 中；未登记的响应结构明确缺失。
正在改造的数据接口和新来源只在确认其发布版本、字段尺度和验证样例后进入正式字典。

## 相关参考

- [DataHub API](../../../outputs/research-web-architecture/reference-api-datahub.html)
- [资产观察 API](../../../outputs/research-web-architecture/reference-api-assets.html)
- [MCP 取数与冻结读取的区别](../../../outputs/research-web-architecture/reference-mcp.html)
