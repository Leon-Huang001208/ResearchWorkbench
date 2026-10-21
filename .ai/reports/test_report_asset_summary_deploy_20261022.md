# 资产观察 v2 固定版本部署：源码检查点

宿主为 macOS，本任务为 Web 功能开发及已获用户明确授权的常驻部署。产品 PR175 已合并为 `93d62be64084a5c92541a4a008216c0b3f56c2f1`；本报告记录正式 v2 操作员源码与文档的检查点。最终候选 CI、实际切换、保全及资源收尾由后续绑定版本的私有回执记录，未执行项不据此宣布通过。

## 范围与保留合同

新增 `reviewed-asset-observation-v2`／`apply-assets-v2`，固定旧主实例／网关 `9bc12355c3b80e4e4459f4c250e13fc2634ed23d` 与上述已审产品；不接受运行时任意 previous 或 payload。原 v1 的 `c68814db` → `54d4c8f9`、模型专项及历史恢复包保留。全部资产 mode 复用原完整差异路径并集、祖先、Git blob、文件模式和固定 `evidence.py` SHA256 核验；产品路径回退、删除或未知修改仍拒绝。

原 v4 journal、不可变 `controller.pyz`、锁、BirthFence、优雅停止与内容寻址恢复包保持。研究、自动化、私有池、资产观察及 DataHub 查询必须明确空闲；主实例和全部私有账号业务 index 每个顶层值冻结 canonical SHA256。前进／回滚／完成／preparing 恢复核对原保全摘要，数据根、账号、会话、模型元数据、凭据、HTTP 和业务持久化不变，无供应商或模型调用。

实际执行源须是最终已合并且三项 CI 合格工具版本的干净受管 checkout，与实际模块路径及原源码 common directory 一致；开发目录的其他任务未跟踪文件继续保留。执行解释器为原生产 venv，不复制源码、凭据，不扩大自动白名单，不新增依赖或修改工作流。

## 已执行与待执行

- 文档已同步部署合同、安装、任务路由、架构／数据／API边界及 README 审阅登记。
- 实时 GitHub API 核验仓库 PUBLIC；最近五个成功 job 的实际耗时为62／310／61／594／60秒，证据 `logs/asset-v2-docs/actions-current-budget.json`。本轮沿原三个作业，无新 runner、依赖、超时或跨平台产品 dispatch。
- Node24 的文档治理／架构／Actions 目标测试109项 PASS（4.324秒），日志 `logs/asset-v2-docs/docs-tests.log`；`scripts/check_doc_sync.py` PASS，含架构、781份文档治理与 Python 文件索引，日志 `logs/asset-v2-docs/check-doc-sync.log`。首轮因所属模块文档未全部同步而失败，补齐既有部署／运行／安全／平台／资讯边界说明后复验通过，原失败保留为 `check-doc-sync-attempt1.log`。`git diff --check` PASS。未新增 Python 文件或符号索引条目，生成索引无需修改。
- 主执行者提供的独立 Python 规格／质量评审为 APPROVE，无实质问题；两个模块合测339项 PASS（9.72秒），Ruff／Black／isort／diff检查通过。批准绑定操作员 SHA256 `3cb77f2990b031b9beb42ed01feba14db1ec23b4e98308803bcecaf5d65bfdcc` 与测试 SHA256 `d4e273053effe52c28bc6a1a59624f5fe27b4156d85b7edb9eb33337a1e0c505`，独立评审完整日志由主执行者归档。
- 完整20文件 changed set 的 Router 为 L4；14份受管内核文件 SHA256逐项通过。L0→L4四个本地门全部 PASS／5.262秒：文档治理、Python索引、完整变更约束、Web完整验证，日志 `logs/asset-v2-closure/results.json`。保留 unknown_impact_boundary，不降级；补充选择既有 Checks、Project Constraints 与 Mac Bootstrap 三项 CI。
- 同候选 Mac 安装、实际部署与资源收尾由后续绑定版本的私有回执记录。其他平台原生产品验收保持 NOT_RUN；Ubuntu 通用检查不能充当其产品验收。

## 架构复核

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅为既有显式联合升级器增加固定v2身份，原v4事务、控制器、进程、锁和恢复拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"两资产profile复用原出生栅栏、空闲和全部业务索引保全，不改账号、私有池、权限或数据根。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"本机操作员CLI不新增或改变公开HTTP方法、路径、请求和响应。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"参数化既有注册测试并保留原三个CI作业，无新job、runner、依赖或其他平台产品dispatch。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"查询状态仅用于已有空闲证明，不发起来源请求、不重写观察或快照。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"不增加Skill、Tool、供应商或研究引擎，DSH保持唯一研究执行。","diagrams":[]} -->
