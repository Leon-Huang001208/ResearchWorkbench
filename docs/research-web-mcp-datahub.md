# WeKnora 的 DataHub 入站工具

get_stock_kline 的规范原始日线请求构造下沉至 DataHub contracts，供 MCP 与资产观察
已覆盖的历史区块共用；MCP公共参数、原scope/grant、提交id和status读取保持不变。
资产页面通过原资产API调用该内部合同，不借用外部应用令牌或跨账号MCP上下文。

## 当前账号已配置数据源

新授权 `rwb.data.configured` 必须同时包含 `rwb.read rwb.data.query`，仅供原已登记
WeKnora 客户端。旧令牌不自动获得此权限，refresh 不能增权。
同意页说明复用账号的厂商配置、权限及可能计费的原额度，不返回凭据。

- `rwb_datahub_catalog` 返回当前账号 callable 且 allowed 的来源、已实现绑定和业务参数；不取源。
- `rwb_datahub_business_query(request_id, query)` 接受原 `BusinessQuery`，要求明确指定目录中的
  source/capability，复用现有查询入口，禁用该次跨源 fallback，不接受外部地址或凭据。
- 返回查询继续使用原 status/cancel 和 grant 上下文，保留原件、快照及质量含义。

未配置凭据、依赖缺失、停用或无权的来源不因 MCP 接入变为可调用；外部金融 MCP
也走该账号的 DataHub Provider。scope 与工具目录按当前令牌过滤。
以下 FRED/BLS 合同和旧授权保持原行为。

本适配沿 RWB 原账号网关、OAuth、Host、DataHub 与 Provider 工作。它让外部研究宿主提交有界公开数据查询，RWB 保留来源选择、供应商调用、权限、缓存、快照、原件及金融质量语义；不把 DataKey、账号根、URL、SQL 或命令交给外部宿主。

## 权限与兼容

默认仍申请 `rwb.read`。旧授权、旧刷新令牌和四项冻结读取工具保持原行为，不能调用 Provider，也不会因版本升级获得新权限。只有显式登记的 `rwb-weknora` 客户端可另申请 `rwb.data.query`，且必须同时申请 `rwb.read`。新的同意页明确说明 FRED/BLS 公开取数、独立上下文和冻结快照；拒绝不产生授权。

SDK 发现与令牌响应使用标准空格分隔 scope；已存授权 scope 与刷新请求必须一致，不能通过 refresh 为旧 read grant 增权。现有 SQLite 表与注册行不做结构迁移；既有客户端注册的 `rwb.read` 基线继续核验，WeKnora 可申请的额外 scope 由固定客户端代码声明。撤销、停用账号与改密的原链继续适用。

工具目录按当前令牌过滤：read 令牌只看到原四项；带 query scope 时另看到以下三项。

| 工具 | 参数 | 行为 |
| --- | --- | --- |
| `rwb_datahub_query` | `request_id`、`source`、`series_id`、`start_date`、`end_date` | 提交公开系列查询，返回原研究台查询记录及其 `id` |
| `rwb_datahub_status` | `query_id`、`offset=0`、`limit=100` | 读取本授权的状态；完成后返回原 manifest 和校验过的分页 rows |
| `rwb_datahub_cancel` | `query_id` | 取消本授权的准确在途查询，已完成结果保留，不自动重取 |

`source` 仅 `ext_fred` 或 `ext_bls`，系列仅字母、数字、下划线，日期跨度最多366天。服务端构造原 `BusinessQuery`，固定 `external_data/series`、`research/strict`、`refresh=true`、无 fallback，最多500行。FRED 使用清单内 Graph CSV；BLS 使用清单内 Public Data API v2 的系列 POST，不增加 API Key 或可选收费参数。BLS 按起止日期所在年份请求，返回的年月范围与原限制必须据 manifest 判断，不能把它伪装成精确日频。

示例：

```json
{
  "request_id": "dff-20240102-08",
  "source": "ext_fred",
  "series_id": "DFF",
  "start_date": "2024-01-02",
  "end_date": "2024-01-08"
}
```

## 执行链

Facade 只选择原账号已存活的 Host。它不通过 MCP 冷启 DSH、scheduler 或其他业务恢复。Host 沿新增 `POST /api/research/data/contexts`，在现有 Store 中为这个 OAuth grant 注册一个 `created=false`、`source_scope=["datahub"]` 的上下文；不调用 `ResearchService.create` 或 native RPC。grant ID 由受信 Facade 注入，不是 MCP 工具参数。

`main.py` 的 service-only HTTP 入口显式允许数据上下文创建、查询提交、按ID读状态及取消；原生会话提交、模型配置和来源配置写入继续拒绝。仅把路由注册进裸 FastAPI 不代表该实际入口已通过，验收还覆盖真实 `create_app` 中间件及 RuntimePool 启动的独立 Web Host。

然后复用原 `POST /api/research/data/queries` 和 `GET /api/research/data/queries/{id}`。幂等键由 grant 与客户端 request_id 组合；同键同参复用原查询，新增记录对同键异参返回409，不重发 Provider。旧无参数摘要的研究台记录保持旧读取语义。取消复用原 DataHub 的准确 call_id，并处理尚未开始的 desk 外层任务，避免查询被取消后仍显示 running。

状态与取消先校验查询的 session 正是当前 grant 的上下文，且为本批公开外部系列。完成数据通过既有冻结读取协议，校验 manifest/rows SHA、保留分页与原数据字段。此结果权限不把其他资料自动加入旧四工具的选材白名单。每次工具在返回结果前再次检查令牌/授权，读取中撤权时不返回已读内容。

## 金融验收边界

HTTP 受理、Provider 执行结束、数据质量可用分别判断。`status=completed` 可能对应 `dataset.status=failed`；单列的 `data_success` 复用原 DataHub `quality_accepted` 判据，running时为null，不把执行结束当数据通过。BLS 403、来源错误、取消、缺失或未知 PIT 不变成成功；原始 `.` 等供应商缺失表示不得补为0。字段单位为 `provider_defined` 时仍未知，须另有官方元数据证据才可在报告中解释。

本模块离线测试使用真实 OAuth/SDK、Store、HTTP 路由和 DataHub，外部 Provider 响应为合成。它不认证真实金融网络、WeKnora 模型、生产 OAuth 或浏览器；这些由本任务现场验证单列。无新增 Python 依赖，公开安装入口及固定 MCP SDK 继续适用，Mac 干净安装需最终候选 CI。

## 本机首个真实闭环（2026-11-23）

同一 WeKnora 会话经实际 MCP query/status、隔离 RWB Host 与原 FRED Provider 取得七行 snapshot；随后实际读取 Skill、编辑并运行沙箱脚本，下载11个产物。Root 独立比较了完整 MCP 状态、脚本输入、算术、source/as_of/SHA，以及三份 raw 与 manifest，均与该样本一致。另一 FinGPT Agent 读取同一快照，没有再发一次取数。

这仍是隔离账号和固定公开样本。数据保留 FRED 原始字段；`provider_defined` 不能自行解释成已核单位，缺失和当前vintage限制不变，未证明 PIT／历史当时可得、BLS实源或 Wind/iFinD/天软覆盖。沙箱临时 Git 仓库的编辑／diff不能替代 RWB 持久代码项目，独立 Agent 对话不证明原生子Agent层级。正式 RWB 产品入口、跨设备独立主机名、旧会话与业务数据接管仍需后续实际验收；本记录不宣布生产替换完成。
