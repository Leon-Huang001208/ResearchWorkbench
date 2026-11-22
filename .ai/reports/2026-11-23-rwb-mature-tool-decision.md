# RWB 成熟工具选型与迁移清单

**FinGPT 优先接入 WeKnora 原生完整 App／Agent，金融数据通过 RWB MCP 提供；FinGPT、Claw 的名称和产品入口保留。** 本批已实际完成 OAuth→DataHub→FRED 七行快照→Skill→编辑脚本／git diff→执行→11个产物下载及独立复算，另一个 FinGPT Agent 读取同一快照和指定文档并给出分块引用，没有再次取数。Claw 的技能与临时计算可用；本次跨轮出现工作区／repo 重建，持久代码项目、长期配置和原生子 Agent 层级未验，不能据此宣布整体金融 Codex 已被替换。

**RWB 继续负责金融 DataHub、账号／来源权限、凭据、PIT、报告和独立质量，通用聊天、检索和执行逐项交给成熟工具。当前真实删除业务代码为0。** DFF样本窗口为2024-01-02至08，七行均5.33、首末差0.00，原字段单位仍为 `provider_defined`；单次DataHub查询耗时499ms、`data_success=true`，不代表完整历史或正式研究通过。模型曾错误声称来源 URL 被污染，Root 比较完整 MCP、输入和原件后确认字节一致；模型另补入无元数据支持的 USD，已由独立 QA 移除并用下载的编辑脚本重算校正版，原数据未改。这说明来源、数值和金融语义复核仍需独立于模型自身的“通过”判断。

完整导航与源码盘点见[原模块清单](2026-11-22-rwb-module-reuse-inventory.md)，本表更新其候选状态。下列路径除另标外均相对 `app/research_web/`；“退出候选”只指对应的通用部分，不表示可以整目录删除。

| RWB 模块与源码 | 成熟工具责任与本批结论 | 保留内容、退出候选及具体条件 |
|---|---|---|
| **FinGPT**：`qa_frontend/`、`qa_worker/agent.mjs`、`qa_worker/worker.mjs`、`qa_execution.py` | 优先 WeKnora 完整问答／Agent工作区，承担对话、文档检索、引用和通用执行。第二 Agent 已读取同一真实快照和指定文档，区分原字段 `provider_defined` 与文档解释的 Percent。 | 保留账号、来源、费用、轮次／产物和质量绑定。新会话在正式账号下完成完整 App 接入、引用回查、旧历史可读与切回后，才退出 `qa_worker` 的重复通用循环／IPC和对应通用问答UI；`qa_execution.py` 的金融归属与状态职责继续保留。 |
| **Claw／专业协作**：`ui/claw-workspace.mjs`、`ui/claw-flow.mjs`、`client.py`、`specialists/`、`runtime/specialists.mjs` | WeKnora 的 Skill、文件编辑、shell、临时 Git diff和产物已真跑。两个独立 Agent 会话不能算“父 Agent 调用两个子 Agent”；跨轮持久项目未验。现有 DSH 路径继续兼容维护。 | 先采用临时分析用例。真实持久 repo、多轮／重连后文件连续、终端、原生子 Agent、审批、取消及旧历史通过后，才退出相应通用会话／事件展示和 `DSHClient._event_envelope` 的有损重建部分；本批不退出整套 Claw、DSHClient 或专业协作。 |
| **知识资料**：`knowledge_backend/{client,service,current,sync}.py`；旧 `knowledge_layer/retrieval/` | 复用已有 WeKnora 解析、索引、检索及完整 Agent，继续使用现有本地 Embedding 和生成模型，不另建向量库。 | 保留用户／空间映射、批准范围、同步版本、current-hit和冻结证据。旧 `vector_store.py`、`hybrid_search.py`、`assertion_search.py` 仅在调用方及持久数据消费者迁完、原文／删除／历史引用验过后退出；不能仅因目录旧就删除。 |
| **DataHub 与专业源**：`datahub/{contracts,broker,snapshots,providers_external}.py`、`datahub/__init__.py`、`market_store/` | 保留金融底座，复用已有 Provider。OpenBB 的48包已隔离安装，但 FRED／BLS 公共SDK均要求额外Key；匿名 BLS 实网超时／403，没有成功对拍。 | BusinessQuery、证券身份、单位／日期／修订、原件、缓存、PIT及 Wind／iFinD／天软边界保留。OpenBB 本批没有可退出旧代码；后续仅对实际扩覆盖或更省维护的单个Provider采用，前提是成功同源对拍且缺失／vintage无损、总代码减少。不是全面否定 OpenBB，也不为两个匿名入口永久再叠一套框架。 |
| **工具来源与金融 MCP**：`mcp_facade/`、`mcp_runtime/`、`mcp_registry/` | WeKnora 复用原生 MCP 配置、工具调用与过程事件；RWB 沿现有 SDK 增加显式 `rwb.data.query`，提供 query／status／cancel，复用原 Host／DataHub。真实主动查询和同键复用已跑。 | 保留账号／grant隔离、幂等、撤权、来源许可和金融状态。旧 `rwb.read` 四工具仍只读已选材料；未选材时 `access_denied` 是边界生效，不应为方便聊天放开。只退出被原生界面等价覆盖的重复通用配置／展示，金融接口与权限不退出。 |
| **技能中心与包分发**：`capabilities/{seeds,catalog,methods,packages}.py`、`plugins/packages.py`、`skills/` | WeKnora 原生安装／执行本批自有金融 Skill已通过。腾讯 SkillHub 作为公开技能来源：原 ZIP及15个文件摘要已有实证，但许可、可信签名和实际安装未闭合。讯飞 SkillHub 仍是私有版本分发候选，未运行双宿主分发。 | 金融Skill正文、业务ID、固定版本、权限、依赖审核和会话快照保留。明确唯一目录后，外部包来源的许可／pin／依赖及实际执行过关，才退 `seeds/catalog` 的重复来源清单；讯飞完成同包版本／hash、双宿主投递和撤权／回滚后，才退通用传输分发部分，不整删安全包边界。 |
| **固定报告／定时任务／Research Bot**：`report_workflows/`、`automation/{service,schedule,transport}.py`、`research_bots.py` | 保留正式生产链。LoopForge 可候选接通用SOP画布、Agent／Script／Human节点；平台0.4试点尚需约1.095GiB压缩镜像及MySQL，未运行。Local Legacy 状态推进不算平台SOP通过。 | 模板／底稿、Wind／Excel、冻结、报告质量、Run／attempt、重叠和投递继续由RWB负责。只有固定三节点SOP实际覆盖原输入／产物、人工决策、失败／取消／重启与幂等，并确定单一调度权威，才退 `ui/capability-editor.mjs` 及通用流程／日程适配的等价部分；当前不新增长期重复平台。 |
| **金融产品与研究方法**：`market_service.py`、`asset_workspace.py`、`asset_history.py`、`frameworks/`、`strategy_validation/`、`event_studies/`、`discovery/`、`ai_news_service.py` | 全市场、资产、研究框架、策略和情报继续保留。知识检索、解释及已覆盖数据源可分别接成熟服务；本批未证明任何候选能整模块替代。 | 保留交易日／复权／单位、金融方法版本、无前视与确定性计算、事件／采编原件及批准发布。只按实际消费者和重复实现划定局部退出，不能把聊天／RAG通过当回测、报告或采编通过。 |
| **账号、历史与设置**：`multiuser/`、`credential_backend.py`、`model_credentials.py`、`store.py`、`ui/settings.mjs` | 系统凭据库与现有认证组件继续复用；WeKnora账号是映射后的外部身份，不取代RWB的admin／租户。 | 账号／来源授权、凭据命名空间、旧会话／文件／报告引用及清理语义保留。PR324源码已合；PR325已合且三项CI通过，主维护窗口已实际部署0657并核验服务与两份UI资源；生产主账号登录DOM尚未自动复验，WeKnora金融接管不因菜单部署而标通过。 |

边界验证已有真实证据：审批拒绝后没有数据返回；SSE读端断开后，原 pending 仍可通过正常答复API继续；跨10分钟access有效期的后续调用实际续期成功。撤销测试账号授权后，真实Agent收到 `mcp_oauth_required` 且没有数据；该类型不能由通用 deny API回答，实际HTTP400后使用正常 stop（200），未称deny成功。BLS真实请求分别出现deadline／403并保持无数据；模型发出的cancel到达时查询已终态，**没有观察到此次实网查询被成功取消**。协议／真实Host取消回归已过，不能替代这一实网缺口。WeKnora原生完整App已用实际历史会话通过浏览器验证：工具树、命令输出、git diff、JSON产物预览与引用原文高亮均可查看，0浏览器／HTTP错误，未新增模型。该UI验证不代表原生USD字段金融合格；校正版以独立QA产物为准。RWB嵌入、生产主账号页面和稳定项目持久化仍未通过；图15实际生成／四视口视觉检查已通过。

## 四步实施顺序

1. **先交付金融MCP薄接入。** 合入本批源码、必要CI与独评，保留旧四项read行为。正式RWB账号映射及OAuth采用独立hostname或Mac mini明确loopback接法，保留精确来源、完整回调和授权边界；当前隔离测试账号／公开样本不冒充生产接管，不用裸反代或关闭边界替代适配。
2. **先迁FinGPT新会话。** RWB保留名称／导航，接WeKnora完整App／Agent；文档命中与DataHub快照走当前用户授权，数值／来源／单位／PIT仍由RWB复核。先取得真实产品页面、旧会话／文件／报告引用与切回证据，再退出表中的通用循环／界面部分；不清空旧历史完成迁移。
3. **Claw按能力接入。** 先采用已验证的Skill和临时计算；持续项目、长期沙箱配置、多轮代码连续性、原生子Agent和完整取消另做实际接管。达不到这些条件就保留现有执行内核与专业协作，不以临时Git演示宣称整个Codex能力替换。
4. **逐块退出重复实现。** 按表确认消费者已迁、数据／历史可读及对应实际验收，再在独立小PR删除已被接替的通用部分。优先清理FinGPT重复循环和确已无消费者的旧向量层；技能来源先补包许可／签名，私有分发或可视化SOP有真实需求才试讯飞／LoopForge。OpenBB FRED／BLS本轮不删旧分支；不让多个目录、调度或Provider框架永久并行。

## 证据入口与当前状态

源码责任见[原盘点](2026-11-22-rwb-module-reuse-inventory.md)、[主动DataHub实现报告](2026-11-22-rwb-weknora-datahub-mcp.md)及[接口合同](../../docs/research-web-mcp-datahub.md)。外置实证位于本任务 Scratch `weknora-live-chain-20261122/`：`results/live-claw-independent-quality.json`、`live-claw-downloads/verified/`、`live-fingpt-messages.json`、`approval-denial-result.json`、`oauth-token-lifetime-observation.json`、`oauth-revocation-result.json`、`datahub-negative-settle-messages.json`、`datahub-cancel-messages.json`，以及 `openbb-trial/SUMMARY.md`、`loopforge-trial/SUMMARY.md`。校正版产物由独立Codex QA执行，不冒充额外一次WeKnora模型运行；上游技术身份和原始失败留在这些证据中，不靠模型总结推定成功。

上游固定依据：[WeKnora Agent／MCP API](https://github.com/Tencent/WeKnora/blob/f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7/website-docs/04-api/02-api-agent-mcp.md)、[Skills／沙箱 API](https://github.com/Tencent/WeKnora/blob/f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7/website-docs/04-api/02-api-sandbox-skills.md)、[LoopForge平台与Local边界](https://github.com/Tencent/LoopForge/blob/eb2e368f14d004e6a22ee25940f5a03c0b5d9f38/README.md)。平台0.4镜像与该main源码身份不同，本轮只读核查不算运行验收。

原 Native LEO-51 保持 blocked、累计16/20及两轮QA记录不改；本清单与代码是Codex接手交付，不把它改报为Super Agent已完成。产品替换、正式上线、跨平台验收和业务代码退役分别记录。

Product-Progress: not-required — 本文件仅汇总选型、退出条件与迁移顺序，不新增或变更产品启用状态。
