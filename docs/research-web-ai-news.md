# AI 资讯自主引擎与本机桥接

研究提交的幂等请求头透传仅作用于逐用户研究代理，不改变共享资讯路由、认证、数据库或采编预算。

研究pair容量显式上限扩展不改变共享资讯执行/数据库/worker；常驻本机选择3额外pair加原primary，不自动开启资讯采集或模型。共享资讯阅读本身不占研究pair槽位。

用户pair重启会复用其既有可信回调端口，不影响服务器共享资讯服务或worker生命周期；未知端口占用不触发其他用户/资讯实例停止。

常驻附接保持 primary 所有者原版 UI、静态资源与原 AIHOT 阅读 API 成对路由到旧实例；不会因登录网关部署切换其资讯内容或启动自主库/worker。新用户沿既有服务器共享只读资讯合同，未配置时明确显示未接入，采编管理仍仅管理员。资讯部署与真实模型预算验收继续独立。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](research-web-ai-news.md)。

AI 资讯使用 `services/ai_news/vendor/aihot` 固定的原始 AIHOT Node API、worker 与 PostgreSQL
实现。Host 负责同源阅读、管理投影及明确的本机生命周期，不把 AI 资讯执行接入 DSH 研究循环。
产品没有 `aihot.news` 读取后备，也不会把旧网站的内容或示例报告作为本机采集结果。

## 默认状态与授权

未安装或未配置时，管理状态为 `not_configured`，阅读返回真实 HTTP 503；不启动进程、
连接数据库、读取 Keychain 或请求外部网站。默认模型、付费 X、微信公众号、Jina 及本地推理
均关闭。配置模型名称、预算或来源并不授予实际推理授权。真实模型验收与生产部署分别记录，
没有执行时保持 `NOT_RUN` / `productionDeployed: false`。

首次 `setup` 创建新的独立 PostgreSQL，必须显式授权；不连接 Hot 业务数据库、复用其卷或
修改它的运行状态。安装原引擎依赖也属于独立授权。CLI `--authorized` 仅表达操作者已获得的
授权，不把前端管理操作转换为数据库创建、恢复或部署许可。

## Host 接口

### 私网多用户权限与共享目录

多用户服务器在认证 gateway 内挂同一组 AI 阅读和管理路由，使用唯一共享 service。
服务 home 为 `server_root/shared`，实际资讯目录为 `server_root/shared/ai-news`，独立于
`server_root/users/<uuid>/research-web` 的 DSH、会话、文件与个人模型凭据。构造 bridge
不创建共享目录、不连接数据库、不读 Keychain，也不自动安装或启动 AI/DSH 进程；首次
共享库 setup 仍须操作员明确授权。没有配置时管理员看到 not_configured，成员阅读得到 503。

| 路径 | 权限 |
| --- | --- |
| 原 `/api/research/aihot/*` 阅读、正文、专题与图片 | 已登录成员 |
| `/api/research/ai-news/feeds/{kind}.xml` 六种 RSS | 已登录成员 |
| `GET /api/research/ai-news/status` | admin |
| `POST /api/research/ai-news/control` | admin |

未知 AI 子路由、未知 feed 和不适用 HTTP 方法直接拒绝，绝不转发到逐用户 Web/DSH 后端，
因此资讯阅读不占用研究实例槽。tenant profile 同时封禁所有 `/aihot` 和 `/ai-news` 路径，
即使调用者持有某个用户后端的实例 key，也不能借用户 Host 访问全局资讯。原单用户权限不变。

沿用既有 gateway 的精确 Host/Origin、Strict/HttpOnly Cookie 及页面账号绑定，不增加第二套
浏览器 CSRF 协议。控制请求必须匹配 `X-RWB-Page-User` 或 `rwb_user`；GET 如携带这些字段
也必须匹配当前账号。control 在 JSON 解析前流式限制 64 KiB，慢 body 结束后重新确认有效
账号和 admin；共享读取返回前再次检查撤销。账号切换、密码重置或停用不能让旧页面继续读取
或提交管理。浏览器 Cookie、Authorization、伪造的私有 Node/tenant key 不传入原 AIHOT 引擎；
原 Node admin session 与 CSRF 仍只由 Host 私有桥处理。

`create_ai_news_service(project, home, credentials=None)` 仅构造对象，不做 I/O。
`service.reader` 注入现有 `app.state.aihot`；原 `/api/research/aihot/*` 阅读、专题、分组、
日报/周报/月报、原文和图片路由保持原合同。传输改为私有回环 API，地址仅从本机私有配置取得，
浏览器不能传入目标地址。所有私有请求携带 `x-rwb-ai-news-token`；浏览器 Cookie、Authorization
与环境代理均不转发。重定向拒绝，JSON 解压后 2 MiB / 20 秒，LRU 64 项；端口或 token 变化
清空原缓存与图片映射。

正文仍经 `aihot_content.reading_tree` 转成白名单惰性节点，禁止脚本、事件、iframe、SVG、表单和
任意图片。图片仅接受本机引擎已签发的 `/api/img-proxy`，先登记 opaque key，再由 Host 读取；
4 并发 / 12 秒 / 4 MiB，只允许栅格 MIME，最多 4096 项映射，不跟随重定向。

管理使用 `GET /api/research/ai-news/status` 与 `POST /api/research/ai-news/control`，后者为
`{ "action": "source.list", "input": {} }`。沿用 Host 已有可信 origin 与认证边界，内部使用原始
AIHOT admin session/CSRF。动作仅允许：`source.create/update/detail/list/preview`、
`content.list/detail/visibility/override`、`runs`、`settings`、`models`、`audit`、`budget.update`、
`model.update`、`settings.contact-qr`。来源试抓只允许原引擎支持的免费 RSS、网页列表、JSON 列表，
付费或未配置能力明确拒绝。来源 URL 仍经过原引擎 SSRF 与逐跳重定向检查。
`model.enable`、任意设置透传、`source.fetch` 和生命周期操作不在浏览器白名单中。
`receipt.release` 必须提交准确 receipt ID、是否已计费和人工核对备注；`processing.requeue`
必须提交原分组及恢复理由。结果未知的付费请求仍待人工核对，不能用自动重试再发送。

RSS 同源出口为 `/api/research/ai-news/feeds/{kind}.xml`，kind 仅允许 selected、selected-full、
all、daily、weekly、monthly，分别读取原 `/feed.xml`、`/feed/full.xml`、`/feed/all.xml` 和
三种报告 feed。2 MiB / 20 秒限制及 token、禁代理、禁重定向继续生效；拒绝 DTD/ENTITY/XSL，
附件响应带独立禁止脚本 CSP。原私有 API 地址改写为公开 Host 及其模块阅读链接，不向读者泄露
私有服务端口。

Host 对管理响应递归脱敏 password/secret/token/API key/authorization/cookie 字段及本机路径。
嵌套 error/last_output 等字符串中的 file URI、macOS/Linux 绝对路径和 Windows drive 路径
也会替换；完整公开 HTTP(S) publisher URL 保留，不能只按字段名称判断路径泄漏。
控制输入上限 64 KiB，未知字段和未知动作拒绝；错误只返回稳定代码，不包含子进程输出、配置、
秘密或正文。日志通过项目设施进入 `logs/`。

## 本机生命周期

`AiNewsManager(project, home, credentials)` 提供 `setup/start/stop/status/doctor/backup/restore`。
凭据后端复用项目 get_password/set_password 合同，允许延迟 factory，仅在显式 setup 访问。
随机 token、数据库、admin、session 与 image 密钥保存为本机私有 600 文件；数据库密码仅通过
只读文件挂入独立容器，不写入 argv、镜像或 Git。`home/ai-news/` 独立于 `home/hot/`。

本机 CLI 入口 `run_ai_news(argv, project, home, credentials=None)` 支持动作与 `--json`、
`--data-home`、`--file`；setup/restore 另需 `--authorized`。不要对真实业务目录试运行。
测试可显式构造 `database_name="rwb_ai_news_test"`，不会改变正式数据库名。

生命周期使用现有 `LifecycleLock` 排他租约；PostgreSQL 创建/启动使用现有 Docker operation lock，
只读获取 Docker VM 总内存和全部运行容器的显式 Memory。未知/无限额容器或预算不足时拒绝。
新容器限制 768 MiB、1 CPU、128 PID，至少为其他宿主活动保留 1 GiB；不扩大 Docker VM。
资源保存 instance、project、purpose、lifetime 与可选 `RWB_DELIVERY_TASK_ID` 标签。

容器镜像使用项目已固定的 PostgreSQL digest，不自动拉取镜像；必须校验容器 ID、instance 标签、
数据卷、只读 secret 挂载及仅 `127.0.0.1` 端口。已存在但身份不符的同名对象拒绝接管。
API/worker PID 同时绑定进程启动时间和完整命令指纹，PID 重用拒绝停止。启动须通过私有健康
检查并确认 worker 存活；同步完成 stage 后再启动两进程。每次 Popen 立即登记本次句柄；指纹、
持久化或健康检查失败时，通过仍持有的本次子进程句柄 terminate/wait 清理，恢复停止则重新
核验持久化指纹。动态进程调度状态不属于身份，僵尸视为停止。进程失效显示 degraded，
当前显式生命周期没有后台自动重启 watchdog，也未安装登录常驻控制器。

POSIX migrate/seed/stage 有限命令使用独立 session/process group；120 秒超时后，在仍持有未回收
Popen 子进程的情况下核验本次 PGID/SID 和组内所有存活成员的 session，先 TERM，有界等待后
必要时 KILL，再回收 launcher。迁移孙进程不会越过生命周期 lease 留到下一次重试。身份核验或
清理失败则持久化 command-recovery.json，状态 BLOCKED，后续生命周期拒绝自动重试，等待
人工核对；不向未知 process group 发送信号。Windows 本机进程树合同仍未验证。

首次 setup 在写 identity 前持久化阶段 journal；身份、secret、database、migrate、seed、complete
分别保留进度。凭据、资源准入或迁移失败后，仅相同 project/home/instance/database 的未完成
事务可以显式重入；既有 secret 必须与凭据后端一致，未知身份或已完成事务拒绝覆盖。重入使用
原迁移和 seed 的幂等性，私有 JSON 替换为 fsync 后的原子发布。状态如实显示 setup_incomplete。

status/doctor 不创建目录、锁、配置或容器，不连接 DB。doctor 纯文件核验固定 commit、MIT/origin、
完整 652 个上游文件集合及逐文件 SHA-256；检查 npm lock v3、安装锁与 fastify/postgres/pg-boss/zod
包版本一致，分别返回 pinIntegrity、dependenciesInstalled、upstreamFiles、upstreamCommit。
全新未配置状态不访问凭据后端或 secret 文件，也不执行子进程。静态检查不能替代迁移、worker、
网络或模型验收；modelAcceptance 保持 NOT_RUN。stop 不删除数据卷。

备份使用独立容器内 `pg_dump -Fc`，私有 archive + SHA-256 manifest，不包含秘密文件。
恢复只面向已验证的本任务数据库，要求明确授权且 API/worker 停止，先核验 manifest 和 hash，
再在同一 owned 容器内新建唯一恢复库，以 `pg_restore --single-transaction --exit-on-error`
完整恢复。恢复成功后在独立 postgres 连接内，以单事务 rename 切换两个已停止的数据库，
原数据库保留为 previous 库。原 pg-boss 分区约束不使用不兼容的 pg_restore --clean 删除路径。
拒绝活动连接，不终止后端；恢复失败不切换原数据库。持久化 restore journal 记录恢复与切换阶段，
切换结果未知时保留人工核对状态。失败归档与恢复临时库保留并报错，不伪称成功；保留原卷、
其他服务与不明对象。恢复不自动删除原库或归档。

## 测试资源退休

未来 `rwb_ai_news_test` 专属容器和卷必须带 `RWB_DELIVERY_TASK_ID` 归属，lifetime 为 temporary；
正式数据库仍为 persistent。已有对象的标签不改写，不能把名称、停止状态或新标签作为退休证明。
本次早期创建的独立测试 PG 标签为 persistent，须按已保存的 instance/container ID/volume/只读
secret 挂载/loopback port/任务标签逐项复核后，才能显式按任务测试资源退休。

收尾顺序为：停止本任务预览及 Node API/worker，确认无进行中任务；在同一 lifecycle/operation
锁内核对精确身份；保存最终测试库备份及 manifest，并在另一个本任务隔离恢复库完成还原和
必要行数/迁移/原件核验；归档报告、日志与恢复证明；随后仅停止并删除本任务已核验的精确
container ID 和已解除引用的精确 volume。测试目录内 staged 引擎及随机 secret export 在归档
证明并确认无占用后退休，不将 secret 复制到公开报告。任何归属、引用、恢复或占用不明保持
blocked。早期通过的备份恢复只证明那个时间点，不能替代结束时的新快照。正式 Hot 数据、
其他运行容器、用户凭据、业务卷和未知对象始终保护。

## 验证边界

`test_ai_news_host.py` 覆盖无配置零副作用、固定回环地址、私有 token、链接与权限拒绝、授权门、
环境秘密剥离、PID 重用、管理白名单与递归脱敏。`test_aihot.py` 覆盖同源阅读和 inert HTML、
身份、缓存、限流、图片与大小边界。Mock 网络测试不证明真实站点、原引擎、数据库或模型可用。
实际原引擎/PG/安装验收与未运行的平台分别保存在本任务 `.ai/reports`，不宣称 Windows/Linux
原生支持或生产部署已完成。

主题大事记通过原ServerModule扩展读取自主库当前精选证据，最多80条并逐条复核撤回、修订与主题归属；事件发生、发布和本机收录日期分别显示，不知道就留空。没有历史导入、模型补史或虚构时间。

公开 `rwb ai-news setup` 在接触Keychain前切换到已验证归属的项目Python环境，依赖来自公开安装锁而非宿主全局包；缺失/不可用环境失败关闭。status/doctor仍为只读stdlib快路径，不要求凭据或可用venv。
