# FinGPT 原生 WeKnora 替换

- 平台：Mac mini，macOS Web 功能开发；Windows/Linux 原生 NOT_RUN。
- 范围：只替换 FinGPT；保留 Claw、知识库、DataHub、正式报告。用户明确直接删除旧 FinGPT 聊天专有数据，不备份或迁移。
- 已运行：11 项相关 HTTP/代理/删除回归通过；真实固定 WeKnora 原生登录经过正常 RWB 测试账号认证，用户与空间匹配，完整页面到达，无页面脚本错误；真实 nginx Cookie 请求/响应双向试验通过；壳重绘后 iframe 内哨兵保持，原生上下文未重载。
- 实际修复：入口 `.mjs` 初次 MIME 错误、原生 OIDC 发现路由缺失，均在原场景修正并通过。不使用模型探针，不伪造正式 RWB 登录。
- 删除现场：主账号5条旧 FinGPT 聊天，其中一条有2份数据集，保留 data-only context；实际生产删除和部署在必要 CI 通过后执行，目前尚未执行。
- 限制：原生 rerank 尚未配置；此次不把界面/登录通过当作全部金融质量或子 Agent 验收。已独立打开的 WeKnora 标签沿原生 token 生命周期，不宣称跨站全局退出。
- 证据：本机 Scratch/RWB/fingpt-replacement-20261123 中 browser-sso-result、cookie-wire-result 和真实工作台截图；CI、最终候选与部署状态后续据事实更新。

## 结构核对

<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"unchanged","reason":"仍由既有网关和原MCP OAuth处理工具授权；仅为已实测Cookie边界的同主机完整前端增加显式配置，服务节点、数据源和逐用户权限不变。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"FinGPT入口复用既有WeKnora五服务与原网关，Claw继续原DSH；升级停止阶段加入显式聊天删除，不新增运行服务、容器或部署层。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在已有RWB浏览器到WeKnora完整应用连接中替换FinGPT视图，复用原账号与导航；节点和来源边界不变，具体入口与局部重绘在界面合同同步说明。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"固定身份交换端点位于既有账号网关，已补真实API库存；原Host只排除data-only聊天投影，不增加研究执行节点或改变正式报告边界。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service仅隐藏保留下来的data-only上下文，不修改Automation调度、运行索引、任务授权或现有研究链；数据与权限拓扑保持原样。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"沿既有三项CI选取本组件与共享账号/MCP的相关闭包，未知路径走完整范围；没有新增工作流、runner、平台声明或执行通道。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"登录桥和精确删除均在既有网关及账号Store内，仍使用原SQLite、既有维护围栏与原WeKnora账号；新增HTTP合同已登记，不增加数据库服务或新的身份系统。","diagrams":[]} -->
<!-- architecture-review {"group":"knowledge-backend","structure":"unchanged","reason":"原生auth/me核验后在原账号绑定补存SSO映射邮箱，知识库、向量化、同步与current-hit权限链保持，未新增数据来源或知识存储节点。","diagrams":[]} -->
