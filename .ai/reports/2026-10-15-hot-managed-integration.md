# Hot 受管主线集成

宿主macOS、功能开发，Mac Native/Docker及同平台CI负责，Windows/Linux真机与产品dispatch交接NOT_RUN。原Goal和业务模型scope不缩减，cap20calls/100000tokens/USD1保持，现有18/77375/10464microUSD不重置。

新task hot-intel-goal-final-20261015通过RWB git_safety delivery start建立，featureWorktree位于hot-intel-managed/hot-intel-goal-final-20261015，base97b7b64e0fc62be98e040a6d212e624dc4c5e80f，合入原检查点321818fb5。旧Hot worktree/PR106/所有运行数据保留，不伪造已有delivery receipt。第一次工具Node24 execPath与既有git shim的/usr/local/bin/node不同而SHIM_INVALID，Git写入前拒绝；检查代码/权限/归属后用既有绑定Node25仅运行Git工具，未改shim/全局PATH/Hot Node24产品合同。

23文本冲突中源码两处：research_helpers保留主线chinese_font_path与Hot read_hot_evidence，AST审查确认两侧原逻辑均完整；app.mjs保留主线EmbedBridge/主题/IME与handleInput单一input/change，增加Hot import及dirty状态，无重复监听/提交。文档保留两侧独立职责段落，architecture-map保留两种近处测试，Python索引/API图册从当前源码重建，不使用旧HTML整文件盖掉主线。

实际验证：源码相关Python166PASS/1warning；Router运行/安装/模式闭包1356PASS/1SKIP/5warnings；全JS+Hot771项中769PASS/2SKIP；Hot类型/两源码语法/Python索引/文档治理及完整299文件项目约束/架构检查PASS。限定Python/JS独立审查无阻断。两个闭包不当作真实模型或当前安装证据；未新发模型。

后续：控制器prepare集成worktree，核对tree/最新基线，再隔离Mac安装/启动、当前候选Mac CI与安全发布。旧7010镜像7800f8dd的Docker证据只认证旧源，当前合并尚未拥有新完整镜像或MacCI。困难关系真实模型与外部TLS真实连接gap保持，整体Goal INCOMPLETE，不auto-merge未完成Goal。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"将既有Hot正式组件合入主线，责任/PG/唯一队列保持，合并不新增接口。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"保留主线嵌入框架/IME与Hot工作台输入保存，两侧原控制器不合并为新引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"合并字体定位和Hot冻结证据函数，原报告/Word路径保持，无新执行或数据源。","diagrams":[]} -->

## 第二轮候选

首轮受管候选ae54f04f完成隔离安装器API、固定DSH构建及Native启动/Doctor/HTTP/停止；发布前master已推进至4eb4d31b，控制器remote_moved，未push、未创建PR。首轮worktree、安装目录、数据与回执保留。安全入口拒绝替换旧prepared目录，因此建立独立任务hot-intel-goal-final-r2-20261015，基线4eb4d31b5457e56b8c682a6a111b7c4735fdb59b。

第二轮合并仅README复核JSON冲突，主线Gold无有效来源时not_connected逻辑完整保留。实际新增回归：test_frameworks/test_fingpt_research/test_hot_research_evidence共32PASS/1warning/37.22s，全JavaScript710PASS/2SKIP/30.705s，文档治理和暂存whitespace PASS。首轮其他闭包是相同Hot/安装/runtime组件的复用证据，不冒充新候选干净安装或Docker镜像。新候选Mac CI、完整新镜像及困难关系真实模型仍待验；整体Goal INCOMPLETE，预算18/77375/10464microUSD不变。
