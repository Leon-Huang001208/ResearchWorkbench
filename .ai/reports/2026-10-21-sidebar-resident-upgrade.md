# Mac mini 侧栏部署的显式静态候选修复

macOS；用户明确授权保留会话/模型部署侧栏，并在发现安全阻断后明确批准先正式修复部署工具。
现场primary与gateway为4d011a0，侧栏源码已合并到ceeac6e。阻断来自两版本间唯一非静态路径gateway_upgrade.py；自动兼容门和旧apply-ui均正确拒绝，未停止服务、未绕过门。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"新增显式stage仅准备原resident的候选和新旧wheel；原不可变controller仍拥有空闲切换、锁、journal和恢复，网关继续原出生栅栏/排空/保全。唯一helper例外绑定完整Git blob并随version 2恢复包冻结，不新增服务、数据根或自动兼容范围。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"部署与恢复角色未迁移；主实例沿原wheel/candidate和不可变bridge，网关沿原独立冻结helper。UI及同一helper的显式升级不改变依赖、固定DSH、运行模式、端口或业务协议。","diagrams":[]} -->

## 实现与边界

stage-primary-ui要求精确干净源、同Git common directory、原解释器、manifest及artifact身份；拒绝主实例/网关恢复journal、隔离候选、其他未接受候选以及构建期间candidate/manifest/master变化。已接受旧候选可退休；同审查身份可验证复用。只写新旧wheel和candidate，不停服务、不改baseline、controller.pyz或自动compatible。

apply-ui的payload可含升级器唯一文件，但其完整Git blob必须等于冻结tool revision；缺失、删除、不同helper和其他后端/依赖/controller路径仍失败。冻结恢复离线重跑该判断，拒绝临时callback/monkeypatch，不减少既有原生/Host/自动化空闲、出生栅栏、优雅排空、恢复及原会话/模型保全门。

已只读核对现场controller.pyz摘要与配置一致，其冻结tick具备同previous/target candidate复用分支，随后仍重新资格核验并调用原deploy。现场原candidate等于accepted，为可退休记录；这些是预检，部署前必须重新核对。

## 验证

新增helper回归先在原实现失败；stage构建期间candidate替换回归先失败，补发布前比较后通过。扩展同helper产品的真实冻结pyz六阶段离线恢复，覆盖preparing/draining/stopped/starting/rolling_back/fallback_starting；原独立工具/产品范围仍覆盖。110项专项回归通过，完整结果见logs/gateway-green.log；后续扩展和最终候选重新绑定日志，不把首次失败抹去。

使用其他任务已有开发解释器只读运行测试/格式/类型工具，不安装或修改其依赖，不登记或清理借用环境。源码已有日志与异常传播；阶段失败由既有命令错误处理输出固定码。真实保全预检仅输出数量/指纹：主实例63会话3193文件，12个私有用户共44会话3288文件；该快照不代替升级锁内和部署后的保全核对。

公开安装器、requirements/web.in和web.lock、setup_web.py及固定DSH未变；同候选Mac干净安装CI仍必需。真实模型调用不在本任务范围，Windows/Linux产品验收保持NOT_RUN。源交付、CI、primary和gateway实际revision以及最终浏览器侧栏验证分别记录，尚未执行的项不标通过。

最终本地闭包：gateway升级、原resident和multiuser-resident合跑176 PASS（23.35秒，1项既有Starlette弃用警告）；治理/架构/Actions/跨平台源码合同112 PASS。Ruff/Black/isort及helper模块mypy通过，check_doc_sync与Project Constraints通过。独立Python评审110 PASS，首轮因未显式绑定PYTHONPATH而误导入借用环境的旧app，改为当前worktree后通过；保留该失败说明，不误归因源码。CI和真实部署仍待后续精确候选证据。

集成最新PR162的v3网关恢复支持后，保留两种事务；只更新网关仍不能交付主账号完整壳，因为primary_ui来自主实例目录，因此本任务仍须stage-primary-ui。合并仅解决相邻函数/参数矩阵及说明文档冲突，未回退并行实现。新增v2同helper恢复组合并保留v3矩阵，最终三模块本机204 PASS（24.85秒，1项既有弃用警告）。主实例和网关真实升级仍在精确源码交付后单独执行。
