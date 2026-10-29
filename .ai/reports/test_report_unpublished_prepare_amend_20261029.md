# 未发布 prepared 候选的原位修订（2026-10-29）

任务：`unpublished-prepare-amend-20261029-f66ce16a`。宿主 macOS，Git 工具源码修复，
独立 worktree；本任务没有执行实际阻塞交付的 receipt 修订、push、PR、merge、部署或全局配置变更。

## 问题与变更

普通 prepare 仅允许 started／remote_moved／ci_passed，原 replace-prepared 需要删除重建，
RWB 已主动拒绝该路径。原未发布刷新还要求 master 改变，无法收养同基线的生成索引修复。

新增 `delivery --prepare --amend-prepared`，只收养原 integration 工作树中已正常提交的
二父 merge（第一父=原候选，第二父=新 feature）。必须 prepared、显式 null 发布身份、
无 CI／发布／合并证据、原资源账本 inode、干净且明确空闲的原工作树／分支、正确祖先链。
GitHub 只读观察 master、任务分支／PR、Actions 和可见提交的 checks/status；未知 HTTP
或权限错误拒绝，仅显式提交404在已验证仓库权限后认作当前不可见。

仓库／integration／任务锁贯穿网络观察、真实 v2 恢复校验、私有历史和最终 CAS。
原 refs 不移动，旧 feature／候选在 sealed backup 的 preservation refs 中保全；旧 receipt
与 proof 追加到私有 epoch。成功后旧 verification／CI／回执 review 失效，原计数／历史保留；
旧独评文件保持但不再匹配新候选。重复调用重新验证同 epoch，下一次 descendant 可追加。
失败在 adoption 前不写原 receipt，不删除工作资源；`--replace-prepared` 仍拒绝。

## 验证

- RED：Node24 `--test tests/javascript/git_safety_amend_prepared.test.mjs`；两项预期失败，
  一项落入禁止重建的共享 prepare，另一项 CLI_OPTION_INVALID。日志 `logs/unpublished-prepare-amend-20261029-f66ce16a/red.log`。
- 初始 GREEN：2/2；扩展第一轮 41/41，真实独立备份恢复、发布歧义、工作树身份／占用、
  祖先遗漏、远端与回执漂移、中断、重复／后续采用、计数隔离及锁保护均通过。
- 完整 Git safety：此基线原112项＋新增42项，共154/154通过，0跳过，196.04秒；
  没有删除或减少原测试。日志 `logs/unpublished-prepare-amend-20261029-f66ce16a/git-safety-full.log`。
- 最后仅补强备份锁覆盖最终网络观察／CAS后，专用42/42再次通过，0跳过，62.78秒；
  日志 `logs/unpublished-prepare-amend-20261029-f66ce16a/focused-final.log`。
- Router L4 本地闭包：原架构／文档／Actions／跨平台合同测试113/113通过（5.87秒）。
- `node scripts/check_documentation_governance.mjs --project .`：通过，无 violations。
- `python3.12 scripts/generate_py_file_index.py --check`：通过；无 Python 源变更，无需更新生成索引。
- 父 checkout `/Users/leon/Developer/ResearchWorkbench-main` 的 `git status --porcelain=v1`
  在开始和实现后均空；仅当前 worktree 修改指定源码、专用测试、工作流文档和本报告。
  最终 `parent-clean.json` 固定 parent HEAD=270644bf1513e65c50859fb2e3baec6ce06ccfef，porcelain为空。

所有 JS 测试使用固定 Node24；没有改现有 immutable shim。正式 RWB 入口继续使用
`/usr/local/bin/node`。fixture Git 固定 `/usr/bin/git` 且 gc.auto=0／maintenance.auto=false，
临时资源以本任务ID标识且只删除本 fixture 拥有的临时目录，无新增依赖。

## 未验证项与风险

实际 GitHub／阻塞任务恢复为 NOT_RUN；未发布 SHA 的404、HTTP错误和本地并发由离线 HTTP
夹具验证，不能替代现场恢复。Router 选择的 Project Constraints CI 未在本子任务执行，
集成／独立评审由主任务完成，因此本报告不宣称 mergeReady、生产恢复或跨平台验收。
仅接纳二父直接合并；在 merge 后额外提交的候选、历史不明或账本缺失均明确拒绝。
adoption 是回执原子 rename 的提交点；若此后日志或资源登记失败，重试必须重新核验已采用
epoch，不回退已提交回执或伪造未执行状态。

## SPEC 修订（基于 e1c8f403 的独立复现）

三项评审逐项核实后，在旧实现新增11个测试全部RED：未知 checkRuns／ciResult／rollback
workflowRun 被接纳；最终网络等待中仓库锁／备份锁被移除或替换后先写回执再报错；
旧 snapshot／proof／backup／history 损坏后仍能追加新 descendant。
日志 `logs/unpublished-prepare-amend-20261029-f66ce16a/spec-red.log`，11失败／0通过。

修订使用 schema1 精确允许字段与嵌套验证；仓库锁从实际取得的 inode／nonce 派生闭包，
备份锁以兼容可选回调参数传出当次 inode 的校验闭包。最终 CAS 前验证两者，拒绝写后才报错。
每次修订和重放逐个校验所有 epoch 的 snapshot 哈希、proof 精确字节、历史前缀、immutable
身份字段、sealed manifest 和旧提交 preservation anchors；持备份锁实际恢复全部历史，
不是只核对最新 epoch 或仅在 replay 验证。备份模块 scope 扩展已经主任务明确授权。

新增备份锁无参回调兼容、闭包过期／漂移、两次有效修订后最早 epoch 损坏的测试。
专项第一轮56/56 GREEN（88.63秒）；补最早 epoch 字节损坏用例后，最终原112项＋专用57项
联合169/169 PASS，0跳过（183.00秒），日志 `spec-full-final.log`。本轮 Router 本地合同113/113
PASS（5.49秒），两份 mjs 语法检查、文档治理、Python生成索引及 diff 检查通过。
最终五文件 changed-set plan 为 `spec-verification-plan.json`，仍为L4；Project Constraints
CI 未执行，mergeReady 不声明通过。正式 `/usr/local/bin/node ... check` 留档于
`spec-precommit-check.json`；父 checkout 源码保持干净。没有修改实际阻塞任务或全局 runtime。
