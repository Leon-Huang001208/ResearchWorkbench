# RWB 私网仅服务模式

本任务在 Mac mini 的独立 worktree 实现显式 `server serve --service-only`。
当前仅处理隔离模式，WeKnora Agent 真实授权、草稿及生产切换待验。
历史索引和已批准文件继续读取，原生正文和需要原生质量核验的下载单列。

受管 WIP 回归通过实际 Web 单子进程启动和 MCP 后端冻结原件读取。
同次验证没有内置 DSH 认证文件、模型或额外依赖。
旧固定 PID 测试改用确定性进程观测夹具，避免本机其它进程导致结果漂移。

<!-- architecture-review {"group":"private-multiuser","structure":"changed","reason":"网关可按显式配置只启动一个账户 Web 进程，存活后端的冷启动、所有权和读取要求分别核验。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"复用原 Web 命令规格，私网仅服务模式只创建和管理 Web 子进程。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"同一账号 Host 在仅服务模式直接提供数据与证据读取，启动时不创建内置 DSH 连接。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"仅服务模式跳过现有研究自动恢复，未引入新的调度节点或执行方式。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"现有状态徽标显示外部执行模式，页面与 API 仍使用原网关调用路径。","diagrams":[]} -->

独立复核指出旧交接 GET 会协调原生状态并写索引。本模式收敛到经检查的
读接口，历史详情仅显示已登记文件与数据集，出站 MCP 历史证据需原授权。
实际完整 CI 和真实 WeKnora Agent 不以本机隔离测试替代。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"历史文件读取使用原索引和同一文件根，已登记文件映射保持并禁止读取动作发现后写入新映射。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"冻结快照读取走原接口与原快照存储，仅服务时使用现有严格场景校验且不恢复执行。","diagrams":[]} -->

首轮合成候选的协议回归发现旧最小宿主夹具未调用构造器。类级默认值补齐原内置行为，实际仅服务对象仍由无传输客户端选择。失败的本机批次按原回执保留。

HTTP 回归覆盖无 lifespan 的静态壳读取。模式在应用工厂内固定，路由守卫因此不依赖 Host 已初始化。相关失败回执保留。
