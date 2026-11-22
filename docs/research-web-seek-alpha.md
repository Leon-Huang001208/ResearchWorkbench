# 小创候选数据与受管 MCP

## 当前边界

本功能沿既有 Host / 受管插件 / 唯一 DSH / 会话证据快照运行，无新依赖、PostgreSQL、服务或第二正文库。
小创返回内容目前一律为 `clue`、`report_admitted=false`，不进入正式数值扫描和报告质量通过项。
公开目录描述不是 MCP 握手、供应商来源证明或实际调用质量验收。

能力中心插件页可下载一方 `seek-alpha-candidate-0.1.0.zip`，重现已有导入预览。
该包包含真实公开端点和说明，无秘密、脚本、Registry 身份或猜测 schema。
导入后明确保持 `unsupported/native_registry_selection_required`，包审批仍不会安装或启用 MCP。

**接入阻断**：当前 MCP 安装器仅接受 Registry 中的固定 ID / server name / version / remote index。
尚未取得供应商可验证的 Registry 条目，不能把候选包名称或版本冒充远端身份。
须供应商提供相应条目，管理员将其映射到现有受管插件，再做安装预览与确认。
本功能不新增任意 URL 安装后门，也不自动握手或导入凭据。

## 个人凭据

唯一允许的静态绑定为安装 manifest 的 endpoint、resource 同时等于
`https://seek-alpha.cn/mcp/rpc`，credential slot 固定 `static_bearer`。
只有已有包审批、安装归属与 native 内容审批有效时才能录入，保存到现有
`ResearchWorkbench.MCPRuntime` 凭据后端的安装独立 account。
Native 使用系统凭据库；显式 Docker 模式保留原私有凭据后端契约。
配置、插件包、预算文件、日志及 HTTP 响应均无 Bearer 明文。
实际使用的 Bearer 在 SDK 创建本次远程 transport 时绑定到局部调用上下文；后续删除或轮换
不会改变此调用的回显检查对象。工具、能力发现以及普通 OAuth 返回均在解析后的 JSON 键和
字符串叶子检查原 token；MCP 文本中有界 JSON 编码也会解码检查，不能用引号/反斜杠转义绕过。
发现回显时不公开、不冻结；已发送的付费调用继续为 unknown 占用预算。
UI 仅提交新值，提交前同步清空密码 DOM；状态只返回 `configured/resource/slot`。
安装卸载同步删除静态 slot，HTTP / redirect / audience 限制不变。

新增固定动作均通过既有插件路径：

| 动作 | 请求与行为 |
| --- | --- |
| `credential-status` | `{resource, slot}`，只返回是否配置 |
| `credential-save` | `{resource, slot, token}`，秘密由 SecretStr 接收 |
| `credential-delete` | `{resource, slot}`，删除当前安装凭据 |
| `evaluation-candidate` | 关闭态候选信息，无供应商访问 |
| `evaluation-preview` | `{cutoff}`，从已审 schema 生成 18 条固定清单，不执行查询 |
| `evaluation-authorize` | 会话、版本、catalog hash、完整清单、上限和明确 `confirmed` |
| `evaluation-call` | `{session_id,budget_id,entry_id}`，派生固定 call_id，单次显式调用 |

单用户路径为 `/api/research/plugins/{digest}/mcp/{key}/{action}`。
多用户路径为 `/api/server/plugins/mcp/{digest}/{key}/{action}`；账号由服务端认证，
保留页面用户匹配、gateway 固定目标、原一次性签名及 schema / session grant。
没有放开 tenant 的通用 `/api/research/mcp` 管理接口。
当前小创候选只允许固定预算内的 tools/call；resources/read 与 prompts/get 在 Host 与 SDK
两层于能力探测和 transport 创建前拒绝，不能借安装授权传送任意私有参数。
能力发现不向客户端宣称这些辅助方法可用；其他 OAuth MCP 的原有资源/提示词能力保持。

## 固定评估清单与费用

标的固定为 `600519.SH`、`300750.SZ`、`688981.SH`。六工具均按公开目录估算每次 3 子弹：

| 逻辑查询 | 精确工具名 | 时点边界 |
| --- | --- | --- |
| supply_chain | query_supply_chain | 仅当前关系，不提供历史可知资格 |
| institutional_surveys | query_institutional_surveys | by_company，6 个月窗口，最多 50 条，不请求 QA |
| consensus | query_consensus | 指定截止日期，6 位证券代码 |
| earnings_revision | query_earnings_revision | by_stock，6 个月，report_year 为截止年份 |
| profit_notice_surprise | query_profit_notice_surprise | stock，6 个月，minBase=10000，非 interim，最多 20 条 |
| risk_alerts | query_risk_alerts | all，6 个月，最多 20 条 |

六个月窗口保守固定为截止日前 183 日。查询日期遵循各工具的 YYYYMMDD 或 YYYY-MM-DD。
预览必须对已审批的实际 input schema 进行离线验证；schema 不匹配或缺工具时拒绝生成。
JSON Schema 的外部引用禁止访问。公众工具目录不能替代此审批。

授权最多 18 次 / 54 子弹，按同一会话、安装、版本、六 schema 与全部参数冻结。
每次正式试跑前必须另行核验当时报价并取得单独授权；报价变更时重新评估清单。
本地预算按本次公开单价估算调度次数，不是供应商保证的扣费上限，也不代表已扣费或返还。
用户先审批清单和预算，再在每项旁明确点击执行；预览、授权、浏览均不发送查询。
不包含深研、轮询或无人值守调用。

原私有 `mcp-runtime/authorizations.json` 增加 `budgets` 和 `calls`；旧 schema version 1 的
工具 / grants / approvals 继续兼容。所有读写均在跨进程锁内重读并原子保存，锁竞争明确拒绝。
清单中的单元最多占用一次，调用身份绑定参数摘要。
状态为 `reserved → dispatched → completed/unknown`；仅可确认未发送的 reservation 能变为
`known_unsent` 释放额度。未知受理、异常、过大响应及取消继续占用预算，不能推定退款。
相同 call_id 重入仅恢复原响应，未知原件不存在时明确拒绝，绝不自动重发。

## 原始结果与撤权

自动冻结在 MCPRuntimeService.call_tool 的服务端链上完成，ResearchService 注入已有 Store。
JSON SDK 返回规范序列化后保存在现有 `.control/snapshots/<sid>/<did>/raw-0001.bin`，
公开 datasets 仍使用现有 `rows.json/rows.csv/manifest.json`；这不是 HTTP wire capture。
`provider_metadata` 包含安装、工具、版本、schema hash、参数摘要、结果 hash、取得时间、
费用状态与明确的来源/内容缺口；未证实的公布时间保持 null。
原件以 call_id 派生的 dataset ID 固定，source 更新不覆盖旧版本。

发布失败保留现有 Snapshot pending 目录中的原件；同调用恢复不联系供应商。
只有校验通过的原件才允许把 unknown 收敛为 completed。凭据回显、非法或过大结果拒绝公开。
费用账本只存 handle/hash，无报告正文或供应商原文。

`assert_frozen_result_authorized(sid,did,metadata=None)` 是同步、离线鉴权：
独立检查真实快照、账户 Store、活动安装、包来源当前审批、精确 schema 与会话 grant。
`read_frozen_result(sid,did)` 是 async 壳，同样不联网，返回 `{result,manifest,evidence}` 并校验原件 hash。
软删除源会话仅保留只读资料，不解除来源或授权检查。档案与 DataHub 的 rows/files 路径应调用同一 guard。

## 验证与未执行项

定点回归：`tests/research_web/test_mcp_seek_alpha.py` 与
`tests/javascript/research_web_mcp_credentials.test.mjs`。
覆盖真实系统凭据失败哨兵、配置不回显、固定参数/schema、跨进程竞争、预算不足、未知与取消、
幂等恢复、原件损坏、包撤权、跨账户以及候选包导入后明确不可安装。

真实 Registry 条目、真实凭据、MCP 握手、18 次付费评估、供应商原始来源质量、浏览器与常驻部署
均需分别留证，不能用离线测试冒充已通过。本轮不执行这些操作。
