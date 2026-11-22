# WeKnora 资料适配结构决策

源码阅读与Atlas链接检查点为 `e06c884fbe38d15a6c03f5a4421013b794992172`，基线为 `46d86544097a04f2404fe0599f90d3553dc0c028`。它是已存在的RWB源码提交，后续文档或上游补丁制品提交不改称在该SHA执行CI；最终候选、上游Go、服务与业务验收另记。

新增外部资料网络边和本地不可变证据，不增加研究执行器、调度器或第二套报告生命周期。WeKnora界面零生成、真实服务、宿主与业务报告验收分别记录；当前未完成底座替换。

<!-- architecture-review {"group":"knowledge-backend","structure":"changed","reason":"新增到固定外部WeKnora的原生用户认证和文档范围读取，以及账号根内内容寻址原件/分块证据；图04明确展示新网络与冻结数据边，不将待验服务或报告宿主画成已部署执行器。","diagrams":["04-data-file-flow"]} -->

<!-- architecture-review {"group":"ui","structure":"changed","reason":"既有数据设置新增资料绑定、独立管理链接和显式库读取入口，确实可到达新外部资料边界；图04展示读取入口与薄适配，未新增导航分类或通用Agent产品。","diagrams":["04-data-file-flow"]} -->

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"Host新增认证资料路由、原生JWT核验、scope和证据冻结，是真实公开协议与持久数据变化；图04补充外部服务及账号证据节点，原研究和报告运行状态机不改。","diagrams":["04-data-file-flow"]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"changed","reason":"原私网账号Host新增操作员origin传递和knowledge-backend保全，资料读取由当前WeKnora用户权限限定；图04展开新跨服务资料边，不新增身份提供方或将空间Key当作个人身份。","diagrams":["04-data-file-flow"]} -->

<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"ResearchService只构造惰性资料适配，没有增加timer、自动入库、模型提交或日程；原Automation图的运行角色和触发链保持，新增资料读取/冻结边在04图单独展开。","diagrams":[]} -->

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"新资料模块组、API分类与图04内容继续沿原字面量扫描、确定性Atlas、固定HTML白名单和同哈希图文门；未增文档服务、任意文件读取或另一生成管线。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"九份离线资料测试加入原Checks列表，设置模块加入原Mac静态资源核对；无新job、runner、时限、依赖或跨平台产品dispatch，原验证与费用门保持。","diagrams":[]} -->


新增stdlib origin校验和冷Doctor、完整资料admission及16KiB绑定写前门，仍属于图04原认证／存储节点内部；不是新执行或部署角色。最终源码pin已核对到e06c884fbe38d15a6c03f5a4421013b794992172，本机早先WIP验证保留真实回执及blob映射，不改称在该SHA当时exact执行。


共享origin校验helper只将现有非秘密配置规则从server启动模块分离，cold Doctor与dispatcher调用同一stdlib实现；图04的角色和边保持，不新增Actor或权限。检查点e06c884fbe38d15a6c03f5a4421013b794992172已包括0003、admission、绑定16KiB门；已实际核对共享helper属于该提交，后续文档提交继续采用此源码检查点，不改变早先验证的真实执行身份。
