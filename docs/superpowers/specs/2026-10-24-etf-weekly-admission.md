# 华安周报可信准入与首次提交恢复

## 故障证据与边界

当前服务36fd990c已部署，历史Run `0ddde75a251543d2b0943fdf980972b6` / SID `d91b0a10-c92e-44f4-aaea-cfb56885153b` / v5的Wind数据门passed、issues为空，采集08:49:07Z、冻结08:51:42Z；快照规范JSON摘要为`3c7f2326ee649bd8982fbe1542c56ab26b9eb11458643e4a3aa2e3dd5822e89a`，冻结文件原始字节SHA256（Run.dataset_snapshot_sha256）为`85bb9debb95c6e754be48c5d9b8ce81f9dda048acb14a70d3b17922ca5543f24`。本例尚无提交receipt/delivery_key，Native会话无消息、活动、子Agent和用量。

Host在调用模型前硬选通用report-production-workflow；它的document-reading和company-research绑定均要求datahub_search_news而未声明data_requirements，因此正确得到两个data_contract_missing并拒绝。Runtime提前写research_admission_at，将该明确预检拒绝覆盖成research_submission_unknown。不能篡改账本清除字段、放松通用data gate、换SID/key或重复取数解决。

目标仅修复该可信周报路径。保留唯一DSH、原输入/owner/日期/行情/长期历史/引用/正文/图表/Word/哈希门、锁定版本的最低原生子研究数（本次v5为2）、最多一次有界内容修订。历史永不正式定稿/覆盖正式pointer/解锁日程，普通能力与租户权限不扩展。Wind Client API仍搁置，无新依赖、凭据、数据库或引擎。

## 可信周报路径

1. Runtime对已通过trusted_weekly_context和weekly_verified_evidence的华安周报不再选择不相关的通用公司Workflow。普通报告/公司研究保持旧选择和准入规则。
2. Host创建专用执行scope，绑定Run/SID/version/owner/purpose、冻结context/snapshot/data-contract hash、原formats和模型绑定；不能接受模型或请求自报的scope。Owner/启用状态和实际冻结字节重新验证，任何缺失/改变均拒绝。
3. 利用已有native_admission/guard的visible_tools与逐工具veto冻结必要工具范围，而不是把tool_ids误作allowlist。仅使用现有注册名称：todo_write、research_run_script、research_check_quality、research_read_source、ask_user_question、datahub_search_news/announcements/research/web、subagent/send_message/interrupt_agent/list_agents。若另需工具须先说明真实注册/必要性，不授予刷新行情、数据库、Automation或额外MCP。
4. 原生/租户/MCP/来源审批继续执行，子Agent继承同一可信来源与工具范围；无法确认归属则拒绝。脚本只可读取已冻结的本Run输入及相同数据快照；Source范围和read_paths不得由模型路径拼接扩大。
5. 每次Native admission仍校验scope、owner、模型工具状态及冻结字节；普通/伪造/撤权/变更scope不获周报投影。可见工具集合使用现有guard协议，保持原生审批及出站限制。
6. Service仍在原send内执行prepare_weekly_evidence、prepare_contract，生成同一原生report_plan/research-report.json合同。保留全部requirements、as_of、formats和子研究要求；不是空合同或质量豁免。

## 提交阶段与安全恢复

1. 明确区分preflight/prepared/rpc_attempted/accepted/unknown。已知预检拒绝保留原稳定错误码，不能仅凭admission_at归为RPC未知。
2. 紧邻session.prompt之前，先以Host受管路径持久化不可覆盖的attempt claim并同步到磁盘；持久化失败不RPC。并发/重启/超时/断连/丢ACK遇到claim只能观察，不重放。旧pending缺phase保持unknown，不泛化成可重发。
3. 所有恢复复用原Run/SID和`report-workflow-{run_id}` key，重验owner、版本、模型、原输入hash及Native空闲。已接受只观察和交付；明确prepared/preflight_rejected且无attempt claim，只有显式retry/inspect才可首次提交，不自动续发。
4. 已冻结的恢复不得刷新Wind、重建SID或改写context/snapshot；抽出共享周报提交函数，让已完成数据的Run直接复用原输入和正文合同。
5. 旧协议缺少可信producer/RPC阶段证据时一律保留unknown，即使没有receipt且Native无执行痕迹，也不能由当前builtin状态推断过去sender身份。显式inspect给出weekly_legacy_sender_unproven且0次prompt；不得硬编码本例ID、手改账本、推断未受理或提供force开关。已接受旧运行只观察和交付。
6. 新协议标识从新Run创建起持久化；旧未知Run检查只可记录recovery协议和缺证原因，不伪造其sender协议。新路径已有attempt claim的未知状态不得落入legacy识别。原失败和采集时间保留，恢复不倒写快照时间。
7. 用户已明确选择：保留本例旧未知Run及其数据证据，修复验证及另行确认部署后，从新发布版本手动启动一次历史验收；该新运行重新采集数据，不重发旧SID/key。源修复不把旧运行标为完成，也不自动创建或启动新版本。

## 旧等待状态与升级衔接

旧版将该未知Run计入Host活动和Workflow重叠；现有取消接口会发送Native取消，且仍保留needs_attention，不能用于本例。准备单独、受限的领域维护动作，并在最终版本可审阅后另行请求用户批准：只结束Workflow等待，控制态为cancelled并显式记录monitoring_disposition=ended_by_user，模型受理状态仍unknown，原失败、SID、采集、合同、快照、收据和历史用途全部保留。不得表述为模型已取消、报告已完成或原请求未受理。

维护入口仅接受严格校验的华安历史legacy未知对象、预期身份和操作ID；新协议或已有attempt claim不能走该入口。沿用主管理员实时资格、既有三把维护锁、目录身份和Native/子Agent空闲检查，不调用任何取消或模型接口。Catalog需显式无reconcile的维护打开方式，避免构造函数清理未索引资源。保存异常按锁内读回的old/new/冲突事实分类，不盲目覆盖原目录。

结束等待只改变Workflow控制记录，不停止计算，也不把旧Host的active=true当作空闲。持维护锁、释放catalog锁后，使用现有单Run GET刷新旧Host缓存，再运行完整且未放宽的原Operations.idle；其他活动或证据未知仍阻止部署。若检查或后续部署失败，保存已授权结束等待的独立回执，代码事务仍按原规则恢复。已结束等待的Run不能被retry或重启恢复重新唤醒；新一期仍需不同发布版本、SID和手动操作。

Workflow列表和详情将该控制态显示为“已结束等待（模型结果仍未知）”，保留原研究/质量/定稿证据与Claw入口，不显示失败重试或取消按钮。普通cancelled记录仍沿原行为，不能把该维护动作显示为模型已取消。

## 回归与交付

- 用真实ResearchService.send和真实capability catalog（仅Native传输/外部响应隔离）重现原拒绝；不能mock send绕过此缺陷。
- 通用缺合同能力仍拒绝；可信周报通过独立投影；owner/inputs/scope/version/purpose/model篡改均0次prompt。
- 验证必要原生工具/子Agent被限定，行情刷新、Automation、任意MCP与外部路径拒绝；后置所有原质量门仍生效。
- 覆盖准备失败0 RPC、claim写入失败0 RPC、未知RPC不重放、accepted仅观察、双击/重启不重复、原数据/SID/key/hash不变的显式续跑，旧不确定状态继续blocked。
- 源码/测试/文档/任务报告和完整Router、独立规格/质量评审、Mac相关本机及原三CI分别取证。Windows/Linux按设备归属交接，不从Mac dispatch。
- 冻结功能修复为完整产品祖先后，另增固定前版36fd990c的封闭Native后继，沿现成v9的完整16MB日志reader及其余原事务/保全/恢复门；不改已发布旧身份。
- 最终维护动作和部署单独明确授权。实际从新发布版本手动历史验收后才认证模型/Word/下载，未运行项不得标通过。
