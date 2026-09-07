# Research Web DataHub

DataHub是`app/research_web/datahub/`内的FastAPI进程模块，不是新守护进程、调度器或全局行情数据库。
DSH仍是唯一研究引擎；Web只读资料，原生插件通过受控回环桥接查询同一DataHub。已配置且可用的来源自动执行，不逐次确认。
不导入旧Connector.run、AKShare生命周期或旧报告编译链；没有新增依赖。

## 当前定位与命名

DataHub 是后台数据总机：统一描述“能查什么”、选择“从哪里查”、把供应商参数翻译成稳定业务参数、标准化结果，并把本次研究使用的数据保存为会话隔离快照。它不替代 DSH、Skill 或 Tool，也不是前端直接执行的能力类型。

```text
FinGPT / Claw / Skill
          ↓
datahub_* 业务 Tool
          ↓
DataHub：静态目录 → 白名单路由 → Provider → 快照与审计
          ↓
东方财富 / 财联社 / 后续完成适配的专业或公开来源
```

Tool 统一使用 `datahub_*` 子系统前缀，而不是 `rwb_*` 产品品牌前缀。这样未来产品改名不会破坏 Skill、会话历史或 DSH 工具协议。`datahub_get_fund_data` 是基金数据能力的正式工具名。

## 全源静态目录

`catalog.py` 始终声明并供页面展示 13 项业务能力和 21 个来源；读取目录不会导入 Connector、访问外网、启动 Excel 或产生供应商费用。目录展示范围不等于 Runtime 工具范围：真实 Runtime 只注册启动时 `callable_source_count > 0` 的能力对应工具。

业务能力包括证券搜索、交易日历、历史行情、实时快照、指数、财务、资金与交易事件、因子与宏观、基金、新闻、公告、研究资料和网页搜索。登记来源包括 Wind、天软、iFinD、AKShare、BaoStock、Tushare、Yahoo、ChinaStock、本地缓存、中证指数、深交所、巨潮、财联社、中国证券网两类内容、知丘三类内容、东方财富基金、Tavily 和 Bing。

每个来源分别展示：

- `code_exists`：仓库存在相应请求或适配代码。
- `integration_state`：是否已经抽取为 DataHub Provider。
- `configured` / `dependency_ready`：当前配置与依赖是否具备。
- `allowed` / `callable`：是否允许进入业务路由、当前是否实际可调用。
- `health` / `last_checked_at`：最近一次显式探测结果，而不是页面加载时偷偷检测。

东方财富基金和财联社无需专业配置即可调用。天软 CJPY 已完成证券目录、交易日历、历史行情和实时快照四项 Provider 适配；只有 `cjpy` 依赖存在且 `CJ_KEY` 已配置时，对应绑定才可调用。AKShare 已实现 `search_assets`、`market_bars`、`market_snapshot`、`financials` 和 `market_activity`，但仅在 `akshare` 依赖就绪时 callable。天软的其他登记能力继续显示“能力仅登记”，不会由来源级“已适配”状态错误放行。真正尚未实现的其余来源只用于展示真实覆盖规划与缺口，不会因为“代码存在”被伪报为已连接。手动探测一次只检查一个来源，重复 Idempotency-Key 返回同一 probe；未适配来源直接返回安全化不可用结果且不联网。

## 稳定业务 Tool

静态业务工具集合包括 `datahub_search_assets`、`datahub_get_trading_calendar`、`datahub_get_market_bars`、`datahub_get_market_snapshot`、`datahub_get_index_data`、`datahub_get_financials`、`datahub_get_market_activity`、`datahub_get_factor_macro`、`datahub_get_fund_data`、`datahub_search_news`、`datahub_search_announcements`、`datahub_search_research` 和 `datahub_search_web`。启动器从离线目录读取每项能力的 `callable_source_count`，把大于零的工具 ID 物化到本次 Runtime 的 `enabledTools`；Runtime 只注册这个子集。配置、依赖或允许状态变化后，必须启动或重启 Runtime 才会重新物化，不会在运行中的会话里偷偷增删工具。

工具只接受对应能力的业务参数及可选 `source`/`allow_fallback`。`source` 必须是目录中的 ID；URL、请求头、凭据、模块名和磁盘路径在 Pydantic 边界被拒绝。已配置且可用的来源会自动查询，包括需要账户或付费授权的来源，不再弹出逐次确认。没有可调用来源的能力不会注册为 Runtime 工具；Agent 不应调用或重试不存在的工具，也不能降级成网页猜测或演示结果。

天软 Provider 通过 CJPY SDK 的专用客户端访问固定 `http://tsl.tinysoft.com.cn/tslweb/api`，Provider 边界限制 15 秒和 5000 行；授权值只在 Provider 内使用，不进入结果、普通日志或提示词。返回数据保留供应商原字段和 raw JSON，不猜测单位。项目未自动安装 `cjpy`，因此没有依赖的环境必须诚实显示阻塞。

自动执行只移除 DataHub 的逐次确认，不放宽其他边界：回环 token、`trustedDirectory` 父系验证、能力/来源白名单与固定参数 schema、会话隔离快照、取消联动、22 秒原生桥接超时和 15 秒 Provider deadline 均继续生效。

`broker.py` 根据能力绑定、覆盖范围、完成适配、配置、依赖和允许状态选源。`source=auto` 只选择一个最终 Provider，不拼接不同口径；显式来源默认不换源，只有请求明确 `allow_fallback=true` 才允许继续选择。结果记录实际 Provider 与尝试来源。

## 查询与来源

| source | 固定公开来源 | 范围 |
| --- | --- | --- |
| fund_nav | `https://api.fund.eastmoney.com/f10/lsjz` | 六位code；成对start_date/end_date按实际分页取得范围，最多十年且不含未来；旧limit只取最近一页、最多100条 |
| cls_telegraph | `https://www.cls.cn/api/cache?name=telegraphList` | 最新limit 1–100条公开快照 |
| fund_profile | `https://fundf10.eastmoney.com/jbgk_<code>.html` | 当前基金身份、规模、经理、费率、基准文字等已核实字段；不是历史时点资料 |
| fund_distributions | `https://fundf10.eastmoney.com/fhsp_<code>.html` | 权益登记/除息/发放日期、每10份分红原文；不构建复权总回报 |
| fund_holdings | `https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc` | code、topline=100、year可选1990..当前年；不填year请求最新可用期。仅解析content的JSON字符串，不执行JS |

source/code/limit/start_date/end_date/year/refresh是业务参数；工具不接受会话、目录、URL、头、cookie、代理或凭据。
日期以Asia/Shanghai校验。基金代码保留前后端份额原文，不合并证券身份。
持仓保留报告期、标题、股票代码/名称、占净值比例、万股/万元原文；报告期不等于披露日期，完整持仓覆盖未知。
HTML资料将换行表头仅用于匹配时去空白，原文字段名仍保留；缺闭合td在下一th/td前截断，避免字段串联。
`---（每年）`等缺失保留original_value而value=null，不解读成零费率。
分红每10份金额保留来源原文；币种未独立核实，currency统一null并标记verified_currency缺失，不由“元”或基金代码猜测币种。

## 限额与状态

内置直接 HTTP Provider 使用固定目的地、不跟重定向、`trust_env=False`，不继承认证或代理，也不自动重试；这些约束不表示 AKShare 或天软 SDK 的底层 HTTP 实现具备同一组限制。直接 HTTP 响应限制为每个1MiB、总原始响应16MiB和最多100页；DataHub Provider deadline 为15秒，原生桥接总超时为22秒，标准化结果最多5000行。
实际NAV响应的TotalCount/PageSize/PageIndex在顶层，记录在Data.LSJZList。请求100实际可能仅20；不能用“少于请求数量”当完成。
实际页码、页大小、总量和日期逐页验证，重复页/总量或页大小变化停止并保留已经得到的原始响应与解析记录。
无穷值、坏日期、超出请求范围、必填数值缺失均明确失败/不完整。

- `complete`：日期范围请求的来源分页结束且没有已检测到的覆盖异常；不是市场全量的独立验证。
- `snapshot`：单次公开快照已取得，不能宣称完整历史。
- `empty`：来源成功返回零条，和取数失败区分。
- `partial`：已经取得部分可用行但后来失败/触限/冲突；不得自动命中完整缓存。
- `failed`：没有可用行且取数或解析失败；manifest明确标记失败，不伪装报告交付。

AKShare 和天软是同步 SDK/库 Provider，其底层线程在 Python 内不能被安全强杀。两者分别使用专用单线程执行器、并发容量 1 和15秒 Provider deadline：首次超时返回带 `deadline` 限制的 `failed` dataset；线程真正退出前，后续请求立即返回带 `provider_busy` 限制的 `failed` dataset，不排队、不另起线程。该 Provider 释放容量后才接受下一次查询，不影响其他 Provider 的独立容量。

同值重复日期去重并记录；唯一日期数少于供应商总量时status=partial，即使来源页确已结束、pagination_complete=true。
冲突日期从可用解析记录移除、不任选其一，原始响应保留。直接 HTTP Provider 的取消会立即停止 HTTP；同步 SDK Provider 的取消只终止等待且不发布快照，底层线程按上一段约束隔离至自然退出。私有调用收据保留 cancelled。
BFF关闭及现有会话cancel均取消相关请求。原生abort通过独立短超时取消请求联动；取消先到的调用ID写入tombstone。

## 私有控制与会话存储

启动器/服务创建独立随机控制凭据`.control/datahub.json`，0600；父目录0700。
原生可信插件在trustedDirectory沿实际DSH父系验证后读取固定文件；DataHub 调用按当前可用工具自动执行。
拒绝symlink、hardlink、错误属主或过宽权限；token不进入脚本环境、prompt、普通API或日志，不读取/复用模型密钥。
地址默认`http://127.0.0.1:8088`，首次可信启动可用`--datahub-url http://127.0.0.1:<port>`指定隔离BFF端口；只接受无userinfo/query/fragment/path的回环HTTP origin。已有地址不符报错，不静默覆盖。

```text
.control/datahub.json                         # 新产品控制凭据，只给可信服务/原生插件
.control/calls/<sid>/<call-hash>.json          # 稳定调用ID + 参数指纹 + 受理/结果
.control/snapshots/<sid>/<dataset_id>/         # 原始响应 + 权威manifest
sessions/<sid>/inputs/datasets/<dataset_id>/   # 只读rows.json、rows.csv、manifest.json
```

每次新查询使用独立UUID，临时目录写完后先rename并fsync公共输入，最后rename私有目录作为目录提交标记，不覆盖旧快照。
若进程在两次rename之间退出，公共孤儿目录与私有.pending目录均不进入资料枚举，不阻塞健康资料或新查询，也不自动删除；原pending调用重启后仍不自动重发HTTP。
数据文件创建0600并拒绝链接逃逸；读路径用NOFOLLOW目录描述符逐级打开。
私有manifest作为校验基线，每次目录/详情/分页/下载复核public manifest及解析文件hash。原始文件没有普通Web下载路由，不进附件或报告产物清单。
manifest含schema_version、query、source/source_url、retrieved_at/as_of、字段单位/币种（未知null）、请求/实际日期、行数/总量/页数/分页、coverage、missing/limitations和原始/解析文件相对路径+SHA256。
manifest自身SHA256由详情返回，避免自引用。CSV把外部公式样式文本前置单引号，合法数字不转义；JSON和私有原始响应保留原值。

同会话、同参数、同schema_version的完整请求快照可复用：资讯60秒、NAV/补充资料15分钟，保持原retrieved_at，返回cache_hit=true。
refresh=true始终新建；同原生调用ID重放返回同一结果，同ID不同参数拒绝，重启后pending状态不自动重发。
自动缓存不跨会话。用户显式FinGPT→Claw升级会先校验原资料与原始hash，再复制为新ID、新owner、不用链接、不发HTTP，并保留origin_dataset_id/origin_manifest_sha256及原retrieved_at。
升级draft保留原消息正文，追加旧→新dataset_id映射、原/新manifest hash、原取数时间及当前会话manifest/rows相对路径与文件hash；明确旧路径不适用于新会话，不替换历史正文。

## API契约

- `GET /api/research/data/catalog`：13 项能力、21 个来源、绑定矩阵和诚实汇总；纯静态读取。
- `GET /api/research/data/capabilities/{id}`：能力参数、字段、覆盖范围和全部候选来源。
- `GET /api/research/data/sources/{id}`：来源鉴权/依赖、状态、限制和支持的数据集。
- `POST /api/research/data/sources/{id}/probes`：以 `Idempotency-Key` 异步检测单一来源。
- `GET /api/research/data/probes/{id}`：读取安全化探测状态、耗时和失败代码。
- `GET /api/research/sessions/{sid}/datasets`：`{items:[summary]}`；老会话返回空数组。
- `GET /api/research/sessions/{sid}/datasets/{did}`：完整manifest、manifest_sha256及下载引用。
- `GET .../{did}/rows?offset=0&limit=100`：`{items,offset,limit,total}`，limit最大500。
- `GET .../{did}/files/{rows.json|rows.csv|manifest.json}`：已校验的当前会话数据文件下载。
- `POST /api/research/internal/data/business-query`：`{session_id,call_id,query:{capability,parameters,source,allow_fallback,refresh}}`；新 `datahub_*` 入口。
- `POST /api/research/internal/data/cancel`：`{session_id,call_id}`。
- `POST /api/research/data/queries`：研究台按业务能力发起幂等查询并创建源会话快照。
- `GET /api/research/data/queries` / `GET /api/research/data/queries/{id}`：读取查询历史、状态和安全化失败原因。
- `POST /api/research/handoffs`：复制并核验所选快照，把页面上下文交给新 FinGPT/Claw 会话。
- `GET /api/research/artifacts`：汇总已有会话的实际输出文件，不扫描任意目录。

所有internal入口在解析请求体之前检查`X-Research-Data-Key`；无认证浏览器不能绕过受控回环桥接直接取数。
公开GET不发起上游请求。浏览器API仍受现有同源边界限制，无CORS、多用户登录或远程部署支持。
`service.detail.datasets`供SSE/UI：id/dataset_id/name/source/source_url/status/row_count/requested_range/actual_range/pagination_complete/retrieved_at/cache_hit/limitations/missing/pages_fetched/provider_total/as_of/files；不推全部行、fields或raw_files。
files条目包含name/path/sha256/size/url/kind=dataset；url为上述专用下载路径。
原生工具返回字符串字段dataset_id/source/status/manifest_json/files_json/sample_json，最多三行样本；Python从只读路径读取全数据，不把历史全部塞进上下文。

## Skill与研究口径

五个内置研究 Skill 及 persona 要求：父 Agent 只调用当前 Runtime 已暴露的 `datahub_*` 工具；可用来源自动查询，不逐次确认。工具未暴露时不调用、不重试；读取 manifest 核对缺失后，复杂 Claw 任务再分两个子 Agent 复用父 Agent 已取得的同一数据集，不重复取数。
计算限定已获得数据；累计净值不是总回报指数。未取得期初前一估值日及分红复权口径时只称“首末观测区间净值变动”，不冒称完整日历年度收益。
业绩基准文字不是基准序列；目前未取得可靠基准序列、合同/报告下载服务。20行最近快照不能证明三年表现。
XLSX应包含原始解析记录和公式/计算说明、dataset_id/hash；DOCX/HTML使用同一ID/日期。输入快照不算报告产物。

## 验证与限制

离线：`python -m pytest tests/research_web --confcutdir=tests/research_web -q`及`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`。
还执行ruff/black/isort/mypy及项目任务完整性检查；2026-09-04 全源目录、真实公开探测、Web 五视口和 Archify 证据见`.ai/reports/2026-09-04-datahub-full-source-catalog.md`，早期 DataHub 实现记录见`.ai/reports/2026-09-02-datahub-implementation.md`。
真实来源只读核对由父任务记录在`.ai/reports/2026-09-02-datahub-source-probes.md`，不把离线测试当真实模型闭环。
2026-09-02集成验收曾按当时机制从Web完成四次原生审批，并取得2025净值13页243条及三类补充资料、完成FinGPT升级复制、两个真实子Agent共享资料，以及DOCX/HTML/XLSX/PNG输出。该记录是旧逐次审批机制的历史证据，不代表当前 Runtime 仍逐次审批；当前行为以上文自动执行和启动时工具物化契约为准。
最终XLSX四张原始表逐值与CSV一致（243/16/25/220行），来源文件hash一致；首末观测区间变动和回撤已独立重算，数值与百分比格式均核对。
首次模型产物曾有回撤百分比放大和无效公式，经真实会话修订后才作为final文件交付；格式检查不是自动语义正确性保证，也不代表任意基金评价已验证。
详细会话、修订、下载和边界证据见[本批真实验收](../.ai/reports/2026-09-02-datahub-acceptance.md)。本批仅更新专属3081/8088；没有修改3080、固定DSH、模型、原生额度或Seatbelt权限。
单Web worker、本机macOS；未验证Linux/Windows、多租户、磁盘总配额或大规模快照目录性能。
