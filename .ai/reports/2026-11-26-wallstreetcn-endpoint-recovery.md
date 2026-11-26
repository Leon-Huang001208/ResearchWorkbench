# 华尔街见闻外部端点恢复

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"两条外部端点改指仍可解析的厂商域名，并在既有 providers_external.fetch 业务分支内接入同一 Provider 的封闭投影；不新增路由、服务、调度器、存储表、Broker 边或快照拓扑。","diagrams":[]} -->

## 范围

宿主为 Mac mini 本机 macOS，类型为 Research Web 功能修复。本次只修复 DataHub
`ext_wallstreetcn` 的取数链路，不改动其他外部源、常驻服务、采集开关或跨平台交付。

Product-Progress: not-required — 本次只恢复外部端点解析与信封判定，未新增或改变任何用户可见页面、交互或产品说明。

## 发现

对 `docs/DATA_SOURCES.md` 已登记的四条华尔街见闻端点逐个实测：

| 端点 | 旧地址结果 |
| --- | --- |
| `lives` | `api-one.wallstcn.com` DNS 无解析记录 |
| `articles` | 同上 |
| `lives-alternate` | `api-one-wscn.awtmt.com` 正常 |
| `popular` | 同上 |

旧域已停止解析，两个主端点长期不可用，而登记状态只写
`code_integrated_not_live_verified`，因此故障不会在离线检查中暴露。

修复过程中还发现第二层缺陷：该厂商用 `code: 20000` 表示成功，
而 `response_rows` 的通用信封检查只接受 `0/200`，因此即便域名改对，
仍会以 `vendor_rejected` 失败。`20000` 是该厂商私有协议码，
不能放宽为全局规则，否则会削弱其他源的拒绝检测。

## 实现

- `external_sources.json`：`lives` 与 `articles` 两条端点改指仍可用的
  `api-one-wscn.awtmt.com`，固定查询参数保持原样；四个端点现统一到同一 origin。
- `providers_wscn.py`：新增封闭投影，校验厂商成功码、`data.items` 列表、
  行身份唯一性与必需字段；异常统一收敛为 `external_wscn_schema_invalid`。
- `providers_external.py`：在 `fetch` 的业务分支接入该投影。
- `test_external_sources.py`：新增退役 origin 防回归、端点同源、成功码接受
  与四类畸形信封拒绝共 8 项。

## 验证

真实端到端（本机 macOS，实际公网请求）：

```text
lives     status=partial rows=3 total=100
articles  status=partial rows=3 total=30
```

两条数据集均取回真实快讯与 AI 文章，`partial` 来自单次响应非完整历史。

离线回归：`test_external_sources.py`、`test_datahub_catalog.py`、
`test_datahub_numeric_sources.py`、`test_connection_center.py` 共 209 项通过。
`black --check`、`isort --check-only`、`ruff check`、`mypy` 均无问题。

## 未验证

本次只恢复端点与信封解析，未改动采集调度，也未在生产常驻实例上重跑定时任务。
`ext_wallstreetcn` 的登记状态仍保留 `code_integrated_not_live_verified`；
真实定时采集、字段完整性与历史 PIT 语义另行取证。
