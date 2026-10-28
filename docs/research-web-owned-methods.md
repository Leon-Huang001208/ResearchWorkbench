# 三个自有原件核验方法

macOS Web 源码切片，版本 `1.0.0`。普通 Catalog 发布三份 `kind=skill`：
`owned-company-evidence`、`owned-news-evidence`、`owned-research-prep`。
它们分别处理公司原件核验、新闻事实与条件传导、调研材料准备；不是供应商同名能力等价承诺。
旧内置方法及 gated 算法不迁移、不改版本。唯一 DSH 继续负责叙事与原报告质量链。

## 冻结动作与台账

`capabilities/scenario_method_packages.py` 将 `skills/_shared/source_actions.py`、
每方法固定入口和证据协议复制为版本资源，所有 Python 字节进入 `reviewed_scripts`。
`references/method-code-manifest.json` 列出文件 SHA-256、方法版本和闭包哈希；Catalog 原有
check、publish、selection、snapshot 独立验证当前资源。该 manifest 不是授权或执行回执。

`scripts/check_sources.py:execute(root, context, execution_id)` 只接受 Host 冻结上下文。
上下文固定为 `research_method_source_context_v1`，包含方法、版本、规范对象、截止日及已选原件描述。
原件描述包含身份、已准入 inputs 相对路径、预期 SHA-256、完整字节 locator、公开日期、材料类别及
全文状态；财务可保留证券、期间、单位、币种、口径与快照 manifest 哈希。不能由模型或客户端正文、
provider、rights 或重新计算的哈希取得来源资格。

三个明确函数重新打开文件、拒绝链接和非普通文件、核对前后文件身份及 SHA-256，拒绝未来公开日期、
证券错配和未知字段。最多二十份原件、单份八 MiB、总计三十二 MiB；非 UTF-8 原件需先经既有 reader，
不安装 OCR，不把空页视为成功。完整原文不在台账中截断为所谓全文。

台账保存在 `outputs/method-results/<execution-id>/ledger.json`，排他创建并读回，包含源引用、
字节定位、输入哈希、实际读取计数、覆盖和缺失。`authority=analytical_output_only`、
`research_quality=NOT_RUN`；它不能自证 `ran`、供应商可用性、来源权利或历史 PIT。
Native 实际执行与 Host 独立读回属于单独验收。

## Host、Native 与读取边界

三份独立方法场景复用原 prepare/handoff/选材/发送，不修改原八合同。已保存原文选择器使用固定
目标 registry 区分两个 pack 与三个 owned-method，后者不产生 pack_seal 或伪造 pack_qualification。
Host 返回并提示 `method_execution={capability_id,version,context_sha256}`；它是预期绑定，不能包含
源、路径、provider、rights、code 或输出覆盖。直接选 Skill 而没有其固定场景返回 missing_selection。

Host 从当前授权原件构造 `inputs/methods/<digest>/source-*.source` 和 `source-context.bound`。
这些是私有冻结副本，不能作为上传文件、档案 file 或 Claw 引用；相同前缀的旧缓存文件 ID 和半文件
也拒绝。公开分析台账继续沿原来源权限读回。扩展名不是授权凭据；三个现有读取边界均做明确路径拒绝。
普通 code 不获得 methods 子树读权，不能写 method-results。只有固定新策略逐文件授予 read-data，
不开放父子树；原 weekly/pack 策略保持。实际 Host/Native 的原件、描述与全部资源合计上限为十六 MiB，
还受单份八 MiB、二十份资料和原脚本预算的交集限制。

准备阶段先验证来源、全部资源与闭包、数量、总字节、runtime 和固定 launcher 上界，再创建私有副本。
准备事务只记录本次排他创建的文件/目录及其父目录、dev/inode；确定失败时只回滚身份仍匹配的文件和
本次创建的空目录，已有文件、替换 inode、未知对象不删除。确认未写入执行回执且回滚成功的准备失败，
没有启动 Native，可以显式重试；未知残留仍被原 method_input_unbound 拒绝。Store save 异常后读回
同一 index 回执：新 ID 已提交或结果无法确认时保留 unknown，不返回执行 scope，不自动重跑。

原私有 pack-completion 桥仅增加严格 `kind=owned-method` 变体；方法不写 pack 账本。真实 supervisor
完成后，Host 重新授权并打开原件、冻结文件与实际台账，核验 dev/inode/nlink/hash，再用与已审资源
字节完全相同的 Host 固定函数复算。只有这些检查通过才写 receipts.method_executions 的 saved；
其位置仍为原 Store `index.json`，随既有保全索引扫描，不新增数据库或账本系统。取消、未知和失败不会
自动重跑，迟到结果不能变成 saved。每次质量检查继续验证来源和台账，动作缺失为 incomplete，
完整性变化、撤权和未登记残留为 invalid。原 source/numeric/canonical 质量门保留。

仅由私有 file_bindings 明确登记的内部副本从观察投影排除，原 selected/page-evidence 原件继续扫描。
未知文件没有前缀豁免；这避免把同原文的内部复制认作独立事实，不削弱旧质量校验。

公司方法不会自行解析通用财务报表或派生数值；财务单位、币种、口径不能在原文确认时保留缺口，
可比性仍须现有 business observations 对齐证券、期间和单位。原 report_plan 配方执行派生计算。
缺业务、竞争或估值材料不称完整公司报告。新闻方法保留全文、时间与反证缺口，条件传导由 DSH
根据实际原文生成。调研方法只做材料准备，没有真实访谈不能生成伪造问答。新闻/调研在显式带时区 `cutoff_at` 与上海 `as_of` 同日时，Host 从当前已授权原件调用
`project_source_version` 与公共 `execute_atom_bundle` 的 `deduplicate_source_versions 1.1.0`，
冻结原 receipt 与完整 full-result canonical 字节。其 legacy digest 对对象顺序敏感，调核前做 canonical
JSON roundtrip固定顺序；不改原核算法。`research_method_c2_dedup_v1` 另绑定 core、依赖闭包、projector、
完整 SourceSet（owner/来源与目标会话/原hash/locator/发表与取得时刻/映射及缺口）和 input digest。
制品进入原16MiB合计、逐文件 file_bindings 和准备事务；Native只读取Host上下文固定声明的制品，
核schema/hash/版本/SourceSet与输入覆盖后消费，Host completion/quality再重开来源、同投影与同atom复算。
身份明确为Host执行C2、Native消费，不称Native运行C2或供应商包。缺cutoff保持cutoff_timezone_required
及source_version_dedup_not_run；file/dataset不可映射、未来取得、角色/发表时刻/上游完整性未知仍保留gap。
不从日期补造时刻。PDF/OCR 自动接入仍未实现，不可读原件拒绝。

MSFT 原文仅沿原 business_observations/report_plan 复算已给定表格数据；现有解析器不认证公司实体、
通用币种与 URI 等价，方法投影保留 unclassified/financials 缺口，未新增 MSFT URL 专用分类。
DataHub 财务快照只从真实 manifest/query/规范 rows 保留证券与报告期；当前 Sina v3 的明确 rCurrency
字段保留币种，单位与累计 reporting_basis 未明则保留未核验，不能据此认证全市场财务覆盖。
公司冻结合同由Host独立投影 `calculation_policy=owned-company-positive-base-v1`；SDK与Host verifier
都把它传到原recipe及Summary实际resolved operands处。percent_change基数非正拒
`owned_percent_change_nonpositive_base`；Summary以$step/abs或派生observation作基数拒
`owned_percent_change_derived_base_unsupported`。公司canonical必须有system_plan，调用方删policy或手写
canonical不能跳过Host从原handoff/contract重建的门。正245122/211915仍为15.67，当前值为负但基数为正
保持原语义；generic、旧八场景和weekly默认数学不变，difference必须显式选择。此门不清除原可比性缺口。

## 严格参数适配

`scenarios/native_argument_adapters.py:adapt_query_news` 仅接受 `query` 与严格整数 `limit=1..100`。
bool、float、未知参数和 URL 均拒绝。输出为现有 `datahub_search_news` 参数；CLS 当前仅对有界最新
快照做正文子串过滤，limit 在过滤之前，不提供全库、历史或所有来源筛选。

`adapt_research_question` 只对 `company_one_pager`、`fundamental_analysis`、`research_outline` 提供
`query→question` 预置。需要 Host 当前选择的规范主体、截止、材料和当前方法版本；缺失返回
`missing_selection`。不能从自然语言抽取证券并自动取数。适配的实际入口是固定RWB wrapper `rwb_query_latest_cls_news` 与owned准备区的三个问题预置。
wrapper复用原private business-query的strict request_kind变体、身份/取消和真实DataHub.query/broker/
provider/snapshot链；原datahub_search_news完整日期及通用schema保持。模型目录只对该wrapper独立
查Host的CLS本地readiness与datahub scope，拒绝时仅掩蔽该工具，实际调用再次强鉴权；不运行网络probe。
三个预置在新handoff/preview/request hash及contract形成前，由Host核当前规范对象/asof/资料与方法
selection，实际调用adapt_research_question冻结question；已有question与preset_query冲突明确拒绝。
不从query猜证券，不换旧任务问题，不注册供应商别名。C1仅这五个参数标native_subset，原别名仍拒调用；
其他参数保持unsupported，`fetch_news_url.url` 不接受替换为 read_source URL。

## 验证状态

目标测试实际覆盖严格参数、原件读回、哈希变化、日期、证券、未知字段、标题无正文、缺口保留、
Catalog 发布及完整资源快照、冻结脚本实际执行与排他写入、未审核脚本拒绝发布。
新执行测试实际使用已固定 DSH 的 FileSystemSkillProvider、ToolRuntime、skill/guard、原 Native
runner 与 macOS sandbox、真实 Host private bridge；三方法分别原件读取→台账→Host 复算→原 report_plan
生成 canonical/HTML/DOCX→真实 research_check_quality，缺证保持 incomplete。公司表格独立预期
245122/211915，系统同比显示 15.67；未手填结果。另覆盖取消、未知不重跑、普通 code 禁读写、回执丢失、
来源撤权、半文件与三个 file-alias 入口。未知普通文件仍可令实际质量返回 invalid。
来源 HTTP 在输送边界用固定离线响应，叙事采用 scripted 测试文字；真实模型、供应商网络、正式报告接受、
常驻部署与其他平台均 NOT_RUN，不把上述动作成功当模型能力通过。

2026-10-28 C3b/C4目标集实际34项通过；另六条正例完整Native/report/quality链复验通过，
包含两个显式cutoff的C2实制品及三个问题预置。合成负基数原文另经真实Native report_plan拒绝：
runner failed/exit1、稳定owned_percent_change_nonpositive_base、无canonical，quality保持incomplete。
不能把ToolRuntime transport isError与子进程状态混为一谈。CLS wrapper由真实pinned ToolRuntime经
Host纯adapter、DataHub.query、原CLS parser及snapshot执行；HTTP仅MockTransport，未mock DataHub.query。
已实际核验limit先行、casefold、empty/空query、strict参数、scope/CLS disabled与取消不落快照。
UI/guard50项通过，包含仅wrapper目录掩蔽/恢复、cutoff和preset冲突/切换。独立评审、完整CI及
同候选Mac干净安装由主任务另验；此代码切片不等于整个T3或62Skill/78Tool融合完成。

独立SPEC发现的预置空原题表单P2已修复：仅当前owned场景的合法固定preset及有效query可替代
原question textarea的required；同一前端谓词用于控制器校验。旧八场景和无有效预置仍保留必填，
已有原题冲突仍明确拒绝，不关闭form原生校验。隔离Chrome实际renderer/controller验证三个preset-only
各submit/handoff一次，空题/错配/空或URLquery受原生必填阻断，冲突题由控制器拒绝；不是完整HTTP旅程。

目录回归固定保留原15个business工具并仅增加CLS wrapper（共16）；底层news未启用时不注册wrapper。
内置Skill UI固定为旧39加三owned CID（共42），18个receipt-gated仍disabled，新三项当前v1仅表示
目录版本与可准备草稿按钮，不授予来源或研究通过。closed script mode测试按四种互斥模式的精确拒绝合同
核验空/mixed输入零spawn；这些测试更新不改变产品运行代码。

真实SDK wrapper合同现在独立为test_owned_news_native_sdk.py，无缺环境skip。通用Checks只跑完整Host
compat模块；原Mac Bootstrap在干净安装/Doctor/资源证明后，复用实际安装器Node与built pin执行SDK
专项，已声明测试工具仅在CI临时venv准备，installed app字节与原runtime distributions保持。普通本机
Node选择可用RWB_TEST_NODE或PATH，缺可执行明确失败；固定SDK须有正确Git HEAD及实际compiled libs。

Native child close到私有完成桥之间仍可能收到取消。桥在入口、两次真实await后和dispatch前重验调用
AbortSignal，组合原signal与有界timeout；wire已发送后的中断保持未知，不新call自动重试。Host在原
service.lock内只信服务器当前receipt accepted、同key/task/marker且cancel_request.accepted严格true，
再绑定本execution任务；取消先接受则state=cancelled，保真实Native completed原结果而不新saved。
先已saved的成果及其独立readback不被后来取消倒改；acceptedfalse、foreign/newtask不误取消，身份不明
在写状态前保持原unknown_do_not_retry，不增enum/binding/schema。时间早于execution start不能放行同一
已取消任务。Mac Bootstrap同一步硬跑SDK一例加pack/method六种真实取消顺序，JUnit exact7且0skip。
