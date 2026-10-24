# 今日发现：最新原始资讯、独立时点与原生双栏

macOS Web功能任务；用户已确认默认原生双栏、最新raw先展示/未形成研判、已有研判独立截止。正式账号/会话/数据/模型配置不作迁移，DSH仍为唯一执行引擎，真实模型/生产跟踪/常驻部署本任务保持NOT_RUN。

问题复现：旧refresh只跳过Host90秒缓存，UI将上游cache_stale泛化为来源未更新；读取原顺序先截60会漏掉实际最新事件（只读样本最新60有13条未进原前60）。raw与已有事件应分别取时/失败，不能仅移除警告或把取得时间补作发布时间。

实现：同reader/radar与/intelligence分别读取、排序和受限缓存；raw独立news_id，没有假event_id。GET selection/association只在当前用户有限内存复核，URL精确匹配且版本校验，关联最多5项且不计作独立来源；正文/关联再读后进入同一DataHub/DSH显式prepare/execute。raw跟踪批准范围锁进原Automation定义，未知受理至多一次，滚窗不可观察不判unchanged；已登记失效任务不回退通用模型路径。旧SOURCE_POLICY/context1字节有固定回归，new raw context2为条件分支；原报告质量门不修改。

原生UI取消hot-reader配色覆盖；查询/来源筛选、两lane、独立时点，保留事件传导/资产/反证/履历、两步研究、独立跟踪和键盘/inert合同。新select稳定id、移动列表overflow、来源明确cache_stale传递等独评问题已有相邻回归。

阶段验证：原定点79 passed/约12.4秒和JS37项为中间证据；最终矩阵/精确候选CI/页面截图随后落logs与正式回执。初次新功能红测、独评拒绝与修复后的状态分别留档，不将中间结果冒充最终验收。安装六文件/DSH pin不新增依赖或变化，由同候选Mac Bootstrap证明兼容。Windows/Linux原生交各自设备，不从Mac派发产品CI。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "在现有Host/Intel/DataHub/唯一DSH/Automation节点内部增加raw联合类型与只读地址核对；来源读取、选材冻结、原引擎执行和文件边界拓扑保持，具体HTTP/行类型/时点已更新相应合同及API清单，无新服务或数据根。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "在现有Host/Intel/DataHub/唯一DSH/Automation节点内部增加raw联合类型与只读地址核对；来源读取、选材冻结、原引擎执行和文件边界拓扑保持，具体HTTP/行类型/时点已更新相应合同及API清单，无新服务或数据根。", "diagrams": []} -->

<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "在现有Host/Intel/DataHub/唯一DSH/Automation节点内部增加raw联合类型与只读地址核对；来源读取、选材冻结、原引擎执行和文件边界拓扑保持，具体HTTP/行类型/时点已更新相应合同及API清单，无新服务或数据根。", "diagrams": []} -->

<!-- architecture-review {"group": "discovery", "structure": "unchanged", "reason": "在现有Host/Intel/DataHub/唯一DSH/Automation节点内部增加raw联合类型与只读地址核对；来源读取、选材冻结、原引擎执行和文件边界拓扑保持，具体HTTP/行类型/时点已更新相应合同及API清单，无新服务或数据根。", "diagrams": []} -->

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "在现有Host/Intel/DataHub/唯一DSH/Automation节点内部增加raw联合类型与只读地址核对；来源读取、选材冻结、原引擎执行和文件边界拓扑保持，具体HTTP/行类型/时点已更新相应合同及API清单，无新服务或数据根。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "仅在原Automation调度入口拒绝已登记但批准范围失效的发现任务，阻止误入通用执行器；仍是同一DSH与原research_task定义，不增加执行、模型、日程或权限节点。", "diagrams": []} -->

实现阶段新增关闭的两个评审缺口：冻结二次读取的实际状态进入manifest，raw无人值守在任何session预留前拒绝新过期；关联顶层传输缓存/as_of/generated_at不计为内容新颖性，event/articles正文与业务时间仍保留。86项发现/跟踪回归、213项API和37项JS通过；本机真实来源GET页面刷新19:46→19:49时最新发布时间19:39→19:46。筛选、研究只读预览和禁用跟踪面板已截图；氦气候选因归档原始地址不同拒绝关联。截图及JSON位于本任务visualizations目录，非生产/真实模型验收。
