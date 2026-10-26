# 剩余57来源实际验证与研究仓证据

日期：2026-10-23。宿主：macOS；任务类型：功能开发中的来源验收与文档核对。本报告仅整理已经执行的请求、完整 Host 与独立 owned PostgreSQL 回执；文档审计没有新增网络、秘密读取、依赖、Git 操作或部署。Windows/Linux 原生验收保持 NOT_RUN，现有服务、PG5432 与外盘不动。

architecture-review: 本报告及台账只记录已有实现的实际证据；不增加架构节点，不把供应商原生快照当成规范跨源数据模型。完整源代码身份由成功回执中的七个源码 SHA-256 与 aggregate 绑定，不能只用 HEAD cc62 推定当时未提交源码内容。

## 57项核对结果

逐项状态、dataset、失败原因与原件 SHA-256 见同目录 `2026-10-23-datahub-source-verification.json` 的 `sources[*].current_observation`。旧 `old_static_snapshot`、历史证据及上次观测保留。剩余57项均已核对，因此 `not_rechecked_count=0`；这不表示57项都可取数。

| 分类 | 数量 | 实际边界 |
| --- | ---: | --- |
| 公开无凭据业务请求记录 | 35 | 29项公开样例与6项首轮宏观样例；含15次运输失败，不是35源业务成功；本轮未采购或执行付费调用，不承诺商业复用免费 |
| 未实现或无公开业务合同的候选（费用/权益未全核） | 9 | 目录、disabled、无Host provider或无端点；费用与权益未知，不从auth=none推断免费 |
| 账号/密钥/权益需求 | 10 | 未猜测秘密联网；Tushare用户明确无账号，优先免费来源；ZQ仅由父任务确认配置名存在，不证明权益或适配完成 |
| Windows终端/设备与实现边界 | 1 | ifind终端源；不混同ext_ths QuantAPI |
| 本地虚拟占位 | 1 | local_cache不是真实远程供应商 |
| 纯目录 | 1 | ext_registry本地目录不算业务数据 |

35项的第一次返回包括：15次运输失败；8项平面或嵌套数值候选；2项新闻内容、1项基金关联映射、1项日历；3项HTML页面/空壳；1项JS报价待解析；3项错误或空序列被包装为snapshot；1项CSV分隔符误解析。候选数据、HTML可读、HTTP成功、native保存与正式PIT分别判断。

### 费用与权益分类纠正

先前“9个免费原生来源/连接器未实现”和“35个免费外部来源”标签缺少逐源费用及商业权益证据，现作为历史分类保留在JSON history，不再沿用其免费结论。这次仅核对Catalog与旧静态快照，没有新增联网或结构审查之外的来源验证；既有请求、成功/失败、原件和哈希保持不变。`auth=none`说明认证声明，不能证明收费、许可或商业复用权益。

9个候选的旧 `old_static_snapshot` 均没有fee字段。当前Catalog对Yahoo、中证指数、深交所、巨潮、中国证券网快讯/新闻声明free，对ChinaStock声明unknown；Morningstar/TradingView没有endpoint，外部Catalog的free来自非秘密源的生成默认值。以上静态声明均不是本轮费用核验，各项实际费用、商业复用权益与账号权益现明确为unknown。

| 候选 | 当前目录声明 | 本轮费用/商业复用权益 |
| --- | --- | --- |
| yahoo | free | unknown/未核实 |
| chinastock | unknown | unknown/未核实 |
| csindex | free | unknown/未核实 |
| szse | free，来源disabled | unknown/未核实 |
| cninfo | free，来源disabled | unknown/未核实 |
| cnstock_flash | free，Host未实现 | unknown/未核实 |
| cnstock_news | free，Host未实现 | unknown/未核实 |
| ext_morningstar | 外部目录默认free，无endpoint | unknown/未核实 |
| ext_tradingview | 外部目录默认free，无endpoint | unknown/未核实 |

35项只称公开无凭据请求记录，未承诺所有商业复用免费；本轮没有采购或执行付费调用。local_cache仍为独立本地占位，ext_registry仍为独立目录。分类计数保持35+9+10+1+1+1=57。Tushare“优先免费来源”保留为用户目标，不用它倒推候选已经完成免费认证。此次报告纠正需由Root新提交并重新绑定适用CI，不伪用旧候选通过状态。

## 错误包装、补样与解析边界

- NASDAQ第一轮缺 `fromdate`，`status.rCode=400/data=null` 是请求样例不足，不能判源失效。第二轮补AAPL `2024-03-01` 一天区间后 `deadline`，仍未取得历史行。
- Danjuan第一轮将ETF `510050`用于指数估值namespace。纠正为 `000300` 后 `index_eva_pe_growths` 仍空，只有参考横线；不算估值历史成功，也不据此判源永久失效。
- CLS `hot-list` 的 `errno=10012` 为签名错误；通用parser第一轮误报snapshot。native CLS telegram使用不同接口和业务合同，不能替代hot-list验收。现有legacy静态sign未证明适用于hot-list。
- KAPSARC原始CSV使用分号；通用逗号parser将四列读为一列，不能称数值解析成功。专用修复与后续测试须另有证据，首轮失败不改写。
- Fed H41、Jin10、ETF.run等HTML仅证明取得页面文本。Tencent、MOEX、WGC等外层一行可能包含数百或上千个嵌套点，默认5行不等于5个业务观测，更不等于完整历史。

## 完整Host与独立研究仓

成功原件：`logs/numeric-host-real/receipt.json`。实际完整 Host 使用隔离临时配置和 owned PostgreSQL，验证以下 native first-observed 捕获：

| 来源/业务 | 行数 | 实际证明 |
| --- | ---: | --- |
| WorldBank通胀 | 2 | 真实请求、native保存、cache读回、冻结 |
| NYFed利率 | 6 | 真实请求、native保存、cache读回、冻结 |
| Treasury现金余额 | 4 | 真实请求、native保存、cache读回、冻结 |
| AKShare财务 | 1 | 真实财务执行、native保存、cache读回、冻结 |

四项 cache 均保持行相等，并且没有新增provider execution；数据库重启后版本相同，独立库恢复后冻结摘要相同，facts_after=4。owned PG停机并清理，配置环境清理；原件记录 `existing_port_5432_touched=false`。这只认证隔离环境，未部署或更新常驻服务。

`formal_backtest_eligible=false`、`historical_point_in_time=false`；原生快照保存第一次观测时间，不能推定历史发布时间、revision vintage或完整历史。快照含来源单位元数据，也不等于已建立财务/宏观/资金流通用规范投影。AK资金流第一轮为 `vendor_unreachable`，本报告不称资金流已入仓。

## 调用与失败证据

| 阶段 | 保留的实际结果 |
| --- | --- |
| 公开与首轮宏观 | 35个来源请求记录；另有AK财务成功1行、AK资金流失败，均保存原件 |
| 纠正样例 | NASDAQ与Danjuan各追加一次；分别deadline与请求序列为空 |
| 第一次完整Host proof | 因验证脚本分页limit=1000触发 `StoreError/invalid_resource`，失败；WorldBank已经发生一次HTTP200，必须保留，不能隐去 |
| 第二次完整Host proof | PASS；父进程计到3次直接上游HTTP，均200；另有真实AK financial provider execution_attempts=1 |
| 缓存、重启与恢复 | cache新增provider execution为0；数据库重启后相同版本和独立库恢复摘要验证通过 |

成功receipt中的 `sdk_invocations=0` 是父进程monkeypatch未穿透公共worker子进程的计数盲区，不表示没有SDK调用。真实AK财务以 `execution_attempts` 的一次成功为准，其底层HTTP次数为 `unmeasured`；不得把“3次直接HTTP”写成全部厂商网络调用总数。原始receipt不改写，台账明确记录计数限制。

第一次失败原件为 `logs/numeric-host-real/receipt-attempt1.json`；首轮目录为 `logs/remaining-public-probes`、`logs/first-numeric-probes`；纠正样例为 `logs/corrected-public-samples`。离线语义审核原件位于旧integration的 `logs/remaining57-static-audit/semantic-review.json`。台账将这些证据的绝对路径与SHA-256逐项绑定，不复制供应商正文、数值或任何秘密。

## 后续真实样例与失败补充

旧四case脚本只重启PostgreSQL，故“restart_same_versions”只认证数据库重启后版本相同，不认证Host/ResearchService重建。最新八case已经另行完成真实ResearchService重建验证；见下节，旧四case回执保持原样。

资金流完整Host原件 `logs/fundflow-host-real/receipt.json` 为FAILED、`cannot_freeze_empty_selection`，completed cases为空，SDK worker submission为1。首次执行失败且无行；随后display cache未命中，试图再次执行，被脚本一次SDK限额的 `sdk_request_rejected` 拒绝，最终冻结空选择失败。这个脚本不能证明第一次上游失败的具体原因；父进程直接HTTP计数0也不表示子进程SDK没有网络调用，底层HTTP未统计。

`logs/fundflow-host-real` 的四次direct guest诊断分别为默认、记录原响应、header、omitUT。均HTTP200但 `vendor_schema_invalid`；有envelope记录的三次为 `rc=100/data=null`，第一次只记录schema失败。所有诊断JSON与三份原始响应bin保留、不改写，不能称成功取得资金流或写入PG。

BLS另有一次官方v2 GET有界请求，`logs/bls-official-get/receipt.json` 记录 `ConnectTimeout`。[官方v2签名说明](https://www.bls.gov/developers/api_signature_v2.htm)仅作为GET合同引用，本报告没有联网读取或验证该页面，也不声称GET路径已成功修复。首轮POST403与这次超时分别保留。

中国宏观SDK真实raw sample见 `logs/china-macro-probes`：CPI225、GDP83、PMI225、货币供应225行，各一次SDK调用。原始厂商响应与标准化样例分开保留；`host_warehouse_verified=false`，历史release time和vintage未知。这些SDK raw sample本身不是完整Host、PG capture/cache或服务重建证据；最新八case中的有界区间已另取完整Host证据，不能反推全量SDK历史同样验收。

## 前一冻结源码的八case完整Host证据

`logs/final-numeric-host-real/receipt.json` 实际PASS，另有8份 `*-frozen.json`。本轮有界捕获WB2、NYFed6、Treasury4、AK财务1、CPI3、GDP1、PMI3、M2 3行，facts_after=8。各case保存、cache的rows/fields相同；PostgreSQL重启后版本相同；实际新建ResearchService后8项全部warehouse_hit，rows/fields摘要相同且没有新增vendor调用；独立空库恢复后的冻结摘要相同。

调用记账为3次父进程直接HTTP（均200）和5次owned public worker submissions；子进程底层HTTP没有分别统计，不能相加后宣称精确HTTP总量。模型调用0。socket-only owned PG清理与临时HOME删除均通过；现有PG5432不动。

该前一冻结回执记录 `source_unchanged=true`，绑定10个实际dirty-tree源码SHA-256及aggregate `d000de0f97ad7aab199ad2d553fc732ff162530957d99e173b7bea504022d155`。HEAD cc62并不独自证明这些未提交字节，最终候选CI为NOT_RUN。该回执的parser修复与最终源码绑定见下一节；旧错误样例不改写，NASDAQ超时或Danjuan空序列不得改为正向成功。正式PIT/回测资格仍为false，未部署。

## 最终冻结源码八case与公开parser样例

最终原件为 `logs/final-candidate-numeric-host-real/receipt.json` 与8份冻结导出。WB2、NYFed6、Treasury4、财务1、CPI3、GDP1、PMI3、M2 3均PASS；数据库重启版本相同，实际重建ResearchService后8项全部库命中且rows/fields摘要相同，额外vendor调用0；独立空库恢复摘要相同，facts_after=8。3次直接HTTP与5次owned public worker submissions分别记账，子进程底层HTTP仍未分别统计；model0、owned PG和临时HOME清理通过、source_unchanged=true。

两个源码aggregate范围不同，已逐路径验证相容：worker的 `logs/external-envelope-source-spec.json` 覆盖7个改动源，aggregate为 `f6ba79c554d11b5bd4a3ebcae30d67a44badadbdb50cff7adf7ab9f9bcd4793c`；Root最终Host回执覆盖10个源，aggregate为 `031489d891c3c83669e4389171e73a198638c2ed32eaa8a482c5737ea14e6465`。两者均为排序键、紧凑JSON map的UTF-8 SHA-256；worker全部7个path/hash逐项等于Root map子集，Root10个hash也与当前文件一致，不能直接要求两个不同清单aggregate相等。最终与前一八case清单有 `__init__.py/broker.py/providers_external.py` 三处源码差异，前一回执保留但不混用。

最终KAPSARC parser真实请求见 `logs/final-public-parser-real/ext_kapsarc.json` 与summary：5行正确拆为country/sub_commodity/year/production，值保持原字符串，单位unknown；provider_total=4128、partial/row_limit、pagination_complete=false，未入研究仓，非全历史认证。首轮单列误解析证据保留。

Nasdaq、CLS、Danjuan和KAPSARC的4份fixture均已与实际反例/空样例原响应逐字节哈希匹配。前三者仍没有正向业务成功：NASDAQ参数修正后超时、CLS hot-list签名拒绝、Danjuan指数000300仍空；不能把错误封包拒绝回归通过写成来源可用。KAPSARC只认证本次四列解析与有界样例。

这是最终dirty-tree源码哈希绑定；最终Git候选CI和部署仍待完成。Root已提供产品验证433 PASS/71 subtests及独立复核315 PASS/59的执行摘要；该摘要归Root执行，本文档审计没有代为运行或把它当作CI。未更改正式PIT=false，也不认证其他既有失败来源成功。

## 最新056b实际基线重跑与PIT元数据边界

最新实际执行HEAD为 `056b030507beb5a4b30cab0b53a28cbaa4364e5f`。`logs/latest-base-real-056b/numeric/receipt.json` 及8份冻结导出重新验证WB2、NYFed6、Treasury4、财务1、CPI3、GDP1、PMI3、M2 3；独立临时PG持久化、跨会话cache、新建Host、数据库重启、独立空库恢复均PASS。计数为3次直接HTTP和5次worker submissions，子进程底层HTTP未分别统计，model0，清理及source_unchanged通过。

7个改动源aggregate仍为 `f6ba79c554d11b5bd4a3ebcae30d67a44badadbdb50cff7adf7ab9f9bcd4793c`；新base的market_service改变使10源aggregate为 `0396b9e59dac1f8d1233a333ef67b16cfa2ef33fe01299d7d8d008769b511873`。新基线已实际重跑，不能直接拿旧10源回执替代；原87份公开源证据及旧hash保持不变。

`logs/latest-base-real-056b/ifind/receipt.json` 与冻结导出另行验证iFinD现有 `external_data/ext_ths/basic_data_service` 的 `ths_net_inflow_amt_stock`：本轮又取得1个非空有限cell，独立PG/cache/新Host/数据库重启/恢复PASS，另1次业务HTTP、0 token exchange、0 SDK、0 model，批准凭据文件metadata未变，临时PG与HOME清理通过。此前 `logs/ifind-fundflow-host-real` 的proof另有一次业务HTTP和1cell；这两次须分别计数，不把全部阶段说成只取过1cell。licensed业务数值仅保留ignored本地原件，Git报告不复制数值或token文件引用。

该THS字段单位未知，订单分类未与东财校准；没有规范 `market_activity` 适配或自动等价降级，不给正式PIT资格。原生快照仍为first_observed，发布时间和vintage未知。

`logs/ifind-followup` 的sanitized元数据按path/hash追加：policy为free、basicData月配额600000 cells，EDB unavailable；这是该接口policy范围，非所有能力免费/可用的推断。净利润PIT映射exist=true，但PIT参数查询为UNVERIFIED/RuntimeError，没有取得PIT数值，不得猜普通模板，也不得宣称账号没有PIT权限。报告没有引用或读取token文件内容。

用户明确没有FRED/ALFRED密钥，继续优先无新增凭据的免费路径。ext_fred保留此前timeout和源码状态；无密钥不证明所有公开FRED路径不可用，本次文档更新未新增请求。

Root最新本机执行摘要为Python512 PASS/71 subtests、JS264 PASS及本机门通过，审计角色未代为运行。旧d696三项CI通过只属于旧候选；新056b CI进行中。此次报告更正提交后仍需绑定最终适用CI，不能提前标最终CI或部署PASS。

## 本报告核验与未完成事项

本次文档核验PASS：JSON可解析、64个source_id唯一；64份旧静态快照与历史evidence前缀保持不变；原剩余57份观测完整保留并追加本轮状态；35+9+10+1+1+1计数相符；四个ownedPG case与原件一致；初轮42个新增证据原件SHA-256逐项相符；后续20个失败/SDK证据及9个最新八case证据另按台账哈希核对，初轮加补充共71个新增原件；最终候选/公开parser/fixture追加16个后为87个；本次056b又追加20个，本轮累计107个原件。文档审计角色没有运行产品测试、CI、浏览器、部署或其他平台验收；Root产品测试摘要在上节单独归属，不代表本审计角色执行。

需继续分别处理：缺失provider/账号与终端设备；失败或受限来源的合法业务参数/授权合同；HTML/JS/嵌套表/分号CSV专用适配；资金流真实成功与研究仓证据；全部必需本机与同候选CI。当前结论是部分来源和四类native捕获获得真实证据，全部来源可用性、正式PIT与跨平台发布就绪仍未成立。
