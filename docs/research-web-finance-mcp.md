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

### 岗底斯文本与宏观参数

现有实测记录（`.ai/reports/2026-11-26-finance-mcp-live-verification.md`，未跟踪）中，
`finance_list_tools` 对 `provider=gangtise` 返回 `未知 MCP 厂商`，未取得逐 operation 的
inputSchema；空参数调用只得到 `上游 HTTP 400`，没有字段级提示。厂商《金融数据文档汇总》
共 92 份 Markdown，其中 67 份含请求参数表（62 份在标准「五、请求参数」章节，
另 5 份在别的章节，含 UTF-16 编码的 `查询群ID.md`）；其余 25 份是常量 ID 表、
计分标准、更新日志及无请求参数的说明页。
下列为文本与宏观两类当前最缺的接口；主营构成、估值分析、前十大股东、题材等
金融数据接口的参数仍在厂商文档中，本节不展开。本节参数按厂商文档整理。
日 K 线、公告列表、内资研报列表已各有一次真实取数记录；其中日 K 线用
`securityList`／`startDate`／`endDate`，而公告与研报列表在记录中沿用同一组参数名，
厂商文档却写 `startTime`／`endTime`，网关实际接受的列表参数名待确认。
其余 operation 未逐个验证，首次接入以实际响应为准。

| operation | 必选参数 | 说明 |
| --- | --- | --- |
| `查询A股公告列表` | `from`、`size` | `size` 上限 50，只取单页；`startTime`／`endTime` 完整格式 `yyyy-MM-dd HH:mm:ss`，厂商兼容 `yyyy-MM-dd` 补全；可带 `keyword`、`securityList`、`categoryList` |
| `下载A股公告文件` | `announcementId`、`fileType` | `fileType` 1=原始 PDF、2=Markdown。参数表写 `reportId`，正文与 URL 示例写 `announcementId`；两者均未实测，先试 `announcementId`，网关拒绝后再试 `reportId` 并记录结果 |
| `查询内资研报列表` | `from`、`size` | `size` 上限 50；另有 `categoryList`、`industryList`、`securityList`、`brokerList`、`ratingList`、`sourceList` |
| `下载内资研报文件` | `reportId`、`fileType` | `fileType` 1=原始 PDF、2=Markdown |
| `查询纪要列表` | `from`、`size` | `size` 上限 50；另有 `keyword`、`sourceList`、`researchAreaList`、`securityList` |
| `下载纪要文件` | `summaryId` | 可选 `fileType` 仅对会议平台来源生效，1=原始内容、2=HTML |
| `查询行业指标列表` | `keyword` | 必填且需具体词（如"空调"），不要传整句；`limit` 上限 200，返回 `indicatorId`、`unit`、`frequency` |
| `获取行业指标数据` | `indicatorIdList`、`startDate`、`endDate` | 单次最多 10 个指标；返回 `fieldList`／`dataList`，首列为 `date`，数值以字符串返回 |
| `知识库查询` | `query` | `top` 默认 10、上限 20。`resourceTypes`：10 券商研究报告、11 外资研究报告、20 内部研究报告、40 首席分析师观点、50 A 股公司公告、51 港股公告、60 会议平台纪要、70 调研纪要公告、80 网络资源纪要、90 产业公众号 |
| `知识库溯源` | `resourceType`、`sourceId` | 取回原文；`40`（首席分析师观点）暂不支持 |

列表接口分页必须显式翻页：`from` 和 `size` 都是必填项，默认只返回一页，
`total` 大于已取行数时不能当作完整结果。公告列表的 `announcementDate`（公告注明日期）
与 `publishTime`（东八区发布时间）是两个字段，正式引用分开记录；`publishTime` 的字段说明
写 `yyyy-MM-dd HH:mm:ss`，而返回示例只到分钟，正式引用须按实际响应核对精度。

试用账号权限随接口而异，不能按“行情”或“文本”整体归类：A 股三表、主营构成、估值分析、
前十大股东、复权因子及沪深京指数日 K 为 3 年；A 股、港股、美股日 K 同为 3 年
且覆盖全市场，个股实时行情覆盖全市场；港股三表同为 3 年；
A 股分钟 K、研报、纪要、机构观点为 1 个月；调研、路演、论坛、线下策略会
等日程类同样为 1 个月，另含未来已发布日期；A 股与港股公告、行业指标、管理层讨论为 1 年；
盈利预测 3 个月；投研线索 7 天；热点话题 30 天；题材基本信息按接口说明；知识库查询无限制。
积分口径厂商自身不一致，接口页与《OpenAPI 接口计分标准》
两套并存：列表接口页 0.01/条、计分标准 0.1/条；下载接口页为公告 1/篇、内资研报 2/篇、
纪要 5/条，计分标准为 10/20/50；知识库查询接口页与更新日志记 1/次，计分标准记 10/次。
以厂商结算页为准，不要把 `total` 当作可一次性下载的条数。

`知识库查询`一次可跨公告、研报、纪要检索，返回 `content` 切片、`sourceId`、
`resourceType` 及页码，可接`知识库溯源`取全文。但在参数之外还有一层阻断：厂商返回示例的
信封是 `code: 200` 且无 `status` 字段，而现有 `gangtise_query` 投影要求
`code == "000000"` 且 `status is true`（`app/research_web/datahub/providers_finance_mcp.py`）。
按文档示例调用会被判为 `finance_mcp_vendor_failed`，需先确认网关实际信封或调整适配器，
不能直接把 `knowledge_base` 当成可用入口。公告与研报列表的信封已有真实取数记录，
与已实测的日 K 线一致；下载与纪要链路尚未验证，可先按列表接通，再逐项补下载与知识库。

两处入口的选择标准：已知证券和时间窗、需要结构化字段（公告日、发布方、评级）时用列表接口；
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
