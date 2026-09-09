# 基金数据完整性与共享研究资料包

用户已同意轻量DataHub方向并要求开始执行。此批完成NAV/资讯的统一数据服务、固定会话快照、基金补充资料、原生审批桥接和Web资料展示；不接Seek-Alpha业务接口，不增加MCP SDK或数据库。

## Global Constraints

- 在 `codex/dsh-web-v1` 的现有隔离工作树实现，基线 `708fbdb`；主工作树、用户3080与其他会话不改动。
- DSH仍是唯一研究引擎。不得放宽原生工具白名单、子Agent策略、脚本沙箱、模型配置和执行上限。
- 不安装依赖。Python使用现有 `python`，Node使用现有运行时。
- 先测试失败，再实现。错误与日志沿用项目设施，不记录凭据或完整私人内容。每个Python变更配测试、模块文档、CHANGELOG、任务报告。
- 每次外部查询仍先经过DSH原生审批，拒绝/取消不得取数。供应商、参数、目录、会话身份不能由模型任意指定。
- 数据集是研究输入，不能计作报告交付文件；不恢复Evidence/Claim/Quality Gate，不让模型抄写原始数据作为权威副本。

## Task 1: DataHub与原生桥接

责任：`app/research_web/datahub/` 新模块；现有main/service/launch_runtime最小接线；runtime/public-data.mjs改为薄桥接；四个Skill及persona的资料使用说明；相关Python/JS测试及 `docs/research-web-datahub.md`。不修改UI源码，由Task2负责。

实现结构：FastAPI内部DataHub模块，包含明确的查询契约、固定来源Provider、快照存储和薄路由。Web与DSH使用同一服务。无新的守护进程、后台调度或全局数据索引。现有datahub_get_fund_data名称保持，参数增加日期范围，仍只向模型暴露业务参数；移除原生JS中的重复上游解析。

传输边界：原生插件在trustedDirectory验证并原生审批后，使用可信配置中的回环BFF地址调用DataHub内部查询端点。通过专属随机凭据校验内部请求，凭据保存在研究根的私有控制目录（0600、拒绝符号链接），不进入提示词、脚本环境、普通API或日志。插件从实际DSH父系目录解析产品会话ID，不接受模型的session/path/url/header。BFF校验现有Store归属，所有内部入口需要认证。禁止自动跟随重定向。未认证浏览器请求不得绕过审批发起查询。凭据创建与读取由启动/服务代码负责，不能动已有模型密钥。

查询行为：
- `fund_nav`保留六位code与旧limit请求。新增start_date/end_date，必须成对且合法、非未来，范围最多10年。显式日期查询分页取完整供应商结果；无日期的旧limit查询保留最多100条的语义，不假称全历史。
- 复用已核实东方财富lsjz请求和字段，不导入旧Connector.run或AKShare全包生命周期。实际响应有顶层TotalCount/PageSize/PageIndex，Data.LSJZList。依据实际页大小/页码/总量翻页，不能假设请求100就返回100。页上限100、总行数上限5000、每响应1MiB、每查询总原始数据16MiB；同源查询整体15秒，无自动重试/认证绕过。命中限制或中途失败保留已取得内容及partial原因；零页失败明确failed。
- 检查响应结构、日期、有限数值、日期范围、跨页重复；相同重复可去重但记录，冲突日期不任取一个而明确失败/不完整；重复页或总量改变必须停止且标partial。支持任务取消，取消后停止HTTP与落盘，不发布成成功快照。
- `cls_telegraph`沿用现有固定端点与最多100条快照语义，同样程序落盘。
- 基金补充资料：固定公开`jbgk_<code>.html`/`fhsp_<code>.html`/`FundArchivesDatas.aspx?type=jjcc...`中经过实际核对的字段。作为 `fund_profile`、`fund_distributions`、`fund_holdings` 明确能力，各自单次审批查询。只用已装HTML解析库/纯JSON提取，不执行远端JS，不传任意URL。保留来源、原文口径、报告期；缺失和取数失败区分。无法核实字段保持缺失。业绩比较基准文本不等于已取得基准时间序列；当前无可靠基准序列、合同/报告下载服务就显式记录未取得，不制造数据。

数据集与读取：
- 上游原始响应在私有、会话归属目录按独立UUID快照保存；解析结果CSV/JSON与manifest以新目录原子发布到该会话`inputs/datasets/<dataset_id>/`，原生沙箱对inputs已有只读保证，不扩大权限。禁止symlink/hardlink逃逸；每次刷新新版本，不覆盖旧快照。取消/失败不能留下看似成功的材料包。
- manifest最少：dataset_id、source、schema_version、query（不含秘密）、retrieved_at、as_of、字段单位/币种（未知为null）、请求范围、实际首末日期、row_count、provider_total、pages_fetched、pagination_complete、coverage说明、missing/limitations、原始与解析文件hash、相对文件引用。明确“来源分页已取完”不是“市场全量数据被独立验证”。
- 仅同会话同参数同解析版本的完整快照可短时复用（NAV历史15分钟、资讯60秒；补充资料15分钟），保留原retrieved_at并标cache_hit；显式refresh新建，不跨会话共享，失败/partial不自动当完整缓存。
- 数据集读取接口提供目录、详情和分页行读取，检查归属/路径/hash。DSH返回短manifest及相对CSV/JSON路径、小样本，不把全部历史塞进模型上下文。原始文件不混进普通报告产物列表。
- 加GET `/api/research/data/capabilities`、GET `/api/research/sessions/{sid}/datasets`、GET `/api/research/sessions/{sid}/datasets/{did}`（含可下载的已有scoped文件引用）、GET同路径`/rows?offset&limit`。查询内部入口与取消入口仅可信插件可调用，使用稳定调用ID避免重复查询；取消处理须与DSH abort相连，BFF关闭时取消未完成取数。公共Web只读入口不产生上游请求。
- service.detail新增 `datasets` 简要数组供SSE/UI：id/name/source/status/row_count/requested_range/actual_range/pagination_complete/retrieved_at/cache_hit/limitations/files；确保旧会话没有数据时返回空数组。取消现有会话时也结束其DataHub请求。
- 保持FinGPT升级Claw的资料携带：显式upgrade校验旧资料归属/hash后在新会话复制新ID快照，保留origin_dataset_id/原来源hash与原retrieved_at，不发HTTP、不使用跨会话共享链接。不能被旧basename附件复制逻辑丢失或扁平化。此为用户显式复制，不是跨会话自动缓存。

Skill：先父任务批准准备资料，读取manifest核对数据和缺失项后，再分配两个子Agent读取同一数据集CSV/JSON；子不重复取数；计算限定已获得口径。生成XLSX包含原始记录与公式/计算说明、dataset_id/hash；DOCX/HTML引用同一ID和日期。不得把累计净值自动视作总回报或只凭20条数据宣称三年表现。

测试：分页实际返回20而请求100、范围非法/未来、跨页去重与冲突、总量变化、分页上限/超时/取消/坏数据、空与失败区分、缓存及新版本、只读输入与跨会话拒绝、数据不计delivery、缺认证拒绝、native审批拒绝零HTTP及原生schema兼容。先红后绿；不启动/重启真实服务、不操作凭据，真实源只读核对由主代理做并传入结论。运行全Research Web Python/JS回归、格式/类型检查；提交自己修改，不提交主代理的plan/ledger。

## Task 2: Web资料展示

Task1接口稳定且审查通过后实施。仅UI模块与JS测试、UI文档。
在当前活动与文件面板增加“研究资料”分区，展示来源、请求/实际范围、记录数、分页是否取完、取数时间、缺失/partial原因及CSV/JSON/manifest下载。与“生成文件/交付状态”分开；空资料不显示模拟卡片。复用SSE详情，不增加新的轮询任务；新旧会话/切换/刷新均可用。安全转义、只接受本会话file路由；未知状态不伪装成功。写失败渲染测试后实现，不改全局视觉风格、不加依赖。主代理负责实际浏览器验收。

接口落定：直接读取service.detail.datasets简要数组；专用下载为`/api/research/sessions/{sid}/datasets/{did}/files/{rows.csv|rows.json|manifest.json}`，不复用报告files列表。前端严格匹配当前sid和卡片did，拒绝其他会话、编码路径分隔符、任意文件名、查询串及外站。显示missing、as_of、pages_fetched/provider_total和source_url（安全外链），快照状态不能译成“全量数据完整”。同一资料的多个下载动作需可由辅助技术区分。沿用现有抽屉/布局，长来源和范围允许换行。

## Task 3: 真实验收与交付

主代理集成、复核实际Provider输出，重启仅专属3081和8088前确认无活跃任务，不改3080。
在专用会话从Web发起一整年/三年基金000001净值查询：实际超过单页、CSV直接生成、manifest覆盖可核对；准备补充资料后两个真实子Agent共读相同数据集，各有真实活动，生成可重开的DOCX/HTML/XLSX及图表。复核数据行数/hash和收益计算口径，不只看文件存在。
验证取消/拒绝无后续取数写文件、重复请求不重复支付/取数、范围不足显示partial、刷新历史、跨会话拒绝、inputs拒绝修改。
最后重跑回归、静态检查和项目完整性/Harness门禁。交付本地地址、真实会话/产物、启动命令及明确不足。若外部数据或授权阻断，保留已完成纵切和真实缺失，不假称完整研究。
