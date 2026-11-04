# 统一事件时间线

时间线位于研究情报，统一浏览历史事件、已公告未来日程与日历事件；日历效应与重大事件使用分别冻结的研究规则。目标历史起点为1990年，未来默认显示12个月，已公告远期事件可继续收录。来源、类别、年份的缺口必须显示，空结果不是无事件证明。全球事件以CN（A股）、US、HK市场相关性为候选标签，仍需人工核对。

FIFA／世界杯及其他体育赛事的自动源尚未实现，当前可人工录入来源候选，coverage明确manual_only。目录中的五个已实现源不代表已经覆盖所有事件类别或1990年以来全部历史。

## 三地市场相关性

自动候选保存event-market-relevance-v1、规则版本、逐市场direct／potential／unknown及原因和原始字段依据。Fed／BLS为US直接宏观背景，CN／HK只标潜在全球宏观传导。GDELT1.0仅从审核的57／58列布局读取Actor1CountryCode（列7）及Actor2CountryCode（列17，均零起点）；CAMEO演员国家码CHN／USA／HKG才直接映射三地市场。Actor名称中的国家文字不会匹配，地理列FIPS码另行保留且不用于演员国家映射，不能把US、CH、HK冒充ISO3或CAMEO演员码。

GDELT事件码为有效三／四位数字、声明root与前两位一致时，18／19／20类暴力／冲突上下文仅给予其他市场potential；不一致或其他事件保留unknown。UCDP的Gleditsch–Ward country_id不套ISO映射；有效state-based violence类型仅作潜在风险上下文，其他或未知类型保持unknown。unknown候选不会丢弃，markets可为空；人工录入／修订仍要求用户明确选择市场。

这些规则是可审计的信息筛选启发式，不证明价格方向、因果关系、影响大小或独立证据。相关性变更属于候选新版本，既有冻结不回填。没有LLM、外部推断调用或自动评分准入。GET时间线返回实际source_catalog的五项来源及各自计划／配置状态，空时间线也能看到来源缺口。

## 状态、时间与研究准入

事件与报道分开保存。事件有稳定ID和追加修订；多份报道可关联同一事件。人工合并、拆分保留父事件及全部旧版本，新事件重新进入candidate。生命周期announced/occurred/ongoing/postponed/cancelled/scenario与研究准入candidate/confirmed/rejected分别记录；scenario不是确定日程。UCDP的date_prec及发生区间原样保留，仅精度码1且起止日相同才提供exact_occurrence_date；其他保留interval／unknown及event_time_eligible=false，不能把区间起点当作精确事件日。

occurrence_start/end是发生或预定时间区间，date_precision保留月／日／分钟精度；source_published_at只来自已核验来源，first_observed由Host归档记录。客户端不能指定取得时间、可信来源、owner、hash、PIT资格或confirmed状态。分钟时间必须包含时区；没有公开时间的历史资料仍能浏览，但不会因人工确认或今天下载而取得历史PIT或正式回测资格。

确认／拒绝支持最多200个精确事件版本，原子执行。任一版本变化、重复ID或原件失效均拒绝整批。冻结仅接受当前confirmed版本，并持久保存事件引用、事件内容、原件引用和摘要；后续事件修订不回填旧冻结。冻结本身不执行DSH、不调用模型、不授权评分或正式交易。

同账号同来源的采集计划首次写入使用owner／source固定身份，经既有RecordStore事务原子
创建；两个不同幂等键不能各自创建一条启用记录。更新继续使用原版本CAS，禁用控制该唯一
计划并阻止后续心跳采集；并发冲突与原幂等重放分别保留，不能把目录中的某一条关闭当作全部关闭。

## 持久化与原件

`TimelineService(research)`使用当前账户Store.root，构造和GET不初始化存储。首次显式写入创建私有`.event-timeline-initialized`、`event_timeline/metadata.sqlite3`和账户绑定。目录0700、文件0600；SQLite追加版本、CAS与幂等收据同事务保存。缺失／空库、跨根副本、符号链接、多硬链接、WAL／journal恢复现场均拒绝；不自动重建或抹掉恢复现场。读写沿resident admission与跨进程保全锁。

原件归档位于该根的私有evidence目录，raw.bin和manifest.json不可变、按来源／URL／内容／metadata寻址去重。读者逐次核验owner、ID、长度、raw SHA256及manifest SHA256。完整性证明不自动提供来源授权或PIT资格；各数据消费者仍执行自己的历史时点与当前权限检查。

共享server-only记录接口为`.records.create(kind,payload,key)`、`.update(kind,id,payload,expected_revision,key)`、`.get(kind,id,revision=None)`、`.list(kind,limit=100,cursor=None)`、`.versions(kind,id)`和`.batch(ops,key)`，返回`{id,revision,payload}`；list返回`{items,next_cursor}`。batch的new_id仅用于服务端显式创建32位hex身份，与更新id互斥，碰撞和同批CAS失败整体回滚，可原子创建日历并绑定行情。namespace固定白名单，不提供HTTP通用写入。动态结果可用`.cached(scope,key,intent)`和`.batch(...,intent=原请求,scope=...)`保证时钟变化不破坏相同意图的幂等重放。

holdout区间claim使用同库事务；不同研究批次不能以偏移边界重复封存或开封重叠数据。多次探索可以登记重叠viewed，已查看区间不能重新充当未触碰holdout；精确同批sealed→opened只执行一次，幂等收据与未知结果另由研究服务核对。

## 固定公开来源与受控更新

首批适配器为Fed FOMC、BLS CPI／就业日历、GDELT 1.0公开档案和UCDP GED 26.1。UCDP官方API目前需要申请访问token，当前没有配置凭据，标为token_required_not_configured，拒绝抓取／启用；免费数据不等于匿名API可调用。本模块不获取token、不发送申请邮件、不读取Keychain，也不借失败切换其他来源。来源目录是代码固定的HTTPS端点，不接受任意URL、请求头、凭据、SQL或模型生成地址。HTTP不使用环境代理、不跟随重定向；8秒网络超时、18秒总限，响应16MiB，ZIP单成员展开32MiB；最多每页1000个候选。超限和结构变化返回稳定错误，不能把截断或HTTP200升级为完整覆盖。

Fed／BLS当前页面不承诺1990年以来完整历史或当时预期值。日程日期已经过去也仍为announced／schedule_only，不凭时钟推断会议已举行或统计数据已发布。GDELT至2005年按年度、2006–2012按月，2013年前三月按月、之后按日；同一档案超过候选页上限时，next_offset指明下一行。固定UCDP GED26.1声明覆盖止于2025年，计划不请求超出该版本的年份；没有因此取得2026年战争实时覆盖。来源目录区分future_supported与历史覆盖，UCDP保留来源版本与原始时间精度，页覆盖不代表完整战争库。解析器不推断报道就是独立事件、不从取得时钟制造新闻时间，也不把全市场候选标签说成已验证金融影响。

来源refresh/backfill仅在明确动作或已绑定的原Automation任务中取数，GET只读。Fed仅解析原生fomc-meeting行中的month／date字段，纪要发布日期、页脚更新日期及页面文字不会生成会议；notation vote与unscheduled保留独立事件类型。BLS只解析已审核regular-data发布表中Release Date列，并要求Release Time列存在；页脚／正文／其他表的日期不产生事件。请求保存source/year/page/offset与检查点；UCDP内部page=0映射官方page=1，下一页仍使用内部索引。失败、取消和中断保留原件、已有事件与失败原因，不自动重试。相同请求键只返回原job；继续工作需显式新的请求并使用已保存检查点。来源内容不变保留同事件；有变化追加修订并重置candidate，不覆盖已冻结样本。覆盖始终按实际页记录partial_page，缺口需独立核对。

解析、归档和最多1000条导入在有界线程中执行，Host事件循环不承担逐条SQLite FULL事务。每账户最多两个来源请求占位，联网前准入；每次写入及事务提交前检查取消、宿主关闭和来源定义。取消后保留active与容量，等待原worker实际排空再记录interrupted，不让迟到线程继续无检查地发布成功或提前释放维护栅栏。已经提交的候选／检查点保留，不把取消伪装成回滚了全部历史。

来源计划默认禁用。未注入原Automation心跳绑定器时启用返回event_schedule_not_configured，不以enabled元数据冒充真实排程。`CollectionScheduler.bind`仅验证并计算稳定scheduler_registration_id，无写入、取数或外部副作用；用户的计划定义、owner、频率和注册ID沿同一CAS事务保存。官方日程默认24小时，GDELT／UCDP默认1小时。

`CollectionScheduler.tick`只由原AutomationService心跳调用，不启动第二timer。每个到期计划在联网前原子保存claim及next_due，最多两个有界源任务；GDELT读取最近已结束UTC日，UCDP保留分页检查点。联网前后及发布前重验enabled、定义摘要和claim，关闭／变更计划不发布迟到数据。失败／中断／未知claim保留现场，不重发同一run；需明确重新配置或核对。构造、GET及没有启用计划的心跳不创建存储。生产启用、实际公开源可达和更新频率另行验收。

## API与安全

统一前缀`/api/research/events`。GET列表／timeline支持发生区间、市场、类别、准入状态、生命周期和有界分页；另有coverage、sources、jobs、详情、versions及frozen。POST创建人工候选、decisions、freeze、merge、`/{id}/split`；PATCH事件需完整新定义及expected_revision。sources/refresh与sources/backfill共用明确source/year/page/offset合同，sources/{source}/schedule配置受控计划。

全部写请求要求现有认证／同源／resident边界及`X-Research-User-Action: ?1`，body使用idempotency_key，版本引用使用`{id,revision}`。客户端不可提交trusted records、源raw字节或评分输入。root Host负责注入`.events`、保全、Doctor和调度绑定。

## 备份、恢复与验证

`.records.snapshot()`／`export_manifest(create_lock=False)`默认不创建锁、不向磁盘SQLite建立连接；持现有保全锁读取有界字节，在内存SQLite验证owner、版本和quick_check，再返回文件清单、长度、SHA256与记录数。最多64MiB／5000文件，超限保留现场并拒绝。

`backup_to(新目录)`一致保存元数据和全部原件及manifest；目标必须在账户根之外，拒绝包含关系、祖先、符号链接／别名，并在mkdir前校验，不能把备份自身递归纳入下一次保全。`restore_from(目录,expected_sha256=...)`核验账户、路径、全部原件和SQLite后才切换，旧目录保留为恢复对象。不得仅备份SQLite并声称原件已保全，生产恢复与清理需遵循原明确授权及生命周期门。

恢复不能让已经查看、封存、开封的holdout重新可用。v1要求备份保留当前records、requests、claims、range_claims的全部历史行；丢失或改变任何已知行会在切换前以event_restore_history_rollback拒绝。当当前库缺失／损坏或目标为空，无法证明外部使用历史时，先持久账户根的`.event-qualification-reconciliation-required`；该标记独立于被恢复SQLite，绑定账户，只能追加、不能通过公开API或普通记录写入清除。历史资料仍可读取，sealed／opened及holdout计算claim拒绝，Host的正式资格与评分接入也必须检查qualification_status。新的前向对账机制另行实现、核验；现有恢复操作不会自动解除该门。备份manifest携带该状态，后续恢复不能抹去已有标记；标记与数据库、原件均属于业务保全。

标准unittest模块`test_event_timeline_storage.py`、`test_event_timeline.py`与`test_event_timeline_scheduler.py`覆盖懒读、CAS、真实并发竞争、账户隔离、缺库、符号链接、原件篡改、合并／拆分、批量确认、冻结不可变、固定来源合同、幂等更新、失败保留、备份恢复、holdout区间，以及合成时钟下的调度claim／撤回／禁止重发。解析成功夹具为明确的synthetic合同输入，不能代替真实来源响应和当期公开源验收；1990全覆盖、真实PIT、部署和生产排程均须以实际回执单独认证。

2026-11-04有界真实验证共发起三个初始来源请求，最多两个并发，无重试或切源。Fed返回HTTP200、166350字节，SHA256为005f9fd0196ab93581a53a3c73b11a216b981efa259f5ac06b03c6072ed4a1e3。实际HTML揭示旧全文日期提取混入纪要日期，已改为原生行提取；同一已保存原件离线核验得到57个来源候选（2021–2027，2025包含notation vote），而非原105个混合日期。真实来源节选及其出处／全文hash进入离线回归，不在测试中重新联网。BLS与UCDP初始请求为非200拒绝，未取得有效原件；官方UCDP文档另明确token与第一页索引合同，代码据此标明受限状态。原失败证据保留在本任务私有logs/event-live-proof，来源可达、解析、历史PIT与业务验收分别记录。
