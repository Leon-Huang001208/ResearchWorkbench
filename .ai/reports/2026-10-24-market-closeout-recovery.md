# Git pending-finalization 恢复入口

Mac mini/macOS管理平面功能开发。旧market-preview-render任务的worktree/短期分支已由正式控制器移除，末端审计拒绝两个已归档Codex快照引用消失，资源回执仍blocked。备份4993cb74保留；DataHub分支b9b4→eb409为合法FF，不是阻断原因。

## 复现与修复

原status-retry4返回UNRELATED_REF_CHANGED，独立审查确认无现成恢复入口。新增两项RED因恢复函数不存在失败；初次夹具BACKUP_RACE来自未忽略运维日志，修正为与真实RWB一致后取得预期RED，所有输出保留。

默认preview真正只读。apply持repo/backup锁，绑定预览与v2备份仓库键、完整旧锚点和原worktree，实际独立恢复验证后再审计、资源复核及fsck。未知删除、分叉、备份损坏及并发变化拒绝。旧pending证明不改，资源回执原件归档后追加epoch/证书。

Python revalidate只接受cleaned、CI通过、四项Git清理标志全成立的任务；退休目录重现/待处置任务对象拒绝，不重放依赖或卷删除；原ManagedCaches身份、停止状态和20GiB预算保持。Python复核不覆盖旧回执，JS在全部检查后正式完成。

## 验证状态

初步定点及启用资源合同的JS→Python子进程桥接通过。旧88项完整git_safety通过属于资源阶段修补前候选；最终完整Router、独评、三CI和同候选Mac安装待执行，不冒充最终结果。独评已发现并修复默认preview意外fetch、旧cleanup拒绝cleaned、重复恢复早于fsck、PASS日志早于证书完成四项问题。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","diagrams":[],"reason":"仅在既有Git安全管理平面与资源收尾边界追加审计epoch和资源复核阶段，不新增Host/DSH节点、产品HTTP、数据通道或部署权限；会话模型与常驻活动门保持。"} -->

## 安装与平台

没有新依赖、安装入口、schema或后台服务。复用原Node/标准库Python与Docker管理能力；核对原Web锁、setup-web与Bootstrap合同，同候选Mac安装必须通过。Windows/Linux原生交接对应设备。

## 交付与真实现场

最终候选验证/三CI/评审、合并后，才执行正式恢复。历史pending未绑定manifest摘要，归档来源须依据原日志独立核对，兼容性不等于历史来源证明。未恢复2637旧树，未执行真实恢复/部署/页面验收。周报未知状态由其所有者正式处理，组合部署及认证页面另取证。
