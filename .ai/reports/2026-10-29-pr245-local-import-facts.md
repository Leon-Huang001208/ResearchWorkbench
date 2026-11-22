# PR245 单次 runtime 导入事实复用：仅本地候选

宿主 macOS，任务为既有 Host 性能改进；验证范围仅本地离线 Python 定点，不是 Windows／Linux 原生验收。源基线为 `4b38e52315f32b577ec2115b6fa611e0bd32076e`。受管 `git_safety.mjs check` 实测 fsck PASS、无锁后开始修改。不提交、不发布、不修改 repairAttempts=3，不新增依赖或 CI timeout。

## 问题与设计

4b38 的 Checks 在 45 分钟被取消，没有 pytest 终汇总或 assertion traceback。API 213 例范围有 180 组初始化／1080 个 seed 事件；可见启动窗口合计 1909.474688 秒，占该范围 2161.770997 秒的 88.33%。这支持重复初始化累积，不证明 Linux 的 CPU／IO 分解或单个 Native 调用故障。

`runtime_identity` 原先 build policy 后，verify 内再次 build。现在仅这对调用共享局部不可变 AST 导入事实；每遍仍枚举当前模块、读取实际字节、重新分类与组装 policy，随后核验当前 loaded objects、search origins、stdlib 与 optional imports。事实键含 name／package／完整源码 bytes；不依赖 size、mtime 或摘要相等。局部字典在 finally 清空，不跨 runtime、Catalog、账户或测试。没有 fixture clone、seed／save 次数调整或授权缓存；异常仍走原日志与失败关闭路径。

## 已执行证据

日志根：`logs/pr245-local-import-facts/`（控制 checkout）。`baseline-frozen.json` 保留两原始源码与之前六源码 hash、完整 oracle／profile／异常证据；不覆盖 4b38 原件。

- RED：真实两次 runtime 调用，`idna/__init__.py` 被解析 4 次，目标为 2；`red.log` 保存 `assert 4 == 2`。
- 初次 GREEN：新增 11 例通过；测试空 match 警告已删除，最终复验另记日志。
- 原 import policy 守卫：13 passed。
- 原 dependency closure 与两个 runtime identity 定点：14 passed。
- 每进程最多 14 例；固定现有 Python 3.12 与批准工具缓存，独占 opaque `/private/var/tmp` 根，先登记 UID／dev／inode／PID／candidate／argv，启动空间至少 3 GiB，运行低于 2 GiB 只终止本进程。外层 Seatbelt deny network*，使用原 function-scope 内存凭据 fixture，不访问实际 Keychain 或设置，不启服务／模型／供应商请求。

新增测试覆盖同 bytes 两遍仍读／枚举、同 size 恢复 mtime、当前模块新增／删除、syntax／dynamic 变化、relative package 上下文、loaded／search shadow、异常清理及跨 runtime 不共享。

## 证据界限与当前状态

本轮未再构造 Catalog 或执行性能实验；没有声称本候选实际测得 6／281 次。`catalog.py`／seed 初始化循环未修改，原 4b38 profile 的六次 fresh／281 save 证据保留为基线。helper 源码与 guard／冻结资源摘要将合理变化，不能宣称旧、新完整 oracle 或冻结包全字节相同；新增 runtime 测试只比较同一候选的两次身份相等。

原完整验收现态仍为 17 门；779 passed／1 skipped 是旧本地范围证据。4b38 Constraints／Mac Bootstrap 成功、Checks 超时取消；mypy 既有 17 项（本 PR 4 项）不在此次范围。Task5 的 19.68 GB 恢复快照及受保护资源状态不由本候选改变。完整 CI、Linux 成本与 45 分钟完成性仍未验证；没有 CI 已修、已合并或可发布结论。后续由 Root 对冻结 diff 安排独立 SPEC 与 QUALITY。

## SPEC／QUALITY 后的 P3 测试加强

独立 SPEC 与 QUALITY 对原五文件局部候选均 Approved；原 `frozen-review.json`／`minimal.patch` 保留，不覆盖历史审查身份。随后仅修改新测试及本报告，两个产品源 SHA 保持不变。

loaded 分支在真实 import 之前通过独立 monkeypatch context 登记 sys.modules 原 absent／对象状态，context 退出后断言恢复原对象身份。两种 loaded 状态与 search 分支均显式参数化重复两次，避免仅靠 pytest 重复 argv（实际会去重）冒称重复执行。relative fixture 同时含 lazy optional 与 lazy dynamic import；相同 facts 的第二遍断言结果相同且 extractor 不再调用，另 package 上下文独立计算。

`p3-final.log` 为同进程 15 passed，`p3-reverse.log` 为 shadow→relative→基础复用逆序 8 passed；每进程最多 15 例，均无 pytest warnings summary。原 13／14 相同产品源门没有重复执行。早期 `p3-repeat`／`p3-repeat-kept` 各只收集 5 例，日志完整保留，不能计作重复执行证据。三格式检查另存 `p3-static-results.json`。普通 Catalog 新候选构造仅准备方案，尚未执行，不据此宣称新候选 6／281／56 实测或性能收益。

## Root 授权的一次 Catalog 观察及交付元数据

前节“仅准备”是执行前记录，原 v2 产品审查不覆盖随后元数据变动。Root 审过固定执行清单后亲自执行唯一 Catalog，回执 exit=0、无监督停止：`single-catalog-receipt.json` 指向 `/private/var/tmp/rwb-single-catalog-8b6e1c740056ddda17708817`，原始 owner／stdout／summary／oracle 均保留。实际 constructor_attempts=1，seed=6、runtime_identity=6、save=281、validate=56；stable oracle 字段差异 0，源码前后 SHA 一致，新 guard 摘要匹配本候选 helper，六次本候选 policy 输出一致。旧 oracle 未保存独立 ordered policy，跨候选该项仍 NOT_AVAILABLE，不以 stable oracle 全等冒充冻结资源全字节相同。

该次 wall=3.2827287919353694 秒、process CPU=3.1330430000000002 秒，带 count-only wrappers，没有 cProfile；原普通样本无这些 wrapper，不能直接计算统计加速。56 次凭据预检被 fail 边界拒绝，实际 Keychain 操作 0；不能称零尝试或完整 Host 内存凭据端到端验收。

本轮只将新 15 例模块登记原 Checks Python 显式清单，同步 Actions 增量预算、能力架构测试索引与 README 不变复核，按原脚本生成 Python 文件索引；没有新增 job／runner／timeout／依赖／触发或发 CI。旧完整三 CI 与 mypy 状态不变，repairAttempts=3 不重置；产品两源码及新测试保持 v2 SHA，不再构造或跑新测试套件。目标文档／索引／结构完整性检查及元数据冻结由本轮日志另证，后续本地 commit／完整 Router 由 Root 处理，不自动远端重试。

目标结构检查首轮真实失败：缺能力／verification-workflow 组文档、结构决策及 atlas 派生 index；`metadata-constraints.log`／`metadata-architecture.log` 保留原 FAIL。按原规则补齐对应文档事实和下面两个不变结构决策，由原生成器更新派生页；不改校验规则或图拓扑。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"同次runtime内的不可变导入语法事实仅省重复解析，实际源码读取、当前导入来源与loaded对象复核、六次freshness和281保存语义保持；新测试登记既有能力索引，不新增API、权限、服务、图节点或唯一DSH以外引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一Python显式清单只追加15例导入事实回归，原job、runner、依赖、触发、45分钟时限、三次修补预算与交付门不变；本地一次Catalog观察不代替完整CI或模型比较，原验证流程图拓扑仍准确。","diagrams":[]} -->
