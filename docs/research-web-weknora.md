# WeKnora 研究资料底座与报告证据

本合同定义 RWB 现有研究资料适配中的原件、解析、索引和检索边界。独立 WeKnora 应用使用完整产品能力；RWB 继续保留金融快照、Word 模板、Excel 底稿、正式报告、冻结证据及现有看板。FinGPT、Claw 保留产品入口，执行内核的替换按同题验证决定；确定性程序继续完成计算、图表、Word 装配和质量检查。

## 完整功能模式（2026-11-22）

用户已明确采用完整 WeKnora 功能，不再把仅管理与检索作为产品限制。原 `rwb-weknora-standard-r2` 实例已在原 Compose 操作锁内将 app 的 `WEKNORA_RETRIEVAL_ONLY` 从 `1` 改为 `0`，复用相同镜像、原卷和账号；仅重建 app，其他四服务保持原身份。应用健康通过，公开 MCP 路径由专用 profile 拒绝恢复为正常 Bearer 认证。实际配置、旧配置和操作回执留在本机私有部署目录，不提交凭据。

该模式开放上游 Agent、Skills、MCP、协作、沙箱及生成能力，实际使用仍取决于对应模型、工具和运行环境是否配置。过去已保存的知识库摘要、图谱等设置保持原值，不自动批量回填或重解析。RWB 现有用户 JWT、current-hit、原文冻结与报告范围适配继续有效；完整工作台与实时 DataHub 的接入、真实模型及金融质量验收见[复用验证报告](../.ai/reports/2026-11-22-rwb-tool-reuse-validation.md)。

## 版本、身份与证据边界

- 基线为 WeKnora `v0.9.0`，源码 `f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7`。实际镜像必须固定 digest，核验源码及 ARM64 产物；不使用 `latest`。
- 两边独立登录，通过不可变用户及空间 ID 显式绑定。个人资料默认私有，跨空间共享须明确授权。
- 用户先自行在WeKnora用真实邮箱注册账号；RWB设置页可用该账号邮箱／密码登录并绑定返回JWT，原JWT高级绑定入口保留。RWB不代为注册，不以bootstrap测试principal替代用户身份；现有测试身份与样本按本轮保全方案留存，用户注册后明确切换。
- 空间级 API Key 是机器权限，不自动继承真人用户的成员撤权。RWB 适配必须核验当前身份及授权，或通过用户原生认证让 WeKnora 执行当前权限检查；不能回退到管理员 Key。
- 普通检索按用户当前权限；固定报告先锁定服务器确认的允许文档、原件版本和截止期，再检索。上传时间不代替发布时间；未知时点材料不获得历史报告资格。
- RWB 冻结实际原件、哈希、引用定位及时间证据，后续重解析、删除或重启不能重写已冻结证据。冻结是独立写权限，不扩充现有四项只读 MCP。
- DSH 官方插件是同一 WeKnora 后台的客户端，首期不把其空间 Key 直连当作 RWB 多用户报告入口。

## 历史：仅管理与检索的模型边界（2026-11-20）

本节记录当时的恢复配置与证据；当前全局模式以上述 2026-11-22 完整功能模式为准。旧补丁、manifest、逐知识库配置和恢复原件按原义保留。

本轮采用本机 Ollama 向量化，`bge-m3:latest` 的实际API已返回1024维，API模型digest为 `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`；原始manifest摘要另随现场回执保留。该实测不替代完整入库、检索和报告验证。原件留在本机资料链，云端研究模型只接收获准研究所需的命中片段。先前硅基流动免费Embedding是历史候选，本轮不自动调用它或收费替代服务，也不把不同模型的向量混入既有索引。

恢复对象是原 `rwb-weknora-standard-r2` 实例、既有固定镜像和原卷，前端仅映射回环 `18181`，启用 `WEKNORA_RETRIEVAL_ONLY=1`。私有 Compose 位于 `/Volumes/WorkDisk/Data/RWB/weknora-runtime`，不把现场配置或凭据提交到仓库。数据库冷备及隔离恢复已核对1份文档、2个知识库；原卷、原件和旧记录保留。该恢复检查不补造旧付费调用台账中的缺口，也不代表新同步、实际 Embedding、浏览器和完整报告已通过。

Ollama 固定官方 SHA 核验后的 `0.40.16`，安装于 `/Users/leon/.local/share/ollama/v0.40.16`，仅由 `com.leon.rwb-ollama` LaunchAgent 管理，模型目录为 `/Volumes/WorkDisk/Ollama/models`。服务绑定 `127.0.0.1:11434`，关闭云能力、并行数为1；容器通过内网 `11435` 代理访问，访问控制只允许 WeKnora app。代理允许 `HEAD /`、`GET /api/tags`、`GET /api/version`、`POST /api/embed` 和 `POST /api/show`，拒绝 pull、chat、generate。权重准备由已授权操作员单独完成，不开放给研究工具。

WeKnora 普通初始化向导要求 LLM，摘要默认开启，表格摘要还有独立入队路径。仓库的固定补丁链由服务端关闭入库生成增强与相应队列，并按固定允许列表拒绝生成 API；不能只凭界面开关证明零生成。当前模型、真实入库／重解析、拒绝计数、宿主调用、浏览器与业务验收分别写入任务回执，未取得证据的项目保持 `NOT_RUN`／`BLOCKED`，不能由恢复或源码检查推定通过。

### 配置模板与补丁链

`deploy/weknora/embedding-only.json` 是0001阶段的逐文档显式 opt-out API 模板，整份JSON不是API请求；其历史 `NOT_IMPLEMENTED`／BLOCKED字段不描述0002的源码状态。严格实例候选以[retrieval-only manifest](../deploy/weknora/patches/retrieval-only-manifest.json)为准，按固定release → 0001 → 0002 → 0003顺序绑定前后像与补丁哈希，再显式设置 `WEKNORA_RETRIEVAL_ONLY=1`。0001模板不能独自放行原UI上传／重解析。历史候选链的隔离验证与本轮原实例恢复分别留证，不把manifest中的NOT_RUN改写为通过。

### 原生知识库设置补丁0003与当前验证

`0003-retrieval-only-kb-settings.patch` 在0002之后增加只检索模式的原生知识库设置：先由 API 建立文档库，再从原界面编辑；首个知识库创建向导仍未支持该模式。认证服务端标记决定 profile，客户端请求不能自行开启该权限；普通模式继续校验真实 Chat 模型。补丁及前后像绑定见[kb-settings manifest](../deploy/weknora/patches/kb-settings-manifest.json)。固定 manifest 的 `NOT_RUN` 不由任务验收回填。

2026-11-06的独立上游 Node 纯函数8项通过，只证明当时的设置逻辑；原生 Go 完成编译，但测试初始化在上游 `go-m1cpu` 崩溃，两次 Docker 编译受容量门阻断。旧失败与固定 manifest 原样保留，本轮恢复、实际向量化和浏览器入库另取证；RWB 的隔离浏览器结果也不能代替这些检查或业务报告接受。

### 原生详情页上传补丁0004（可选源码资产）

`0004-retrieval-only-native-upload.patch` 仅补齐 `KnowledgeBase.vue` 详情页的上传前校验，与0003的设置页分开。只有认证的 `GET /api/v1/initialization/config/:kbId` 返回当前库的只检索 profile，才允许缺少摘要模型；未取得 profile、普通模式或切库后旧响应到达均不能沿用该例外。Embedding 与存储校验保持。补丁及固定前后像见[native-upload manifest](../deploy/weknora/patches/native-upload-manifest.json)。

0004是未应用的可选上游源码资产，不属于当前实例的必需补丁链，也不证明现役标准版的上传或零生成已通过。其离线文本／哈希检查、上游补丁应用、前端构建、真实服务和浏览器上传分别取证；此前 Lite／Vue／向量化证据不认证本次候选或 #318／#319 的运行状态。

## 本机目录同步与当前研究

账号设置绑定 WeKnora 原生用户 JWT、workspace 和一个当前可见的自有知识库，再以明确动作启用固定目录 `/Volumes/WorkDisk/Data/RWB/knowledge-inbox`。来源目录的 owner 标记同时绑定 RWB 账号根、origin、用户、workspace 和知识库；其他账号或共享／跨空间库不能占用同一目录，调用方不能改 root。访问 WorkDisk 时校验实际 APFS 卷 UUID，磁盘不可用时拒绝写入。

Host 持有现有账号生命周期内的60秒同步巡检，只恢复明确启用的资料同步，不恢复其他 Automation。两次稳定观察后上传内容快照；支持含文本的 PDF、DOCX、Markdown 和 TXT，单件8 MiB。更改文件产生新版本，仅在 WeKnora `parse_status=completed`、已启用、原件哈希及当前授权复核后切为 current；失败或解析未完成保留旧 current。删除只撤回当前入口并保存 tombstone、旧版本与冻结历史，不删除上游文档或既有证据。

固定DocReader的TXT兼容层为 `deploy/weknora/docreader/plain_text_entrypoint.py`：只读挂载后在原 `container_entrypoint.py` 的ARM／OpenSSL启动检查之后注册builtin TXT解析器，再运行原服务模块。严格解码UTF-8（可带BOM），保留文本空格、换行及原件字节；空白或无效编码明确失败，不解释链接、图像或Markdown，不发网络／模型请求，不替换原PDF、DOCX、MD解析器。兼容层的离线合同与实际容器TXT入库分别取证。

可变状态位于账号根的 `knowledge-sync/state.sqlite3`，与 `knowledge-backend/` 的不可变回执／证据分开保全。目录逐文件有界检查，只保留路径、版本、hash和stat元数据，不以整个目录64 MiB或1000文件作为同步准入。原字节仅为待上传／结果不确定的任务保留，实际查询验证原件后按SHA pin一份；发布且未被引用的副本可释放，已引用版本不因源修改或删除而释放。SQLite与历史证据使用持锁流式hash保全，业务历史总量不受整体读入内存的预算限制；写入前按系统盘10 GiB／其他写入卷2 GiB的实际余量准入。跳过清单最多128条。每轮公平游标最多处理8个待传／待解析版本并审计1个current；I/O前保存游标，避免超时或重启使后缀持续饥饿。完整枚举失败不会推定删除。临时文件忽略，符号链接、硬链接、空文件、不支持类型或过大文件记录跳过原因；不是OCR或任意格式导入器。

当前研究工具 `research_search_knowledge` 接收查询，`research_read_knowledge` 接收已有命中句柄；Host 注入当前 `session_id`，模型不能选择账号、资料库、文档白名单或写入范围。检索只召回同步清单中 current 的原件，核对原件 SHA-256、完整分块指纹和权限后发布最多8个会话命中回执。读取仅接受同会话 `hit_id`，源变化、删除或被替代时返回对应状态并保留原命中片段。用户可明确选择最多8个回执冻结实际原件和分块，历史证据不随重新索引或删除改变。

当前资料的 `available_at`／`time_evidence` 未知，结果固定 `historical_eligible=false`、`source_time_unknown`；检索命中与冻结均不授予历史 PIT、回测或正式报告资格。质量链只登记可信 Host 回执，沿原来源选择与准入复核；固定报告继续使用下述显式批准的 scope 流程。

## Host 批准范围的单轮研究

认证用户可先经原 `POST /api/research/knowledge/scopes` 批准原件、截止期和来源时间证据，再在全新研究会话的首条消息中提交 `Prompt.knowledge_scope_id`，同时携带 `X-Research-User-Action: ?1`。Host 在既有提交回执中原子保存 scope、完整请求摘要及实际提交摘要，并把会话标记为 `knowledge_single_turn`；该持久 grant 由 Host 派生，模型文本或 DataKey 不能创建。已受理的相同请求沿原幂等回执返回，新的追问不能复用此会话授权。

正式范围可以包含最多10个获准知识库，不依赖普通 current 同步所选的单库。它继续使用唯一一组工具协议：`research_search_knowledge(query)` 产生不透明的会话 `hit_id`，`research_read_knowledge(hit_id)` 只读取该句柄；不新增同名的 operation／document／chunk 工具。模型不能指定 scope、库或文档白名单。Host 在内部 DataKey 回调中根据持久会话选择正式分支；原生桥另从实际执行元数据注入 `X-Research-Native-Session`，正式调用要求 caller 与获准根会话一致，不能把子会话折叠为根会话来继承授权。

每次正式检索／读取均核对当前 grant、取消／终态、唯一运行中的原生根会话、首个且尚未结束的 turn，以及原生用户消息的 `requestId`。上游 await 后、发布回执或返回正文前再次复核；撤权、取消、原件／分块漂移或 grant 改变即拒绝。正式命中回执同时绑定 scope、原生请求和提交摘要，不能跨会话、跨请求或使用普通 current 回执；失败不回退到 current 检索。没有单轮 grant 的普通 current、登录、tenant、同步及版本 pin 合同保持。

来源时间批准只保存用户提供的证据，不自动获得历史 PIT 或正式报告资格；正式分支仍返回 `historical_eligible=false`，未知来源时点仍标为 `source_time_unknown`。资料冻结、质量复核与正式定稿继续走各自的原入口。本节描述源码合同，不代表真实原生宿主、模型、上游服务或业务报告验收已完成。

## 接口与权限

状态和Doctor中的 `expected_release`／`expected_source_commit` 是本适配要求的目标版本，不是已连接服务的运行版本证明。绑定状态还提供 `credential_cleanup_pending`：为 true 表示旧凭据槽保留待处理，不能把新绑定成功解释为旧凭据已全部清理；不会返回凭据内容。

以下路径均位于现有 Host／认证网关边界；调用方不能选择 RWB owner、数据根或上游 URL。默认 `RESEARCH_WEKNORA_ORIGIN` 为空，状态读取不联网。操作员设置仅接受无凭据、路径、查询和片段的 HTTPS origin，HTTP 限回环／localhost。配置无效或缺少授权时拒绝，不降级空间 Key。

| 方法与路径 | 权限与实际作用 |
| --- | --- |
| `GET /api/research/knowledge` | 本机绑定元数据和同步摘要；不探测上游，配置状态不认证服务或报告。 |
| `POST /api/research/knowledge/login` | 明确用户动作；`email`／`password` 只向固定operator origin的官方 `/api/v1/auth/login` 登录已有账号，随后沿原bind核验身份并保存受保护JWT引用；不保存密码，不注册账号。 |
| `POST /api/research/knowledge/binding` | 明确用户动作；接收 `token` 与正整数字符串 `workspace_id`，用上游原生用户身份验证后保存受保护凭据引用。 |
| `GET /api/research/knowledge/bases` | 显式读取该用户当前可见库，返回 `items`；不做问答或建库。 |
| `GET /api/research/knowledge/sync` | 当前账号的启用状态、固定目录、current／pending／error计数、最后扫描与有界跳过原因；不触发扫描。 |
| `POST /api/research/knowledge/sync/config` | 明确用户动作；`knowledge_base_id`、`enabled` 绑定当前用户可见的自有知识库及固定目录，不接收 root。 |
| `POST /api/research/knowledge/sync/scan` | 明确用户动作；空对象请求，执行一次有界扫描并返回结果，失败保留错误码与旧 current。 |
| `POST /api/research/knowledge/scopes` | 明确用户动作；确认来源可得时点与时间证据，锁定报告期、截止、原件及完整分块指纹。 |
| `POST /api/research/knowledge/search` | `{session_id, query}` 检索当前同步清单并生成会话命中回执；保留普通检索与已批准 scope 的 Top 8 原文流程，不返回生成答案。 |
| `POST /api/research/knowledge/read` | `{session_id, hit_id}` 读取同会话回执并复核源状态；保留当前授权文档读取及 scope 冻结字节复核。 |
| `POST /api/research/knowledge/freeze` | 明确用户动作；`{session_id, hit_ids}` 冻结当前研究回执，或沿旧 scope 冻结所选分块及原件，独立写入证据。 |
| `GET /api/research/knowledge/evidence/{identifier}` | 当前 RWB 账号读取本地不可变证据，复核 manifest 和已存原件。 |
| `GET /api/research/knowledge/evidence/{identifier}/original/{sha}` | 当前 RWB 账号下载该证据实际包含的原件，不解析任意路径。 |
| `POST /api/research/internal/data/knowledge-query` | 原 DataKey 回调；仅接受 `{session_id, query}`，Host 依据持久会话选择普通 current 或单轮 grant；正式分支另核对可信原生 caller，不接收模型自选 scope。 |
| `POST /api/research/internal/data/knowledge-read` | 原 DataKey 回调；仅接受 `{session_id, hit_id}`，正式句柄绑定当前 scope／请求／grant；不开放配置、扫描或冻结。 |

资料异步操作在网络读取、授权复核和存储提交全过程持有既有 resident `admission`；维护冻结生效时拒绝新操作，返回 `knowledge_maintenance_busy`，不通过查询通道绕过停机门。绑定元数据写前及读取同为16 KiB上限，超限不写入不可恢复的大记录。

登录绑定、JWT高级绑定、同步配置／手动扫描、scope与freeze要求 `X-Research-User-Action: ?1`，不授予内部工具写权限。JSON请求有明确长度且不超过64KiB，验证失败不回显JWT或密码。浏览器提交即清空密码／JWT输入，密码只在本次登录内存中转发，不写入凭据库、配置、日志、草稿或持久浏览器存储。仅JWT经既有受保护后端保存。登录失败保留旧绑定，切换身份后旧同步配置不能继承或读取；若已有旧身份配置，`reconfiguration_required` 表示须先按明确授权保全并安全处理旧绑定资料，再作全新配置，设置按钮不覆盖旧owner标记或移植历史。失效、撤权及空间变化重新核对，不自动续令牌或回退管理员。

RWB owner 是当前 `Store.root` 的摘要，绑定及证据复制到其他账号根会拒绝。WeKnora 的 `file_hash` 是来源 MD5；范围权威使用实际下载字节的 SHA-256，以及按分块身份、文档／库身份、正文、序号和定位计算的完整指纹。报告查询在上游召回前附加允许文档 ID，前后复核当前身份；原件、分块或库范围漂移均拒绝。原件每件8 MiB、冻结事务32 MiB、manifest256 KiB，单次超限保持失败，不裁剪证明；历史保全流式读取，不因已保存记录超过1000条或总原件超过64 MiB而使正常使用停止。冻结仍要求实时身份和库权限核验成功，原件endpoint故障可使用先前已验证的本地pin，不提供离线授权降级。

`available_at`、`time_evidence` 和 `confirm_source_times=true` 记录认证用户对真实来源证据的明确批准，**不是自动推导的发布时间或历史 PIT 认证**。晚于 cutoff、未知时点和重复文档在上游检索之前拒绝。报告 scope 不能由 DataKey、四项只读 MCP 或模型文本创建。既有正式报告的质量及定稿权威不变。

## 本机诊断与保全

Doctor 的可选 `knowledge_backend` 项只检查当前账号内的绑定、不可变证据及同步保全摘要，不读凭据、不联网、不创建未配置的数据根。已配置不等于已连接，模型与报告验收保持 `NOT_RUN`。`knowledge-backend/` 与 `knowledge-sync/` 加入既有私网账号保全；中断 staging、未知目录、哈希变化或预算超限阻止收尾与切换，不清空或迁移原件来放行。

现有一键安装不安装 WeKnora／Go／Ollama、下载模型或新增 Python／Node 依赖。同步、回执和保全使用既有依赖及标准库 SQLite；macOS Bootstrap 在原步骤校验新增模块可导入，仍须最终候选的干净安装证据。本轮原实例恢复和本机服务配置按当前明确授权操作，实际资料切换与原周报接受另行留证。

## 只读候选工具

`scripts/weknora_candidate.py` 仅使用标准库，不调用网络、Docker、模型或凭据，不扫描生产资料、不创建／复制／删除文件。CLI 只读指定 JSON，返回有界摘要与哈希，详细条目可由 Python 函数取得。错误仅输出稳定错误码，不回显原文、路径或秘密；日志由宿主收集到任务 `logs/`。

```bash
python scripts/weknora_candidate.py capacity /explicit/capacity.json \
  --available-disk-bytes 0 --available-memory-bytes 0
python scripts/weknora_candidate.py inventory /explicit/materials.json --root /explicit/material-root
python scripts/weknora_candidate.py benchmark /explicit/gold.json /explicit/actual.json
```

以上是参数示例，`0` 不是容量准入。退出码 `0` 表示本项输入检查通过，`1` 表示容量或基准未达标，`2` 表示输入拒绝。任何结果都不授予安装、启用、迁移或部署权限。

### 容量清单

清单 `schema_version=1`，固定 `release` 和 `source_revision`。`components` 恰好包括 `app`、`frontend`、`docreader`、`paradedb`、`redis`；每项声明 `image`（`repository@sha256:<64hex>`）、`platform=linux/arm64`、正数 `image_bytes` 和 `peak_memory_bytes`。`proof` 绑定 `image_digest`、`platform`、`source_revision` 和 `evidence_sha256`；前三个产品组件源码必须等于固定版本，第三方组件记录自己的源码版本。

`disk_bytes` 必须包含正数 `originals`、`database`、`index`、`parsing`、`recovery`、`reserve`。恢复副本估算不得小于原件、数据库及索引之和。总磁盘峰值为五组件镜像加上述各项；总内存峰值为五组件峰值加 `memory_bytes.parsing_extra` 及正数 `memory_bytes.reserve`。可用容量由调用方提供本次实测值，不以 Docker 总分配内存冒充空闲内存。

工具核验声明之间一致性，**不验证镜像仓库或证明文件真实性**；回执保留 `artifact_evidence=declared_not_runtime_verified` 和 `deployment_authorized=false`。镜像 digest／源码／ARM64 的实际构建证明与现场容量准入仍需单独完成，不填造示例 digest 作为真实证据。

### 显式资料盘点

旧底座分为会话inputs/outputs、网页取证、DataHub快照及Dossiers/固定Workflow资源四层，并非单一原件仓库。Store的附件ID来自相对路径摘要，不是原件内容哈希；网页取证和DataHub另有内容哈希合同。盘点必须区分这些身份，保留旧引用解析；模板、底稿、输出与金融快照继续由RWB管理。现场有界引用审计仅观察当前文件哈希，不能补造缺失的历史哈希；真人及WeKnora用户/空间未映射的资料保持原状。

清单 `schema_version=1`、`owner_id` 明确，`materials` 每项包含同一 `owner_id`、唯一 `source_id`、`kind=research_material`、根内规范 `relative_path`、历史 `legacy_ref`；可选 `original_sha256` 用于复核已知原件。函数 `inventory(root, manifest)` 只打开列出的文件，输出原件 SHA-256、大小、逻辑身份和旧引用，不保存正文或复制资料。

未知／其他归属、金融快照、模板、工作底稿、正式报告，以及 `snapshots/templates/workbooks/outputs` 路径拒绝纳入。符号链接、硬链接、根外／遍历路径、非普通文件、读取期间变化和超过容量上限均拒绝。单件上限 128 MiB、每清单上限 512 MiB／200件；超限须分批，不放宽门槛。盘点通过不表示已迁移，旧引用和原件继续保留。

### 冻结检索对照

先准备并冻结 `gold`：恰好20条唯一 `question_id` 与非空 `expected_document_ids`；`documents` 登记受准入文档的 `document_id`、`original_sha256` 和可核验引用对 `locator/excerpt_sha256`。完成金标后再采集实际检索，不能从新输出反填金标。

`actual.gold_sha256` 必须等于完整 gold 的规范 JSON SHA-256；实际20条问题逐一对应，每题至多8个顺序命中，每个命中包含文档身份、原件哈希、定位和引文哈希。至少18／20题命中预期来源，所有返回引用均与冻结语料匹配，且无语料范围外命中，才返回 `passed`。完整逐题预期／实际记录及其哈希由函数返回，CLI 只输出摘要。

此检查只计算**提供的冻结材料**是否达标，保留 `live_acceptance=false`。真实金标质量、实际检索调用、时点和权限由 RWB 及操作员独立验证；合成测试通过不能冒充实际周报检索或业务验收。

## 实施与验收状态

按顺序进行：显式盘点 → 候选容量及版本核验 → 隔离资料管理／检索 → 截至2026-10-30华安ETF周报固定资料对照 → 原窗口明确交接 → 同一 Workflow 的 Word／Excel 集成 → 按资料库分批切换。原窗口继续生产，不平行生成另一份周报。

只读候选工具不能证明本轮原实例恢复、新目录已完成同步、真实 Embedding、命中质量或原报告材料接受。恢复／备份、实际链路、双用户及撤权、原生宿主、完整报告、最终候选 CI、常驻服务与其他平台各自取证，缺项保持 `NOT_RUN`／`BLOCKED`。本轮原数据保留且不凭源码迁移；旧付费记录缺口继续单列，不能用新零生成观测覆盖历史未知。

非秘密origin的stdlib校验由 `research_workbench_entrypoint/knowledge_configuration.py` 供公开dispatcher和冷Doctor共用，冷诊断不导入server启动模块或访问凭据。该修复与资料网络／存储admission仍使用原账号及维护边界，没有新增服务或执行角色。
