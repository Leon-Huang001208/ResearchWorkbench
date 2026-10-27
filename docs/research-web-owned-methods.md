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

台账保存在 `outputs/method-actions/<method-id>/<execution-id>.json`，排他创建并读回，包含源引用、
字节定位、输入哈希、实际读取计数、覆盖和缺失。`authority=analytical_output_only`、
`research_quality=NOT_RUN`；它不能自证 `ran`、供应商可用性、来源权利或历史 PIT。
Native 实际执行与 Host 独立读回属于单独验收。

公司方法不会自行解析通用财务报表或派生数值；财务单位、币种、口径不能在原文确认时保留缺口，
可比性仍须现有 business observations 对齐证券、期间和单位。原 report_plan 配方执行派生计算。
缺业务、竞争或估值材料不称完整公司报告。新闻方法保留全文、时间与反证缺口，条件传导由 DSH
根据实际原文生成。调研方法只做材料准备，没有真实访谈不能生成伪造问答。版本去重继续使用既有
source-version 制品，动作本身不重写去重算法。

## 严格参数适配

`scenarios/native_argument_adapters.py:adapt_query_news` 仅接受 `query` 与严格整数 `limit=1..100`。
bool、float、未知参数和 URL 均拒绝。输出为现有 `datahub_search_news` 参数；CLS 当前仅对有界最新
快照做正文子串过滤，limit 在过滤之前，不提供全库、历史或所有来源筛选。

`adapt_research_question` 只对 `company_one_pager`、`fundamental_analysis`、`research_outline` 提供
`query→question` 预置。需要 Host 当前选择的规范主体、截止、材料和当前方法版本；缺失返回
`missing_selection`。不能从自然语言抽取证券并自动取数。适配函数不是工具注册；实际入口尚未连接的
参数继续保持 pending，`fetch_news_url.url` 也不接受替换为 read_source URL。

## 验证状态

目标测试实际覆盖严格参数、原件读回、哈希变化、日期、证券、未知字段、标题无正文、缺口保留、
Catalog 发布及完整资源快照、冻结脚本实际执行与排他写入、未审核脚本拒绝发布。
这些测试不认证 Native ToolRuntime 完成、真实模型、供应商网络、正式报告接受、常驻部署或其他平台。
完整 Native→canonical→quality 证据必须另由当前执行链提供；不得以测试文字冒充模型生成。
