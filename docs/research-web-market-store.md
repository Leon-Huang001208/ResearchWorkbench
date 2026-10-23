# DataHub 研究数据仓库内核

terminal-v2指数集合使用独立市场缓存键；既有MarketReader/研究仓core-v1完整12身份和原生封包不改变，不能把24指数塞入旧仓库profile。新浪历史为price_index、实际采集时间first_observed、historical_pit_verified=false；画像可以展示可算特征，但不能据此认证历史PIT、回测或配置有效性。

2026-10-23新增宏观使用现有SnapshotSeries与PostgreSQL适配：官方数值v2和AK中国宏观v1进入各自schema/units身份；不新增表、不连接正式库、不迁移旧记录。范围查询结果以原生响应冻结，首次观测时间与供应商观察期分开，尚不是可按历史披露版本重建的规范宏观事实。字段、原字节、版本与摘要可随导出恢复复现；Broker当前仍拒绝AK宏观as_of，包括库读取，不宣称Host已支持该历史查询。旧显式冻结包保持可读。

2026-10-23：本轮限价、昨日逐股金额和资金日期留存仍在原market-cache，不新增研究仓schema、SQL迁移或默认写仓。已配置的固定12指数仓桥和账号/profile校验保持，公开缓存历史不冒充研究仓PIT事实。 具体来源、缺口与缓存合同见[DataHub](research-web-datahub.md#无会话全市场数据)。

资产历史的chip_inputs扩展只冻结既有Provider返回与同版本价格派生，不启动正式MarketStore、不迁移数据库或外盘，也不在共享仓库写入自有筹码估算。原OHLCV、因子和授权指纹保持；新旧规范版本与取消排空沿原快照机制隔离。

本阶段为 macOS 上的隔离功能开发。`app/research_web/market_store/` 提供可选 PostgreSQL 后端及确定性测试参考实现，不连接现有 5432、不改生产数据库配置、不启动采集、不调用付费来源、不使用外接 ExFAT 盘。生产部署、盘格式/备份、全历史导入和跨平台验收各自另行授权。本模块不是第二研究引擎。

## 数据及身份契约

`StoreScope(owner_id, entitlement_scope, source, config_digest)` 为冻结身份。owner 来源必须为服务器认证上下文；`entitlement_scope` 是许可证/共享批准的非秘密 ID，不能放令牌或连接字符串。`config_digest` 为移除秘密后的来源配置 SHA-256。共享数据使用明确共享 owner 和独立 entitlement scope，个人商业许可使用个人 owner；后端策略逐次核验，不能依据浏览器提交的 owner 自我授权。

`DatasetIdentity(capability, asset, market, frequency, units, adjustment, factor_contract, semantic_digest, metrics)` 将能力、标的、市场、频率、币种/单位、复权/因子定义、语义定义和必需指标一起纳入 key。raw 行情与 adjustment factors 必须使用不同 capability，不能把复权结果回填 raw。因子定义、锚点、财务会计准则、合并/母公司口径、宏观初值/终值、持仓及成分有效期等差异必须进入语义合同摘要及指标/维度。指标集合必须显式列出，只有该日所有指标存在才算覆盖。

`Fact` 是追加式观测，包含 `metric`、`business_date`、`period`、不可变规范 JSON `value_json`、排序后的 `(key,value)` 维度、`available_at`、`ingested_at`、`source_version` 和 `raw_hash`。财务期末日/宏观参考月不是公告日；`business_date/period` 保留业务期间，真实公开日进入 `available_at`。入库时间不能推定为公开日；不知道公开日就存 `None`。JSON 数值须有限；需要十进制精度时存字符串并由语义合同声明。每个来源版本的同一逻辑观测不可改写；修订追加新 `source_version`。同时间不同值且无法排序的修订拒绝读取，不能任选一条。

语义时间入模型时统一为 UTC：Fact 的公开/入库时点、CoverageProof 的公开时点和读取 cutoff 均按同一瞬时规范化，身份摘要与 Python 时间判等一致。原件中的原始时区文本/响应字节不变。同批次出现 UTC／+08:00 表达的相同观测/证明会去重，跨批次重复也不推进版本。已有修订还须同时匹配规范文档和持久 `fact_id`；不一致失败关闭，不允许 `ON CONFLICT` 跳过事实后发布悬空 manifest。

`RawOriginal(payload:bytes)` 以真实响应原字节 SHA-256 绑定。批次包含其事实所需原件，或引用同 scope/dataset 已存在原件；不允许引用其他账号/来源缓存。`Batch` 将 originals、facts 和 coverage 一起提交。失败、取消、缺原件、指标越界或同版本冲突不会推进批次或 watermark。

## PIT、覆盖与冻结

`read_range(..., as_of=aware_datetime)` 只选取真实 `available_at <= as_of` 的观测，未知公开日一律不进入 PIT。`as_of=None` 明确表示最新探索，可读取未知公开日数据，并在 `ReadResult.unknown_available_at/pit_complete` 标记。修订按公开时间、入库时间排序；入库更晚不会使真实公开更早的历史修订覆盖更晚已公开版本。调用者如需“本系统当时已收录”而非“市场当时已公开”，须另立双时间查询，不能混用。

`find_gaps` 必须传非空、无重复的明确期望日期，不能用“最早到最晚”冒充连续覆盖。交易日历应由受信来源提供；非交易日、停牌、上市前缺失须提供 `CoverageProof(date, state, evidence_id, available_at)`，不推定为零值或向前填充。`unknown` 不填补缺口；无已公开时间的证明不能填补 PIT 缺口。`watermark` 仅为最大已入库事实日期，**不代表区间连续完整**。内部缺口、缺指标仍由 `find_gaps` 判定。财务/宏观日期集合须遵循对应发布/参考期合同，不能直接套股票交易日历。

`freeze` 将实际选定修订、原件字节、coverage、完整来源和语义身份、起止日期、PIT cutoff/状态序列化为规范 JSON SHA-256。后续新增修订不改变旧对象。`FrozenSnapshot.export()` 是逻辑可移植包，不含宿主文件路径、DSN 或凭据配置；原始响应仍按源字节保存，提供方不得把凭据当成业务响应入库。读到已持有的冻结包后，接入端仍须按当前 entitlement 决定是否允许外发。

合法空结果可以仅由明确的 nontrading/prelisting/suspended 证明冻结并导出恢复；没有事实也没有上述证明、或仅 unknown 不能冻结为可用资料。PIT 同样要求证明本身的真实公开时间，未知公开时间的证明不进入历史选择。最新探索可冻结这些证明，但冻结 manifest 的 `pit_complete=False`；该字段仅描述所选事实/证明的时间可得性，不宣称区间连续或研究质量通过。

`export_restore` 验证包摘要、原件摘要、scope、指标、范围、PIT 声明及事实引用，原 scope 恢复并保留原冻结摘要；不把包内 owner 作为授权。SHA 只检测一致性，不能认证供应商真实性或替代可信导出签名。合并包不能直接恢复为某一个来源，防止跨源观测污染单源事实域。

跨源合并仅通过 `MarketStoreService.merge_snapshots`：逐输入来源重新鉴权，`verify_semantics(proof)` 必须确认已登记的独立语义审查证据。`SemanticProof` 绑定全部输入冻结摘要和语义摘要，单位/频率/复权等完整 dataset 和 cutoff 必须相同。重叠同业务键不同值失败；同值去重保留全部原件、输入冻结 manifest 和 proof，结果顺序无关。纯 `merge_snapshots` 是仅供受信内部使用的校验原语，不应暴露为未鉴权 HTTP/Tool。没有自动来源替换。

## 接入界面

固定公开indices的sessionless接入由`MarketReader`复用此仓库与同一个`StorageRunner`，不创建研究sid、不连接业务5432、不新增数据库服务。`ResearchWarehouse.capture_identity()`只返回当前个人profile的id/owner/enabled及安全配置摘要，不返回密码；Host读写前后比较该身份。SnapshotSeries底层每次授权另校验profile配置未替换，原个人/共享范围不放宽。取消或关闭MarketService必须等待实际在途StorageRunner事务结束；数据库故障只标明未持久化，不抹去原生快照或旧完整捕获。生产配置、全量导入和部署仍各自单独授权。

默认 `ResearchService` 已挂入 `ResearchWarehouse`，配置页与能力中心提供同一个仓库面板。未配置时不连接、不初始化；有界免费验证只通过既有资产观察 API 取最多14天数据，第二次必须数据库命中。可选 Doctor 只确认配置/驱动，连通性仍未知。原始股票规范桥限已审的 AKShare、BaoStock、Wind，逐个非空数值字段核对单位；天软尚未验证单位，保留供应商原生快照，不提升为规范价格/量额。其他财务、宏观、资金流及ETF/指数原生数据保存首次观测版本，限制见[原生快照合同](research-web-vendor-snapshots.md)。

同一逻辑事实、同一公开/入库排序时刻出现不同值，在提交边界即拒绝；PostgreSQL在既有数据集事务锁内核验并发冲突，失败不发布原件、版本或水位。查询时仍保留歧义检测，不能将既有损坏记录任意选一条。跨源锚点数值一致不等于单位已经得到验证。

```python
from app.research_web.market_store import (
    DatasetIdentity, MarketStoreService, PostgresMarketStore, StoreScope,
)

# factory 每次返回新连接；连接信息仅从受管凭据后端获取。
backend = PostgresMarketStore(connection_factory)
# 仅经批准的隔离/迁移步骤显式调用 backend.bootstrap()。
warehouse = MarketStoreService(backend, authorize=current_entitlement_policy)
scope = StoreScope(authenticated_owner, license_id, source_id, config_sha256)
dataset = DatasetIdentity(
    "bars", "600000.SH", "CN", "daily", "CNY/share", "raw", "none",
    semantics_sha256, metrics=("open", "high", "low", "close"),
)
cached = warehouse.read_range(actor, scope, dataset, start, end, as_of=cutoff)
missing = warehouse.find_gaps(actor, scope, dataset, expected_dates, as_of=cutoff)
# 仅在原有来源授权及任务预算内查询 missing；成功校验后一次原子提交。
version = warehouse.commit_batch(actor, scope, dataset, validated_batch)
frozen = warehouse.freeze(actor, scope, dataset, start, end, as_of=cutoff)
portable_bytes = frozen.export()
```

`authorize(actor,scope,action)` 必须返回精确 `True`，动作是 `read/write/export/restore`。权限回调缺失、异常或撤销均失败关闭；缓存命中也再次检查。service 是受信 Host 边界；直接后端仅供受管内部/离线迁移调用。共享白名单、厂商连接权限和商业数据外发许可仍由现有 Host policy 负责。

### 受控线程与取消边界

```python
from app.research_web.market_store import OperationContext, operation_context

operation = OperationContext()  # 每次请求独立实例，不能跨用户复用。
with operation_context(operation):
    version = service.commit_batch(actor, scope, dataset, validated_batch)
# 请求取消时 operation.cancel()；Host 必须等待已启动的工作线程 drain。
receipt = operation.outcome  # committed / cancelled / result
```

ContextVar 传播每次操作的独立 `threading.Event`，不使用全局取消开关。`asyncio.to_thread` 自动复制当前 context；手动 executor 必须显式复制 context，或在 worker 内进入同一个 `operation_context(operation)`。读操作在查询和返回边界检查；写操作在处理原件/事实及最终提交前检查。提交前取消抛 `MarketStoreCancelled` 并回滚；参考内存后端在发布前同样检查。提交成功后再收到取消保留 `operation.committed=True` 和真实 `operation.outcome.result`，不能声称已回滚。提交已进入数据库时不会强杀其他线程或连接；Host 等待工作线程真实终态再生成回执。未显式使用 context 时原同步接口行为不变。

## PostgreSQL 与运维边界

`PostgresMarketStore` 用新 DBAPI 连接及参数化 SQL。`from_dsn` 只在操作时懒加载可选 `psycopg`；import、构造、read 均不创建 schema。专用库 `bootstrap()` 显式建立 indexed-v2：`rwb_market_originals`、`rwb_market_facts`、`rwb_market_coverage`、`rwb_market_batches`、`rwb_market_watermarks`、`rwb_market_frozen` 与 `rwb_market_schema`。原件、事实修订及 coverage 有独立主键；事实外键只引用同 scope/dataset 原件，来源/时间范围及修订有专用 B-tree 索引。发现已有批次却没有版本 marker 时拒绝 bootstrap，不能把旧历史静默遗漏；本阶段没有生产 v1 部署或已授权的 v1→v2 迁移。

运行账号仅应拥有 originals/facts/coverage/batches/frozen 的 SELECT、INSERT，watermarks 的 SELECT、INSERT、UPDATE，schema marker 的 SELECT；不得拥有 DDL、DELETE 或不可变表 UPDATE。迁移 owner 与运行 role 分开；模块不自动配置权限。真实隔离 role 已验证无法修改或删除批次、原件和事实。

同 scope/dataset 写入先获事务 advisory lock，再在 READ COMMITTED 中只读取当前 head、批次去重键、所引用的原件 hash 和本批涉及的修订键。原件、事实、coverage、批次 manifest 和 watermark 一次事务提交。版本为 `SHA256(parent_version,batch_hash)` 增量链，重复提交同批次不增加版本，`version/watermark` 仅查 head 单行。审计 batch 保存内容 ID/原件 hash 及父版本，不重复保存 base64 原件，也不参与常规读取重放。后批只引用旧原件不受批次 hash 排序影响。

`read_range` 通过 scope/dataset/date 范围及公开时间条件查询事实投影，只在命中范围内选取最新可得修订；读使用 REPEATABLE READ READ ONLY。先在数据库统计实际结果的行数/编码字节，再取回文档，避免先拉取大响应后才检查。`find_gaps` 只查询明确期望日期及该日期的 coverage；freeze 在同一一致快照内取所选事实和对应原件并持久保存 manifest。

历史累积没有原先 10,000 批/64MiB 永久上限。每次批量导入最多各10,000事实/原件/证明且总量32MiB；每次查询最多10,000事实/32MiB，每次导出/恢复包最多32MiB。超限明确拒绝当前操作，调用者分批、缩窄日期后仍可继续，不能截断资料或禁止后续正常窄范围追加。生产容量、真实全市场压力、备份恢复、WAL/保留策略、分区及生产 schema 升级仍需对应验收。`InMemoryMarketStore` 仅用于确定性单元测试，无持久化保证，也不承担生产投影算法。

## 验证入口

### 当前 Host 接入范围

默认 ResearchService 已接入个人研究仓：先检查完整交易日覆盖，再补内部缺口和新增日期范围；`refresh=true` 显式重取修订。当前尚无同一日期范围的自动尾段刷新策略，盘中数据与后续更正不能仅凭已有覆盖视为永久新鲜。共享仓、市场页 MarketService、私有 Wind 周报和基金 NAV 的不完整原生响应仍待各自接线，不能从内核接口推导这些路径已经持久化。

规范股票桥在写入前只接受沪市 6 开头、深市 00/30 开头的代码及相符交易所后缀，拒绝将指数、ETF 或错配后缀作为股票；此规则不能证明证券真实存在，完整证券主数据验收仍独立。显式指数/ETF 原生合同不套用股票规则。财务、宏观等原生快照保存本次捕获时间和供应商口径，尚不满足正式历史时点回测要求。

普通测试不连接数据库：

```sh
python -m unittest discover -s tests/research_web -p 'test_market_store*.py'
```

安装好测试依赖且明确允许隔离验收后，`RWB_MARKET_STORE_LIVE_PG=1` 启用 `test_market_store_live_postgres.py`。它只创建本任务临时 PGDATA、0700 Unix socket、关闭 TCP、有限连接/缓存/WAL，验证真实进程重启、PIT/修订、冻结、逻辑恢复、watermark 写失败全事务回滚及运行 role 禁改原件。结束只停止/清理自己创建的临时实例；不扫描、停止或重配已有服务。测试门未启用时记为 SKIP，不能算真实 PostgreSQL 通过。

### 2026-10-22 本机隔离实测

解释器为本任务 worktree 的 `.venv-tests/bin/python`，自包含已批准依赖，无 `PYTHONPATH` 和全局包写入。实际命令 `RWB_MARKET_STORE_LIVE_PG=1 .venv-tests/bin/python -m unittest discover -s tests/research_web -p 'test_market_store*.py'` 返回 **42 tests / OK / 无 SKIP**（其中15项为真实 PostgreSQL，其余为领域、DBAPI 与线程 context 合同测试）。TDD 缺模块、PIT 伪造、合并区间、恢复原子性、原件依赖反向 hash 排序、历史累积门、响应字节前置检查及等价时区身份等均先见证失败后修复。

独立审查复现的 P1 在 DBAPI 和真实 PG 上先报 `missing_original`，索引版在后批只引用前批原件、hash 逆序及进程重启后仍能 read/version/freeze。P2 旧重放实现于累计64MiB门失败（165.478秒）；索引版实测66个1MiB原件后继续窄范围读取/冻结/追加，最终完整40项测试2.625秒。真实 PG 还验证空数据库逻辑恢复、增量链/重复提交、两个并发写入、范围索引 EXPLAIN（302条夹具、ANALYZE 后正常 planner 选择日期索引）、旧 schema 拒绝、coverage-only 冻结及取消提交边界。该小型 fixture 不代表全市场性能已验收。

质量审查的等价时区回归先在内存复现 `Fact相等但identity不同`、真实PG复现重复提交推进版本；修复后跨批次及同批双 offset 都只保留一个事实/证明和一个批次，悬空 manifest fact ID 为0，原件字节未变，进程重启及等价 cutoff 时区冻结/恢复摘要一致。

真实实例的 `SHOW listen_addresses` 为 `''`、`SHOW fsync` 为 `on`；独立临时数据库和受限 NOLOGIN role 在本实例内验证，未向现有 5432 或外接盘发送命令。测试结束 `pg_ctl -D <本任务PGDATA> -m fast -w stop` 成功且临时目录不存在，输出清理回执 `owned_pgdata_removed=true owned_pg_stopped=true tcp_disabled=true fsync=on`。此结果证明隔离测试实例，不证明生产权限、备份或部署已完成。

限定新模块及其测试的 Ruff、Black、isort 检查通过；`mypy --follow-imports=silent --check-untyped-defs app/research_web/market_store` 返回5个源文件无问题。现有全库回归、安装 CI、DataHub 接线、运行服务及其他平台验收由父任务单独记录。


2026-10-22 基金NAV入仓：Host原生快照层仅为完整分页、有界东财NAV开放三项已声明语义缺口，rows/fields/missing/raw逐字节保真；不改变MarketStore内核schema、历史可得性或冻结恢复合同。

2026-10-22 iFinD凭据复用：iFinD access优先及纯元数据授权验证只调整Provider凭据调用顺序，不改MarketStore schema、范围覆盖、PIT或冻结恢复。

2026-10-23 资产历史任务可请求recent/daily/none/source:auto并通过现有Broker降级；其会话规范快照使用asset-history-raw-2，不能替代研究仓的独立交易日历、PIT、缺口或正式回测质量证明。未知单位响应在历史发布前失败，不伪称跨源质量已通过；没有启用正式数据库或移动数据根。

2026-10-23 Tinysoft原生股票日线新增经CJPY0.5.2字段字典证明的vol股、amount原生元声明，不提供OHLC单位或CNY证明。ResearchWarehouse._bridge的规范股票来源仍排除Tinysoft；原生快照可保留真实声明，不能凭成交量局部证明通过统一价格单位/PIT或正式回测门。此次不连接数据库、不读取行情、不改数据库/外盘配置。

2026-10-23 `required_semantics=cn_stock_daily_cny_share_v1`是Host对候选价格/量额单位的显式收窄合同；原生快照不满足它，不能通过旧native缓存命中绕过OHLC单位门。当前Tinysoft缺OHLC/CNY证明，因此规范raw候选在Broker准入跳过；其通用原生响应和metadata仍可冻结。此变化不启用Tinysoft规范bridge、不新增SQL表/依赖/数据库配置，不改变历史PIT或正式回测合格状态。


2026-10-23 Wind容量回归修复：供应商60自然日上限不再阻断已授权完整仓库长窗读取。对沪深股票daily/none、无as_of、refresh=false的长窗，Host可在同一查询预算内先取得一次Wind缺口计划；每个实际缺口仍须正常通过60日限制及当前权限/配置校验。计划与原查询指纹及来源配置绑定，未知/空库全窗、过大缺口、规划繁忙或失效不会自动拆成供应商可执行小块。固定Wind保留明确失败，auto保留实际skip原因后选择其他候选。取消必须等待规划事务的实际Future结束，不能提前释放容量。此修复没有启用跨来源部分覆盖拼接，Asset新历史job仍为refresh=true整段刷新；交易日历准备也可能联网，不能据此称所有查询均只读离线缓存。

## 官方档案的有限历史发布回放（2026-10-23）

`bea_archive_store.py` 是现有 `WarehouseBinding` 的受信绑定，使用同一专用库、scope、当前profile/来源授权和StorageRunner，不创建表或服务。只处理BEA 2024Q2实际GDP季调环比折年增长率：原始HTML分别证明BEA24-33/38的数值与8:30 EDT公布时刻。季度末是业务日期；`available_at`取已核实的原发布时刻，`ingested_at`仍是本次入库时间。它认证官方发布信息的历史可得性，不宣称本系统当时已收录。

row和gdp_growth两指标共享逻辑期、发布编号、公布时刻和原件hash；release ID放修订版本而不放dimensions。每个旧版按其公布cutoff独立核对，不能只看最新投影；同发布改值整体拒绝，重复原值幂等。两个Host并发提交同发布时只允许一次重新校验，不能吞掉真实数值冲突。读取重验所选行与原始HTML，冻结/独立恢复保留实际选择的发布版与原件。

仅允许`2024-07-25T12:30Z <= as_of < 2024-09-26T04:00Z`；初值2.8与第二版3.0的切换点为`2024-08-29T12:30Z`。无as_of的latest仅指reviewed_archive_catalog末版，不是当前终值。其他宏观和财务native仍按首次观测保存，不能借此放宽正式PIT。财务报告日/公告日/更新时间、资金流单位和定义另行核验。逻辑恢复哈希不替代供应商真实性/导出授权；原有共享/个人与撤销校验继续适用。

部分恢复也核对cutoff应有的发布编号：只恢复初值时，初值期间可读，第二次发布后及catalog latest均为missing，不能以旧值代替缺版；只恢复第二版不能回答初值期间。该矩阵在离线回归与真实独立临时SQL恢复中分别留证。


## 2026-10-23：BaoStock盈利能力来源

BaoStock盈利能力进入独立baostock-quarterly-profitability-v1的provider-native schema/units身份，仍为first_observed，pubDate保留在数据中而不冒充Fact的历史available_at。只有完整固定响应及已知单位合同可捕获；空/partial/错误不宣称覆盖。显示可显式allow_stale读仓，严格最新研究重新取数；冻结支持原字段与原SDK载荷恢复，不提升正式PIT。原日线身份、旧冻结读取和授权检查保持。


600000.SH/2026-06-30实际双源与发行人半年报核对仅确认两格金额对应集团半年累计，不能当作Q2单季或归母净利。两源公告日8月28日与issuer列表8月27日保留不同来源，不回填精确时刻。两个provider-native版本独立冻结和恢复；样本核对不升级通用跨源等价或财务PIT。详见任务报告。

## 2026-10-23：长期研究档案与机会预警

长期档案的个人 SQLite 是观点、原件引用、pin 与扫描／跟踪元数据索引，区别于本章可选 MarketStore／PostgreSQL 研究仓；不启用或迁移研究仓，也不复制供应商正文、规范序列或历史版本。档案读取原 manifest 与当前来源权限，扫描只认合格冻结材料；first_observed、报告期及小创产业链当前关系均不获得历史 PIT／回测资格。备份必须连同原快照保全，详见[档案存储](research-web-dossiers.md)、[扫描](research-web-dossier-scans.md)与[候选限制](research-web-seek-alpha.md)。
