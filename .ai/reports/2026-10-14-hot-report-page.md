# 研究情报真实报告与状态接入

macOS功能开发，continuation worktree，父候选5ce3d5dab；原目标及预算保持。
读取接口新增GET /hot/research/runs，显式POST /hot/research/runs/{id}/refresh，
GET /hot/research/runs/{id}/docx。GET/下载无模型动作。POST只观察原Native回合及条件更新PG。
报告只绑定原deliveryKey；旧成功回执必须重新核对当前字节，pending走既有严格沙箱验证。
运行失败与报告completed分别显示。PG不可用返回stateVerified=false；不认证活跃状态。

审查发现并修复三个HIGH：后续会话混入旧run、先提交完成再验hash、pending误判永久失败。
UI两个P2（过期拒绝覆盖新视图、POST失败提示被GET重读清掉）已修复。限定复核均关闭。
39项Python交付/结果回归PASS；3个原格式测试在基线原Delivery同样因fund_nav能力前提缺失409，
仅补synthetic catalog fixture，未修改生产准入或删验收。UI10 PASS，原能力拒绝反例仍保留。

实际签名Node/原PG→HTTP→浏览器显示run1f0ba854… failed及报告completed，核对/Word下载成功。
下载Word重开25段含原manifest hash；API导出38556bytes。截图report-page-real.jpg；
report-page-api-proof/download-proof记录原件及0模型调用。原scope仍17/76804/10253microUSD。
旧pr92 build源目录已被外部移除；本轮使用同固定SHA的干净已安装DSH，新私有state_root保留
旧build-lock，未改写或绕过旧锁；隔离Runtime和Web在600秒边界自动退出，Hot controller已停。

后续继续选定研究快照联合恢复、Mac Docker实际构建/持续来源/切换与干净安装。完整Goal
未完成，远端CI未运行，无生产部署、secret复制或新预算。治理/候选日志待最终补充。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "在原Host/PG/Store/DSH及严格沙箱内增加结果读取和原回合核对，复用现有UI组件与交付校验；无新服务、队列或研究引擎，运行和文件状态分开。", "diagrams": []} -->

<!-- architecture-review {"group": "files", "structure": "unchanged", "reason": "在原Host/PG/Store/DSH及严格沙箱内增加结果读取和原回合核对，复用现有UI组件与交付校验；无新服务、队列或研究引擎，运行和文件状态分开。", "diagrams": []} -->

<!-- architecture-review {"group": "hot", "structure": "unchanged", "reason": "在原Host/PG/Store/DSH及严格沙箱内增加结果读取和原回合核对，复用现有UI组件与交付校验；无新服务、队列或研究引擎，运行和文件状态分开。", "diagrams": []} -->

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Hot沿既有Supervisor Web角色和Node子进程进入容器，新增锁定生产依赖构建层与可写日志路径，不新增服务、队列或Docker socket；模型装配仍限Native，联合恢复不复制认证与执行历史。实际Docker和安装证据单独记录。","diagrams":[]} -->

联合恢复真实证据：原暂停 PG 的 50 表恢复到任务独立目标库；选定真实会话输入/输出、
冻结清单与交付回执逐字节核对，报告 SHA256 不变。联合恢复回执
`logs/hot-resume/joint-restoration-receipt.json` PASS；Native 执行历史 NOT_RESTORED。
安装/恢复/Hot管理回归162 PASS（182.12秒）；非法UUID、未知目录、篡改回执与并发index拒绝保留。
