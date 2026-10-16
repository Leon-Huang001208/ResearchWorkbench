# AIHOT 站内全文与专题阅读

宿主macOS，Web功能开发；本地与macOS CI验收，其他平台不冒认。基线b9ecded85549323d5e650654b3461c305fbd1256。

用户要求文章详情、事件及主题留在模块内完整阅读。使用上游c8704e5313e6b051560365226b3919d7e0ada5ea公开页面合同，真实item/original/story/topic接口已读取；正文3947/6998字符、专题34篇报道/11进展、主题4页。

实现：固定GET、身份校验、惰性HTML阅读树、本地路由、语言切换、目录、关联阅读、来源列表、专题筛选排序/热度、主题大事记/分页、Markdown复制导出。无新产品依赖、迁移、定时采集或模型。上游缺失/部分正文如实显示。

验证：新增JavaScript回归先红（缺少阅读模块），其后21项JS、41项Python已通过；后续完整闭环与浏览器/CI结果以最终候选独立证据为准，当前NOT_RUN，不复用旧PR126证据。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "沿既有Host匿名API与浏览器模块实现站内阅读；正文转为惰性节点，不新增部署节点、存储schema、研究引擎或调度器。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "沿既有Host匿名API与浏览器模块实现站内阅读；正文转为惰性节点，不新增部署节点、存储schema、研究引擎或调度器。", "diagrams": []} -->

独立评审发现并已用反例修复：embed无闭合标签吞掉后文、剪贴板异步完成误写新页面、Markdown漏掉图片/内部引用/引文。扩展后24项JS、43项Python通过；无skip/todo。真实隔离浏览器已见英文全文5407可见字符/7章节、同新闻23篇来源、事件全文/10篇官方筛选、主题第二页20篇/四页、所查页面无控制台错误。

本地Router完整影响29文件、L4；logs/reading-local-results.json记录11项exit0（含架构/文档/索引/JS/Python/Project Constraints/Ruff/Black/isort/mypy/git diff）；新增docs08纳入完整changed-set再次Constraints通过。新依赖仅为先前已授权的任务隔离测试工具，无产品依赖变化。

实现源码检查点80c0eab8f70c8a7a63fbfd18c3a1f6596f4ad099；架构源码链接绑定此点，生成物交付提交另记。完整本地JS220/220、Python73/73通过，目标43项覆盖AIHOT；其余30项为相邻intel。Windows/Linux原生NOT_RUN，未调用模型、未改常驻。

最终浏览器回读发现重复访问同一文章会被误判为历史后退，导致返回落到日报。新增反例先红，修复为显式站内链接意图与受控返回栈；筛选状态仍按事件保留。旧6c候选Mac运行38886160713主动取消，旧证据不用于最终新候选验收。

返回路径修复源码检查点88c3fab3971befa1703837ea64411ec62631bdee；最终源码链接转到此点，生成物提交独立。25项AIHOT JS通过。
