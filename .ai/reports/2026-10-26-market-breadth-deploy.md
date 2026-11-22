# 全市场广度与参考证据组合部署后继

Mac mini / macOS，Web Native运维配置；任务ID market-breadth-deploy-20261025 延续到10月26日。无新依赖、引擎、数据库迁移、业务API或权限。

## 固定范围

用户批准原98c23ed8产品及PR233后，明确纳入PR237，又批准本轮统一纳入通过必需检查和独评的主线业务；新增依赖、迁移、权限、付费仍单独确认。当前补入已审PR236的NYFed SOFRAI证据合同，固定PREVIOUS为实际常驻b800e50366d1a0868372bbf173822976066c143f，PAYLOAD为4c72ed4349c087cf0b7d037d7133b84201a76d5f（含PR233/235/237/236）。新apply-market-breadth / reviewed-market-breadth-v1不接受任意目标SHA；最终操作员必须是该产品加必要操作员/文档/测试的受审最新合并版本。

reader193f4fcc、web.lock7c631d4f及原controller/evidence源码保持，新增mode完整进入旧ASSET_MODES的源码并集、严格业务索引、manifest、全部账号后台/工作流/市场、Host/Native空闲及version4三锁/BirthFence/保全/回滚。没有加入周报桥或Wind恢复执行分支。

## 实际验证

- 新冻结合同RED：旧源码缺mode，1 failed / 2752 deselected（0.27秒），不是导入失败冒充RED。
- 新mode关键GREEN：5 passed（0.58秒），包括真实operate、真实g.verify_primary/LegacyBinding的Host true/null提前拒绝，原索引不变且没有维护栅栏、周报intent或恢复副作用。
- 原profile扩展及缓存邻近闭包八模块：3106 passed，1条既有AnyIO弃用警告，300.83秒；外层实测301.207秒。涵盖operator/gateway/resident/dossier/graceful shutdown/snapshot store/PR233 BaoStock及reference evidence。
- Ruff、Black check、isort check、Mypy定点通过；生成Python索引check通过。完整Router、最终候选独评/原三CI及同候选Mac安装待最终冻结后另记，不能借产品旧CI认证新操作员。
- 无包安装。首两种既有测试工具复用方案因Desktop云占位的AnyIO插件/源码导入阻塞，分别中断自有测试进程和超时，原证据保留，未算测试通过。最终只读复用本机primary库并把已有批准的ETF测试工具放在其后，关闭第三方插件自动发现并显式加载项目需要的pytest_asyncio；选定用例/断言未删除，完整CI仍沿原环境。离线runner在导入前以失败哨兵封锁xlwings App/Book，未操作Office/厂商/模型。

## 现场阻断，不等同上线

实际只读GET仍为enabled=true/revision=b800/maintenance=false/active=null，私网health ready且无围栏；日志存在Wind清理未确认。原周报任务只读复核亦明确PR237只有preflight、recovery_implemented=false，旧Host缺分项见证，没有已审可执行恢复途径。日志不能证明Wind是唯一未知项或所有Future已结束。

普通Primary/idle门保持拒绝，不清标记、不取消其他任务、不强杀或重放模型；新产品范围批准不构成unknown放行或Wind恢复许可。本轮实际服务切换和认证新页面仍BLOCKED/NOT_RUN；必须等原门可证通过再执行。

## 结构与保护

同步原安装/Docker/平台、01/02/03/04/05、资讯/周报、架构开发映射、工作流、预算及README评审。原节点/领域边与图保持，无需新增图。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","diagrams":[],"reason":"仅在原Mac Native version4操作员增加固定b800前版与获批4c72完整产品身份，严格reader、三锁、BirthFence、保全和恢复路径保持；无新服务、依赖或研究引擎，01/12图及既有模块映射准确。"} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","diagrams":[],"reason":"新增mode沿原全部账号后台/工作流/市场与Native空闲门、租户根、业务索引及档案保全，不增加HTTP或宿主权限；旧Host未知继续拒绝且不触发Wind恢复或日程，原私网数据流和图保持准确。"} -->

历史Git原树缺口及隔离材料原样保留，本任务不删除历史或恢复替代对象。常驻、会话、业务数据与模型配置没有写入或切换。Windows/Linux原生保持对应设备交接，Mac不派发其产品CI。源码按持续授权交付及安全清理；实际部署状态与源码资源cleaned分开记录。

## 本轮统一范围与重新冻结

新主线PR236增加NYFed原件/单位及入仓合同，原源码独评、三CI、Mac安装和真实重启/空库恢复均有本任务之外原证明；不据此替代操作员CI。此处仅更新固定产品祖先，不扩大通用路径白名单。八模块3106项为DAC阶段实测，最终集成后追加NYFed邻近模块并重做完整冻结候选验证；实际Wind阻断不因此解除。
