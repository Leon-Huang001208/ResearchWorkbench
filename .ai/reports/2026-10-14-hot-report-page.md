# 研究情报真实报告与状态接入

2026-10-14后续：用户明确允许复用已停止stage/candidate并保留旧镜像/5卷，预算不变。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在既有macos-14公开安装任务中选择受支持Node24.19并增加Hot生产包纯导入核验，保留完整平台与模型硬门；停止错误不再省略，不新增工作流、运行器或付费调用。","diagrams":[]} -->
首次受管replace-image拒绝container_ownership_mismatch；实际字段只差默认DNS的
null/[]与已规范化的OOM默认。DNS新增RED反例后仅规范化空默认，18测试PASS，
显式DNS变更仍拒绝，限定Python与合并审查通过。未手改账本。
随后同一candidate被docker-release-g2b工作流并发使用；不抢占其运行演练。
最新0cf38ff主线合并25个冲突文件已处理，保留Hot报告与Claw/凭据/历史能力。
合并后JS464项：463 PASS/1 SKIP/0 FAIL；Python必需闭包执行中，MacCI尚未开始。

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

## 当前本地验收与阻塞

- 源码提交 `6aa80b64bb6e37855a4490ab5bb6b4ffa310fba6`。真实浏览器截图在
  `logs/hot-resume/report-page-real.jpg`；隔离预览已停止。
- 恢复后独立目标库实际启动正常 source worker，DeepMind 与 ECB 的公开来源采集成功，
  原材料身份保留；停止后 `paused=true`。`joint-recovery-runtime-receipt.json`
  保留原预算 17/76804，模型禁用、没有付费调用。最新文件恢复重验见
  `joint-restore-current-code.json`；不恢复 Native 会话执行历史。
- 干净 Git checkout 为相同源码提交，在独立数据目录通过 `SetupWebInstaller`
  安装 API 完成哈希锁定 Python、CJPY、固定 DSH 和 Hot 生产依赖的完整安装；
  实际 Web/DSH 启动、Doctor、首页/静态模块/Hot 状态与结果读取、受管停止 PASS。
  证据在 `/Users/leon/.codex/worktrees/hot-clean-install-20261014/ResearchWorkbench/logs/`。
  公共 shell 入口真实安装 NOT_RUN；其入口/安装合同测试通过。Mac CI NOT_RUN。
- 受管冷构建、重建和 exact-commit 镜像完成；当前候选镜像
  `sha256:6733bdd1825dec80ff487fcbad5754e47b3ab2d8e7da16180403e39320c2aac7`，
  镜像 revision 与源码提交一致。未把编译成功当作 Docker worker/切换通过。
- Docker stage register 返回 `environment_pool_exceeded`：另一个已停止候选保留
  stage 配额。未退休/删除它，未手改账本或通过私有账本绕过配额。
  复用其镜像与数据需要用户明确授权，已经提出一次请求；Docker 运行/切换 BLOCKED。
- 必需源码门：127 项治理/架构/Docker 合同、247 项容器/协议、162 项安装/恢复/管理
  回归 PASS；结果 Python 39 项与 UI 10 项 PASS。计数覆盖不同闭包，重叠不相加。
  Git 绑定回执 `report-install-bound-receipt.json` 为 BLOCKED/NOT_READY，远端门未运行。
- 最新 master 为 `0cf38ff23f72b9537ca4a09616115ec1cc50d979`。系统 Git 无
  `merge-tree --write-tree`；使用兼容三参数的只读预览保留原始字节，发现 40 个冲突标记。
  尚未合入新主线。未 push/PR/CI/merge/部署，其他平台保持交接 NOT_RUN。

完整 Goal 仍未完成。后续需完成关注/周期简报产品动作、来源/留出样本收束、
Docker 实际采集与顺序模式切换、最新 master 集成及候选 Mac CI/可审查交付。
预算仍 20 次 / 100000 tokens / 1 美元，累计 17 次 / 76804 tokens / 10253 microUSD；
本轮新增模型调用 0，不创建或重置 scope。
