# 共享阻断恢复与非 iCloud 主仓库准备

> 任务记录，不是业务部署完成证明。macOS 运维修复及源仓库分批迁移；Windows/Linux产品未验。

## 授权与边界

用户批准恢复资格链、受控恢复及分批迁移至Developer/ResearchWorkbench-main。现有Developer/ResearchWorkbench不覆盖；旧目录、所有工作树、业务/账号根及凭据保留。真实模型预算$1仍未使用；本任务没有调用模型或厂商。

## 已执行并取得证据

- 交付208份及评审133份均已完成本地化。Finder明确iCloud满额且主仓库位于桌面同步域；仅对必要元数据保留下载，未购买空间/关闭同步/删云端数据。
- 新目标从GitHub完整克隆，非浅克隆、master干净、fsck通过。只准备新目标，未变更Codex项目或常驻source_common。
- 原仓库fsck通过。PID62030失效受管锁经显式seal预览、独立recovery fence、完整原生锁检查、外部备份与实际恢复比对后，按原inode归档；原始字节sha256 fa5d14020638d6ac37d86b311a76e2b3fd4813561d7745e1978884f7816b8caf。实际后验无原生锁/无受管仓库锁，无业务或未知PID终止、无Git引用修改。
- 旧锁备份：~/.codex/backups/rwb-repository-lock-recovery-20261028/5670ffa2a15c4762a6c91406cb825647。对应结果及恢复证据在logs/recovery-unblock/old-lock-retirement-result.json。
- 原控制器缺master回执，是因为PR244的真实ci_passed回执及PASS评审在独立checkout .codex/checkouts/report-production-workspace-20261027，原controller只查旧common。已用真实PR、merge/head、三CI最新run/checkout/tree和完整日志重新资格认证，不伪造PASS。
- 新主仓库已完成上述原件的跨common登记，journal为verified。复制原始delivery/review字节与摘要，冲突不覆盖。尚未宣称原controller已使用新common。
- 已盘点全部165条worktree注册，首次元数据复原后139项工作状态可读、16项READ_TIMEOUT、8项missing_or_alias、2项缺gitdir；全部仍protected，clean不等于可删。旧primary最初READ_TIMEOUT、backup返回COMMAND_FAILED；下述现场保全进展已替代primary的旧状态，其他工作树未提交字节仍未因此认证。

## 代码与测试

新增delivery_transfer维护入口（preview/apply/verify/rollback）、只读source_inventory及独立显式repository_lock_recovery；原普通delivery不自动遇锁删除。与既有GitSafety使用相同repository.lock协议，回滚持supervisor锁，精确inode/摘要归属、no-overwrite发布、独立恢复fence及崩溃重入覆盖。

真实PR244完整job为16,527,303字节，原16 MB读门拒绝。保留压缩8 MB、总展开64 MB、CRC、完整deflate、UTF8和checkout/tree校验，只将单job有界门改20 MB。原zip sha981be7c7f7c6d4fb5109148ad47ac612cb099e3903ceaccd48cbae856b905b72，完整job sha ddd6e7384ce9b9e6b68b5839a6d22236cf1240149252809036f043a753ecfde4，已实际完整读回。

控制JSON1 MB与业务index64 MiB分离，离线/缺失/不可读/非法分类。实际业务index约22 MB、69会话已只读解析，无回写。gateway既有封闭profile默认准入不扩权。

独立评审拦住并已修复no-overwrite竞态、回滚rebind锁/新writer保护、prepared中断/部分回滚、唯一staging、原始source消失后的回滚、PR绑定、恢复并发fence及完整native锁检查。维护闭包141项通过；后续最终闭包/Router/CI仍需绑定最终候选，不把中间通过当成发布验收。

## 仍未完成

旧Host b800e503 active=null，Wind清理未知，未普通重启、清保护标记或替换controller.pyz。原受控恢复任务仍在资格认证；其controller_migration.apply当前明确diagnostic-only，不能把源码inspect当作执行器已就绪。

新主库只是准备好，尚未全量导入未推送提交/未提交字节、未切165项worktree、未更新项目入口/常驻source_common、未清理旧目录。业务PR246仍单独保留真实模型、Native/Docker与部署验收门。Shared恢复不替代业务质量验收。


## 结构复核

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "新增维护入口只预览/转移真实资格、盘点源仓库及显式归档已死owner锁；业务index与控制metadata分别有界。新主仓库仅准备，原Host/DSH、安装根、端口、账号根和原恢复事务保持，未切服务。", "diagrams": []} -->
<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "原Checks同一Python步骤追加三个stdlib维护合同，无runner/job/超时/依赖变化；实际原始CI日志有界完整读取，不用CI绿替代现场或业务验收。", "diagrams": []} -->


## 冻结旧路径的回归修复

相邻回归拦住了修改旧evidence.py/controller.py/host_metadata.py导致旧封闭profile摘要失效。已将三文件原样恢复至基线，仅在独立maintenance_evidence模块提供20 MB完整job及64 MiB业务reader，异常类型复用原UpdateBlocked，不改普通兼容包络。新版本通过显式维护资格接口调用，旧pyz并未升级。旧容量拒绝测试仍保留16 MB；新容量在新generation单独测试，不删除旧断言。


## 当前候选验证更新

旧三文件字节恢复后，维护测试144通过；专用安装环境对真实隔离冻结恢复包27项全部通过。相邻大闭包3052通过（无测试跳过/放宽原断言）。新CLI拒绝秘密形状未知参数且不回显，以真实子进程验证。专项Ruff/Black检查通过。

该专用环境按Web锁安装，项目使用editable --no-deps仅用于隔离子进程namespace；不等于全量非Web项目依赖完整，pip check报告未安装的legacy非Web依赖，不伪称product_ready。新环境不修改MVP任务的venv。

最终代码冻结后的维护/旧resident/协议闭包225项通过（5.70秒，1条既有弃用警告）；Router所选Node合同230项通过（6.34秒），四个维护模块mypy通过，相关Ruff及Python索引核验通过。3052项相邻闭包发生在最终CLI微调前，归属保留在candidate-frozen-final.log，不冒充最终提交的全量证据；该CLI微调已由最终225项再次覆盖。原三CI及Mac干净安装仍等待最终候选发布后取证。

实际原件已在旧common与新主仓库分别登记为verified，来源与摘要保留；旧不可变controller未更新，仍可能因旧日志读取器报错，现场Wind状态仍未知。新主库尚未作为Codex项目或常驻source_common启用。

最终独评再次拦住delivery_transfer共享reader尚未添加O_NONBLOCK；真实FIFO子进程先复现3秒超时，补齐非阻塞普通文件拒绝后226项通过（5.33秒）。原失败保留fifo-red.log。之前225项及汇总仅归属当时提交，不声明是最终发布验收。Atlas同时登记index和api-atlas两个生成物，不能遗漏后者形成脏候选。

## 现场保全进展（2026-10-29）

针对最初4299个离线tracked文件约143MB，先申请下载；发现低空间下再次回收后，使用Finder对核对容量的源码目录以及HEAD/index/config/packed-refs设置保留下载。最终6179个tracked文件全部本地化，status实测0.79秒完成；75条工作状态记录不发布。旧primary HEAD/master为bb40c791，和GitHub主线分别记录，不覆盖该现场。

正式Git安全入口成功生成v2恢复点 `~/.codex/backups/rwb-git-safety/8a3c7d7f-1e89-4dfa-93d5-97b6c82e597c`：restoreVerified=true、fsck=PASS，222个引用、6179个tracked、75个untracked及分开的index/staged/unstaged均实际恢复校验。Git报告的164个worktree含primary，不包含两个HEAD/gitdir均缺失的注册。补充控制元数据归档在 `~/.codex/backups/rwb-source-migration/c874c9bc95d2402e8449cce5b9f5b802`，持相同managed锁、双次源清单比对和实际临时恢复，覆盖2111项及全部165条注册；archive sha256 430790009b0ff8c94fa25b838a937334e2e1e2ac539c17191f35e5e149fcbb08。它不认证其他worktree的工作副本内容，两个损坏注册继续保护。

只对本任务已完成的五个pytest根做归档、实际恢复/哈希复核及占用重查后退休10843项，逻辑字节3531598388；117项外部符号链接/特殊测试夹具保留，备份在 `~/.codex/backups/rwb-shared-maintenance-tests-20261029`。剩余磁盘约8.8GiB，是当时观测，不保证未来容量。未删除其他任务、服务或业务数据。

初候选e24420b6的Mac安装与Constraints已通过，实际checkout33a34112547165502932812fde30fb203e0a7e79的父提交和tree已本地核实。CI期间PR247合入使主线前进至07220cd2，必须刷新基线并给新候选重新绑定评审/全changed-set Router/原三CI；不得把旧候选通过提升给新候选。旧常驻仍b800e503/active=null，未切换服务或source_common；受控恢复执行器缺口保持。
