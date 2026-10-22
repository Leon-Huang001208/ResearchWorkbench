# DataHub、研究资料与实际文件

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 无新服务、HTTP、持久格式或依赖；现有图及 API Atlas 准确，不重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 v4仍使用原version4 journal和全账号index canonical SHA-256冻结/复核，不新增业务schema；固定旧5495与PR180产品`9b436613aad9136f4959c992c89dd72fc7354ed5`。旧v1/v2/v3、原始/因子/规范快照、账号/模型/凭据及controller/evidence保持。旧v3因默认键物化被门禁拒绝后已正式恢复5495/preserved=true；v4承接已合并启动修复，不清洗索引、不忽略键或改严格保全。现有图/HTML/PNG保持，v4最终资格和实际切换保全另证。

2026-10-22 Wind部署profile v3只在原v4 journal内记录封闭mode、旧5495与产品a0ff3ae2身份，不新增journal版本或业务schema。主实例与全部账号业务index顶层值仍冻结canonical SHA-256并区分缺失/空值，前进/回滚/恢复逐项复核；观察、历史块、规范快照、会话、报告、账号和凭据不覆盖。旧v1/v2恢复材料与controller/evidence保持，产品存储/交接图准确且本轮不改HTML/PNG。真实切换前后保全由root另留证，产品与profile候选验收分开。

## 资产历史与图表偏好存储

最后核对：2026-10-22。Store在内存兼容提供`asset_history_jobs={}`、`asset_history_keys={}`及`chart_preferences={panels:[volume,macd],revision:0}`，无数据库/schema迁移。对于旧磁盘中未有且仍精确等于这些默认值（含JSON类型）的键，启动或无关服务save只序列化原有业务字段，不把三键物化到`index.json`；某键第一次真正改变后才写入，并在原子替换成功后登记为已持久化。原磁盘已存在的键，包括空对象、空列表或null，以及已持久化后恢复默认的键均不得删除；保存失败不提前登记。其他键、原子写入/错误处理及部署严格保全比对保持。指标偏好保留0至4个唯一有序副图及revision，默认VOL＋MACD，账号内所有证券共用；保存失败恢复原值。任务保存原始请求、观察/会话身份、代次、当前快照、扫描进度和安全失败码，公开投影隐藏内部字段。

该边界修复了旧24项业务键/12账号未变、却因启动新增3个默认键而被严格保全门拒绝的v3切换。故障回滚/恢复另留真实状态；不通过忽略新增键、清洗原索引、改控制器或伪造保全摘要解决。现有数据根、快照和交接图未变化，不重画图，也不改CI结构。

不可变块位于当前账号 `.control/asset-history/chunks/<UUID>.json`，绑定证券、会话、观察、扫描区间、配置摘要、定义哈希、原始来源manifest、规范原始行及逐日因子；重试复用前复验归属、哈希、授权和因子版本。单次取数沿原 `.control/snapshots/<session>/<dataset>/` 保存行、raw和manifest。每块校验后创建包含全部累计日线的新规范snapshot，`asset_history` metadata 同时保存固定截止/锚点、定义、因子版本/摘要、实际与扫描coverage及全部输入；随后核对generation、原dataset指针和授权再原子保存Store。存储失败恢复原内存指针，已发表旧快照继续可读，不把部分成功说成全历史完成。

前复权 `P(t)*A(t)/A(as_of)`，后复权 `P(t)*A(t)/A(listing_date)`；更早历史扩展保留既有截止锚点。同一规范快照的全行使用相同定义/因子版本，不能直接拼接不同锚点的复权块。原始行、因子和输入证据保留；缺失、冲突、未证明上市日/锚点或版本变化失败关闭，不补因子或回退原价。量额不随复权缩放，OHLC单位/币种未知保持未知。细则与有限厂商预检范围见[DataHub](../../research-web-datahub.md#资产历史任务与固定复权)。

旧观察、原DataHub快照及旧研究冻结材料不重写。交接复制规范行和自包含的raw/因子/metadata，来源hash仍可复核。会话purge先取消并等待真实Future排空；Store拒绝清理非终态任务，缓存逐项核验归属与哈希，未知对象保留并报错。进程恢复将无存活owner的任务标为interrupted，显式重试后才继续取数；服务关闭与会话取消共用排空边界。常驻活动投影和操作员空闲证明覆盖非终态任务及真实Future，不因浏览器关闭或HTTP取消而提前放行。

## 全市场概览缓存

全市场缓存属于当前用户 `store.root/market-cache/`，与 `index.json`、研究 inputs/outputs 和会话数据集分离；保留当前及上一完整快照，有界原子写入，失败／partial 不覆盖可恢复的完整版本。GET 筛选、分页与 CSV 固定 snapshot_id，板块成员与同份股票池相交；筛选不改变总览分母。数据流见[市场概览](../../../outputs/research-web-architecture/13-market-overview.html)。

报价行保留来源上市日期 `listing_date`；summary 的 `upcoming_count` 区分目录内未来上市证券与一般缺报价。未来上市行不参与有效行情统计，原始缺口保留；`complete` 认证范围分页，不认证每个字段都有值。成交额缺口不补零，不将旧范围中的退市／非普通股复制到当前快照。

资产观察 v2 profile 在原 v4 journal 中记录固定 mode、旧版与目标，主实例及全部私有账号业务 index 仍按每个顶层值冻结 canonical SHA256，区分缺失与空值；v1 同样保留此检查。前进、回滚、完成和 preparing 恢复不覆盖观察、查询、会话、账号或凭据。固定身份增加不改变 journal 版本、数据根、HTTP 或业务存储，现有文件流图无需新增节点。

资产摘要的 `valuation`／`coverageRows` 是浏览器内存投影，不写入 Observation、DataHub 快照或任何数据库。覆盖数要求 dataset 身份与当前实际载入行同时存在，保留失败／加载中的旧快照身份；数据日、`as_of`、`retrieved_at`、报告期及请求／实际／载入区间分别保留。PB与PB-MRQ、明确PS-TTM与单期财务、零与缺失各自区分；Wind股本数量级未核验，不换算或派生市值。折叠状态仅按当前资产恢复，主题切换不改变源数据、公式、快照或交接材料。

AF连续指标迁移不增加数据库或迁移：`section_sources`／`section_ranges`随原 `asset_observations` 请求保存，旧记录缺省为空映射，公开request_parameters与区块状态回显有效来源／范围。valuation仍是所属会话的market_snapshot数据集；六MA／BOLL／MACD／KDJ／RSI和180桶筹码只在浏览器由快照派生，不写回来源。筹码明确估算，财务／股东／行业／事件／宏观缺字段保留空位，资金净额和北向持仓不冒充流入流出。来源、交易日、单位、复权、TTM／MRQ及报告期保留。

CI大日志读取预算30→120秒仅改变资格证明的网络等待，不写DataHub、会话或业务索引。资产专项仍核对主实例及私有账号完整索引摘要，读取器完整SHA256绑定入原恢复包，不覆盖业务数据。

资产观察部署沿原v4 journal记录profile、固定旧版、目标及逐路径Git身份；旧记录仍由原model profile解释。资产/查询状态只读用于空闲证明，不恢复或重写观察数据；保全摘要、业务数据根和凭据存储保持。

资产观察继续保存于既有 Store 的 `asset_observations`，行情/财务等实际数据仍是所属研究会话的 DataHub 快照，没有新增数据库或迁移。单区块刷新在观察记录内保存 `refresh_keys` 的 SHA-256 键、目标区块及 `call_id`，公开响应隐藏原请求、刷新键和内部 sample，只给受限请求参数、区块状态与 dataset 标识。受理先持久化再创建取数任务，保存失败回退内存状态且不启动查询。

刷新保持原 dataset 直到新结果可用；失败、取消或重启中断保留原 dataset 身份，同时标明新的 `failure_code`，不得把旧快照冒充本次刷新成功。已有加载区块没有存活 owner 时恢复为 `unavailable/interrupted`，取消为 `unavailable/cancelled`；不自动重试厂商取数。财务最新一期、Wind资金／两融60天及旧观察行情按原参数记录；新历史任务按上述独立coverage保存；图表仅从这些快照行计算，Golddata 新闻/公告阅读不写成 DataHub 快照或 Hot 证据。

联合升级 journal 增加各发布角色的 common directory/inode 元数据；原 source_common、业务数据、凭据及会话不改写。冻结源码从权威源码仓库创建，发布 clone 原地保留。

PR168 导航资格只增加五个精确 UI blob 身份；v4 journal、原数据摘要和非秘密模型元数据格式不变。新旧会话、附件、原生历史、模型连接及凭据仍在原根，界面更新不移动或重新创建这些对象。

联合升级 v4 journal 保存旧源码/wheel、配置、非秘密模型元数据和完整保全摘要；独立内容寻址恢复包在停机前准备。只变更部署 revision/baseline 与网关匹配绑定，不覆盖业务文件、账号库、凭据或会话；到期删除历史可能被启动清理时先阻断。

恢复任务的工具PATH由plist身份摘要绑定；冻结包和plist均保留内容身份。环境修复不更改业务文件、会话、账号库或模型配置格式。

v3 journal记录static-gateway模式、实际primary、两份资格及三段blob；保全摘要与旧业务文件格式不变。恢复仅回退网关，账号库、会话和模型设置不覆盖。

显式静态准备只写私有 candidate/wheel 与 scope/blob 回执，不回写会话、附件、账号库或模型配置；旧 candidate 仅在已接受退休或同一审查身份时可处理。真实部署后的原文件/会话摘要及非秘密模型指纹继续独立核对。

新网页研究在既有receipt冻结report_binding_policy=bound-analysis-v1，不回写旧receipt。中文字数目标同时读取当前问题及原冻结requirements，补资料新回合不得丢失；目标冲突时拒绝，不选择较宽松值。report_plan保存system_plan与由系统生成的presentation；analysis只允许{{fact:同节已选引用}}和{{formula:$计算id}}插入数字，完整指标/期间/单位一同生成，不接受裸value替换。标题、缺口及建议也拒绝作者手写数字/算式。annual_change和gdp_implicit_deflator仅接收真实年度GDP原始观测，按精确输入计算，仍不认证统计可比性。重复英文取证句、逐项声明/笔记/精确轨迹保存为research-report-<随机id>-audit.json；canonical的audit_attachment绑定文件SHA，附件内绑定报告语义core SHA，最终归档再绑定完整canonical SHA及全部文件，避免循环哈希。附件与原生格式分开计数，随JSON最后发布及回滚；缺失/损坏附件属于完整性失败。约中文字数从冻结问题识别（允许的/正文表述），按可见标题/章节/去重数据表/缺口汉字数±20%核对，不把来源目录或审计底稿算入正文。

完整保全manifest可能超过1 MB。仅gateway-upgrade.json使用16 MB专属私有reader/writer，发送首个信号前按实际UTF-8编码预留4096字节phase余量。reader对同一fd核对uid/0600/nlink、前后身份/长度/时间和当前路径，拒绝替换、短读或超限；通用配置与业务数据格式不变。

进程映像修复只使既有升级journal的command记录已验证的实际argv0，journal/schema、账号库、模型设置及会话文件格式不变；内核探针不读取研究内容。

网关升级仅新增私有 run/gateway-upgrade.json、birth-fence.json 及结果/恢复证据。owner.json 空槽的操作员占位是带inode/事务标记的目录，不伪造原生owner记录；原子no-replace发布，退休阶段持久化后只清理本事务对象。账号库只持EX查询并rollback，研究文件与模型设置不改写。

研究版本列表包括当前检查归档和同任务旧稿，is_current/quality_binding 区分当前与未绑定检查；旧稿不能继承新版本 passed。SDK sources 有界覆盖最多20上传加20已取得网页；GDP 投影保留原文 span、全文 SHA、期间、单位及初步/最终版本。没有数据迁移或报告改写。

旧 payload 和 SDK 默认三格式保持兼容；允许网页取证的任务从首次空索引就统一 plan，独立 Python 仍用于计算/阅读/绘图。新增 calculations 只含id/operation/operands/decimal_places，sections以$计算id选择；数值、单位、引文、所有父来源、notes/coverage均由系统从实际观测构造。Host独立重读原始输入重算，派生scope绑定任务/配方/父观测，不能用模型副本或声明value认证。分析、缺口和跨版本可比性保留原检查。

research_report_delivery 为动态只读投影，不迁移存储：files 指向当前规范JSON及其Host检查归档，aliases仅包含实际字节哈希相同的本会话路径。64文件/32MB是可选别名扫描上限，超限只禁用未检查别名，不影响已验证归档；旧版本与原生消息不改写。

SDK 兼容读取不迁移数据：resources 中原 helper/字体保持原字节，新报告由当前 Host 包的固定 SDK 处理，所有输入、输出、谱系和模型设置仍归原会话。_SESSION_ROOT 只定位 PDF 输出/恢复 cwd，不是质量或路径授权。

Host 抓取的 inputs/web-*.txt 按本会话 web_evidence 的真实 file_id/path 登记保持 web 来源身份；文件和历史仍原位可读，不再在来源清单、业务索引/快照或上传观测中产生无日期的 file 别名。普通用户上传的同前缀文件不凭名称排除。登记与 Store 路径不一致时拒绝分类，不回退为上传。

resources/research_report_plan.py 在原沙箱组装 JSON、Markdown及冻结要求中的HTML/Word/PDF；仅显式summary生成工作簿。只/仅生成的明确格式列表从冻结question推导，由受信上下文传入，Host独立核对；模型不能通过report_formats删减必需交付。原默认仍为三格式。数值表格只投影正文内一致声明，全文与缺口仍完整保留。calculations以精确有理数执行有界计算并只在最终展示时一次HALF_UP舍入，保留精确分数和操作数/公式trace；展示值由Host独立重算认证，绝不修改原质量门。旧Summary的ExactValues/Calc、真实父来源及建议不自动认证合同保持。所选格式先暂存、归档旧版，再最后发布JSON；回滚先撤下新JSON，全部恢复后最后恢复旧JSON，恢复失败保留私有恢复副本并保持canonical缺失。

比较case的数据和产物不进入生产会话。只克隆实际取得的响应作审计，不回填模型证据；预览/下载和归档分别核对实际字节。缺原生格式、版本或质量回执保留缺项，辅助审计文件不冒充原生交付。

web_search 原生 Markdown Sources 清单与旧 JSON 均可登记，身份保持原始 title/url（含片段），state=search_summary 不含正文。Host 只按已登记 ID 读取公开 HTTPS，正文 inputs/web-<id>.txt 与会话 web_evidence 记录实际字节 SHA、最终URL和取得时间；模型不能写 inputs 或自报观测。质量检查重读并复验这些字节。

每次检查把规范 outputs/research-report.json 的内容哈希与经核验的 JSON/HTML/DOCX/PDF 归档关联到具体检查 ID。同回合新版替换会产生新哈希和回执，旧版保持旧状态；历史 fallback 没有相符内容哈希时保持 incomplete，不借用最新报告的 passed。当前版不重复显示为历史，旁路 JSON 不成为规范报告。

write_summary_workbook原子生成Summary的metric/value数值首表、完整空白分隔行及独立ExactValues；额外Facts/Notes等表不混入首表，列表单元格保存JSON且转义公式文本。CPI历史月值仅来自核对过的表头/同一行，百分点按Decimal复算；前月同比只接受完整肯定发布段落并核对本期表格。NIST仅提取原字节句，不认证译文/落地。

可选calculations是数据配方，不是脚本或可信结果；Host只读取本会话允许inputs的实际全文字节并核对SHA，生成绑定用户根/session/task/算法/输入与配方摘要的观测。模型sources/coverage/notes仍由原门逐项核验，不自动改写。

幂等请求头透传不改变账号库、会话及模型配置格式，不搬移历史或凭据；原后端继续维护请求幂等性。

stage 释放仅归档原私有身份账本并退休容量；全部数据、日志、缓存、凭据和模型密钥卷以及恢复档保持原样，不迁移或删除。

常驻私有resident.json增加可选整数max_additional_instances（1至4），缺失保留额外1；不改变SQLite、会话、文件、模型及控制token格式。容量修改与版本路径一起通过已审操作事务保全、回滚及重启，不迁移用户数据。

不新增端口账本或schema：用户.control/datahub.json及可选mcp-runtime.json继续是可信回调地址权威；恢复只读其原址，不重写token。原址事务journal存在时不启动用户pair。

primary UI 文件只从已验证的旧 project/app/research_web/ui 读取；数据与源码根均不能由浏览器传入。静态响应不缓存，原研究文件与模型命名空间不搬移。

显式附接不搬移原 `research-web`：primary 继续使用原 index、会话文件和模型凭据命名空间。私有 server/resident.json 记录非秘密绑定与源码 SHA；run/cutover.json 是切换写入栅栏，run/recovery 保存前一 boot 的控制记录。保全摘要覆盖全部原会话文件（包括业务 tmp 和 .lock），只记录内容哈希与计数；原模型密钥值不读取。账号库和生产验收证据不进入 Git。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](../../research-web-ai-news.md)。

## 服务器账号与用户数据

可选服务器根默认为 `~/.research-workbench/server/`，与原 `research-web/` 个人数据根分离。`accounts.sqlite3` 只保存账号、scrypt 密码摘要、登录令牌哈希、过期与限速事实；不保存研究正文。服务端生成的 UUID 对应 `users/{uuid}/research-web/`，其 Store 索引、`sessions/{session_id}/inputs|outputs` 和 `runtime/home/sessions/` DSH 历史各自独立；`users/{uuid}/state/` 保存该实例私有认证及所有权记录。`logs/server.jsonl`、`logs/runtime.jsonl` 记录非秘密审计；用户 pair 日志在其数据根 `logs/`。

全局资讯单独使用 `server_root/shared/ai-news` 的原API/worker配置、私有token与独立PostgreSQL；不存入任何用户Store、DSH HOME或个人凭据命名空间。成员共享公开阅读投影，管理和状态仅admin；tenant后端无法代理全局AI路径。默认bridge不创建该目录，备份账号或用户研究根不能替代独立资讯库的备份与恢复核验。

服务器目录权限为 0700、私有文件 0600，拒绝符号链接、硬链接及未知归属；凭据继续按用户 data home 命名空间进入既有系统凭据设施，不复制管理员密钥。账号密码重置或停用撤销所有登录态，停用账号不删除其历史和文件。只备份账号 SQLite 不能恢复聊天：完整服务备份须包括所有用户数据、DSH 历史及经独立授权的凭据恢复方案。首版不自动迁移原个人数据或清理用户历史；同 UID 后端本身仍受信任，文件目录分离不是 OS 隔离。

报告 Workflow 在服务器 profile 禁用；FinGPT/Claw 的原会话文件和文件式文档继续按用户根校验。浏览器草稿用账号 UUID 命名空间的 sessionStorage，导航偏好用相同账号空间的 localStorage，避免恢复其他账号状态；Cookie 不进入这些存储。同一浏览器 profile 的本地存储仍由该 profile 持有，命名空间不是本地数据保密边界；浏览器下载副本由用户自行保管。

## FinGPT 证据与报告版本

每轮用户要求、截止时点、模式、前轮身份及质量回执复用 Host receipt；DSH 继续保存原生正文。模型只能提出报告、覆盖定位和数值主张，不能修改冻结要求或自证通过。Host 有界读取文本附件及 DataHub 快照真实字节，将数值、期间、单位绑定后复算；无法确定的结论保留未核验。

新报告替换前将上一版 JSON/HTML/DOCX/PDF 的可用字节归档至会话 outputs/report-versions，原本缺失的产物继续标缺失，Host 保存哈希锚点。当前报告完整性无效时停止报告导出，原始输入附件保留可读。历史版本按原检查结果展示；版本保留不等于恢复执行，续研仍为新的原生回合。

原生沙箱内的归档临时目录以 UUID 名称在同一输出目录排他创建，不调用会解析相对路径并访问 getcwd 的 tempfile.mkdtemp。字节复验、只读归档、原子发布与错误清理保持；沙箱权限不扩大。当前质量投影只接收会话文件映射中的 outputs/research-report.json；同名备份不覆盖当前报告，只有非规范副本或重复规范身份时仍判 invalid。

Host专项升级只读检查index中sessions/项目/导航命名空间类型，不迁移或回写数据；原Claw项目和凭据保留。成功健康后baseline审核位于私有resident/baseline-reviews/<target>.json并原子更新config.baseline，固定controller artifact、工具路径、生产目录及端口不变；候选/accepted/transaction仍由原事务维护，回滚不覆盖研究数据。

旧格式历史保持原始字节和文件时间，不发布迁移 successor。搜索只删除陈旧派生索引，不修改用户原文或文件产物；未搜索会话数量和片段只在当前搜索响应中返回。

resident管理记录位于产品home/resident，config/state/candidate/transaction/accepted及失败SHA隔离
均为用户私有JSON；artifact与wheel记录hash/来源SHA。journal先于停服务同步文件及目录。
回滚只恢复源码、wheel和安装manifest，不还原PID/auth、不覆盖研究data或Keychain；敏感持久化变化暂停。

Claw 步骤展开显示实际参数、结果、错误、已知退出码与耗时；回答可折叠回执不改变文件身份、哈希或来源。聊天试跑继续用独立执行会话及Run定义快照；执行结束、文件实际交付和金融数据缺口分别核验，纯执行流文件不得冒充真实收盘研究。

任务资源ledger与回执位于Git common directory的`leon-engineering/resource-closeout/<task-id>/`；日志证据逐文件hash复核后保存到其私有evidence目录。node_modules、.venv等可再生依赖不进入永久证据；业务数据、凭据及恢复归档均保留。卷清理继续使用原docker_resources的归档、SHA和真实恢复比较。宿主df增量与缓存逻辑容量分开记录，不重复累计共享层。

Hot Word投影与既有report_documents共用标准日志，导入不初始化旧core.settings或读取
开发.env，不创建项目根的旧存储目录。单次报告在Docker只读根内仅用内存生成，原件
由Hot持久表保存；Host明确保留副本时仍只写其受控私有资料根。

AKShare不支持的northbound/money_flow资金口径及index/ETF股票feed快照在选择、缓存和SDK前
失败关闭，不把个股资金流或股票价格冒充目标数据。fund_flow按日期裁剪再限行数，股票后缀保持。
Provider semantics revision纳入非秘密授权摘要；旧cache不能复用，新调用可重新取数，历史raw/rows保留。
Matplotlib字体使用research_helpers.chinese_font_path()的打包绝对路径；旧会话可由该模块__file__
构造同一已准入字体路径，不需要getcwd、额外宿主目录或网络权限。

`external_data` 复用既有 Broker、会话快照和原生工具桥，不创建新数据执行器。
外部来源总目录包含取数登记与仅参考来源；目录、凭据配置、健康和实际查询状态分别认证。
外部响应保存供应商原字段及单次响应限制；未验证成交量单位保持 provider_defined，
指数价格使用 points，不猜测换算。模型面对的前三行样例按 UTF-8 字节裁剪，完整数据仍在
会话 inputs/datasets 的 JSON/CSV 中；不能用截断样例认证历史完整性。

services/hot/evaluation/real-corpus-v1.json为可版本化公开样本，保留不可变材料版本/原页/完整材料快照hash和三份模型packet/response hash。不是生产数据备份或秘密载体；外部参考文章未冒充已入PG。2开发/3回顾留出仅主样本分离，真实候选上下文重叠原样保留并在回执列出。

事件快照occurredAt/effectiveAt支持null、YYYY-MM-DD日精度和UTC毫秒时刻，新增可选dateEvidence两项nullable引用与manual.times；仍append-only/schema20，旧snapshot兼容。日期依据为材料id/revision/quote与来源时区，不能用取得时间补空。旧截止/旧简报/研究快照不回填，新冻结版本携带日期依据。

schema20原raw_pages metadata保存runId/pageIndex/url/stop/backfillDays，已有partial/gap枚举记录边界。每轮原件和inbox同事务先于水位；晚页失败仍保留早页但不发布成功水位，已存页解析不清除错误或回退水位。

sources只读返回adapter/catalog_id、绑定状态与激活许可，不回传完整config或秘密。来源表单期望版本来自最新config_revision，保存与审计沿原表；频率0由Host转为默认null，不增加数据文件或复制旧原文。

公开目录激活用JSONB合并只更新adapter/catalogId，旧配置额外字段和大整数原样保留；materials/material_versions/raw_pages及研究快照不改。审计追加理由、旧adapter和前后配置SHA，编码postgres-jsonb-text-v1对应实际SQL config::text，不把原配置或秘密复制到回执。

Hot周期aliases在旧Automation关闭时继续仅访问Hot PG和其已冻结简报，旧Automation Store没有读取或写入。已有计划/运行/选材不复制到旧调度存储；无新增schema、秘密或目录。

显式stage升级只更新固定image/source SHA及清空原容器projection，previous_image与data/logs/credentials/cache/model_key五卷保持。停止pre-AES兼容判断不读取密钥，不更改model_instance/model_store_state，不迁移业务数据。

可选`model.materialIds`只限定处理范围，不复制材料、事件或预算。明确选择的排队任务在同一hot.process队列按当前owner generation精确优先级领取；重启只取消/重新入队这些已选择的created/retry任务，不改其他任务ID/排队状态或活动尝试。schema20联合恢复已核验58表全量清单及所选真实研究报告字节哈希；恢复目标暂停，原生执行历史不恢复。

schema19保存follows、不可变follow_versions和follow_requests（理由/操作者/前后状态）。schema20保存periodic_plans、不可变计划版本/请求、periodic_runs和不可变选材。简报及周期run回执同事务发布；迟到领取回滚整个发布。每份周期简报包含planId/planVersion/runId、固定cutoff、窗口、跳过周期数、来源覆盖限制；网页/Markdown/DOCX沿同一冻结版本。关注中的旧事件ID沿既有别名解析，不复制事件或原件。

研究页面从不可变简报的报告集合中选择1–20个唯一材料ID，连同简报ID/版本准备已有Hot运行。原件及会话快照由既有Host校验发布；浏览器不复制可变原件。未知执行保留runId、问题、格式，核对不生成新runId或改变原deliveryKey。

Hot正式研究固定deliveryKey绑定问题和输出格式，并复验会话快照/manifest哈希。
只对数据库证明reserved、dispatched_at为空且无回执的尝试允许停止后显式取消/归还预留；
dispatching/outcome_unknown费用保留，操作审计和UUID重放避免重复退款。

Hot流回执复用原PG model_receipts；Host只透传绑定根Hot会话的预算操作，费用由Hot计算。
hot-context内容不授予权限。请求含完整messages/tools/toolHistory，以UTF8字节加余量登记；
未知结果保留额度，未保存回执不输出。

AIHOT阅读界面适配只读取原事件、频道和材料投影；列表日期明确是观察日期，展示层不重写
原文/版本/发布时间、不搬运Golddata记录进Hot。新版快捷筛选开始时清空旧分页与cutoff，
失败后不能用新条件续接旧频道资料；本页热度不是完整来源覆盖或全榜。

schema17 在同一 Hot PG 增加不可变 research_model_calls，关联现有 model_attempts、
研究 run/session、请求哈希和固定价目；与预算预留原子提交。它不保存凭据，也不新建
快照目录或付费队列。归档现有全 schema 清单会包含该表，研究文件联合恢复仍待验。

私有research.model接口复用该call映射及同一model账本。完整流回执最多1MiB/8192块；
服务按固定价目和标准usage计算费用，不接收调用方费用。已知失败保留rejected缓存标记；
缺usage或结束标记不能冒充完成。完整回执的签名帧及缓存返回最多2MiB，普通帧范围不变。

Hot 非秘密配置位于产品数据根的 `hot/settings.json`，采用 0600 原子替换并绑定当前项目根；
未启动时诊断不创建目录或查询凭据；实时状态通过系统库解析签名 key。`identity.json` 与
`process.json` 绑定项目与进程身份；受管 PG 使用独立实例卷和私有密码文件导出，秘密权威仍为系统库。
Hot 业务材料、版本和任务由独立 PostgreSQL schema 持有，不让
后台进程写现有 Store。研究快照联合恢复尚未实现；当前最小库恢复不能证明会话恢复。
Hot 私有归档包含 `hot.dump` 和认证清单，原文 bytea 随库保存；`archive-attempt.json`
记录非秘密执行状态，未知结果阻止自动重复恢复。当前归档上限为 256 MiB。
`collection_runs` 关联准确领取尝试；`material_inbox` 保存不可变解析输入及单向处理标记。
原文、全页 inbox、水位和 parse 入队原子提交；解析批次共享原文 ID，材料版本不会覆盖。
来源为最新快照，不能推断历史完整覆盖；无效编码或 XML 保留原文与错误，成功水位不前移。
`source_control_requests` 保存不可变前后状态、请求 hash、操作者类别、时间与代次；
来源 `config_revision` 条件更新避免并发覆盖，`frequency_seconds` 可空以继承全局周期。
同内容重复条目的原始时间可能保存为排序 JSON 数组字符串；可信瞬时冲突时 parsed time 为 null，
完整原文和页 metadata/gap 保留声明。材料身份不会因来源列举重复而增加，也不猜测发布时间。
Hot model_budgets 保存累计授权与收费预留，model_attempts 保存发送状态和令牌 hash；
model_receipts/model_results 不可变并按输入/模型参数 hash 复用。未知发送不退款，
迟到回执可保留，但不能绕过业务任务的代次/租约提交门。
固定 DSH 成功流不提供 HTTP request ID，provider_request_id 可为 NULL；不能伪造本地 UUID。
记录请求模型名与报价 hash，不把旧模型别名冒充为已验证后端版本或账单费用。
day_key 属于发送/预留所在日，派发跨日必须重验；未知尝试继续占额。cost_basis 明确计费来源。
频道条件配置保存在 channel_versions 与 channel_control_requests，纠错保存在 event_versions/
event_corrections；CLI不写旧Store或改动原文。配置/纠错输入为有界、无alias的JSON普通文件，
不接收凭据字段。频道集合可按ID选择；控制结果未知时，调用方须保存UUID和原参数用于重放。
Web输入为有界JSON正文而非本机路径；配置只在当前项目绑定的数据根保存。浏览器只保留
非秘密视图、已选材料ID和待确认控制参数，不复制原文或凭据，也不把Hot数据写回旧Store。
验收控制身份位于私有 hot/acceptance/model-identity.json，控制/worker 秘密只存系统凭据库。
真实模型回执与缓存留在持久 hot_acceptance_model schema，不能因重跑验收丢弃账本。
Hot内部简报冻结核心在同一只读repeatable-read事务中取得截止时点的频道配置、事件和
全部关联材料版本，保存原判断覆盖依据并生成有界、规范JSON哈希。Markdown区分归组摘要、
来源陈述与规则/模型/人工判断；不把旧判断覆盖写成当前采集健康。当前仅内部返回与验收导出，
尚无简报表、公开路由、DOCX或研究冻结原文副本，不能据此认证阶段四完成。

验收 control/ledger 位于实例私有 live-acceptance/<身份> 叶中，控制摘要、永久锁、FD 复核、原子替换和读回绑定票据。describe/reserve 不创建；init 拒绝已有或中断初始化的实例，不修复、不退款或重置。最多3票、512输出/票、1536累计；旧费用政策仅为已过期历史字段。

原生事件仍由 DSH 日志保存；历史/分页/SSE 归并的同序号冲突标记只保留在 Host 内存记录外层，不新增正文库、持久 schema 或写回日志。Automation 草稿及文件交付不能从计划项完成推导。

Docker 模型密文是 AES-256-GCM 版本化 envelope，复用私有文件权限、锁和原子替换。
credentials 卷的 models 子目录与独立只读 model_key 卷、随机实例身份共同构成恢复材料。
每次写入生成 nonce，AAD 绑定实例与 ref；身份/主密钥丢失或错误不会自动重建。
Host 认证 record 和通用业务凭据仍为独立通道，不接收模型 Key。

## ETF 工程模拟与真实准入边界

`portfolio_decisions/` 是 Host 内的确定性领域计算，独立于 framework-explain/verify 的只读解释。
固定 63 交易日总回报排序、正动量过滤、最多 3 个 ETF、周内最后交易日收盘后确认，最早下一时段模拟。
用户明确风险预算、证券/行业上限、现金下限、费用、滑点、价格偏离、参与率与有效期；示例只用于工程断言。

工程输入 `ReplayRequest` 包含不可变 `StrategySpec`、冻结 `ResearchSnapshot`、日期范围与人工裁决。
快照声明来源/版本、证券身份、历史资格、日历和可知时间、逐日未复权二级市场价格、总回报指数、
成交量份额单位、停牌/涨跌停、现金分配与拆合份额。NAV价格口径、单位错配、重复记录、非有限数值、
无时区时间与缺行业上限均拒绝。信号只读确认时刻可知的64个相邻交易日；缺历史阻断而不推导清仓。

`PaperEngine.step` 共供回放与前向工程模拟。等权后施加预算、证券、行业及现金约束，余量留现金，
不重新归一化。成交再按可用现金、价格和现有敞口检查。旧可卖批次与当日新买批次分开；
未成交卖单不释放资金。数量/价格按显式版本单位取整；涨跌停触价保守拒绝。部分成交、延期、过期、
撤销分别保存。整数份额公司行动与现金分配只按显式数据入账；分数份额权益未支持，拒绝执行。
公司行动导致原计划失效时撤销并等待新计划。

关联链为 strategy version → signal → intent/decision → order → fill → lots/cash/review。
人工采纳、否决、延期仅接受相应周频事件到下一交易时段前的窗口，保存理由、证据与前状态，
机械影子结果另算。checkpoint绑定全部输入，重复日无效，异常整日回滚。
开盘字段与公司行动由独立 `execution_known_at` 绑定，必须在09:30可知；close/总回报按 `known_at`
用于收盘信号。成交风险估值只用开盘价，扣费/滑点后重检全账户。全日成交量明确作为
`daily_post_session_participation` 的事后撮合上限，成交分别记录假定开盘时间与盘后确认时间，
不把全日成交量声称为开盘已知。持仓公司行动资料晚到时回滚该日、停止推进、保留账本缺口，
当前请求区间收益显示未知；恢复不能跳过尚未处理的交易日。
SQLite位于产品根 `portfolio-decisions/paper.sqlite3`；完整请求、结果、版本与幂等键同一事务提交。
完整输入和实现摘要共同生成运行ID；键重用但输入变化返回冲突，策略版本不可改写。输入/单个结果各≤8MiB，
运行ID及checkpoint另绑定规则实现源码摘要，避免不同实现复用同一结果；该摘要不是准入回执。
资产≤30、日历≤1500、运行≤100；列表只读摘要。沿已有产品隔离，无全局数据库前置。

真实入口始终 `BLOCKED`：DataHub尚无已认证的ETF历史资格、二级市场原价、总回报、公司行动与
可知时间闭包，必要计算能力真实当前版本比较证据未闭合。`provenance=engineering_only`上传不授予准入，
不能通过别名、复制旧calculator或普通JSON绕过receipt-gated Skills。readiness只读现有DataHub目录，
不自动取数。工程API不注册为DSH Tool/Automation，不接券商或真实成交；真实适配及准入须独立验证。

复盘保存净/毛收益、费用、回撤、换手、现金、基准、未成交与估值缺口。缺估值不输出完整净值或收益；
参数试验随规则保存，未认证真实固定样本/样本外区间时研究状态为`NOT_VALIDATED`。
毛收益只加入已支付费用，不代表另一成交路径的反事实回测。

会话文件的 Markdown 预览响应使用 `text/plain`，让浏览器在既有 sandbox iframe 内显示原始内容；下载仍按原始 Markdown 类型和字节返回。此处不执行Markdown中的HTML，不改变归属校验、CSP或下载路径；格式化报告仍由安全Markdown渲染器展示。

`write_deliverables(..., formats=['md'])` 只生成所选格式，按需导入 Office/PDF 依赖；默认调用继续生成原四格式，旧 pdf=True 继续兼容。空、非法或矛盾选择在创建目录前拒绝并记录日志，Path 返回值保持兼容；对话工具打印路径时先转为字符串。原对话可在禁脚本的沙箱 iframe 内展开同一 Run 执行会话的真实 MD 预览，不复制到来源会话输入，也不授权模型跨会话引用。

Claw 原对话运行卡显示真实执行会话的文件和版本来源，不复制或合并其他会话产物。执行要求由历史 Run 快照恢复，正文完成不替代文件校验；DataHub 查询身份、实际日期、单位及覆盖口径保留在模型摘要，不把单一未识别标的当作指数或全市场。

历史子 Agent 的原生 catalog 与正文保持原状。模型设置可以读取已核实的 inactive 活动而不恢复 unknown 执行模式；不清理、转换或重写历史记录，也不改产品索引 schema。

## Claw 本地研究项目

`claw_projects.py` 按 mode 管理索引中的 `claw_projects`（原键保留）与新增 `fingpt_projects`，及所属模式会话的 `project_id`；旧会话归入各模式默认项目，不迁移历史数据，执行 `workspace_id=research` 不变，项目归档不删除会话或文件。成员聚合、移组、会话创建及显式文件引用均验证同模式项目归属。

`navigation.py` 在同一 Store 的新增 `session_navigation` 键下按 claw/fingpt 保存 `{revision,pinned,project_order}`，缺省 revision=0、列表为空。导航只是元数据，不复制正文、产物或研究事实。写入沿 ResearchService.lock 和 Store.save 的原子替换，并在失败时恢复旧内存对象；冲突拒绝且不覆盖原状态。读取过滤已删除会话、归档项目及其会话的失效导航引用，不清理源记录、不写索引。项目排序可为有效 ID 子集，新项目由客户端追加；两模式的默认项目 ID 均为 default，但对应独立成员及导航。
项目文件列表保留来源会话和 SHA-256；跨会话文件引用须显式选择，同项目归属、普通文件身份、允许附件格式与 30 MiB 上限逐项校验，读取源文件使用既有 descriptor-relative `Store.open_file`。
复制生成独立附件，并在 `file_references` 保存来源与内容哈希；来源后续修改不改变已经引用的副本。附件索引与来源记录通过一次 Store.save 发布，避免扫描附件时提前保存；包含临时索引创建失败在内的 OSError 会恢复旧索引/来源记录，并移除本次新副本，既有附件保持原样。项目保存与移组也在裸 OSError 时恢复原内存状态并返回领域错误。
DataHub 资料快照仍属于原会话，项目仅聚合摘要和来源链接，不隐式复制或混入新会话数据准入范围。

`automation_drafts` 保存提出、取消与确认状态；原生工具只提出草稿，不写可执行 `automations`。
确认调用原 Automation 创建逻辑，稳定创建键与内容绑定处理重复请求及确认检查点失败。旧目标保持默认停用；research_task 明确确认创建并启用，失败保留已创建停用任务。
任务保留 definition_version/definition_revisions，Run 保留 definition_snapshot/version 和 source_session_id。automation_tombstones 仅保存已删除稳定 ID 的拒绝重放索引；automation_trial_requests 保存用户请求序号到 Run 的受理指针，不保存第二份正文。历史研究与数据不迁移。执行会话删除或单条历史异常只显示受限结果，不阻断来源对话。

## 会话研究底稿与中文 PDF

research_sources 从本会话输入文件、DataHub 快照和已完成检索活动派生；web:URL摘要、file:文件ID、dataset:资料ID 是来源标识，不代表全文已读。网页日期未知、资料不完整或无法证实的引用保持限制。它不是第二套事实数据库。

受控 resources/research_report.py 的 write_research_report(output,payload) 共用同一正文生成 HTML/DOCX/PDF，重开后发布 outputs/research-report.json。底稿绑定 delivery.task_id，含 title/as_of/sections/required_sections/sources/notes/missing；section.id 与 note.stage_id 为显式底稿关联。每次生成使用独立文件名，并记录 artifact 名称与 SHA-256；变更/缺失或跨会话来源不认证质量检查。

PDF 使用锁定 ReportLab 与随包中文字体 Noto Sans SC（许可证与固定来源摘要在 resources/fonts）；所有文本转义，无外部字体或宿主 Office。PDF 交付检查在既有严格沙箱内重开，要求有文本且不超过 300 页，仍受 16 MiB 限额。源身份/声明覆盖检查不等价完整研究或数值事实复核。


新 Docker 目标采用每实例独立 data/logs/credentials/cache 四个命名卷；data 映射
`/data/research-web`，包含既有 DSH home、会话索引、上传、产物与产品日志。
管理账本保留数据卷身份；开发重建/退休仅删除精确所属容器，保留四卷与源码，
不迁移 canonical Native 根、PID、cookie、Keychain或旧Compose bind数据。
stage/prod不挂载开发源码，各实例网络、端口与运行状态分离。
通用业务凭据目录与模型存储仍是两个合同：Docker 模型桥显式绑定
`/run/rwb-secrets/private/models` 的加密记录，既有通用凭据保持原路径和格式。
主密钥一次创建且跨重启保留，两个 ref 的密文绑定 data-home 命名空间与账户；
缺失/损坏密钥或密文失败关闭，不从环境、旧 YAML 或 Native Keychain 恢复。

Docker 资源清理不删除产品 bind mount 的宿主目录。废弃数据卷先保存到本机私有归档目录，
以 SHA-256 和临时卷实际恢复/逐文件比较建立恢复证据，再删除原卷；归档不自动过期删除。
当前及上一接受镜像分别由原安装摘要和 `install/docker-previous-manifest.json` 保护，
失败发布恢复两份摘要。历史标签、未知卷与缓存不能被当作有效安装或可丢弃数据的证明。

DSH 0.2.1 的 preset 注册改为 owned overlay 中的声明式插件行；原 `.agent-presets/<id>/agent.cordis.yml` 仍是产品生成源，不再依赖旧版文件目录自动发现。空实例默认模型为 `deepseek-flash`；已有保存的模型 ID、历史会话和快照不自动重写。安装清单绑定新的固定源码及实际构建闭包，模型秘密仅进入 Native Keychain 或显式 Docker 加密凭据挂载，不随 preset、安装摘要或快照复制。

Automation 沿用 automation_runs 的 session_id、report_run_id、updated_at 和 failure_code 字段，不新增索引或迁移。已知关联通过现有原子 Store.save 写入；失败回滚内存关联，不以未落盘引用继续提交。报告晚到的会话 ID 同样保存；未知、陈旧和异目标引用保留失败原因与原记录，恢复不删除或重建原数据/产物。

Native 停止端口等待只在 RAM 保留停止前端口元组与最多45秒单调期限；
不保存观察基线或新状态，超时不写模式记录，产品数据、认证与凭据沿原路径。

模式切换 finalize 诊断仅使用既有 stderr logger，不创建报告快照、marker、持久 proof 或日志目录。
Native status 阶段诊断同样仅写固定 stderr 字段，不保存子进程报告或新增状态文件。

容器 Web 单轮就绪预算调整只影响现有内存中的探测期限；不新增持久字段、目录、
认证预写或数据迁移。失败仍清理本次精确子进程，研究数据与凭据保留原有路径。

异根 Native 认证只读取两份既有私有 launch ledger；调用内比较 hint、目录/record FD 和
进程事实均只在 RAM。不会新增 marker、持久 proof、Native 端点或认证文件，不读取环境/秘密，
研究会话、附件、控制 token/有效额外字段与凭据仍沿原路径；作用域退出关闭 FD 并清观察。

同 scope 的 Native own state 从原 mkstemp writer FD 保留 dup 到发布/就绪/停止结束，
只在 RAM 记录实际 Popen、记录元数据与完整进程/listener 基线。记录同内容替换不能继承
该观察；失败按精确 child 收尾，未知持久记录保留，不新增 auth、marker 或 proof 文件。

内部类型说明和格式整理不新增文件格式或持久字段；控制记录仍保留原 token/额外字段，
私有诊断仍不写入异常正文。类型检查日志与产品数据分开，不能充当运行时归属证明。

Docker missing/new-root witness 仅为调用内 RAM：保留真实 lease/controller、私有父/根 FD、inode/owner/mode 与已有 OS 监听身份，不写 marker、PID、认证、controls 或元数据备份。no-start 只发布原安装摘要与模式，产品根保持缺失；实际 start 创建私有根并在 up 前失去分配权限。失败后只按原精确容器归属清理本次对象，未知替换保留；根和用户数据不删除，不把已创建根清掉来假造下一次 fresh。旧状态、凭据与研究数据不迁移。

模型默认值、清除/回执未知标记及最近显式生成结果只保存于既有非秘密产品索引，不保存Key。macOS Native固定DSH模型秘密仅在系统Keychain；权限受限私有文件仅用于Host认证record；不进入DataHub快照、Automation索引、模型上下文或导出。提交前的未知标记支持取消/崩溃后的冷恢复失败关闭。

运行状态 guard 的拒绝取证仅进入既有私有日志：固定枚举与身份变化字段名不包含路径、
数值身份、文件内容、Cookie或token。不新增状态文件、marker、认证预写或数据迁移。
身份变化日志只增加精确root/runtime对方向与相对位置枚举；仍不记录具体祖先目录或真实UID/GID。

Docker `/state/runtime` 位于 1 MiB 的私有 `/state` tmpfs；认证通过每次启动/重启的原链重建，
容器停止丢弃状态，不做文件预写、marker、权限修复或旧认证迁移。
宿主 state/logs 单独 bind `/state/logs`，产品日志继续保存在 data-root/logs；
旧 host state/runtime 原样保留，数据与凭据持续使用原绑定。Docker VM tmpfs 可能进入 swap，
见 [Docker 文档](https://docs.docker.com/engine/storage/tmpfs/)，不能宣称秘密永不落盘。

包明确发布子树中的 `doc/docs` 代码和配套运行资源属于镜像资产，继续进入既有 staged manifest。
用户资料与包顶层文档不因此进入运行资产；未选开发包、测试、fixture、缓存不复制。

Docker 派生资产的根模块相对别名只指向镜像内已选生产包，和私有 pnpm hoist 一同进入已有
staged manifest。它们属于只读代码资产，不迁移用户 Profile、日志、缓存或研究资料。

构建stream复用调用方私有任务stdout日志；仅脱敏内容外流，不新增持久数据格式或研究文件。原始捕获每路≤2MiB、合计≤4MiB，不上传日志。

Docker builder 的 Node headers 是固定基础镜像资产，和 binary 同源，不是用户数据或新依赖锁。
完整目录覆盖 config.gypi/common.gypi；只在 dsh-builder 使用，不进入最终 runtime 或研究根。

Docker pnpm 下载并发 8、单请求期限 120 秒是[构建命令局部参数](../../research-web-installation.md)，
不新增缓存或持久字段，也不改变研究数据、认证状态或凭据路径。

Docker CLI代理只来自本次host环境校验，不写研究数据、manifest、Compose或镜像；provider
秘密和Docker endpoint/TLS覆盖项不继承。Doctor.proxy只投影state/configured/local_bypass/issues，
没有代理URL、认证或NO_PROXY原列表。

正常 Native installer auto-start 凭同次 manager 在真实持锁 scope 实际创建根并保留身份至
build-lock 就绪，不能从已有文件认领；no-start/跨调用没有该证明。环境 marker 仅证明
checkout-owned Python，不承载数据根 witness、lease 或控制 token。

Native 补齐任一缺失控制文件前先只读验证全部既有控制记录；MCP-only 动态 origin 成为
正常 DataHub creator 的输入，畸形 MCP 不会留下新建 DataHub 文件。

Native 环境和运行账本缺失的只读桥核验监听事实，不创建账本或控制文件；外来实例的
已证明监听不会被当作本研究数据根的写者，未知或同根进程仍保留原文件并拒绝生命周期。

Web 的 RESEARCH_DATA_HOME 与 DSH 配置均可使其他 checkout 使用相同数据根；仅 argv 路径
不同不足以证明隔离。fresh 创建身份仅在本次启动内存中持有，已有 setup runtime/build-lock
目录不取得该证明；拒绝时不删除、移动数据根或改写账本以制造全新状态。

fresh 失败恢复的外来监听身份仅存在于本次内存记录，不写入 ledger/journal/日志。持续根与
lease 身份、全部本次对象退出和原监听事实一致时才恢复原 controls 字节；未知或替换保留 intent。

独立端点 helper 的 `install/endpoints.json` 是运行时元数据，不是第二份依赖或研究事实。
启动链的 origin helper 对两份 `.control` 记录保留 token/其他有效字段并改 URL，
不迁移数据或凭据；原始回滚字节只留在内存，持久中断标记没有 token 备份。

Native 在可信正常 creator 补齐缺失记录后开始事务；Docker 首次两份都缺失由正常 guest
creator 初始化，单缺失由受管 prepare-only guest 先补齐。host 保留已有文件身份并在guest
退出后复核未被替换，再对两份可信文件建立事务基线；不认领外来替换。
端点CAS恢复生成新revision，不覆盖并发发布或另一模式记录。

固定Docker bind中的私有叶首建不读取认证或凭据；创建阶段允许的父owner映射只限root到
当前进程UID/GID，随后重新完整验证节点。已有文件、叶目录和canonical数据根均不chmod/chown。

新建Compose调用的launch label通过私有临时目录内的最小配置overlay提供，退出后清除。
它不含凭据或用户内容，不写入接受摘要；持久化数据与秘密不参与失败容器回滚删除。

Docker 凭据记录继续位于独立凭据 bind 的 `private/` 子目录，重建后验证并复用；
Docker Doctor schema 1 的 `volumes` 安全类型投影为 data=bind、state=tmpfs、logs=bind、credentials=bind；新增 logs 为固定非秘密类型字段。`verified` 仍只由实际容器 inspect 归属/挂载核验成功决定，缺失或不安全容器为 false；只读查询不创建日志目录。
运行状态为临时 tmpfs 的 `runtime/` 子目录，每次正常重建认证。旧宿主 runtime 不再挂载，
不迁移或删除，不复制 Native Keychain，也不改变 canonical data-root。

Docker 接受摘要 `install/docker-manifest.json` 是私有、限长、禁止 alias 的部署状态，绑定
image ID 与构建合同，不能充当研究数据。候选健康失败或发布失败只回滚本次已确认归属的
容器；共享研究数据、独立凭据与旧接受镜像保留。模式提交失败恢复旧接受摘要字节。
显式离线 repair 只可非 force 移除已证明停止且归属正确的旧容器，不删除其镜像或挂载数据。

双运行时不复制或分叉研究事实：Native 与 Docker 依次 bind/读取同一 `~/.research-workbench/research-web/`，会话、附件、DataHub 快照和产物仍使用下述相同文件合同。模式切换先停止并确认旧模式退出，禁止并发写。Native PID 账本保留自身 `run/` 路径，认证与构建锁沿用既有产品 `runtime/` 目录；Docker 运行状态、认证及启动器生成的 `build-lock.json` 位于容器 `/state/runtime` 私有 tmpfs，每次正常启动重建。宿主 `run/docker/<installation-id>/logs` 仅用于持久日志 bind，旧宿主 `runtime/` 内容原样保留、不迁移；Docker 凭据仍单独存入 `secrets/docker/<installation-id>/` 并 mount 到容器，Native 系统 keyring 不自动迁入。安装摘要分别记录 Native 与 Docker 事实，不能互相证明健康。卸载默认保留数据和秘密，任何清理需独立授权及备份。

Web 安装清单位于 Research Workbench 私有数据根的 `install/manifest.json`，只保存代码/依赖版本与
摘要；CJPY wheel、Web 锁和 DSH 闭包均以哈希核对。清单和安装日志不保存 `CJ_KEY`、模型密钥、
Cookie、环境变量值或用户文件正文，也不改变会话数据集/产物目录。

Gold 与 Dollar 快照分别位于产品数据根的 `frameworks/gold/` 和 `frameworks/dollar/`，采用各自严格 schema（Gold V2、Dollar V1）、内容 revision、2 MiB 上限和同目录原子替换。路径解析前拒绝任何现存符号链接组件；识别到旧 Gold V1 结构时先保留单份 `snapshot.legacy-v1.json` 再安装确定性 seed。框架快照不进入 Automation 事实索引、会话正文或资产数据集。

Phase 2A 另在 `<RESEARCH_DATA_HOME>/mcp-registry/` 保存非敏感 Registry 索引以及按 Registry
隔离的原子缓存。官方 `/v0.1` 的不透明游标、ETag 与同步时间只随成功结果提交；网络或上游失败
只把最后成功缓存标记为 `stale`，不会用空结果覆盖。缓存目录元数据经过 schema 校验和长度限制，
以 Unicode plain text 保存名称、描述、包/远程元数据，拒绝控制字符和 surrogate，不保存 HTML entity
编码。Bearer/OAuth 秘密不进入这些 JSON、会话、资料快照或日志，而由系统凭据库服务
`ResearchWorkbench.MCPRegistry` 持有。

Phase 2B 在 `<RESEARCH_DATA_HOME>/mcp-runtime/` 保存不可变安装清单、安装状态、启用清单、
工具 schema/风险策略、会话授权快照和人工审批元数据。短期确认令牌绑定完整规范摘要并防重放；
本地包只从已验证 staging 原子发布到独立安装目录，远程目标只保存规范化端点。环境变量值、
OAuth token、清单完整性密钥和 loopback 控制密钥分别由 `ResearchWorkbench.MCPRuntime` 系统凭据
或私有控制文件持有，不进入清单、会话快照、浏览器响应或日志。删除安装前必须停用 Runtime；
健康失败保留安装记录并原子恢复上一份启用清单。
PyPI 安装使用 staging 内的私有 home、临时目录和缓存；当精简解释器没有 pip 而宿主已有 uv 时，
额外使用 staging 下的 `.uv-cache` 并禁用用户级 uv 配置。该回退不会新增持久数据类别，也不会读取
用户缓存、改变清单或放宽离线 wheelhouse 边界。
staging、安装 payload、清单与确认令牌重放目录在 Windows 上以目录类型、符号链接和重解析点
作为结构证据，不使用 POSIX mode 投影代替 ACL；POSIX 仍要求 group/other 无权限且目录属于当前用户。

Phase 2C 在同一本地数据根中原子保存 Automation、AutomationRun 和非敏感投递渠道投影。任务记录
锁定目标种类、ID、版本、内容 SHA、输入模板、工作空间、输出格式、允许的 MCP 工具快照、日程与
投递引用；Run 只保存计划时间、触发类型、会话 ID、研究/投递状态、稳定失败码和重试关联。渠道
URL、SMTP 密码与 Webhook 签名秘密由 `ResearchWorkbench.Delivery` 系统凭据库持有，不进入 JSON、
浏览器响应、会话或日志。默认外发仅含状态、摘要和本机会话链接；产物引用须逐任务显式开启。

## 一个数据服务，两种消费者

DataHub 是 FastAPI 进程内的后台“数据总机”，不是用户直接运行的第四种能力，也不是新服务。Web 通过“能力中心 → 数据”浏览 15 项业务数据能力、22 个登记来源及其绑定矩阵；其中 21 项是远程数据源，`local_cache` 是兼容的本机投影。DSH 通过品牌无关的 `datahub_*` 业务 Tool 取数。通用 MySQL 配置与会话文件位于当前设备数据根，密码由系统凭据库隔离；15 个稳定业务 Tool 常驻 Research Runtime，Broker 在每次调用时按最新状态选源，无可调用 Provider 时返回明确错误。

统一连接中心由 `datahub/connection_center.py` 汇总来源声明、非秘密配置、系统凭据存在性、平台能力、最近探测和 Runtime 适配状态；`datahub/connections.py` 仅原子保存 `<RESEARCH_DATA_HOME>/connections/` 下的非秘密 JSON，秘密通过系统凭据库按规范化 data home 服务命名空间和来源/账号键隔离。`datahub/probes.py` 执行有界诊断：Wind 沿用本机登录会话，iFinD SDK 探测登录后在 `finally` 登出，Excel 与插件只有实际心跳或工作簿探测才能标记可用。保存配置或检测成功都不自动等价为 Provider 可调用。

旧环境变量迁移先返回只含“是否存在、冲突、目标来源”的预览；执行时要求来源白名单与二次确认，先写入并回读系统凭据库，再原子清理 `.env` 对应项。配置文件、凭据或 `.env` 任一步失败时恢复原始字节、权限和旧凭据；DSH 模型密钥不进入该流程。

会话软删除不改写任何资料或文件，墓碑保留期为 30 天。永久删除必须先由 DSH 确认原生根会话及其级联子会话已删除，随后 Workbench 才删除该产品会话目录中的附件副本、数据集快照、产物、`.control/calls/<session>`、`.control/snapshots/<session>` 和索引记录；若原生确认失败则保留全部文件与墓碑供后台重试。会话内已发布能力快照保持只读封装；清理时仅为产品根目录内的真实目录恢复所有者写权限，不跟随符号链接。文件系统清理失败会保留带 `native_deleted_at` 的墓碑，后续重试不会重复调用 DSH。DSH 内容寻址的全局附件对象可能被多个会话共享，不在单会话删除中误删。

全局 Artifacts 目录只枚举未软删除会话；显式访问已删除会话仍返回 `410 session_deleted`，恢复后才重新进入目录。Artifacts 错误属于研究会话页面，资产观察既不请求该目录，也不继承此前页面的错误状态。

目录读取只访问 `datahub/catalog.py` 的静态声明，不实例化旧 Connector、不联网、不启动 Excel，也不产生供应商费用。目录分别展示代码存在、完成适配、配置齐备、依赖齐备、允许调用和最近健康状态；只有完成 Provider 适配且满足条件的绑定才进入自动路由。东方财富基金和财联社可直接调用；天软 CJPY 已实现证券目录、交易日历、历史行情和实时快照 Provider，但本机缺依赖或授权时保持 `blocked_dependency` / `blocked_config`，其他登记能力不会借来源级状态冒充已实现。

现有 Provider 闭环补强不改变该目录、Broker 或快照拓扑：AKShare 探针改用固定域名、10 秒总墙钟可取消异步流和 16 KiB 上限的真实交易日历请求，并与业务查询共享容量门闩；天软将精确的 `cjpy==0.5.2` 保持为厂商可选依赖，厂商 wheel 由离线哈希锁约束，实时快照只查询上海时区最近 14 天，历史类请求要求真实合法且正序的日期；MySQL 按驱动缺失、认证、权限、库缺失、忙碌、网络和 TLS 映射稳定安全错误码。三类 Provider 都只记录安全码和异常类型；天软还会拒绝响应的键或值中的当前 Token 反射，不把 SDK、数据库或网络原始错误正文写入日志、快照或 API。公共来源的真实成功不替代天软 Token/许可或 MySQL 可达只读测试库的逐项外部验收。

Wind DataHub Provider 只把已登记的业务能力、数据集、字段、日期与复权枚举映射到现有
`WindAdapter` 方法；请求不能携带公式、表达式、文件路径或凭据。行情、快照、指数、财务和市场
活动仅在口径可证明等价时返回固定字段、类型、单位和日期映射的标准 `BusinessResult`。指数只登记
可真实执行的实时行情 `quotes` 子集；宏观/利率与基金持仓在现有适配器没有等价方法，因此不登记为
Wind 已实现绑定；现有 `fetch_block_trades` 是龙虎榜而非大宗交易，也不纳入市场活动数据集。
DataHub 只把 xlwings/Excel `WindAdapter` 视为依赖就绪，`client_api` 偏好或仅有 WindPy 不会令
Runtime 暴露必失败能力，Wind binding 市场固定为 `.SH`/`.SZ`/`.BJ` A 股。自动查询每次使用隐藏
独立 Excel 应用和专用 workbook，finally 不保存关闭，绝不选择用户当前工作簿；同步调用在容量为 1
的 worker 中执行，18 秒 deadline 后仍保持单飞直到 Excel 返回并完成清理。quit 无法确认时保留
client 所有权并 poison Provider 至进程重启，不再实例化 Excel。响应逐行核对证券身份
和请求日期，未知返回列、关键字段全空、越界日期、未登录、SDK 方法缺失和超过
5,000 行的响应均失败关闭。Wind `market_bars` 与 `market_snapshot` 只支持显式 `asset_type=stock` 的股票，指数继续走
`index_data` points 映射；日线行情、资金流与融资融券在 adapter 初始化或可用性检查前验证起止
日期并限制最多 60 个日历日，不从返回代码或代码外形猜测资产类型。请求字段部分缺失或历史响应
未覆盖请求终点只返回 partial，不把供应商截断误报完整。
5,000 行分别失败关闭，不回退其他来源、不截断也不制造数据。

上游仅接受注册来源 ID 和能力限定参数，不接受任意 URL、模块、路径、请求头或凭据。`datahub/broker.py` 先按能力绑定、启用状态和覆盖条件筛选，再选择单一 Provider；显式来源默认不静默换源。访问边界限制域名、重定向、体积、时长及取消；请求失败与空数据不同，返回状态、原因、尝试来源和实际覆盖。原始响应留在私有区域，解析数据以 JSON/CSV 和 Manifest 保存至当前研究可读资源目录。

桥接上限为 22 秒；AKShare 与天软同步 Provider 在 15 秒内返回终态。超时写出 `failed/deadline` 快照而不是顶层活动异常；第三方同步调用若仍在运行，每个 Provider 的单线程门闩让新请求快速返回 `failed/provider_busy`，避免排队和线程累积。Python 不能强制终止已经进入 SDK 的线程，因此该线程仍会运行到供应商调用自行结束。

主任务准备资料后，子 Agent 读取同一组数据集引用。升级 FinGPT → Claw 时复制并验证目标会话资料，保留 origin dataset / manifest hash 与新 ID 映射，避免让新会话访问旧路径。

## Report Workflow 的 Excel 与文件链

具体报告的 Word/PPT 模板、Excel 底稿、映射、校验规则和交付格式属于不可变 Workflow 版本。运行先复制母版到独立 Run 目录，再由 `report_workflows/workbook.py` 串行控制本机 Excel：检查声明的 Wind/iFinD Provider，刷新、完整重算、等待稳定、保存并产生刷新 manifest。插件未登录、公式错误、日期或必填项不合格、异常零值和超时均进入 `blocked_data`；没有显式字段及口径等价映射时不使用 DataHub 或旧缓存替代。

`integrations/` 内的协调器只保存不含秘密的状态证据：启动先恢复原子快照，再异步探测；数据源和本机设置页的“重新检测全部”会创建真实批次。配置或环境指纹变化使旧证据过期，但保留最近成功时间。账号、终端和可能计费来源必须先取得逐来源自动探测授权。

`report_workflows/tooling.py` 只从刷新后的运行副本提取有界内容，并一次性生成 `report-data.json` 共享快照及 SHA-256。Claw 父任务和至少两个真实子 Agent 读取同一快照，不重复刷新。模型只负责生成会话自有的 `report_payload.json`；即使 Claw 提前创建了同名 Office 文件，Report Workflow 也必须经 `report_rendering.py` 与 `report_render_script.py` 做确定性模板组装，再由独立交付检查重开文件、检查 HTML 非空、占位符、数据日期和文件哈希。PPTX 占位符按段落合并 `<a:t>` 文本片段后替换和检查，跨文本片段的残留同样会被拒绝。Payload 可按 `*_blocks` 家族组织，但显式 `missing` 始终优先于解释文字：缺失区块可显示原因，不能因此通过完整交付门禁。Claw 回合结束只进入交付检查，缺 Payload、投影失败、必需区块或约定格式时保持 `delivery_incomplete`。

本机集成的 Wind 真实验证不读取报告 Workflow 母版，而是在独占空白工作簿中执行最小厂商公式；报告刷新由各 Workflow 按自身资源、校验和时限独立判断。iFinD HTTP 探测继续读取 DataHub 的非秘密配置与系统凭据库秘密，按登录、健康、最小只读查询、登出的顺序执行，响应和日志均不包含令牌。

如果 Payload 晚于父回合结束才写入，重试仅在当前会话和当前 Run 的文件边界内查找新建或更新文件，直接恢复确定性组装，不再刷新 Excel 或重启 Claw。旧历史产物、附件和运行前已有文件均不计入本次交付。

## 资产与主题查询及快照交接

`workbench.py` 为资产观察、基金数据和研究情报中的主题检索提供既有产品 API。前端取消研究台主导航，但查询持久化的 `assets/funds/market/industry/documents` section 与 HTTP API 保持；新闻、研报、公告分别映射原 `market/industry/documents`。页面打开只读取目录、历史查询和资产个人观察；上传材料、数据集与生成文件从来源会话查看，不再展示跨会话文件总览。用户提交后才创建源会话并调用 DataHub；查询状态与幂等键写入产品索引，最终数据仍以 DataHub manifest 和文件为准。

“交给 FinGPT / Claw”先验证所选 dataset 确实属于来源会话，再新建目标会话，将选定 dataset 逐文件复制并复核 SHA-256，最后把页面筛选、来源、截止时间和 dataset 映射写入 `inputs/page-context/`。页面上下文上限为 64 KiB；查询与交接分别通过幂等键及准入锁防止并发重复创建。交接不重新联网，不创建符号链接，也不让目标会话读取源会话路径。

基金数据使用 `fund_data` 的基本资料、净值、分红和披露持仓四类查询，不借用股票通用区块。恢复历史查询后，交接上下文从该查询实际 manifest 恢复参数、来源和截止时间；当前未提交的表单不能替换快照原上下文。页面按归属隔离异步结果，迟到响应不覆盖其他视图。导航迁移不改写查询、快照、自选、笔记、提醒或模拟记录，不增加资产与研究产物关系。

模块依赖图和研究时序图继续描述同一 Host/DataHub/DSH 调用链；图中“研究台查询与快照”是沿用 `workbench.py` 的兼容模块称谓，表示本节查询/交接链路，不代表仍有研究台主导航。前端路由投影重分组没有新增服务、存储或执行关系。

资产观察通过 `ui/asset-workspace.mjs` 恢复为独立产品入口。概览、历史行情、财务、资金与交易事件、公告、新闻、研究资料、同类比较、主题暴露和来源口径逐块保留真实状态；历史行情有数据时显示 OHLC K 线、MA/BOLL、成交量、成交额、MACD、KDJ、RSI、换手率和细行情栏，技术指标仅在浏览器内由当前 DataHub 快照确定性派生，不写回或伪装为来源字段。DataHub 标准行的 `turnover` 是成交额，`turnover_rate_pct` 是换手率；UI 分别映射并对缺失值保持未知，不在两个口径间回填。AKShare 财务摘要的布尔缺失哨兵在 Provider 规范化时写为 JSON `null`；历史快照仍可读取，但财务表按缺失值显示 `—`，不会改写原不可变文件。自选、观察笔记和提醒仍存放在 Research Web 数据根，不依赖旧 PostgreSQL，也不恢复旧 Agent 委员会、信号、情景或回测链。

## 报告 Workflow 资源与迁移

具体报告不再放入研究台的通用“报告页”。`report_workflows/` 管理每篇报告的不可变版本、资源、运行和日程，`report_workflow_routes.py` 提供产品 API，Claw/DSH 是唯一研究执行引擎。Word/PPT 模板、Excel 底稿、映射、素材和交付规则属于该 Workflow 版本；每次运行复制到独立 Run 目录，不能修改母版。

启动迁移优先读取 `~/.research-workbench/research-web/report-projects/` 中已经管理的原项目；只有该目录无项目时才回退仓库旧目录。迁移对每个文件核验类型、路径和 SHA-256，拒绝链接与越界，支持 dry-run 和幂等重复执行。当前实际目录包含创业板50周报、华安ETF周报、华安ETF投资风向标和 AI 周报；前三者已发布 v1，AI 周报因资源不完整保持 `needs_attention`。历史产物只建立只读索引，不伪装成新 DSH 运行。

Excel 刷新由受控 `workbook_refresh` 逻辑在运行副本上串行执行。Provider、登录态、公式错误、数据日期和必填单元格校验失败时进入 `blocked_data`；只有 Workflow 明确声明等价映射时才允许 DataHub 备用，不能按文件名猜测公式来源或静默切换口径。

详细已实现来源和口径见 [DataHub 模块](../../research-web-datahub.md)。来源截止时间、报告期、抓取时间、请求与实际范围、分页结束和覆盖不足必须分别保留。数据集存在不代表资料完整。

## 文件安全边界

上传支持 PDF、图片、Markdown、CSV、XLSX，单文件 30 MiB，每批最多 20；模型图片内容另有单张 8 MiB / 合计 16 MiB 限制。上传成功不是模型已阅读证明。

文件 ID 和会话归属由索引解析，不接受浏览器传入任意磁盘路径。服务通过不跟随符号链接的目录描述符安全读取；跨会话、路径穿越、链接风险应拒绝。

研究脚本只在当前会话 outputs 写入，在 inputs/resources 读取。使用本机已验证的内核限制及环境白名单，不能因创建/import Skill 获得更多宿主、Shell、网络或依赖安装权限。

HTML 产物使用无同源权限的 sandbox 预览与限制 CSP。下载不执行文件。应用凭据不得暴露给生成页面。

## 独立交付状态

`delivery` 是会话详情中的独立字段；不是 DSH 的运行状态。

| delivery.status | 条件 |
|---|---|
| `pending` | 已受理但父/子任务未结束，或尚无完整确认条件 |
| `admission_unknown` | 受理收据 pending/unknown，等待原生日志关联 |
| `not_required` | 本任务未要求文件 |
| `completed` | 所有要求格式都有本次新增/更新且验证有效的文件 |
| `incomplete` | 有要求格式缺失或文件无效；保留有效部分及缺失原因 |
| `verification_failed` | 沙箱检查失败、文件太多、文件变化、响应无法验证，或明确停止且父子任务已确认空闲但缺少原生终止事件 |

提交前记录 outputs 哈希基线。只检查本任务新建或哈希改变的输出，不把附件、历史文件或聊天文字当作交付。候选解析限单文件 16 MiB、每会话 100 个输出；Office 文件须实际重开且包含内容，XLSX 须有表头和数据行。解析在严格沙箱完成，发布前再次核对文件大小/哈希，防止检查后被替换。

`required_formats`、`missing_formats`、`files`、`reasons` 和 `checked_at` 支撑界面展示。格式检查不能证明数值、引文或研究结论正确；研究质量仍需使用者复核。

停止异常复核直接记录失败原因，不解析文件；只有完整原生结束证据才进入实际文件校验。收据内部的停止意图不暴露给模型或浏览器，错误码与解释可见。详见 [交付实现](../../research-web-delivery.md)。

来源：`delivery.py`、`delivery_validation.py`、`store.py`、`sandbox.py` 和 `datahub/`。既有协议、文件安全、取消、自动工具过滤、数据快照与真实文件验收在本次 UI/能力改动后需要重跑。

产品索引和 Report Workflow 目录的文本元数据固定使用 UTF-8 读取与原子写入；Windows 默认代码页不得改变中文内容。文件归属、目录结构、原子替换和单 worker 边界均保持不变。

DataHub 控制文件、调用收据和会话快照在 POSIX 继续使用目录描述符和 `NOFOLLOW`；Windows 使用规范化路径回退，并拒绝重解析点、非普通文件、硬链接、越界路径、超限内容及打开前后身份变化。Windows 快照继续以同目录临时目录和原子改名发布，目录 `fsync` 明确跳过；此修正不改变会话快照格式。

DSH 认证控制文件在 POSIX 继续要求私有 mode；Windows 不把 POSIX mode bit 当作 ACL 证据，而是校验普通文件、单硬链接、大小、重解析点及打开前后身份。下载采用相同的 Windows 身份核验。永久删除只在产品根内恢复真实目录和普通文件的所有者写权限，不跟随链接或重解析点。

连接配置仍先刷新临时文件、关闭句柄并原子替换。POSIX 随后刷新父目录；Windows 明确跳过不支持的目录 `fsync`，不把跳过记录伪装成持久化成功证据。

三个 Phase 2 功能默认开启只改变服务装配条件，不创建虚假目录记录、安装清单、授权、Automation 或交付渠道；对应事实仍只在用户显式操作成功后原子持久化，环境变量设为 `0` 时保持原数据不变。

Method 的会话证据独立写入 `<session>/.rwb/method-trace.jsonl`，单行只含 `method_id`、`version`、
`source`，文件总量限制 64 KiB。Runtime 使用 no-follow 文件句柄、普通文件检查和同步写入；产品读取
同样拒绝链接、异常类型、超限或无效字段。该文件不是研究正文、产物或数据快照，不进入跨会话共享。

## 2026-09-23 稳定性变更回执

本轮重启活动授权和目录读取有界化不新增或迁移持久数据。会话索引、资料快照、附件、产物、交付
收据、能力版本、Automation Run、系统凭据库和清理语义均未变化。各目录独立的 pending count、
generation、逐资源 settled 和 latest-request-wins 都是内存请求账本；只有 runtime 的 pending/settled
failure 会投影为可见 connecting/offline，且不会写入新的缓存或文件。数据文件关系和相关架构图保持不变。

DataHub 连接凭据以公开 canonical data home 的 SHA-256 后缀隔离系统服务；账户标识与非秘密 JSON 保留。旧全局服务不读取、不复制、不删除，升级后需在所属实例重新录入；旧记录可供旧版回滚，不写秘密备份。

## 设置闭环阶段3：当前能力范围

DataHub快照增加非秘密authorization_fingerprint，来自配置、实例命名空间和原子配置文件身份，不读取或散列秘密值。旧快照留作审计；新查询/回执/缓存重用须重检当前授权与配置版本。脚本只获当前准入版本和已授权dataset目录；旧resources/skills和全集版本快照不可作为执行许可。


## 单一兼容模型连接

兼容模型连接只在产品状态中持久化非秘密字段和公共revision；秘密仅存于实例系统账户RESEARCH_COMPAT_API_KEY，与原RESEARCH_DSH_API_KEY分离。地址变化不继承旧Key，文件/环境不作为模型回退。GET model-connection复用私有鉴权通道，不返回秘密；数据快照与商业数据账户合同不变。

Docker 持久数据与私有凭据挂载保持既有归属检查；Windows DACL 未验证继续阻断。Office/Wind/Tabbit 宿主能力不会因挂载可见而开放，跨模式不隐式迁移秘密。

## 结构化Office文件操作

现有报告执行器承接会话document-operations：读取已登记文件，生成新文件或按有限段落、单元格、文本对象目标修改副本。输入来自Store安全文件身份；原生执行未接通时明确unavailable，不用文件结果冒充原生成功。文件模式沿既有Seatbelt sandbox，无新增宿主文件/子进程/网络权限。

Word复杂字段/对象/修订及多段表格单元格拒绝修改；Excel文件模式保留公式但显示not_recalculated；PPT以presentation关系定义展示页序，文本对象按shape ID定位，保留未改页原始字节及被改页命名空间，生成须有登记模板。处理范围仍需真实产物及页面验收，ZIP片段合同不能证明PowerPoint可打开。

写操作先落本任务独占暂存文件；完整响应及输入指纹复核通过后，以不覆盖的发布方式接入原outputs下载目录。输出冲突不覆盖已有文件；失败暂存不成为可下载成功产物。日志只记录格式、操作、状态和异常类型，不记录文档内容。

普通会话文件面板现在提供三格式生成及有限局部编辑表单。Word/Excel通过结构化字段生成；PPT缺省复制`office-template.pptx`中性两页布局，也可使用已登记模板，生成内容匹配标题/正文对象ID2/3，不承诺任意模板的语义槽位兼容。该资源一次构建后随产品源码交付，产品不依赖开发机python-pptx。模板变更和布局可用性仍须实际PowerPoint验证。

原生模式由同一文档业务入口委托现有LocalIntegrationManager和受监督工作进程，不进入文件处理sandbox，也不开放通用脚本或路径接口。Word仅支持简单标题/单行段落及单表格，编辑只写选中目标；Excel使用已准入副本的独立实例、真实重算与重开值，PPT使用受控单文件系统打开及原地保存。可用性、功能结果和清理分别记录，失败不能发布产物或改称文件模式。既有Host、Store、报告sandbox及本机执行边界保留；新增的是有限操作合同及连线，未新增后台服务或通用Office平台。

Runtime私有文档调用的等待边界与执行边界分开：文件模式仍为35秒；原生模式等待195秒，覆盖Host既有180秒执行及10秒协调上限，并留5秒传递结果。该等待不会延长Host的10秒准备、30秒单步及190秒监督总限；调用者取消信号仍合并进入请求，不授权额外执行或自动重试。

Word原生新建使用专用save-as接口并显式选择DOCX格式；HFS文本路径在进入Word的tell上下文前从受控任务路径转换。转换语句放在Word上下文内的真实只读探针曾返回空值，不能把这种空参数交给保存接口。该接口合同和上下文测试不替代实际保存/重开/读回证据；失败继续记录原生错误及独立清理状态。

Word单文件交接沿已有PowerPoint模式通过正常LaunchServices打开受控副本，按完整HFS路径与saved状态确认归属后才使用文稿引用。原生新建先准备不含请求内容的空DOCX作目的文件交接；关闭该空文稿后，Word自身执行make new document，再写入与保存。空交接文件不计作原生新建或功能通过。原始输入仍保持不变，未验证引用不关闭，共享Word不退出；交接、真实创建及最终读回均须各自有实际证据。

Word目标段落/单元格的多run只有rPr规范化字节完全一致时允许编辑，真正混合格式继续拒绝，不忽略字体、语言或其他属性。Word段落集合计入表格行结束段落，映射同时计数XML段落与表格行；段落写入范围排除结束标记，以保留后续表格和段落边界。标题读回从段落取得样式对象，与该文稿内置Title的本地化名称及built-in标志比较；区分大小写的比较在Word tell之外，原加粗及全量内容校验保留。
staging 修复只作用于镜像只读发布资产，不删除或迁移产品数据、凭据及 Native 目录。包根开发目录与深层运行时代码区分，文件内容和 manifest 哈希继续逐项绑定。

正常 Hot Native 模型使用配置指定的已有 model_budgets scope，累计额度不会随重启/日期改变。input-v2 缓存身份仅绑定模型参数、输入和提示版本；旧价格身份的回执和未知尝试在同一 schema 栅栏查询，预留前原子复查。历史回执 resultKey 和原费用记录保持原值，不转写或退款。当前联合研究快照备份仍未完成。

迁移14新增不可变 model_control_requests，保存 UUID、操作者、理由、输入 hash、前后状态与响应。模型尝试增加 abandoned；保留费用和唯一输入阻断，只有已有 receipt 才可进入 received。累计预算不因重复授权而重置。定价配置、研究快照联合恢复及恢复后的预算核对仍待完成。

用户定价保存 hot/pricing/YYYY-MM-DD.json 与内容hash归档；原记录保留，当前指针原子发布。目录/文件 private 属性及实例/项目绑定校验；已可见但目录fsync失败的回执带hash和durability unavailable，重放补验。其备份/恢复整合仍待完成。

浏览器旅程读取原PG不可变版本而非复制数据，展示发布时间与取得时间分离、未知发生/生效时间、原文hash与频道判断。准备/恢复保存非秘密来源基线、预算快照和清理回执；不把临时框架采集输出计为Hot原文或研究快照。

Migration15增加briefs head、不可变brief_versions与brief_requests。版本保存冻结输入/哈希，UUID参数hash与版本映射同事务发布；既有材料/原文/模型账本不变。内部signed读取复验完整性，后续仍需研究原文副本与联合恢复。

简报网页预览只读取保存的payload。Markdown文本哈希不同于冻结payload哈希；Node分块读取精确正版本，Host有界组装/核验后才发送完整附件，失败不发送部分文件。导出不写Store、不生成研究会话、不改Hot原文，未知创建仍重放原UUID。

原验收库现保存浏览器生成的两份真实简报version1，内容hash与实际下载字节分别核对，刷新不会新建版本。测试基线按proofId隔离且写一次；失败恢复保留FAIL与独立角色收尾状态，实际预算账本不因故障注入或重跑重置。

### Office 两条能力与任务清理的页面投影

本机设置页在 Word、Excel、PowerPoint 各自行内分别显示文件处理和本机操作。文件处理的固定 capability 标记仅表达 Mac 文件业务所需的项目依赖/内置模板就绪，操作仍受既有文件身份、有限内容、版本检查及沙箱约束；不从 Office 安装、授权或模型生成结果推导。其他平台保持未验证，不新建后端或文件回退。

本机操作沿既有显式验证与有效期判断；过期或实例状态变化保留最近时间和失效说明，不提升授权或可调用。最近有效验证只将既有安全诊断的最后完成步骤、功能和清理结果投影到现有 detail，不增加持久协议、路径或秘密。普通刷新不启动 Office。文档业务结果同时显示清理已确认/未确认/失败/未创建，下载产物和功能状态独立保留；没有清理证据时明确未确认。该展示不更改原生执行、保存重开、取消或归属边界。


## 研究情报统一入口 · 2026-10-12

主导航统一为“研究情报”，本地热点与事件在 `#/intel/hot`，六个外部栏目在 `#/intel/*`；新闻/公告旧地址保留证券参数转入资产观察。旧 `#/workbench/hot` 链接保留视图/事件参数后转入本地页。两类页面共用栏目导航、主题与Host；本地版本证据和Golddata外部只读数据保持身份与覆盖来源区分，外部读取不写Hot、领取任务或调用模型。Hot未启用时，外部栏目与设置继续可用。

恢复的DOCX切片通过 `GET /api/research/hot/briefs/{brief_id}/docx?version=<固定版本>` 从签名/哈希核对的冻结输入生成并保留私有产物，复用报告DOCX生成器；导出不创建会话、不调用模型、不外发。该路径尚需完整产品/恢复验收，局部测试不代表研究闭环完成。


## Hot完整已存储原件冻结 · 2026-10-12

研究输入先固定简报ID、正版本及所选材料ID。Node在只读一致快照中取得对应不可变材料版本及原始响应，核对版本内容哈希、原URL身份和截止时点，并保存完整存储文本；后续更正不回填旧输入。清单绑定逻辑实例、简报哈希、频道判断和截止时间，每个原件有独立字节数与SHA256。RSS响应不等于链接网页全文，同页其他条目不扩充选材。

私有签名RPC的清单和原件均按32KiB分块。Host保留生产者规范JSON字节，避免Python/JavaScript小数重序列化差异；另核对原简报锚、实例、材料选择、文件名、偏移和最终哈希，整个重建有15秒期限。超限/取消/缺页失败，不发布部分文件。当前产物仍为内部冻结输入，尚未放进DataHub会话目录；接下来必须使用真实目标会话及既有私有快照目录校验，不能虚构来源会话或引用可变库记录。


## Hot会话原件副本与运行映射（schema16）

PG research_inputs在任何原生副作用前保存固定输入、规范清单字节/哈希和预留session UUID；research_runs仅按版本CAS推进，research_operations保留请求/前后状态/代次/回执，输入与审计不可改写。唯一迁移/业务写入所有者仍为Node，worker无这些映射写权限。

Host在既有Store保留匹配的hot_origin，再调用现有DSH session.create/selectModel/rename。创建未知时先查固定原生ID；存在且归属一致才确认，未知缺席不自动重发。只有取得原生创建确认的目标会话可发布Hot证据。DataHub以hot_evidence快照种类直接保存固定原件；不伪造Provider查询或来源研究会话。

public inputs完整写入并fsync后，private快照UUID目录才作为目录提交标记。确定性dataset ID、固定准备记录和逐文件哈希支持同请求重放与公开目录已发布/私有未发布的中断恢复；错误/异名内容拒绝，不覆盖既有资料。普通copy_selected/升级也复制这些独立原件，取得时间不改成复制时间。Hot原库不依赖研究会话存活，删除会话不删除Hot原件。


2026-10-13续跑：Snapshots.admit_hot_script核对created/purpose、run/instance/manifest和私有快照文件hash，安全FD有界读取最多40个原件后validate_bundle；仅许可会话所属资料副本，不引用可变Hot对象。


Hot报告固定绑定PG deliveryKey，核对读取原RWB_HOT_EXECUTION回合，不使用会话后续任务的交付或终态。当前文件SHA须在完成状态条件提交前核验；pending通过原严格沙箱校验，未核对不能判失败。Word由已校验MD确定性转换并复验来源hash。

当前报告核验沿用Delivery的最多100文件、每文件16MiB合同，64KiB分块哈希；不按5文件或累计16MiB截断后推导失败。联合归档的选定会话metadata计入64MiB展开总量，最终ZIP也须在同上限内才签成功manifest。PG inventory直接保存规范JSONB文本的哈希，encoding为postgres-jsonb-text-v1；旧JS数值inventory存在不可逆碰撞，旧档保留但自动恢复拒绝认证，要求从原库用新版重新备份，不能仅重签旧manifest。

ReportLab 初始化需读取当前目录；PDF helper 在已授权输出目录初始化，再恢复工作目录，未增加沙箱目录授权。底稿 JSON 在三份唯一产物生成并重开后以临时文件替换发布；质量还要求独立交付验证哈希一致。

## 历史子会话模式兼容 · 2026-10-13

不会删除或重写旧子会话数据来修复列表。父历史与会话文件保持原归属读取，子历史在执行模式未知时明确不可用。

PR96 与既有 Fernet 模型桥共用唯一私有 stdio 接口；默认 `native-keychain`、常规 staged `docker-encrypted-file` 语义保留，管理器仅显式绑定 `docker-encrypted` 选择 AES-GCM。两种 Docker 格式与主密钥布局独立，混合绑定或外来格式失败关闭，不转换密文、不删除旧 Key、不回退。四操作与固定 ref 保持；来源如实区分，configured/Doctor 不证明真实生成。

AES 载入检查每个 JSON 的 canonical 外层记录、完整封装、版本/实例及固定 namespace/ref 文件名，并认证密文；正确旧树只读通过，外来/未知记录拒绝且保留原字节。

## 受限CSV计算证据

结构化research-report.json可选calculations，最多4项，每项精确包含id、source_id、source_sha256、operation、weights、terminal_shocks。source_id为当前允许input的file:ID，source_sha256为完整实际文件摘要，不是12KB摘录摘要。operation目前仅buy_and_hold。权重列1至8个，非负且精确和为1；冲击列必须属于权重列，区间[-1,1]。不接受其他字段、路径或代码。

Host按CSV行序（不推断日期）归一化首行价格，计算静态初始持仓组合收益、路径最大回撤、仅修改末值价格的情景收益及行数。固定规范列序，Decimal精度34、ROUND_HALF_EVEN，比例结果固定10位小数，period为完整输入样本，单位ratio；行数单位行。正有限价格在1e-18至1e18，数字最多64字符且指数绝对值不超过30；超出计算可表达范围失败关闭，不截断输入。

Host观测ID由隔离scope及输入/配方SHA生成；模型不能声明可信观测。research_check_quality返回真实quote、value、period、unit和来源绑定，模型在原补查预算内据此完成自己的numeric_claims、notes、coverage与有证据的叙述；不自动替模型填写或消除缺口。原严格验收器保持。

模型可显式调用 `research_report.calculation_evidence(observations, requirement_ids, methods_requirement_ids=[])`，将同一配方四项实际Host观测序列化为sections、notes、numeric_claims和coverage。指标到冻结要求的映射由作者提供，例如 `{"total_return":["r1"],"max_drawdown":["r2"],"terminal_scenario_return":["r3"]}`，方法要求另传 `["r4"]`。每个指标包含独立章节，claim、operand.quote和正文逐字引用观测第一行，方法节引用原换行后的说明，避免行数claim悬空或拼接改写引文。多配方须先选取同一calculation_id的四项；混合来源/配方/输入、重复或缺少指标拒绝。

该纯格式helper不读取文件、不生成可信观测、不写missing/quality/research_accepted，不改变Host检查或409下载门。伪造ID、数值、外来会话观测、缺失需求或真实missing仍不能通过。`missing`仅记录真实未完成/未验证事项；合成数据、未年化等既定范围限制应保留在报告说明，不混作已完成要求的缺口，亦不得以此删除真实缺口。

### 实际业务证据预检查

Host还可从本会话实际完整、严格UTF-8、单个不超过12000字节的允许输入生成`business_observations`。它是原observations路径内的有界适配，不读取报告自写观测，不增加网络/表达式求值/路径能力。封闭支持同一年度百万口径/XBRL行表、CPI Table A明确SA月列及NSA十二月列、完整受支持的FOMC官方声明/实施说明版式及肯定决议、显式公告/生效日、完整可枚举的NIST所选记录与功能标题。歧义、缺列、季度冒充年度、交换表头、重复、未知发布前后文、否定/提案/条件、超长或截断均不产生新可信事实。

每条观测保留源文件完整SHA、原文字符位置与原文、算法/字段/值及当前用户根/会话/任务/冻结合同绑定的ID。金额不猜测美元币种；财务cashflow phase和有符号子项须一致，派生公式封闭；CPI不混用季调/未季调；分数利率转换与日期分开。计数仅表示完整所供摘录内的记录或标题，不是完整框架或组织认证。最多200条、180000字节，不能唯一解析时保持未核验。

`business_evidence(selected_observations, requirement_ids)`与既有CSV格式helper一样，只序列化所选真实Host规范句/方法、全部父来源、notes/coverage及identity claims；需求映射仍由作者提出并接受原Host检查，不写missing/quality。模型可在原一次补查内修正草稿对应事实，不用原文外中文推断冒充可核验结论。跨文件claim遗漏任一父来源会判invalid；评分后原文件SHA变化也判invalid且不返回旧观测。质量检查缓存绑定实际证据context，不能因相同缺口重放旧数值。`research_quality.py`的原精确数值/逐句检查保持，不把新规范化当外部真实性、预测或语义评审认证。

报告资源提供纯 Python helper，不增加信任来源或模型循环：

- `canonical_source(host_sources, identity)` 只接受 Host 的准确 ID 或唯一准确标题，返回规范 id/title 和实际提供的 url/as_of；不把上传文件名拼成 file:ID。Facts、Controls、Timeline 的 source_ref 复用规范 ID。
- `evidence_section(id, heading, text, citations, requirement_ids)` 复制作者提供的原文、完整引用、同节 notes 与 coverage，避免漏掉节内来源；不写 numeric_claims、missing 或通过状态。作者仍须覆盖全部冻结要求。
- `build_numeric_claim(id, section_id, text, period, unit, operation, operands)` 按原精确算术计算 value，并提前拒绝错误操作数数量、期间/单位、同句多数量、舍入冒充精确结果。identity 为一个操作数，difference/ratio/percent_change 为两个，sum 逐项列实际操作数。helper 不读取资料或证明引文真实；Host 始终独立核验实际字节、指标标签及笔记血缘。
- `reconcile_amounts(total, signed_components)` 返回有符号子项合计和真实差额；`rate_difference(before_pct, after_pct)` 分别返回 percentage_points 和 basis_points。它们是底稿计算工具，不能把生成文字当成可信观测。
- `numeric_summary(rows, expected, decimal_places={metric: digits})` 仅用于独立验收器：读取 Summary 首个连续数值表，允许全空尾列，拒绝重复键、公式、布尔、字符串数字、非有限值和带数据的额外列；空行后的说明不能覆盖指标。默认精确比较，只有显式登记的展示位数可使用 ROUND_HALF_UP，且仍接受独立期望精确值。此展示规则不传入 Host，不改变研究质量的精确算术门。

原材料无法提供可核验的期间、单位、唯一数量（例如跨列表格、分数利率或文字计数）时，预检查不能把它们伪装成合格 quote。应保留未核验状态与真实缺口。宏观季调口径需同时读取表头，百分比水平与百分点变动分开；政策工具方向不得无依据扩写；治理建议和 not_assessed 不冒充组织实施证据。真实模型的内容、来源和计算声明仍需独立审查，文件下载 200 不是研究通过。

Delivery先检查当前key；FINAL输出集合或字节变化后重新走原sandbox和发布后字节复验。不变的失败不隐式重试，取消/原生执行证明失败不能靠改文件恢复成功。report-versions只属于历史归档，不满足当前任务格式要求；解析中集合改变保留未验证/incomplete，绝不复用旧通过。


### 受任务绑定的便利投影

prepare_contract使用实际允许上传输入，在会话resources/research_evidence.json原子保存schema_version=1、task_id、contract_sha256、sources、observations；无quality、passed或模型设置，最大256000字节。未知资料可返回空观测。它可再生，不是业务数据迁移；旧会话文件不批量回写。SDK load_business_evidence要求固定合同标识并以相对路径只读，避免原生沙箱getcwd和手抄JSON错误。Host评分始终重读原始输入，不读取此副本；副本中伪造数据不能获得信任。

source_references允许纯规范ID列表，或精确的“规范ID · 准确Host标题 · 定位”；定位不参与身份推断，错误标题/外来ID/file:文件名继续拒绝。定位本身的事实正确性仍需独立审查。Decimal参数的算术结果及claim操作数均序列化为精确字符串，不降低原数量、单位和quote约束。

旧网页记录只有as_of值、没有可追溯出版meta/header证据时，当前只读投影保守返回unknown；有正文header但与旧日期冲突时同样保留unknown。旧索引和原文不回写，此状态不能被当成来源已核验；新读取会保存实际出版证据，未来发布日期继续触发原截止日门。

原交付层与报告格式器共用同一task_id的冻结required_formats；显式UI/能力选择优先，deep无选择时才从用户明确格式文本取默认。上下文和Host投影均读取Store中的同一回执，拒绝错任务和未知格式，不能由模型或传入的交付投影减项。
## 网关静态部署的恢复文件

`apply-ui` 使用 version 2 journal，记录产品、工具、双段受限 Git blob 与项目身份。恢复 pyz 按内容摘要独立命名并携带 Git 模块 manifest；离线恢复重新核验对象与文件身份，旧恢复包拒绝新版事务。原数据/模型保全快照和恢复边界保持，禁止用恢复覆盖业务数据。

模型profile为index.json中的非秘密加法索引，包含公开连接字段、物理账号标识及当前路由，不含Key正文。旧会话绑定legacy身份，新的会话与显式选模研究日程保存profile ID；引用存在时拒绝归档，未知凭据提交持久标记，研究文件/报告/资料不迁移。
