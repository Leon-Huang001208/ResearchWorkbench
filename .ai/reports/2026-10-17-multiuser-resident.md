# 多用户常驻附接与保全

宿主 macOS / Mac mini；任务为功能开发及已授权常驻部署。本平台验证覆盖绑定、保全、进程恢复和真实私网登录/隔离；Windows/Linux 产品验收 NOT_RUN，完整机器重启及模型生成单独记录。

保留原监督器、原数据目录、原模型 Keychain 命名空间及原 Web/DSH。唯一可信 primary 管理员绑定原实例，新用户只使用独立 pair。原实例占一个容量槽，primary 禁止停用/停止。新 LaunchAgent 固定交付 SHA，私有 journal 先于 HTTPS 切换；失败回到原路由，不覆盖数据。

审查修复：匿名健康改为廉价先前状态；认证深度核验单飞三秒缓存。保全覆盖业务 tmp/.lock，未知链接拒绝；跨 boot 恢复要求完整已知 owner 及安全目录，无 PID 信号。同 boot 及未知归属仍拒绝。

新增离线测试最初因模块不存在失败；修复后 16 项通过。真实原实例只读绑定验证通过，revision a2030f68522f47fad07f55943696bb7ff2d40608，active=false；尚未部署，不将此结论称为生产完成。生产密码、账号、会话字节和私有部署验收仅保存在本机，不提交仓库。

后续独立评审发现扫描根及父目录符号链接遗漏，现逐级 lstat 拒绝，并补充10种存在/悬空根及index链接用例。最终定向27项通过；前次完整相关Python158项、JavaScript233项通过。Ruff/Black/isort及multiuser mypy通过，文档同步与Project Constraints无违规；最终集成候选须重新执行相关闭环并等待三项CI。机器阶段与Windows/Linux缺证保持。

第一候选94ba3e7的三项CI实际通过；等待期间PR129先合并为8a2071b。原集成分支保留祖先合入新主线，两侧文档说明均保留，README遵循上游对旧资讯段落的替换。为避免隐式切换primary现有资讯功能，认证后的primary界面/静态资源与原AIHOT只读API绑定原backend版本；新用户维持最新独立实例和共享资讯合同，不配置资讯库或worker。新增回归先失败再修复，resident与共享资讯49项通过；新候选重新验证与独立评审。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"复用既有部署图网关按账号路由到Native Web及DSH的同一边界，primary仅绑定已有pair的身份与生命周期所有者；不增加图中节点、网络路径或执行引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有登录与研究路由内按已认证primary绑定原界面版本，并隐藏受保护按钮；组件和网络边界保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅向已有Research Web Checks相同Python步骤加入有界离线测试，没有新增job、runner、依赖或平台dispatch。","diagrams":[]} -->
