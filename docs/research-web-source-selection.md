# 研究组合包原文选择合同

`scenario_source_selection.py` 是 Host 的有限文件准备桥，仅供 `pack-research-prep`
和 `pack-global-opinion`，以及固定 registry 中三个 `owned-*` 方法场景。后者按
独立 method_execution 合同准备，不制造 pack_seal。均不注册供应商工具，不抓取网页、不调用模型，不建立第二个研究引擎。
包的公司 `stock`、行业 `industry`、主题 `topic` 沿 `pack_catalog.select`；自有方法沿
`method_catalog.select`，新闻方法允许三类，另外两个方法只允许stock。均保留完整subject及合法name；行业仍为真实分类身份（如 `sw:801890`），主题保留原中文文本。
原八场景、资产 bundle、基金、日线和原 source/file 权限边界保持。

## HTTP 与只读边界

- `GET /api/research/source-selections/sessions/{sid}`：重验本人会话、祖先、当前 web 权限、
  原文 hash 和私有 capture proof；返回标题、source ID/SID、hash、取得时刻、日级发表信息、
  host、未知语言/地域/角色及 capture 状态。不返回正文、摘录、原文 path/下载 URL 或 proof。
- `POST /api/research/source-selections/preview`：closed `{handoff, sources}`；sources 仅允许
  `{source_session_id,id,sha256}`，1–20 个，重复同 SID/ID 拒绝，同 URL/hash 不同 SID 保持独立。
  handoff 为原 closed Handoff，必须是真实已有来源会话、上述固定 registry 目标之一、明确 datahub/uploads/web
  三 scope，`material_ids` 精确对应 dataset_ids；不得提供 workspace_material、context 或观察。
  纯内存复用原 prepare_context 的私有 reader，逐条重读已授权原文并提供真实 qualification。
  不创建文件/业务记录、Native 会话或模型请求。内部暂定 file token 只服务原材料一致性检查，
  不返回为可执行权限。返回确定性 preview_sha256、方法 closure/input 摘要、实际可执行方法及缺口。
- `POST /api/research/source-selections/freeze`：相同请求加 `preview_sha256` 和原
  `Idempotency-Key`。重新计算 preview，变化返回 409；发布真实 manifest 后调用原
  `create_handoff`，返回原 prepared/draft 或原 creation_outcome_unknown 结构，最终 Send 仍独立。

预览 digest 绑定完整请求、当前 SourceMeta、原件 hash、真实资格和能力版本。所有客户端
owner/rights/provider/coverage/rows/body/URL/path/module 自证字段拒绝；方法参数仅沿各固定场景schema校验：包使用scenario_inputs.research_scope，新闻/调研自有方法可显式cutoff_at；
问题预置在Host核当前选择后形成question。不从浏览器选择reader或执行模块。

## 文件、私有登记与重验

文件为 `inputs/source-selections/<selection-id>.json`，不使用受管网页命名。
closed `research-pack-source-selection/v1` manifest 仅包含 schema/schema_version、选择身份、
确切 scenario、真实 subject、as_of、完整请求摘要及 sources 三字段引用。无正文、密钥、
owner 声明或质量通过位。selection-id 绑定 request SHA 与 preview SHA；相同请求的新资格
版本可以在新 key 下形成新的不可变文件，绝不覆盖旧文件。

私有 `.control/source-selections/` 的 key 绑定与选择 intent 使用既有 directory/write_new/
fsync/读回机制，仅位于当前服务账号根。intent 保留完整请求、已重验 SourceMeta、manifest
和 file token，不是 Dossier、来源签章或额外权限。最多 256KiB，不增加数据库或签名系统。
manifest 必须逐字节等于私有登记，不能只用上传 JSON 的 self hash 认证 Host 来源。
`snapshot_selection_receipts` 在原 `snapshot_dossiers` 的 retention fence 内枚举固定私有
命名空间并返回实际文件 SHA；现 multiuser preservation 与 resident `@dossiers` 消费者复用，
未知发布/创建的 key 和 intent 同样保全；无 Dossier 的账号不因此初始化数据库。

pack-only reader 按固定登记路径精确派发；原 asset bundle 仍走原 reader。新 manifest
用于其他场景时拒绝，不做异常 fallback。每次读取都走 resolve_reference 验实际文件/源/祖先，
重核完整原请求、所有源当前 metadata/hash/proof，并重新计算同一语义 preview 摘要，拒绝
能力版本、参数、截止、来源或资格变化。真实交接始终按文件重建 context/seal/hash，preview
中的临时 token 从不进入执行。manifest 和全部源引用共同写入原 intent.lineage，再沿原
复制、封印、发送、Dossier 与删除 fence 保持 target/source 权限；不把网页改作 uploads。
重算预览只发生在新的 prepare/交接准入。已冻结档案与结果读取的 `trusted_context` 沿原
references/expected hash/target scope 复验，不调用此 reader、不按最新预览替换历史 context。
只有实际成功的私有登记 reader 所确认的精确 envelope 身份，不作为研究原件映射；因此
预览与冻结的 qualification 全字段一致。该文件继续完整保留在 references、hash、权限、
lineage 与封印重读链；普通 file 和旧 asset bundle 仍保留其原材料缺口，不按扩展名豁免。

## 幂等、未知和保全时点

相同 key/完整请求/preview 只发布一份选择文件，原 create_handoff 同 key 只创建一次研究。
相同 key 的参数、源或预览版本不同均 409。文件 intent 已登记但发布未确认时只核原文件，
不存在或未登记则 `source_selection_write_unknown`，不补写、不换 key 或重复创建 Native。
RPC outcome unknown 沿原 `/api/research/handoff-requests/{key}` 对账，同 key 重读保持 unknown。

freeze 预检沿原 `workbench_lock → service.lock → retention_lock` 顺序，仅服务器内部标记
尚未开始任何发布的纯预检失败。私有同 key/selection intent 已存在或无法安全读账时不标记。
共享的原交接 helper 再在创建锁内核对本账号同 key 无任何 handoff intent，才返回原
`error.handoff_outcome=not_created`；此前 accepted/unknown/prepared 均禁止该证明。
文件/receipt 发布、IO 和未对账发布异常不获标记；lookup 404 本身从不证明未创建。
外层创建锁及 service.lock 在调用原 create_handoff 前释放，旧 sender 自己的 hash/intent
幂等锁保持。只有明确 not_created 才能保留输入后修正；未知仍用原 key 观测。

选择文件不是 retention holder。只有原 handoff intent.lineage 持久化后，源及 manifest 会话
才受原保全关系保护。文件发布到原 intent 之间若源被永久清理、撤权或改变，真实 prepare
立即拒绝，不重抓、不默建档案、不伪造保全。freeze 成功才返回原 prepared；未知状态不承诺
已准备完成。没有当前 proof 的合法旧原文保持 completeness unknown，不升级全文/海外/角色/
历史 PIT 或研究质量；proof 缺坏的新捕获保持拒绝。

## 验收与本切片范围

定点测试 `tests/research_web/test_scenario_source_selection.py` 覆盖三主体、只读零写入、
多会话同哈希来源、重复/外来引用、客户端字段、当前权限/proof/hash、参数变化、真实 manifest
及原交接/草稿、保全窗口和未知不重建；opt-in 测试复用 pinned DSH 的真实 ToolRuntime/
FileSystemSkill/guard/macOS sandbox/Host 产物读回，供应商和 LLM 不执行。

C6b UI 已在本候选实现，浏览器证据见 [UI合同](research-web-pack-ui.md)；真实模型、62/78 全项能力、
T4/T5、最终候选CI与常驻部署仍独立待验，静态映射不等于供应商 alias 已注册。
API Atlas、架构图文和模块登记已在本轮集成元数据核对；完整changed-set Router、最终评审、CI与
交付收尾由主控在最终候选认证，不能以本模块本机通过替代。
