# WeKnora 读取 DataHub：任务级技能层设计与实施计划

Status: implementation-candidate（2026-11-25；9 个工具源码已注册，未部署）
Host: macOS arm64 Mac mini
Task: `weknora-datahub-skill-layer-20261124`
Baseline: `63a24daa9c9fb86e0a2c5917cffb70bcc2ddfaeb`

本批源码实现状态见[业务工具合同](../research-web-business-tools.md)与
[实现报告](../../.ai/reports/2026-11-25-weknora-datahub-tools.md)。下文保留12个候选的目标设计；
当前实现9个：K线仅daily/none、指数仅单个index、证券检索无limit、筹码尚未映射。
新闻/公告/MySQL按条件不注册；此前“任务工具尚未注册”等盘点属于实现前历史，
不得据此判断当前候选源码，更不能将候选源码当作常驻已部署。

本文是设计与决策记录，不是已交付合同。厂商目录、能力矩阵和技能层方案的
状态以带日期的历史记录与本版落实表为准；未执行项保持 NOT_RUN。

本版采用三个代码模块：业务工具、DataHub 查询服务、供应商适配器；
语义是共享契约，规划与路由是查询服务内的职责，不新增五套执行框架。
设计阶段只更新文档；2026-11-25 实现阶段已在独立工作树修正 B1 并新增业务工具，常驻服务未改。

### 本版落实表

2026-11-25 设计增量：用户确认按 Wind 七域 34 个工具组织目标目录；
必须结合已有数据源主清单与本机 AlphaDesk 补充进行来源选择。
本轮落地关系、K 线合同与验收规格见第 14 节。上方 9 工具实现记录及下方旧 12 工具
草案保留各自范围；旧合并工具与 quote=快照命名须按目标目录迁移，不宣称已经完成改名。

“设计落实”表示本文已明确规则；不表示业务功能已交付。

| 已确定事项 | 文档位置 | 设计状态 | 实现状态 |
| --- | --- | --- | --- |
| Wind 七域分类，扩展公共/数据库工具 | 4.1、12 | 已统一 | 9 个工具源码已注册；3 个候选条件未满足 |
| 三模块；语义为契约，规划/路由在查询服务内 | 11 | 已统一 | 已复用原模块接入；未增加执行服务 |
| 同源本地覆盖、换源整段重算、权限不绕过 | 10.4、11.3 | 已定义 | v2 泛化未实施 |
| 交易日合并、源窗口分段、区分停牌与缺失 | 11.4、13 | 已定义 | B1 已修正接入，Wind 已分段；证明沿原存储 |
| 原始价/量额加版本化因子，读时复权 | 4.2.1、11.5 | 已定义 | 仅已验证来源可用，统一视图未实现 |
| 工具参数、共享提交/status/分页链 | 4.2、12 | K 线主线已细化，其余受限合同见各项 | 新工具及映射未实现 |
| Finance MCP 岗底斯正式行情绑定与主源评估 | 3、10.3–10.4、13.5 | 条件已明确 | 已增加原始日线 binding；有限样本核验，旧顺序不变 |
| 复合行情 Skill | 6、11.2 | 角色与依赖已定义 | 未编写，WeKnora 加载方式未验收 |
| WeKnora 授权与工具目录 | 4.3 | 保留原权限，按实现进度切换目录 | 9 个工具来自历史同步；本轮未实调 |

本轮核对覆盖全部 13 章；文档一致性检查不替代代码、供应商或 WeKnora 验收。


## 导航

| 章节 | 内容 |
| --- | --- |
| [1. 结论先行](#1-结论先行) | 核心判断与优先级 |
| [2. 现状](#2-现状已接入的底层接口) | 接入点、八家厂商目录、完成度、已知问题 |
| [3. Capability 映射](#3-capability-到厂商的映射提议待契约验证) | 12 个能力与候选源 |
| [4. 技能层设计](#4-技能层设计) | [工具面](#41-工具面)、[固定 capability](#411-固定-capability-是什么)、[命名约定](#412-命名约定)、[行为](#42-行为约定)、[复权口径](#421-复权口径)、[可见性](#43-可见性)、[错误码](#44-错误码) |
| [5. 主流做法](#5-主流做法参照) | Wind、iFinD、RQData、Tushare、OpenBB |
| [6. 实施阶段](#6-实施阶段) | Phase 0–4 |
| [7. 验收与证据](#7-验收与证据) | 分层判据与证据目录 |
| [8. 已定与待核实](#8-已定与待核实) | 既定决策与证据缺口 |
| [9. 下一步](#9-下一步) | 后续动作 |
| [10. K 线契约](#10-契约样例个股-k-线) | [设计原则](#101-设计原则)、[工具契约](#102-统一工具契约)、[数据源](#103-已实现与已登记的数据源)、[路由表](#104-来源策略与优先级)、[Wind 映射](#1041-wind-官方三层映射参照)、[字段质量](#105-字段与质量门)、[完整示例](#106-完整调用示例)、[维护](#107-维护流程)、[本节状态](#108-本节状态) |
| [11. 查询架构 v2](#11-查询架构-v2与增量补齐设计) | 三模块、同源覆盖、增量补齐、复权、端到端调用 |
| [12. 工具契约](#12-工具输入契约12-个) | 12 个工具的逐项参数、约束、错误码与示例 |
| [13. B 实施设计 v2](#13-b实施设计-v2) | B1 缺陷、交易日合并、Wind 分段、来源隔离、接入验收 |
| [14. 清单驱动的工具与 K 线合同](#14-清单驱动的工具与-k-线合同) | 主清单、私有补充、七域来源映射、K 线输入与路由验收 |
| [15. 股票域逐工具映射](#15-股票域逐工具映射与实施缺口) | 十个工具的输入输出、清单来源、适配状态、固定路由与验收 |
| [16. 股票快照字段合同](#16-股票快照逐字段来源与时间合同) | 七字段口径、各源真实投影、时点准入、路由与迁移验收 |
| [17. 资产观察首条接入](#17-资产观察首条接入的源码候选) | 页面与MCP共用日K合同、兼容边界、验证与PR状态 |

快速跳转： [K 线工具契约](#102-统一工具契约) ·
[源优先级](#104-来源策略与优先级) ·
[端到端示例](#106-完整调用示例) ·
[复权 qfq/hfq](#421-复权口径)

## 1. 结论先行

1. 问题不是"底层没接"，而是"接了但没有按任务契约化"。已有金融聚合入口通过
   `ext_finance_mcp` 接入 DataHub；目录列出八家，但逐服务发现与契约化仍为 PARTIAL。
2. 缺的是 vendor 到 RWB capability 的数据契约：字段映射、单位、日期语义、
   PIT、分页、错误码和质量门。模型选业务工具；服务端依据已验证契约选源。
3. 不应把 100+ 个厂商原生工具暴露给模型。WeKnora 只应看到少量任务级工具；
   capability 与 source 的固定在 RWB 服务端，模型只填业务参数。
4. 底层契约优先于复合 Skill。首先完成 `market_bars` 与 `get_stock_kline` 的完整链路，
   再扩展 `financials` 和 `search_announcements`；不要求三者同时完成才开放首个工具。
5. 复合技能（如 `market_overview`）在底层工具稳定后再做；v1 规划最多 12 个业务工具，
   按逐项验收注册，其中新闻检索、公告和用户数据库工具按条件启用。

架构入口：[系统总览](../ARCHITECTURE.md)、
[Research Web 分层阅读](../architecture/research-web/README.md)、
[开发地图](../DEVELOPMENT_MAP.md)、[数据源清单](../DATA_SOURCES.md)。

## 2. 现状：已接入的底层接口

### 2.1 接入点

| 项 | 现状 |
| --- | --- |
| DataHub 源 ID | `ext_finance_mcp` |
| 上游地址 | `https://www.huaanifd.com/finance-data/mcp` |
| 传输 | MCP Streamable HTTP，无状态 |
| 鉴权 | `Authorization: Bearer <FINANCE_MCP_TOKEN>` |
| 凭据存储 | DataHub 本机 OS 凭据库，单一客户端令牌 |
| RWB 适配器 | `app/research_web/datahub/providers_finance_mcp.py` |
| RWB capability | `external_data` |
| 网关工具 | `finance_sources`、`finance_list_tools`、`finance_call`、`alpha_query`、`gangtise_query` |

厂商 Key 与 Windows 中转令牌由上游管理。RWB 不保存、不向模型或快照返回。

### 2.2 八家厂商目录（2026-11-24 实测）

2026-11-24 用本机凭据实调 `finance_sources` 与 `finance_list_tools`，得到下表的
工具与操作清单。`windows_worker` 是配置状态，不是取数成功。

| 厂商 | 服务数 | 代表性数据 | 主要工具 / 操作 |
| --- | --- | --- | --- |
| Alpha 派 | 1 | 投研观点、问答、个股 Agent、研报、图片 | `recall`、`qa`、`stock_agent`、`stock_report`、`search_image` |
| 岗底斯 | 1 | A/港/美股日 K 与分钟 K、实时行情、复权因子、三大报表、主营构成、估值、前十大股东、盈利预测、公告/研报/纪要/调研/路演/论坛/策略会、行业指标、题材、知识库 | `查询A股日K线`、`A股利润表（单季度）`、`查询A股公告列表` 等 59 个操作 |
| DM | 15 | 债券分析/市场/一级、境外债、公司、基金、期货、外汇、指数、股票、衍生品、票据、宏观、货币市场、工具 | `equity_bars_data`、`index_bars`、`fx_market_data_bars`、`options_bars`、`edb_code_info`、`edb_indicator_data`、`get_trade_dates`、`bond_price_calculate` |
| 财汇 | 1 | 企业筛选/档案/股权/财务经营、股票发行、债券登记发行承销、PEVC、租赁、应收、银行授信、担保、信用评级、诉讼、监管、知识产权、招投标；债券、货币利率、LGFV、宏观区域；新闻研报、公告、法规；基金；股票；指数；国债 | `query_enterprise_financial_and_operating_data`、`query_stock_trading_and_capital_flow`、`query_announcements`、`query_fund_nav_and_return`、`query_index_profile_and_components` 等 42 个工具 |
| 携宁知丘 | 1 | 行情信息、文档详情、财务报表、一致预期、目标价评级展望、股票图谱、产品图谱 | `get_financial_statement`、`get_consensus_forecast`、`get_targetprice_ratingoutlook`、`get_stock_graph` |
| 进门财经 | 1 | 股票标准化资料、会议/路演资料 | `get_stock_details`（文档示例） |
| 通联 Datayes | 35 | 股票/基金/债券/指数/港股/期货/期权/因子/宏观/公告/研报 | `stock_info_get_data`、`macro_get_data`、`list_stock_annos`、`get_report_full_text` 等，统一 `*_get_info` / `*_get_data` |
| 同花顺 iFinD | 7 | 股票 11 工具、基金 9、宏观 2、新闻 3、债券 5、全球股票 5、指数 3 | `get_stock_performance`、`get_stock_financials`、`get_fund_portfolio`、`get_edb_data`、`search_news`、`global_stock_quotes`、`sector_data` |

目录发现失败项：DM 的 `bond-analysis`、`bond-market`、`bond-primary`、`company`、
`fund`、`futures` 与进门财经在本次调用中超时；通联 `datayes-data` 返回空列表。
这些发现结果记为失败/空列表，不记为成功；尚未覆盖的功能保持 NOT_RUN。通联另按 2.4 排除。

### 2.3 历史接入完成度（2026-11-23～25）

| 层 | 状态 | 证据与说明 |
| --- | --- | --- |
| 传输与鉴权 | PASS | 实调 `finance_sources` 返回 8 家 |
| 工具发现 | PARTIAL | 8 家主体已返回；DM 6 个服务、进门财经、通联 `datayes-data` 超时或空 |
| 结构化投影 | PARTIAL | 仅岗底斯 `fieldList`/`list` 转为行对象；其余保留 `provider_payload` |
| 字段与单位 | NOT_RUN | 多数厂商 `units_not_verified` |
| 日期与 PIT | NOT_RUN | `historical_pit_not_verified` |
| 质量门 | PARTIAL | `quality_accepted` 仅对目录调用与岗底斯结构化行成立 |
| 真实取数 | PARTIAL | 历史记录含岗底斯短区间与一年期、DM 一年期、iFinD 样例；后两者有延迟/非交易日行限制。本轮未重跑 |
| 平台归属 | PARTIAL | `windows_worker` 是上游执行位置标注；Mac 请求已有部分成功记录，不等于厂商在 Mac 原生运行或八家全验收 |
| WeKnora 接入 | 历史确认 | 2026-11-25 08:46 同步记录为 9 个工具；本轮未重验 token，任务工具尚未注册 |

### 2.4 已知问题

1. 多数工具使用自然语言入参，例如 iFinD `get_stock_performance({query:"..."})`。
   RWB 必须用结构化参数拼出确定性 query，不能把模型原话直接透传。
2. 通联两次调用均返回 `INSUFFICIENT_CREDITS`（实测 2026-11-24，600519 与 000001
   各一次）。**用户已决定 v1 排除通联**，不进入任何路由候选；恢复条件是重新购买
   额度，并通过一次真实 K 线取数验收。
3. 不同厂商同一指标的口径、单位、复权和日期语义未对齐。
4. 该 MCP 不提供 PIT 证明；正式回测和历史时点研究不能直接采用。
5. 岗底斯操作名为中文，参数键为 camelCase；其他厂商用英文工具名和不同参数风格。
   契约层必须逐厂商适配，不能假设同构。

## 3. Capability 到厂商的映射（提议，待契约验证）

只覆盖 12 个候选业务工具实际需要的 capability，不做全量规范化。

| RWB capability | 主源候选 | 备选 | 当前可调用源 | 结构化程度 |
| --- | --- | --- | --- | --- |
| `market_bars` | 岗底斯 `查询A股日K线` | iFinD `get_stock_performance`、DM `equity_bars_data`、Wind、天软 | 天软、Wind、AKShare、BaoStock | 高（岗底斯）/ 中 |
| `market_snapshot` | 岗底斯 `查询个股实时行情` | iFinD `stock_highfreq_quotes`、DM `equity_bars_data` | 天软、Wind、AKShare | 高 / 中 |
| `index_data` | 先核验指数单时点报价 | 岗底斯/DM/iFinD 的报价；历史 K 线另立契约 | Wind（单日 quotes） | 按数据形状分别验证 |
| `trading_calendar` | DM `get_trade_dates` | 天软、AKShare、BaoStock | 天软、AKShare、BaoStock | 高 |
| `financials` | 岗底斯三大报表 | 携宁 `get_financial_statement`、iFinD `get_stock_financials`、财汇企业财务 | 天软、Wind、AKShare、BaoStock | 高 / 中 |
| `market_activity` | 岗底斯股东/估值/主营 | 财汇股权/质押/诉讼、iFinD | 天软、Wind、AKShare | 高 / 中 |
| `fund_data` | iFinD 基金工具 | 财汇基金工具、东方财富 | 东方财富 | 中 |
| `search_assets` | 天软 `stock_list` | iFinD `search_stocks`、`search_funds` | 天软、AKShare、BaoStock | 高 |
| `factor_macro` | DM `edb_indicator_data` | iFinD `get_edb_data`、财汇宏观 | 天软、AKShare；BEA Archive 为其他系列，不等于四个中国系列都支持 | 高 / 中 |
| `search_news` | iFinD `search_news` | 财汇新闻；trending/财联社最新流不等于关键词检索 | 财联社仅最新流，不满足本工具合同 | 待检索契约验证 |
| `search_announcements` | 岗底斯 `查询A股公告列表` | iFinD `search_notice`、财汇 `query_announcements` | **无**（需 P1 接入） | 高 |
| `table_query` | 用户 MySQL | 无 | **无**（需配置） | 高 |

不在 v1、但 catalog 已登记的能力：`search_research`、`search_web`、
`database_schema`、`external_data`。前三个无可用源；`external_data` 是已登记外部端点的通用入口，形态与业务工具不同。目标切换后
只保留于诊断通道；当前 raw 工具仍按原账号目录可见，不能把目标行为写成已上线。

选源规则：RWB Broker 按 binding priority 选第一个 ready 源；不跨源拼接同一指标；
现行底层请求的 fallback 行为按原合同；v2 自动业务工具的替代来源策略见 10.4，尚未实施。

## 4. 技能层设计

### 4.1 工具面

按 Wind 的七个业务域组织工具目录，不再使用“行情与交易 / 公司与基金 / 宏观与资讯”的混合分组。
域决定工具放在哪里；`get_*` / `search_*` 只是命名约定，不是 Wind 的域分类。
七域是目录分类，v1 继续使用一个 MCP 端点，不创建七套服务。

| 业务域 | 中文 | 本版范围 |
| --- | --- | --- |
| `stock_data` | 股票数据 | 股票 K 线、快照、财务、交易与股东活动 |
| `fund_data` | 基金数据 | 基金净值、档案、分红、披露持仓 |
| `index_data` | 指数与板块数据 | 当前先提供指数单时点快照 |
| `bond_data` | 债券数据 | 保留域，尚未定义可交付工具 |
| `financial_docs` | 公告、新闻与研究文档 | 新闻检索、公司公告；均需契约验收后启用 |
| `economic_data` | 宏观与行业数据 | 当前先提供四个中国宏观系列 |
| `analytics_data` | 通用结构化取数 | 保留域，本版不开放自然语言通用取数兜底 |

本版仍为 12 个候选工具：金融业务域内 9 个、跨域公共工具 2 个、RWB 数据库扩展 1 个。
下表均是待实现的工具设计，不表示已出现在 WeKnora；不带 `rwb_` 前缀。
所有提交工具沿用 `request_id` 幂等合同。内部 capability 映射见 4.1.1，不作为业务域分类。

#### 1. stock_data · 股票数据

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `get_stock_kline` | 单只沪深 A 股日 K：开高低收、真实成交量额；复权分源验收 | `asset`、`start_date`、`end_date`、`frequency?`、`adjustment?`、`adjustment_base_date?` | 优先实现 |
| `get_stock_quote` | 1–20 只 A 股最新行情快照：价格、涨跌幅、量额 | `assets`、`fields?` | 待实现 |
| `get_stock_financials` | 单只 A 股财务摘要、利润表、盈利指标、现金流指标 | `asset`、`dataset`、`periods?` | 待实现 |
| `get_stock_activity` | 个股资金流、融资融券、股东数据、大宗交易与筹码换手 | `asset`、`dataset`、`start_date?`、`end_date?` | 待实现 |

#### 2. fund_data · 基金数据

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `get_fund_detail` | 基金净值、基本档案、分红或已披露持仓 | `code`、`dataset`、`start_date?`、`end_date?`、`year?`、`limit?` | 待实现 |

#### 3. index_data · 指数与板块数据

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `get_index_quote` | 指数单时点行情；不代表已支持指数历史 K 线或板块排名 | `indexes`、`date?` | 待实现 |

#### 4. bond_data · 债券数据

当前无已定义并验收的债券业务工具，不注册占位工具。供应商债券目录存在不等于 RWB 已支持。

#### 5. financial_docs · 公告、新闻与研究文档

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `search_news` | 按关键词与日期检索财经新闻；最新 N 条过滤不满足本合同 | `query`、`limit?`、`start_date?`、`end_date?` | 条件启用 |
| `search_announcements` | 按公司与日期查询公告，返回标题、披露时间与可核实链接 | `asset`、`query?`、`start_date?`、`end_date?` | 条件启用 |

#### 6. economic_data · 宏观与行业数据

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `get_economic_series` | 中国 CPI 当月同比、GDP 累计同比、制造业 PMI、M2 同比 | `series`、`start_date?`、`end_date?` | 待实现 |

#### 7. analytics_data · 通用结构化取数

保留分类但不注册通用取数工具；复杂行情请求继续拆成专项工具，不通过自然语言兜底绕过契约。

#### 跨域公共工具（RWB 扩展，不是第八个金融域）

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `search_assets` | 按名称或代码查股票、基金、指数的规范证券身份；不是条件选股 | `query`、`asset_type?`、`market?`、`limit?` | 待实现 |
| `get_trading_calendar` | 查询市场开市与休市日期，为各金融域共用 | `market`、`start_date`、`end_date` | 待实现 |

#### 用户数据库工具（RWB 扩展）

| 工具 | 中文说明 | 业务输入 | 状态 |
| --- | --- | --- | --- |
| `query_user_table` | 对已配置 MySQL 执行参数化只读单表查询 | `database`、`table`、`columns`、`filters?`、`order_by?`、`offset?`、`limit?` | 条件启用 |

数据库未配置时不注册 `query_user_table`；域目录和工具说明不改变实际权限。

#### 条件启用与暂不规划的能力

下表区分接口未适配、账号未配置和暂不规划；出现在候选设计中不表示当前会注册。

| capability | 缺什么 |
| --- | --- |
| `search_announcements` | 无已实现绑定；岗底斯/iFinD 公告接口尚未接入 DataHub |
| `search_research` | 无已实现绑定；研报/纪要需要 Alpha 派或岗底斯先做结构化投影 |
| `search_web` | 无已配置搜索供应商（Tavily/Bing 均 disabled） |
| `database_schema` | 本机未配置 MySQL |
| `table_query` | 同上 |

`search_announcements` 仍列入 v1 工具面是**有条件**的：P1 期间若岗底斯公告
接口契约验证通过则启用，否则工具不注册，文档与 WeKnora 目录同步标注
`NOT_RUN`。新闻检索同样须满足 12 节合同；不把最新流当成已实现关键词检索。

现有 4 + 3 个工具名保持不变，避免破坏 WeKnora 已同步目录与 tool approvals。

### 4.1.1 固定 capability 是什么

**capability 是业务工具内部固定的数据标识，不是新增执行层。模型调用这些业务工具时不填写它。**
原 raw 工具仍接收显式 capability；它与本节业务工具的入参不同。

| 对外工具 | 内部 capability |
| --- | --- |
| `get_stock_kline` | `market_bars` |
| `get_stock_quote` | `market_snapshot` |
| `get_stock_financials` | `financials` |
| `get_stock_activity` | `market_activity` |
| `get_fund_detail` | `fund_data` |
| `get_index_quote` | `index_data` |
| `search_news` | `search_news` |
| `search_announcements` | `search_announcements` |
| `get_economic_series` | `factor_macro` |
| `search_assets` | `search_assets` |
| `get_trading_calendar` | `trading_calendar` |
| `query_user_table` | `table_query` |

同名不代表同层：`fund_data` 业务域包含基金工具，内部 `fund_data` 则是现有请求枚举。


调用链是单向固定的：

```text
模型选择工具           服务端固定映射             内部执行
get_stock_kline   →   capability = market_bars   →   Broker 按 binding 选源
```

具体含义：

| 问题 | 答案 |
| --- | --- |
| 模型需要传 capability 吗 | 不需要，也不能传；工具名已经决定了 capability |
| 模型能改 capability 吗 | 不能；映射写死在服务端注册表里 |
| capability 用在哪 | catalog 能力目录、broker 选源、binding 表、快照 manifest、测试断言 |
| 改了工具名会影响 capability 吗 | 不会；两者独立，只改对外工具名 |
| 为什么要两层 | 对外名字可读、可演进；内部 capability 稳定，历史快照和回归不受影响 |

**`market_bars` 保留吗？保留。** 它只是不再作为对外工具名：

| 层 | 名称 | 是否对外 |
| --- | --- | --- |
| 工具名 | `get_stock_kline` | 是，模型看得到 |
| capability | `market_bars` | 否，只在服务端与 manifest 中出现 |

保留历史快照里的 `capability: "market_bars"` 与现有枚举；注册业务工具仍需实现
服务端映射、查询服务接入和必要适配，不是只改工具名就能完成。

一句话：**工具名是给模型看的，capability 是给服务端用的。**

### 4.1.2 命名约定

参考 Wind 的业务域和明确工具名。资产工具在名称中体现资产类型，跨域工具例外；
这是可读性约定，不是单 MCP 端点强制要求。

| 动作 | 模式 | 示例 |
| --- | --- | --- |
| 取确定性数据 | `get_<资产>_<形状>` | `get_stock_kline`、`get_stock_quote`、`get_stock_financials` |
| 取目录/基础信息 | `get_<对象>_<类型>` | `get_fund_detail`、`get_economic_series`、`get_trading_calendar` |
| 检索 | `search_<对象>` | `search_news` |

与内部 capability 的关系：

- **对外工具名**可以改；**内部 capability 名不变**（`market_bars`、`market_snapshot`、
  `financials`、`fund_data`、`factor_macro`、`search_news`、`trading_calendar`）。
- capability 名出现在 catalog、broker、binding、测试和快照 manifest 中；改名收益低、
  回归面大，不在本批范围。
- 工具名与 capability 的映射固定在服务端，模型不能传 capability。

为什么 `market_bars` 不适合做工具名：

- `market` 太泛，可以读成全市场、大盘或板块；
- `bars` 是图表术语，中文语境说“K 线”；
- 不含资产类型，股票、ETF、指数边界不清；
- 与 `market_snapshot`、`index_data` 的差异从名字看不出来。

接受 `get_stock_kline` 把“股票”写死的代价：v1 只支持 A 股，名字准确优先；
将来支持 ETF 时新增 `get_etf_kline`，而不是让模型猜 `asset_type`。

### 4.1.3 与 Wind / iFinD 的对照依据

12 个候选工具参考上游既有工具或服务，但不强求一对一等价：

| RWB 工具 | Wind 官方对应 | iFinD（经 finance MCP）对应 | 切分理由 |
| --- | --- | --- | --- |
| `get_stock_kline` | `get_stock_kline` | `get_stock_performance` | 同属 K 线需求；Finance MCP 的 NL 参数必须适配，不能假设与原生 API 同构 |
| `get_stock_quote` | `get_stock_price_indicators` | `stock_highfreq_quotes`（real_time） | 同为单时点快照 |
| `get_index_quote` | `get_index_price_indicators` | `index_data` | 指数与个股分开，避免 ETF/指数混用股票端点 |
| `get_trading_calendar` | 本地 MCP Skill 未列独立工具，不代表原生 Wind API 无日历函数 | 无；DM 的 `get_trade_dates` 属另一厂商 | 缺口计算的前置依赖，必须独立 |
| `get_stock_financials` | `get_stock_fundamentals` | `get_stock_financials` | 三表与指标同属财务域 |
| `get_stock_activity` | `get_stock_equity_holders` + 事件类 NL 工具 | 股东/事件/资金流分散在多个服务 | RWB 合并为一个「个股活动」入口，用 `dataset` 区分 |
| `get_fund_detail` | `get_fund_info` + `get_fund_holdings` + `get_fund_performance` | 基金 9 个工具 | 同理合并，`dataset` 区分 |
| `search_assets` | 无直接等价；`search_stocks/search_funds` 是条件筛选 | 原生 API 证券身份搜索更接近；聚合 MCP 另核 | 身份解析与条件选股分开 |
| `get_economic_series` | `get_economic_data` | `get_edb_data` | 宏观 EDB 一一对应 |
| `search_news` | `get_financial_news` | `search_news` / `search_trending_news` | 同属资讯检索 |
| `search_announcements` | `get_company_announcements` | `search_notice` | 同属公告检索 |
| `query_user_table` | 无（不在 Wind 范围） | 无 | RWB 特有的用户数据库只读入口 |

有意**不照搬** Wind 的地方：

1. **不拆 `get_stock_price_indicators`**。Wind 把它做成「`windcode` + `indexes` 白名单」，
   需要维护一份中文指标表；RWB 用 `fields?` 收窄，字段集合由服务端契约控制，
   避免模型接触 200+ 指标名。
2. **不保留 `analytics_data` 通用兜底**。Wind 有自然语言兜底入口，但 RWB 的
   12 个工具都是结构化参数；开放 NL 兜底会让「选源 + 选字段」重新回到模型手里，
   与本设计目标相反。需要新数据形态时，按新增 capability 走一遍契约，不开口子。
3. **分类与部署独立**。参考 Wind 七域组织工具说明；RWB v1 保留单 MCP 端点与原 OAuth。
   没有证据证明 Wind 的域划分由账号网关决定，撤回此前推断。域是业务目录，
   不是内部 capability，也不要求对应独立进程。
4. **合并 NL 域工具**。Wind 的股东、事件等工具使用 NL 参数；RWB 先以明确的 `dataset` 枚举
   覆盖已实现的子集。风险指标等未定义功能不因合并命名而自动获得支持。

CN 宏观的来源补充：iFinD `edb` 服务提供 `search_edb` + `get_edb_data` 两步式取数
（先找指标 ID、再取值）。RWB 的 `get_economic_series` 先用固定的四个系列
（`cn_cpi`/`cn_gdp`/`cn_pmi`/`cn_m2`）收敛范围，指标 ID 映射留在服务端；
将来扩到任意 EDB 指标时，再按 iFinD 的两步式增加 `search_economic_series`。

### 4.2 行为约定

- 业务工具固定映射到内部 `BusinessQuery`，模型不传 `capability` 或 `source`。
  查询服务在既有账号权限内按第 11 节选源；对单个候选执行时绑定明确来源、
  `allow_fallback=false`，由查询服务统一控制是否转下一候选。
- 复用原提交结果，查询标识保留 `id`；调用 `rwb_datahub_status(query_id=返回的 id)`。
  状态、source、dataset 等以原返回结构为准，不凭设计示例新增 query_id 别名。
- rows 由现有 `rwb_datahub_status` 分页读取，保留 manifest、SHA、单位、缺失和 `as_of`。
- `asset` 业务参数仅接受规范代码。名称与裸代码先走 `search_assets`，由调用方选择唯一候选；
  不声称所有供应商都能直接解析中文名。股票工具由服务端补 `asset_type=stock`。
- `get_stock_financials` 的 `dataset` 映射：`summary` 不传 statements；`income_statement` 走 AKShare；
  `profitability`/`cash_flow` 走 BaoStock，沿用既有语义过滤。
- 美国宏观继续使用 `rwb_datahub_query`（FRED/BLS）；`get_economic_series` 只覆盖中国宏观。

### 4.2.1 复权口径

| 口径 | 中文 | v2 定义 |
| --- | --- | --- |
| `none` | 不复权 | 当日真实成交价格；历史更正仍可能改变源返回值 |
| `qfq` | 前复权 | 按明确的复权基准日缩放价格；基准变化可能改变历史价格水平 |
| `hfq` | 后复权 | 按明确的起始基准缩放价格；因子修订仍可能改变历史值 |

RWB 统一契约：价格按所选口径输出，`volume` 和 `turnover` 保留真实成交量额。
这是 RWB 的产品约定，不是所有供应商的默认行为。RQData 明确存在调整成交量的
选项；供应商返回复权量时，需独立取原始量并验证，不能直接换字段名后声称等价。

新增可选 `adjustment_base_date`：仅 `qfq` 可传，默认有效窗口末个已完成交易日。
`hfq` 使用该源经核验的起始/上市基准，manifest 写明；`none/hfq` 带该参数时拒绝，
不把自定义锚点静默称为标准后复权。显式基准日需为已完成交易日且不早于有效窗口结束日；不得晚于当前可获得因子的日期。
只表示复权锚点，不表示历史可知时点；`as_of` 仍专指 PIT。无能力支持该锚点的源
应退出候选，不能悄悄换成今天。manifest 记录基准日、因子来源与版本、公式版本。

相同原始价、因子序列和模型下，前后复权仅相差常数，区间收益率相同；不能推广为
跨供应商、跨复权模型必然等价。固定快照及因子版本可复现 `qfq` 与 `hfq`，
不再声称“前复权不能冻结”或“后复权历史永不变化”。

岗底斯 `adjustFactor` 的方向与模型仍待除权样本验证。普通历史查询没有 PIT 证明时，
不能作为历史时点已知数据；不因此禁止其用于当前历史走势展示。

### 4.3 可见性

以下为目标行为，当前两个 raw 工具仍在历史同步清单中。新业务工具通过真实调用验收后
再切换 WeKnora 的 raw 可见性；不先隐藏尚无替代入口的工具。

- WeKnora 的 `rwb_datahub_catalog` 与 `rwb_datahub_business_query` 保留代码，
  但对 `rwb-weknora` 客户端隐藏并拒绝调用（列表与 `tools/call` 两处过滤）。
- RWB 浏览器 API 与运维仍可查 catalog，用于诊断。
- 技能工具由 `rwb.data.configured` 控制；不新增 scope 名称。

**工具总数变化（容易混淆，单独列出）：**

| 阶段 | 冻结读取 | FRED/BLS | raw 诊断 | 12 个任务工具 | 合计 | 实测 |
| --- | --- | --- | --- | --- | --- | --- |
| 重授权前 | 4 | 3 | 0（无 configured scope） | 0 | **7** | 2026-11-23 确认 |
| 重授权后（历史同步） | 4 | 3 | 2（catalog + business_query） | 0 | **9** | 2026-11-25 08:46 同步确认 |
| 全部候选工具完成后 | 4 | 3 | 0（对 WeKnora 隐藏） | 最多 12 | **最多 19** | 未实施；按条件实际注册 |

注意：**重授权本身只增加 2 个 raw 工具，不会出现 12 个任务工具。**
首个 K 线工具在 Phase 1 实现，其余候选在 Phase 2 逐项实现后才会出现；
届时再按本节把 raw 两个隐藏；实际数量由已通过契约验收的工具决定，不承诺固定 19 个。

### 4.4 错误码

`skill_parameter_invalid`、`skill_asset_not_found`、`skill_asset_ambiguous`、
`skill_source_unavailable`（附 attempts）、`request_id_conflict`，以及既有
`data_not_equivalent`、`data_query_failed`。

## 5. 主流做法参照

### 5.1 证据范围与设计取舍

本轮核对项目 Wind MCP Skill、已安装 iFinD API Skill 与下列官方文档。
公开接口能证明调用契约，不能证明厂商内部的采集、清洗、主备切换机制。
金融聚合 MCP 的封装限制也不能推导为原厂 API 限制。

| 参照 | 公开设计 | RWB 采用什么 |
| --- | --- | --- |
| Wind MCP（项目本地 Skill 版本） | 七业务域；行情结构化、领域 NL、文档检索并存 | 按金融域组织目录；对外工具名称明确；不照搬全部 NL 入参 |
| iFinD 原生 API 与 Skill | BD/DS/HQ/RQ/HF/EDB 等函数；证券、指标、参数字典；Skill 指导选择与核验 | 开发时查指标并固化契约；生产只执行已确认映射 |
| RQData | 通用 `get_price`；单/多标的；显式复权、停牌选项 | 统一行情形状；明确停牌与成交量语义 |
| Tushare | 基础接口与 SDK `pro_bar` 组合；复权锚点与 end_date 有关 | 业务工具可以组合数据与确定性计算，不必一对一包装供应商 API |
| OpenBB | QueryParams/Data 模型；供应商 Fetcher 的参数翻译、取数、结果转换 | 公共契约与供应商适配分开，保留无法等价的差异 |

Wind 本地契约中 `get_stock_quote` 是分钟行情，快照用 `get_stock_price_indicators`；
RWB 的 `get_stock_quote` 明确定义为最新快照，两者不是同名同义。
Wind `index_data.get_index_kline` 在其本地 Skill 中存在，但 RWB 当前接入的 Wind Excel
`index_data` binding 只有单日快照；不可把后者限制写成 Wind 全产品限制。

### 5.2 可复核参考

- [Wind 本地 Skill](../../.agents/skills/wind-mcp-skill/SKILL.md) 与
  [工具契约](../../.agents/skills/wind-mcp-skill/references/tool-contracts.md)：本地版本，未在线刷新清单。
- [iFinD API](https://quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/) 与
  [官方 Skill](https://quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/ai-skill.html)。
- [RQData 通用 API](https://www.ricequant.com/doc/rqdata/python/generic-api)。
- [Tushare pro_bar](https://tushare.pro/document/2?doc_id=109)。
- [OpenBB 架构](https://docs.openbb.co/odp/python/concepts/architecture) 与
  [标准化契约](https://docs.openbb.co/odp/python/developer/standardization)。

iFinD 原生 Skill 列有 `THS_ReportQuery` 公告列表与下载链接；第 12 节对
`search_notice` 文本片段的评价仅针对已测试的金融 MCP 封装路径。

## 6. 实施阶段

第 13 节定义具体代码步骤，本节定义交付批次，两者采用同一顺序。

### Phase 0：设计对齐

本版完成七域、三模块、同源覆盖、复权与调用契约说明。B1 是未接入的原型，
有已知缺陷；文档通过不代表 B1 已修复。

### Phase 1：首条 K 线链路

按 B1 修正 → B2 保持原行为接入 → B3 同源泛化与窗口分段 → B4 K 线工具映射 →
B5 摘要的顺序，先以既有适用来源完成不复权 K 线。本批不要求财务、公告先完成。
复用原 OAuth、查询提交、status、分页、快照与仓库；不另造任务/状态服务。

### Phase 2：供应商契约与工具逐项扩展

岗底斯正式 K 线 binding 完成单位、日期、分页、错误与缺口验证后再进入候选；
复权单独验收。随后逐项接财务、公告及其他候选工具，保持第 4.1 与第 12 节同步。
服务端共有逻辑复用 backend，不把 `configured_query()` 直接用于 auto：它当前要求显式来源。
不为每个阶段强制新增固定名称函数；实现选最小必要改动。

### Phase 3：WeKnora 工具验收与切换

首个业务工具即可独立刷新 metadata、完成真实调用和分页读取验收，不等 12 个全齐。
configured scope 来自历史重授权；无权限变化时不重复要求授权。
业务工具覆盖目标场景并通过后，再按 4.3 切换 raw 工具的可见性。

### Phase 4：复合行情 Skill

底层具备所需数据后实现“今日市场行情”工作流；先确认 WeKnora 的 Skill/Workflow
加载或调用入口。固定查询段落、数据时点和缺项说明，复用已交付工具。
缺少板块排名或市场宽度时显示覆盖不足，不用网页片段补造成实时市场统计。

## 7. 验收与证据

| 层级 | 判据 |
| --- | --- |
| 契约 fixture | 结构、单位、日期、缺失、错误码全部断言 |
| 真实取数 | 正常交易日样本非空；休市/停牌样本以日历或证明解释空结果，记录来源与快照 |
| 任务工具 | 执行完成且 data_success、所需字段、单位、覆盖/证明与分页分别满足合同 |
| WeKnora | 本批业务工具可发现、可调用、可分页读取；raw 隐藏只在 4.3 切换阶段验收 |
| 失败 | 稳定错误码与 attempts，不伪造 rows |

历史实测证据目录：`/Volumes/WorkDisk/Data/RWB/acceptance-20261124-mcp-skills/`（本轮未复读或重跑）。
本轮只做文档检查，结果写入原任务报告，不冒充新的供应商实测证据。

## 8. 已定与待核实

已定：对外不加 `rwb_`；内部 `market_bars` 等枚举保持兼容；工具先做 K 线完整链路；
通联排除；同一序列不跨源拼接；文档按金融域组织，单 MCP 端点部署；
不新增语义服务、数据库或调度器。Skill 负责复合任务编排，数据工具负责执行。

待核实：岗底斯原始 K 线完整字段与单位、复权模型与锚点、供应商窗口与调用限制；
财务/公告绑定的正式适配；新闻真正的关键词/日期检索；付费源在重复样本下的成功率与耗时。
不根据单次成功或付费身份宣称“最稳定”。

尚未冻结的适配细节：除 K 线主线外，财务长表投影的 field 字典、基金各 dataset 的
分页覆盖、宏观源指标代码/发布时间、公告分页和原文取得方式仍需逐源契约验证。
第 12 节定义业务入口与约束，不把这些未核实字段当作完整可直接编码的供应商 schema。
这些缺项不阻塞首条不复权 K 线实现，但阻止相应工具注册为可用。


## 9. 下一步

按第 13 节先修正 B1 的交易日合并设计与差分验收，再以既有来源接通一条
`get_stock_kline` → 本地同源读取 → 同源补缺 → 原快照/状态读取的完整链路。
金融 MCP 岗底斯完成正式行情契约后进入候选，最后才调整默认来源顺序。
不把 12 个工具同时铺开作为第一条链路的前置条件。

## 10. 契约样例：个股 K 线

对外工具 `get_stock_kline`，固定 capability `market_bars`。

### 10.1 设计原则

用户的理解方向正确，但要区分三件事：

1. **工具写死**：模型只看到一个稳定工具和一套稳定参数；capability 与
   source 的参数不暴露给模型；工具名供模型选择。
2. **路由表写死**：候选源和优先顺序由服务端固定维护，不是模型临时决定。
3. **源可维护**：接口变更或不可用时改适配器和路由表，不改工具契约。

因此"写死"的是契约和路由，不是写死单一供应商。单源写死会在该供应商限流、
停服或权限变化时直接失去能力；RWB 现有设计是固定候选集 + 固定顺序 +
不跨源拼接。

### 10.2 统一工具契约

工具名：`get_stock_kline`（不带 `rwb_` 前缀）。
固定 capability：`market_bars`（不作为业务输入；结果溯源可显示）。

输入：

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 幂等键，1–64 字符 |
| `asset` | string | 是 | 必须为 `600519.SH` 等规范沪深 A 股代码，规则同 12 节 |
| `start_date` | string | 是 | `YYYY-MM-DD` |
| `end_date` | string | 是 | `YYYY-MM-DD`，不晚于今天 |
| `frequency` | literal | 否 | 默认 `daily`，v1 仅日频 |
| `adjustment` | literal | 否 | 默认 `none`；`qfq` / `hfq` 需满足 4.2.1 |
| `adjustment_base_date` | string | 否 | 仅 qfq 使用；规则见 4.2.1，不能代替 PIT |

输出复用现有查询提交结构；以下仅为关键字段示意，不表示新增完整 DTO：

```json
{
  "id": "00000000-0000-4000-8000-000000000001",
  "session_id": "00000000-0000-4000-8000-000000000002",
  "status": "running"
}
```

调用 `rwb_datahub_status(query_id=返回的 id, offset=0, limit=100)`；
最终来源、数据集、计划摘要和质量状态从原查询/status 与 manifest 读取。

行数据由 `rwb_datahub_status` 读取，每行固定字段：

| 字段 | 单位 | 说明 |
| --- | --- | --- |
| `asset` | — | 规范代码 `600519.SH` |
| `date` | — | 交易日 `YYYY-MM-DD` |
| `open` | 元/股 | 按请求复权口径 |
| `high` | 元/股 | 同上 |
| `low` | 元/股 | 同上 |
| `close` | 元/股 | 同上 |
| `volume` | 股 | 不复权 |
| `turnover` | 元 | 不复权 |
| `turnover_rate_pct` | % | 源未提供时为 `null`；与金额字段 `turnover` 不同 |

manifest 必须带：`source`、`actual_range`、`as_of`、`adjustment`、
`units_identity`、`pagination_complete`、`missing`、`limitations`、
`rows_sha256`、`historical_point_in_time=false`。

### 10.3 已实现与已登记的数据源

旧基线 `market_bars` 工厂表登记 9 个候选，其中四个已有实现。
2026-11-25 实现候选另加岗底斯，完整清单对照见14.3。本表保留原四源限制，
不证明这些来源此刻在当前账号都已就绪。
依据 `app/research_web/datahub/catalog.py` 的 `IMPLEMENTED_BINDINGS` 与
各 Provider 校验逻辑：

| 源 | 实现 | 频率 | 复权 | 时间跨度 | 身份范围 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| `baostock` | 是 | `daily` | 仅 `none` | ≤1464 天 | 沪 `6`、深 `00/30` | 免费；单位已核 |
| `akshare` | 是 | `daily`/`weekly`/`monthly` | `none`/`qfq`/`hfq` | 股票日线按起止日期请求；指数全段后裁剪 | 股票/指数/ETF | 免费；日线优先新浪，失败降级东财（仅 `none`） |
| `wind` | 是 | `daily` | `none`/`qfq`/`hfq` | ≤60 自然日（含首尾） | 沪 `6`、深 `00/30` | 本机 Excel；容量 1，18 秒 deadline |
| `tinysoft` | 是 | `daily` 等 | `none`/`qfq`/`hfq` | 无显式日历天上限；结果 >5000 行失败 | 沪深北 | CJPY 0.5.2；复权为产品策略，非厂商保证 |

已登记但当前不可用：`ifind`（disabled、未配置）、`tushare`（disabled）、
`yahoo`（disabled）、`chinastock`（disabled）、`local_cache`（disabled）。

2026-11-25 候选源码已新增岗底斯 `market_bars/gangtise_raw_daily` 正式绑定；
原 external_data envelope 保留。当前仅日频不复权，单位经有限跨源样本核验；见业务工具合同。

### 10.4 来源策略与优先级

旧基线代码顺序为 `tinysoft → wind → ifind → akshare → baostock → ...`；
实现候选追加岗底斯后的规范 raw 顺序见14.5。
v2 不在文档阶段变更现行默认源。付费金融 MCP 的原生数据必须先成为正式
`market_bars` binding，不能把 `external_data` 原样结果当作 K 线契约。

| 请求 | v2 候选策略（待实施） | 限制 |
| --- | --- | --- |
| 已指定来源（脚本/API） | 仅查该源的同口径本地数据并补齐 | `allow_fallback=false` 时不得换源 |
| 自动来源，不复权 | 优先保留既有可用来源；岗底斯正式绑定验收后评估为主源，Wind/天软/免费源为候选 | 按声明优先级评估；不按缓存量临时改变业务优先级 |
| 自动来源，前/后复权 | 只选择模型、锚点、原始量额都满足契约的来源 | 因子方向未核实的岗底斯不进入复权候选 |
| 缺口超单次窗口 | 在同一来源内拆成供应商支持的小段 | 例如 Wind 的每段 ≤60 自然日；不以完整历史窗口直接淘汰 |

选择算法见 11.3：候选按优先级分别查同源覆盖，完整本地命中不要求启动供应商；
缺口请求才要求实时 readiness。来源因禁用、撤权而失去准入时，本地数据也不能越权使用。

超时或临时不可用可按固定候选顺序换源；认证、额度错误不重试该源，只有明确允许
替代源的策略才继续。字段/单位/复权不等价的候选直接退出，不降级口径。
换源时重新计算新来源的整个窗口覆盖，丢弃本次结果中前一源的组合，禁止拼接。
尝试原因进入 `attempts`，不由模型临时挑选供应商。

当前证据不足以排出跨供应商“稳定性冠军”；优先级变更应记录相同样本的成功率、
延迟与字段差异。付费资格表示访问权益，不是稳定性结论。

### 10.4.1 Wind 官方三层映射（参照）

Wind 官方 skill 把"域 → 工具 → 参数"三层全部写死，RWB 可照搬其结构，
但不能照搬"单一数据源"假设。

| 层 | Wind 官方 | RWB 对应 |
| --- | --- | --- |
| 域 | 本地 Skill 的 7 个 `server_type` | 金融业务目录分组，共用 RWB 网关；不是 capability |
| 工具 | 每个域固定 tool 清单，如 `get_stock_kline` | 固定技能工具 `get_stock_kline`（capability `market_bars`） |
| 参数 | 结构化：`windcode` + `begin_date` + `end_date` + `period` | 结构化：`asset` + `start_date` + `end_date` + `frequency` + `adjustment` |
| 白名单 | `tool-manifest.json` + `indicators.md` 本地先行校验 | 路由表 + 字段/单位表，同样在联网前失败 |
| 数据源 | 隐含唯一 | 显式 4 个候选，按语义固定顺序 |

Wind 的 `get_stock_kline` 只支持单标的、日期格式 `yyyyMMdd`、多标的必须拆多次，
且明确禁止用 `analytics_data` 兜底行情。RWB 对应约束是：单标的、
`YYYY-MM-DD`、禁止用 `external_data` 兜底 `get_stock_kline`。

### 10.5 字段与质量门

| 源 | 已核单位 | 未核 / 限制 |
| --- | --- | --- |
| `baostock` | open/high/low/close=元/股；volume=股；turnover=元 | 仅日线、仅不复权 |
| `akshare` | 同上；东财成交量已由手换算为股 | 新浪换手率由比例 ×100；上游口径可能变化 |
| `wind` | 当前投影 schema 声明 OHLC=CNY/股、volume=股、turnover=CNY | schema 声明不等于本轮上游实测；完整单位需按来源证据核验 |
| `tinysoft` | 日线 vol=股、amount=元；OHLC 币种未声明 | 复权为产品策略，经验范围仅两只股票 |

质量门：

1. 正常交易日应有真实行；休市或全停牌允许有证明的空结果。源分页完成与客户端已读完分别判断。
2. 日期严格升序，无重复交易日。
3. 请求范围内的交易日缺口写入 `missing`，不补点。
4. `volume`、`turnover` 不得因复权被改写。
5. 身份必须与请求一致；响应含错代码直接失败。
6. 必需 OHLC/量额字段的单位未核验时不标质量通过；可选字段可为 null 并解释，不能只加 limitations 就放行。

### 10.6 完整调用示例

用户问“贵州茅台 2026-11-10 到 11-16 的日 K，不复权”。本例是假设调用轨迹，
不填写价格，不冒充供应商实测。

模型直接选择业务工具，或由行情 Skill 指导选择：

```json
{
  "request_id": "kline-600519-20261110-16",
  "asset": "600519.SH",
  "start_date": "2026-11-10",
  "end_date": "2026-11-16",
  "frequency": "daily",
  "adjustment": "none"
}
```

工具补入内部 `asset_type=stock`、`capability=market_bars`，复用原账号、幂等提交和授权。
查询服务验证日期、代码与口径。假设权威日历给出 10、11、12、13、16 日五个交易日。

1. 假设固定优先候选 Wind 的同口径仓库有 10～12 日，13、16 日缺失。
2. 覆盖计算绑定账号、来源 Wind、配置摘要、证券、字段、单位和调整口径；
   AKShare 的缓存不能补这两个 Wind 缺口。
3. 13、16 日在交易日序列中相邻，合并为 `2026-11-13..2026-11-16` 一个请求；
   周末不填造 K 线。Wind 每段跨度限制再独立检查，本段合规。
4. Wind 适配器翻译到既有 Excel 数据路径：规范代码、起止日期、日频、不复权。
   原始返回验证身份、OHLC、股/元单位、缺失与分页后写入同源仓库。
5. 仓库重读完整窗口：有五条真实行则完成；有停牌证明则分别报告行数与证明日数。
   不用“预期交易日数”冒充真实价格行数。
6. 提交返回原查询 id，模型用现有 `rwb_datahub_status` 读取；分页未读完不能声称全量完成。

如果 Wind 实时取数失败且允许下一候选，则重新查下一源整个窗口。
假设 BaoStock 五日全命中，返回整段 BaoStock 数据；不能返回三天 Wind 加两天 BaoStock。
若所有候选均不完整且补齐失败，沿既有失败/部分结果合同报告缺口，不标完整成功。

目标 manifest 增量摘要（示例，不是当前生产字段承诺）：

```json
{
  "capability": "market_bars",
  "source": "wind",
  "plan": {
    "version": "plan-v2",
    "expected_trading_days": 5,
    "covered_fact_days": 3,
    "covered_proof_days": 0,
    "missing_days": 2,
    "fetch_segments": [["2026-11-13", "2026-11-16"]]
  },
  "adjustment": "none",
  "historical_point_in_time": false
}
```

原有快照身份、单位、SHA、缺失与来源配置记录保持；字段落点遵循现有 manifest
扩展方式，不在文档阶段改变外部 schema。

### 10.7 维护流程

供应商变更能在现有语义内兼容时，优先改以下四处并保持对外合同；
若数据定义本身变化，必须版本化更新合同，不能靠字段改名伪装兼容：

1. `app/research_web/datahub/catalog.py` 的 binding 与语义表。
2. 对应 `providers_<source>.py` 的请求构造、归一化和校验。
3. 路由表（本文件第 10.4 节同步）。
4. fixture 与验收样本。

维护触发条件：依赖版本变化、厂商字段改名、单位变化、限流或权限变化、
`probe` 连续失败、真实 smoke 失败。

不做的事：不为单次故障临时改模型可见参数；不在运行时让模型挑选 source；
不把失败源的行与其他源拼接；不把未核单位写成已知。

### 10.8 本节状态

对外契约与来源策略为 v2 设计；正式绑定和新工具未实现。
第 11 节是执行职责，第 13 节是实施顺序；此前 Wind 优先、失败必须运维换源的提议被本版替换。

## 11. 查询架构 v2与增量补齐设计

### 11.1 三个模块与共享契约

```text
模型/脚本；复杂任务可先读 Skill
    ↓
业务工具：get_stock_kline / get_stock_quote / ...
    ↓
DataHub 查询服务：校验与准入 → 按候选查覆盖 → 选源 → 同源补缺 → 冻结结果
    ↓                       ↕ 既有本地 MarketStore
供应商适配器：翻译请求 → 调接口 → 归一化并校验
```

| 模块 | 复用位置 | 职责 |
| --- | --- | --- |
| 业务工具 | `mcp_facade/tools.py`、`backend.py` | 固定业务参数、映射内部请求、复用原提交和状态读取 |
| 查询服务 | `datahub/__init__.py`、`broker.py`、`warehouse.py`、`planning.py` | 授权、候选、同源覆盖、缺口、窗口分段、执行与结果 |
| 供应商适配 | `providers_*.py` | 源专属参数、字段、单位、分页与错误转换 |

语义是公共输入输出契约，不独立成服务。规划与路由保持可单测的函数职责，
不要求新增 `DatasetRequest`、`router.py`、独立进程或数据库。
`BusinessQuery`、`Result`、既有 catalog/binding 和 MarketStore 身份继续使用。
`market_bars` 只是内部注册标识，不是额外执行层。

### 11.2 工具域与 Skill

文档与工具目录按第 4.1 节的 Wind 七域组织；跨域公共工具、用户数据库另列为 RWB 扩展。
域目录不自动注册工具；v1 仍只做已定义且可验收的子集，债券和通用取数域暂不注册工具。
分类目录不要求拆成七个 MCP server，也不改变内部 capability 标识。

简单 K 线请求直接调 `get_stock_kline`。复杂任务如“今日市场行情”，由 Skill
规定查询哪些指数、涨跌家数、成交额、行业表现与资讯，再调用已经存在的业务工具。
Skill 不能通过说明文字获得缺失数据能力；指数历史和市场宽度工具未实现时必须报告缺项。
WeKnora 能否加载文件型 Skill 仍需单独验证，不能把普通工具说明当作已安装 Skill。

### 11.3 候选与本地覆盖共同决定来源

1. 验证账号权限、请求证券、字段、频率、单位、复权及 PIT 约束。
2. 获取已实现且满足口径的固定顺序候选。显式源请求保留该来源约束。
3. 对当前候选，按其存储身份查覆盖；全覆盖则直接冻结本地结果，不调用供应商。
4. 有缺口时检查该源实时就绪，按交易日合并缺口，再按该源调用上限分段。
5. 只从该源补齐；验证、写仓、重读整个窗口，仍有未知缺口则不算完整。
6. 当前源失败且策略允许替代时，对下一候选重新执行 3～5。
   账号/授权范围拒绝属于整个请求错误，直接停止；不能以换源绕过。

“先查本地”表示不为已有事实重复调用网络，不表示先把所有供应商数据混成一张无来源表。
覆盖身份沿用账号/授权范围、来源与配置摘要、证券、数据类型、频率、单位/字段和语义摘要。
金融聚合入口的身份还必须区分上游 vendor/service；不能把 DM 与岗底斯都只记成
`ext_finance_mcp` 就认定同源。正式 binding 标识在适配时落实并写进来源元数据。
实时服务离线与授权失效不同：前者不必阻止合法本地读取，后者仍按原权限合同处理。

### 11.4 覆盖、停牌与增量补齐

覆盖检查使用权威日历和覆盖证明；不能从 max(date) 推定中间日期都完整。
`last_complete_date` 只能作为加速提示，不是跳过区间检查的依据。

| 日期状态 | 处理 |
| --- | --- |
| 正常已完成交易日且事实满足字段合同 | 算事实覆盖 |
| 有来源可追溯的停牌、未上市证明 | 算证明覆盖，不填造 OHLC |
| 缺行且无证明 | 缺口 |
| 今天未收盘 | 最终日 K 查询排除该未完成交易日并记录有效范围；盘中快照另走快照工具 |
| 整个窗口均休市 | 日历已确认时返回空且无缺口；日历未知不能当作完整空结果 |
| 历史值被供应商修订 | 显式 refresh 重取；普通缺口补齐不保证发现既有日期修订 |

真实 `CoverageProof` 字段为 `business_date / state / evidence_id / available_at`，
state 为 `suspended / prelisting / nontrading / unknown`。不新增虚构的 `reason/source_digest`
字段；来源与授权身份位于现有存储上下文。`unknown` 不算覆盖。

缺口按交易日序列合并：周五、周一都缺则是一段；中间有已覆盖交易日则分开。
超过现有 16 段阈值时保留现行折叠规则；折叠后仍按源窗口拆分，
返回重叠数据时沿既有一致性校验，不能绕过冲突处理。

### 11.5 原始数据、复权与快照

复权仓库目标为不复权价格及真实量额，加同来源的因子/公司行为数据；
不是宣称当前全部 provider 已能产出该存储形态。现有已存数据不迁移或删除。

只对已验证为兼容乘法因子的来源使用下式，其他模型交给相应适配并单独验证：

```text
qfq(t, base) = raw_price(t) × factor(t) / factor(base)
hfq(t, origin) = raw_price(t) × factor(t) / factor(origin)
```

同时记录因子来源、版本、基准日、公式版本、原始价版本；raw 与因子不能随意跨源。
读取时生成复权视图；冻结查询结果仍可保存复权行作为证据，不当作无版本的仓库事实。
`as_of` 是历史可知时间，`adjustment_base_date` 是价格缩放锚点，二者严格区分。
PIT 查询继续走已验证的时点读取路径，v2 不把实时源当作历史可知数据。

### 11.6 输出与复用边界

沿既有查询幂等、任务状态、分页与冻结快照链。manifest 记录实际来源、有效区间、
单位、缺口、证明摘要、复权元数据及有界计划摘要。无需创建另一套取数作业和状态服务。
快照可用不等于 PIT 已验证；供应商调用成功也不等于完整字段和覆盖通过。

查询服务、MCP 和脚本共用同一执行逻辑，避免将业务校验和缺口算法各复制一份。

### 11.7 一条链路的验收范围

首条链路为沪深 A 股日频不复权 K 线；复权能力分源验收后启用。
全命中零供应商调用；部分命中只补同源缺口；换源重新规划；
单段不超供应商限制；空窗口、停牌和失败不会被伪报为完整价格序列。
先通过这一条链路，再扩展财务、公告和其他工具。

## 12. 工具输入契约（12 个）

本节是逐个工具的目标参数合同；尚未生成或部署 schema。实现必须与模型、metadata、
测试和说明同步；K 线为首条主线，其他工具未覆盖的上游限制不得猜成已支持。

统一约定，后文不再重复：

- 所有工具都必填 `request_id`：`^[A-Za-z0-9_.:-]{1,64}$`，用作幂等键；
  同键同参返回原查询，同键异参返回 `request_id_conflict`。
- 日期一律 `YYYY-MM-DD`，不接受时间戳；`start_date <= end_date`。行情日期不晚于今天；
  交易日历可查询权威已发布的未来日历，未知日期不得猜测。
- 股票工具只接受规范沪深 A 股代码，`BJ` 与 ETF 不走股票工具。
  指数工具按指数身份校验，基金工具接受其六位基金代码；不能把股票限制套给其他域。
- 工具不接收 `capability`、`source`、`allow_fallback`、URL、凭据、SQL。
- 返回保留原提交结构中的 `id` 与 `session_id`；status 调用的入参名为 `query_id`，
  其值来自返回的 id。最终字段与行数据由原 status/manifest 读取，不另造查询标识。

### 12.1 get_stock_kline

所属域：`stock_data`。

单只 A 股日 K 历史。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `asset` | string | 是 | `^[0-9]{6}\.(SH\|SZ)$`，前缀须与代码家族一致 |
| `start_date` | string | 是 | `YYYY-MM-DD` |
| `end_date` | string | 是 | `YYYY-MM-DD`，与 start 同日或之后 |
| `frequency` | literal | 否 | 固定 `daily`；v1 不支持周/月/分钟 |
| `adjustment` | literal | 否 | `none`（默认）/ `qfq` / `hfq` |
| `adjustment_base_date` | string | 否 | 仅 qfq 可用，规则见 4.2.1 |

返回行字段：`asset`、`date`、`open`、`high`、`low`、`close`、`volume`、`turnover`、
`turnover_rate_pct`。

约束：

- 单标的；多标的必须拆多次调用。
- 复权只作用于 OHLC，`volume`/`turnover` 永远原始值。
- Wind 的 60 日上限约束单次取数段，长窗口先查同源覆盖再拆缺口；
  BaoStock 当前只支持 none。复权模型/基准日不满足时退出候选。

错误码：`data_not_equivalent`（代码或复权不支持）、`workload_too_large`（超单源上限且
无可用源）、`invalid_date_range`。

```json
{"request_id":"kline-600519-20261110-14","asset":"600519.SH",
 "start_date":"2026-11-10","end_date":"2026-11-14","frequency":"daily","adjustment":"none"}
```

### 12.2 get_stock_quote

所属域：`stock_data`。

1–20 只 A 股的最新行情快照。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `assets` | string[] | 是 | 1–20 个合规代码；不可重复 |
| `fields` | string[] | 否 | 字段白名单，见下；省略返回默认集 |

默认字段集为 `price`；`asset` 与来源时间信息始终返回，不要求模型重复请求。
指定 fields 时严格检查候选源是否满足所需字段；Wind 当前快照投影并非每项都支持，
不能用价格数据伪造涨跌幅或实时量额。

字段白名单（v1）：`price`、`change_pct`、`volume`、`turnover`、`pe_ttm`、`pb`、
`total_shares`。白名单外的字段返回 `unsupported_field`，不做静默忽略。

返回行字段：`asset`、`as_of`、`price`、`change_pct`、`volume`、`turnover`，
其中只承诺请求字段；未请求字段可省略。`change_pct` 是百分数（1 表示 1%），
volume=股、turnover=元、total_shares=股、pe_ttm/pb=倍。
来源只给交易日期时如实返回日期精度，不能补成实时秒级时间；“最新”指该源最新可得，
若为收盘数据应明确标注。最新快照不使用历史 K 线覆盖作为时效证明。

错误码：`invalid_asset`（超过 20 个或重复）、`unsupported_field`。

```json
{"request_id":"quote-20261124","assets":["600519.SH","000001.SZ"],
 "fields":["price","change_pct"]}
```

### 12.3 get_stock_financials

所属域：`stock_data`。

单只 A 股财务数据。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `asset` | string | 是 | 沪深 A 股代码 |
| `dataset` | literal | 是 | `summary` / `income_statement` / `profitability` / `cash_flow` |
| `periods` | string[] 或 int | 否 | 报告期 `YYYY-MM-DD` 列表，或最近 N 期（1–100） |

数据集与源的对应（内部路由用，不暴露给模型）：

| dataset | 首选源 | 说明 |
| --- | --- | --- |
| `summary` | 天软 → Wind | 通用财务摘要 |
| `income_statement` | AKShare | 新浪披露利润表，不是利润率指标；最多 8 期 |
| `profitability` | BaoStock | 仅一个明确季度末，2017 年起 |
| `cash_flow` | BaoStock | 仅一个明确季度末的现金流比率，不能冒充完整现金流量表 |

返回行字段：`asset`、`report_period`、`field`、`value`、`unit`、`as_of`。

约束：单季与累计值必须分开返回，不得相加；`BaoStock` 的季度末快照不是
完整季度流量。`profitability/cash_flow` 必须显式传单个季度末列表；
`income_statement` 只允许最多 8 期；不能把通用参数表中的 100 期上限当作所有 dataset 都支持。
summary 未传 periods 时按当前源最新可得报告期返回，并在元数据明确实际报告期。
岗底斯三大报表仍是待接契约，不改变此表现有路径。

错误码：`data_not_equivalent`（dataset 与源不匹配）、`invalid_date_range`。

```json
{"request_id":"fin-600519-2025","asset":"600519.SH",
 "dataset":"income_statement","periods":["2025-12-31"]}
```

### 12.4 get_stock_activity

所属域：`stock_data`。

个股资金与交易事件。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `asset` | string | 是 | 沪深 A 股代码 |
| `dataset` | literal | 是 | 见下表 |
| `start_date` | string | 条件 | `margin_trading` 必填 |
| `end_date` | string | 条件 | `margin_trading` 必填 |

数据集（对齐天软已实现的六类）：

| dataset | 说明 | 时间参数 | 跨度 |
| --- | --- | --- | --- |
| `fund_flow` | 资金流 | 可选 | 按源限制 |
| `margin_trading` | 融资融券 | 必填 | < 60 天 |
| `holder_data` | 前十名股东合计 | 不需要 | 取最新报告期 |
| `holder_details` | 前十名股东明细 | 不需要 | 取最新报告期 |
| `block_trade` | 大宗交易 | 可选 | 按源限制 |
| `chip_turnover` | 筹码换手 | 可选 | 按源限制 |

返回行字段：`asset`、`date`、`dataset`、`field`、`value`、`unit`。

约束：

- 天软只支持单标的；`holder_data` 要求前十名完整，否则 `top10_pct` 为 `null`
  并标 `partial_top10`。
- `margin_trading` 跨度必须小于 60 天，否则 `workload_too_large`。
- 不同源的资金流口径不同（主动买卖 vs 成交额拆分），manifest 必须记录 `source`，
  禁止跨源拼接同一序列。

```json
{"request_id":"act-600519-202611","asset":"600519.SH","dataset":"margin_trading",
 "start_date":"2026-11-01","end_date":"2026-11-20"}
```

### 12.5 get_fund_detail

所属域：`fund_data`。

基金资料。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `code` | string | 是 | 6 位基金代码 |
| `dataset` | literal | 是 | `nav` / `profile` / `distributions` / `holdings` |
| `start_date` | string | 否 | 仅 `nav` 使用 |
| `end_date` | string | 否 | 仅 `nav` 使用 |
| `year` | int | 否 | 仅 `holdings` 使用，1990–当前年 |
| `limit` | int | 否 | 1–100，默认 30 |

返回行字段：`code`、`date` 或 `report_period`、`field`、`value`、`unit`。

约束：`holdings` 是「已披露持仓」，不是完整持仓；`nav` 的净值单位是元/份，
不得与累计净值相加。当前唯一源是东方财富。

```json
{"request_id":"fund-000001-202611","code":"000001","dataset":"nav",
 "start_date":"2026-11-01","end_date":"2026-11-20","limit":30}
```

### 12.6 get_index_quote

所属域：`index_data`。

指数单时点行情。注意：RWB 的 `index_data` 目前只有单日快照，**没有指数区间 K 线**。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `indexes` | string[] | 是 | 1–20 个指数代码，如 `000300.SH` |
| `date` | string | 否 | `YYYY-MM-DD`；省略取最近可得交易日 |

返回行字段：`asset`、`as_of`、`name`、`price`、`change_pct`。

约束：

- 当前已实现的对应来源为 Wind Excel，不代表此刻 callable；未就绪时按本地覆盖/来源规则判断。
- `indexes` 是计划中的批量业务输入，底层 `BusinessQuery` 只有单个 `index`：
  查询服务逐个构造 `index_data / dataset=quotes / index=代码 / date?` 并在原作业内组合结果，
  全部标的使用同一来源，不新增子任务服务。任一失败需列出标的缺项，不伪报整批完整。
  该批量映射尚未实现，注册前必须验收；源分页完成不代表整批标的齐全。
- 需要指数历史走势时，本批不提供；不要用 `get_stock_kline` 冒充，
  那会走股票端点并返回 `data_not_equivalent`。

```json
{"request_id":"index-20261124","indexes":["000300.SH"],"date":"2026-11-14"}
```

### 12.7 search_news（条件启用）

所属域：`financial_docs`。

财经新闻关键词与日期检索；必须先接通真正支持该语义的上游才注册。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `query` | string | 是 | 1–128 字符 |
| `limit` | int | 否 | 1–100，默认 20；表示输出上限，不保证命中数量 |
| `start_date` | string | 否 | `YYYY-MM-DD`，语义与上游检索能力核对 |
| `end_date` | string | 否 | `YYYY-MM-DD` |

返回 `published_at / title / content / source_url / source`，并注明检索范围与覆盖限制。
当前财联社 binding 仅最新 N 条，不能用“先取最新再子串过滤”冒充历史检索。
本工具状态 NOT_RUN，候选 iFinD/财汇完成适配后启用。
若后续需要最新电报另定义 `get_latest_news`，不在本批悄悄增加第 13 个工具。

```json
{"request_id":"news-fed-202611","query":"美联储","limit":20,
 "start_date":"2026-11-01","end_date":"2026-11-20"}
```

### 12.8 search_announcements（条件启用）

所属域：`financial_docs`。

公司公告检索。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `asset` | string | 是 | 沪深 A 股代码 |
| `query` | string | 否 | 1–128 字符 |
| `start_date` | string | 否 | `YYYY-MM-DD` |
| `end_date` | string | 否 | `YYYY-MM-DD` |

返回行字段：`published_at`、`title`、`document_url`、`document_type`。

**状态：本工具绑定未实施，验收 NOT_RUN。** 此处仅指本工具的正式 DataHub binding；
不否认其他独立公告入口、既有事件标题索引或前述上游公告实测。
岗底斯 `查询A股公告列表` 与 iFinD `search_notice` 都需要先完成结构化投影和单位/
字段核验。P1 验收通过后本工具才注册；否则不注册，WeKnora 目录里也不出现。

**两个候选源的实测对比（2026-11-24，600519.SH，2026-10-01～11-14）：**

| 维度 | 岗底斯 `查询A股公告列表` | iFinD `search_notice` |
| --- | --- | --- |
| 返回形态 | 结构化列表，每行一个对象 | 语义检索片段（文本段落） |
| 实测规模 | `total: 167` | `size` 上限 20 |
| 字段 | `announcementId`、`title`、`announcementDate`、`publishTime`、`securityCode`、`securityName`、`primaryCategory`（含二级分类）、`sourceName` | 段落文本，需自行解析 |
| 分类 | 有（财务报告 / 公司治理 / 一般公告等两级） | 无 |
| 来源标注 | `sourceName: 上海证券交易所` | 未明确 |
| 检索方式 | 按代码 + 日期区间精确查询 | 自然语言语义查询，`time_start`/`time_end`/`size` 必填 |
| 是否需二次调用 | 是，取 PDF 需另调 `下载A股公告文件` | 否 |

**结论：`search_announcements` 接岗底斯。** 契约要求的 `published_at`、`title`、
`document_type` 岗底斯直接给出；实测的 iFinD MCP `search_notice` 返回文本片段，
需额外解析且无分类。这不是对 iFinD 原生 API 公告能力的结论。
iFinD 的日期格式描述写成 `yyyyy-MM-dd`（五个 y），本身也需要另行验证。

岗底斯的缺口是 `document_url`：列表接口未直接给出 PDF 链接，需二次调用
`下载A股公告文件`。可核实到该条公告的来源页才填写链接；否则返回 null 并标
`attachment_status=pending`，不得用交易所首页冒充该公告原文。

### 12.9 get_economic_series

所属域：`economic_data`。

中国宏观时间序列。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `series` | literal | 是 | `cn_cpi` / `cn_gdp` / `cn_pmi` / `cn_m2` |
| `start_date` | string | 否 | 省略取源默认窗口 |
| `end_date` | string | 否 | 不晚于今天 |

返回行字段：`date`、`series`、`value`、`unit`、`frequency`。

约束：

- 四个系列口径分别是：CPI 当月同比、GDP 累计同比、PMI 制造业、M2 同比。
  单位与口径固定，manifest 必须写明，不能只写「CPI」。
- 不提供 `as_of`（历史时点）；请求带 `as_of` 返回 `data_not_equivalent`。
- 美国宏观仍走 `rwb_datahub_query`（FRED/BLS），不在本工具范围。

```json
{"request_id":"macro-cpi-2025","series":"cn_cpi",
 "start_date":"2025-01-01","end_date":"2026-10-31"}
```

### 12.10 search_assets

所属域：`跨域公共`。

按名称、简称或代码检索证券。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `query` | string | 是 | 1–128 字符；代码或名称 |
| `asset_type` | literal | 否 | `stock`（默认）/ `fund` / `index` |
| `market` | literal | 否 | `CN`（默认） |
| `limit` | int | 否 | 1–50，默认 20 |

返回行字段：`asset_id`、`code`、`name`、`market`、`asset_type`。

约束：

- 只做证券身份检索，不是条件选股。股票结果可调股票工具，基金/指数分别调对应域工具。
  当前来源不支持某资产类型时返回不等价，不承诺所有类型都可检索。
- 天软对纯中文检索返回 `data_not_equivalent`（只接受代码或字母数字），
  此时路由落到 AKShare/BaoStock；中文名检索能力当前有限。
- 结果可能为空，`empty` 不等于「该证券不存在」。

```json
{"request_id":"find-maotai","query":"600519","limit":10}
```

### 12.11 get_trading_calendar

所属域：`跨域公共`。

交易日历。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `market` | literal | 是 | 固定 `CN` |
| `start_date` | string | 是 | `YYYY-MM-DD` |
| `end_date` | string | 是 | 跨度 ≤ 1464 天 |

返回行字段：`date`、`is_open`。

约束：`is_open=false` 只是休市，不等于数据缺失；缺口计算必须区分这两者。

错误码：`invalid_date_range`（跨度超限或倒序）。

```json
{"request_id":"cal-202611","market":"CN",
 "start_date":"2026-11-01","end_date":"2026-11-30"}
```

### 12.12 query_user_table（条件启用）

所属域：`用户数据库扩展`。

对用户 MySQL 执行参数化只读单表查询。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `database` | string | 是 | 必须精确来自 `information_schema` |
| `table` | string | 是 | 同上 |
| `columns` | string[] | 是 | 1–200 个，必须精确来自表结构 |
| `filters` | object[] | 否 | ≤20 个；operator 限 `eq/ne/lt/lte/gt/gte/in/between/is_null/not_null` |
| `order_by` | object[] | 否 | ≤5 个 |
| `offset` | int | 否 | 0–100000，默认 0 |
| `limit` | int | 否 | 1–5000，默认 500 |

返回行字段：用户选择的列。

约束：

- 只允许单表 SELECT，禁止 JOIN、子查询、聚合、表达式、DDL/DML。
- 每次执行前校验账号只读权限（`USAGE`/`SELECT`/`SHOW VIEW`）。
- **状态：NOT_RUN。** 历史盘点未配置 MySQL，本轮未重验；未配置时本工具不注册。
  `database_schema` 仅为内部能力，尚无本文定义的新 MCP 工具，不计入 12 个。
- filters 的每项为 `{column, operator, value?}`：列名精确来自结构；in 的 value 为数组、
  between 为双元素数组；is_null/not_null 不带 value。其余操作值为与列兼容的标量。
  order_by 每项为 `{column, direction}`，direction 只允许 asc/desc。所有值使用参数绑定。
- 发现库表和列结构沿原 RWB 数据库设置/目录；WeKnora 尚无独立 schema 工具，
  结构未经确认时不调用本工具，不让模型猜库表。

## 13. B实施设计 v2

本节以下为原实施设计；当前完成情况：B1交易日合并修复、B2仓库接入、
B3 Wind缺口分段、B4九个业务工具与岗底斯日线绑定、B5有界计划摘要已在候选源码实现。
既有同源仓库与权限路径复用；不声称实现了所有源的任意长窗口、因子视图或12个候选。
历史测试与后续候选验收分别见实现报告；原“尚未修改”描述是当时计划状态。


### 13.1 当前实现与缺陷

B1 文件已存在但未接入生产调用；历史记录为 planning 27 用例及 warehouse 6 用例通过。
本轮未重跑这些测试，不能将该记录视为 v2 完成证据。

- `warehouse.py:missing_queries()` 按完整 expected_dates 序列合并缺口。
- `planning.py:merge_days()` 按自然日相邻合并，周五与周一被拆为两段。
- 本轮最小复现：缺口 2026-11-13、2026-11-16，旧实现一段，新实现两段。
  撤回“原样提取、算法等价”的表述；现有单测不足以证明与旧实现等价。
- `_can_plan_wind_gaps()` 还检查 Wind 原始跨度是否超限，决定能否延后完整窗口限制。
  它是布尔策略判定，不能直接替换成一个返回 `Plan` 的调用。
- `plan()` 的 proofs 目前只保留排序；排除停牌必须由明确的覆盖逻辑完成，
  不能声称传入证明就自动消除了缺口。

### 13.2 B1 修正：使用交易日序列

目标纯函数签名（设计，尚未修改代码）：

```python
def merge_gaps(expected_dates, missing_dates, *, max_segments=16):
    # expected_dates 必须是已验证窗口内的有序交易日序列。
    # 顺序扫描：缺口日期延长当前段；已覆盖交易日结束当前段。
    # 16 段折叠沿用旧规则，随后由源专属分段函数约束跨度。
    ...
```

日期去重、窗口边界、证明有效性由现有上下文与覆盖服务提供。
B1 修正保留既有计数接口；事实天数、证明天数的区分在接入时添加摘要，
不把旧 `covered_days` 未经核对直接改解释成“真实行数”。

### 13.3 B2 接入：先保留原有 Wind 行为

在现有 `warehouse.missing_queries()` 内复用修正后的纯函数，继续使用原
actor/scope/dataset/configuration_digest 计算缺口。暂不改变源顺序、授权、refresh、PIT、
Wind 延后跨度检查与 source 约束；避免一次改变算法和准入语义。

旧算法与新函数做固定输入差分测试即可，不新增生产双跑开关。
暂留旧接口给调用方使用，避免直接替换 `_can_plan_wind_gaps()`。

### 13.4 B3 查询服务：同源规划与窗口分段

复用既有 broker 来源候选与权限校验，依次构建 source-bound 存储上下文。
显式 `source=akshare` 只命中 AKShare 对应仓库；auto 不能复用任意来源的覆盖集合。

缺口合并后，按该源单次跨度/行数限制拆分。Wind 单次 ≤60 自然日，
长历史请求可以由本地覆盖加多个合规缺口请求完成；不得仅因整体窗口 >60 天淘汰。
去掉 source 特例必须同时通过权限与来源隔离、调用上限测试，不能只删条件。
源专属校验留在原适配/准入逻辑，不复制到 MCP 工具。

### 13.5 B4 工具与供应商契约

先注册 `get_stock_kline` 并复用原提交/status 链，工具补入固定股票类型。
岗底斯经 `ext_finance_mcp` 接入正式行情 binding 前，逐项核对：
OHLC、真实量额单位、日期、分页、频率、窗口上限、错误、复权因子模型与基准日。
不复权契约可先验收；复权未通过时不承诺支持 qfq/hfq。

业务工具的 `adjustment_base_date` 当前不在 `CAPABILITY_PARAMETERS[market_bars]` 中；
启用时需同步扩展参数允许集、源支持校验、缓存/语义身份和 manifest。未完成前拒绝该参数，
不能绕过 BusinessQuery 校验。指数批量参数、证券搜索 limit 等工具输入与原请求不同的地方，
也需在查询服务显式翻译或本地裁剪，不能整包透传。

此步骤可能需要局部修改供应商适配，撤回旧版“不改任何 provider”的绝对限制。
不新增依赖、迁移、常驻服务或处理凭据；付费实测按单独授权的范围执行。

### 13.6 B5 计划摘要与逐项扩展

在既有 manifest 扩展位置记录有界计划摘要，旧快照无字段仍能读取。
使用原查询 id、来源、授权和快照记录关联计划，不另造一套作业表。
只有 K 线端到端通过后再逐项接财务、公告等；不为阶段标签强拆五个 PR。

### 13.7 必要验证

| 场景 | 必须观察的结果 |
| --- | --- |
| 周五与周一连续缺失 | 一段，与旧算法一致 |
| 两个缺口之间有已覆盖交易日 | 两段 |
| 碎片超 16 段 | 旧折叠规则，最终执行段仍满足源上限 |
| 同源全覆盖、供应商离线但授权有效 | 0 次供应商调用 |
| 显式源 A，只有 B 的本地缓存 | 不得命中 B |
| A 部分覆盖后失败转 B | 重算 B 整段覆盖；最终序列没有 A/B 混合 |
| 长历史中有 >60 日连续 Wind 缺口 | 切成多段，每段 ≤60 自然日 |
| 停牌证明、未上市、休市空窗口 | 事实行、证明日、未知缺口分别计数 |
| 今日未收盘 | 不当作已完成日 K；报告有效范围 |
| refresh / PIT / 配置摘要变化 | 保持原语义与授权检查 |
| 复权锚点或模型不支持 | 拒绝不等价来源，不换口径 |
| WeKnora 发现与实际调用 | 只有已注册工具可用，不能以重新授权替代实现 |

### 13.8 本轮交付边界

v2 本轮只更新本文、任务报告及生成 HTML；B1 缺陷仍待上述实现修正。
没有新增业务工具，没有变更默认来源，没有部署服务；历史实测不冒充本轮复验。

## 14. 清单驱动的工具与 K 线合同

本节为 2026-11-25 追加设计；只补文档，不改变实现任务的代码、源优先级或部署状态。
第 13.8 节记录设计阶段边界；其后的实现候选状态以开篇链接的实现报告为准。
本节纠正“只看 Wind 工具和现有 binding 就定数据源”的不完整盘点方式。

### 14.1 已有清单怎样进入设计

**Wind 决定工具如何分类，已有数据源清单决定有哪些来源可以评估，已验证契约决定哪些来源可以执行。**

| 依据 | 本轮使用范围 | 维护责任 |
| --- | --- | --- |
| [数据源主清单](../DATA_SOURCES.md) | 行情、财务、宏观、文本及各入口覆盖/访问条件/证据 | 来源事实与已核范围的入口，变化更新原条目 |
| 主 checkout 清单指向的本机 AlphaDesk 补充 | 历史线上样例、额外行情与文本线索 | 私有材料留在本机，本计划仅记录必要能力与限制 |
| Wind 本地工具 manifest/合同 | 七域 34 工具的名称与职责 | 业务目录；不据此推定 DataHub 已实现 |
| DataHub catalog/binding/Provider | 可执行能力、参数翻译、单位与来源准入 | 代码中的固定适配和路由 |
| 具体样例/任务报告/现场响应 | 实际证券、期间、字段、单位、错误和权限状态 | 带日期、入口及范围；历史成功不变成当前全源 PASS |

主仓库 DATA_SOURCES.md 有未提交的 AlphaDesk 私有补充指针，本轮只读取，
不覆盖或代交其他窗口的清单改动。清单、旧 checkout 和实现候选不一致时，
在来源表说明具体版本；不能只因旧代码没有 binding 就删掉已有可用来源线索。

工作顺序固定为：**用户问题 → Wind 域/工具 → 查主清单及补充 → 匹配市场/字段/时间/复权
→ 核对已实现契约和授权 → 按固定路由执行 → 更新来源证据**。
清单是开发与维护的依据，生产模型无需每次读整份清单或重新选择供应商。

### 14.2 七域与已有清单的对应

| Wind 业务域 | 清单中的候选入口 | 应优先核实的边界 |
| --- | --- | --- |
| stock_data | Wind Excel/MCP、天软、AKShare、BaoStock、iFinD QuantAPI；金融 MCP 的岗底斯/iFinD/DM；AlphaDesk 东财/腾讯线索 | 市场、单股身份、周期、原始/复权、成交量额、实时与最近日线 |
| fund_data | 东方财富基金/天天基金、Wind MCP、iFinD、财汇；AlphaDesk 基金排行/详情线索 | 净值与成交价区分，ETF/LOF 与场外基金区分，持仓披露期与实际覆盖 |
| index_data | Wind Excel/MCP、腾讯固定九指数、东财市场页、中证/国证、蛋卷/FundDB；岗底斯/DM/iFinD 指数接口 | 固定九指数不等于全市场，报价/K线/成分/估值/排行分别绑定，板块分类体系固定 |
| bond_data | DM、iFinD、财汇、Wind MCP；AlphaDesk 中美国债收益率、NYFed/Treasury 相关利率线索 | 国债收益率曲线不等价于单券成交 K 线；票息、收益率、估值与发行人财务分别验收 |
| financial_docs | Wind MCP、发行人/交易所原站、岗底斯、iFinD、财汇、Alpha 派、Golddata、财联社及其他已登记资讯入口 | 公告索引/全文、新闻/研报分开；最新流不等价于历史检索；AI研判与发布方原文分开 |
| economic_data | AKShare 中国宏观、FRED/BLS/Fed/NYFed/Treasury/WorldBank/BEA、iFinD/DM、WGC/SPDR/KAPSARC | 指标、单位、发布/观察期、修订版本；利率、黄金实物与经济序列按具体工具合同决定覆盖 |
| analytics_data | 保留通用取数目录位置；参考主清单中尚未纳入专项工具的真实需求 | 暂不注册 get_financial_data；不要将所有残余源自动塞进万能接口 |

公共证券检索和交易日历，以及用户 MySQL/文件/冻结快照，仍为 RWB 扩展或受控输入。
AlphaDesk 只是能力和历史证据的补充，不默认为每次取数的中转服务。
先复用 RWB 已有适配；缺少适配时才评估新 binding，并保留真实底层出处。

### 14.3 K 线来源矩阵：接口存在、适配与实取分开

本轮核对了主清单、AlphaDesk 2026-11-16 记录、旧基线代码及
weknora-datahub-complete-20261125 候选实现/报告。没有新请求供应商或读取凭据。

| 来源/入口 | 可供设计使用的证据 | RWB 接入与缺口 | 本轮结论 |
| --- | --- | --- | --- |
| Wind Excel | 已有沪深 A 股 daily，none/qfq/hfq；源单段 ≤60 自然日 | 已有 market_bars；规范 raw 语义准入，依赖本机 Excel/授权，长窗可同源分段 | 已适配；本轮未实取 |
| 天软 CJPY 0.5.2 | 日线、分钟、复权相关接口；vol=股、amount=元有固定记录 | 已有 market_bars；OHLC 币种/单位仍缺规范 raw 依据 | 保留候选线索；严格 CNY/股合同暂不准入 |
| AKShare | 沪深股票 daily/weekly/monthly；新浪、东财实际出处；none/qfq/hfq | 已有 market_bars；raw 单位已定义，东财手转股；显式 qfq 锚点另外验证 | 首条 raw 候选；本轮未实取 |
| BaoStock | 沪深不复权日线、股/元；单段日期差 ≤1464 日 | 已有 market_bars，仅 none；不从上游其他能力推定当前适配支持复权 | 首条 raw 候选；本轮未实取 |
| Wind MCP | stock_data.get_stock_kline；period=10 为日线 | 独立 Skill 有工具，未接为 DataHub 行情 binding；aftime=0 为前复权、1 为后复权，none 参数未核 | 待接入；不能用 aftime=0 冒充 none |
| 岗底斯，经金融 MCP | 历史日线样例；11-25 实现报告新增 raw 四行跨 BaoStock 对账 | 新候选增加 ext_finance_mcp/market_bars/gangtise_raw_daily，单股 daily/none，单次 ≤367 自然日；旧 checkout 不含 | 已有候选绑定；有限跨源单位证据，不等于厂商完整字典/生产验收 |
| iFinD QuantAPI / ext_ths | 主清单记有授权历史行情端点和受限历史样例 | external_data 已登记，与旧 disabled 的 ifind SDK 入口不同；成为公共 K 线 binding 尚待规范化 | 需纳入后续适配评估，不因 SDK disabled 排除 HTTP |
| iFinD / DM，经金融 MCP | get_stock_performance、equity_bars_data 等发现记录 | 自然语言/原生参数与输出需分别适配；网关目录不是完整行情合同 | 待公共 K 线绑定 |
| 东财/腾讯，经 AlphaDesk 补充 | 东财前复权 600 根日线曾有线上样例；腾讯前复权为源码/备用路径线索 | 未据此认证当前 RWB 独立单股 binding；与 AKShare 共用东财底源时不算独立出处 | 纳入线索，不直接进入 none 候选 |
| Yahoo/Nasdaq 等外部端点 | 主清单有海外历史线索；AlphaDesk Yahoo 全球资产记录 | 当前受限沪深 A 股首条工具不使用；单独核对海外证券、币种、交易时区 | 留给后续港美股合同 |

因此不再使用“只有四个/六个来源”概括全部可用资源。**旧基线四个 market_bars
适配、实现候选新增岗底斯、独立 MCP/HTTP 与私有清单线索**应分别计数。
同一接口的不同部署、同一东财数据经不同库转发，都不算独立数据提供方。

### 14.4 get_stock_kline 的首条公共合同

目录位置 stock_data，MCP 工具名 get_stock_kline；输入只收业务参数。
当前实现候选与后续目标分开：现有候选只接受截至昨日，未来要支持“今日已完成日线”
时须增加权威收盘/到数判断后再开放，不能仅把 today 当作完成日。

| 参数/行为 | 首条实现合同 |
| --- | --- |
| request_id | 必填，1–64 个字母/数字/下划线/点/冒号/短横；按 grant 幂等 |
| asset | 必填，单个规范大写沪深代码；SH 以 6 开头，SZ 以 00/30 开头；不接名称、裸代码、数组、ETF/指数或 BJ |
| start_date/end_date | 严格 YYYY-MM-DD，含首尾，start ≤ end；end 早于受理时上海日期 |
| frequency | 可省，默认且仅 daily；其他周期拒绝 |
| adjustment | 可省，默认且仅 none；qfq/hfq 与 adjustment_base_date 此阶段拒绝，不静默换口径 |
| 内部映射 | capability=market_bars、asset_type=stock、required_semantics=cn_stock_daily_cny_share_v1，来源由服务端固定规则决定 |
| source 等参数 | 公共工具拒绝 source/capability/allow_fallback/URL/凭据/SQL/未知键；原脚本/API 显式源合同保留 |
| 时间含义 | date 是上海市场交易日期；取得时点、行情日期与 PIT 分开，历史数据不自动具备历史当时可得性 |
| 容量 | 沿用既有 5000 行及响应字节限制；分段不解除总容量和执行截止，不静默截断后称完整 |
| 结果读取 | 原提交 id/session_id/status；rwb_datahub_status(query_id=id)，默认100行、每页最多500行 |

必需行字段：asset/date/open/high/low/close/volume/turnover。
OHLC 单位 CNY/股，volume=股，turnover=CNY；turnover_rate_pct 可缺且为 null。
数值须有限，量额非负，真实交易行满足 low ≤ open/close ≤ high；停牌占位与真实交易行
按来源合同解释，不能凭 volume=0 推断停牌，更不能制造停牌日价格。

完整性按权威日历与来源可追溯的停牌/未上市证明判断；未知缺行是缺口。
全休市窗口可有证明地返回空结果，空响应本身不构成完整覆盖证明。
实际范围、字段单位、来源及 upstream、证明/缺口、复权和 rows 摘要沿原 manifest 保存；
原件字节与模型可读投影分别保留。data_success 还需看字段/质量/覆盖，不能只看 completed。

### 14.5 首条路由与维护规则

旧基线规范 raw 顺序为 wind → akshare → baostock。
实现候选的 Broker 额外允许岗底斯，binding 追加在既有候选之后，
因此该候选中的顺序为 **Wind Excel → AKShare → BaoStock → 岗底斯**。
这不是本轮实测的稳定性排序。天软补足单位证据、Wind MCP/HTTP 等完成正式绑定后
再版本化调整固定表；不能因为清单有接口就现场临时插入运行路由。

每个候选均执行：授权与语义准入 → 同源本地覆盖 → 缺口合并与分段 → 只补同源缺口
→ 验证写仓 → 重读整个请求区间 → 冻结快照。全覆盖时无需供应商在线；
仍有缺口才检查实时 readiness。未配置研究仓时不能伪报命中，复用原查询路径取完整源数据。
源身份包含账号、授权、配置、真实 vendor/upstream、证券、频率、字段/单位与调整语义。

| 情况 | 处理 |
| --- | --- |
| 请求非法或 RWB/grant 权限失效 | 停止请求，不换源绕过权限 |
| 来源不支持单位/频率/身份，或未配置/依赖缺失 | 记录跳过原因，评估下一合格候选 |
| 网络失败、限流、busy、源超时 | 不自动重放同一候选；原策略和剩余预算允许时转下一候选 |
| 厂商认证/配额错误 | 不重试该源；替代源必须有独立授权且既有策略允许 |
| 错证券、非法值、单位不明、形状变化 | 不发布合格价格事实，保留原安全错误分类与 attempts |
| 缺行且无证明、分页未完成 | 保留缺口，不能称完整；换源则从新源重算整个窗口 |
| 取消、执行结果未知、同步 SDK 尚在运行 | 沿原取消/排空机制，不重放未知调用、不提前释放容量 |

换源不得混合前一候选已取得的行；前一源合法已落仓的事实可留在自己的存储身份下。
沿用原执行 deadline、MAX_ATTEMPTS、Wind 单线程与排空约束；多段请求必须受总预算约束。
Facade 异步提交不赋予无限执行时间，也不擅自扩大已有 Provider 截止。

维护时依次同步：主清单中的范围/证据 → Provider 翻译与校验 → catalog binding/顺序
→ 同源存储语义身份 → fixture/真实验收样例 → 工具说明。
字段仅改名且语义相同可局部兼容；单位、复权或时间定义改变时必须更新合同版本，
不覆盖旧快照，也不让模型改问法来修接口。

### 14.6 调用轨迹与验收规格

用户要“贵州茅台11月10日至16日的不复权日 K”，名称经 search_assets 确认身份后：

```json
{"request_id":"kline-600519-20261110-16","asset":"600519.SH",
 "start_date":"2026-11-10","end_date":"2026-11-16",
 "frequency":"daily","adjustment":"none"}
```

假设日历确认10/11/12/13/16五日；Wind 同源已覆盖10～12，仅缺13/16，则周末跨越合为
13～16一段，取回并核验后重读五日。若 Wind 失败、AKShare 整段可得，则最终全部使用
AKShare，并保留真实新浪/东财 upstream。提交返回原 id，status 分页至完整；
这里是假设轨迹，没有填写或伪造价格。

| 实施验收场景 | 必须观察的结果 |
| --- | --- |
| 标准五日请求 | 源、证券、原始OHLC/量额、日期与单位逐项对账；事实/证明/未知缺口分别记录 |
| 同 request_id 同参/异参 | 同参复用 id 和冻结快照且不重复调用；异参冲突 |
| 错后缀、裸代码、ETF、未来/当日 end、额外键 | 入场拒绝，Provider 调用数零 |
| qfq/hfq/周月分钟/自定义基准日 | 首条接口拒绝，不改口径；后续启用需另验 |
| 周五与周一同时缺失、超60日 Wind 缺口 | 前者一段；后者同源按上限拆分，不直接淘汰长窗 |
| 同源全覆盖但供应商离线 | 授权有效且仓已配置时零上游调用；授权失效不能读 |
| A 有部分数据后失败转 B | B 重算整段；输出无 A/B 混合 |
| 全休市、停牌、缺行、无日历 | 有证据空结果/证明覆盖与未知缺口分开，不造OHLC |
| 源 total 不符、分页 incomplete、错单位/错证券/重复日 | 按源合同拒绝或保留缺口，不能完整通过 |
| 东财手转股、501行读回、超总上限 | 不重复换算；分页完整读回；容量拒绝/partial不伪装完整 |
| 重取历史修订、撤权、配额不足、deadline、取消排空 | refresh 沿原语义；原快照保留；无越权返回、同源盲重试或提前释放容量 |

本表是新增验收规格，不是本轮测试结果。已有实现报告的通过用例只覆盖其明确列出的范围；
工具名称迁移、全面同源覆盖、空窗口证明与新增矩阵需逐项核对，不能一并声称通过。

### 14.7 紧接着的实施输入

先把当前九工具候选与 Wind 34 工具目标目录做名称/职责迁移核对，再对 K 线链路
按14.4～14.6补缺。其中当日 K 线、复权、独立 Wind MCP、iFinD HTTP、AlphaDesk 补源
不纳入首条 raw 的已完成范围。后续每个工具继续以同样的“清单来源 → 公共契约
→ 合格绑定 → 固定路由 → 维护与验收”模板迭代。

## 15. 股票域逐工具映射与实施缺口

本节按用户确认的 Wind `stock_data` 十工具逐项设计，结合数据源主清单、
AlphaDesk 本机补充、Wind 本地合同及业务工具候选源码。
核对日为2026-11-25；本轮没有供应商实取、模型调用、凭据读取或部署。
“已适配”表示原能力可复用；“待接”表示需要公共合同/绑定；均不等于现场 callable。

### 15.1 公共约定与证据入口

- 十个工具共用现有账号、grant、request_id、提交 id/status/冻结证据路径。
  参数表是目标设计；仅已存在的参数模型才可作为当前可执行 schema。
- 首批以沪深 A 股为范围；Wind 支持港美股不自动扩大 RWB 覆盖。代码先解析成规范 asset，
  ETF、指数、基金不得落到股票端点。
- 每工具固定内部 capability/dataset/候选来源，模型不指定 source、SQL、URL、厂商工具名。
  暂无等价能力时记为待适配，不通过 external_data 的任意参数透传补洞。
- 每项输出至少能追溯证券、数据日期/期间、取得时间、来源/upstream、原件与快照。
  比率尺度、币种和时间精度未核时说明未知，不默认为 CNY、百分数或实时秒级。
- 输入/输出表中的新字段是设计提议，实际 schema、字段字典与样例验证完成后才能注册。
  原件和标准化投影分别保留，模型不负责转换供应商单位。

| 证据入口 | 本节怎样使用 |
| --- | --- |
| [数据源清单](../DATA_SOURCES.md) | Wind、天软、AKShare、BaoStock、iFinD HTTP、市场页、文本源的覆盖和既有证据 |
| 主 checkout 的 AlphaDesk 私有补充 | 东财/腾讯报价和前复权历史、iFinD/公司/产业链线索；区分线上样例与源码描述 |
| [Wind 工具合同](../../.agents/skills/wind-mcp-skill/references/tool-contracts.md) | 十工具的职责边界，quote 为分钟行情，price_indicators 为快照 |
| [来源修复账本](../research-web-source-repair-ledger.md) | 历史实取及未验范围，不能以2026-10记录认证今天权限 |
| [业务工具合同](../research-web-business-tools.md) | 原九工具候选实现；不是目标十工具已实现声明 |

### 15.2 十工具输入与输出设计

所有输入均另含必填 request_id。单标的资产工具先固定为一个 asset；快照保留原候选
assets=1～20 的批量合同，底层若只支持单股，由服务端明确拆分，完整性按请求证券集合核对。

| 工具 | 业务输入设计 | 返回内容与关键口径 | 参数成熟度 |
| --- | --- | --- | --- |
| `search_stocks` | market=CN、conditions、order_by?、limit?；conditions 使用受支持字段/操作符/单位枚举 | 规范证券代码、匹配指标及其时点、实际筛选范围与分页；不只返回无依据代码 | 筛选字段/指标、比较算子与排序字典待定，不能注册泛化任意 conditions |
| `get_stock_price_indicators` | assets、fields?；沿原快照 price/change_pct/volume/turnover/pe_ttm/pb/total_shares 子集 | 请求字段、各股 as_of、时间精度/市场状态；价格CNY/股、量股、额CNY、change_pct百分数、估值倍数按源核验 | 可复用候选 StockQuote；改名与字段覆盖须验收 |
| `get_stock_kline` | asset、start_date、end_date、frequency=daily、adjustment=none | 原始OHLC、volume、turnover及可选换手；日期与单位按14.4 | 首条合同已细化；截至昨日，复权/其他周期未启用 |
| `get_stock_quote` | asset、trading_date；首批单日完整可得分钟序列，不增加任意 begin/end 跨日范围 | timestamp、price、volume、turnover、可选 avg_price；时间为Asia/Shanghai，分钟增量与日内累计分开 | 新分钟公共合同；不可套旧 StockQuote 模型 |
| `get_stock_basicinfo` | asset、fields（如身份/上市日/主营/行业子集） | 实际支持的档案字段、有效日/取得日；行业注明分类体系及版本 | 公开字段白名单待定；search_assets 只负责身份检索 |
| `get_stock_fundamentals` | asset、dataset、periods?；先复用summary/income_statement/profitability/cash_flow | 保留原财务形状、报告期、披露/可得时间和字段单位；单季/累计/集团/归母分别记录 | 可复用 StockFinancials 子集；不承诺完整三表 |
| `get_stock_equity_holders` | asset、dataset=holder_data或holder_details；暂不新增历史报告期输入 | 股东/持股数/持股比例或汇总、实际参考期/披露日；数量与比例尺度核验 | 从 StockActivity 拆分；源不支持历史期不能给假 periods |
| `get_stock_events` | asset、event_types、start_date、end_date | 事件类别、发生/公告日期、标题、来源引用与原件；日期不明保持未知 | event_types 与实际源事件类型的映射待定；先做已验证公告事件索引子集 |
| `get_stock_technicals` | asset、dataset；两融沿已支持日期范围；MACD等另带已冻结指标参数与价格口径 | 技术指标或交易统计的值、单位、窗口、输入版本及实际数据日期 | 可先拆出margin_trading子集；技术指标、龙虎榜未因此自动实现 |
| `get_risk_metrics` | asset、metrics、start_date、end_date；按指标要求带benchmark、risk_free及frequency等 | Beta/波动率等值、统计区间、样本数、年化/收益定义、基准与无风险来源 | metrics/计算参数完整合同待定；暂不注册未定义算法 |

字段白名单按工具独立维护。图表上的“近30日”不自动等于30个自然日或30个交易日；
调用方先解析成明确范围，筛选和计算任务还须声明实际样本日序列。
技术/风险输入参数只有被 schema 明确定义才允许传入，不能把本表的举例当开放字典。

### 15.3 逐工具来源、接入状态与固定路由

来源列先列原 RWB 可复用路径，再列主清单/私有补充中的待接入口。
除 K 线外，不凭工具名制定未经覆盖验证的全局主备排名；先收窄到有已实现等价字段的
候选，按原 binding 顺序执行。暂无等价 binding 的工具不注册可用项。

| 工具 | 原能力及可复用来源 | 清单/补充中的其他入口 | 目标路由决定与限制 |
| --- | --- | --- | --- |
| `search_stocks` | search_assets 不是条件选股；无已核公共筛选 binding | Wind search_stocks；iFinD QuantAPI smart_stock_picking；金融MCP iFinD search_stocks、财汇筛选 | 待选择一条受限条件合同并适配，再排主备；不下载不完整50条目录样本后称全市场筛选 |
| `get_stock_price_indicators` | market_snapshot：天软、Wind Excel、AKShare；旧get_stock_quote可复用 | Wind get_stock_price_indicators、iFinD real_time_quotation/stock_highfreq_quotes、岗底斯实时行情、AlphaDesk东财/腾讯报价 | 原顺序为天软→Wind→AKShare，经字段/单位/证券数量过滤；AKShare最近日线不伪装盘中实时，缺实时字段须拒绝该实时请求 |
| `get_stock_kline` | market_bars：Wind、AKShare、BaoStock；候选新增岗底斯；天软单位受限 | Wind MCP、iFinD HTTP/聚合、DM、AlphaDesk东财/腾讯前复权线索 | 首条规范raw按14.5：Wind→AKShare→BaoStock→岗底斯（候选版本）；none不接前复权备用 |
| `get_stock_quote` | 资产工作台已有天软分时/分钟读取与单位检查，尚非新MCP分钟工具 | Wind get_stock_quote、岗底斯分钟K接口、腾讯minute等目录 | 首条分钟合同先评估复用天软分时路径；“分钟K OHLC”与“分钟价格/增量量额”不直接互换；其他源先适配后入路由 |
| `get_stock_basicinfo` | search_assets/资产目录能复用身份；天软market_activity/industry、factor_macro/listing_date可复用限定字段 | Wind get_stock_basicinfo；iFinD get_stock_info/basic_data_service；岗底斯、财汇；AlphaDesk公司资料线索 | 先按身份/行业/上市日期等字段分别匹配已核来源；完整主营/工商档案暂无公共合同；多来源档案须逐字段标出处和时点 |
| `get_stock_fundamentals` | financials：天软/Wind摘要、AKShare新浪利润表、BaoStock盈利/现金流比率 | Wind get_stock_fundamentals；iFinD get_stock_financials；岗底斯三表、携宁、财汇；AlphaDesk SEC美股财务线索 | summary沿原天软→Wind→AKShare等合格来源；income_statement固定AKShare，profitability/cash_flow固定BaoStock；美股SEC不纳入沪深合同 |
| `get_stock_equity_holders` | market_activity：天软holder_data/holder_details；Wind holder_data覆盖按具体投影核对 | Wind get_stock_equity_holders、iFinD get_stock_shareholders、岗底斯前十大股东、财汇股权数据 | 天软明细/汇总先拆工具；Wind仅在同dataset/日期/字段等价时做候选，不将总股本当十大股东明细 |
| `get_stock_events` | 天软market_activity/events为公告标题/类型/公布日索引；现有StockActivity尚未暴露events | Wind get_stock_events；iFinD get_stock_events；岗底斯公告与事件、财汇；AlphaDesk披露日历 | 首阶段只认天软已适配事件子集，须接入工具；IPO/并购/分红等逐类补，不把披露预告当真实事件；全文另走financial_docs |
| `get_stock_technicals` | market_activity/margin_trading的Wind/天软读取可复用；完整技术指标公共合同未有 | Wind get_stock_technicals；iFinD get_stock_performance技术字段；已取得K线上的本地计算方案 | 两融按原合格binding；MACD/RSI等需先决定供应商指标或本地公式并版本化，不能运行时混算；资金流/筹码不强行塞到技术指标 |
| `get_risk_metrics` | 无独立已核风险公共binding；已有K线只构成输入候选 | Wind get_risk_metrics；金融MCP iFinD get_risk_indicators；本地风险计算方案 | 未核输入收益、基准与算法前不注册；供应商风险值与本地计算是不同合同版本，不能失败时无提示互换 |

补充限制：

- AlphaDesk 已有行情样例并不自动成为 RWB 取数中转；腾讯/东财与 AKShare 共用底源时仍须识别出处。
- “Wind”需区分Excel/MCP/Client API；“iFinD”需区分HTTP、SDK与金融聚合MCP；
  一个入口配置失败不能据此否定其他入口，反之一个成功也不能全品牌通过。
- 市场页的全市场宽度、资金与排行为专用路径，不能直接装进单股工具；
  筛选时使用这些数据须验证完整证券集合和时间一致性。
- 行业、公司档案等异构属性可以逐字段引用多个来源；同一K线序列仍严格同源，
  同一报表或同一风险计算输入也不得混合不同口径后伪装一个原件。

### 15.4 候选实现到目标目录的迁移

以下依据 complete 工作树的 task_contracts.py 读取，属于源码检查；
本轮没有重新验证其PR、合并或部署状态。它仍采用旧九工具命名。

| 原候选 | 目标股票工具 | 可以保留的部分 | 必须变更或补齐 |
| --- | --- | --- | --- |
| get_stock_kline / StockKline | get_stock_kline | daily/none、规范证券、截至昨日、原提交/status | 对照14节补覆盖/完整性用例；其他周期与复权保持未开放 |
| get_stock_quote / StockQuote（快照） | get_stock_price_indicators | assets/fields参数模型及market_snapshot链 | 改注册名、metadata、测试与说明；旧名是否已对宿主发布后决定迁移，不同职责不能直接覆盖 |
| 尚无对应分钟工具 | get_stock_quote（分钟） | 天软分时中的已有校验可评估复用 | 新参数/响应合同；先验证时间和增量/累计量额，不能沿用StockQuote |
| get_stock_financials / StockFinancials | get_stock_fundamentals | 四类dataset与报告期限制 | 改名；保留摘要/比率/报表不同形状，不统一伪造为完整三表 |
| get_stock_activity / StockActivity | get_stock_equity_holders | holder_data/holder_details分支 | 拆职责与参数白名单；限定报告期、持有人与股东字段字典 |
| get_stock_activity / StockActivity | get_stock_technicals的两融子集 | margin_trading分支 | 拆入口；不附带声称MACD、龙虎榜或风险已实现 |
| events 原Provider分支 | get_stock_events | 天软事件索引及日期验证 | 公共参数模型、事件类别映射、注册接线与权限测试 |
| 无对应工具 | search_stocks、get_stock_basicinfo、get_risk_metrics | 身份目录/已有输入可局部复用 | 筛选、完整档案、风险分别补合同，不用search_assets冒充选股 |

原StockActivity最新候选已不含block_trade；旧章节的大宗交易/筹码范围不能沿用为
已实现承诺。fund_flow是现有内部能力，目标股票十工具尚未指定独立承载方式，
本轮保留旧能力，不删除、不默认改名为事件或技术；需要时再明确是否增加扩展工具。

工具名迁移须先核宿主已发现的目录。若旧get_stock_quote已发布，不能一边让旧会话继续
用它查快照，一边无提示改成分钟：先更新宿主目录和调用说明，旧快照别名退出前
不占用同名分钟语义。此处是待实施迁移设计，本轮不改注册或审批记录。

### 15.5 逐工具验收缺口

| 工具 | 注册为可用前需补的证据/用例 |
| --- | --- |
| search_stocks | 条件字段/算子/单位字典、输入时间、筛选全域与分页；同名证券/空结果/无权字段；不得自行加条件 |
| get_stock_price_indicators | 同股每字段单位、时间精度与盘中/收盘标识；批量缺项；涨跌幅百分数与比例差；旧命名迁移 |
| get_stock_kline | 第14.6节；单位、原始价、量额、同源覆盖、换源、分段与分页读回 |
| get_stock_quote | 实际分钟时点、交易日/午休空段、乱序/重复、增量/累计量额、均价分母与昨收字典；K线不能充当分钟 |
| get_stock_basicinfo | 规范主体/上市日、行业体系、主营/工商字段实际覆盖与生效时间；仅目录字段不冒充完整档案 |
| get_stock_fundamentals | 原始报告期、披露时点、币种/倍率、累计/单季、集团/归母、修订版本；cash_flow比率不冒充金额表 |
| get_stock_equity_holders | 持股数量/比例尺度、排名、同名股东身份、报告期/披露日；汇总与明细一致性范围 |
| get_stock_events | 发生日/公告日/预告日分开、去重身份、事件分类、链接可追溯；覆盖窗口与正文缺失说明 |
| get_stock_technicals | 两融字段/单位；技术指标算法、预热窗口、交易日序列、价格复权与缺值；供应商值与本地值版本分开 |
| get_risk_metrics | 收益类型、交易日对齐、样本数、年化天数、无风险利率、基准、估计方法；方差为零/样本不足等确定行为 |

以上是新增规格，不是已执行测试。首轮实现顺序建议为 K线→快照命名迁移→股东/财务
拆分复用→分钟/事件→档案→筛选/技术/风险。顺序依据已有适配与契约缺口，不表示
必须等待十项完成才交付一项。按该顺序逐项补schema与真实样例，而不是给未实现工具注册占位。

### 15.6 本轮交付与后续动作

十工具的职责、来源对应、参数轮廓与验收缺口已列齐；K线沿第14节已有细化合同。
下一项可编码前的文档工作是股票快照：冻结字段白名单与各源逐字段/时间覆盖，
并核对旧quote目录的迁移时点。筛选算子、风险模型等尚未定义完，保持待设计。
本轮只追加讨论稿与阅读页，原实现候选、数据源清单现场和文档中心模板不变。

## 16. 股票快照逐字段来源与时间合同

目标工具为 stock_data.get_stock_price_indicators；它与目标 get_stock_quote 的分钟序列
职责分开。候选源码仍用旧 get_stock_quote / StockQuote 代表快照，改名尚未由本轮实施。
本节冻结首批字段及准入设计，不把所有 provider 原生返回拼成一张“实时行情表”。

### 16.1 依据与范围

本轮只读核对主清单、AlphaDesk 2026-11-16 补充、Wind 指标词典，以及 complete 工作树
`8c728630` 检查点附近的 task_contracts、Broker 和 Wind/天软/AKShare Provider。
来源表描述所读代码与文档，不是当前账号或最终合并版本实取验收。

首批继续沪深 A 股；输入 assets=1～20，fields 可省略，默认仅 price。
资产身份、request_id、原提交/status/OAuth 沿第15节。fields 明确传空数组、重复值、
未知字段或重复证券应在目标 schema 中拒绝；当前模型是否覆盖这些检查需实施核对。
字段排序不改变请求语义，规范化后生成幂等指纹；同一次请求始终读回同一冻结结果，
新报价需新 request_id，不能靠重复轮询让已完成快照变成实时流。

目标新增可选 `timing=latest_available|intraday`，默认 latest_available：

- latest_available：允许来源最新可得的日级或盘中观测，但必须显示真实时点和精度。
- intraday：要求上海当日、来源真实盘中时间戳及盘中报价合同，不能用日线日期或取得时间满足。
  它不承诺逐笔实时或固定秒级延迟；有此需求时再定义延迟合同。

timing 是为避免把“盘中”降级成“最近日线”的目标参数，当前旧StockQuote尚无此参数。
工具描述只能宣称 latest_available，直到 intraday 源完成接入和验收。
示例：`{"request_id":"snapshot-example-1","assets":["600519.SH"],"fields":["price","pe_ttm"],"timing":"latest_available"}`。

### 16.2 首批七字段与标准口径

| 公共字段 | 固定含义与单位 | 禁止的替代/推断 | 覆盖要求 |
| --- | --- | --- | --- |
| price | 不复权最新成交价或明确标注的最近收盘价，CNY/股 | 前复权日线close未经等价证明不作原始报价；指数点位/基金净值不混入 | 必需被请求时有限且正值；停牌状态与可得价日期分开 |
| change_pct | 相对来源同合同昨收的涨跌幅，百分数：1代表1% | 不与涨跌额、5分钟涨幅、比例0.01混用；不从不同源前收和现价计算 | 当来源明确该定义且字段有效才覆盖 |
| volume | 报价所属交易日截至来源时点的累计成交股数，股 | 手/万股需有证据换算；不是现量、最近一分钟量或可疑复权量 | 非负，注明日累计及所属交易日 |
| turnover | 同交易日截至来源时点的累计成交金额，CNY | 不是换手率；不以price×volume估算真实成交额 | 非负，金额倍率需核验 |
| pe_ttm | 明确TTM盈利口径的市盈率，倍 | 动态PE、LYR/预测PE不冒充；亏损时不擅自改成零 | 有效数字可为负；无意义/缺失值需标不可用，不编造 |
| pb | 首批定义为最新已披露财报口径的PB（LF），倍 | PBMRQ及其他净资产口径不自动等价 | Provider必须证明分母口径；仅有字段名pb不算证明 |
| total_shares | 总股本，股，保留实际生效/参考日 | 流通股本/自由流通份额/市值不替代；不以市值除现价反推 | 单位和股份类别核实，数值非负；时点与价格可不同但须分别注明 |

pb 的LF范围属于本轮目标口径，现有泛化pb模型未因此自动满足；如需PBMRQ，后续
明确新增字段，不扩写pb含义。market_cap、turnover_rate_pct、pcf_ocf_ttm、pb_mrq等
原生字段可以留原件，但本批七字段不顺手开放。沪深货币按已核来源确认，不按代码猜币种。

### 16.3 已有三个 Provider 的逐字段实际覆盖

下表“有值/有列”只指代码构造，仍需单位、口径与来源时间验证，不能单看列名准入。

| 字段 | Wind Excel / market_snapshot | 天软普通日线末条路径 | 天软估值路径 | AKShare 当前快照 |
| --- | --- | --- | --- | --- |
| price | 原close→price，schema声明CNY/股，as_of来自trade_date | 原close等字段原生保留；默认rate=forward，未有公共price归一及完整价格单位证据 | 用rate=不复权读取日close，返回close而非price；价格单位依据仍需复核 | 前复权日线末条close→price；目标原始报价等价未验 |
| change_pct | 当前快照schema无此输出，请求应退出候选 | 无已核公共映射 | 无此输出 | 构造为null，不覆盖 |
| volume | 当前快照无此输出 | 原vol，精确SDK/单股身份下字典给share | 无此输出 | 日线volume，代码标share；须核前复权路径是否调整量 |
| turnover | 不提供成交额；原turnover是换手率，映射turnover_rate_pct | 原amount单位元，公共金额归一仍需接线 | 无此输出 | 取日线amount，可能缺；不能因为输出键存在就承诺非空 |
| pe_ttm | 返回pe_ttm，schema为倍 | 不走此路径 | PETTM→pe_ttm，验证固定公式/说明 | pe_ttm为null；动态PE也未在此快照路径取得 |
| pb | 返回pb，但LF定义仍需来源证据 | 不走此路径 | PBLF→pb，和PBMRQ分开 | 不提供 |
| total_shares | 返回total_shares，schema为share，实际参考日另核 | 不走此路径 | 总股本因子；基本信息股本单位与同截止日股本结构一致才核实为share | 不提供 |

Wind 的请求翻译已有 price→close，并区分金额turnover与原生换手率turnover。
某些内部显式wind原生请求可继续使用原参数，但新公共工具永远按本节金额语义解释。
不能只改名或在模型说明中解释后继续返回混淆值。

天软路径由fields触发：请求pe_ttm/pb等估值字段时走structured_query；普通路径
则读最近14日日线后取最后返回行。估值路径核对日期后取最新日，二者实际返回形状不同。
普通路径的最后一行不自动等于最大日期，需在归一化验收中检查乱序。
估值路径代码中的价格单位判断使用vol/amount字典，量额字典本身不能单独证明
OHLC币种；目标价格合同须补足价格证据，不把该布尔判断当作完整厂商证明。

AKShare 当前快照逐股读取最近14日的新浪前复权日线，不是spot实时端点。
_normalize_snapshot在缺as_of时可能用取得时间回填；目标接口须将取得时间与行情时间
分开，不能用此回填证明数据新鲜。PB/总股本缺失、change_pct=null都不能通过重命名补齐。

### 16.4 主清单与补充来源的字段对照

| 入口 | 可核对的字段/能力 | 接入差距与时间限制 |
| --- | --- | --- |
| Wind MCP get_stock_price_indicators | price→最新成交价，change_pct→涨跌幅，volume→成交量/日成交量，turnover→成交额/日成交额，pe_ttm→市盈率(TTM)，pb→市净率(LF)，total_shares→总股本 | 本地白名单是字段名依据，不保证实际返回；交易日/交易时间、日累计定义、股本单位与币种须随实取核验；需新DataHub绑定 |
| iFinD QuantAPI real_time_quotation | 主清单已登记实时行情；基础/财务字段可能要独立函数 | 不假定一个函数覆盖全部七字段；指标字典、权限、响应单位、time/table对齐和逐字段时间待核 |
| 金融MCP iFinD stock_highfreq_quotes、岗底斯实时行情、DM | 发现目录表明存在行情入口 | K线binding成功不提升为快照binding；原生schema、累计/快照时间与字段逐项核对 |
| 东方财富市场页/公开行情 | 主清单有沪深北股票池、报价、量额等专用路径 | 可复用前须核身份、精确字段/倍率和时间；专用市场页不是已注册单股快照工具 |
| AlphaDesk东财报价 | 历史样例确认价格、涨幅、成交额和市值为数值 | 样例没有来源及行情时点字段，不覆盖目标intraday；市值不等于total_shares，不能反推 |
| AlphaDesk腾讯报价线索 | 私有清单有报价与观察名单路径 | 不将九指数样例认证为个股快照；逐字段、单位、时点和真实底层请求待核 |

这些入口属于后续适配候选，不将“理论七字段都有”写成已完成路由。
同一供应商经不同中转的样例仍保留底源身份，不按中转数增加独立来源数量。

### 16.5 时间、缺失与批量完整性

目标结果每股须有数据时间、时间精度、来源与取得时间；估值/股本实际参考日可不同，
需能逐字段追溯。新信息优先落在原manifest字段元数据/provider_metadata扩展，
实现时核定具体位置，不在本轮声称当前DTO已含全部字段。

| 数据情况 | latest_available | intraday |
| --- | --- | --- |
| 来源有上海当日真实盘中时间戳及受控延迟报价 | 返回并注明时间/延迟事实 | 满足时间准入，仍不宣称逐笔实时 |
| 只给最近交易日期的close或日线量额 | 可在价格原始口径等字段条件满足后返回，并标日级/最近可得 | 拒绝该候选，不能补当前时刻 |
| 只知道HTTP取得时间 | 可以保留原生证据，但目标标准快照不合格，需补数据时间 | 拒绝 |
| 停牌，保留上次成交价 | 有真实停牌证明、最近成交日才返回且明示停牌 | 不把上次成交价作为今日盘中成交价 |
| 已收盘、盘后/休市 | 保留来源明确状态与实际交易日；不能靠系统时钟推值 | 没有盘中观测则不满足，不能静默改成latest_available |

“字段被请求且来源支持”与“本次字段恰好缺值”分开：

- 未请求字段不因Provider返回而扩张公共结果；溯源/身份字段始终保留。
- price、change_pct、量额等请求字段缺失，不以0代替；标出证券+字段+原因。
- 估值可能因亏损或不适用缺失；保留原生原因，不能无限换源直到找到一个正数。
- 有明确不适用原因可作为带限制资料返回；请求字段未全部满足时不可宣称完整字段覆盖，
  原data_success/质量布尔的实际判据须在实现中接线核对，不能用completed代替。
- 批量1～20股每股都核身份与字段；一股失败必须列missing，不伪报整批齐全。
- 一个批次优先使用同一个Provider合同；天软若需逐股拆调用，时间允许不同但须逐股注明。
  单股禁止从A取价格、B取PE、C取股本拼成无逐字段来源的一行。

### 16.6 字段驱动的固定路由设计

沿用原market_snapshot候选顺序天软→Wind→AKShare作为起点，先按字段、时间和
原始价格口径过滤，任何跳过都说明原因。没有来源能满足时返回真实覆盖缺口，
不强行给每个组合安排一个必成功主源，也不以新快照规则改动旧运行工具。

| 请求组合 | 现有路径的判断 | 进入目标路由前的工作 |
| --- | --- | --- |
| latest_available + price | Wind投影最接近标准字段；天软有归一/价格依据缺口，AKShare有前复权等价缺口 | 来源逐项验收后才准入；不能因为仅一个字段就绕过时间/单位 |
| latest_available + pe_ttm/pb/total_shares | 天软估值、Wind有部分字段，但股本参考日/PB定义/批量能力各有限制 | 只在同源满足整个请求时选用；PB LF和股本单位证据缺失则退出或按明确缺失返回 |
| 任意组合含change_pct | 旧Wind快照不提供，旧AKShare明确null，天软两路径无已核归一 | 需接Wind MCP/iFinD/东财等合格快照或另验证同源昨收计算，当前不能承诺标准覆盖 |
| 任意组合含volume/turnover | Wind退出；天软原生vol/amount需标准化，AKShare为日线末条 | 不从换手率生成金额，不用最近一分钟代日累计；新增源先核字段单位与时间 |
| intraday任意组合 | 当前三个DataHub路径都没有足够证据保证目标盘中语义 | 目标参数定义但暂不启用；先接并验收至少一个真实盘中来源 |
| 多股含估值组合 | 原Broker跳过天软单股限制，Wind只覆盖其支持字段 | 先验Wind批量与字段完整；若设计为天软逐股计划须独立实现，不能说已有批量 |

结论是先改善现有字段合格子集，并为缺失的涨跌幅/盘中语义选择一个清单中有依据的
新来源适配。新源优先级须看实际权限、同样本时间/字段证据和成本后确定，
不在文档阶段凭品牌指定Wind MCP或iFinD必胜。

### 16.7 旧名迁移与实施验收

1. 先确认候选/已发布宿主目录中get_stock_quote的实际职责和使用情况。
2. 将快照模型/字段合同接到get_stock_price_indicators，更新MCP注册、metadata、说明和测试。
3. 旧快照quote若已经被使用，明确迁移窗口；同名分钟quote在旧调用退出前不直接占用。
4. timing仅在参数模型、Provider时间准入和结果元数据都实现后开放；先保持latest_available子集。
5. 按以下场景验收后刷新真实宿主目录，再逐源扩字段，不批量注册未验能力。

| 场景 | 必须观察的结果 |
| --- | --- |
| 默认fields与非法fields | 默认仅price；空/重复/未知字段和重复证券拒绝；未请求字段不悄悄加入 |
| Wind请求turnover或volume/change_pct | 退出不支持候选；原生换手率不返回为成交额 |
| Wind/天软PB与PBMRQ | LF口径证据核验，MRQ不会混入pb |
| 天软仅价与估值触发路径 | 原生close/date/vol及结构化输出正确归一；数据日期取最大合法日，时间/币种不靠量额推断 |
| AKShare前复权末条、缺as_of | 不自动认证原始实时报价；取得时刻不冒充行情时刻 |
| PE亏损、无估值、股本倍率/生效期变化 | 原因与参考日保留，缺值不填0，股本不从市值反算 |
| fields=[price,change_pct]但只price有值 | 明确字段缺口/质量限制，不以Provider执行结束宣布全字段成功 |
| 20股中一股无返回、单股需拆分来源 | 批量缺项可见；不合并不同源字段伪装同一快照；拆分时间逐股可追溯 |
| timing=intraday遇日级/昨天/无时间样例 | 候选不合格，不静默降级；当前未启用时参数直接按未支持处理 |
| 同request_id轮询/新request_id重查 | 前者原id/快照/时间不变，后者执行新查询且保留真实新时点 |
| 撤权、限流、失败换源、客户端未读完 | 原权限与预算生效、原件可追溯，缺字段或未读完不宣称完整 |

本轮只做源码/清单核对和设计写作，上表是待执行规格。
可执行下一步是先做快照模型命名迁移与字段检查，再选择并实测补齐盘中/涨跌幅的一条来源；
本轮没有供应商取数、业务代码修改或常驻更新。

## 17. 资产观察首条接入的源码候选

2026-11-25 用户授权资产观察联通新工具。实现于独立任务 asset-business-query-20261125，
基于 PR338 合并版本 d8be7c41；[PR341](https://github.com/Leon-Huang001208/ResearchWorkbench/pull/341)
候选已刷新为61e81cab（功能提交0e575bbd、21bb6d0c、41e8d677，合入文档主题主线ede76ea9）。
第二项功能补充主图history-jobs中的规范raw历史分段，保留原任务与因子/取消逻辑。
本节记录源码实现，新候选CI正在执行；旧候选Mac/Constraints通过不替代新候选，尚未部署。

实际调用链：

```text
资产观察普通history → 原资产API/AssetWorkspace ─┐
                                               ├→ DataHub stock_kline_query → 原query/Broker/仓库/Provider/冻结快照
模型get_stock_kline → 原MCP/账号Host ────────────┘
```

- 首条覆盖：stock/daily/none，截止日早于上海今日。共享构造函数固定规范raw语义。
- 主图history-jobs中已带规范raw语义的行情分段也共用该构造函数，保留source和refresh=True；其余任务输入不变。
- 页面保留裸代码身份解析、显式来源、refresh与观察状态；MCP仍只收规范代码和原参数。
- 资产侧保留SH/SZ厂商前缀解析；北交所前缀/后缀请求继续原路径，不受沪深共享合同缩减。
- raw历史懒加载继承观察来源，区间优先级为加载body→history区块范围→全局范围。
- 复权、周月、非股票、含当日请求、canonical历史任务与分时保留原路径。
- 页面不绕行MCP HTTP，不借外部OAuth grant读页面材料；两入口各沿原账号权限。

验证：前批381个相关pytest case执行退出0；审查修复后最终资产185项通过；
MCP参数原生unittest23项和相关JavaScript230项通过。独立审查的区块日期优先级与
裸代码兼容两项P2已修复并复核。一个pytest9 subTest批次的JUnit记录数校验失败
单列保留，实际测试退出0；未伪改为证据通过。测试使用合成供应商边界和真实DataHub/快照。

该PR没有实现第16节快照新字段/命名迁移，也没有新取真实供应商数据。
部署另需明确授权和维护窗口；文档中心的部署不会因此自动包含本候选。

最终补充：资产加载/观察110项、历史任务82项回归通过；源与CI增量均独立复核无发现。
明确的三文件桥接变化接入原MCP/DataHub定点CI范围，保留原全模块并加入完整资产三模块，
未知文件/缺锚点仍全量；三个必要CI保持，旧候选未完成Checks按替代取消，不作PASS。

