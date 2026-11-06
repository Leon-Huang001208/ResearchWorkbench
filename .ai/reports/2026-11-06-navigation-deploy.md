# 统一导航固定 Native 部署

宿主 macOS，维护任务。用户明确要求将已合并PR275上传／合并／部署；源码产品已合并为b192dd1a7d71080a1a4d83ade02102a15cd9f365，本任务只补固定执行器与实际切换，不加入新UI、依赖、数据库迁移或采集／MCP开启。

Product-Progress: not-required — 本次仅增加已合并导航产品的封闭维护执行器及恢复安全校验，不改变用户界面或另行承诺新功能交付。

## 固定身份与安全合同

实际主实例和网关均为5ffecb5219d46a5d3e4148a4ddb630f23a09ab3b；初次读取时两种恢复journal均不存在，Doctor安装／产品就绪，MCP配置为严格False。此预检不是停机许可，切换时仍须锁内重验全部活动。

新 `UNIFIED_NAVIGATION_*` 独立身份为 reviewed-unified-navigation-v1／apply-navigation-ui；PREVIOUS固定5ff，PAYLOAD固定b192。旧PR168 `NAVIGATION_PAYLOAD=4e8be6…` 不变。完整previous→payload/target路径并集、blob及mode冻结，仅本操作员、原专用测试和docs／报告例外；额外tests、README、workflow、后端及新增UI改变拒绝。证据reader193f4fcc、Web锁7c631d4f、不可变controller与自动名单不改。

旧static-ui分两步流程不提供本次需要的全账号原子保全，因此不用该路径绕过workflow兼容门。沿既有v4三锁、BirthFence、64MiB严格业务索引、全部账号／@events／@dossiers和模型元数据保全，Native必须是真实空list，Host及全部后台、市场inflight必须明确空闲。事件日程disabled证明在准备、空闲、切换与恢复边界冻结／重验。

NAV旧gateway_config必须有严格False；forward与rollback均读取local/private实际health，MCP字段必须is False，并核对PID、出生／命令、listener、plist、repository与配置前后不漂移。EVENT旧db2回滚缺字段豁免继续保留，不转给NAV。恢复包强制保存source；实际执行源码须以Git冻结在resident/artifacts/<final-tool-SHA>/source，不成为开发工作树清理对象。

## 定向验证与独立审查

新增身份断言先RED（缺mode），实现后GREEN。新增模式WIP定向180项通过，所有根均按登记身份退休。三次失败原件保留：旧fixture目标manifest集合缺新mode、独立release-clone前版映射缺新mode，以及新payload与旧常量重名导致两项legacy测试失败。均修正后，经独立审查批准的caller在原根／nonce／同20节点精确重入，保持512MiB／64MiB／3GiB、超时、owned PID及正式retire门；未另造失败根或改旧RED证明。新常量全部改为UNIFIED_NAVIGATION_*并硬编码断言新旧payload，旧legacy测试重新通过。

覆盖真实Git union及revert／mode／额外tests／README／workflow拒绝，真实operate Native未知／Host／日程／原空闲边界漂移，CLI模式映射，NAV双向实际MCP布尔、进程及配置漂移和v4失败／恢复矩阵。Ruff、Black和scoped mypy独立检查通过；冻结候选的完整本地回归、独评和同候选三CI仍须实际完成，不借PR275的产品CI认证新操作员。

## 架构复核

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"统一导航固定身份仅扩既有macOS Native v4维护操作员，不增加运行服务、容器或模型引擎；primary、gateway、DSH和恢复数据归属沿原01部署与12资讯图，采集关闭和全账号保全不变。","diagrams":["01-deployment","12-ai-news"]} -->

已复核01部署与12资讯图，保留原图源／产物，未声称重画或新视觉验收。此任务不构建或部署Docker，不认定Windows/Linux原生支持。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"复用原账号网关及v4 BirthFence、全账号业务索引和永久恢复source；仅新增固定导航mode并严格保留MCP关闭，无新HTTP代理、授权范围、账号节点或资讯队列，01部署、12资讯和15入站MCP图拓扑保持。","diagrams":["01-deployment","12-ai-news","15-inbound-mcp"]} -->

已复核15入站MCP图。UI产品、工具Git／CI资格、实际切换、数据保全、健康／Doctor与真实页面分别留证；不启用来源日程、MCP、模型或周报，不处理秘密、不清锁或改变其他任务资源。README入口无需改变，安装器及依赖锁保持。

## 尚待执行

最终source／CI与本机维护回执各自绑定后才可切换。实际部署结果、authenticated页面与资源收尾不得从上述WIP测试推出。原主checkout有一项无关删除差异超过Git备份64MiB缓冲，已由导航源码任务单独记录；本任务不恢复该文件、不扩缓冲或借此绕过Git清理门。
