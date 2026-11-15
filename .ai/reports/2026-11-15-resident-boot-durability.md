# macOS 常驻启动恢复与网关本地源码

- 类型为 macOS Native 安装与维护功能，开发在非云盘隔离工作树完成。
- 安装时登记 APFS 稳定身份，现有安装可显式登记独立恢复工件。登录恢复校验已登记物理目录后仅同步设备号，保留原 supervisor、稳定绑定、业务数据、账号和模型配置。
- 网关从登记的本地 Git common 生成精确工作树。既有云盘依赖由离线同版迁移事务恢复，保留原配置和工作树证据。
- Product-Progress: not-required — 本次仅修复安装和运维恢复逻辑，桌面内功能和入口保持一致。
- 原三个 GitHub 检查及 macOS 干净安装门继续适用。Windows/Linux 本机验收不在本 Mac 任务运行。候选源码、真实常驻切换和登录后技能验证分开取证。

## 结构复核

原 Native 与私网网关是独立用户 LaunchAgent。新增 APFS 恢复工件只在配置层修复物理设备号；网关工作目录校验与迁移集中到同一模块。既有监听端口、业务数据流、账号边界和升级资格未改变。原公开安装器、Web 锁定依赖与固定 DSH 沿原 CI 核对。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"APFS 作业属于 Native 登录维护控制面；Native Web、网关与 DSH 的既有端口、所有权、Docker 挂载及业务拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"同版本网关工作目录迁移与启动检查保留既有原管理员绑定、所有额外用户数据、认证和 Tailscale 入口。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在既有 Python 检查步骤纳入离线原子恢复和云盘阻断回归，Mac 安装步骤增加 APFS 临时目录及工件执行探针。","diagrams":[]} -->
