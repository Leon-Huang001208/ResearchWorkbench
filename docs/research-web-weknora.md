# WeKnora 研究资料底座与报告证据

本合同只涉及研究资料原件、解析、索引和检索。WeKnora 使用自己的资料管理界面；RWB 继续保留金融快照、Word 模板、Excel 底稿、正式报告、冻结证据及现有看板。WorkBuddy／Codex 负责研究写作和既有 Workflow 编排，确定性程序继续完成计算、图表、Word 装配和质量检查。

## 版本、身份与证据边界

- 基线为 WeKnora `v0.9.0`，源码 `f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7`。实际镜像必须固定 digest，核验源码及 ARM64 产物；不使用 `latest`。
- 两边独立登录，通过不可变用户及空间 ID 显式绑定。个人资料默认私有，跨空间共享须明确授权。
- 空间级 API Key 是机器权限，不自动继承真人用户的成员撤权。RWB 适配必须核验当前身份及授权，或通过用户原生认证让 WeKnora 执行当前权限检查；不能回退到管理员 Key。
- 普通检索按用户当前权限；固定报告先锁定服务器确认的允许文档、原件版本和截止期，再检索。上传时间不代替发布时间；未知时点材料不获得历史报告资格。
- RWB 冻结实际原件、哈希、引用定位及时间证据，后续重解析、删除或重启不能重写已冻结证据。冻结是独立写权限，不扩充现有四项只读 MCP。
- DSH 官方插件是同一 WeKnora 后台的客户端，首期不把其空间 Key 直连当作 RWB 多用户报告入口。

## 仅管理与检索的模型边界

默认候选为硅基流动免费 `BAAI/bge-m3`，允许处理用户批准外发的个人研究资料。实施时重新确认价格、实名认证和账户限流；不自动选择 `Pro/` 或其他收费型号。无可用免费服务时另行落实本机向量化，独立建索引并验证，不混用向量。

WeKnora 普通初始化向导要求配置 LLM，且摘要默认开启。固定版本的表格摘要还有独立入队路径，不能仅凭关闭普通摘要就推定无生成调用。仓库提供受固定源码／前后像哈希约束的显式 opt-out 补丁 `deploy/weknora/patches/`，但它只让明确 `summary_enabled=false` 的上传、URL 导入及两种重解析路径不入表格摘要队列，保留缺省及开启时的上游行为。补丁夹具可应用不等于 Go 或服务验证；其他摘要、QA、Graph／Wiki和图像增强仍须分别关闭。

**WeKnora 界面的上传／重解析零生成上线仍为 `BLOCKED`。** 在0001之后，`0002-retrieval-only-profile.patch` 已提供实例级服务端策略源码：仅在专用全新候选实例显式 `WEKNORA_RETRIEVAL_ONLY=1` 时生效，缺省关闭。它强制关闭入库生成增强，即使界面省略或传入 true；使用内置确定性解析，阻止表格／画像／图像及后处理生成队列，并以固定允许列表拒绝其他生成 API。该配置不负责接收或清理既有生成任务、旧队列或正式资料。

源码实现状态为 `IMPLEMENTED / AWAITING_VERIFICATION`；Go 原生编译已完成，但目标用例因上游初始化崩溃未开始，Go运行为 `BLOCKED`。真实服务、管理界面和零生成调用计数仍 `NOT_RUN`，实际结果记录在任务回执，不改写固定补丁 manifest 自证。只有这些门全部有真实证据后，才能将 WeKnora 界面认作本轮可用入库路径；不能用虚假 LLM、自动收费回退或绕过界面声明完成替换。真实免费 Embedding 亦独立验收。

### 配置模板与补丁链

`deploy/weknora/embedding-only.json` 是0001阶段的逐文档显式 opt-out API 模板，整份JSON不是API请求；其历史 `NOT_IMPLEMENTED`／BLOCKED字段不描述0002的源码状态。严格实例候选以[retrieval-only manifest](../deploy/weknora/patches/retrieval-only-manifest.json)为准，按固定release → 0001 → 0002 → 0003顺序绑定前后像与补丁哈希，再显式设置 `WEKNORA_RETRIEVAL_ONLY=1`。0001模板不能独自放行原UI上传／重解析。该链仍只适用于全新隔离候选，Go／服务／UI验证未完成前不启用生产，也不把manifest中的NOT_RUN改写为通过。

### 原生知识库设置补丁0003与当前验证

`0003-retrieval-only-kb-settings.patch` 在0002之后增加只检索模式的原生知识库设置：先由 API 建立文档库，再从原界面编辑；首个知识库创建向导仍未支持该模式。认证服务端标记决定 profile，客户端请求不能自行开启该权限；普通模式继续校验真实 Chat 模型。补丁及前后像绑定见[kb-settings manifest](../deploy/weknora/patches/kb-settings-manifest.json)。固定 manifest 的 `NOT_RUN` 不由任务验收回填。

当前独立上游 Node 纯函数8项通过，只证明设置逻辑；完整 Vue 构建、真实 WeKnora 服务及浏览器入库仍未验证。原生 Go 可以完成编译，但测试初始化在上游 `go-m1cpu` 崩溃；两次 Docker 编译受容量门阻断，未进入测试。上述均不能写成 Go runtime PASS。RWB 自身隔离浏览器通过，也不替代上游 UI、免费 Embedding 或业务报告接受。

## 接口与权限

状态和Doctor中的 `expected_release`／`expected_source_commit` 是本适配要求的目标版本，不是已连接服务的运行版本证明。绑定状态还提供 `credential_cleanup_pending`：为 true 表示旧凭据槽保留待处理，不能把新绑定成功解释为旧凭据已全部清理；不会返回凭据内容。

以下路径均位于现有 Host／认证网关边界；调用方不能选择 RWB owner、数据根或上游 URL。默认 `RESEARCH_WEKNORA_ORIGIN` 为空，状态读取不联网。操作员设置仅接受无凭据、路径、查询和片段的 HTTPS origin，HTTP 限回环／localhost。配置无效或缺少授权时拒绝，不降级空间 Key。

| 方法与路径 | 权限与实际作用 |
| --- | --- |
| `GET /api/research/knowledge` | 本机绑定元数据；`connectivity=not_verified`，真实服务与报告均 `NOT_RUN`。 |
| `POST /api/research/knowledge/binding` | 明确用户动作；接收 `token` 与正整数字符串 `workspace_id`，用上游原生用户身份验证后保存受保护凭据引用。 |
| `GET /api/research/knowledge/bases` | 显式读取该用户当前可见库，返回 `items`；不做问答或建库。 |
| `POST /api/research/knowledge/scopes` | 明确用户动作；确认来源可得时点与时间证据，锁定报告期、截止、原件及完整分块指纹。 |
| `POST /api/research/knowledge/search` | 普通检索或已批准 scope 的 Top 8 原文命中，不返回生成答案。 |
| `POST /api/research/knowledge/read` | 读取当前授权文档及实际分块；给出 scope 时同时复核冻结字节。 |
| `POST /api/research/knowledge/freeze` | 明确用户动作；只冻结已有 scope 内选择的分块和相应原件，独立写入证据。 |
| `GET /api/research/knowledge/evidence/{identifier}` | 当前 RWB 账号读取本地不可变证据，复核 manifest 和已存原件。 |
| `GET /api/research/knowledge/evidence/{identifier}/original/{sha}` | 当前 RWB 账号下载该证据实际包含的原件，不解析任意路径。 |
| `POST /api/research/internal/data/knowledge-query` | 原 DataKey 回调，仅查询；必须带已有 `scope_id`。 |
| `POST /api/research/internal/data/knowledge-read` | 原 DataKey 回调，仅读取；必须带已有 `scope_id`。 |

资料异步操作在网络读取、授权复核和存储提交全过程持有既有 resident `admission`；维护冻结生效时拒绝新操作，返回 `knowledge_maintenance_busy`，不通过查询通道绕过停机门。绑定元数据写前及读取同为16 KiB上限，超限不写入不可恢复的大记录。

绑定、scope 与 freeze 要求 `X-Research-User-Action: ?1`，不授予内部工具写权限。JSON 请求有明确长度且不超过64 KiB，验证失败不回显 JWT。浏览器输入提交即清空，卡片不缓存凭据、原始响应错误或向宿主转发秘密。失效、撤权、身份改变及空间变化均要求重新核对，不自动续令牌或回退管理员。

RWB owner 是当前 `Store.root` 的摘要，绑定及证据复制到其他账号根会拒绝。WeKnora 的 `file_hash` 是来源 MD5；范围权威使用实际下载字节的 SHA-256，以及按分块身份、文档／库身份、正文、序号和定位计算的完整指纹。报告查询在上游召回前附加允许文档 ID，前后复核当前身份；原件、分块或库范围漂移均拒绝。原件每件8 MiB、冻结事务32 MiB、manifest256 KiB，账号保全合计64 MiB，超限保持失败，不裁剪证明。

`available_at`、`time_evidence` 和 `confirm_source_times=true` 记录认证用户对真实来源证据的明确批准，**不是自动推导的发布时间或历史 PIT 认证**。晚于 cutoff、未知时点和重复文档在上游检索之前拒绝。报告 scope 不能由 DataKey、四项只读 MCP 或模型文本创建。既有正式报告的质量及定稿权威不变。

## DSH 单轮只读资料

普通研究的认证消息入口可在全新 FinGPT 会话中附带 `knowledge_scope_id` 与
`X-Research-User-Action: ?1`。提交即确认当前运行可将所选原文交给会话模型。
Host 在派发前复核范围，持久化 scope 与幂等指纹，并封存会话。相同幂等请求复用受理
回执。索引写入失败时回滚未派发的授权。受理未知、历史续发与升级复制会话均拒绝。
场景及证据交接会话沿各自冻结范围和截止点。普通研究的资料授权由认证 API 完成。

固定 DSH 工具 `research_read_knowledge` 支持 `search(query)` 和
`read(document_id, chunk_id)`。工具使用实例私有 DataKey 回调。Host 通过当前
会话的原生首轮、原生请求 ID 和受理回执确定范围，并在返回前再次核对。检索最多八条
原文定位，读取只返回一个批准分块及原件与引文的 SHA-256。撤权、取消、原件漂移、
子 Agent 和未授权会话均不能读取。通过认证 API 创建 scope 和冻结证据。

实测顺序为隔离实例零生成验证、双用户权限与冻结、20 题基线，再在最终候选以公开样本
完成一个 DSH 回合。若仅命中率未达标，可用原语料和金标做一次关闭上下文补充的同口径
对照。DSH 实测先要独立授权和最多三次实际发送的硬限额，底层重试也计数。现有
Docker text 预算档拒绝工具，旧工具验收档只允许基金数据，均不能认证本工具实测。

## 本机诊断与保全

Doctor 的可选 `knowledge_backend` 项只检查当前账号内的绑定和不可变证据保全，不读凭据、不联网、不创建未配置的数据根。已配置不等于已连接，模型与报告验收保持 `NOT_RUN`。`knowledge-backend/` 加入既有私网账号保全；中断 staging、未知目录、哈希变化或预算超限阻止收尾与切换，不清空或迁移原件来放行。

现有一键安装不安装 WeKnora／Go／新 Python 或 Node 依赖。隔离服务安装、模型凭据、真实资料迁移和常驻切换仍按项目规则单独落实；底座替换尚未完成，不改变另一窗口的原周报运行。

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

本合同和只读工具不证明已部署 WeKnora、已迁移资料、已发生真实 Embedding 调用或已取得原报告材料。上述真实链路、双用户共享撤权、原生宿主、完整报告、正式部署和其他平台在取得对应证据前保持 `NOT_RUN`／`BLOCKED`。源码验证、同候选 CI、本机服务、宿主调用、业务报告和部署分别记录。新依赖、凭据处理、生产迁移及常驻服务更新仍需按项目规则单独落实。

非秘密origin的stdlib校验由 `research_workbench_entrypoint/knowledge_configuration.py` 供公开dispatcher和冷Doctor共用，冷诊断不导入server启动模块或访问凭据。该修复与资料网络／存储admission仍使用原账号及维护边界，没有新增服务或执行角色。
