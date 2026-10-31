# 共享部署资格恢复与源仓库迁移

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
