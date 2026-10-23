# 今日发现读取与手动研究

本模块属于现有 Research Web Host；固定使用 `intel_routes.read_upstream` 的公开 Golddata
端点，DSH 仍是唯一会话、模型执行和历史引擎。模块不启动 Hot、PostgreSQL、采集器或第二调度器。

## 读取与选材

`DiscoveryService(research, reader=None)` 的 `feed(horizon="medium", refresh=False)` 是有限
GET，只读已有事件及第三方判断，不调用模型或写 Store。缓存以当前用户 Service 实例隔离，90秒
复用、最多6份/8 MiB（含私有预览投影）、30分钟后失效，最多投影60个真实事件。来源空、失败、
上游陈旧、未知日期与已有分析错误分别保留；读取失败后保留旧资料会明确标记陈旧。

期限仅表达研究问题范围；来源未提供期限时不伪造分类。每个主题的可选资料是事件归档包，稳定
ID/hash 绑定事件身份及统一display_fields，包含传导/反证/失效、verification、priority、资产、分组及结构存在性；显示判断变化即使revision不变也拒绝。首页摘要不证明正文无变化。首次新研究/跟踪抽屉调用GET /selection：cached_preview校验当前用户的精确feed_id/horizon/theme和event_ids，selection_preview只读完整详情，生成独立scope feed及证据Hash，不改首页feed、不写Store、不创建会话或调用模型。freeze/save再次核对这一详情Hash，变化409；未知或已经prepared的抽屉沿用原请求/会话，不刷新替换。
跟踪保存则先读取批准event_id的完整详情建立基线，refresh_theme后续只读同一批准事件，不依赖首页排名；稳定evidence_sha256覆盖event/articles/revisions/explanation，排除retrieved_at/acquired_at/fetched_at采集时钟。正文/报道变化也触发；缺批准事件/Hash的旧记录不补猜。不存在的传导、反证和失效条件保留空列表。

## 显式研究合同

严格 `Prepare` 字段：`request_id`（UUID字符串）、`feed_id`、`horizon`（short/medium/long）、
`theme_id`、`material_ids`（1至20个、不重复）、`target_mode`（fingpt/claw）、非空`question`
（最多6000字符）。后端仅接受缓存中已登记的选择，不信任浏览器传入正文、URL、版本或哈希。

`await prepare(body)` 再取所选事件详情，比较用户已核对的展示投影/版本及完整证据哈希；发生变化即拒绝。
随后预分配会话ID、持久归属和交接元数据，在 DataHub 发布 `discovery_evidence` 快照与只读
上下文，最后创建并配置同一ID/cwd的真实 DSH 会话。此步骤不发送模型提示。
回执可返回经request_sha256核验的原七字段prepare_request，供同UUID显式恢复配置，不能更换选择或重复发送模型。
成功返回 `snapshot_ready`、`execution_started=false`、会话/快照身份、冻结时间、实际归档
报道清单及哈希。资料源为 `golddata_intel`，不借 CLS、Hot 或 `web_evidence` 身份。

`await execute(handoff_id, request_id)` 是单独的用户提交动作。执行键由交接及上下文哈希固定，
发送前持久 `execution_starting`，只调用一次原有 `ResearchService.send`。受理未知只查原
receipt/DSH历史中的精确标记；同一交接换 request_id 也不能重新发送。没有receipt的发送前
失败为 `failed`，不自动重试。跟踪只有 Host 已绑定的 `automation_research_scope` 才传递其
approved_tools，手动研究不自行增加日程、权限或外部投递。

`await get_handoff(id)` 只查询 DSH，不创建、选模型、重命名或发送提示。丢失创建回执后，找不到
同ID会话保持 `session_outcome_unknown`；相同ID但不同cwd拒绝；发现同ID/cwd则等待显式动作
完成配置。`list_handoffs()` 仅返回当前用户最多100项收据投影。

`trusted_context(sid)` 给原质量合同使用，重新验证会话归属、快照manifest/rows、私有原始
归档以及上下文全部哈希。普通会话返回 `None`；不一致抛结构化错误。返回`cutoff`是本次
冻结时点，不是文章来源时间。质量、报告与输出状态必须取现有 ResearchService/Host 质量
服务；`running`只说明执行已受理，绝不等于质量通过。

私有raw-0001.bin保存已解析detail及选择包经json_bytes规范化的JSON字节，不是远端HTTP压缩/空白等transport原字节，也不是Host抓取URL网页正文；Hash绑定该规范归档。

Store首次显式prepare才增加懒`discovery_handoffs`元数据索引，不保存另一份对话；原始资料
保存在现有会话隔离不可变DataHub归档。跨会话显式复制保留原快照映射，但不授予旧交接执行权。

## 验证

`tests/research_web/test_discovery.py` 使用离线读取器、真实Store/DataHub文件合同和可丢失回执
的DSH替身。覆盖不调用模型、不改旧索引、空/错/陈旧源、选择/版本校验、原始归档、未知时间、
重复请求、未知创建禁止重建、归属与哈希篡改、执行至多一次及持久失败。没有真实模型或生产
服务验收声明。服务器权限与独立跟踪由相邻tracking模块及Host策略维护。
