# RWB 存储留存与可再生产物回收

宿主为 macOS；任务类型是交付控制面规则与离线工具变更。未调用模型、供应商或 Docker，未修改常驻服务、业务数据、凭据或生产恢复档案。基线为 `master 911dfee9de3648cefe36db6aa1ab054bb72b9159`，本任务使用受管隔离工作树。

## 问题与处置

旧规则把测试临时根拖到 PR 合并后才清理，`preserve_evidence` 还会逐文件复制整个 `logs/` 到长期证据区。它保护了失败与恢复证据，也让成功夹具和重复输出持续占盘。2026-10-31 只读盘点发现 `/private/var/tmp` 约 8.9 GiB，其中角色研究 v13/v14 的旧 pytest 根约 6.5 GiB。用户分别授权的精确清单下，v13 删除 21/53 份、约 3644.7 MiB 逻辑文件，v14 删除 14/18 份、约 2993.2 MiB；剩余分别约 4.0 MiB 与 1.3 MiB，硬链接检查拦截后原位保留。旧 PR245 c814 身份绑定根约 180 MiB 也已清理。每份外部 result/JUnit/stdout/stderr 或旧 PR245 原始日志在删除前复核；清理回执保持在各任务私有 `logs/`，并行 Docker 写入期间不把 `du` 累计冒充宿主物理回收。

## 新合同

- 每批在运行前登记任务、候选HEAD、批次/最多20个用例、根设备/inode和nonce；同任务同时只有一个活动根，前批回收后才可建下一批。`run`自己执行pytest并冻结真实退出码与JUnit/stdout/stderr哈希；仅退出码0、逐用例无失败、根外证据同批、无占用且硬链接都在根内时提前隔离删除。隔离后和中断重入前重新核对每个路径的类型、inode、大小与内容hash；只读目录在隔离后最小权限修复。运行期每秒监测512MiB根、64MiB根外输出和3GiB空间，超限终止并等待自己启动的pytest进程组，流式限量记录失败回执。exact模式在运行前后均核对干净HEAD并固定cwd；WIP模式显式标记`exactCheckout=false`，只允许夹具回收，不认证最终候选或自动丢弃日志。
- 新任务资源ledger带`selective-v1`，最终归档必须有覆盖所有现存文件的`logs/evidence-retention.json`。任务全部工作树的保留集合计最多128MiB；自动丢弃只接受同任务已退休exact批次回执明确列出的stdout/stderr，回执、实际退出码、冻结用例、JUnit与输出hash必须互相匹配。复制前冻结各源文件哈希，删源前重验，归档后以相对路径重放批次语义。最终/失败/未知回执、下载副本及恢复材料不能借别批PASS丢弃。漏列、证据变更或超限都不删除源文件。既有ledger无模式时保持`legacy-full`，历史证据不被升级代码静默删除。
- Git 工作树、Docker 缓存/镜像、生产恢复和业务资料仍各走已有受管收尾与权限；测试临时根的即时回收不改变 PR、CI、部署或模型质量状态。

## 验证记录与缺口

- 初版五个核心用例因模块不存在真实RED、随后5/5GREEN；归档选择四例因缺`policy`参数真实RED、随后4/4GREEN。独立Python审查指出根内证据、伪造JUnit汇总、任意成功证明删最终日志、隔离/重入后新增文件四项P1，及并发/容量/归档预算P2；均以反例驱动修正。WIP源码曾按20/1/20/5四批运行46项，测试根逐批回收；这份WIP证据未被当成最终验收。冻结源码提交`22bd700fa343e9dd2c8a032905b3a2bcf6097f63`又以exact模式按20/1/20/5真实运行46项，JUnit合计46通过、0失败、0错误、0跳过，四个根均退休；manifest SHA-256 `ed48725d783a75969007ee6f597962cf4dead7254506c5bd7b7f5a6e6c2926ed`。同候选协议81项按20/20/20/20/1运行，所有批次通过且credential boundary报告真实Keychain调用0。原始JUnit、stdout/stderr和lease保存在任务私有`logs/storage-retention-tests/`。
- 完整变更集Router为L4；33文件Project Constraints为0违规，文档治理、Python索引和架构一致性检查均通过。Archify图08通过9项showcase、0错误/警告，四视口截图无溢出，实际看过1440浅色及2048深色。L1验证策略/回执/Skill/平台/架构Node合同及L4本地组合均实际退出0。Ruff、isort、`git diff --check`通过；Black对新脚本、新测试和修改的资源模块通过，既有`test_iteration_resources.py`的master原版单独做Black检查亦会报would-reformat，未借本任务大面积改写旧格式。独立Python审查在最近的源码版未发现P1/P2；最终文档提交后的Router及同候选GitHub CI、Mac干净安装仍待执行。现有缓存中的mypy因缺`librt`无法启动，本轮不安装新包，类型检查记为NOT_RUN。历史task archive的期限性轮转未在本次自动删除范围；现有未知或未归并任务需要逐项身份与恢复引用审计。Windows/Linux产品门保持`NOT_RUN`，不能从Mac单测推定。
- 后续精确归属：特性提交`13a1ae58fc0a24f26f8fa0387ad150c3aae7b19a`与受管集成提交`5dc24828a749852ecb6c7c5a5ac8670b5c611afa`的树同为`fa49985ec09b0a63913b969dee2ada41e55a04dd`；两处干净工作树分别以自己的HEAD跑过46/46局部用例和81/81协议用例，均零失败/错误，五批协议的真实Keychain调用均为0。集成候选的本地回执位于`logs/storage-retention-integration/`，局部/协议manifest SHA-256分别为`82a340e1cbc97404a06cf25a9c3fa549d67157ca5c2287a90ea7d870059f0b54`与`50093f912775d51925827bf3788b334b1b65cd4421837d56a5497b5b0e07e830`；该归属不把随后文档修订生成的新提交说成已跑过同SHA测试。最终PR合成checkout、Project Constraints CI及Mac干净安装仍须用最终SHA另证。

## 2026-11-01 prepared-amend 兼容回归

为修正上段验收归属，特性分支新增了仅文档提交，旧prepared回执仍固定`5dc24828`、尚无CI/PR。项目入口按设计拒绝`--replace-prepared`；原`--amend-prepared`在备份前返回`UNPUBLISHED_STATE_INVALID`，因为共享控制器的回执多了`mergeSourceCommit=旧feature`而安全入口允许字段未同步。旧回执未手改，旧集成的94份原始日志经hash验证归档到仍受管的feature日志，四份可再生依赖/空目录由项目资源入口清理。原integration按安全合同继续提交了第一父链为`5dc24828`、第二父为新feature的合并提交，保留原refs与候选身份。

窄修复只在严格回执允许字段中加入`mergeSourceCommit`，要求它精确等于旧`featureCommit`，正式收养时推进到新feature。新增合法/错绑两例先真实RED（1失败、1通过），修复后2/2GREEN，完整`git_safety_amend_prepared.test.mjs` 106/106通过（约274.8秒）；缺字段旧回执、恶意扩权字段和恢复失败合同仍在原完整集合。安全入口再次收养、备份恢复与最终同候选CI仍未运行，本段不把单测说成受管交付成功。

<!-- architecture-review {"group":"verification-workflow","structure":"changed","reason":"新任务证据收尾由全量logs复制改为显式选择并限制保留字节；新增本机测试临时根的身份登记、PASS证据封存和提前安全回收。08图源新增即时回收与选择性归档节点，并连接实际回执门。","diagrams":["08-iteration-docs"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增回收只操作登记过的本机pytest临时根与交付日志清单；Docker的容器、镜像、业务卷、BuildKit锁与预算均未变，Native/Host/DSH产品部署拓扑保持由各自任务管理。","diagrams":[]} -->
