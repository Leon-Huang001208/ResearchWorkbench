# 本地知识库 Native 私网路由预检修复

宿主 macOS Mac mini；本任务属于已授权本地知识库功能交付的部署修复。macOS Native、Docker Desktop 及适用 macOS CI 为本平台范围；Windows/Linux 原生验收保留独立交接。

## 实际复现与影响

PR #318 合并为 `238c219f1a29b72374b4ac666b811a10cab34f00`，三项 CI 通过，交付证据已通过正式 `delivery_transfer` 校验导入登记的 Git common。生产解释器执行 `apply-local-knowledge` 在修改服务前被 `model_upgrade_private_route_unknown` 拒绝，未发布事务围栏或切换服务。

原因是旧 `verify_serve` 只允许443，而实际已授权现场同时存在8443 SuperAgent与9443 WeKnora。修复只为 `reviewed-local-knowledge-v1` 核对固定9443和可选固定8443的完整 HTTPS 根路由；未知目标、路径、端口及 Funnel 继续拒绝。原443及其他升级模式合同保持。预检、维护围栏准备和切换检查点使用同一模式，避免前置通过后再次拒绝现场配置。

## 验证与部署

最近回归覆盖实际三入口、无SuperAgent的合法现场及漂移拒绝，既有 Native 回归、项目完整性、独立 Python 评审和原三项 CI 绑定最终候选执行。最终测试数量、命令、退出码与候选存于本任务 `logs/` 和受管交付回执，不将计划当作通过证据。本修复无新依赖、workflow、runner或平台 dispatch；实际受管切换、正式用户绑定和研究界面验收另留运行回执。

WeKnora 的真实邮箱账号由用户本人注册。已注册不等于已绑定 RWB；需由用户在 RWB 设置的本机表单输入既有密码，JWT只存系统凭据库。测试身份及其同步状态保持归档，不自动迁移给正式账号。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅收紧既有Native升级的已授权固定私网路由核验，继续复用原服务、三锁、BirthFence和恢复事务，不增加节点或改变数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"仍由原账号网关和Host执行身份、同源和资料权限核验，只为本次封闭升级检查既有私网转发，不增加用户、授权范围或业务接口。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"回归沿原Native测试模块和既有三项CI，不新增工作流、runner或交付流程。","diagrams":[]} -->
