# 事件时间线／日历效应／六维评分：CI夹具修补完成，待重新验收

- 任务：`events-calendar-20261104`；宿主macOS，Web功能开发。
- 基线：GitHub `master` `87b6cd99653d9f8160dc7eb0b3bea8d5d9ea93db`。
- 独立checkout：`/Users/leon/.codex/worktrees/rwb-events-source-20261104`。
- 受管分支：`codex/events-calendar-20261104-events-calendar`。
- 工作树：`/Users/leon/.codex/worktrees/rwb-events-source-20261104-worktrees/events-calendar-20261104`。
- 当前状态：PR #264首轮候选`16451d02...`完成939项exact验证（938通过、1项原生Windows跳过）；
  Mac安装与Project Constraints通过，Checks在7897项中发现4个旧夹具活动见证失败。
  repair1仅修两测试模块及本报告，130项WIP回归通过；后继1069项exact及新候选CI待执行，尚未合并。
  源码、本机技术验证、真实业务接受与生产激活分别记录，不能互相替代。

## 现场与权限

原项目受管入口实际返回 `NATIVE_LOCKED`。原`.git/index.lock`、原工作区未知文件及其他任务
全部保留；没有清锁。为隔离并发，从GitHub创建独立浅checkout后通过本仓库受管入口check／
configure／start建立上述worktree。新仓库fsck通过且无原生锁；没有迁移或覆盖旧仓库。

用户随后明确授权在独立环境安装现有 `requirements/web.lock` 与
pytest／pytest-asyncio／ruff／black／isort／mypy。实际环境为
`/Users/leon/.codex/worktrees/rwb-events-testenv-20261104/bin/python`，安装记录在
`logs/event-testenv-install.log`，冻结清单在 `logs/event-testenv-freeze.txt`；pip check通过。
产品依赖清单、生产环境与原项目环境没有因此变更。

已执行有界公开来源预检，未调用付费模型、读取供应商秘密、启用实际采集日程、修改生产库、
更新常驻服务或执行Windows/Linux产品dispatch。已按持续授权push并创建PR #264，尚未合并或发布版本。
当前仓库规则的Mac安装CI为macos-15。测试及浏览器使用合成账号／输入，真实研究仍为NOT_RUN。

## 已写入候选

- `event_timeline/`：账户SQLite、不可变版本、确认/拒绝、合并/拆分、冻结、私有原件、覆盖、
  固定公开源与有界任务、备份恢复；来源采集只挂现有Automation心跳且默认关闭。
- `event_studies/`：九指数目录、日历及代理合同、固定窗口、匹配对照、Decimal账本、试验记录、
  封存与一次性测试、相关区块重采样／Holm、持久结果和JSON/CSV导出。
- `market_scoring/`：分市场六维固定配置、时点/单位核验、等权与缺项拒绝、结构性验证身份、
  当前事件/日历适用性与修正上限；研究评分不启用生产总分。
- `event_datahub_bridge.py`：显式引用本账号已有日线、原生日历和冻结节假日定义；核验身份/
  哈希，原始字节和派生输入分别归档。标准时段假设与历史PIT缺口保留，不能伪称官方逐年时段。
- `event_host_inputs.py`：实际Host从本账号Snapshot、私有原件与当前canonical Warehouse查询
  核验日历、代理、指数及因子资料；声明或浏览器布尔值不能授予PIT。紧凑因子矩阵支持长历史，
  逐期可知时间、权限、单位、独立指数／代理、停牌与不复权依据均有失败关闭合同。
- 原Host路由、UI导航、源与研究活动见证、保全、Doctor及模块文档已接入。
  新领域使用 `research.event_timeline`，原 `research.events` SSE会话字典保持原义。
- 事件时间投影由研究及当期评分共用；拒绝不确定精度，不为进行中事件捏造结束日，
  每个revision须遵守自身首次取得下界，预测窗口在开始前必须已知。
- 描述统计明确使用指数日历／价格／范围，ETF仅用于可成交重放；缺指数证据拒绝代理回退。

## 实际验证

下表保留首轮提交前的本地检查点；其后的exact、CI与修补证据见文末追加记录，旧通过不认证新候选。

| 检查 | 结果 |
|---|---|
| 新领域Python完整本地回归 | 最终19文件、189/189通过；十批正式 `run_batch`，每批≤20真实nodeID，均已退役；`logs/event-recheck-final/summary.json`。先前176／188轮与最终复审红绿证明分别保留 |
| 邻接Router Python回归 | protocol／api／service_manager／local_integrations共750唯一用例：749通过、1个原生Windows用例按原声明跳过；另6个夹具清理回归通过；40份回执全部退役，`logs/event-neighbor/final-summary.json` |
| Router Node最终并集回归 | 14文件370/370通过，包含Router全部Node及event-lab／Intel／market-terminal；`RWB_TEST_PYTHON`指向上述独立环境；`logs/event-router-node-final.log`与`.json` |
| 格式／静态／类型 | 全部62个变更Python的ruff／black／isort／AST通过，全部40个变更源码的mypy `--follow-imports=silent`通过，pip check通过；`logs/event-final/static-summary.json` |
| 文档／架构／索引／约束 | 文档治理、架构gate、生成索引和完整changed-set约束门通过；`logs/event-final/`。架构新增14图，API Atlas登记452个声明／449个独立操作 |
| 浏览器WIP实际操作 | 最终UI的隔离Host Chrome六步全部通过，覆盖创建／确认／冻结、PATCH修订、历史只读、拆分／合并、实际Snapshot引用登记、95样本描述统计及缺证据评分关闭；仅VALIDATED且角色匹配的证书可选、人类可读标签及无获准提示正确。0 JS异常、1440/390px无横向溢出、model_prompts=0。`logs/event-browser-last-evidence.json`与`event-browser-last-host-evidence.json`；原旧进程超时及早期证明保留。自身5197夹具已停止，尚待提交树身份绑定 |
| Mac Docker Desktop WIP smoke | 冻结源码34个实际加载文件SHA与当前tree匹配；已有精确本地镜像配本任务只读源码overlay、network=none、2GiB限额的ASGI隔离冒烟通过；原4个Paperclip容器、镜像／卷及ledger不变、builder仍停止，任务资源已回收；`logs/event-docker-final.json`。不是新镜像构建、Linux原生或生产验收 |
| 精确候选CI／生产业务 | 同候选Mac Bootstrap、Research Web Checks、Project Constraints及真实业务接受尚待执行／核验；生产部署与采集激活均NOT_RUN |

早期环境诊断：主项目`.venv`和全局Python均真实返回没有pytest；旧保留环境只读尝试又报缺少
`pluggy._manager`。主`.venv`直接导入fastapi/pydantic/structlog长时间无法完成，精确核验后
只终止本任务自己的导入探针；没有把导入卡住当作测试通过。各代理unittest同样尚未进入用例
执行。该早期阻断已由后续明确授权的独立测试环境消除，未安装到原项目或常驻环境。
后续全部Python批次均用原 `scripts.test_artifact_retention.run_batch`、同任务唯一活动根
`/private/tmp/rwb-events-tests-20261104`、真实收集nodeID及外存JUnit/result/stdout/stderr。
当前为 `mode=wip`，不能充当干净exact-SHA最终验收；提交后须由受管交付重新绑定。

邻接原019批19通过／1失败由旧夹具硬编码 `/private/var` 引起，尚未进入目标锁逻辑；现同时
验证macOS真实 `/var` 或 `/tmp` 系统别名及完全相同的resolve目标，原失败证明保留，原根
重跑20/20后退役。原017批不可读权限夹具和036批FIFO均在产品安全断言成功后补测试清理；
只复查并回收已登记、同inode的合成对象。权限、特殊文件、外部硬链接与严格hash门没有放宽。
恢复证明与原始失败／退休阻断均保留在 `logs/event-neighbor/`，没有改写原证明为PASS。

最早浏览器夹具未关闭原有框架collector，曾触发Gold／Dollar框架的公共只读采集；记录保留在
`logs/event-ui-browser-server.log`。识别后只停止本任务PID25788，后续夹具显式设置
`RESEARCH_FRAMEWORK_COLLECTORS_ENABLED=0`。这不是事件采集激活，也没有秘密／付费模型／
生产日程操作；事件live-proof中的三个来源预检仅代表该试验的调用范围，不能概括整个任务。
最新六步浏览器夹具由主任务核对身份并停止，不继续占用5197。

## 独评修复与证据边界

已写修复包括：日历因子报告合同、两类overlay独立事件门、历史证据与当前输入身份分离、
实际窗口适用性、逐公告日历可得时间、源解析精度、BLS页脚误识别、异步导入排空、备份路径
和原子关联记录。后续又修复原生长期因子大小、单位／当前授权／逐期可知时间、独立指数、
停牌／调整基准、恢复资格栅栏、修订时间下界及预测已知时间；均已进入上述实际回归。
独立Python审查的已知问题由只读复审及对应新增反例关闭；最终提交身份仍须重新绑定。

最终接线复审另外完成四项红绿闭环：默认Host的signal source_ref精确绑定；首次同来源计划
并发唯一性及禁用后的零采集；封存实现摘要覆盖实际研究／评分／Host链且开封前重验，并在
正式评分消费与历史当前资格中拒绝缺失／变更摘要；原生节假日历史／当前共享投影，且必须
由同版本canonical事实实际包含原项并提供可知时间。原始RED、同根GREEN、JUnit计数不一致
的中间阻断均保留，未修改留存／时点／canonical资格门。只读独评已复核四项关闭。

复市跳空继续提供描述统计，但在预检／封存／正式评估拒绝准入：统一下一开盘成交无法取得
此前已发生的跳空，不能把统计收益当作已实现收益。拒绝准入且不消耗holdout的回归已实际通过。
实际私有Snapshot／RecordStore／WarehouseBridge验证15年紧凑因子大小限制与因果流式计算；
独立的明确合成市场完成创建→封存→独立指数预测→代理重放→10000次区块重采样／Holm与
双倍成本→评分。新增默认Host真实来源链以两年合成canonical资料穿过封存及normal／stress
重放，样本资格仍为INSUFFICIENT_SAMPLE，未借短样本产生VALIDATED。它们证明实现可运行，
不能授予任何真实指数基础分、事件加减分或样本外市场有效性。

公开小样本保留原始结果：Fed页面实际HTTP200、166350字节，原解析105条错误候选的记录
保留；同一SHA原件离线修复后得到57条2021—2027会议，排除minutes公布日，无新HTTP重试。
BLS公开请求实际失败；UCDP匿名请求失败后依官方文档标记requires-token、首API页1，
未读取token或重试。赛事自动采集明确manual-only。1990年至今全覆盖、全部三地正式交易及
因子历史PIT和任何真实评分准入均未证明，不能因九指数目录或免费源存在而宣称已具备。

既有三安装入口、requirements/web.in／web.lock、setup_web.py已核对，产品依赖与安装流程
未新增依赖；Mac Bootstrap同一原job补两项静态资源。Research Web Checks原45分钟job
补齐19个新模块，不增runner／job／超时。兼容性仍需精确候选Mac干净安装、固定DSH、
3081/8088健康及Doctor证明。本机源码overlay不认证后续字节漂移或新镜像构建。

## 恢复执行

沿本任务相同worktree和受管账本继续，不重新克隆或清理未归并候选。主任务完成最终扩展
浏览器旅程／只读复审后，执行提交、managed prepare、exact候选验证、发布PR、原必需CI及
macos-15干净安装、分支保护与最新基线校验，再依持续授权合并及本任务资源收尾。
`logs/event-final/run_acceptance_batches.py`已由两轮WIP实际执行验证，支持参数化项目／候选／
外部解释器／日志位置。exact模式强制完整新领域与冻结邻接集合，实际collect并去重校验后，
按最多20个nodeID顺序运行原正式runner；未改写任何WIP回执为exact。干净integration提交后
应实际执行189新用例与750邻接用例共939项，再记录该精确SHA的通过／平台skip与原必需CI。
平台任务JSON模板及当前L4完整规划仅保存于`logs/event-final/`，提交后必须重新绑定候选SHA，
不能把基线HEAD或此WIP规划当作干净候选的验收证明。
Windows/Linux原生与对应设备dispatch保持NOT_RUN交接；本Mac任务不替它们签发PASS。
执行期间继续保护原仓库锁、其他任务、研究数据、服务和恢复证据；部署和日程启用仍另行授权。

## CI repair1：补齐既有活动见证夹具（2026-11-04）

上述正文保留首次发布前的阶段记录；本段追加远端失败后的实际修复，不改写旧证明。
Research Web Checks run `41839575009`实际执行7897个用例，两个worker各返回2个断言失败，
不是timeout、基础设施失败或未执行。安全产物按原策略去除断言正文，保留精确nodeID与失败
分类；实际诊断在原integration的`logs/event-delivery/ci/41839575009-failure-diagnosis.json`。

对feature提交`c9e0953a4d189aa2db8351870189375461b27983`，在既有授权测试环境用原正式
`run_batch`、同任务唯一临时父目录、WIP模式及四个精确nodeID实际复现4/4失败。两个原idle
用例得到active=None；两个Wind poison用例的其他checks出现None。根因为旧测试stub缺少
`event_timeline`、`event_collection`、`studies`与`event_inputs`，新增三个见证正确地将
AttributeError记为UNKNOWN；生产拒绝未知是预期行为，无需生产修复。

本轮仅修改`test_resident.py`与`test_wind_recovery_activity.py`：完整空闲夹具明确提供四个
active=False组件；新增20个参数覆盖逐组件活动和缺字段UNKNOWN，真实cold Host另核对
event_sources／event_studies／event_inputs均明确False。原Wind cleanup_unconfirmed与全部
原断言保留，没有把UNKNOWN改成idle，也没有降低维护／保全门或修改生产源码。

原四例同receipt／root重跑4/4通过并退役，原RED的result／JUnit／stdout／stderr全部保留。
两完整模块实际收集130个唯一用例，按≤20分为七批执行，130/130通过、无skip、七批均退役；
`logs/event-ci-repair1/summary.json`和`reported-failures-retry-green-01.result.json`分别记录
完整模块与定点修复证明。两文件ruff／black／isort／AST通过。此次仍为WIP证据，不能把旧
integration的exact回执改成修复候选PASS；后续由主任务提交、受管repair交付并等待新候选
原必需CI。尚未合并，未执行任何工作树／分支交付清理、生产部署或日程激活。

后继exact选择另存`logs/event-ci-repair1/neighbor-nodeids-880.json`：原冻结750与完整修复
模块130无重叠，合计880邻接；加189新功能共1069项。原750 manifest与旧939 exact证明
完整保留，不把新增选择回填到旧候选。root另在旧干净integration `16451d02...`实际执行
完整CI JavaScript glob，1302项中1298通过、4个条件skip、零失败；见该树
`logs/event-delivery/ci-js-preflight.log`。这证明JS预检实际运行，不能代替后继修复候选CI。
