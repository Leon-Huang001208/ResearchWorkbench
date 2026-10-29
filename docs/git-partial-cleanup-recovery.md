# Git 部分收尾恢复

## 范围

旧控制器会依次删除工作树、分支，最后保存 `cleaned`。中间失败可能留下
`ci_passed`、两个工作树已不存在、部分引用尚存的状态。普通 cleanup 不能将不存在的
工作树解释为新的干净工作树，也不能手工补齐账本布尔字段。

`closeout-recover` 的 `partial_cleanup` 分支只处理**全部受管工作树已退休**之后的引用及
元数据收尾。任何原路径重现、符号链接或分支在另一注册工作树被重新 checkout 都拒绝。
它不恢复或删除仍存在的工作副本，不处理业务维护，不停止 Host、DSH、Office 或 Docker。
旧的“已 cleaned 但历史引用退休导致 finalization pending”路径保持独立。

## 前提与预览

必须有原 pending proof、匹配候选的独立评审、真实通过的 CI、实际合并的 PR、原仓库
身份及完整 v2 恢复点。恢复点必须覆盖每个受管工作树的原 HEAD/branch/path、调用
checkout 和全部保全引用；apply 会再次实际还原验证，不能只信 `restoreVerified` 字段。
本地分支和远端分支只能是原任务 namespace 中的准确提交，且已包含于主线。

```bash
node scripts/git_safety.mjs closeout-recover --project /absolute/RWB \
  --task-id TASK --recovery-backup /absolute/verified-v2-point
```

预览不写文件、不 fetch、不删除引用。该新分支会读取 GitHub PR/引用状态；原历史恢复
预览仍按原本地审计边界运行。结果包含 `kind: partial_cleanup` 和 `previewSha256`。

```bash
node scripts/git_safety.mjs closeout-recover --project /absolute/RWB \
  --task-id TASK --recovery-backup /absolute/verified-v2-point \
  --apply --preview-sha256 EXACT_PREVIEW_SHA
```

## 实际应用和中断

apply 持原仓库锁及备份锁，重新核验 plan、实际恢复、原 CI/评审/分支保护和 Actions
费用资格。原 delivery 按原字节保存，intent 在任何删除前同步到磁盘。
框架验证期间复用进程私有的不可变 Git shim，固定原生 Git、禁用自动维护并过滤
fetch 的 prune 参数；退出成功或失败都恢复原 PATH，不修改全局工具或 PATH。

远端使用 GitHub [`updateRefs`](https://docs.github.com/en/graphql/reference/git#updaterefs)，
每个引用必须仍等于 `beforeOid`，`afterOid` 为零 OID，`force` 固定 false；一项变化即
整批拒绝。本地用原生 Git 引用事务和 expected SHA 条件删除，不使用强推、强删或覆盖。
最后一次远端观察之后重新核对本地路径/注册，避免网络等待期间出现新工作树。

网络请求失败保留未完成状态，同次 apply 不重发。再次显式恢复先观察；已退休引用不
重复提交删除，新提交或重现路径保持原样并拒绝恢复。仓库锁只覆盖采用正式入口的
操作，不声明对任意不合作原生 Git writer 提供系统级排他。

所有引用实际退休之后才能写 Git `cleaned` 阶段记录。资源还须重新验证；引用保全、
原始 proof、intent、恢复点和实际 delivery 在证书提交前再次核对。证书最后提交，
其中绑定实际 delivery 摘要和原始 intent 摘要；原 pending proof 保持原字节。任何
中断仍保留原件和 epoch，不以 fsck 代替引用名称保全或以 Git 阶段完成代替全部收尾。
完成态预览依旧执行 fsck/独评/证书及只读远端观察，不调用会 fetch 的控制器方法。

## 验收边界

离线真实 Git/v2 还原夹具覆盖：新路径/新 checkout、新提交、远端 CAS 竞态、错误
namespace、缺评审、过期 preview、费用拒绝、远端已退休中断、delivery 提交中断、
receipt 新写入、资源复核时引用丢失、FIFO 和完成态对象损坏。

源码及算法 CI 与当前现场 apply 分开；只有实际恢复与全部收尾复核成功才返回
`cleaned`。macOS 本机证据不代表 Windows/Linux 产品已验证。
