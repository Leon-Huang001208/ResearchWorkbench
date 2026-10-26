# 华安 ETF 周报数据合同

股票分钟K保留原始字段字典/因子/时间证据，不扩展ETF周报数据集或历史PIT准入；分钟与日线频率分开，不把分钟派生快照自动冻结为正式报告证据。

股票分钟合约不进入ETF周报清单，也不授予周报正式/PIT资格；原宏观和Excel来源口径不变。

新CJPY snapshot字段合同只覆盖经核实沪深股票日K原生vol股、amount元，不猜价格币种，不将单位推广至ETF/指数/债券/期货或周报工作簿，既有冻结合同/owner/purpose门保持。

Wind 清理故障的运行见证不替代数据快照：Future 结束不证明 Excel 清理完成、行情齐备或交易日历正确。只读恢复准备既不重采也不沿用旧值生成新快照；API 延期、Excel 原件与必需数据门均保持，旧 Host 缺证仍阻断。

专属准入只消费已通过的同Run冻结快照、上下文与Host工作簿投影；恢复不得重取数据或改写原采集/冻结时间。已完成数据门与模型受理不同：旧账本缺阶段证据仍unknown，不能用数据passed证明模型未调用。用户明确的新版本是新一次真实采集，原快照及失败证据保留；价格、日历、历史、经济事件合同不变。

历史验收只有Host冻结的Run用途能进入事后采集分支；Provider仍记录historical_recheck及实际开始/冻结时间，Host仍独立核验原件、57必需序列、交易日历/完成收盘、单位/币种/端点、长期补点及下周经济日历。普通评估默认formal并拒绝历史快照，不能通过模型或snapshot字段开启验收。历史数据通过仅说明该验收输入合格，不授予正式定稿、实时快照或历史PIT认证；源采集主因应先于空快照次级错误报告。

今日发现的golddata_intel归档只证明选中事件响应在冻结时的字节，不是周报Wind同源API、Excel等价或57必需序列的来源。它不变更私有collect_report_weekly、主管理员及Dataset/报告期核验；上游陈旧、未知日期或缺原始披露继续作为缺口，不能用于取消原blocked_data/unverified。新归档机制见[今日发现](research-web-discovery.md)。

SPDR GLD净资产、持金重量和总份额按独立来源及各自日期保存；原单位标签和精确小数字符串保留。
四项首次观测快照没有历史披露/修订链，也未获本周报逐指标等价认证；既有私有数据、Wind/Excel优先级及正式回测门保持。

终端v2新增的新浪价格指数日线和六维证据只服务市场画像，不自动切换周报数据源，也不替代Wind/Excel逐指标同源校准。真实首次观察元数据不认证历史PIT、收益回测或已有ETF模拟准入。

2026-10-23公开宏观封包与AK财务/宏观原生捕获不自动满足本周报字段合同。CPI指数、增长字段及累计GDP分别保留来源口径；未知单位、首次观测或缺历史vintage不能替代同源指标校准。公开来源的错误封包拒绝和缓存合同升级不改变本合同的Wind权限、日期锚点、Excel保底或真实数据验收。

2026-10-23：市场上一交易日逐股金额与东财订单资金日线不替代华安周报Wind数据、同源等价校准或正式历史时点；公开资金缺口不补造，不改变私有collector。 具体来源、缺口与缓存合同见[DataHub](research-web-datahub.md#无会话全市场数据)。

本轮chip_turnover是个股专用封闭32日期因子输入，与周报私有Wind数据配方分离。资产的同复权VWAP、OHLCV估算、显示万/亿与筹码龄不提供本周报PIT、历史权重、同源等价或汇率证据；原数据合同与真实预检门保持。

2026-10-23公开indices仓库桥保留本合同全部私有Wind边界：市场页12指数原生响应与周报采集无互换承诺，首次观测时间不补造周报历史发布时间、单位/市场日历或来源等价。未改私有collector、权限、SDK调用与真实周期验收；不把公开缓存命中提升为周报data_success。

研究仓并行整合保留 `collect_report_weekly` 的受信私有入口、Wind Client API 源等价校准和真实 Future 排空边界。通用 `BusinessQuery` 的用途/历史时点约束及 MarketStore 冻结只约束其自身查询；provider-native 快照的首次观测时间不补造本周报的历史发布、跨市场交易日历或经济日历。连接中心的短期实际调用证据按能力与配置隔离，不认证周报整组数据；仓库/会话缓存命中也不刷新上游可用证明。缺少同源对照、单位或日期合同仍保持 `blocked_data`。

全市场访客行情补取只写当前用户MarketService缓存，停牌参考价、未上市和零成交额按来源分别标记；不替代本周报的私有Wind API、精确字段校准和同源对账，也不新增周报外部查询授权。市场实采与周报数据准入各自验收。

2026-10-22资产集成边界复核：DataHub新增的无会话A股目录只核验当前账号`search_assets/tinysoft`授权，固定表／预定义因子及dataset感知选源只服务资产观察请求；它们不调用或放宽私有`collect_report_weekly`、受信Report Run身份与WindPy同源读取合同。目录授权指纹、资产快照和全历史`as_of`不能替代周报的连接身份、固定映射、报告期、Dataset哈希及API／Excel等价证明；resident目录租约等待真实Future排空也不认证任何供应商字段覆盖。原周报的`unverified`／`blocked_data`及未运行项继续由本页证据决定，A股财务、股东或公告预检不提升为ETF周报数据验收。

本模块用于主管理员周报试点，沿用 DataHub、报告 Workflow 和唯一 DSH 执行链。
它不是新的行情数据库、研究引擎或公开 DSH 工具。

## 数据与报告期

`report_workflows/huaan_weekly_mapping.json` 冻结旧项目实际工作簿公式和 EDB 元数据，
并保存原配置及三份底稿的 SHA-256。57 个必需序列包括五个境内指数、中证全指成交额、
31 个申万行业、12 个海外指数、两种黄金、两种原油和四个长期 EDB 序列。
另有下周经济日历合同。不存在按“ETF”名称推定的基金份额、持仓或估值需求。

`build_weekly_data_contract` 将请求时间锚定到不晚于请求的最近周五 15:30，时区为
Asia/Shanghai。提前手动试跑得到上一期，不能提前冻结未来行情。截止时间、报告期、
下周日历区间、映射哈希和一交易日滞后上限共同形成不可变合同。

`assess_weekly_snapshot` 只接受 Host 取得并验证过原始来源的标准化序列。交易日历须
显式给出交易日期、已结束交易日和各日实际收盘时间；不把工作日当作交易日，也不把
抓取时间当作海外收盘时间。周收益从前一周最后交易日与本期实际端点独立复算，
成交日均使用本期和上期实际交易日数。计算使用 96 位 Decimal，输出十进制字符串，
并保留原始逐日金额、端点、日期和来源哈希。长历史不允许截断或填补假日价格。

黄金 EDB 分别为 S0270980、S0035819，原油连续结算价为 S0031525、M0000005。
现货、连续合约、收盘和结算的身份不能互换。来源日期、单位、币种或原始数据缺失会
返回 `blocked_data`；模型的质量状态和缓存单元格总数不能消除这些问题。

固定映射 `kind=edb` 的长历史按原生观测日期保留数据：已结束交易日上限之前的非市场日
记录不会因不在 TDAYS 内而被丢弃或改写。上限仍是该市场 `completed_dates` 的最后一天，
当前未结束／未来日期不因此取得资格。额外观测不加入交易日历，不参与市场周收益或成交天数。
只有固定 `S0031525/ICE`、`M0000005/NYMEX` 的 `continuous_settlement` 历史允许有限负值
（例如 WTI 2020-04-20 原生负结算）；黄金、指数和其他行情的负值仍拒绝。
Provider 与 Host 使用同一日期／负值域判定；NaN、无穷值与布尔值仍拒绝，零／空值不变为
有效价格，也不补必需历史缺口。原生文件和哈希保留，日志分别汇总非交易日观测与负结算条数。
Host 原 `expected market sessions` 历史完整性门不变：S0270980 若缺2017-01-30，仍为
`weekly_history_incomplete`，除以下固定单点补查外不能用额外日、旧缓存或其他品种补齐。

## Excel 主来源（显式继任版本）

`WeeklyProductionPolicy.data_source` 默认仍为 `wind_client_api`，保留历史已发布版本与未来
API 迁移路径；准备操作只创建未发布的 `wind_excel` 继任版本。Run、生产上下文与幂等身份
冻结来源、版本和来源资源哈希。当前发布版本、主管理员归属、Wind allowed/configured、
凭据存储和取数前后配置摘要继续校验，不能从模型或公开工具参数选择本私有路径。

Excel 模式不导入 WindPy，不要求 API 权益、WSET 配置或 API/Excel 等价校准。依赖检查只
说明 xlwings 可发现，不能证明 Excel、Wind 登录或业务数据成功。schema2 的工作表 WSD 与 TDAYS
显式使用每个市场已审 `TradingCalendar`，每段最多366自然日，防止1000行助手区域截断。
私有采集对每个 TDAYS 请求按自然日窗口传入行数、1列，对普通单字段 WSD 按自然日窗口
传入行数、2列；印度按该段官方已结束交易日的完整列表传入行数。实际读取保留额外1行和
1列溢出哨兵，`0`／`False` 也算占用，超界直接阻断而不截取成可用结果。原始请求只写
一次；预清理、写入、读取、清理和关闭分别记录安全请求哈希及范围，未知结果仍不重发。
自有助手范围在 Mac 直接使用 `range.api.clear_contents()` 原生清空命令，不查询范围形状、
不切换应用全局 `screen_updating`；其他平台使用 xlwings 标准 `clear_contents()`。
本机原生对照已证实 `raw_value=None` 保留原数字，因此不能用于清理；旧值若留在溢出
哨兵仍须阻断。此离线修复不证明完整57项取数成功，也不放宽 Host 的日期与质量复算。
schema3 仅给印度 `IN/SENSEX.BO` 增加下述显式交易所日历；其余12市场保持原路径。
工作表 WSD 的每个选项必须是独立字符串参数。配置中的分号 `options` 只是内部表示，
由共享 `build_wsd_formula` 拆成 `...,"Period=D","PriceAdj=U","Days=Trading","Fill=Blank","TradingCalendar=TSE")`。
不能把 SDK 的单个分号选项字符串直接作为 Excel 第五参数；Mac 原生插件可能忽略该组合并
退回默认日期轴。私有 collector 记录并执行同一个真实公式，保持单次调用，不改 API SDK 语法。
每次工作表请求只执行一次；未知、超时和取消不得自动重放。与普通 Wind Provider 共用单线程
和 Future 容量；私有周报默认显式使用 `isolated_workbook=True, existing_app_only=True`，只在
既有可连接 Excel 实例中新建本任务拥有的临时工作簿，不启动或退出用户实例，不修改既有
工作簿或用户应用设置。真实供应商操作及自有工作簿 close 完成后才释放；close 失败将容量
标记为不可继续使用。执行持有现有常驻维护准入，普通 Wind 入口的选择策略保持不变。

长期 EDB 使用用户显式冻结的 Wind 原生数值导出，不把失败刷新称为成功。已发布资源的
schema2 来源合同包含 `data_source=wind_excel`、`excel_exports` 和全部已审市场收盘定义。
`verification.evidence_path/evidence_sha256` 必须绑定同版本不可变审查资源；经济日历配置为
`method=wind_excel_export` 和显式 `importance_values`。原生“重要/中等/低”分别映射为
“重要/较重要/一般”，不猜测 WSET。`excel_exports.edb` 声明 `path`、`sha256`、`exported_at`
和 `sheet`；经济日历另声明 `coverage_start/end`、`coverage_evidence_path/sha256`、
`observation_path/sha256`，并可通过
`additional_sheets` 保留“财经大事”。事件保留原始页名。静态导出时间与原生零结果观察时间
均须位于截止前一天至冻结截止点之间；当前时间已经更晚也不能追认历史截止点之后取得的输入。
文件须匹配同版本哈希。读取有ZIP大小及行列上限，并处理 Wind 导出的错误A1维度。
经济数据使用原生八列表头，财经大事使用五列（或同结构八列），各页均须保留 Wind 来源标记。
经济事件投影同时保留原始 `time/previous/forecast/actual`：对应原生第2、6、7、8列，
仅接受原样字符串、整数及有限浮点数，整数或浮点零均保留。缺列、空单元和空字符串为
`null`；不猜测单位、不补值、不改时区。布尔、非有限数、容器及原生 `datetime.time`
等未审类型明确返回 `weekly_excel_economic_value_invalid`，沿现有采集阻断日志留证。
此投影保持日期、国家/地区、指标、重要性、原页名与事件顺序；Word母版经济表仍为原有
日期／国家地区／指标三列，八列数据底稿不扩写Word版式。

### 印度 BSE 显式日历（schema3）

schema3 保留 schema2 的 Excel 来源、全部导出与 `verification` 审查资源合同；只允许
`calendars.IN` 显式选择 `calendar_source=exchange_calendar`。该项精确字段为
`calendar_source/semantics_verified/market/asset/timezone/close_time/completion_basis/evidence_path/evidence_sha256`，
身份固定 `IN`、`SENSEX.BO`、`Asia/Kolkata`，`completion_basis=full_session_end`。
不会把 Wind `BSE`（北京）或 `NSE`（日本）猜作印度，也不以别的证券替代 SENSEX。

`evidence_path` 是当前版本真实发布资源内的规范化 JSON，精确字段为
`schema_version:1/calendar_source/market/asset/timezone/completion_basis/coverage_start/coverage_end/observed_at/native_sources/days`。
覆盖须包含本次 `window_start` 至 `period_end`，同一年度且最多63个自然日，每日恰有一行
`{date,status,close_at,reason}`；`status` 为 `open|closed`，`reason` 为
`regular|holiday|weekend`。闭市日 `close_at=null`；开市日为该日有时区的完整收盘时间。
不接受遗漏日期、乱序、重复、范围不足或从价格行反推的交易日。

`native_sources` 恰含 `holidays` 与 `hours`，每项具有
`path/sha256/publisher/notice/source_url/published_on`；`hours` 另有 `effective_from`。
`published_on` 只记录公告原生日期，不虚构发布时间；`observed_at` 是操作员实际观察的有时区
时间，可晚于市场截止，但须不晚于 Host 本次实际采集和当前时间。公告日期不能晚于市场截止
日或观察日。规范化文件与两份原生 PDF 都必须存在于同版本不可变 manifest，Host 按实际
字节重算哈希并直接用既有 `pdfplumber` 提取原文，独立核对 BSE 署名、公告编号、日期、年度
和休市日。只提供一份自填日期名单、模型伪造路径、原文与每日状态冲突均阻断。
镜像的 `source_url` 如实保留镜像地址，不把券商托管的 BSE 署名文件标成 BSE 官方域名。

当前有界 hours 解析仅接受 BSE `20260610-41` 官方 PDF、2026-06-10 公告日期及
2026-08-03 生效原文，核对 `Post closing session shall be from 3:50pm to 4:00pm.`。
由此确定 `close_time=16:00`、`full_session_end`；这是全交易时段结束的保守完成口径，
不宣称16:00是指数定价时刻，也不改变 Wind `SENSEX.BO/close` 字段。
生效前覆盖、旧2025年规则、擅用15:30或15:35以及不匹配的官方URI均拒绝。
其他年度、特殊周末开市或新 hours 通知需要另行审查和实现，不能静默推广本合同。
特殊开市说明按有界句子上下文核对，规范化 PDF 跨行空白后识别月份、日期及 may/will/shall
说明；当前覆盖内或无法解析日期的特殊开市明确阻断，只有已解析日期全部位于覆盖外才放行。
不支持的序数日期、待公布或超出有界上下文的日期同样保持未知，不借用相邻表格、公告日期或下一句。
原生段落空白保留；仅完整的纯 `Timings of Muhurat Trading shall be notified subsequently.`
可继承紧前同段有明确日期的 Muhurat 开市句，总长须不超过512字符。独立、断段、插入无关句或
前句日期未知时均拒绝；这不会把“时间待通知”解释为另一个无日期的开市日。

Host 用核验后的每日收盘时间计算 `completed_dates`，查询上界为最后一个已结束交易日。
仅把这些日期分成连续自然日区间（最多64段），每段 WSD 显式
`Period=D;PriceAdj=U;Days=Alldays;Fill=Blank`，不传未知印度 `TradingCalendar`，
不请求周末／官方休市日，不过滤或制造返回价格；意外日期的非零观测仍拒绝。
每段返回日期列表必须与官方已结束交易日的该段完整、有序列表逐项相等；空段、缺首尾／中间日、
重复或乱序立即阻断并停止后续分段，不等到周收益端点门才发现缺口。实际公式、预期日期、
原始返回行及原生证据哈希保留在失败序列的 raw 证据中，规范化价格行保持为空。
印度公式形如 `=wsd("SENSEX.BO","close","2026-10-05","2026-10-09","Period=D","PriceAdj=U","Days=Alldays","Fill=Blank")`，
各选项独立传递；不增加 `IDC` 或其他未经本合同选择的日历作为兜底。
日历快照和印度行情显式保留 `calendar_source=exchange_calendar`、原生证据路径和哈希，
原始请求参数／返回行继续归档，Host 原有交易日、数值、日期和新鲜度质量门继续独立复算。
这只支持明确审查的本期覆盖，不认证全年日历、真实 Wind 结果或正式稿；定时始终关闭。

### 伦敦金单点历史补查（schema4，仅2026-10-23试点）

schema4 严格继承 schema3 的 Excel 来源与印度日历合同，只增加
`history_supplement:{path,sha256}`，绑定同版本不可变 JSON。该资源仅适用
`history_gold_london` 的原 EDB `S0270980` 在2017-01-30的唯一空单元；不成为通用补缺
或其他报告期的入口。当前资源与代码均固定报告期2026-10-23、历史覆盖截止2026-10-22；
下一周须重新审查来源和实采，不能复用旧 proof 认证新周期。原导出 XLSX 及其哈希保持
不变，来源 lineage 单列原 EDB 哈希、
补查资源路径／哈希、日期、数值与2534个重叠点计数。

Host 从资源重新解析原 EDB、10段 `SPTAUUSDOZ.IDC/close` WSD、10段 IDC TDAYS 和
2017-01-30 同公式单点重查。每段保留原公式与原始返回行；日历和 WSD 日期逐项一致，
重叠价格逐项按 Decimal 精确相等，单点值为1191.27。原 EDB 其他价格及两个非交易日
观测继续保留；第二处必需交易日空／零、替换原价格、日期或单位不符、重复／缺失、公式
或哈希改变均阻断。
原 EDB 在本报告期内晚于最后已收盘日的非空值沿原 Provider 硬门拒绝；空、零可以跳过，
布尔值仍拒绝，同一未来日期即使两条均为空／零也按重复日期拒绝。报告期之后的行仍遵循
旧 Provider 的日期筛选，不借补查扩大拒绝范围。
Wind 原生导出的单独末尾“数据来源：Wind”尾注不是观测行。Host 对快照独立重放来源合同与
四组原始资源；先检查工作簿成员、累计解压大小及行列预算，再扫描原始 worksheet XML
拒绝公式。快照删除／改写 lineage 或价格仍返回 `blocked_data`；无 Run 上下文时不能
凭快照自报通过。schema1–3 与 API 旧语义不受此补查影响，原历史完整性及正式定稿门不变。

`observation_path` 指向操作员从原生 UI 捕获并审查的不可变 JSON，不由模型填写。其固定字段为
`schema_version:1, source:wind_excel, kind:native_export_observation`、实际 `application/source_url`、
`export_path/export_sha256`、原生 UI 的 `coverage_start/end`、`observed_at` 及 `pages`。
`pages` 必须恰含 `economic_data`、`financial_events`；各页含 `sheet`、`result:exported|empty`、
`filters`、`message`、`raw_accessibility_excerpt`。过滤须为全国家、全部事件和三档重要性，
原始 AX 文字须显示对应页名、起止日期及全部过滤状态。非空页绑定本导出实际工作表；空页
须有原生明确零结果文字，且不能与工作表中的事件冲突。观察须不晚于市场截止点。
原生标签 `选择国家: 全部`、`数据/事件: 全部`、`重要性: 重要 中等 低` 直接支持，不能为适配
验证器而改写原始 AX 文字。

EDB 列按原始4个指标ID与单位核对，忽略派生 `s1` 列；超过最后已结束交易日的非空值拒绝，
假日空值/零值不变成有效价格，也不补齐实际交易日缺口。旧底稿中的周收益、周均与固定除五
不能替代这些原始逐日数据。数据仍通过原 `assess_weekly_snapshot`，再投影原三份工作簿与图表。

经济覆盖证明JSON为 `{schema_version:1, source:"wind_excel", windows:[...]}`，每窗具有
`start/end/resource/sha256/kind`；窗口并集必须覆盖下周一到周日，每份证据均为同版本不可变
资源。`native_export` 指向实际原生导出；`native_empty_result` 须含原生应用/URL、同一日、
有时区观察时间、全国家/全部事件/三档重要性过滤和两页明确零结果及原始可访问性文字。
原生导出窗口只接受本合同经济导出的精确路径与哈希，并精确匹配原生 UI 观察的实际起止范围；
只有 XLSX 哈希或人工填写的整周范围不能证明覆盖。每条原生事件
须属于该导出已审窗口。窗口可以跨入前周日，最终表格只投影下周一至周日的事件。
不能由表格最小/最大行日期或单个 `coverage_verified` 标记推断周日覆盖。缺失、过期、单位、
日历或覆盖证据错误均保留 `blocked_data`，不进入正式定稿。

市场 `cutoff` 仍为本期周五15:30；在线采集实际开始和完成冻结由 Host 时钟记录为
`acquisition_started_at`、`frozen_at`，随 `collection_policy=wind-excel-weekly-v1`、
`acquisition_kind=current_period` 一起进入快照哈希。仅报告期结束日当天、市场截止点之后的
实时生产可正式通过；Host 独立复算开始不晚于冻结、冻结不晚于真实当前时间，以及各序列和
日历的实际取回时间位于采集窗口内。已有原始冻结快照可以复读；对过去报告期新发在线查询
标为 `historical_recheck` 并阻断正式定稿，不能补写成当时快照。周报事实证据显示市场截止、
实际采集开始与实际冻结时间。Excel 仍依赖每期人工准备，当前禁止启用定时。

## Client API 与授权

`WindClientAPIProvider` 仅在受理调用时惰性导入已安装的 WindPy，不安装 SDK、启动
Excel、登录、接收任意模块或终止用户已有 Wind 会话。封闭序列请求使用已审映射的
WSD 或 EDB 参数，并保留原始响应、请求及哈希。SDK 数值、身份、日期、大小和字段均
受检查；超时或取消之后，真实同步 Future 返回前继续占有唯一容量。

目前本机 SDK 权限与实际取数尚未得到验证。冻结资源中的跨市场日历及收盘定义仍为
`unverified`，经济日历没有已确认的 API 数据集；默认明确阻断，不猜测 WSET 名称。
单次序列查询可用于后续受控同源对照，但不能由“可导入”推导为已具备周报覆盖。

`DataHub.collect_report_weekly` 是私有 Host 入口，不注册到 `BUSINESS_TOOLS`。
Broker 先检查现有 Wind 配置、允许状态及健康，再执行现有任务准入。已发布华安版本
显式启用 `weekly_production.policy_id=huaan-etf-weekly-v1` 时，collector 须先完成可信
Run 身份与来源资源哈希验证，才由 Host 导出内部 API 选择标记；它不修改全局 Wind
首选适配器，原资产观察仍可继续使用 Excel。没有该受信报告合同的直接调用仍要求
全局显式选择 `preferred_adapter=client_api`。内部标记不进入 HTTP 或 DSH 参数。
原 Excel 适配器的失败探测不作为这条受审 API 路径的健康结论；API 自行检查 SDK
连接和真实供应商响应。来源被禁用、未配置或凭据存储不可用仍然拒绝，不能因报告
选用了 API 绕过全局来源授权。
取数前后复查配置身份，复用会话归属、不可变快照和调用回执。
未决、失败或取消的调用不会自动重发；成功回执仍区分完整输入与不完整输入。

同源对照材料只接受本会话已保存、哈希核验的 Dataset 引用。API/Excel 的实际输入
重新比较，不采信外部 `passed` 标记。`merge_weekly_sources` 逐组替换：只有整组身份、
日期、单位和数值符合对照容差时才采用 API，其余组保留 Excel，原底稿不被改写。

首次校准可由 `register_report_weekly_inputs` 从当前 Run 的实际三份工作簿注册私有
Excel Dataset。主数据及图表底稿必须分别有匹配输出哈希的 Wind 刷新清单，主表缓存
日期必须匹配本期；不能把手工 JSON 或尚未刷新的图表当成同源对照。
Host 生成的等价证据保存在私有控制目录，绑定映射、连接配置、SDK 模块身份和来源
合同。后续周期重读证明中的真实旧输入并重新比较，检查绑定未变后只验本期 API
新鲜度，不要求每期再刷新 Excel。任何配置或定义变化都会使证明失效。
等价身份还绑定受审适配器语义版本及适配器、周报计算、Excel 读取实现的实际源码
SHA-256；仅修改 WSD 选项或归一化也会使旧证明失效。

首次校准的 `prepare_excel` 回调只在 API 已取得完整、可独立检查的输入而仅缺等价
证明时执行；SDK、登录、权限、交易日历或必需字段失败时不启动 Office。回调先用
`freeze_weekly_workbook_dates` 将主数据与行业图的 Run 日期固定到报告期，再走原有
受控刷新与刷新清单。旧目录或母版不被改写。

collector 实际调用 `adopt_verified_groups`：已获证明的组采用 API；未获证明的组
只有在本期已刷新 Excel 提供足够逐日原始数据时才明确保留 Excel，例如原图表中的
长期 EDB 序列。只有周收益/均值的缓存不能冒充逐日原始数据，不足仍阻断。快照的
`source_groups` 分别记录 API 与 Excel，部分迁移不能显示为全量去掉 Excel。

已核实的日历和经济日历通过已发布版本资源
`mappings/huaan-weekly-source-contract.json` 接入。资源须匹配 manifest 哈希，包含
审查证据哈希、全部市场的固定 Wind 日历标识、时区、收盘规则及半日市例外，和
经济日历的固定 WSET 数据集、日期参数与精确字段映射。私有 collector 只从属于当前
会话的 Run 副本读取此配置；没有配置时继续阻断，不赋予模型任意 WSET 查询权限。

## Office 投影与版本绑定

`materialize_weekly_workbooks(snapshot, run_root, manifest)` 先重新评估数据，核对 Run 中
已保存的 `snapshots/report-data.json` 与传入正文一致，再只修改三个工作簿副本。
通过 OOXML 局部更新保留样式和其余包部件；冻结日期和行情，更新申万、黄金、原油
图表数据及缓存、动态历史范围和下周日历，不让 Word 使用旧的图表缓存。

返回的 `snapshot_sha256` 绑定实际 JSON 文件字节，`snapshot_content_sha256` 另说明
标准化 JSON 哈希；每份工作簿记录实际输出 SHA-256。`charts` 提供行业、黄金、原油的
工作簿、工作表、图部件、分类范围、值范围及最后行；`overseas` 和 `economic_calendar`
提供确定性表格范围。下游渲染须使用此投影和对应哈希，不能自行填入另一套数值。

## 验证边界

离线测试覆盖固定时间、真实交易日分母、一日滞后、过期/未来行情、精确品种、下周
日历、逐组替换、私有调用准入/幂等/快照交接、SDK 身份、超时容量及 Office 缓存。
所有测试数据均为明确合成输入；通过不表示 Wind 已登录、日历映射已核实、业务口径
已通过真实对照，也不表示已经连续三个周周期无人值守运行。


2026-10-22 基金NAV入仓：最多31日东财NAV原生快照仍带未知币种、基准和总回报缺口，不作为本周报Wind/Excel同源输入或正式回测数据。

2026-10-22 iFinD凭据复用：同花顺权限策略验证属于来源认证，data_permission_verified仍为false，不能取代本周报Wind/Excel同源资料、覆盖或正式回测证据。

2026-10-23 Broker新增股票原始历史的Wind范围候选准入，只让auto请求跳过超60自然日Wind；私有周报WindAPIQuery仍经resolve_report_weekly，不借股票备用源填周报组或改厂商字段。已有同源校准及原件绑定继续独立验收。

## 2026-10-23：新研究资料的周报边界

新浪利润表的日期精度公告字段与BEA封闭2024Q2 GDP档案分别属于其来源合同，不能替代本周报Wind同源指标/日期校准。BEA有限历史发布回放不认证其他财务、资金流或经济序列PIT；东财两个通道不构成第二独立来源。原Excel保底、主管理员、授权和blocked_data条件保留。


## 2026-10-23：BaoStock季度财务边界

BaoStock盈利能力只提供来源限定的单季度快照，货币单位证据不覆盖本周报Wind口径、股数/比例尺度、累计期间或历史PIT。未知和不等价不替换现有指标；本次不调用私有collector或Wind。

## 2026-10-23：长期研究档案与机会预警

ETF 可把已有组合／行业研究和周报成果关联到长期档案，但档案引用、A股信号或小创候选内容均不替换本周报逐指标 Wind／Excel 口径，也不提供 ETF 自动证券匹配或历史 PIT 准入。原始数据仍留在既有来源快照，SQLite 只存引用与 pin；缺数据、截断和未知披露时间保持明确缺口。小创 Registry 身份与真实费用尚未验证，不以18／54估算充当等价证明；见[档案合同](research-web-dossiers.md)、[扫描范围](research-web-dossier-scans.md)及[候选边界](research-web-seek-alpha.md)。


WGC 两个公开端点新增月度吨数原生研究快照，存量/流量和来源范围分别保存，不替代现有 Wind/Excel 或私有生产验收。AK 个股资金流在 SDK 前拒绝历史时点/正式回测；first_observed 不获得历史 PIT 资格。详见[原生快照](research-web-vendor-snapshots.md)与[研究仓](research-web-market-store.md)。本轮未部署、未启动生产库或日程。


KAPSARC/BGS 黄金矿山年产量只进入按来源隔离的原生研究快照；不替代 Wind/Excel、WGC ETF 流量或 SPDR 持仓，不获得历史 PIT 资格，也不启用正式生产库/日程。kg字典、原件、注释缺口及版本合同见[原生快照](research-web-vendor-snapshots.md)。


## 2026-10-24：现金流财务比率

既有 BaoStock 公开 worker 增加 `financials` 的 `statements=["cash_flow"]`、单证券及单季度末请求，绑定 `quarterly_cash_flow_ratios` 与独立 `baostock-quarterly-cash-flow-v1`。七项原生比例保留空值，unit/currency=None、scale=unverified；累计/单季、集团/本行口径未知，不能当作现金金额或证券交易资金流。原件重解析结果、行、字段、固定字典哈希和声明完全一致才入原可选研究仓。

披露日保留自然日精度；first_observed、历史PIT和正式回测资格分开，as_of/backtest在公开worker前拒绝。来源隔离、当前授权、旧盈利能力合同及快照兼容不变；没有新依赖、HTTP路由、服务、正式库配置或外盘迁移。真实验证与最终候选证据见[任务报告](../.ai/reports/2026-10-24-finance-flows-warehouse.md)。


2026-10-24：今日发现原始资讯与事件的时间/关联元数据不作为周报数值底稿，也不替代Wind/Excel字段和时点合同；本轮不更改任何周报数据Adapter或正式来源验证。

## 2026-10-24：公开代理策略与原件绑定v2

匿名AK public worker在既有独立子进程中禁止requests继承系统/环境代理和netrc，清空该session及调用代理；保留4秒网络和12秒进程上限，不修改宿主或系统设置、账号SDK或TLS验证。系统最小环境并不能自动排除macOS系统代理。

中国宏观及新浪利润表的v2来源合同将原件重解析结果与完整行、字段、单位/语义、来源URL、总数、分页和参考时间逐项绑定。GDP保持年内累计/累计同比，单位仍未知，不按字段名猜亿元或百分数，也不与BEA单季QoQ SAAR归并。新浪有限snapshot和未知金额尺度、币种/累计口径、自然日披露精度保持；first_observed不等于历史PIT。旧缓存不冒充v2，旧call_id和冻结证据按原义保留。

实际取数、默认Host入仓、PG重启后的独立进程读回、第二空库恢复及最终候选验收分别见[本轮报告](../.ai/reports/2026-10-24-proxy-pit-warehouse.md)。不启用正式库，不部署现有服务或迁移外盘，无新增依赖。


## 2026-10-24：参考证据合同（宏观／新浪v3、资金流v2）

原SDK四案请求在接收响应头前关闭，仍未恢复；没有用改参数、换客户端或后备成功冒充原端点修好。自然失败现在保留有限error_code，资金流尝试链必须存在且精确验证，旧档按原义可读。

GDP v3依据已固定SHA的东财页面脚本字段映射和统计局方法，把四项累计金额标CNY_100million／现价、四项累计同比标percent／可比价；保持年内累计，不推导单季QoQ SAAR。此前v2“GDP单位未知”的段落为当时历史状态，未回写旧快照。

新浪v3只对600600.SH／2025-06-30／合并期末／CNY的营业收入与集团净利润两格，按原件页5（印刷页4）及精确十进制字符串／整数哈希附加参考匹配。float、bool、别股／别期／别项及值修订不获得认证；原data和全局单位不变，未匹配时单位及basis均未知。供应商日期和发行人发布声称分开，冲突不覆盖；PDF历史版本未知，PIT／正式回测始终false。冻结包保留供应商原件和引用元数据，外部参考原件随单独证据包迁移。

实现及逐阶段实际结果见[本轮报告](../.ai/reports/2026-10-24-origin-reference-evidence.md)。不改现有服务、正式库、系统代理、凭据或外盘，无新依赖／付费。


## 2026-10-25：月度宏观与限定财务参考扩围

宏观v4通过固定东财页面实际引用的CPI/PMI/货币供应量脚本绑定字段定义：仅明确变化率为percent，CPI当月／累计指数的基期仍未知，PMI水平不冒充百分点变化；M2/M1/M0数量亿元和月末存量分别声明。央行原件记录M1自2025-01调整并回溯2024年，供应商采用的修订版本未证明，不自动跨年拼接。统计局2025-09 CPI页声称次月公布，只作时点差异示例，不给当前API值回填历史可得时间。

Bao盈利能力v2以保存的SDK原始字符串重建行、字段、固定元数据与引用，伪造或错原件拒入仓。仅600000.SH／2026H1两格与已归档集团半年报的百万元换元值精确匹配，附集团累计／非归母说明；其他证券、期间、比例或修订值不外推。两源分别入仓，首次观察／历史PIT及正式回测限制保持。旧schema缓存跳过，旧显式冻结可读，无新服务、表、HTTP或依赖，原架构图仍准确。外部定义/PDF原件由独立证据包归档，数值冻结保留引用元数据。SDK原端点交叉路由仍失败，不能以后备成功冒充修复。


## 2026-10-25：NYFed SOFRAI 专用v3

NYFed rates单独使用nyfed-rates-native-v3，Treasury/WorldBank保留official-numeric-v2。官方API Schema原件将SOFRAI与四个数值字段绑定；三个30/90/180日历日均值为ACT/360年化复合百分率，营业日复利、非营业日按前营业日利率单利，发布五位小数。指数为无量纲累计因子，2018-04-02基准1、发布八位；不按百分率解释，也不从已舍入指数重建原均值。

官方首次正式发布2020-03-02与2018指数基准分开；SOFRAI在自身value date发布，普通隔夜SOFR在其value date下一营业日发布。约08:00ET后发布及约14:30ET同日修订只是规则，不证明任一历史API记录的真实可得瞬时或vintage；revisionIndicator保留供应商原字符串。当前捕获仍first_observed、非历史PIT/正式回测不可用。

生产和入仓共享严格JSON原件投影与固定字段/依据；拒绝重复键、错误类型/日期/字段scope、深层递归、超限、被篡改的行/字段/元数据/来源，拒绝时保留已有好版本。源数值不重算；只有NYFed旧v2缓存失效，旧显式证据保留。五份官方HTML/YAML原件随私有证据归档，引用元数据随原生冻结/恢复保存；未新增表、HTTP、服务、依赖或执行引擎，原拓扑仍准确。
