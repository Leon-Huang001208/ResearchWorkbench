# 今日发现、手动研究与独立跟踪

场景首批增加完整选材的可选v3分支，原七字段摘要和v1/v2不迁移；仍先selection复核，再prepare/review，明确execute后才发DSH。来源／时间／重要性／自选筛选仅作用于有界返回集，未知日期和无规范关联不能称无自选资讯。祖先撤权时文件、详情、回执与重放不输出摘录；仅服务器证明not_created的输入拒绝可修正，普通404及已有未知意图仍只查询。计划的保存／启用和无变化静默策略保持，不因浏览或场景准备而运行。

今日发现位于 `#/intel/discovery`，属于既有“研究情报”。浏览已有事件、准备研究、执行研究、保存跟踪及启用跟踪是五个不同动作。打开页面只读取真实来源与当前用户收据，不调用模型；手动研究和明确启用的计划继续使用唯一 DSH、现有 DataHub 文件快照及 Host 质量门。

## 来源与页面

`discovery/sources.py` 从现有 `intel_routes.read_upstream` 取得 Golddata / Vibe-Research 的固定公开 HTTP GET。请求不接受任意 URL、不发送本机凭据、不跟随重定向；沿原20秒/16 MiB响应边界。页面展示已有事件摘要及第三方判断，保留来源时点、未知时间、陈旧、空结果、读取失败和上游分析错误。来源没有给出的传导、反证、失效条件和资产不补造。

每用户 `DiscoveryService` 的内存预览缓存最多6份/8 MiB，90秒复用，30分钟后失效，最多60个真实事件；超过展示范围用 `bounded` 表明。研究期限是用户问题范围，不声称来源已经按该期限完成因果研究。稳定主题ID来自事件ID，资料包ID/hash绑定事件身份及统一display_fields投影，覆盖传导、反证、失效、verification、priority、资产、分组与结构存在性，即使revision没变，显示判断变化也拒绝旧选择。首页摘要没有预取正文，因此摘要不变本身不能证明正文无变化。手动研究或跟踪首次打开新抽屉时，GET selection先只读该已选事件的完整详情，建立独立scope feed及完整证据Hash；不污染首页缓存，不创建会话/写Store/调用模型。抽屉离页或主题变化丢弃迟到响应，读取失败不能继续freeze/save。

`ui/discovery.mjs` / `discovery.css` 沿已确认v0的主题列表、证据工作区及侧栏，使用真实来源填充。主题和资料选择、研究问题及模式、冻结清单确认、独立跟踪设置都有加载/空/失败/未知状态。离页或选择变化不允许迟到响应覆盖新主题，写入失败不自动重发。旧情报栏目和直达链接保留。

## 手动研究合同

`POST /api/research/discovery/prepare` 接收严格 `Prepare`：UUID `request_id/feed_id`、`horizon`、`theme_id`、1至20个不重复的 `material_ids`、`target_mode=fingpt|claw`、非空且最多6000字符的 `question`。只接受当前用户已登记预览及资料ID；客户端不能提供正文、任意URL、归属或可信哈希。

Host按当前owned selection feed再读事件详情，比较展示投影、revision/hash及完整event/articles/revisions/explanation证据Hash；新抽屉只读核对与freeze/save之间发生变化时409拒绝并要求重新确认。GET selection只是详情核对，既未把数据保存为不可变快照，也未独立抓取链接网页全文；prepare才将核对一致的规范JSON归档冻结，确认页显示实际冻结清单、时点及哈希。随后预分配会话ID，持久元数据归属与创建阶段，写入原 DataHub `discovery_evidence` 快照及 `inputs/discovery-context.json`，最后创建/配置同一ID和cwd的真实DSH会话。准备阶段不发送模型提示。

交接回执可返回经request_sha256重验的原始七字段prepare_request；用户以同UUID再次确认只恢复原配置，参数变化409拒绝，不把此恢复当新模型授权。

`POST /handoffs/{id}/execute` 是独立明确提交，按交接及上下文生成固定执行键，发送前持久 `execution_starting`，调用原 `ResearchService.send` 最多一次。未知创建或受理只查询同ID/cwd、原receipt/历史标记，不自动重建或重发；换request_id也不能重复同一交接。来源或文件哈希损坏、foreign cwd、资料不完整、配置/权限或模型绑定变化都失败关闭。

`trusted_context(sid)` 重验会话、manifest、rows、私有原件及上下文哈希后才交给原质量合同，FinGPT和Claw都需规范 `research-report.json` 与已有Host质量检查。`running`仅证明受理；`incomplete/invalid/report_missing/NOT_RUN`均保留，不能因页面可下载、模型自评或Automation完成而变为通过。

## 持久化与资料边界

首次显式准备才写入懒 `discovery_handoffs` 元数据；初始化和GET不增加旧索引空键。归档资料在当前用户现有会话隔离的DataHub文件中，公开 `rows.json/csv/manifest.json` 与私有原件各自有Hash。读取器已将上游响应解析为dict；私有raw-0001.bin是选择包及完整detail经json_bytes规范化的JSON字节，并非远端HTTP传输、压缩或空白原字节，Hash与恢复均绑定该变换后的归档。来源/Provider为 `golddata_intel`，覆盖为 `explicit_frozen_selection`，不伪装成CLS、厂商原生快照、PIT或Host已抓取网页全文的 `web_evidence`。显式复制给新研究保留原dataset/manifest映射，但不获得旧交接执行权限；不建设第二份对话或研究仓数据库。

## 独立开启跟踪

保存跟踪调用既有 AutomationService，默认 `enabled=false`，原子保存跟踪元数据和锁定定义；单独启用才排入同一个现有调度器，创建不立即执行。计划锁定当前用户、主题、期限、条件、频率/时区、模型/profile、来源与固定只读工具，禁止通过该路径取得MCP、外部投递或任意目标执行权。启停均验证定义版本；原任务历史可查询。

跟踪save从用户已确认的精确cached_preview读取选择，不以较新的首页替换；再只读所批准event_id完整详情核对展示/证据Hash并建立evidence_sha256基线；后续refresh_theme只读这一已批准事件，不依赖首页60条排名。指纹覆盖完整event、articles、revisions与explanation，递归排除retrieved_at/acquired_at/fetched_at采集时钟；同事件新增归档报道会触发，只有取得时钟变化不会触发。缺approved_event_ids或完整证据Hash的旧记录不猜造授权；观察与prepare间再次变化409拒绝且不发模型。未变化时静默、不调用模型；空、陈旧或不可核验来源保留错误，不算“无变化”。每条计划每日最多尝试一次模型研究，未知或失败不自动重复收费；预算是次数约束，不能声称已独立测量货币花费。新资料仍走冻结、原DSH、原质量门；只有Host原check receipt与当前规范报告版本、task和合同实际相连的合格研究才更新accepted基线；公开质量投影是否附报告hash不是独立验收条件，执行/质量/通知分别投影。

服务器模式保持通用 `RESEARCH_AUTOMATIONS_ENABLED=0`、泛用Automation/MCP/Hot/AIHOT接口禁用。账号后端只由宿主显式注入 `RWB_DISCOVERY_TRACKING_ENABLED=1` 开放窄范围跟踪。启动网关从已认证且启用的用户中恢复持久同意，经过原RuntimePool容量准入；不足标记 `deferred_capacity`，不抢占活动研究、不启动第二worker。计划仅在其owner后端存活且原调度器正常运行时执行；离线、容量延期或故障不保证准点/全天服务。没有启用计划的GET不会启动调度器。

## API与实现定位

| Method / 路径（统一前缀 `/api/research/discovery`） | 合同 |
|---|---|
| GET `/feed` | 有界真实预览；`horizon`、显式刷新；不调用模型 |
| GET `/selection` | 校验owned feed/theme/horizon，只读所选event完整详情并生成独立scope feed；无会话、模型或Store写入 |
| POST `/prepare` | 校验选择、冻结、准备同一原生会话 |
| GET `/handoffs` | 当前用户收据列表 |
| GET `/requests/{request_id}` | 丢失prepare回执后只查询确定性交接ID |
| GET `/handoffs/{handoff_id}` | 只查询、校验和恢复投影 |
| POST `/handoffs/{handoff_id}/execute` | 独立明确动作、固定键一次提交 |
| GET / POST `/tracks` | 查询或保存禁用计划；不立即运行 |
| POST `/tracks/{track_id}/enable` | 核对版本与宿主资格后独立启用 |
| POST `/tracks/{track_id}/disable` | 核对归属/版本后暂停 |

账号网关另有 GET `/api/server/discovery-tracking-status`，只读当前认证用户的恢复状态（主管理员为resident_owned，容量不足可见deferred_capacity），不返回其他账号计划或启动后端。

写请求要求 `X-Research-User-Action: ?1` 和原同源/认证边界。模块目录 `app/research_web/discovery/` 分开严格模型、来源投影、创建/上下文、手动编排、跟踪与HTTP；Store/DataHub/Automation只增加必要复用方法。具体接口声明由[API Atlas](../outputs/research-web-architecture/api-atlas.html)与机器清单逐项登记。

## 验证与平台范围

本轮是Mac功能开发；离线合同覆盖来源失败、未知/陈旧、选择和版本变化、持久失败、同账号恢复/跨账号拒绝、Hash篡改、创建/受理未知、跟踪独立开启、去重/日限、容量恢复与既有质量状态。前端回归验证真实响应投影及两条明确操作链，不能代替实际模型质量。

既有Checks同一Python步骤登记 `test_discovery.py/test_discovery_tracking.py/test_discovery_routes.py`，JS沿 `research_web*.test.mjs`；原Mac Bootstrap在同一步逐字节核对 `discovery.mjs/css`。公开三安装入口、锁文件、固定DSH、3081/8088和Doctor门保留，无新依赖或数据库启用。最终完整Router、独立评审、同候选CI由交付报告记录；本模块的真实模型、生产跟踪、常驻部署与Windows/Linux原生层均未据此认证，保持 `NOT_RUN`。

## 原生双栏与最新原始资讯（2026-10-24）

默认原生RWB双栏，使用appearance.css暖灰令牌、字体和控件，不再继承hot-reader的独立配色。最新原始资讯与事件/已有研判分栏，均先按明确发布时间排序后截取；未知时间置后，不以读取时间代替发布或研判时点。保留事件传导、关联资产、反证、跟踪条件与判断履历。

既有Intel /radar与/intelligence通过同一个固定只读reader分别读取；原始资讯最多180条、事件最多60条，共用原90秒/6份/8MiB/30分钟账号内存缓存。两个读取lane分别保存成功/空/失败、原读取时间、本次尝试、最新发布时间、上游缓存状态/明确时点与覆盖信息。一侧失败只保留这一侧旧资料，不能重新赋予旧资料新读取时间；两侧首次失败明确报错。显式refresh跳过Host缓存，只执行既有GET，不触发上游重算、模型或采集计划。上游缺失cache_stale保持not_reported，显式true传递到预览/冻结并阻断跟踪基线，不能改成新鲜。

原始资讯使用news-身份（来源与安全URL的内容地址），source_kind=news、news_id，与event_id分开；无有效身份、冲突版本仅可阅读。内容指纹包括正文/标题/明确发布时间，排除取得时钟与来源的相对time标签。GET selection只读重新取得当前归档；prepare再次核对完整内容及关联指纹，然后复用原DataHub discovery_evidence/唯一DSH两步提交。原始归档是现有源返回内容，不宣称独立抓取链接网页全文。旧event行和旧context v1/SOURCE_POLICY字节不迁移；只有新raw上下文采用v2条件分支。

GET /api/research/discovery/association仅接受本人同一feed中的news_id和已展示event_id；逐次读取指定事件归档，只有article的精确安全URL匹配才建立地址关联，标题近似和同主题无效。最多保留5个已核验候选，记录匹配报道指纹、事件原件和分别报告的研判截止/事件更新时间；缺研判截止保持未知。关系不是事实核验，也不增加独立来源数。GET仅修改有限内存预览，不能创建会话、快照或计划。

raw跟踪继续复用discovery-tracking-v1与原Automation，不更换调度器；批准news_id及显式关联事件范围绑定在锁定定义中，旧event任务的指纹/批准范围/冷恢复保持。原始资讯滚出/radar窗口时标不可观察，不报unchanged、不删除计划、不回退旧档当新观察。已登记的发现任务定义失效时分派直接拒绝，不回退通用执行器。无变化不模型、未知受理不重发、每日一次尝试、模型连接/工具范围与原精确版本质量门保持。

本轮验证只使用隔离Store/DSH替身和只读来源，真实模型、生产跟踪启用及实际常驻切换分别保留NOT_RUN，不能由源码或CI通过推导。
