# 金融数据 MCP 接入 DataHub

金融数据网关固定为 `https://www.huaanifd.com/finance-data/mcp`，在 DataHub 登记为
`ext_finance_mcp`。它是现有 `external_data` 能力的 Provider，不是第二个数据平台。
厂商 Key 和 Windows 转发令牌由上游管理；本账号只保存 `FINANCE_MCP_TOKEN` 对应的一份
客户端令牌，复用 DataHub 的 OS 凭据库。令牌不进入模型参数、普通配置、快照或日志。

## 查询入口

`parameters.dataset` 使用网关原生工具名；`arguments_json` 是该工具的参数对象：

| dataset | 参数与用途 |
| --- | --- |
| `catalog` | 本地登记信息，不请求上游 |
| `finance_sources` | `{}`；发现八家厂商及配置状态 |
| `finance_list_tools` | `provider`、`service`；读取原生工具及 inputSchema |
| `finance_call` | `provider`、`service`、`name`、`arguments`；按运行时 schema 查询 |
| `alpha_query` | `operation`、`arguments`；Alpha 派投研资料 |
| `gangtise_query` | `operation`、`arguments`；岗底斯数据 |

例如原有 DataHub 业务查询：

```json
{
  "capability": "external_data",
  "source": "ext_finance_mcp",
  "parameters": {
    "dataset": "gangtise_query",
    "arguments_json": "{\"operation\":\"查询A股日K线\",\"arguments\":{\"securityList\":[\"600519.SH\"],\"startDate\":\"2026-11-16\",\"endDate\":\"2026-11-19\"}}",
    "limit": 20
  },
  "refresh": true
}
```

先查 `finance_sources`；六家原生工具型厂商再查 `finance_list_tools`。
Alpha 派和岗底斯按返回的 operations 调用。`windows_worker` 是配置状态，不是取数成功。
网关 `ok:true` 也不代表厂商业务成功，MCP 错误、网关错误和厂商状态分别判断。

### 岗底斯参数契约

网关对 `gangtise_query` 不返回逐 operation 的 inputSchema（`finance_list_tools` 报
`未知 MCP 厂商`），空参数调用只得到 `上游 HTTP 400`。厂商《金融数据文档汇总》中的
OpenAPI 文档（92 份）给出了每个 operation 的必选参数，可作为调用前的契约依据；
它以厂商 REST 入参书写，经网关后参数名保持一致。下列为文本与宏观两类当前最缺的接口。
本节参数由文档整理，链路本身尚未逐个调用验证；首次接入时仍须以实际响应为准。

| operation | 必选参数 | 说明 |
| --- | --- | --- |
| `查询A股公告列表` | `from`、`size` | `size` 上限 50，只取单页；`startTime`／`endTime` 用 `yyyy-MM-dd`，可带 `keyword`、`securityList`、`categoryList` |
| `下载A股公告文件` | `announcementId`、`fileType` | `fileType` 1=原始 PDF、2=Markdown；文档参数表误写为 `reportId`，以 URL 示例的 `announcementId` 为准，调用时先用 `announcementId`，400 再试 `reportId` |
| `查询内资研报列表` | `from`、`size` | `size` 上限 50；另有 `categoryList`、`industryList`、`securityList`、`brokerList`、`ratingList`、`sourceList` |
| `下载内资研报文件` | `reportId`、`fileType` | `fileType` 1=原始 PDF、2=Markdown |
| `查询纪要列表` | `from`、`size` | `size` 上限 50；另有 `keyword`、`sourceList`、`researchAreaList`、`securityList` |
| `下载纪要文件` | `summaryId` | `fileType` 仅对会议平台来源生效，1=原始内容、2=HTML |
| `查询行业指标列表` | `keyword` | 必填且需具体词（如"空调"），不要传整句；`limit` 上限 200，返回 `indicatorId`、`unit`、`frequency` |
| `获取行业指标数据` | `indicatorIdList`、`startDate`、`endDate` | 返回 `fieldList`／`dataList`，首列为 `date`，数值以字符串返回 |
| `知识库查询` | `query` | `top` 默认 10、上限 20；`resourceTypes` 用 10 券商研报、11 外资研报、50 A 股公告、51 港股公告、60 会议纪要、70 调研纪要、90 产业公众号圈定范围 |
| `知识库溯源` | `resourceType`、`sourceId` | 取回原文；`40`（首席分析师观点）暂不支持 |

列表接口分页必须显式翻页：`from` 和 `size` 都是必填项，默认只返回一页，
`total` 大于已取行数时不能当作完整结果。公告列表的 `announcementDate`（公告注明日期）
与 `publishTime`（东八区发布时间）是两个字段，正式引用分开记录。

试用账号权限按接口不同：公告列表回溯 1 年；研报、纪要及路演等日程类接口 1 个月；
行情与三表 3 年。积分口径厂商自身不一致：接口页写公告、研报、纪要列表 0.01/条，
而《OpenAPI 接口计分标准》写 0.1/条；文件下载两份一致（公告 10/篇、内资研报 20/篇、
纪要 50/篇），行业指标数据 3/指标，指标检索不消耗积分。以厂商结算页为准，
不要把 `total` 当作可一次性下载的条数。

`知识库查询`按 10 积分/次计费，但它一次可跨公告、研报、纪要检索，返回
`content` 切片、`sourceId`、`resourceType` 及页码，可直接接`知识库溯源`取全文，
因此在 `financial_docs` 域优先于逐个列表接口。
两处入口的选择标准是：已知证券和时间窗、需要结构化字段（公告日、发布方、评级）时用列表接口；
按主题或跨品种检索、只需要命中段落时用知识库。列表结果只含详情摘要，不含原件，
原件仍需下载接口或溯源接口另取并单独记录。

## 结果与证据

保存 MCP 工具结果的 JSON 序列化记录及原生 structuredContent/文本，不声称是原始 HTTP
字节抓包。岗底斯表格将原 fieldList/list 对应为行对象，保留字段名称和空值；异构厂商输出
保留 provider_payload，不猜测数值语义。未认证的异构业务结果不标记 quality_accepted。
原件、快照、查询记录继续由 DataHub 保存。单位、币种、复权、分页及 PIT 未核验时明确未知；
不提供正式历史时点或回测等价保证。

2026-11-23 实际鉴权和五工具发现通过，八家厂商均返回目录登记。
岗底斯 `600519.SH`、2026-11-16 至 19 的日 K 线通过 DataHub 新适配实取 4 行。
其余厂商本轮未逐家取数；通联额度按实际响应判断，不沿用文档中的旧额度结论。
源码验证、CI、生产部署、正式 RWB MCP 调用分别验收。

## WeKnora 使用

通过正式 RWB MCP 的 `rwb_datahub_catalog` 发现账号当前可调用来源，然后用
`rwb_datahub_business_query` 提交以上业务查询，沿 `rwb_datahub_status` 读取冻结结果。
这需要新确认的 `rwb.data.configured` scope；原 `rwb.read` 和 FRED/BLS 的
`rwb.data.query` 授权不自动扩权。WeKnora 不保存厂商密钥，也不直接绕过 DataHub 取数。
