# 共享部署资格恢复与源仓库迁移

原 PR #284 在当前主线仅前移两处附接 MCP 围栏内复核，旧财经日历载荷已归并，
不恢复其过时部署 profile。继续沿已登记 Git common、受审精确候选及原 `delivery_transfer`
合同；本次不替换常驻源码、不移动业务或账号数据，也不退休旧脏工作树、历史回执或恢复锚点。
源码前移与正式部署／收尾分别留证，见[当前保护范围](research-web-gateway-upgrade.md#附接-mcp-保全的围栏内复核)。

管理员构建队列只从已登记源码的完整提交生成临时构建上下文，绑定任务、SHA和固定选项；
该归档不是源码 common 或业务数据迁移，不更改常驻源归属。旧工作树的未提交字节、未推送提交、
恢复锚点和原数据卷继续受原保全与恢复验证约束，不能因新队列或源码前移而删除。

本地知识库固定升级要求在原登记 Git common 下准备同一 exact SHA 的干净执行树，并通过现有 `delivery_transfer` 导入另一 common 的真实交付和评审依据。安装清单与网关配置只新增受管 `weknora_origin`；保持源仓库登记、账号根、模型、MCP 和执行器身份，主动回滚恢复字段旧值或缺失状态，不借此迁移源码或业务数据。

固定私网路由修复仍由已登记common中的受审执行树交付，不替换 `source_common` 或复制Git元数据。
旧路由检查拒绝的目标保留真实失败回执；后继候选重新核验评审、CI和路由身份，不能通过删除既有
SuperAgent或WeKnora入口冒充原现场，也不从源码合并推断常驻已切换。

管理器源码可推进到受审注册恢复版本，运行镜像继续按显式完整 ID 选择固定产品提交，并记录实际注册源码。

Stage 预留交接沿原 Docker 管理账本保存原件和审核绑定；固定产品候选从独立干净 checkout 构建。

FinGPT 双入口回滚继续验证两个已登记 Git 工作树的目录身份及提交。回滚材料放在受管工件目录，引用原前版安装配置和轮子。

上线后的工作树退役只读取 resident 明确绑定的 Git common 及其登记路径，并要求任务提交已包含于实际上线版本。云盘旧工作树、未知归属和未完成保全的目录留待核对，既有迁移证据及回滚材料按原流程保存。

源路径迁移后可用 FinGPT 的逐页重组核验冻结正文与原 SHA-256 的一致性。

策略验证操作员要求干净受审工作树。主实例与附接网关的各自 Git 仓库须在停机前具备同一精确目标对象；从已核验的远端取得对象后，由联合事务切换源码。

受管 Docker 开发构建的标签可随源码规则更新。迁移或恢复既有实例时，继续核对其账本中的完整镜像 ID、工作树和数据卷归属。

Radar 时效升级绑定固定产品提交与普通合并祖先。若交付工作树的 common directory 与常驻登记仓库不同，仍经 `resident.delivery_transfer` 导入精确评审与 CI 证据。

Research Bot 操作员从已注册的 `source_common` 使用干净受审工作树。交付记录来自另一个 Git common directory 时，先用 `delivery_transfer` 核验并导入精确交付和评审记录。

网关同版本搬迁以来自已登记本地 Git common 的精确提交为目标。原云盘工作树作为历史证据保留，详见[同版本恢复](research-web-gateway-upgrade.md#网关同版本迁移到非云盘仓库)。

市场逐日后继固定已接受37051f8f前版及受审载荷；不迁移业务数据或改写前次失败隔离记录。

失败目标9a97168e保持隔离，已接受a76保持可恢复；通过新审核合并SHA部署，不修改原失败回执或绕过同SHA拒绝。

明确动作补丁从已接受a76版本建立独立后继身份，旧EVENT/NAV/LIVE1常量和恢复原件保持。
同一GitHub目标须进入三个实际Git common并核验，受审执行源码继续留在永久artifact/source，
不为部署恢复主工作区的无关删除或用开发worktree作恢复依赖。

`apply-market-live` 固定当前前版5ff及三地总览产品检查点a2ee；最终已合并目标必须包含
该产品并严格匹配全部产品 blob／文件模式，后继只允许操作员、原测试、文档与报告变化。
primary与gateway独立Git common均须拥有目标对象，不能复制Git元数据、迁移源归属或
用开发目录替代已验证常驻依赖；原恢复链和旧profile身份不变。

统一导航维护不迁移仓库：沿配置source_common核对受审源码、两角色repo/目录身份、完整冻结产品及三CI；执行器以Git保留在resident/artifacts/<target>/source，不能引用将清理的开发worktree。不复制Finder源码、不删锁、不改变未知归属资源。

## 事件固定部署的源身份与恢复范围（2026-11-05）

`apply-events` 固定前版为 `db2ae9a48ceca365852072e622aa6627aa7d0b83`，事件功能为 `a398a29429a1c0bdddd34ce50bc336fd6e20f2ee`，产品载荷为 `60416994f88eeead8a3891dbe9a7dfd617c566fc`。后两者 app 树相同，载荷包含已审工程闭包；仍须验证祖先关系、固定源身份及新操作员自身资格，不从开发 worktree 或旧 CI 继承部署许可。

该事务不移动生产根或删除账号历史。全账号业务索引含 `@events` 随原备份、切换与恢复链保存；恢复须重验事件源 disabled 证明、标记及实际无写者状态，WAL／SHM／journal 和孤儿标记保持拒绝。源码迁移或文档补齐不代表当前常驻已更新，实际切换见[部署合同](research-web-gateway-upgrade.md)。

## 事件研究业务根与资格历史（2026-11-04）

事件候选新增个人 `event_timeline/`、初始化标记及独立资格对账标记；它们是业务与恢复证据，不是可随源码worktree替换的缓存。源码仍按GitHub与受管Git流程交付，迁移不得靠复制空库、改owner或删除标记重置已查看／开封区间。

完整事件备份需要元数据及原件；恢复时保留现有追加历史，缺库或未知现场恢复须保持资格对账门，不能从源码迁移成功推断正式回测已重新可用。本候选不授权移动生产账号根、迁移正式库或更新常驻实例，合同见[事件时间线](research-web-event-timeline.md)。

## 源与恢复原件的留存边界（2026-10-31）

本轮可回收对象限于登记过的本机测试根和新任务选择清单中由通过 JUnit 证明的交付原始输出。Git 对象、已审源码快照、固定执行器、迁移前后源身份、恢复 journal、业务/账号/模型配置不随日志清单删除；源迁移和生产恢复仍走原 exact SHA、备份与锁合同。旧任务没有新 ledger 模式时保持原证据字节，不静默套用新清理规则。

## 小型 executor provenance 与原源绑定（2026-10-31）

新 successor 使用独立 `executors/<sha>/stage.json` 与内盘原维护根的小型 pyz，不覆盖冻结 1529 source／旧 pyz，也不复用旧 `artifacts/<db2>/executor`。stage 分别绑定 executor 和固定 db2 资格，运行依赖仍来自已保留且验证干净的 db2 product source；开发 worktree 不成为 production 依赖。固定 90e 的 journal 字节＋inode 交接为 v5，不等于可以任意改 `source_common`，原 before／after 双态仍须核验。

原 15 账号、模型、业务及恢复归档保持原址；admin＋新 test 的账号清理只能在维护终态后独立执行，不是源码迁移的附带动作。fresh retry 依据明确 terminal receipt 开新事务，不借迁移静默清 quarantine、重发未知 spawn 或改变其他平台职责。入口及同事务续行见[successor handoff 合同](research-web-trial-successor-handoff.md)。

## 授权试验退役的来源重绑定（2026-10-30）

固定 `apply-trial-retirement` 沿原 Native 事务，将旧 Desktop common → 新主仓库 common 的 before／after 双状态写入日志并严格复核；新主仓库准备好或资格转移完成，均不等于现场绑定已经改变。产品 b800e503 → db2ae9a4 与受审执行器身份分别认证，回滚／恢复复用既有入口及锁，不任意搜索替代源码。

本章旧日期关于历史 Wind UNKNOWN／`active: null` 的否决，已由用户对历史试验明确丢弃的授权在该窄模式中调整；普通模式仍未知拒绝。账号／模型保全、进程复核及异常留栅栏不变，未提交或未知来源状态不能伪报迁移成功。见[维护、丢弃与恢复合同](research-web-trial-discard.md)。

## 维护边界

本流程只由本机维护者显式执行。业务数据、账号根、模型凭据、常驻安装和活跃 worktree 保持原址；不更换 DSH，不创建新服务，不关闭 iCloud，不用目录别名或整体复制 .git 替换历史。

新主仓库目标为 `/Users/leon/Developer/ResearchWorkbench-main`，从 GitHub 完整克隆。既有 `/Users/leon/Developer/ResearchWorkbench` 不覆盖。新主仓库准备好不等于项目路径、controller source_common 或现有聊天已经切换。

## 真实资格转移

`python -m research_workbench_entrypoint.resident.delivery_transfer preview` 接受 source、destination、task、target；只读检查两个真实仓库身份、原始交付/评审字节、准确 PR/head/merge、原三CI的checkout/tree和完整日志。输出sealed预览。`apply --expected-seal` 重新核对后才登记；`verify` 复查已导入原件和远端证据；`rollback --resident-home` 从目标持久journal恢复，不依赖原source继续存在。

导入沿受管repository.lock及专用import锁；冲突不覆盖，先发布评审再发布交付。目标通过no-overwrite发布，journal记录实际inode、来源摘要与创建归属。回滚与resident重绑定共用supervisor锁，只移除本导入的原inode/原字节；已在使用的source_common、新writer内容和原有相同文件均保护。prepared、部分发布及部分回滚均保留可重入状态，源原件不删。

该入口不伪造PASS，也不因为某个CI显示成功就创建评审。若未完成资格、文件离线、PR不一致或远端超时，明确BLOCKED。指向另一common的真实历史回执只能在重新认证后转移，不能让原controller偷偷搜索任意目录。

回执先以非阻塞、拒绝符号链接方式打开，再检查普通文件和所有权；FIFO不能令维护调用等待外部writer。真实子进程有界测试覆盖该拒绝路径。

## 读取容量与诊断

旧evidence.py、controller.py与host_metadata.py保留原字节及封闭profile。新容量和诊断只位于独立maintenance_evidence版本，由显式维护入口使用；不会自动注入旧controller.pyz。

控制JSON继续限制1 MB。业务index使用独立64 MiB有界读取器，拒绝别名、非普通文件、非本人所有文件、超限和非对象JSON；离线/缺失/不可读/非法分别报错。原封闭升级profile和普通gateway准入不扩权。

真实PR244 job日志为16,527,303字节，故每job展开上限固定20 MB；压缩传输8 MB、总展开64 MB、目录数/路径、完整deflate、CRC、严格UTF-8及真实checkout/tree检查保持。不得截断尾部或只保存通过行。

## 显式失效锁退休

`python -m research_workbench_entrypoint.resident.repository_lock_recovery preview` 只检查准确repository.lock：仓库和路径身份、本人的普通文件、PID确实不存在、两次稳定观察、完整fsck和全部原生Git锁。

`apply --expected-seal --backup-root` 是独立的人工维护动作，不是普通delivery遇锁时的自动fallback。它持独立recovery fence，先备份并实际恢复校验，再次核对PID、nonce、inode、摘要及完整原生锁列表，最后把原锁按原inode归档到retired-locks。已有recovery fence、活PID、未知权限、变化或原生writer都拒绝；没有kill、prune或引用修改。归档和外部备份保留，不能将后续新锁当旧锁恢复覆盖。

## 分批迁移与验证

`python -m research_workbench_entrypoint.resident.source_inventory --source ... --destination ...` 是只读预览。记录每个注册worktree、HEAD、工作状态和引用，所有条目默认protected；READ_TIMEOUT不是对象损坏、缺失注册不是允许删除、clean不是已归并或无占用。预览本身不授予apply能力。

旧库的未提交字节、未推送提交和历史保护锚点须通过正式Git安全备份并实际恢复后，才可迁移对应批次。活跃、离线、别名、缺元数据或归属不明者保持原址。仅在受管恢复、引用完整性、全账号保全及维护租约满足后，更新controller配置和应用项目路径。

当前Wind恢复仍复用原任务的维护租约、生产者闭包和版本化controller迁移；诊断或测试通过不等于其执行依赖已资格认证。旧Host active=null仍阻断服务切换，不清保护标记、不普通重启、不强杀、不重发未知模型请求。

仅服务启动只读取受管账户根中的已有索引和已批准资料。会话原生正文和正式报告质量核验需要独立交接，旧会话与冻结原件继续保留。

主账号原位挂载保留原安装身份与数据目录。接管前复查固定前版的生命周期锁协议，回滚前确认新 Web 已退出。

AlphaDesk 候选将前端锁文件和工作进程随源码交付，产物由固定源码构建。旧普通会话原件纳入回滚备份。
