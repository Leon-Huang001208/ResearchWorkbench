## 先分清三种角色

要查看七个业务域、`get_stock_kline`、`get_stock_quote` 等候选工具及完整输入设计，见[DataHub 工具与技能层设计](../../../outputs/research-web-architecture/design-weknora-datahub.html#41-工具面)。设计目标、源码候选与当前可用接口分别标注，不将待实现工具列作已上线能力。

| 角色 | 作用 | 阅读路径 |
| --- | --- | --- |
| RWB 入站 MCP | 外部客户端调用 RWB 的获准能力。 | 从本页与 MCP 使用指南开始。 |
| 上游金融 MCP | RWB 通过 DataHub 调用外部供应商。 | 查看数据来源目录与绑定。 |
| 客户端 / Registry / 安装 | 发现、配置并连接工具服务器。 | 查看 MCP Registry API；注册不等于调用成功。 |

## 授权范围

rwb.read 仅能读取明确批准的 public/synthetic 冻结材料。额外的取数权限需要另行明确授权，
并受客户端登记、来源白名单及当前账号配置约束；旧令牌不会因升级或刷新自动增权。

外部客户端不能选择账号目录、任意 URL、SQL 或主机命令，也不能取得厂商凭据。

## 冻结读取工具

| 工具 | 输入 | 返回与效果 |
| --- | --- | --- |
| rwb_capabilities_list | 无参数 | 返回 tools、scope、execution、contexts 与批准能力元数据；不分配后端。 |
| rwb_datasets_list | context_id | 返回该上下文的 context_id 和 items；只列获准数据集。 |
| rwb_dataset_read | context_id、dataset_id、offset=0、limit=100、view=rows | 读取已冻结行或 manifest；limit 最多500，不重新取源。 |
| rwb_source_read | context_id、可选 file_id、offset=0、limit=12000 | 不给 file_id 时列批准来源；给定时读取已冻结文本。 |

读取行默认 100、最多 500；文本最多 12000 字符。字节上限也会限制返回，不能把截断或缺页解释为完整结果。
材料列表中的标识叫 object_id；传给 dataset_id 或 file_id 时，使用对应材料的该值，不能按显示名称自行拼造。
工具返回的额外结构以实际响应为准，不在本页生成未登记的业务样例。

## `rwb_dataset_read`

```python
rwb_dataset_read(context_id, dataset_id, offset=0, limit=100, view="rows") -> dict
```

读取一个已获准数据集的冻结行或 manifest。读取前校验原件哈希，不重新向供应商取数。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| context_id | UUID 字符串 | 必填 | 当前授权返回的上下文标识。 |
| dataset_id | UUID 字符串 | 必填 | 数据集列表中该条材料的 object_id。 |
| offset | integer，≥0 | 0 | rows 视图跳过的记录数。 |
| limit | integer，1–500 | 100 | rows 视图本页最多返回的记录数。 |
| view | rows / manifest | rows | rows 返回分页数据；manifest 返回冻结清单。 |

### 返回值

返回字典。rows 视图包含以下字段；这张表描述已知返回字段，不排除额外元数据。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| items | array | 本页记录。字段结构取决于所读取的数据集。 |
| offset、limit | integer | 本次分页起点与上限。 |
| total | integer | 冻结行文件中的总记录数。 |
| partial | boolean | offset 大于0或本页未覆盖全部冻结行时为 true。 |
| manifest | object | 对应的冻结 manifest。 |
| manifest_sha256、rows_sha256 | string | 完整 manifest 与冻结行文件的校验值。 |
| fragment_sha256 | string | 本页记录片段的校验值。 |
| fragment_encoding | string | 固定为 utf8_json_compact。 |

partial 不能简单当成“还有下一页”：只要 offset 大于0，即使已到最后一页，它仍可能为 true。

### 示例

这是 MCP 工具调用对象；先将占位符替换为本次授权和材料列表实际返回的 UUID。

```json
{
  "name": "rwb_dataset_read",
  "arguments": {
    "context_id": "<本次授权的 context_id>",
    "dataset_id": "<材料的 object_id>",
    "offset": 0,
    "limit": 10,
    "view": "rows"
  }
}
```

预期得到最多10条冻结记录和上述分页/校验元数据。空页应结合 offset、total 判断；它不证明上游没有数据。

### 错误与限制

需要 rwb.read 及该上下文/材料的批准权限。格式、枚举和分页范围不合法时，工具输入校验会拒绝请求。
原件发生变化或不可校验时读取失败，例如 frozen_rows_changed、frozen_rows_invalid；不返回未经验证的替代数据。
响应还受字节上限约束。完整授权步骤见[MCP使用指南](../../../outputs/research-web-architecture/guide-mcp.html)，字段业务含义见[数据参考](../../../outputs/research-web-architecture/reference-data.html)。

## 有额外授权时的 DataHub 工具

本版说明已发布的通用调用；接口窗口设计中的分业务工具，待版本与字段确认后再接入，不在此宣称可用。

| 工具 | 输入概要 | 效果 |
| --- | --- | --- |
| rwb_datahub_query | request_id、source=ext_fred/ext_bls、series_id、start_date、end_date | 显式公开系列查询，区间最多366天，创建冻结结果；不执行模型。 |
| rwb_datahub_status | query_id、offset=0、limit=100 | 读取本次 grant 的状态与冻结结果；completed 后仍需核对 data_success。 |
| rwb_datahub_cancel | query_id | 取消准确的待完成查询，保留已完成数据。 |
| rwb_datahub_catalog | 无参数 | 配置来源授权下，列当前账号可调用来源、绑定与业务参数；不取源。 |
| rwb_datahub_business_query | request_id、query | 配置来源授权下，提交明确的 BusinessQuery；不接受凭据或任意地址。 |

前三项需要 rwb.read 与 rwb.data.query；后两项还需要 rwb.data.configured。该附加授权仅向已登记的相应客户端开放。
具体工具是否可见，应以当前令牌的 tools/list 为准。

## 幂等、异步和失败

同一个 request_id 只用于相同输入。保存返回的查询 id，再使用 status/cancel；超时后先查状态，不盲目重复取数。
维护中、后端缺失、范围无权、原件校验失败或返回过大均需保留错误，不降级成任意读取或自动扩大授权。

## 相关指南

- [完成一次获准只读调用](../../../outputs/research-web-architecture/guide-mcp.html)
- [查询结果与字段语义](../../../outputs/research-web-architecture/reference-data.html)
- [Registry 和安装 API](../../../outputs/research-web-architecture/reference-api-mcp.html)
