# 长期研究档案

档案沿当前 ResearchService 的个人 Store.root 保存；没有公共档案根、第二研究引擎或 PostgreSQL 连接。公司使用市场代码，行业／主题保留独立 key；名称不是合并依据。Web 页面和后续机会扫描均复用这份元数据。

## 持久化与版本

个人根的 `dossiers/metadata.sqlite3` 只在首次显式写入时初始化，GET 与服务构造不创建该文件。SQLite `user_version=1` 与账户根绑定；新建目录为0700、文件为0600。档案、事件、原件引用、成果关联、保全引用、冻结交接和幂等请求同库保存，源字节继续保存在既有会话／DataHub 快照中。幂等回执保存版本指针，历史视图由不可变事件重建，避免每次编辑重复保存全部旧观点。

已存在的dossiers目录内数据库缺失或为零字节时，返回稳定503 `dossier_storage_uninitialized`，列表、写入、备份与永久删除保全检查全部停止，不返回空列表或重建数据库。首次初始化事务失败留下的空库也需人工核对恢复；只有首次创建目录的同一事务能暂见自己的未提交空文件。显式restore在完整验证备份hash、账户、pin与原件后，才允许原子替换缺失／空的目标；旧pin随恢复重新生效。

首次显式初始化先在保全锁内以O_EXCL、0600创建根级 `.dossiers-initialized`，fsync文件及根目录后才创建dossiers目录。目录整体缺失时，持久标记使重启后的读取、写入、备份和purge仍返回503。未初始化账户的GET不写标记，初始化失败后不自动重建。标记必须是当前用户所有的私有普通文件、单链接，拒绝符号链接／重解析点，并验证路径inode、精确长度和hash；损坏标记以 `dossier_marker_invalid` 停止操作。

保全接口为 `DossierStore.marker`、`marker_size`、`marker_sha256`，构造零I/O。标记是123字节UTF-8紧凑JSON、键排序且无换行：`{"format":"rwb-dossiers-initialized-v1","owner_binding":"<sha256(str(root).encode())>"}`。marker_sha256是这段账户绑定字节的SHA256，不是数据库内容hash。根级标记须与SQLite及原件一起进入业务保全；显式restore完成备份hash／owner／pin／raw核验后可以恢复整个缺失目录并补齐缺失标记，已有安全标记不重写。

所有档案写入要求 `expected_revision` 和8–128字符 `idempotency_key`。相同键与请求返回原版本结果，不同请求或版本争用返回409；失败事务不推进版本。观点、风险、催化剂均追加记录修订，详情展示最新投影，timeline保留原修订。归档不是删除，也不释放原件保全。

根目录 `.dossier-retention.lock` 是跨进程、非阻塞保全锁，覆盖证据解析到引用／pin提交，以及 DSH `session.delete` 到 Host purge 的完整窗口。争用返回 `dossier_retention_busy`，不在事件循环里等待文件锁。Host原生日志永久删除前和Store.purge各自检查引用，软删除不解除引用。外部手工删除不能被此锁防止，只会在读取时显示 missing／changed。

## 证据与成果

证据请求只接受来源会话、受控引用及用户定位说明，不接受 owner、根目录、hash、披露日期或“passed”声明。Host从现有原件解析来源、SHA256、字节数、权限、已证实公开日期和取得时点；数据的观察期 `as_of` 不冒充公开日期。手工上传文件的取得时点是Host首次归档读取时间，未知公开时间保持null。

支持三类引用：

- `file`：会话内 `inputs/...` 或 `outputs/...` 相对路径，拒绝路径逃逸、符号链接及硬链接；网页取得文件必须走原 `source` 身份，数据集必须走 `dataset` 身份。
- `source`：当前来源会话已取得正文的 `web:...`，只读已保存字节，归档与重读均不联网。
- `dataset`：既有DataHub不可变数据集，验证公开／私有manifest、原件hash及当前来源授权；MCP原件另逐次检查受管安装、schema与精确grant，未经准入的结果保持clue。

详情显示证据的 available／missing／changed／revoked／unavailable 状态。正文读取、交接重放及模型重读再次检查当前授权和字节，不用新取数替代旧版本。UTF-8投影最多24000字符，内部扫描可读取受控完整rows和manifest；二进制只返回明确的binary_source投影，未新增PDF／Office解析器。输出文件与未准入MCP结果可作为材料保存，不升级为数值事实。

已绑定来源按项投影失效状态与稳定error_code；一项旧原件缺失、变化或撤权仍保留其他来源及会话访问。精确读取坏原件继续拒绝，admission与事实观察只使用available项，质量上下文以 `dossier_evidence_gaps` 明确列出缺口。DataHub原始响应清单逐项核对受控路径、文件大小和SHA256；只有公开rows完好不能证明声明的raw原件仍在。归档、读取、一致备份及恢复都执行该检查。

成果关联只能引用Host已有会话、文件或报告，报告保留Host原有quality、内容hash与task身份；不会把报告正文复制进档案数据库，也不会把incomplete／invalid改为passed。普通文件接口拒绝数据集路径，MCP数据集禁止普通跨会话复制；应使用重新鉴权的档案交接。

报告关联优先选取同内容hash的既有不可变report-version；未形成版本的报告保留当前原件定位与hash。详情逐次投影链接state/error_code，历史quality只描述保存的原内容。`GET /{id}/links/{link_id}` 通过 `preview_url` 重新鉴权并核对字节后返回有界投影；覆盖或缺失的可变原件不能沿旧quality打开为当前成果。

## HTTP 与研究交接

`/api/research/dossiers` 提供列表、创建、详情、patch、records、timeline、evidence、links及handoff。列表和timeline有界分页；请求模型拒绝未知字段。links使用 `{type:session|file|report,source_session_id,reference_id?}` 加通用并发／幂等字段。

handoff只返回草稿：`{prompt,mode,auto_send:false,context,dossier_revision}`。context包含不透明 `handoff_id`、冻结档案版本、hash、必要权限及原件句柄。上下文最多64KiB，只携带最近20条记录的有标记摘录；完整记录仍由不可变版本保留，截断与省略数量明确展示。

只有用户真正发送研究时在 `Prompt` 结构化提交 `dossier_handoff_id`，Host才将该冻结receipt绑定一个明确sid。普通会话创建、浏览器候选加载与包含同样草稿的文本都不能授权。相同receipt只可同sid重放，跨sid拒绝；当前source_scope和mode必须覆盖原交接，不自动扩权。

`research_read_source` 的既有Host分支接受本会话绑定的档案句柄，返回原契约允许的canonical file／web／dataset来源ID。精确source参数进入原native preflight；只有已绑定的档案来源可通过该分支，原网页权限规则保持。当前会话登记可重建的证据句柄和hash，原业务观察、规范报告与质量门继续独立重建事实，不复制正文或启动第二执行器。

## 备份、恢复与部署边界

`DossierService.backup_to(new_path)` 使用SQLite一致快照，仅复制元数据；备份中仍包含原会话／快照引用。`restore_from(path, expected_sha256=...)` 验证摘要、账户根、SQLite integrity／FK、全部pin对应关系和当前原件后，才原子替换旧指针。验证或替换失败保留旧库。备份必须与原证据存储一同保全，单独SQLite不是原文备份。

全部HTTP写入沿现有resident admission；元数据事务、显式备份／恢复与交接绑定也在服务内部持admission，后台调用不能绕过维护锁。新档案根和lock属于业务保全清单。本文不授权执行正式恢复、常驻部署、供应商实测或处理真实凭据。

## 验证

`tests/research_web/test_dossiers.py` 覆盖真实子进程重开、幂等／并发、事务与pin共同回滚、路径／跨根隔离、missing／changed／撤权、软删保留、原生删除竞态及一致备份恢复。`test_dossier_api.py`覆盖结构化handoff绑定与重放、来源伪造拒绝、原生删除前置保护与Host质量保留。原JS quality-tool回归增加档案canonical身份及精确preflight参数。验收使用隔离临时账户和native fixture，不调用真实模型、来源服务或收费MCP。
