# 安全边界与验证方法

账号管理迁入设置不改变后端鉴权：浏览器普通用户拒绝挂载管理面板，API仍独立校验管理员。密码只存在当前表单DOM和必要的提交请求，重绘复用DOM，离开页、取消及请求结束清空，不写应用状态/存储/日志。写操作不自动重试，停用/停止/改密保留确认；重置自己密码后回到登录。浏览器验收使用隔离假接口，不能操作真实账号或研究实例。

网关apply-ui为显式管理操作：旧网关→产品仅UI/docs/tests/report，产品→工具仅升级器及docs/tests/report；两段Git祖先、路径和blob及两份GitHub资格分别认证。version 2独立恢复包验证自身内容及实际primary，旧helper在副作用前拒绝该版本；不能以进程内临时放宽review替代恢复合同。原EX锁/出生栅栏/排空/保全不减，发信号后未完成必须保留recovery_required。

自由分析的数值绑定由系统入口和Host独立重建共同执行，不依赖提示词：拒绝Unicode/中文分数/英文数词、裸数字和手写算式；只接受同节所选观测或有界系统配方的完整事实/公式引用。新receipt policy阻止手写payload降级，旧报告不补写policy。Host重建声明、笔记、引用和presentation，并检查审计文件实际字节与语义core；自洽的伪造SHA不能认证文件内容：HTML逐字节重建、DOCX有界ZIP成员/内容逐一核对、PDF invariant确定性字节核对（含可见绘制，不能只查文字层）。解析错误归一为invalid，附件和内容错绑不作为资料缺口放行。原research_quality.py未修改；来源真实性、可比性和解释性分析仍可incomplete。

恢复预算仅扩展专属journal到16 MB，保留通用配置1 MB门；同一O_NOFOLLOW fd有界读取并复查inode、UID、mode、nlink、size与时间。大manifest超过预算时在首个信号前撤本事务栅栏。退出后遇到zombie/签名变化/重用都只等待，不再向该PID发信号；超时延后而非当作退休。

Mac的proc_pidpath把gateway PID实际映像与当前生产venv解释器映像精确绑定；argv0仅允许配置路径、其canonical路径或该映像路径，完整模块/root参数必须一致。发送SIGTERM前再次核验；未知PID、读取失败、foreign映像均拒绝。Mac Bootstrap执行同一原生探针，Ubuntu不冒充该证据。

网关更新必须同时证明不能出生新私有实例、已接纳HTTP已优雅排空及primary Native/Host/自动化空闲；单次owner=0或active=false不能代替。目标持久gate在认证前拦GET与控制操作；未知owner/auth/key/进程、SQLite sidecar及版本不匹配均拒绝。失败先落rolling_back再恢复代码和匹配绑定，不恢复业务旧快照。详见[安全升级](../../research-web-gateway-upgrade.md)。

日期合并出版 meta 与正文 header，冲突保持 unknown；只读缓存同样检查。GDP 只支持明确年度公报主段、核实完整肯定句和明确全年列/计价注释的表格；错列、否定、错期和互相冲突的值拒绝。完整性核对、结构化数值精确复算、覆盖与叙述核验原门不变。

指令一致性回归以真实上传CPI驱动原API，兼测一般资料仍可用原payload；补查指令不续授权或改变Host状态。真实FOMC错字段/错误基点工作簿保持拒绝，沙箱错误不通过自动导入、猜参数或扩大权限掩盖。

显式算式仅允许有界数值AST的加减乘除及百分数，无eval/名称/调用；整数精确、十进制按写明位数ROUND_HALF_UP展示核对，原结构化数值门仍精确。报告链接只由Host实际归档哈希生成，来源/数值未核验不被算术匹配覆盖；附件下载不受报告链接拒绝影响。

当前 SDK 的新增 read-data 精确列出 research_helpers.py、research_report.py、research_report_plan.py、research_report_calculations.py 和 NotoSansSC-Regular.ttf；资源/字体目录只有literal列名权限，绝不添加包父目录或仓库subtree。拒绝软链、多链接和非规范路径；旧会话副本不写。Native回归验证新旧会话所选格式及旧默认交付及新增独立审计附件、SDK只读、未列__init__.py/父service.py拒绝以及既有网络/fork/文件/预算门。原venv读取合同保持，不能把固定SDK位置用作任意宿主路径参数。

派生配方不接受literal value/unit/quote/source；操作只取有界实际原始业务观测，单位/期间/同指标family、零分母与重放scope分别校验。Host评分不信任SDK缓存，独立从原始字节重算后才交原identity门。格式缩减由冻结要求确定，不信任模型metadata；可预览下载不等于通过。新成功测试只认证受控数字合同，原题全文的叙述/缺证据仍保持incomplete。

网页正文的 scope 和截止日不能经上传别名绕过：服务来源清单、source_context、observations、业务索引/快照及 quality_result 共用会话内 Host provenance 分类，web 禁用时不生成网页观测；启用时保留原 as_of 并走原日期门。跨会话相同文件名不继承 provenance；损坏登记不授予上传身份。端到端回归覆盖真实 Host 落盘、关闭 web、未来日期、同前缀合法上传和跨会话隔离。

数据配方仍在既有 script 权限内执行：未知/歧义观测、外来绑定、额外字段、超限、错误单位/算术/父来源继续拒绝。所有分析和控制建议保留在 Host 评分正文，不能藏入工作簿绕过；独立算术一致仅证明计算和展示，不证明公式语义或外部真实性。质量扫描修复同期间多条已核验声明的误报：先删除全部通过原 _verified_claim 的完整原句，再清理期间；数值、期间、单位、引用和缺口判据不变。新增错误值/单位/期间/原句/额外数值/额外分析及双重写入恢复失败回归。

隔离设置页仅回环地址，单次grant兑换HttpOnly同站Cookie并验证Origin；凭据保存与执行评审分开，未获执行评审禁止预约。Keychain值仅到client私有管道/内存；Flash固定ref只读，Lite命名空间独立。缓存重绑定从已验证原始pyc构造manifest，末次扫描只作相等检查，竞争出现的未知文件不进入删除许可。

公开正文工具拒绝调用方任意 URL、凭据、正文与宿主路径，只取当前原生搜索登记的身份。每跳只允许 HTTPS/443，无认证、Cookie或代理；解析全部 DNS 后拒绝私网/保留/多播地址，连接固定数字地址但 TLS 验证原域名，最多两次跳转。响应限2 MB、提取文本20万字符，只接收 HTML/纯文本，不执行脚本。有限读取进程有总时限，超时及取消均 kill/reap；取消前到的墓碑阻止晚启动，同一 call_id 不重复取证。tenant 两个回调仍强制实例私有 key。

正文 SHA/身份/期间、笔记链、覆盖摘录和独立数字复算门不放宽。已检查版本的真实字节与归档/回执精确绑定；未检查或回退版本不得继承其他版本质量。旧报告、完整性错误、未知活动继续 fail closed。

本轮失败样本回归包括：FOMC父来源/观测ID混用和映射不一致、微软非空分隔行/列表单元格、CPI前月与百分点、NIST原句遗漏。负例保留未知来源/歧义metric/非有限数/否定或不完整同比段落/伪造投影拒绝。原Host质量规则不变，真实模型的工具错误、未核验分析与下载状态须另行实测，不能从离线helper成功推断。

resources/research_evidence.json只含当前允许上传资料的有界实际派生，使用既有NOFOLLOW目录fd和原子私有写入；整包≤256000字节。SDK核对task/contract、普通单链接文件和大小；Host判定不读取此副本，篡改/旧回合/外来观测不能据此通过。不存在跳过未核验中文分析、删除missing或增加补查预算的路径。

业务证据helper只解析调用者数据和计算，不联网、读凭据、写可信observations或覆盖质量状态。独立Summary展示舍入策略不能传入Host；非有限值、重复键、公式、伪造身份/观测及真实缺口继续拒绝。资金方向、宏观表头和治理来源还需对实际官方原文独立审查。

Host业务适配只读取当前会话允许的完整小型UTF-8输入，严格绑定原文表块/列顺序、肯定决议句、完整所选记录及用户根/会话/任务/冻结合同SHA。模型自写business_observations会被忽略；外会话、旧SHA、评分时变化、跨文件缺父引用均不能通过。原文/字符位置随观测保留，外部真实性、可用日期、中文推断与组织实施不能因规范化被认证。未知/歧义/截断布局不生成新事实；无网络/路径/代码表达式能力，原质量算法及一次补查预算不变。

calculation_evidence不建立信任，只序列化调用者提供的观测；Host仍从本会话实际输入独立复算并核对ID、数值、原句及冻结要求。伪造/外来观测、真实missing和缺失覆盖负向测试仍拒绝；helper不读写凭据或自动改写旧报告。

CSV复算只接收受限data-only配方，无eval/exec/网络/任意路径。最多4配方、8价格列、100000行、每输入16MiB；拒绝bool、非有限/极端数字、非法UTF-8、宽松截断CSV、重复表头、缺失单元格与未知字段。按规范列序用固定Decimal精度复算；每次重验全文SHA，缓存仅有界结果，隔离用户根/session/task/算法。

stage release-reservation 要求指定完整 CID/image/source 和已完成任务标识，复查原归属、停止状态与卷无其他容器引用。先归档回读原账本，失败保留预留；禁止用于 prod。

max_additional_instances只接受整数1至4（拒绝bool、字符串、空值及越界），旧默认1保留；本机显式3表示primary加3共4。Doctor仅检查私有有界无链接文件并失败关闭。容量提高不放宽逐用户数据/凭据/执行隔离，也不是OS内存限额；本机须保留主机余量，不因轻量RSS测量宣称真实重型研究已验收。

恢复端口只来自该UUID私有根内通过既有严格parser验证的DataHub/MCP控制记录；要求同一规范IPv4回环URL、私有权限、无链接及无未完原址事务。先bind预留再启动；占用失败不接管监听、不旋转控制token，日志仅记稳定错误码。

primary 原版 UI 与静态资源根由已验证 project 身份选择，不能由 URL/header 指定。AIHOT 原阅读仅对该 primary 走原 backend，仍有同源、认证及页面身份检查；不向普通用户开放此附接例外。

显式附接例外只给可信服务器所有者 primary 管理员：原个人后端保留既有能力与回环边界，不获得逐用户令牌；Tailscale 根入口经新认证网关，受邀普通账号始终绑定私有令牌保护的新 pair。绑定验证原目录 dev/inode、owner、安装与 Git SHA、归属及健康，不通过失败回退指向其他根。原实例由原监督器拥有，网关不能停用其账号或停止它。保全检查不得忽略业务 tmp/.lock 或未知链接；匿名健康不执行昂贵探测。原监督器兼容拒绝策略保持。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](../../research-web-ai-news.md)。

## 私网邀请制账号与执行边界

服务器模式仅在 macOS Native 显式启用，固定一个 Tailscale HTTPS origin/Host；回环 HTTP 仅供本机开发。Tailscale 网络准入和产品账号登录分别验证，无公网注册或 CORS。账号库用 scrypt 密码摘要、随机 Cookie 令牌的哈希和到期时间；密码不进入参数、日志或浏览器持久存储。HTTPS Cookie 为 HttpOnly/Secure/SameSite=Strict，12 小时过期；未知账号与错误密码同样失败，登录失败有界限速。停用、密码重置和退出登录即时撤销对应登录态；最后一个活动管理员受保护。

认证用户 UUID 由网关决定唯一 backend 和文件根，浏览器的 owner、目标地址、Cookie、Authorization、代理头或伪造内部密钥不能选择其他实例。研究提交所需的 `Idempotency-Key` 按原值透传到已认证用户的 backend；网关不生成缺失键，也不从键选择用户或扩大请求权限。逐实例私有令牌保护后端直连；DSH 的允许内部回调另验数据密钥，浏览器不能经网关访问 internal。下载、搜索、SSE、取消和审批复用该用户既有会话与文件校验；SSE 与流式下载在撤销后停止交付，换账号旧页由页面身份标记拒绝。代理请求体有界，同源响应使用 no-store；上游重定向拒绝。

全局AI资讯不选择用户backend：gateway固定使用 `server_root/shared/ai-news`，成员仅阅读，status/control仅admin；tenant后端完整拒绝全局AI路径，即使实例key有效也不放行。未知AI路径不会启动DSH。管理复用精确Origin和页面身份，64KiB流式限额后重验有效admin，读取返回前复查撤销；浏览器凭据和伪造Node key不转发，原Node session/CSRF保持私有。共享目录与用户研究根分开，不扩大同UID隔离承诺。

每用户 Web、DSH、HOME/TMP、端口、数据、状态和系统凭据命名空间分开，不继承管理员 HOME 或密钥。服务器 profile 在 UI、API 和原生 guard 禁用宿主浏览器、Office/Wind、MCP、Hot、日程/自动化、报告 Workflow、本机连接配置和运维；文件式文档仍可用，native 文档必须在实际执行及签名回调入口拒绝。模型只允许官方 DeepSeek，不接受任意 Base URL。

**同 UID 信任限制：** 数据目录与进程分离不等于 OS 租户安全边界。首版信任固定 Web/DSH 后端和受管工具实现，研究脚本继续使用现有 macOS Seatbelt；不承诺防御同一 macOS UID 的恶意进程、被替换后端或任意插件。此模式只服务邀请制受控网络，不能据此开放公网。默认两驻留实例满时拒绝，不为容量回收终止研究；未知 PID、所有权记录或崩溃残留失败关闭。部署、原数据迁移、真实模型/来源和各平台验收必须分别授权及留证。

全文HTML转为白名单阅读树，丢弃脚本/样式/iframe/SVG/表单和事件属性，节点30000/嵌套64上限；正文图片仍只能使用上游签发路径。前端独立限定标签/链接、转义文本、仅本地sec目录跳转，不插入原始HTML。详情身份不匹配或专题合并环明确失败；摘要/部分正文如实标注。

AI资讯Host只访问已归属本机API，所有私有请求使用token，不转发浏览器Cookie/Authorization或环境代理，不跟随重定向。原引擎API额外要求原管理员session/CSRF；浏览器只可使用有限管理动作，秘密只在本机凭据库或600私有文件中接收。零调用默认关闭模型、付费源、通知，逐次预算及持久授权到期失败关闭；未知付费结果等待人工账单核对，决不自动超时释放。

正文保持惰性树与同源CSP；图片只接受本机API签发的不透明映射，有界大小、并发、时间与MIME。原采集逐跳SSRF规则保留，并拒绝aihot.news及其子域；没有外站故障回退。备份/恢复仅作用于身份核实的新独立库，进程与资源使用任务归属和锁。真实模型及生产切换验收独立，未执行为NOT_RUN。

质量工具复用内部 DataHub token、可信原生会话血缘及原工具预算；普通网页不能伪造观察证据或授权补查。Host 冻结用户要求，模型 coverage 仅提出定位。来源身份与内容分别核验；无法独立验证的定性陈述、数字期间/单位冲突保留未通过。损坏/错配产物为invalid并拒绝正式导出；旧版本以 Host 哈希锚定，不把任意自建输出目录当认证历史。离线测试不证明真实模型或供应商可用性。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

导航写接口按模式验证现有会话/项目身份、退役状态、唯一ID与revision，持有原service锁并原子保存；过期版本409且不自动重放。项目/置顶是本机显示元数据，不授予跨模式资料引用或研究权限。问题补充内容和答案不进入UI诊断日志；跳过不是自动化试跑或权限授权。

正文搜索使用固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73` 的显式部分搜索接口：Host 将 RWB 已创建、未删除且符合当前模式的 ID 范围传给原生层，再与原生列表可见范围取交集。响应必须包含完整范围内的 `unavailableSessionCount`；Web 返回 `unavailable_count` 并在零命中时仍提示部分历史未搜索。旧格式源记录保持不变，不授予恢复执行；I/O、损坏及取消仍失败。未升级的旧接口缺少覆盖信息时明确报错，不假称搜索完整。

resident 仅在本机明确安装后生效。固定控制器 artifact/目录身份/进程归属与精确端口，
按 EX admission → lifecycle lease 顺序切换；HTTP 用户写操作、研究提交及自动任务均参与共享锁。
journal 存在时崩溃后仍拒绝新写入；恢复失败保留 blocked。日志不含凭据或提示词。
GitHub 合并事实、matching review、本地完整交付及三个工作流实际 checkout tree 均须匹配；
成功的旧 SHA、其他树、未分类路径、依赖/迁移/控制面变化均不放行。
不改变 FileVault、Keychain、Tailscale 成员/ACL，不启用 Funnel，不自动安装新依赖或迁移数据。


正文搜索先验证独占Runtime归属，再调用固定白名单session.search；严格校验20行/240码点响应并过滤RWB未持有、未成功创建、已删除或模式不符的ID。没有第二正文库、跨会话上下文注入或隐式研究；查询/片段不写日志。UI只临时保存当前明确搜索结果，关闭/导航立即清空并拒绝迟到响应。

Claw试跑授权不交给模型：只解析句首祈使、实际任务名/精确ID、配对引号、可选当前版本与有限附加约束；引用、解释、条件、否定、其他任务或版本漂移拒绝。扩大可识别的明确语句不改变批准的工具/资料/输出范围。Automation错误仅传播固定稳定码，原4KiB、JSON、正则、重定向拒绝、取消与无自动重试边界保持。

每轮资源收尾只接受同任务归属、已登记目录身份和白名单类型；删除前复查Git跟踪状态、inode、进程及容器引用。未知ignored数据/其他任务/未归并提交仍拒绝。构建器维护持有rwb-docker原操作锁，验证单节点/endpoint/卷与实例绑定；不得用同名Buildx重绑定清理远端或其他实例。in-use记录由BuildKit保护，内存门或恢复失败即blocked，不绕过原Git可恢复备份和审查门。

Native 可通过 `RESEARCH_WEB_PRIVATE_ORIGIN` 显式信任单个精确 Tailscale HTTPS origin。
默认 Host 列表不变；指定域名仅接受 HTTPS、默认 443，Host 与 Origin 必须配对。
仅根路径 `/` 的用户触发顶层 GET 文档导航可从外站进入：mode=navigate、dest=document、
user=?1，且 Origin 缺失或与本站一致。显式外站/null Origin、跨站 API/静态资源、
iframe/后台请求不获得此例外；原文档/OAuth 专属导航例外保持各自边界。
X-Forwarded-Host 不授予信任；可信回环代理的协议由 Uvicorn 原有 proxy-header
合同确定。无效配置仅记录稳定错误码，不回显输入。私有 DSH/DataHub 认证和 CSP 保持原门。
操作安全清单：确认代理仅在 tailnet，Funnel 关闭、成员获准、客户端无私网域名代理劫持；
单个 RWB 实例不提供按 tailnet 用户划分的研究/凭据权限，获准设备具有同一实例权限。
配置、认证、证书、跨设备 HTTP 与真实 SSE/模型是分别验收的状态。

数据型Word子执行不导入会初始化旧设置的日志facade，避免只读镜像根目录写入和开发.env
读取；沿既有report_documents的标准日志进入父进程日志。隔离进程禁用core模块仍能
生成并重开Word，这是无旧配置/模型环境依赖的反例测试，不是新增模型验收。

schema21周期报告由唯一Hot任务领取：私有bootstrap选择已安装产品Python，只执行固定
hot_periodic_report模块，以有界stdin传冻结资料；25秒、SIGKILL/取消与8MiB输出硬门。
该模块复用brief_docx/report_documents，不加载DSH、读取模型凭据或对外发送。子执行MD/DOCX
与hash先存不可变PG表，再由hot.brief专用controller事务与领取/队列共同完成；其他任务继续
使用worker角色。未知完成恢复复用既有子执行回执，旧租约、计划改版或停用拒绝晚到提交。
reader只能有界分块读已保存报告，Host复验固定metadata、完整长度和hash；GET不重新执行。
研究联合ZIP同时限制含metadata的展开总量与实际ZIP大小。新PG inventory哈希直接使用
数据库JSONB精确文本；未标记的旧JS数值hash无法证明精度，保留旧档并明确要求原库重备份。

字体兼容不扩大sandbox：getcwd、network connect和未准入资源依然拒绝。chinese_font_path
仅由模块绝对__file__定位打包字体，缺失或alias固定错误退出，不扫描其他宿主文件。
非2xx错误摘要只取4KiB JSON中白名单code，redirect立即拒绝，流读取/清理不超过原超时信号；
scope拒绝仍deny且不登记资源，只追加安全missing.code摘要。准入快照只是提示，不能覆盖实时guard。

外部资料取数只使用登记的固定 endpoint；认证请求必须为 HTTPS，检查在读秘密前执行。
HTTP 认证来源保留目录和 `credential_transport_blocked`，不以配置完成冒充可调用。
秘密不得出现在原始响应、解析后的数据、日志或会话快照中；测试仅使用合成凭据。
兼容模型的传输实现不替代 endpoint/model 的工具验证，未知组合保留未验证准入。
脚本结果仅在可解析且明确 status=completed 时标为完成，未知和损坏结果失败关闭。
推理块必须在正文或工具块开始前结束，取消和后续非法推理保持原失败语义。

评价器不信材料hash格式或自报official：核对完整冻结row、目录主体/origin、packet完整材料字段与response/packet指纹；跨partition主事件/ID/URL及参考URL泄漏拒绝。生产候选历史重叠单独披露，不改真实回执以制造独立性。没有独立人工金标准，不输出accuracy；source-review-only案例模型NOT_RUN保留。

日期纠错使用原同源/显式动作/UUID/expectedRevision及签名controller权限。Python发送前验证真实日期、时区、精度与引用shape；Node核对版本在当前事件并与原文quote字面匹配，权限/owner和旧PIT合同不弱化。日期依据文本转义，日志不记录正文。真实PG覆盖worker拒绝、旧版未知、自动保护、撤回解锁和无效引用不落盘。

分页拒绝跨origin、非HTTPS、凭据、fragment、循环、多next和重定向；三页各4MiB、整轮25秒，不复制SDK/Key，不增预算。真实PG测试覆盖后页HTTP失败/水位保留、顺序排空和事务中断回滚。

来源UI的permission旗标只作提示，Node在新激活写入前核对实际config列UPDATE权限；真实PG revoke反例确认拒绝新请求且保留旧回执读。表单不接受URL/凭据，文本转义，显式checkbox+有界理由才激活；SDK/model权限不变。真实组件浏览器保存及审计核对、错误console0通过，不替代完整安装/镜像验收。

source.configure的useCatalog只接受严格true及非空有界理由，绑定DataHub同ID/同operator，拒绝URL和其他adapter。controller新增sources.config列UPDATE，普通worker仍无该权限；条件版本/审计/owner双检保持。真实PG覆盖错误operator、旧owner、UUID重放、目录不可读时缓存复用、落库指纹与大整数/旧版本不变。升级先停止setup，新镜像和MacCI须另验。

Hot周期aliases去除旧Automation feature guard后仍调用相同Hot query/body/user-action及签名controller合同。关闭旧Automation时GET/POST Hot适配不访问旧服务，原Automation GET仍404；无动作POST403、明确动作POST200和Hot503传播均有回归。不得为修复Hot页面而启用旧scheduler或扩大预算。

pre-AES例外只在显式stage replace的两次owned验证内使用，要求ready账本、停止原容器、精确四挂载、无RWB_MODEL_环境和旧镜像无加密标签；新镜像须AES。普通owned继续拒绝缺密钥挂载。运行中、已AES镜像、模型环境、projection变化及initializing反例均拒绝并且没有Docker rm调用；26项本地回归通过，不冒充实际容器验收。

处理选择接受最多20个唯一材料UUID并小写归一化；省略/空列表保持默认范围，不授权费用。现有预算、发送回执、owner/领取租约仍为硬门；旧代次不能调度，超过正int32优先级范围拒绝。真实PG测试核对未选择积压原ID/状态保留、重启仅领取所选材料和零模型调用。真实Native处理沿已明确使用的原安装固定凭据桥接，不复制密钥，隔离home未配置的失败单独保留；不外推为Docker模型验收。

关注和周期计划仅controller获得INSERT/有限列UPDATE权限，worker只读这些表。计划不接受模型、工具或外发配置，周期run不接收用户SQL。固定输入/选材与审计不可改，发布前后核对当前claim和计划，慢写期间租约过期须整体回滚；空窗口/取消终态也复核领取。非法日期偏移、时间下溢、未知配置和非严格布尔/整数拒绝，凭据与控制key不进入页面、审计或产物。

研究页面prepare/execute经现有同源API及X-Research-User-Action提交；GET不调用执行。选材必须属于当前冻结简报且唯一、有界。缺失/未知响应不清除原请求，过期响应不覆盖新视图提示；服务仍校验会话归属、快照hash和固定问题绑定。接口替身测试不算真实付费执行。

已启用Hot模型的同项目私有配置才选择官方零重试；非法配置不探测凭据或阻断基础Web。
正式执行先PG登记、再既有send，失去受理回执只查原生marker。未发送取消必须停止态、
迁移owner、匹配instance/token和无发送/回执证据；未知发送不退款。真实PG和否定用例覆盖。

Hot流桥核对私有key、owned Runtime和Store/PG归属。prepared单发、未知发送不退款，
回执先存后输出，迟到取消及逐块回放检查signal。大帧/HMAC/稳定错误码有真实loopback测试；
真实厂商研究和安装CI尚未执行。

AIHOT阅读组件继续转义标题、理由、标识和版本文本；快捷频道/排序校验现有范围后仅GET。
新筛选请求清空旧列表/分页，过期成功与失败都由generation隔离；没有可续页时拒绝more。
视图不获得控制key、不创建任务或研究。外部页面模型榜等非开源模块不伪造可用状态，
原站blocked/567记录为未取得视觉证据，不通过绕过浏览器/网站保护补造验收。

研究预算预留与不可变 call/attempt 映射在同一 owner fence 和 PG 事务内提交；只由
控制角色插入映射。已有结果按原 attempt 复用，不受后续日期或 run 终态影响；取消或
缓存指向其他 attempt 时拒绝，不通过相同 callId 再扣费。实际 LLM 流尚未接入该边界，
因此不宣称已约束正式研究费用。Native route 继续经固定 ref 的只读凭据 seam 解析。

research.model五项私有操作只接受控制key，核对run/session/call/ticket/scoped budget；
发送前的运行状态与价目检查和预算dispatch处于同一owner事务，终态竞争不能准入新发送。
回执可跨日恢复，费用由服务按冻结价目计算；实际DSH流桥尚未装配。大帧只用于receipt输入
与reserve缓存返回，仍受签名、权限、实例/模式/代次、连接、时限及1MiB业务回执上限控制。

Hot 阶段一内部服务使用仅回环可达的签名消息：请求/响应均以 HMAC 验证，key 不进入消息；
校验当前实例、模式、代次和操作权限，并在真实数据库代次变化后拒绝旧端点。响应在编码前
检查凭据反射，限制绝对时限、帧大小、连接与在途数量。读取入口暴露状态/来源/任务投影，
不暴露 SQL 或凭据管理。配置入口拒绝 alias、FIFO 和非私有存储；未知参数不回显输入。
Native 管理器在发信号前核对 PID 启动身份与 launch nonce；受管 PG 恢复前核对标签、卷、
固定镜像和回环端口。角色不得重叠，已有 schema 所有权先于迁移检查。Keychain 持久化、
完整产品安全与跨模式验收仍待验证，测试通过不表示跨平台已验证。
归档按当前实例 key 认证，并验证实际传入恢复工具的 Buffer；禁止覆盖现有 schema。
容器内工具具有 deadline，失败后按唯一 application_name 取消对应 backend；无法确认的
结果保留 outcome_unknown，不能伪称已回滚。Python 中断也信号回收独立 Node session。
HTTP 采集限固定 DataHub catalog 来源、禁止重定向、限制时限与字节；解析不获取原文中的链接。
pg-boss 监督仅由控制角色执行，增加 job_dependency DELETE 与 version.monitor_backoff_on
列更新权限，并在启动前检查。普通 worker 不能修改版本编号、迁移或运行身份。
Native stop 识别 zombie，TERM 后 argv 暂变只观察，最终再核对身份，拒绝对变更 PID 升级信号。
新增 `source.configure` 仅允许控制 key，拒绝读取 key；校验请求 UUID、配置版本和固定参数。
普通 worker 无 enabled/frequency/config_revision 更新和 source audit 插入权限；审计不能覆盖。
客户端不能认证或完整解析操作回执时显示 outcome_unknown 并保留原 ID，禁止伪报成功。
累计模型额度由迁移所有者显式授权；worker 只更新计费字段/尝试状态，无授权插入或额度改写权限。
预算、发送和回执已做真实 PG 竞争验证；实际 provider 上限、秘密反射防护及真实费用未验收。
DSH text adapter 必须使用零重试 prepared call，并在保存前做同步秘密安全过滤。
固定验收入口已装配每日准入与任务累计额度；正式 Web/worker/研究装配仍未完成。
Native credential 服务只允许固定模型 ref，拒绝写入/记录操作与环境回退；解析后 JSON 字符串和键也检查反射。
验收先核对原 PG 容器/卷/实例身份，再迁移，不能接管同名的外部 schema。
Native CLI事件查询只用reader key，配置/纠错只用controller key。廉价结构、字段范围、UUID与
JSON非有限数/编码/大小校验先于控制凭据查询；Node仍负责版本、归属、来源和图完整性。
回执须确认标题锁、频道集合、合并canonical目标、移动材料移出/移入和保护，不能只凭revision
宣称成功。不可信、不完整或迟到响应保留UUID为outcome_unknown；已知版本冲突明确拒绝。
测试父Python退出后通过独立身份核验的Manager.stop回收Node；不是系统Keychain或跨平台证据。
Hot Web复用本地Origin边界；控制正文必须有明确动作标记且先过字节/类型门。桥接不开放任意
操作/SQL/路径，凭据按当前模式选择。超时线程保持容量，关闭后二次检查拒绝等待中的写入。
UI转义原文并限制外链协议/无userinfo，持久选择与详情cutoff防跨页混合；未知写入原参数重放。

预算新增不可退款预留：调用失败或预先取消仍扣票，迟到响应不能延长期限。旧政策 2026-10-10 到期，当前真实时钟拒绝；不得自动刷新费用、日期或旧账本。截止通过固定 SDK 公开 Agent.cancel 中止已绑定的原 transport signal；原生 loop marker、会话身份和当前 owner signal 均校验，陈旧 timer 不能取消下一轮。供应商远端计算是否停止仍不由本地 abort 认证。历史时钟夹具只验证机制，真实模型和其他平台仍未运行。

研究工具边界仅新增精确 `todo_write`，仍要求启用研究及 Agent 归属，沿用48工具/4子任务
预算；相似名称、任意 shell/宿主文件和既有拒绝项不得随 Todo 放开。计划正文来自原生日志，
UI 转义显示，项目日志只记错误状态/事件计数。无稳定 item ID、缺回合或序列缺口不猜测身份；
坏数据不保留完成清单。Todo 完成、研究终态和文件交付各自独立。真实集成使用测试私有根，
不触碰生产 runtime、秘密或付费模型。

私有凭据模块使用项目已配置的标准日志 handlers，不加载会创建全局目录的 Settings。
隔离导入测试拒绝 core.settings 导入；实际只读镜像中的 bridge 仍须独立验证。

Docker 模型后端使用已有 cryptography AES-256-GCM；主密钥独立随机生成并在业务运行时只读挂载。
密文 AAD 绑定稳定实例身份和固定 ref；无环境/旧文件/Keychain 回退。权限、alias、篡改、
错误主密钥和中断写入须失败关闭；真实生成、重建后生成与合成隔离分别验收。

ETF工程模拟沿原同源/回环边界，只有显式用户POST；工程上传不提升DataHub或receipt-gated Skill权限。
SQLite参数绑定、私有叶目录、8MiB输入/结果预算及100次运行上限限制本地存储。同UID可改产品根的
信任边界未被声称解决。真实数据闭包、算法比较、完整门禁、浏览器和安装CI分别验收。

Markdown预览仅将响应类型转为`text/plain`供浏览器显示原字节，下载类型保持原状。文件读取仍通过原会话归属与目录FD校验；预览保留无同源权限的sandbox、原CSP、nosniff和无referrer，不增加脚本、HTML转换、外部导航或任意路径读取。

RuntimeMode 读入共享祖先时，初始 stat/open 与后置验证统一比较 dev/inode/mode；祖先替换、符号链接或权限变化仍拒绝。立即私有父目录继续比较完整元数据，UID、0700、文件0600、链接数与FD验证均保留。确定性回归允许无关 sibling 创建/删除，拒绝祖先替换、符号链接和私有父目录变化；该修复不变更系统配置或权限。公开活动证据的32KiB上限按 UTF-8 字节计量，数值字符串保持类型。

研究型 Automation 的模型目录与执行期批准工具同时受限，未知目录或执行快照失败关闭；执行追问不得通过恢复草稿扩大范围。公开工具证据使用共享预算、深度和节点上限；递归秘密字段、认证/Cookie 头、带引号及未闭合凭据先脱敏再截断，transport error 同样处理。测试只用合成秘密字面量；数值型字符串答案保持类型，脱敏不丢失合法确认历史。

Claw 研究任务的确认卡展示模型、时间、时区、资料与工具白名单；仅明确点击后保存启用，不授予 MCP/外发权限。独立运行仅采用 SELECTABLE 工具，原生准入逐次核对任务 approved_tools；空数组不扩大权限，执行会话不能管理日程。聊天试跑必须来自真实最新用户肯定指令与匹配任务；单请求受理索引拒绝跨任务重用，未知受理不自动重发。确认更新使用预期版本，已删除稳定 ID 不得通过旧卡恢复。历史异常仅影响展示，不放宽归属、执行或交互权限。原生提问成功受理后清除等待状态，失败保留问题。

启动恢复回归固定端口选择以确定进入控制地址变更事务，保留所有原有身份、字节回滚与拒绝恢复断言；另测同地址 prepare/rollback 不改写内容、stat或journal。原生子会话归属使用固定源码实际导出的 `parentSessionId`，错误父归属、来源与非布尔活动状态仍拒绝。
模型空闲检查允许原生标为 unknown 执行模式的历史条目仅提供已经核实的活动状态；内部 activityOnly 标记须为真布尔值，默认详情和执行模式门禁不变。回归覆盖原生活动 true/false、缺失 live、外来父、错误来源和字符串布尔值，不删除历史数据。

Claw 项目只是产品索引分组，不授权任意宿主文件访问。文件聚合校验所属会话，显式引用在复制前核对项目和普通文件身份、复制后核对哈希；接收文件使用所属目录 FD 创建，来源变化明确拒绝。
日程提出端点由原实例私有认证保护；确认/取消端点校验会话归属。模型草稿拒绝 MCP 与投递权限，不能直接启用日程。确认稳定创建键绑定内容，重复请求不得生成第二任务。
相关回归为 `test_claw_projects.py`、`test_automation_drafts.py`、`test_api.py` 和 `research_web_automation_draft_tool.test.mjs`；这些测试不替代真实模型与同平台 CI。

新管理入口验证私有管理根与记录无alias、环境/实例labels、不可变镜像、容器ID、
完整配置/挂载、网络、资源限额及卷归属后才启停/重建。Docker在start时把
`OomKillDisable=null`补为false，两者同为启用OOM killer；只规范化该等值默认，true和其他变更仍拒绝。
管理代码在只读绑定的管理员worktree中，瞬时控制器独占Docker socket；业务/dev无socket。
独立BuildKit 3GiB初始编译不足，实测冷构建借stage额度至5GiB，与stage互斥，退出停止；
入口另核对VM实际内存与所有运行容器硬上限，保留2GiB余量。未知无限额容器拒绝。
容器隔离不替代用户鉴权或任意代码沙箱；显式 Docker 模型加密文件桥之外的多人授权、
严格 Linux 沙箱、公网及其余 G2-G5 工作仍待实施。

Docker 清理只执行经预览的精确身份，并持指定 home 的现有生命周期/安装锁，复查保护和引用。
卷归档的源挂载为只读且 `volume-nocopy`，辅助容器无网络/端口；恢复卷与辅助容器有独立任务标签。
辅助镜像的未绑定 VOLUME 使用 tmpfs，避免隐式匿名卷遗留；辅助容器删除只释放自己的匿名卷。
错误与中断停止后续处置并持久化回执，日志不记录 stderr、环境、数据内容或秘密。

## 资讯雷达 · 2026-10-09

资讯适配器只开放固定目标的 11 个 GET 路由，不转发浏览器 Authorization/Cookie、不继承代理环境、不跟随重定向；请求总超时 20 秒，JSON 响应上限 16 MiB，禁止任意 URL 转发。标的、ID、分页与游标有界验证。远端内容转义，原文链接只接受 HTTP/HTTPS；既有 CSP 保持同源。未提供上游鉴权时显示服务不可用，不读取本机模型或业务凭据。

新版原生模块解析使用 `createRuntimeResolution`，每个 packageDir 必须属于固定源码或两项既有受管供应包；解析成功不扩大模块白名单。认证 bootstrap 的 source_commit 从共享 runtime 合同读取，仍验证所属进程、cwd、端口与私有控制文件。preset 注册迁移不改变固定模型 ref 的 Keychain 私有桥接，也不让模型 ref 委托回旧环境/文件解析器。父子活动状态未知时配置和提交失败关闭。

Automation 恢复不重发研究；缺 ID、未知提交和 workflow/version 冲突失败关闭。初始报告保存失败时，只有已验证 Runtime 事实源且本次确实新建的活动 Run 才允许停止；陈旧/错误引用及恢复期间保存失败不能取消既有任务。日志只记录固定事件、类型和 Run ID 摘要，不含 Prompt、文件内容或凭据。受控 macOS 进程探针只处理自建进程/临时私有根，不证明真实 DSH/model 或其他平台。

Docker DSH builder 的[下载参数](../../research-web-installation.md)仅将现有 pnpm install 并发设为 8、
单请求期限设为 120 秒；frozen lockfile、默认重试、registry、TLS、签名和最低发布时间校验保持。

停止端口等待不授予所有权：只在实际 NativeRuntime 的初始状态已确认运行、显式
stop-current 与公开 stop 成功后执行；原 Native 端口在停止前冻结。预算在停止前
拒绝 bool、数值子类、非有限、负数与超过45秒的值；巨大整数先比较界限。
等待不刷新 ForeignLedger，不重试已失败的 guard，不用 SO_REUSEADDR；结束后仍走
原 lease/scope、新状态和 CAS。日志仅固定 begin/released/timeout，不含身份或秘密。

模式切换 finalize 日志仅输出固定模式、拒绝分支与显式 allowlist 的首个 issue 代码；未知、
非字符串及空 issue 映射为 `unknown`，仍运行映射为 `none`，不输出 report、异常、路径或秘密。
严格 running 类型检查、短路、错误优先级、所有权、锁与模式 CAS 均保持原合同。
Native status 日志只记录固定 precheck/child/postcheck 阶段和固定 code，不输出子进程原 issue 或 stderr。

容器 Web 启动探测使用 3 秒单轮总期限，并裁剪到剩余 35 秒角色启动期限。
Runtime API、首页与主静态模块仍须全部通过状态码、媒体类型、正文标记与响应大小检查；
认证会话、PID 绑定、2 MiB 响应上限及精确子进程清理不因预算调整而放宽。

macOS 异根 Native 认证仅复用既有私有 launch ledger 信任模型。OS UID 的标准产品根是
唯一候选；不使用 HOME/环境 override 扩大发现、不遍历其他用户或 checkout、不读取进程环境、
认证秘密或执行候选源码。两角色必须完整且一致，相关 listener PID 集合精确等于已认证 pair。
alias、不安全 owner/mode、单角色、额外未知 listener、PID 重用、argv/start 或记录/root 替换拒绝。
Web 的 data-root 关联来自可信私有记录，未增加密码学或进程环境独立 attestation；既有同 UID
可任意替换私有内容的信任边界没有被宣称解决。只读结果不产生写 capability；实际 lease 下的
调用内 FD/身份观察才参与写门，scope/lease/controller 不匹配与 lease 丢失均失败关闭。
原同根/未知写者拒绝、认证 token/额外字段保留、精确 ID 回滚和 stopped-port-conflict 均保持。

本次 Native spawn 不以 `(role,pid)` 单独授权：scope 保留原 Popen 对象与实际 state writer
FD，publish 前后及后续复核命名记录/FD identity、owner/mode、metadata；同内容换 inode
亦拒绝。实际 start 在启动阶段只建立一次，稳定 owned-listen 时冻结完整 argv 与 exact
listener 基线；其后变化永久失效，重复登记不重新捕获。停止阶段的合法退出不授予新 writer
权限。Popen 返回后登记丢锁须收尾该精确新 child，保留原错误；未知记录或进程的普通
rollback 不发信号、不删记录，health 错误继续为主错误。普通已有实例和认证字段合同不变。

调用内拒绝是单调失效：已捕获 scope 看到未知 target 槽或不合法 own-child 退出时，统一撤销
同一个 RAM 观察；未知记录后来删除、其他事实恢复原样也不能重新授权检查或 rollback。
本次精确 stop 的 stopping/stopped 退出阶段属于预先验证的对象，不按未知退出撤销。
该失效不持久化，finally 仍清观察与 FD；下一次调用须独立取得完整当前证据。

target 槽读取的非 missing I/O 也先撤销当前观察再传播原错误；Docker 仍报告原 docker_io，
不降级为空槽。权限/I/O 恢复不能使同 scope 重新获得 mutation 或 rollback 权限。

安全拒绝与完整清理边界保留必要的宽异常捕获，逐处说明单行 lint 例外；不会为消除
BLE001 而记录异常正文或缩窄到可能遗漏失败的类型。日志 handler 失败仍返回原拒绝路径，
可选身份分类失败仍记录 `other`；验证脚本的 `check=False` 明示既有退出码断言责任。

Docker fresh-root 权限不能由 mode、manifest、venv、bool/tuple、只读状态或外来 lease 推导。缺失观察限同一 controller 外层真实 `_locked_guard` 的私有父 FD/lease/元数据与稳定 OS 事实；真实 mkdir 后首次 open/fstat 捕获并 pin 当前根身份，up 前失去分配权限。捕获后的 parent/root 身份、lease、mode 记录值、PID/端点/监听或容器变化拒绝；已有根不授予该例外。另一个 controller 不能转移 witness；外层 abort 仅在本次容器已精确退出且原 lease/根/父/监听与 CAS 一致时恢复，本次恢复不授权重试。所有 witness 在 finally 清除，原通用目录/生命周期 guard 与认证实现不放宽。

mkdir 到首次身份捕获非原子，沿用 Native/Supervisor 创建模型，不承诺抵御同 UID、可写 HOME 且不遵守 lease 的任意捕获前替换。mode 比较沿用 RuntimeModeRecord 值和逻辑 CAS，不跨读取保留 mode 文件 inode；合法同内容换 inode 不单独使 witness 失效。该边界不改变私有读取的 alias/owner/mode/no-follow 校验，也不改变安装摘要发布时独立的字节/FD 身份恢复检查。

启动认证链接不得进入普通日志。产品Node preload在固定DSH CLI之前截获stdout/stderr认证行，临时启动token只进入既有0600认证控制文件；管理器验证authority/cwd/source_commit后交换Cookie并移除临时token字段。输出拆分、错误端口、过长无换行输出均不转发认证链接；控制写入拒绝别名、硬链接、非私有或非当前用户文件。模型Key与该Host认证平面保持分离；用户录入阶段不采集DOM、HAR、截图或请求体。

macOS Native 的固定模型 ref 通过 owned overlay 挂载产品 provider，私有 stdio 桥接只允许 resolve/describe/set/unset 与所属规范化 data home。桥接使用受管产品 Python，直接选择 macOS Keyring；其他平台、未知后端、拒绝访问或进程失败均失败关闭。秘密只存在系统库和受控进程内存/管道，不进入 argv、环境、URL、普通日志或报告；只散列公开 data home 路径生成命名空间，不散列秘密。不新增通用取密 HTTP API、不复制生产 Key。合成值 Keychain 验证与真实供应商生命周期分开。

模型配置保持同源、回环与专属 Runtime 所有权检查。不回退环境、`.credentials.yaml`、项目 `.env` 或 DSH_HOME `.env`，不复制 Keychain 值到旧文件。浏览器认证的 client-connection/browser-session 与 readRecord/modifyRecord 仍使用固定 DSH 原有受控实现及独立 `.browser-credentials.yaml`；模型未配置、清除、桥接失败不使 record 接口失效。配置保存不读取旧秘密制作备份。活动父/子任务阻止凭据更新；凭据提交结果未知时拒绝新请求，不能假定旧秘密未变。最小生成是用户显式操作，不由列表、刷新、Doctor 或保存自动触发。

Docker 模型桥仅接受 owned overlay 的显式后端和私有凭据挂载绑定。Fernet 记录位于独立
`models/` 子目录，使用原目录/文件身份守卫、0700/0600 和进程锁；子目录与主密钥首次创建
串行化，主密钥不隐式轮换，密文校验命名空间及固定 ref，重放到另一 ref 失败关闭。
既有通用凭据和浏览器认证不迁移。API Key 明文只在受控进程/管道内流转，不进入 argv、
环境、日志、安装摘要、镜像或业务索引。主密钥与密文同一私有挂载，不抵抗同 UID 或管理员
读取完整挂载；不把该存储合同当作研究代码沙箱。合成值测试、配置保存与真实推理分别留证。

Docker Doctor schema 1 的 volumes 只投影固定类型：data/logs/credentials=bind、state=tmpfs；logs 为新增非秘密字段，不暴露路径，verified 仍须实际 inspect 成功，失败或缺容器为 false，查询不写目录。

`runtime_state_directory_rejected` 的私有日志在原拒绝分支记录固定原因
`invalid_type/reparse_point/unsafe_owner/unsafe_mode/identity_changed`，阶段限定
`enter/open_fd/pre_yield/post_yield`，范围仅 `ancestor/leaf`。身份变化仅列
`dev/ino/mode/uid/gid` 字段名，不输出目录名、路径、身份数值、文件内容、Cookie、
token 或异常正文。既有外层未分类错误保留通用事件；日志 handler 失败只放弃诊断，
继续原 `RuntimeStateError("runtime_state_unsafe")` 拒绝与异常传播。
该取证不放宽任何 owner/mode/no-follow/身份校验，不修复目录、不预写认证、不重试。
容器公开启动诊断仍为原五字段，CI artifact scanner 不接收此私有日志。
确定性负面测试证明日志与 guard 合同，不证明真实 Docker startup 或根因已修复。

`identity_changed` 私有事件另含 `ownership_transition` 和 `position`。
只有完整 `(uid,gid)` 从 `(0,0)` 到当前进程对时分类 `root_pair_to_runtime_pair`，
相反完整匹配为 `reverse`；混合root/runtime组、foreign GID、其他变化、无法读取进程对，
以及进程对本身为 `(0,0)` 均为 `other`。`position` 仅由检查节点与叶的关系派生为
`leaf/parent/other_ancestor`，不硬编码Docker挂载路径。分类只是拒绝后的诊断，不改变guard、
不证明具体业务写入层、不授权初始化修复；原字段和公开五字段启动事件保持原合同。

已安装生产包的发布载荷不因嵌套 `doc/docs` 名称被裁掉；Workspace 仍按 files 和目录
negative 规则选择，绝对/越界声明拒绝。包顶层开发目录/README/suffix 及任意层级 Git/cache
元数据过滤、source asset escape 和 manifest 哈希校验保留；嵌套 README 仅是载荷元数据，
不构成可执行能力或秘密读取权限。源码回归不能代替真实 Docker 生命周期验收。

根模块别名复用 pnpm hoist 的选中目标过滤与冲突检查；模块根须为规范真实目录，选中别名须
严格解析到固定源码内的生产实体，输出相对链接。测试覆盖 scope、坏生产链接、越界、冲突、
替换与资产 escape；未选开发别名不复制，launcher 不跳过私有模块校验。

Docker stop 的端口认证先于任何 stop mutation：原 status 验证精确 loopback Web mapping，
已有 Legacy 映射恢复实际端口后固定调用内 ID/image/ports；后续 inspect/status 必须一致。
错误 0.0.0.0 或晚期 mapping 改变不先停止，宿主释放等待不包含容器内部 DSH；外来占用
保留，超时仍拒绝，不删未知实例，不产生新的 endpoint 或模式 authority。

固定Compose构建独享每路2MiB预算，完整argv精确匹配，默认/metadata64KiB保留。既有stream在token/auth等行外，抑制SOCKS、userinfo、loopback及明确proxy行的传输URL，保留错误文字与普通公开HTTPS下载URL；跨chunk按行脱敏。超限精确清理本次树，不操作无关进程。

DSH builder 使用同一固定 Node stage 的本地 headers 与 builder-only nodedir，避免 node-gyp
另下载不同 headers；不关闭 TLS/签名、不改官方软件源/依赖锁/代理协议。最终 runtime 无该
开发目录或 ENV，继续原非 root、受管挂载与完整 staged-image 校验；源码合同不替代真实构建。

Docker host CLI代理允许列表：仅http/https、localhost或loopback IPv4/IPv6、显式1..65535端口，
输入≤1024ASCII字符；userinfo/path/query/fragment/control/畸形/非回环拒绝。大小写变量同时
存在须校验后相等；均空禁用，空/非空或不同值冲突拒绝。URL归一化scheme/host/IP/端口，
NO_PROXY保留合法列表顺序/拼写（仅trim元素空格），两种列表不同也冲突。
NO_PROXY输入≤2048字符/64项，每项≤253字符，仅host/IP/CIDR/*或*.domain/.domain；无URL、
凭据、端口或控制字符。有效配置追加localhost,127.0.0.1,::1本地bypass，输出有界至2074字符。
诊断/安全stop滤除无效pair，稳定warning/Doctor状态无原值；构建以实际传给Popen的同一已验证
env快照失败关闭。ALL_PROXY、DOCKER_HOST/TLS/任意provider秘密仍排除；共享minimal环境不变。

installer auto-start 只借 manager 实际持有的同一 lease/mkdir 身份，bool、tuple 或持久
marker 不能充当 fresh；root/lease/监听变化拒绝，no-start/失败退出失效。公开重执行限定
精确 owned venv/已有 marker、同脚本原参数 -I，在创建根前完成，保持批准的 HOME/Node/
代理/credential-root，不输出环境值、不添加全局包或新协议。

失败停止既有容器须重新核对精确 ID、image、installation、mount 和 launch；任一替换均
保留对象。安装摘要恢复必须匹配原发布写 FD 的 inode 与字节，同内容替换不成为恢复权限。

无 Native 环境/账本的只读监听证明须取得 alive PID、无错误的 argv 与启动身份，并复查
进程身份和监听 PID 集合；同数据根/当前 checkout 进程或不完整/变化事实拒绝。端口可连接
本身不证明归属；Docker 容器仍必须独立核验安装/image/mount/实际 mapping 和健康。

稳定 PID/argv 与其他 checkout 不证明产品写者的数据根不同：Web 环境和 DSH 配置均可能
指向当前根，可识别产品命令无该证据时拒绝；不读取全进程环境或秘密。共享判定同时约束
Native 静止与 bind retry。fresh 根只认本次已验证生命周期 lease 内成功 mkdir 的 inode，
替换拒绝，首个 spawn 前与 finally 失效；不能用既有安装目录、测试目录名或环境开关伪造。

另一个严格限于本次回滚的恢复证明要求原 lease 仍持有、根 inode 未替换、本次所有 Popen
对象已精确退出，原外来监听集合及 PID/argv/启动身份未变。未知/新增 writer、PID 重用、
root/lease 替换或本次对象仍活着均拒绝；内存基线不读取环境/配置，不记录 argv/秘密到日志。
恢复证明不能恢复分配权限；恢复不确定时保留原错误和 intent，附加稳定诊断并停止重试。

macOS 动态端口启动在共享生命周期锁内验证两模式静止后重绑成对可信origin；仅URL改变，
token与其他有效字段保留。显式占用端口拒绝，自动候选不代表已保留监听；只有完整真实健康
后写实际端点。Docker prepare-only guest必须匹配安装ID、单次nonce、不可变image、固定command、
受管data挂载与无发布端口，成功/超时均按精确ID复核并清理，未知替换不删除；不挂载真实凭据。
EndpointStore.restore仍受本次发布快照CAS和严格私有目录校验，回滚不重用旧revision。
临时guest UID映射与完整双模式往返仍待真实macOS验收，源码fixture不等于平台安全证明。

端点与成对 origin helper 已接入公开启动链，独立负面测试继续保留。端点 schema/type、Native
不同端口、CAS revision、私有目录/文件与单链接均严格校验。新 helper 仅接受 POSIX 私有权限
边界；这不构成 Windows/Linux 验收。共用原子 writer 保留旧调用默认行为，新 `strict_parent=True`
禁止目录创建/权限修复，发布后仍持有写 FD 并与路径身份对照；未来操作须再次核对身份。
端点写锁也显式使用严格父目录入口：可以创建缺失私有目录，但现存目录在预检之后变为非私有时
只拒绝、不 chmod。原 RuntimeModeStore 未传严格选项的旧调用保持原行为。

内部 origin 事务只处理 `.control/datahub.json` 与 `mcp-runtime.json` 的已知 schema，复用原 token/
URL validator，拒绝重复 JSON key、漂移旧 origin、非私有父目录、alias 与内容相同的 inode 替换。
`origin-transaction.json` 仅保存固定文件名、回环 origin、阶段及私有身份/摘要，不保存 token
或原始记录备份；原始字节仅在进程内用于回滚，摘要也不进入日志。标记残留表示 interrupted，
不自动猜测崩溃恢复。第二次写失败只有在整个 pair 仍可证明属于事务时才恢复；发布身份不确定、
foreign 替换或未知静止状态保留标记并失败关闭。commit 不要求服务仍停止，但重验文件归属。
原 DataHub/MCP `load_control()` 继续拒绝未经显式事务的 origin 漂移。

容器启动诊断只记录固定阶段/异常类别、errno 和两个子进程退出码，不序列化异常文本、
路径、命令、环境或输出。CI 仅接受精确五字段、枚举白名单及有界整数，最多保留 16 条；
未知字段或无效记录丢弃，原始日志行继续全部省略。
launcher 不再将异常字符串写入失败事件；CI 只解码 runtime 角色的固定 child 日志封装，再按相同五字段规则验证。

启动前无容器不等于启动后同project容器就是本次创建：回滚还必须验证本次随机launch label、
候选image与全部原所有权项。临时Compose overlay仅添加此非秘密标签；`--no-recreate`
禁止改造既有停止容器，未知/不可读/不匹配状态不删除，保留原失败与恢复失败issue。

Docker Desktop bind 根的 UID 映射不能替代私有目录所有权证明。Docker-only 使用挂载内
由非 root 容器 UID 创建的 0700 子目录；原 runtime_state_directory 与 File credential
backend 的 owner、mode、dirfd/no-follow 检查保持不变。新增回归覆盖启动前准备、重启复用、
state/credential alias 和不安全权限拒绝；物理 bind 映射必须另记真实 Docker 证据。

Desktop首建阶段仅凭据与产品日志两个固定缺失叶可采用安全mkdir后重新pin：父FD全程保留，dev/inode/mode
与路径一致不得变化，仅固定mount父允许root:root→当前UID:GID。已有叶、自定义路径、foreign
UID/GID、权限改变或节点替换仍失败关闭；原runtime_state与credential backend源码规则不变。

Docker 状态通过 `/state` 私有 tmpfs 隔离 Desktop bind 父节点映射，选项为
`rw,nosuid,nodev,noexec,uid=10001,gid=10001,mode=700,size=1m`。controller 有界 inspect
同时核对实际 Mounts 的 Source/Destination/Type/RW 和 HostConfig.Tmpfs，后者必需三个 tmpfs；
兼容 Engine 省略 Mounts 的 tmpfs 重复条目；任何显式条目仍严格检查，bind/volume 遮盖拒绝。
按选项语义核对 UID/GID、八进制 mode 与字节 size，拒绝未知、重复、矛盾或缺失选项。
已有认证、健康与 runtime_state_directory 的 owner/mode/no-follow/身份检查保持不变；
状态叶不再享有 bind 映射例外，也不进行文件预写或权限修复。
host state 根及其 logs 子目录必须私有且归属明确；只在正常受管生命周期创建缺失 logs，
只读查询不创建，alias/foreign/不安全既有目录拒绝，旧 runtime 内容保持原状。
Docker VM tmpfs 可能进入 swap，见 [Docker 文档](https://docs.docker.com/engine/storage/tmpfs/)；
认证每次启动正常重建不等于秘密永不落盘。真实镜像与 macOS 验收仍需独立证据。

Docker 公共 start/Doctor 必须安全读取接受摘要并按不可变 image ID 核对实际容器，不能因
共享 tag、静态 runtime label 或 `running=true` 就宣称 ready。回归覆盖摘要损坏/缺失、
alias/hardlink/超限、锁/Compose/DSH 不匹配、tag 改写、延迟健康及失败回滚归属。
合同 pin 仅放宽无关祖先内容活动，直接父目录瞬时 alias 检测保持；API/集成测试的内存
keyring 隔离只在测试作用域内生效，不降低生产凭据后端的错误传播。

构建时保留 pnpm hoist 拓扑须逐项核对目标属于已选生产图；未选开发/平台别名不复制，hoist 根别名、目标改变或输出冲突失败关闭。新别名同样进入派生资产摘要与启动前验证。

Docker 与 Native 复用固定运行合同，但部署证据分开：Docker 构建需验证完整 DSH 来源/闭包及精简运行资产清单，镜像内再以非 root 做 Web、CLI、supervisor 和健康入口检查。Compose 不向宿主发布 DSH 3081，只 bind 共享产品数据、独立日志和独立凭据目录，运行状态使用私有 tmpfs；只读根、cap drop 与 `no-new-privileges` 不是宿主系统集成能力证明。Host controller 对容器归属标签、镜像、挂载和端口做有界核对，未知实例不删除或接管。Docker 凭据目录的 Windows ACL 不能证明时返回 `docker_credentials_acl_unverified`，不得用 POSIX mode 位替代 Windows ACL。Native 保留系统 keyring。模拟单元测试与源码检查不证明真实 Docker 镜像、Windows 生命周期或第三方软件可调用；它们应在任务回执中分别列为未验证门。

一键安装只允许固定 PyPI 索引、指定 DSH GitHub 仓库和随包 CJPY 文件集；Python 锁、wheel、来源、
提交、工作树与 DSH 构建闭包任一不符即关闭失败。子进程环境采用允许列表，不传应用密钥；安装器只
修复带当前 checkout 所有权标记的 `.venv` 与 DSH 目录，并拒绝符号链接/Windows 重解析点。
Git 可保留 SOCKS 代理；pip 与 Node 只继承 HTTP(S) 代理。大小写非兼容代理变量均被移除，安全日志只
记录过滤数量，不记录地址、认证信息或原始值，也不修改宿主进程环境。
DSH clone、checkout 与干净工作树校验都只对当前子命令应用同一组长路径、换行和 Windows symlink
配置，不修改机器级 Git 配置；Windows 进程检查与 `taskkill` 均以参数数组且 `shell=false` 调用，
并在终止前复核受管命令签名。Windows Node 构建的允许列表只额外保留 PowerShell 模块、标准系统程序
目录与系统盘发现路径，供 `node-gyp`/MSBuild 使用已安装的 Visual Studio C++ 工具链；不传应用密钥
或任意环境变量。
服务启动在 spawn 前复用 Doctor 的安全化安装投影；未受安装器所有的 checkout 环境、锁漂移、
CJPY/Node/DSH 未就绪均失败关闭并只输出稳定 issue code，不以 35 秒健康等待掩盖安装错误。
后备 status/Doctor 只用标准库读取有界非秘密状态，不加载 Runtime auth 或执行生命周期操作。
后备顶层 `--help` 更窄：只输出固定命令与安装提示，不读取状态、凭据或监听端口；其他未知命令
及未安装环境中的生命周期操作继续失败关闭。
共享私有 JSON reader 对 POSIX 使用 no-follow 描述符与 0600/单链接检查，对 Windows 拒绝
reparse 并复核打开前后身份。普通服务归属须同时证明 state 签名、精确 argv、进程启动身份和
监听 PID；不能证明时为 unknown，不凭 PID 文件或端口猜测。生命周期 guard 锁串行化状态恢复；
只对再次核验为 owned 的进程停止、回滚或清理 auth，foreign/unknown 一律失败关闭。
HTTP 就绪探测直连回环、不经过代理，正文有上限；JSON 限制媒体类型、UTF-8 与对象形状。
Doctor 只输出 allowlist issue/warning，不含 Cookie、命令行、代理 URL、响应正文或模型失败详情。
Node 选择只接受显式路径、受控环境值、可执行的 Codex bundled 路径或 PATH，并在版本门禁后用于
所有 Node 构建子进程。Runtime build lock 只能由固定 commit、规范 SHA-256 与固定文件数的已验证
DSH state 原子更新；文件数必须是严格整数。POSIX 逐级使用 `dir_fd`、`O_DIRECTORY`、`O_NOFOLLOW`
和独占临时文件，Windows 逐级校验 canonical path 与 reparse point；最终文件拒绝 symlink、hardlink、
越界大小和非私有 POSIX mode。安装器在写锁前只对当前用户拥有的产品 data home 收紧为 0700，
未知 owner 或 alias 仍失败关闭。缺失、陈旧或路径不安全时 Doctor 和 start 均失败关闭。
状态命令的轻量导入只避免在诊断前加载 DSH Capability/MCP 功能图，不跳过任何归属、端口、认证或
HTTP 健康核对；Doctor 与 start 仍延迟加载并执行完整构建闭包和安装证明。
`--repair` 仅替换所有权 marker 与 checkout 哈希均匹配的环境，并保留旧目录作为回滚副本；pip
探测和 Web import readiness 都使用不含应用秘密的 Python 子进程允许列表、有界超时和稳定错误码。
首次安装写入前原子发布 `status=installing` 的最小清单，使已有 `installed` 证据立即失效；只有
依赖、Web import、固定 DSH、Runtime lock 和最终清单全部成功后才重新发布 `installed`。

Gold 与 Dollar 快照在路径解析前拒绝任一现存符号链接组件，限制为 2 MiB，使用各自严格 schema 和内容 revision，并同目录原子替换。旧 Gold V1 结构先保留为 `snapshot.legacy-v1.json`；已存在备份时拒绝覆盖。生产浏览器不导入测试 fixture，来源失败不得伪装成实时成功。Bot 上下文另设 80,000 字符上限，默认解释预设不暴露工具。

全局 Artifacts 枚举忽略软删除会话，显式访问墓碑仍返回 410；资产观察不加载或显示该错误域。恢复会话后，其真实产物才重新进入全局目录。

## 当前部署的信任模型

这是单人、本机回环部署，不是公网认证或多租户隔离方案。浏览器请求由同源与 Host 检查限制；BFF 确认自己管理的 DSH 实例与会话归属。3080 不是产品执行端，模型凭据只由专属 DSH 管理，研究脚本没有凭据环境变量。

| 边界 | 实际约束 | 核对位置 / 测试 |
|---|---|---|
| Web → FastAPI | 本地 Host、同源、输入 schema；不开放任意代理 URL | `main.py` / `test_api.py` |
| FastAPI → MCP Registry | 官方端点固定 `/v0.1`，私有 Registry 仅显式配置；认证 Registry 只允许 HTTPS，无认证 HTTP 仅限 `127.0.0.1` / `localhost` / `::1`，OAuth 端点始终为 HTTPS，客户端不跟随重定向；同名身份隔离、游标不解释、ETag 与最后成功缓存原子提交 | `mcp_registry/` / `test_mcp_registry.py`、MCP 市场 JS/E2E |
| Registry 凭据 → 系统凭据库 | Bearer/OAuth 秘密只存 Keyring `ResearchWorkbench.MCPRegistry`；索引、缓存、日志和响应不含秘密 | `mcp_registry/credentials.py` / `test_mcp_registry.py` |
| Registry 文本 → 浏览器 | schema 校验与长度限制后保存 Unicode plain text，拒绝 control/surrogate；数据层不做 entity escape，最终 HTML sink 单次转义且不热链图标 | `mcp_registry/models.py`、`ui/mcp-marketplace.mjs` / Python、JS、E2E |
| Registry 版本 → 本地安装 | 只接受固定 npm/PyPI/MCPB 目标；完整依赖与哈希、直接 argv、`--ignore-scripts`、隔离目录、最小环境、安全解包和短期摘要确认；PyPI 在解释器缺少 pip 时只允许已存在的 uv 执行同一离线计划，禁用用户配置并使用 staging 私有缓存；禁止 shell、范围/latest、钩子、隐式环境和链接越界 | `mcp_runtime/package_resolver.py`、`package_planner.py`、`package_installer.py` / `test_mcp_installation.py` |
| MCP Host → 私有安装目录 | staging、安装 payload、清单与确认令牌重放目录拒绝非目录、符号链接和 Windows 重解析点；POSIX 额外校验 group/other mode 与所有者，Windows 不将 mode 投影当作 ACL | `mcp_runtime/installation_store.py`、`package_resolver.py`、`package_installer.py` / `test_mcp_installation.py` |
| Research Web Host → 远程 MCP | 仅 HTTPS 或字面 loopback HTTP；无自动跨源重定向；OAuth 使用 PKCE/state/元数据发现/受众校验，token 只进 `ResearchWorkbench.MCPRuntime` 凭据库且不 passthrough | `mcp_runtime/transport.py`、`oauth.py`、`sdk_host.py` / `test_mcp_transport.py` |
| DSH → MCP Host → Server | DSH 只加载命名空间化声明并经私有 loopback 控制令牌代理；每次调用重核安装版本、schema 哈希、会话快照、风险和一次性审批；参数正文不进日志或审批列表 | `runtime/mcp-adapter.mjs`、`mcp_runtime/authorization.py`、`service.py` / Python 与 JavaScript MCP 回归 |
| Automation → Claw / MCP | 每个 Run 使用独立会话并锁定目标版本、内容 SHA 与工具 schema；无人值守只允许任务明确授权的只读工具，私有数据须任务级授权，高风险工具拒绝 | `automation/service.py`、`mcp_runtime/service.py` / Automation 与 MCP route tests |
| Automation → 投递渠道 | 研究/投递状态分离；HTTPS 或字面 loopback、SMTP STARTTLS、通用 Webhook 固定事件 ID/时间戳/HMAC；渠道秘密只进 `ResearchWorkbench.Delivery` | `automation/delivery.py`、`channels.py`、`transport.py` / delivery、channel、transport tests |
| 本机诊断 → 宿主 | 发现只读取标准位置/注册项/模块；真实验证须显式触发并限制目标、Office 容器内确定名称的临时文件、独立进程组和超时；Excel 使用本轮独立实例，PowerPoint 保存后按随机文件名重新绑定本轮对象，Wind 复用已登录 Excel 但只操作独占空白工作簿，且只上报验证器真正拥有的进程供精确清理；投影排除绝对路径、秘密、命令与环境变量 | `local_integrations/`、`report_workflows/workbook.py` / `test_local_integrations.py`、`test_report_workflows.py` |
| 浏览器 → 集成写操作 | 仅接受精确同源 `Origin` 和显式用户动作头；探测与授权快照只保存白名单状态字段，原子文件权限为当前用户。该边界不抵御同源 XSS 或能伪造本机 HTTP 请求的同用户进程 | `integrations/` / `test_integration_coordinator.py`、设置页 JS 回归 |
| FastAPI → DSH | 固定回环 RPC、共享有界认证控制读取、文件身份/别名检查、方法白名单、双事件通道 | `runtime_auth.py`、`client.py` / `test_runtime_auth.py`、`test_protocol.py`、`test_event_recovery.py` |
| 服务管理 → 私有目录 / 进程 | spawn 前要求 Doctor 安装事实及 Runtime build lock 通过；拒绝非目录、符号链接和 Windows 重解析点；POSIX 检查 group/other mode 位，Windows 不将 mode 投影当作 ACL，并以无 shell PowerShell PID 探针和 `taskkill` 管理受控进程树；Profile 的 symlink/junction 最终目标必须留在固定 DSH 源码树 | `service_manager.py`、`launch_runtime.py` / `test_service_manager.py`、`test_runtime_launch.py` |
| 用户 → 会话文件 | 会话归属、规范路径、安全文件描述符、有限上传体积和类型 | `store.py`、`main.py` / `test_store.py`、`test_artifacts.py` |
| DSH → 工具 | 精确注册工具集合，子 Agent 深度、并发和步骤限制 | `runtime/guard.mjs` / `research_web_guard.test.mjs` |
| 会话 → Tabbit 标签页 | 当前 Runtime 生命周期内的会话授权；发送前按所选实例实时重验可 claim 的 HTTP(S) 标签；正文仅进入绑定会话、单次消费、10 分钟过期的 DSH 内存 token | `tabbit.py`、`runtime/tabbit-adapter.mjs` / `test_tabbit.py`、`research_web_tabbit_adapter.test.mjs` |
| DSH → 公开数据 | 15 个品牌无关工具常驻；私有认证 BFF 入口在每次调用时按最新安全状态选源，固定来源/参数，无任意 URL、重定向或自动安装 | `runtime/public-data.mjs`、`datahub/` / `research_web_public_data.test.mjs`、`test_datahub.py` |
| 脚本 → 宿主 | macOS Seatbelt 内核约束，环境变量白名单；只读 inputs/resources，仅 outputs/tmp 可写，无网络和子进程 | `sandbox.py` / `test_sandbox.py` |
| HTML → 浏览器凭据 | 隔离 iframe，后端 sandbox CSP，无同源权限；模型 Markdown 先转义 | `main.py`、`ui/markdown.mjs`、`ui/views.mjs` / UI 安全测试 |
| 研究结束 → 交付完成 | 本任务输出基线、哈希复核、沙箱解析与重开；旧产物、附件和正文不补文件格式 | `delivery.py`、`delivery_validation.py` / `test_delivery.py` |
| 导入包 → 本地存储 | 有界读取，不 extractall、不执行；拒绝穿越、链接、祖先路径冲突、嵌套压缩及伪装可执行；图片/PDF 容器证据检查 | `capabilities/packages.py` / `test_capabilities_safety.py`、`test_capabilities_review.py` |
| 草稿 → 原生发现 | 检查元数据、调用方式、脚本哈希、已安装依赖与精确工具名；活动任务阻止发布/停用/回滚 | `capabilities/catalog.py`、`routes.py` / `test_capabilities.py`、`test_capabilities_admission.py` |
| 原生能力 → 当前研究 | 仅专属 Skill root；所有启用包检查依赖与关联版本，再复制只读资源；失效包不能在自主发现时绕过 | `capabilities/catalog.py`、`runtime/research.cordis.yml` / `test_capabilities_native.py`、`test_capabilities_review.py` |

包管理后端最近完成 233 项完整 research_web 回归与两轮限定修复复审。真实 UI 已完成对话产物创建/审查/发布/新研究调用/HTML 下载，以及手动导入/编辑两版/停用/回滚/导出；Workflow 与全轮交付检查另行记录，不由这些结果推定。媒体容器检查不是恶意内容证明，静态 Python 检查不授予额外宿主访问或网络权限。发布暂存失败保留草稿与旧版；无法确认恢复时维持 pending 并拒绝继续，不悄悄抹去失败。

Tabbit 页面访问授权不持久化到 Research Web 会话文件；拒绝授权会撤销适配器内的本会话 grant。`read_only: true` 只是调用方声明，不能静态证明任意 Playwright 代码无副作用；缺失或为 `false` 的调用必须逐次经过原生审批，系统提示禁止把写操作伪装成只读。claim、DOM 提取或 `finishTask(..., {keep:true})` 任一失败都会阻止消息提交，且标题、URL、正文和执行代码不进入日志。

供应包校验使用 tar 原生 POSIX 路径语义，拒绝反斜杠、链接、绝对路径和 `..`；解包阶段才建立宿主路径。Tabbit 供应目录以 Git `-text` 保持跨平台原始字节，License 与归档摘要仍严格匹配 manifest。Tabbit 配置异常路径始终关闭仍由调用方持有的描述符，二次清理失败只记安全日志并保留原始异常。

Windows 不使用 POSIX mode bit 证明 DSH 认证文件或 DataHub 私有文件安全；路径回退要求规范化后仍位于产品根内，拒绝链接与重解析点，并验证普通文件、硬链接数、大小和打开前后身份。快照的创建、原子发布与失败清理通过同一受限路径层完成。POSIX 的目录描述符、`NOFOLLOW`、私有 mode 与目录 `fsync` 保持不变。

创建会话从产物导入时只读取当前安全文件清单。已改名旧 ledger 不作附件来源；仍实际存在但不安全的固定伴随路径、读取时消失或创建类型冲突均拒绝。显式 ZIP 不吸收会话中无关 JSON。真实修复后同名包按名称冲突拒绝，未覆盖现有已发布能力。

## 验证层次

1. 协议与渲染测试验证确定性契约，不要求消耗模型。
2. 原生沙箱与 DSH schema converter 测试要求本机环境以及 `DSH_SOURCE_ROOT`；缺失时明确 skipped，不能当作通过。
3. 独立浏览器回归验证实际页面与响应式布局，不写会话或调用模型；截图必须另行人工检查。
4. 真正研究旅程由本机 Web、专属 DSH 和真实模型完成，保留会话、版本、工具事件及文件；单元测试和旧验收不能替代新功能验收。
5. 图文一致性检查只核对路径、接口、字节哈希及更新记录。人工仍需审查语义、权限和实现是否相符。
6. 本机集成“已发现”不能替代真实调用验证；Office 只有创建/刷新、保存、关闭、重开与必需结果校验全部成功才可投影为可调用，Wind 则必须返回预期的最小厂商公式结果。二维码安全验证投影为待授权；超时、权限、登录或厂商异常均关闭失败。
7. 本机验证证据的 TTL 使用包含截止边界；零 TTL 必须立即关闭可调用投影。Workbook 阶段 timeout 显式钳制为 180 秒总预算减 10 秒协调余量。POSIX 进程组清理测试不在缺少对应系统调用的 Windows 上伪执行。
8. 集成协调器同时保留最近尝试与最近成功；配置、环境或 Provider 指纹变化会使旧证据过期。公共来源最多并发四个，厂商来源串行，未获逐来源授权的收费、登录或厂商探测保持跳过。

## 当前可复跑命令

```bash
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs
python -m pytest -q tests/research_web/test_mcp_registry.py
node tests/e2e/research_web_mcp_marketplace.mjs
node --check app/research_web/ui/app.mjs
git diff --check
```

UI 布局验收：`node tests/e2e/research_web_layout.mjs`，可用 `RESEARCH_PLAYWRIGHT_MODULE` 指定已经安装的本地 Playwright 模块入口；该脚本不安装依赖、不改变当前浏览器会话、不提交研究。证据输出至 `outputs/research-web-ui-acceptance/`，日志为 `logs/research-web-layout.jsonl`。它不把截图自动标为视觉优良。

## 未覆盖的部署保证

不声称 Windows/Linux 原生研究沙箱、桌面安装、公网访问、多个 FastAPI worker 或多人协作已经验证。停止后如有内核退出异常，仅报告并保留证据，不自动重启系统。真实文件解析检查也不能自动证明财务结论正确或资料覆盖充分。

功能默认开启不放宽安全授权：Registry 仍只读，安装仍需摘要绑定的二次确认，工具仍需风险分级与会话快照，高风险仍逐次审批，Automation 仍锁定版本与无人值守只读 allowlist。三个显式关闭值均有回归测试。

2026-09-11 的格式基线维护不改变秘密过滤、授权、验证证据、文件边界或关闭失败策略。

全局启动器先进入其解析后的部署根，防止调用目录中的同名包遮蔽受审代码；显式或 bundled Node 的绝对路径继续写入受管命令指纹，ABI 变化不会被静默接管。

Method 本身无脚本、依赖、Tool 声明或外部权限；用户不能创建或导入 Method。内部
`rwb_record_method_use` 仅接受固定方法 ID、语义版本和四种来源，拒绝额外字段，并在当前可信会话
目录以有界 no-follow 记录保存。测试覆盖越权字段、符号链接、解析冲突、上限、不可用版本、必需
缺证据阻断和推荐缺证据降级；真实研究质量仍须由独立 Research Evals 验证。

## 2026-09-23 重启与目录读取验证回执

非强制重启的活动门禁现在以已认证 `session/list` 为唯一 DSH 活动事实，任一运行会话都会失败关闭；
未认证、无效响应或查询失败均不得降级为“无活动”。目录刷新使用一次父 `session.list` 加全部合格
父作用域 `subagent.list`，50 个父会话的扇出并发不超过 8。只有已创建、存储为 `running`、原生父
会话与全部子会话均空闲的陈旧行才进入 `detail()` 恢复；恢复也受不超过 8 的上限、保留目录顺序，异常
或取消时取消并等待所有未完成任务后才传播。未创建、原生运行或子会话运行的行不恢复。该变化
不放宽会话归属、文件、能力、Tabbit、Automation 或外部访问权限；真实生命周期与浏览器验收仍待
本轮后续外部门禁，不由本地契约测试代替。

## 2026-09-28 Windows 进程所有权验证回执

Windows 停止仍先验证产品状态文件、PID 存活与命令签名，绝不按端口或任意 PID 清理。仅非强制
`taskkill /T` 失败可进入原有 `/F` 升级；强制失败继续 fail closed。该修复不扩大文件、凭据、网络、
会话或本机软件权限。

启动handoff不能以DSH_HOME父目录推断独立state位置。Node preload接受launcher明确的state绑定；消费方验证私有目录/文件、authority、cwd、固定commit及PID，秘密只进入脱敏集合和受控Cookie交换，独立健康检查保持只读。

## 公网部署预留决策（阶段6，仅设计）

原单用户模式的 owner 是本地实例及其 canonical data home；它不是 tenant 身份。新增邀请制服务器的已认证账号边界见本页开头，不等同于公网多租户平台。连接、秘密、缓存、快照、任务的归属须由后端受管目录和会话绑定确定，不能由浏览器提交的 owner 标识授权。DataHub 连接服务按实例路径后缀隔离；旧全局秘密不自动读取或复制。

未来公网任务必须先引入经服务端认证的 user/tenant 归属，并逐次校验连接、任务及缓存权限。公开可访问数据不等于可再分发；项目获准共享与用户商业私有数据须分别记录许可，私有及派生结果不得进入跨用户共享缓存或模型上下文。向所选模型服务外发商业数据须有独立数据外发授权。

远端服务 API Key 与用户电脑的 Wind/Office 登录会话是不同授权主体。公网后端不扫描或控制浏览器所在电脑；远程本机能力须另立身份验证、限定白名单、超时、撤销和设备所有权的桥接任务。

新增公网端点配置前必须确定 TLS、鉴权、DNS/重定向及 SSRF 规则，对环回、内网和跨用户目标失败关闭；审计只记录非秘密归属与操作结果。当前继续保持 loopback/same-origin/TrustedHost，不能通过绑定0.0.0.0宣称公网已支持。

独立未来任务依次为：身份与授权归属合同；数据共享/外发许可和缓存隔离；模型端点SSRF与TLS；受限远程设备桥接。当前不实施注册、计费、多租户平台或公网监听。

## 设置闭环阶段3：当前能力范围

数据准入必须覆盖DSH tools/pre-execute及agent/pre-step产生的真实skill-invocation来源；不能仅依赖前端或提示词。最终tools/result成功后登记，未确认登记不继续执行。当前声明数据任务禁止借web_fetch、一般网页或MCP绕过；实际查询参数与dataset-specific频率/复权/单位及历史时点合同匹配。Seatbelt取消整resources/受限datasets读取，仅放行通用资源及受信响应生成的精确目录，模型不得指定授权路径。


## 兼容模型的有界传输（1B实施中）

新增一项固定系统ref RESEARCH_COMPAT_API_KEY，与原RESEARCH_DSH_API_KEY共享实例归属规则、使用不同系统账户；resolve/describe/set/unset不进入环境或文件，两ref也拒绝委托Host record路径。Host browser-session记录原行为保留。明确无Key模式不查询任何模型凭据，不填假Key或降级为ambient来源。

新文本/流式适配复用固定DSH的LlmAdapter与同一Agent loop；请求禁止重定向、最多一次HTTP发送、90秒取消/超时、输入/输出有界，HTTP200与残缺流均不能产生成功finish。连接/凭据绑定相同公共revision，实际发送前检测变更；版本不读取或散列Key。工具、图像及其它能力未认证，不能因模型ID推导支持。保存/应用及合成生成已沿产品API接通，合成链路不冒充供应商验收。

平台能力投影不降低安全门：Windows 安全文档 reader 不支持时返回 501；非 Mac 研究脚本保留严格沙箱阻断，Windows Docker 保留 ACL 未验证。能力 available 不等于 validated，真实验收在支持矩阵与任务回执中记录。

生产资产筛选不得用模糊目录名删除程序；dist/doc 运行时代码保留，全深度 Git/cache 元数据排除以及 package graph、路径 containment、alias/no-follow 与 manifest 完整性仍失败关闭。Windows ACL、严格研究沙箱和 Docker 非 root 边界保持。

Docker Desktop 初始化在固定 bind 私有叶的原完整 guard 内，用 O_DIRECTORY/O_NOFOLLOW 固定描述符对父根执行不跟随链接的相对属性同步；前后 dev/inode/mode/uid/gid 和父别名/叶替换仍完整复核。同步不 chmod/chown、不读取秘密、不增加 owner 例外；自定义目录仍使用原严格边界。

Native Hot 模型加载只引用已有持久授权范围；配置本身不能建额或重置。初始化前通过现有受控凭据桥检查 configured，缺失时不注册付费 handler。跨日定价检查在运行、预留和派发前重复执行；旧价格回执/未知尝试的兼容查询和新预留与迟到回执持同一 schema 栅栏，避免读 miss 导致重复收费。正常研究 handoff 与用户授权/价格刷新 CLI 仍待完成。

模型管理不开放 worker/Agent RPC：迁移身份、实例控制 hash、停机/过期归属与同 schema 栅栏共同准入。普通 worker 不能授权或终止，也不能把 abandoned/unknown 退回 reserved/cancelled 来退款；收到 receipt 后的 received 转换和派发后的 day_key 受数据库状态门保护。

model-pricing-import 要求显式官方核对标记和停机；不读取凭据或授予额度。只接受固定官方模型/币种及已知保守费率下限，私有定价加载不允许symlink、多链接、外部实例或坏记录回退；运行指纹阻断旧费用派发。核对标记是操作者声明，不是厂商账单认证。

浏览器真实数据验收仅使用任务原schema与预算；模型关闭、来源临时暂停和恢复都有真实状态。临时控制角色退出后NOLOGIN；元数据与凭据来源在报告标注，未据此认证SystemKeychain完整生命周期。

Hot简报冻结核心使用只读repeatable-read事务与精确版本引用；有界规范JSON摘要只用于完整性检查，不充当身份认证。Markdown转义发布者HTML与块级标记，外链仅允许无userinfo的HTTP(S)，原始判断与继承后应用版本分别呈现。日志只记固定事件类别/数量，不写原文；当前不开放浏览器导出或研究创建路由。

持久简报写仅controller可用；request与version不可变，输入严格字段白名单，发布时间窗口和资料校验在冻结核心执行。发布保留owner/代次检查，读取复验hash；350000字节输入限制为现有1MiB签名帧留余量。公开Host导出与研究受理边界尚未实现。

Hot简报Host输入在读key前验证身份、严格版本和选材边界，Node仍是窗口/归组/预算权威。预览转义发布者文本并限定HTTP(S)无userinfo外链；下载只返回经固定版本分块与最终SHA256验证的Markdown附件，无缓存。块offset/大小/总长/哈希/identity一致才接收；Unicode字节边界和后续version0拒绝有回归。

浏览器fixture在迁移/创建role前拒绝已有基线，恢复先绑定实例/role再产生效果。NOLOGIN独立于来源恢复与预算核对，即使注入审计失败也运行；收尾后的receipt保留FAIL与实际权限清理状态。实际浏览器使用临时Hot凭据backend和offline研究，不能证明完整系统凭据生命周期。

## Office 自动验证同意

设置 → 本机集成的 Office 开关默认关闭，仅明确同意后允许所属实例的 Word/Excel/PowerPoint。授权仍要求精确同源及用户动作头，只扩展三个精确 local:* 目标，其他本机目标拒绝；厂商调用仍单独确认。同意绑定私有状态根，不跨实例继承。会创建、保存、重开并清理本轮登记测试文稿，保留验证账本与阶段诊断（沙箱文件经归档后精确删除，合成副本由私有run目录按原容量/期限保留）；不会扫描用户文档或关闭用户文稿。系统权限提示必须人工处理，不reset TCC、不修改沙箱/目录权限。超时、拒绝、人工处理或清理未知停止该目标自动尝试，关闭开关取消所属任务，冷启动不重放历史任务。Doctor只读取安全开关投影，不执行验证。

本机scope和Office同意的持久状态恢复不触及DataHub连接配置/凭据元数据；没有明确confirmed清理诊断的Office历史成功也不提升可调用，保持人工处理与停止标记。

2026-10-09追加授权收口：Office成功且关闭确认后，仅归档登记的合成文稿到既有私有验证run目录，再清理沙箱副本；成功marker移除，仍沿原16项/512MiB/24小时有界保留策略回收，不新增执行器或任意路径接口。Office开启改用页内说明、确认/取消按钮，系统权限弹窗仍由人工处理。


## 研究情报统一入口 · 2026-10-12

主导航统一为“研究情报”，本地热点与事件在 `#/intel/hot`，现有外部8栏目仍在 `#/intel/*`。旧 `#/workbench/hot` 链接保留视图/事件参数后转入本地页。两类页面共用栏目导航、主题与Host；本地版本证据和Golddata外部只读数据保持身份与覆盖来源区分，外部读取不写Hot、领取任务或调用模型。Hot未启用时，外部栏目与设置继续可用。

恢复的DOCX切片通过 `GET /api/research/hot/briefs/{brief_id}/docx?version=<固定版本>` 从签名/哈希核对的冻结输入生成并保留私有产物，复用报告DOCX生成器；导出不创建会话、不调用模型、不外发。该路径尚需完整产品/恢复验收，局部测试不代表研究闭环完成。


## Hot冻结原件的读取边界 · 2026-10-12

`research.evidence` / `research.original`仅在当前签名reader权限、实例/模式/代次和活跃owner fence内读取。请求只能指定已保存简报的正版本及1–20个明确材料ID，不能选择schema、地址、SQL或任意文件。原件必须属于该固定选择；哈希变化、失效代次和未选择原件拒绝。Host不解析原文为代码或指令，不领取任务或调用模型。清单700000字节、单原件8MiB、总量32MiB；每页最多32KiB，校验完整后才交给未来会话发布流程。

本轮真实PG/签名RPC、Host重建及DOCX HTTP是隔离凭据fixture；原两份真实简报的DOCX内核输出已验证。两者不认证实际安装的SystemKeychain、研究受理或生产部署。累计授权账本继续沿用原scope，不因接续worktree或恢复而重置。


Hot研究映射prepare/advance为controller-only，所有变更仍受实例/模式/代次与CAS；原件和状态为reader-only。预留session身份先持久化，未知结果不能自动创建另一个会话或重发付费执行。原生ID存在但cwd/本次归属不一致时拒绝采用。DataHub只允许已原生确认的匹配目标会话导入固定bundle，校验原件键/文件名/字节数/SHA与清单、截止时点；不会把材料解释成代码或用户授权。跨会话复制保留独立字节，未知暂存内容与已存在不同快照拒绝覆盖。


2026-10-13续跑：migration18允许不可变amend-tokens审计；仅停机迁移Owner及匹配实例凭据可增加已有scope两token列，次数/费用/已用值/authorization hash不变。冻结快照仅在既有capability准入通过且本会话归属/全hash核对后只读。


报告GET不创建运行、请求模型或改变预算。显式refresh须原user-action/header，匹配run/session/instance/manifest并只观察原Native回合。PG不可用仅展示未核验状态和已保存文件；旧成功回执不能认证当前变更字节。

## FinGPT 研究融合 · 2026-10-13

FinGPT 资料范围在工具 preflight、上传入口及脚本数据集 read_paths 处执行；datahub_search_web 按 web 分类。底稿绑定当前 task_id，未知来源/缺笔记链路/重复格式/哈希改变或未通过独立沙箱解析均保留缺口。报告仅检查声明章节与来源身份，不证明全文阅读或数值正确；数字结论显示需独立复核。旧任务与无效报告不会展示为当前笔记。

## 历史子会话模式兼容 · 2026-10-13

activityOnly仍逐项验证父子关联、origin=subagent及running为布尔值，不能将missing/unknown活动推断为空闲。历史mode=unknown不授权打开子历史；继续、取消和删除路径仍使用严格执行模式查询。

POSIX运行记录读取的共享祖先在stat/open与退出复查均采用dev/inode/mode及UID/GID，
允许无关sibling目录变化；直接私有parent与记录文件保留完整元数据、单链接及权限校验。
目录替换/alias/owner或mode变化仍拒绝；私有UID异常继续unsafe_path，不改变格式或端点。

PR96 与既有 Fernet 模型桥共用唯一私有 stdio 接口；默认 `native-keychain`、常规 staged `docker-encrypted-file` 语义保留，管理器仅显式绑定 `docker-encrypted` 选择 AES-GCM。两种 Docker 格式与主密钥布局独立，混合绑定或外来格式失败关闭，不转换密文、不删除旧 Key、不回退。四操作与固定 ref 保持；来源如实区分，configured/Doctor 不证明真实生成。

AES 专用模型后端在构造器的既有文件锁内核验全部现有 JSON：外层私有记录格式、完整密文封装、版本与实例身份、实例 service 与两个固定模型 ref 派生的文件名，以及相同 AAD 的 AEAD 认证。A 密文树与 B 完整主密钥/身份绑定不能被新命名空间遮蔽成未配置；未知 JSON、篡改或旁写记录失败关闭且不改原密文。正确旧 AES/Fernet 树保持可读；通用 PrivateFileCredentialBackend 仍允许其原服务/账户用途，不做迁移。

## 框架嵌入核心闭环 · 2026-10-14

嵌入资源使用 /frameworks-embed/ 路由级同源 CSP，不放宽宿主 CSP。宿主与子窗口桥接校验 origin、source、slug、revision 与本次 token，重新挂载必须重新确认；过时回执不能解锁 Bot。原生快照不回退静态 JSON；来源缺口、数据准入和固定 DSH 权限门保留。真实模型、供应商和跨平台证据独立记录。
