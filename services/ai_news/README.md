# AI 资讯原引擎适配

Research Web 内嵌的本地 AI 资讯引擎。`vendor/aihot` 保留 MIT 上游
`KKKKhazix/AIHOT@26d436497d9ddba9e7dd88eed255cfe0105ce368` 的 652 个原文件，
来源、归档校验和每文件 SHA-256 见 `upstream.json`；MIT 原文保留在
`vendor/aihot/LICENSE`。本产品使用“AI 资讯”，不使用上游站名或 Logo。

不是远端网站代理，也不启动上游 Web/SSR 进程。API 调用原 Fastify 路由与
`publication/`；worker 运行原 pg-boss 队列、采集、预筛、独立双评分、写作、
事件归组、热度、日报/周报/月报、回执和预算逻辑。所有提示词、评分权重、
门槛和历史 SQL 均保持上游原文。资料、发布和运维状态来自原 PostgreSQL 表。

## 私有启动合同

当前验收宿主为 macOS；Windows/Linux原生未验。要求 Node >=24.11、锁定 npm 依赖和独立 PostgreSQL。安装依赖、迁移、服务启动、
正式数据和付费操作分别遵守主项目授权；不要运行上游 `scripts/init-env.ts`。
用户批准后在本目录 `vendor/aihot` 执行 `npm ci --ignore-scripts`，不得修改锁文件。

```
node services/ai_news/runtime.mjs doctor --config /absolute/bootstrap.json
node services/ai_news/runtime.mjs stage --config /absolute/bootstrap.json
node services/ai_news/runtime.mjs migrate --config /absolute/bootstrap.json
node services/ai_news/runtime.mjs seed --config /absolute/bootstrap.json
node services/ai_news/runtime.mjs api --config /absolute/bootstrap.json
node services/ai_news/runtime.mjs worker --config /absolute/bootstrap.json
```

bootstrap 字段为 `port`、`dataDir`、`tokenFile`、`adminPasswordFile`、
`sessionSecretFile`、`imageSecretFile` 和 `database: {host,port,name,user,passwordFile}`。
端口必须1024–65535，数据库 host 仅回环。所有秘密文件必须绝对真实路径、当前 uid、
普通文件且权限0600；拒绝符号链接，先打开 O_NOFOLLOW 后核对文件描述符。
桥 token 最少24字符、admin最少12字符、session/image最少32字符。
秘密只进入子进程私有环境，不进入命令行、bootstrap 明文或启动错误。
继承环境采用有限字段白名单；不继承模型/采集凭据、代理、dotenv 或开发认证绕过。
API 只监听127.0.0.1。日志保存到 `dataDir/logs/{api,worker,migrate,seed}.jsonl`。

默认采集、模型、飞书和 IndexNow 安全阀关闭；采集与模型可以通过下述显式授权独立激活。种子导入保留原18个公开来源，
初始全部暂停，不覆盖已有管理员修改。六种来源能力和账号候选状态见
`source-presets.json`；X/公众号没有伪造账号、Cookie 或 key，显示 configured-pending。
此阶段不声称生产自动采集/模型已激活；开通付费另行验收，本次没有激活。

可选 `activationFile` 指向当前用户0600普通文件，JSON合同如下（示例不是有效授权）：

```json
{"version":1,"collectionEnabled":false,"modelCallsEnabled":false,"services":{}}
```

免费采集单独将 collectionEnabled 设为 true，仍需手工启用选定来源。模型启用时必须提供
services.llm：`approvedBy`、`approvedAt`、未来 `expiresAt`、`budget:{perMinute,perHour,perDay}`
（均正整数请求次数）、`credentialFiles:{LLM_API_KEY:"/absolute/private-key-file"}`、
`publicConfig:{LLM_BASE_URL:"https://provider/v1",LLM_MODEL:"chosen-model"}`。
其他原服务 grant 可为zhipu/deepseek/dashscope/mimo/embedding/socialdata/dajiala/jina，
仅接收该服务的固定环境变量，不允许注入任意环境、dev bypass或命令。
所有秘密仍以独立0600文件载入，不能放在公开配置或浏览器表单。
模型provider可使用HTTPS或明确的回环HTTP（127.0.0.1/[::1]），支持本地OpenAI兼容端点；
采集付费provider仍要求HTTPS。回环provider也必须具有同样的授权、凭据和持久正数预算。

原 paidRequest 的事务内预算检查在每次实际付费尝试前重读私有授权，检查期限、
服务开关及数据库 budgets 正数配额不超过授权。删除DB预算不会变成无限制；
将预算调高到授权之外也不会放行。没有grant或缺key均失败关闭，复用既有回执
不新增付费。当前没有写入任何激活记录、真实key或调用模型。
采集开关/凭据变更后重启本服务；付费授权过期或撤销在每次新尝试即时生效。

## API 与管理

所有请求（包括健康、图片、feeds、未知路径、管理）在原 handler 前验证
`x-rwb-ai-news-token`，常量时间比较并从原请求日志中脱敏。
保留原 `/api/site/*`、`/api/img-proxy`、`/feeds*` 和原管理领域逻辑。
不信任转发代理头。浏览器不接收私有 token 或管理 session。

`GET /internal/rwb/status` 返回原来源列表、队列/进程/错误/回执运维事实、
固定 engine SHA、实际安全阀及 configuredPending。status直接复用原listSources/runsOverview只读查询，不创建管理员session或auth.login审计，也不调用模型。
`POST /internal/rwb/control` 接收 `{action,input}`，有限动作如下：

- `source.list/detail/create/update/preview`
- `content.list/detail/visibility/override`
- `runs/settings/models/audit`（这四项只读）
- `budget.update`：`{service,perMinute,perHour,perDay,reason}`
- `model.update`：`{capability,model:string|null,reason}`，仅原已注册模型选择
- `settings.contact-qr`：`{slot:"wechatQr"|"feishuQr",image}`
- `receipt.release`：`{id:正整数,billed:boolean,note:非空字符串}`，必须人工核对账单并记录结论
- `processing.requeue`：`{group:string|null,reason:非空字符串}`，复用原失败任务恢复和审计

管理动作通过原 passwordLogin 建立原持久认证 session，再以原 CSRF token
调用原 admin handler；编辑的版本冲突、审计和发布刷新保持原实现。
成功响应统一HTTP200、原JSON结构；错误保留原状态码。
`source.preview` 仅允许明确提供配置的RSS、HTML和JSON免费试抓；拒绝X、公众号、
external与Jina地址，不调用付费请求或模型，保留原SSRF、日期、字段与大小规则。
未知动作、模型启用和付费试抓失败关闭。

## 原文与补丁闭包

每次启动校验上游完整文件集合及哈希，缺失、额外文件和非普通文件均失败关闭。
`dataDir/engine` 是经过验证的运行副本，`.rwb-patches.json` 记录适配器哈希、
上游提交及每个补丁前后SHA。重启复核每个运行文件；适配器变更或stage篡改要求
人工确认后重新准备，绝不静默覆盖已有未知目录。npm依赖复用锁定安装目录，
所有 `@aihot/*` 工作区链接指向运行副本，避免补丁被原vendor路径绕过。

仅运行副本上的七个原文件有最小补丁：

| 文件 | 原因 |
| --- | --- |
| `operations/recover.ts` | 未知付费结果永不因30分钟超时自动释放；原人工核账、审计、恢复逻辑保留 |
| `providers/receipts.ts` | 每次实际付费尝试在原事务内核对当前授权及持久正数预算，缺预算不再无限制 |
| `operations/alerts.ts` | 提示人工核账，移除错误的自动放行说明 |
| `lib/url.ts` | 逐跳SSRF入口额外拒绝aihot.news及其子域 |
| `apps/api/src/app.ts` | 原handler前的私有token守卫、敏感头脱敏、不信任代理 |
| `site/site.ts` | 使用本产品名称 |
| `industry/sources.json` | 初始全部暂停 |

`network-guard.mjs` 在API/worker/迁移/种子进程载入原模块前安装 native fetch守卫，
拒绝aihot.news与子域，并禁止携凭据的native fetch隐式重定向。
原采集器的undici transport仍使用上游逐跳SSRF与重定向保护和新增域名拒绝。

## 验证与实际限制

```
node --test services/ai_news/tests/*.test.mjs
```

`runtime.test.mjs` 验证秘密权限、污染环境拒绝、回环数据库、完整pin、篡改拒绝、
未知付费回执跨时段不释放、有限动作与付费预览拒绝、默认关闭与授权/凭据/期限/持久预算激活硬门。
`engine.test.mjs` 直接加载经过补丁的原引擎，以禁止真实联网的MockAgent验证RSS、
HTML、JSON解析，原API在DB查询之前拒绝未认证请求和外域禁止；依赖未装时明确SKIP。
不以这些测试替代真实PostgreSQL迁移、持久队列、后台认证或模型质量验收。

本次原上游全standalone测试实际执行失败：包含需要未构建SSR产物
`apps/web/build/server/index.js` 的网页元数据测试。该产品不运行SSR；失败保留为
未满足的原站全套测试，不声称全套通过。backend focused子集另有独立日志。


### 本次真实零外部调用验收

适配测试9/9通过，包括外域TCP/DNS围栏自测。原后端standalone定向71/71通过。
新增可复跑真实PG入口（须先批准临时数据库，不能指向业务数据库）：

```
node services/ai_news/tests/run-pinned-invariants.mjs --config /absolute/test-bootstrap.json
node services/ai_news/tests/run-pinned-invariants.mjs --config /absolute/test-bootstrap.json --reports-only
```

runner校验原652文件pin，为本次运行创建全新随机名字的`*_test`模板与各文件独立克隆，
结束只删除本次生成的库。所有Node子进程继承`deny-external.mjs`，真实TCP只允许回环，
外部DNS拒绝；模型、SocialData和Dajiala只连接本地fake provider，使用合成test-key。
没有调用真实模型或付费服务，不读取宿主供应商凭据。

| 证明 | 实际结果与范围 |
| --- | --- |
| RSS / HTML / JSON | `engine.test.mjs`直接加载staged原collector，MockAgent禁止联网并验证真实解析 |
| X | 原`x-article.test.ts`：fake SocialData采集、长文章提取、重复不增加revision或重复请求 |
| 公众号 | 原`dajiala.test.ts`：fake Dajiala正文临时失败恢复、已存正文不重复购买、密钥不跨源重定向 |
| external | 原`ingest.test.ts`：暂停来源拒绝push且不伪记成功，启用后通过原入库链 |
| 持久流程 | 原9文件82/82：并发去重、版本、阶段恢复、预算并发拒绝、回执复用、事件人工纠正与发布幂等 |
| 成刊 | 原`reports.test.ts`、`report-recovery.test.ts`7/7：日报/周报/月报重复调度不重写、不重复请求；显式纠正保留旧revision；成刊与回执原子提交，失败恢复复用响应；空缺期不饿死后续刊期 |

82项集合显式排除原上游“未知付费结果30分钟自动放行一次”的相反政策测试，不能宣称
它通过；RWB补丁另以未知回执不重发、无授权零dispatch的真实PG证明验收。
7项成刊集合没有排除项。原全standalone的SSR失败仍保留。
本地日志和机器摘要分别在`logs/pinned-pg-invariants.{log,json}`、
`logs/pinned-pg-editions.{log,json}`，包含原pin、文件集合、网络政策、退出码与日志SHA-256。

## 自主题大事记

`chronicle.mjs` 经原 ServerModule topic-page 扩展读取自主库中最多80条当前仍公开的精选报道，原 loader 重新核对撤回、主题归属和更正版本。每点引用文章ID、revision、factID，区分 publishedAt / occurredAt / collectedAt；未知事件时间保持空，复合报道不冒充单一事件。无历史导入、无模型生成大事记。

授权或凭据/供应商地址变更后，正在运行的付费调用会被拒绝并要求显式重启，防止旧进程使用旧账户执行新的授权。来源编辑拒绝URL查询和JSON中常见明文凭据字段；鉴权JSON来源仍待本机凭据引用适配，不能将key写入信源配置。
