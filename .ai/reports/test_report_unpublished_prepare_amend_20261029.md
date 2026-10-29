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

## QUALITY 修订（基于 d4458d30 的实际复现）

新增12个针对性用例，在旧实现11 RED／1控制PASS：snapshot／proof 的删除、损坏及同字节
inode替换均被收养；临时回执损坏或替换被收养，临时回执删除原本由 rename 失败拒绝。
真实 Git fixture 的单父候选通过 `refs/replace` 或 `info/grafts` 投影成二父后，旧入口完整
收养成功；原本已是 root 的 base 写为 shallow marker 也被成功接纳。日志 `quality-red.log`。
另单独复现了已实际恢复后重封印的错误 old-feature anchor 被新 proof 绑定：1 RED，
日志 `quality-backup-red.log`。这些不是仅 mock 的静态推断。

修订使本入口沿用 readOnlyGit 的 NO_REPLACE／NO_LAZY 进程环境，merge 父提交从原始 commit
对象直接提取，拒绝 graft／shallow 文件或对应环境歧义；元数据在网络后复查，原 refs 不删。
文件身份读取使用 NOFOLLOW／descriptor 并前后复查。新 snapshot／proof／临时回执在创建时
绑定预期字节与 inode，最后观察后再次 CAS；新 proof 绑定本轮实际恢复的 manifest／seal
身份与哈希、原提交 anchors、两工作树 tip 与原 master，拒绝重封印错配。

新增合法无关 replacement／引用保全、等待期间 graft／shallow 出现的实际 fixture 正反例。
专项73/73 GREEN（145.32秒）；随后补临时回执被替换／损坏时保留证据的精确归属清理及
断言后，完整原112项＋专项73项联合185/185 PASS，0跳过（178.71秒），日志
`quality-full-final.log`。本轮 Router 本地合同113/113 PASS（6.16秒），文档治理、生成索引、
语法和 diff 检查通过，正式 check 记录 `quality-precommit-check.json`。
父 checkout 源码仍干净，未修改实际任务、远端或全局 runtime。SPEC／QUALITY 独立复评由
主任务在新候选上重新执行；本地测试通过不能冒充评审或生产恢复通过。

## CI 登记及完整七文件闭包

发布前确认原 Project Constraints Git safety step 只显式运行 `git_safety.test.mjs` 与
`iteration_closeout.test.mjs`，没有间接包含新 amend 文件。该 SAME step 现追加
`git_safety_amend_prepared.test.mjs`，保留原两文件；job、runner、Node20、10分钟上限、
触发频率与依赖完全不变。功能源码及测试内容与已独评 d585e6f5 保持相同字节。

本机固定Node24的完整同命令三文件实际188/188 PASS，0失败／错误／跳过，177.636秒，
JUnit及原始输出见 `logs/unpublished-prepare-amend-20261029-f66ce16a/ci-wiring/`。
此前185项包含Git安全112＋新73，但未包含原iteration_closeout三项，不是原CI全部门。
预算说明按本次188项实测记录；本机结果不替代Ubuntu／Node20及最终候选CI。

完整七文件 Router 选取L4，新增 CI／critical-chain 所需本地门均已执行：policy74、receipt23、
incremental skill5、platform／delivery15、architecture84、原full Router113全部通过，
文档治理与Python生成索引通过。协议 smoke 先收集81个nodeID，再按20／20／20／20／1
分五批执行，81/81 PASS，JUnit精确并集，无遗漏或异步skip，合计2.454秒。

协议使用主任务批准的既有release Python与UV缓存pytest／pytest_asyncio，源码cwd优先、
`-B`、显式异步插件及`--confcutdir=tests/research_web`，没有安装依赖。任务局部Seatbelt
禁止网络和日志私有根外写入，native TCP负例确认内核拒绝；真实keyring／进程／网络
哨兵全为0，数据／日志／缓存／空配置仅位于任务logs。第一次收集因未重定向
OBJECT_STORAGE_PATH被沙箱拒绝（无源码写入）；补全该环境及PDF路径后重新收集与执行，
失败原件与成功证据分别保留。没有放宽测试或产品边界。

仅feature的workflow、预算文档和本报告修改；integration、受管交付回执及远端未操作。
后续新候选收养由主任务使用正式入口完成，并重新绑定SPEC／CI；此前候选验收不冒充新候选。
