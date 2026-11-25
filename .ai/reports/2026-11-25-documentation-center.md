# RWB 文档中心

宿主 macOS；任务为文档信息架构、静态阅读模板与内容迁移。已有返回链接修复保持。
现有生成链内增加共用模板、有限页面清单和内联搜索，未新增依赖、业务API、数据存储或执行器。
首页与阅读页实际预览先交付用户；后续补三条样板及同源分域参考。迁移/接口边界见 docs/manual/migration.md。

验证：读取器/文档中心35个Python通过，另有两个MCP发现/冻结读取目标测试分别通过；
架构Node162通过、额度治理38通过、设置UI12通过。实机浏览器在原sandbox/CSP下验证了
内联搜索、结果跳转、深色主题、390px目录/表格及旧module锚点跳转，无整页横向溢出。
只读主实例目录/技能API返回200且形状与样例一致，未新取供应商数据或执行模型。

独立Python及JS评审未发现安全回归、操作锚点丢失或业务语义修改；评审指出CI遗漏架构清单，
已加入文档闭包和完整页面集正例。生成器首次有stdin EOF等待，改为JSON行协议并增加保持
输入管道打开的回归测试；现有生成与完整changed-set门禁通过。所有生成物提交前统一重建。

P4：接口主线 #338 已合并为 d8be7c41，现场主实例仍为 beefb617；接口窗口另在
asset-business-query 独立候选继续实现，尚未收到正式新契约与部署确认。新工具不写作
线上能力，正式参考仍绑定既有发布快照。文档交付与业务部署保持分开。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"在原静态文档生成与隔离阅读节点内重组用户内容、共用模板和有限白名单，业务接口、运行拓扑与权限语义保持，文档合同已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅将设置页既有文档卡片的名称和说明改为文档中心，入口URL、事件、业务表单和权限保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"复用既有文档闭包加入固定页面、生成器与相关合同，不增加作业、runner、依赖、平台派发或时限。","diagrams":[]} -->
