# RWB 本地知识库：目录同步、当前研究引用与本人账号

宿主为 macOS 24GB Mac mini。本任务为功能开发，本机验收覆盖 macOS Native 和 Docker Desktop；其他平台产品验收保持独立。

## 已批准范围

固定目录 `/Volumes/WorkDisk/Data/RWB/knowledge-inbox` 自动新增、更新和撤回当前资料；WeKnora 仅做解析与检索，原生 Ollama 本地向量化，RWB 沿用已有研究模型。用户自行注册真实邮箱，RWB 设置只登录并绑定本人身份，不代为注册。Obsidian、SuperAgent 接入和本地生成模型均未纳入。

## 实现与验证

- 私有 SQLite 保存不可变原字节、版本和 pending/current/tombstone；两次稳定扫描后入库，索引成功才提升，失败保留旧 current。暂时网络失败恢复轮询，待处理优先并持久轮转。身份、挂载缺失、扫描失败不会推定批量删除；容量在写前准入，错误和跳过可见。
- 新增可信会话 query/read 与明确用户确认后的引用冻结；保留正式报告 scope 分支。检索按已绑定 current 文档分批召回并合并 Top8；读取绑定真实命中版本，来源时间未知不能通过历史报告质量门。
- 复用 Host 生命周期和原 scheduler，原有 discovery 恢复先于知识任务注册；仅服务模式不因知识同步恢复其他日程。固定安装清单与网关配置可持久绑定 origin，字段缺失保持旧启动行为。
- 本人邮箱登录仅向固定 WeKnora origin 发请求，禁止重定向，核对 active workspace 与 `/auth/me` 后仅把 JWT 存入系统钥匙串。密码不持久化、不回显；登录失败保留原绑定，换身份不承接旧资料。
- 真实实例恢复使用原 `rwb-weknora-standard-r2` 镜像、卷和网络。数据库冷备份已在隔离 Postgres 恢复并读回；原付费 sidecar 与缺失历史账本保持原状。本机 Ollama 0.40.16 官方归档校验通过，BGE-M3 实际返回 1024 维，模型与文件清单哈希分别记录。
- WeKnora 通过 Tailscale Serve 的独立 HTTPS 9443 提供私网访问；现有 RWB 443 和 SuperAgent 8443 路由保持。当前主机链路实测页面 200、匿名知识库 API 401、公开 Embedding 路径 404；未宣称另一设备实测或公网发布。
- 现役 DocReader 缺 TXT parser 已在真实入库复现；兼容入口仅增加严格 UTF-8 文本提取，保留原 ARM/OpenSSL 启动检查与其他解析器，不更改原字节。离线 10 项测试通过，服务修复与重解析另留运行回执。

WIP 阶段分别实跑：同步及 client 41 项通过；当前研究、API 与原件保全 34 项通过；登录及 API 29 项通过；质量相关闭包 52 项通过。数字为不同批次，存在重复，不相加作为唯一用例数。新行为先观察实际 RED 后实现；独立 Python/JavaScript 评审发现的重试、容量、调度顺序与中文 UTF-8 回包问题已修复并补回归。最终 exact-SHA 测试、CI、受管上线、20题及登录后研究验收以最终回执和 PR 状态为准，本报告不自证通过。

## 架构复核

<!-- architecture-review {"group":"knowledge-backend","structure":"changed","reason":"新增固定目录同步与账号SQLite版本状态、会话命中回执和本机Embedding边，图04同步目录到Host及回执冻结关系。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"ui","structure":"changed","reason":"原数据设置卡片新增本人登录、自有库绑定、同步启停和扫描状态，图04同步明确动作入口与目录资料边。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增登录与同步HTTP端点并在既有检索读取冻结端点接会话回执协议，图04区分账号同步与Host准入。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"changed","reason":"全账号保全增加knowledge-sync独立SQLite状态，图04标示账号目录快照及历史保留；网关身份角色不变。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"在既有能力工具目录加入两个仅查询读取工具，沿原DataKey与可信会话回调，不增加能力执行器或MCP授权。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"知识工具沿原Host回调及运行时guard取可信session_id，现有研究执行、任务恢复和权限角色不变。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Host仅为明确启用的资料同步运行60秒worker并在关闭时取消；既有Automation日程、运行恢复及研究状态机保持。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"原可信回调中补知识资料查询投影，金融Provider、数据仓、快照原件与PIT准入链保持；资料新数据边由knowledge-backend图04负责。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"规范报告仅扩充knowledge回执引用的合法身份并由Host质量链复核，原报告文件装配、模板底稿和正式定稿生命周期不变。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks步骤保留旧WeKnora回归并追加离线合同，原Mac安装步骤仅补模块导入；作业、runner、依赖、触发和门禁不变。","diagrams":[]} -->

## 交付与恢复边界

源码、CI、安装、业务接受分别记录。原生图04由未修改的 Archify 生成与验证；生成器产生的15处纯空白行保留原字节和 provenance，对其余源码执行严格 diff 检查。正式账号与测试账号分开；用户注册后须通过本人登录绑定，测试资料、旧凭据与旧 owner 状态先留存再受控切换，不伪造身份或重写旧引用。服务更新走专用固定产品 profile，保留原模型、MCP 与执行器配置，成功后主动回滚另有显式入口，不能把普通 recover 当成完成后的回滚。
