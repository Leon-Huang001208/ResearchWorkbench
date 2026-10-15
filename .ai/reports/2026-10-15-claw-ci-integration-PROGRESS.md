# Claw 候选发布与主线整合

宿主：Mac mini/macOS。任务：Web 功能候选的 CI 与冲突整合。状态：IN_PROGRESS；不合入 master、不部署、不清理。

## 已发布的原候选

PR103 分支已从 `de0fc4e30` 快进推送到 `e44cb7c90073790a44b365e8310937341a689eff`，原 worktree、Native 候选和证据保留。发布使用仓库安全锁、系统 Git 和当前 public 仓库额度检查，没有强推。

- macOS Bootstrap：run `38659276112`，success；Checkout 日志与安装摘要均为 e44cb7c90。
- 通用 Research Web Checks：run `38659279129`，success；Checkout 日志为 e44cb7c90。
- Project Constraints 自动 PR CI 未启动：该候选与主线冲突，不能把旧 SHA 的成功移用到此候选。

## 独立整合

整合 worktree 为 `/Users/leon/.codex/worktrees/claw-ci-integration-20261015/ResearchWorkbench`，分支 `codex/claw-ci-integration-20261015`。基线为主线 `4eb4d31b5457e56b8c682a6a111b7c4735fdb59b`，合入候选 e44cb7c90，40 个文件产生冲突；未改 master，也未修改原候选 worktree。

保留主线本地模型、FinGPT 原生计划/思考/停止/重试、框架嵌入与快照、字体和 Docker 显式验收预算；同时保留 Claw 日程/草稿、原生时间线、批准工具目录、文件链接/格式、侧栏与时钟。共享祖先身份使用主线已包含 owner 校验的实现，保留候选的并发同级目录容忍意图，不放松私有父目录检查。

DataHub 保留主线的错误体大小/类型/超时/取消/重定向和固定错误码白名单；仅补入本候选实际定义的两个不可用业务码。`dataset_invalid` 等非白名单字符串继续泛化，不因测试放开。AKShare 不支持参数的精确拒绝优先于普通来源不可用。原生工具仅报告范围与缺口，不增加供应商或权限。

前端四文件由受限 implementer 单独处理，父 worktree 对应源码 SHA 前后相同；Node24 语法4项及五套相关JS117项通过。Root 另测 guard/public-data/外观首次56通过/1描述文字契约失败，恢复主线“注册不代表可调用/不重复请求”说明后57项通过；新增不可用码投影已通过25项复测。原候选CI不认证整合后提交。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有原生壳内保留FinGPT回合/模型/框架bridge与Claw序号卡片和工作区，没有新增渲染引擎或服务。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"合并主线事实投影与Claw现有日程/文件/时钟合同，仍由同一Web Host与DSH执行，没有第二执行循环或认证通道。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"普通Native输出预算与显式Docker验收预算分别保留；DataHub使用固定错误码白名单与原私有桥，无新工具权限。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"按所选格式生成文件并保留中文字体和授权资源路径，文件仍归原会话；预览与下载安全边界不变。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"保留主线AKShare参数拒绝与Claw不可用原因分类，仍由原Broker选择已适配来源和保存隔离快照。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"使用包含owner和私有父目录身份保护的主线实现，保留共享祖先同级活动容忍，Native/Docker仍互斥复用既有控制记录。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"日程研究定义、显式确认及不可变Run仍由现有Automation管理；主线模型和框架整合不增加调度层。","diagrams":[]} -->

来源调查保持 PARTIAL：前端静态索引、实际用户操作与未验证请求/动态状态分别记录；金融与官方文档全文限制保留。任何后续合并、部署或清理仍遵守本任务禁止边界。

## 整合验证更新

- Python：目标模块361通过/3跳过（2项需显式真实Keychain/runtime opt-in、1项Linux限定）；Router组合927通过/3项旧DataHub状态码断言失败/1跳过。按新契约修正3项断言后，完整catalog/protocol135项复测通过，原失败日志保留。安装与运行时607通过。Docx路径修复相关15项通过。
- JS：发现Claw遗漏reasoning展示，新增测试先失败，修复后37通过；最终完整530通过、无跳过。审查确认历史折叠、当前流式展开和原生seq顺序保持。
- 质量：28个变更Python文件Ruff/Black/isort通过，15个目标源码mypy通过；架构、文档治理、Python索引及完整changed-set约束均通过。后端与前端独立审查无未解决重要问题。
- 新整合提交的独立Native安装、真实模型/文件与CI仍待执行，不能移用e44证明。

日志：logs/claw-integration-python-{target,router,closure,install}.log、logs/claw-integration-js-final.log、logs/claw-reasoning-{red,green}.log及.codex/acceptance/claw-ci-integration-20261015/。
