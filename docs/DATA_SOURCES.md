# 数据源清单

2026-11-25：`ext_finance_mcp` 新增正式 `market_bars` binding（固定岗底斯日频不复权）。
600519.SH 11-10～13 四行与 BaoStock OHLC/股数量一致、金额差异≤1元，total=4；
这是有限样本的股/元口径证据，复权与 PIT 未核验，默认源顺序不变。
源码与常驻部署分开，见[业务工具合同](research-web-business-tools.md)。

Research Workbench 查数据时先看本页。**2026-11-22** 在 `92ae4ae` 基线上增补了 FRED／BLS 的本次观测；其他条目保留 2026-11-15 按 `0ca0f4c0` 实现与已有记录核对的范围。表中状态描述具体入口的接入和验证范围；当前账号是否能取、能取到哪天，以请求当时的权限、响应和覆盖为准。

## 怎么选源

1. 到[行情数据](#行情数据)找价格、成交、指数、财务数值、资金流与宏观序列；到[文本数据](#文本数据)找公告、政策、报告、新闻、日程及文档原件。同一供应商的不同接口按各自能力查找。
2. 先匹配市场、证券代码、字段、起止日期、频率和数据口径。优先使用任务指定、覆盖匹配且当前可调用的入口。未指定来源时，数值从已有同口径快照或适用的 DataHub / 专用行情入口查起；正式引用优先找发布机构、交易所或发行人的原件。Wind 查询进入 [Wind 能力发现](../.agents/skills/wind-find-finance-skill/SKILL.md)选择对应工具。
3. DataHub 当前状态在 Research Web **设置 → 数据源** 查看，或按 [DataHub 合同](research-web-datahub.md)读取 `GET /api/research/data/connections`。查询时保留实际来源、时间、覆盖和缺口。需要换源时核对单位、币种、复权和指标定义。通过不同接口获得同一上游的数据，只算一个出处。
   RWB 全局设置从左下角账号菜单进入；二级侧栏收起或窗口较窄时，点顶栏的二级导航按钮展开分类，再选择“数据源”。该分类不按管理员身份隐藏；WeKnora 账号绑定卡片位于数据源页。
4. 正式研究保留数值、原字段、单位、币种、数据日期、实际取得时间和快照 ID，文本保留原标题、发布者、原链接、发布时间及版本。回测须另核历史当时可得时间（PIT）和修订版本。快照取得时间、报告期和预告日期分别记录。

表中“已适配”表示有现成入口，“已有样例”表示已有记录证明某个范围曾取到数据，“仅登记”表示待核验的线索。“原站核验”可走公开网页或用户提供的原件。账号授权、依赖、额度或服务开关按各行核对。

## 行情数据

| 来源 / 入口 | 提供的数据 | 接入状态与范围 |
| --- | --- | --- |
| Wind Excel · DataHub `wind` | A 股日线及不复权／前复权／后复权、近期报价、固定估值和财务指标、指数报价、主力及北向资金、两融、股东数据 | 已适配。依赖本机已登录的 Wind 与 Excel/xlwings，仅接受封闭字段。股票日线、资金流和两融单次最多 60 个日历日。见 [DataHub 合同](research-web-datahub.md)。 |
| Wind Excel / Client API · 华安 ETF 周报 Workflow | 周报合同所列 ETF 指标、境内外市场指数与资产价格、汇率、利率和交易日历 | 专用取数路径。按周报数据就绪表逐项核对，当前流程以 Excel 为主，Client API 按已验证字段使用。见 [周报数据合同](research-web-etf-weekly-data.md)。 |
| Wind MCP · 项目 Skill | A 股、港股、美股的筛选、行情快照、K 线、分钟行情及基本面；基金与 ETF 净值、规模、持仓及业绩；指数、板块、债券、宏观和行业 EDB | 已有独立工具入口。需要 Wind MCP 的有效接入及工具权限，实际范围以工具合同与请求结果为准。见 [Wind MCP 工具](../.agents/skills/wind-mcp-skill/references/tool-contracts.md)。 |
| 天软 CJPY · DataHub `tinysoft` | A 股及基金证券目录、交易日历；股票近期报价、日线、限定股票的分时／分钟 K、换手、复权因子、估值、财务摘要、股东、行业分类及两融等封闭字段 | 已适配。需受支持的 CJPY SDK 和账户配置，分时、复权与单位以逐接口已核范围为准。见 [DataHub 合同](research-web-datahub.md)。 |
| AKShare · DataHub `akshare` | A 股证券目录、A 股及 ETF 历史、指数不复权日线、交易日历、最近日线报价；财务摘要、限定新浪利润表、东方财富个股资金流和 CPI / GDP / PMI / 货币供应等宏观数据 | 已适配，部分有取数样例，需 SDK 就绪。AKShare 是接入库，保留新浪、东方财富、同花顺等实际出处。最近一条日线的报价属于日频。见 [来源账本](research-web-source-repair-ledger.md)与 [原生快照合同](research-web-vendor-snapshots.md)。 |
| BaoStock · DataHub `baostock` | 沪深股票不复权日线、证券目录、交易日历、单只股票、指定一个季末报告期的盈利能力及现金流比率 | 已适配，历史日线与部分财务指标有样例。财务累计／单季及集团／归母口径按字段核验，历史披露时点仍缺证据。见 [来源账本](research-web-source-repair-ledger.md)与 [DataHub 合同](research-web-datahub.md)。 |
| 东方财富基金 · DataHub `eastmoney_fund` | 基金净值及历史净值、当前档案、分红、披露持仓 | 已适配，部分历史净值有样例。按请求日期、实际分页和持仓披露范围使用。报告期和披露日分开记录，使用总回报时需另核复权口径。见 [DataHub 基金查询](research-web-datahub.md#查询与来源)。 |
| 东方财富访客行情 · 市场页 | 沪深北股票池及行情、涨跌宽度及成交额、指数报价和分时、行业和概念排行、沪深大盘资金 | 市场专用入口。根据现场响应核对覆盖；沪深大盘资金排除北交所。新浪有限指数历史可用于专项对账。见 [市场数据合同](research-web-datahub.md#无会话全市场数据)和 [缺口实测](../.ai/reports/2026-10-22-market-gaps.md)。 |
| 腾讯行情 · 全球市场页 | 固定九个境内外指数的报价和近期开收高低日线 | 已有九指数报价和每指数 100 条日线样例。成交量单位保留未知，扩展指数或日期须单独核验。见 [九指数验收](../.ai/reports/2026-11-06-global-market-indices-backend.md)。 |
| 中证指数／国证指数 · 指数结构采集 | 各自官网公布的指数成分及权重 | 独立指数数据库采集；用成分文件所属日期和覆盖。中证指数估值属另一个外部端点。见 [指数结构存储](DATA_STORAGE.md)与[外部入口目录](../app/research_web/datahub/external_sources.json)。 |
| 同花顺 iFinD QuantAPI · DataHub `ext_ths` | 已登记历史行情、实时报价、基础数据、智能选股等 HTTP 端点 | 需配置并核实字段、市场和额度。历史行情及个别资金流字段有受限真实样例。旧 iFinD SDK 为其他入口，按设备与账户独立核验。见 [外部数据合同](research-web-datahub.md#已整理外部数据源2026-10-13)、[历史样例](../.ai/reports/2026-10-23-datahub-source-verification.json)和[资金流样例](../.ai/reports/2026-10-23-remaining57-actual-validation.md)。 |
| 纽约联储 · `ext_nyfed/rates` | SOFR 等参考利率，SOFRAI 的 30／90／180 日复合均值与指数 | 有原生快照合同与有限样例。利率、无量纲指数及发布时间分别记录。见 [SOFRAI 合同](research-web-datahub.md#2026-10-25nyfed-sofrai-专用v3)。 |
| 美国财政部 · `ext_treasury/cash` | Daily Treasury Statement 的日度经营现金余额，含 TGA | 按账户科目识别余额，保留报告日及原单位（百万美元）。见 [官方数值快照](research-web-vendor-snapshots.md)。 |
| 世界银行 · `ext_worldbank/inflation` | 全球年度 CPI 通胀率（%） | 已有官方 API 取数样例。当前合同固定经济体 WLD 和指标 FP.CPI.TOTL.ZG，按实际日期与分页覆盖使用。见 [来源账本](research-web-source-repair-ledger.md)。 |
| 美国经济分析局 BEA · DataHub `bea_archive` | 2024 年二季度美国实际 GDP 季环比年化率的初值、第二版 | 固定官方档案。先归档再按规定的截止范围读版本。见 [发布版本合同](research-web-datahub.md#2026-10-23披露日期与官方发布版本)。 |
| 世界黄金协会 WGC · `ext_wgc/etf-holdings`、`etf-flows` | 黄金 ETF 四地区月度持仓与净流量，单位为吨 | 两个独立指标，各自保留月份、完整性和原件。见 [WGC 合同](research-web-datahub.md#wgc-月度吨数与研究时点2026-10-23)。 |
| SPDR Gold Shares · `ext_spdr/gld` | 单只 GLD 的净资产、黄金吨数、盎司数、发行份额 | 已有四字段原生快照和取数样例，范围为 GLD。见 [GLD 合同](research-web-datahub.md#spdr-gld-四项原生快照2026-10-23)。 |
| BGS，经 KAPSARC 转发 · `ext_kapsarc/production` | 各国家或地区的年度矿山黄金产量（千克） | 以已验证导出的年份、单位和覆盖为准，BGS 与转发入口共同指向同一数据出处。见 [BGS 合同](research-web-datahub.md)。 |
| 圣路易斯联储 FRED · `ext_fred/series` | 固定 FRED Graph CSV 序列入口 | 2026-11-22 经现有 Provider 真实读取 `DFF`、2024-01-02 至 2024-01-08，取得 7 行 `snapshot`，保留原始字段与原件。单位／频率字典、完整历史及 vintage／PIT 未由本次认证；不是 OpenBB 对拍。见[本次复用验证](../.ai/reports/2026-11-22-rwb-tool-reuse-validation.md)。 |
| 美国劳工统计局 BLS · `ext_bls/series` | 固定 Public Data API v2 统计序列入口 | 2026-11-22 经现有 Provider 查询 `CUUR0000SA0`、2024 年，实际 HTTP 403、0 行、`failed`；不伪报已连通，不与日历入口的历史超时混同。见[本次复用验证](../.ai/reports/2026-11-22-rwb-tool-reuse-validation.md)。 |
| 用户授权数据库 / 文件 / RWB 快照 | 已有报价、因子、财务表或用户交付的任何可核实数值 | 按具体表和文件登记来源、单位及有效期。DataHub `mysql` 支持目录与只读单表；同口径会话快照和研究仓可复用已取得的原件与版本。见 [MySQL 合同](research-web-datahub.md#用户-mysql-边界)和 [研究仓合同](research-web-market-store.md)。 |
| 其他目录项 | Tushare 的证券目录、日线、交易日历及财务指标；Fed、CFTC、LBMA、Cboe 等的经济序列、联储资产负债、持仓、定盘或衍生品数据；Yahoo／Nasdaq 历史行情、MOEX 指数日线、中证及其他指数估值 | 作为补源线索。逐端点区分已适配、已观测、仅登记、需独立连接器及不可调用。见 [外部入口目录](../app/research_web/datahub/external_sources.json)和[逐源记录](../.ai/reports/2026-10-23-datahub-source-verification.json)。 |

### OpenBB Provider 试点（2026-11-23）

已在独立 macOS Python 3.12 环境安装 `openbb-core==2.0.1`、`openbb-fred==2.0.0`、
`openbb-bls==2.0.0` 及锁定依赖，SDK 导入和命令帮助通过；没有修改 RWB 运行环境。
实际公共 SDK 的 FRED、BLS 命令均在 HTTP 前要求 API Key，不能直接接管现有匿名入口。
官方 BLS helper 的一次匿名请求超时，同端点同请求体的 HTTPX 对照返回 403，未取得可对拍数据。
FRED 转换还会删除缺失行和每条观察的 realtime 字段；BLS 转换简化 period 与脚注结构。
因此本批保留两个原 Provider，旧实现删除清单为空，不把安装成功称为数据接管成功。
后续扩大其他金融覆盖时再按具体 Provider 评估；数据许可、单位、修订及 PIT 仍由 DataHub 核验。
详见[本次实际试点](../.ai/reports/2026-11-23-openbb-provider-trial.md)。

## 文本数据

### 金融数据 MCP（2026-11-23）

`ext_finance_mcp` 通过固定 HTTPS Streamable HTTP 入口
`https://www.huaanifd.com/finance-data/mcp` 连接八家金融厂商。
本轮鉴权、五工具发现、八家目录通过；岗底斯 A 股 `600519.SH`、2026-11-16 至 19
日 K 线实际取得 4 行。行情与投研文本按原工具分别查询，复用本账号客户端令牌。
目录配置状态不代表各厂商权限和额度均通过；单位、复权、完整历史及 PIT 未认证。
源码已接入 DataHub，生产启用与正式 WeKnora 调用另验。
见[金融 MCP 合同](research-web-finance-mcp.md)。

| 来源 / 入口 | 提供的数据 | 接入状态与范围 |
| --- | --- | --- |
| 发行人、交易所、巨潮资讯 · 原站 | 公司公告、年报／半年报／季报、招股书、监管披露及相关 PDF | 正式引用优先核原发布方、公告编号、披露日期及附件。巨潮资讯和深交所的旧 DataHub 公告绑定停用，公开原件可从原站获得。见 [来源登记](../app/research_web/datahub/catalog.py)。 |
| 政府、央行、统计机构 · 原站或专用日历 | 政策正文与解读、统计公报、数据发布公告；Fed FOMC、BLS CPI／就业发布日程，以及上交所、NYSE、港交所的休市／半日安排 | 正文走原站核验，日程有专用入口或固定原件导入。记录计划时间、时区和实际发布时间。BLS 两路在专项实测中超时。见 [日历实测](../.ai/reports/2026-11-08-market-financial-calendar.md)和[交易所日历合同](../app/research_web/event_timeline/exchange_calendars.py)。 |
| Wind MCP · `financial_docs` | A 股公告、上市公司披露、招股书及定期报告检索；财经新闻、政策及政经动态检索 | 已有文本工具入口，需 Wind MCP 权限。用命中记录定位原文，按发布者和链接复核。见 [Wind MCP 工具](../.agents/skills/wind-mcp-skill/references/tool-contracts.md)。 |
| 天软 CJPY · `market_activity/events` | A 股单股公告标题、事件类型及公布日 | 已适配有界事件索引，单股最长 60 日。公告正文从原站或其他获准入口取得。见 [天软事件适配](../app/research_web/datahub/providers_cjpy_assets.py)。 |
| 财联社 · DataHub `search_news` → `cls/telegram` | 最近电报的内容、发布时间、ID 和原链接 | 已适配，已有小样例，无专业配置。调用读最近 1–100 条，不提供关键词或日期范围检索。见 [Provider](../app/research_web/datahub/providers.py)和[来源账本](research-web-source-repair-ledger.md)。 |
| Golddata / Vibe-Research · 研究情报、今日发现、资产资讯 | 财经资讯流、事件归档、第三方研判、市场及早餐焦点、按证券新闻与公告、上游研究报告记录及详情；情报页另有华尔街见闻及社交聚合入口 | 已接只读上游。关注缓存和覆盖，把聚合命中返回的原文链接、第三方研判和发布方报道分别引用。见 [今日发现](research-web-discovery.md)和 [Intel 路由](../app/research_web/intel_routes.py)。 |
| Federal Reserve Board · DataHub `ext_fed/news` | 官方 RSS 公告标题、摘要、原始 `pubDate`、GUID 和文章链接 | 固定读取 `https://www.federalreserve.gov/feeds/press_all.xml`，保存原始 XML 与内容摘要。RSS 摘要与公告全文分别标识，未知发布时间不推算；既有 Discovery 跟踪按条目身份及内容差分，不使用 Golddata 计费端点。见 [来源实现](../app/research_web/discovery/fed.py)。 |
| 东方财富、同花顺门户 · DataHub 外部端点 | 东财 `ext_eastmoney` 提供研报、新闻；同花顺门户 `ext_ths` 提供资讯、研报、期货研报 | 经 `datahub_get_external_data` 的 `ext_registry` 查各自 `reports`、`news`、`futures-reports` 等已登记端点。逐项核实响应和访问条件。见 [外部入口目录](../app/research_web/datahub/external_sources.json)。 |
| 新浪、财联社、华尔街见闻、金十 · DataHub 外部端点 | 新浪财经新闻；财联社首页、联储专题和热榜；华尔街见闻全球快讯、文章及热文；金十热门和重点快讯 | 固定入口已登记。财联社热榜另有签名参数要求。逐端点核实字段、原链接和发布时间。见 [外部入口目录](../app/research_web/datahub/external_sources.json)。 |
| Google News、Forex Factory、AIHOT 公网站、Reddit 及 RSS · DataHub 外部端点 | 新闻聚合、本周经济日历、AI 精选与日报、社区帖子和科技／数字资产报道 | 适合发现线索，覆盖及取数按端点验证。AIHOT 公网站与本机自主资讯是两个渠道。TikHub 提供小红书／抖音搜索，中金点睛 `ext_cicc/search` 提供文章／研报知识库检索，均依赖各自授权。见 [外部入口目录](../app/research_web/datahub/external_sources.json)。 |
| AIHOT · RWB 自主资讯 | AI 资讯、精选条目、原文视图、故事、议题、热点以及日／周／月报 | 有独立引擎与读取路由，需当前实例的引擎和本地资料就绪。报告、聚合与原发布者分别留证。见 [AI 资讯合同](research-web-ai-news.md)。 |
| OpenAI、Google DeepMind、Fed、ECB，以及 The File · Hot RSS/Atom | AI 官方新闻、技术博客、央行新闻稿与第三方资讯 | Hot 采集目录独立于 DataHub 业务工具，能读到的内容取决于是否启用及已有采集。The File 为非官方资讯。见 [Hot 机器目录](../app/research_web/datahub/hot_public_sources.json)。 |
| GDELT、UCDP · 事件时间线 | GDELT 媒体编码的地缘事件记录；UCDP GED 26.1 的 1989–2025 年冲突事件数据 | 用于事件检索和索引。原始报道及事件真实性另核。UCDP 入口默认标记待配置，需有效 Token 和实际导入。见 [事件来源实现](../app/research_web/event_timeline/sources.py)。 |
| DSH 网页搜索及来源读取 · `web_search` / `research_read_source` | 搜索结果的标题、摘要和链接；经会话授权、已登记来源的公开 HTML 或纯文本正文 | 搜索服务用于发现，正文读取用于取证。付费、登录或 PDF 附件走合法可访问原件或显式上传。见 [工具登记](../app/research_web/capabilities/tools.py)和[来源读取](../app/research_web/research_web_sources.py)。 |
| 用户上传文件／获准档案 | PDF 报告、图片证据、Markdown 和其他已支持文件；既有研究档案中的原件、摘录及冻结证据 | 按当前账号和会话授权使用，引用原文件名、版本、页码或分段。WeKnora 检索仍是独立候选，以其开关和验收记录为准。见 [文件合同](architecture/research-web/03-data-files.md)、[研究档案](research-web-dossiers.md)及 [WeKnora 资料候选](research-web-weknora.md)。 |
| 知丘、中国证券网及其他目录项 | 知丘的研报、公众号、会议纪要；中国证券网新闻和快讯；旧 Yahoo／AKShare 新闻、Tavily／Bing 搜索等 | 知丘需账户且对应 DataHub 适配待接入。中国证券网属旧 Connector，默认只采列表；其他旧 Provider 或目录项按实际接入核对。可从原站或获准的独立入口核实。见 [来源登记](../app/research_web/datahub/catalog.py)和 [旧 Connector 归档](archive/legacy/data-sources-connectors.md)。 |

## 维护规则

- 每次取数遇到清单外的新来源，先按任务授权验证最小代表性样例。核对实际返回的字段或正文、关键日期、出处和可访问范围。验证成功就在本次任务中补入相应分类。只有入口或权限线索时记为“仅登记”并注明缺口，后续可用时更新同一行。
- 已收录渠道发生字段、权限、费用、接入路径或稳定性变化时，更新原行及对应证据。确认停售、停用或被替换时记下状态、日期和已核实的替代渠道，便于追溯旧研究。
- 新增或更新一行时填写 **来源和入口（含已有 ID）、数据与覆盖、条件与限制、核验日期和样例证据**。行情注明适用市场、频率、单位／复权及历史限制，文本注明正文或索引、原始发布者、发布时间与访问范围。记录文档、公开原件或经过脱敏的回执链接，账号和凭据由原系统管理。
- [DataHub 业务目录](../app/research_web/datahub/catalog.py)、[外部入口目录](../app/research_web/datahub/external_sources.json)、[Hot 机器目录](../app/research_web/datahub/hot_public_sources.json)维护可执行声明；本页维护选源与已核实范围。新增或变更 Provider 时同步更新本页、对应合同文档及测试。历史兼容 API、采集器及 Connector 的维护从[旧 Connector 归档](archive/legacy/data-sources-connectors.md)查起。
