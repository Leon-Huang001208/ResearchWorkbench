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
