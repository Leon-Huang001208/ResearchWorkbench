# PR245 pack import 纯语法缓存性能修复

宿主为 macOS，任务类型为既有 Research Web Host 性能修复；本任务验收范围是本地离线 Python 定点、静态格式及项目完整性门，不是 Windows／Linux 原生验收、常驻部署或模型质量验收。feature worktree 从 `a82bba2cd0e1ed22a4caa75214c411a0fb9d78e6` 正常 `--ff-only` 到已评审集成基线 `29e86d18c60f3c2aaabdad33357a77973ac11212` 后开始。受管 Git `check` 实测 `fsck=PASS`、无原生锁；未 push、prepare、publish、重置 repairAttempts、创建新任务或发起 CI。

## 根因与最小改动

现有修复已让同一次 `runtime_identity` 的 build／verify 共享局部 AST facts，但一次真实 Catalog 仍调用 6 次 `runtime_identity`，相同固定依赖源码在同一进程被重复解析。基线 cProfile 的调用数为：6 次 runtime identity、12 次 policy build、18 次 module inventory、270 次 `_import_facts`。这是真实本机热点，不把 `packages_distributions` 的另一个热点做跨目录缓存，因为那会削弱当前安装态 freshness。

`pack_import_policy.py` 新增只保存不可变语法 facts 的进程内 LRU：最多 64 项，每个源码最多 1 MiB。键绑定每遍重新读取的完整源码 bytes、module、package、绝对文件路径（安装根）、当前 `ast.parse` 对象及 Python implementation/cache-tag/version；大源码直接 fresh parse。缓存值只有 `(tuple(imports), dynamic_bool)`，不保存 runtime identity、完整 policy、依赖身份、授权、验证 PASS、loaded/search 结果或凭据。

每次调用仍重新执行：依赖文件与 metadata 的 no-follow 读取、权限／inode／size／mtime／ctime／nlink 竞态核验、全部文件 hash（含 pyc）、模块枚举、源码读取、policy 组装、loaded object／search origin／stdlib／optional import 核验。源码同尺寸且恢复 mtime、import 字节、module/package、安装根或 parser identity 变化均不命中；模块新增／删除仍由当前 inventory 和完整依赖 closure 发现。

## RED／GREEN 与语义证据

全部 pytest 进程使用固定 `/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python`、既有 uv pytest cache、显式 `--confcutdir=tests/research_web`、独立 opaque `/private/var/tmp` 根、临时 HOME、`PYTHONDONTWRITEBYTECODE=1`、`PIP_NO_INDEX=1` 和外层 Seatbelt `deny network*`。每进程最多 17 个 case；原 `test_api.isolated_keyring` function-scope memory vault 保持，不读取真实 Keychain／SecretSource，不启动服务、供应商、Office 或模型。每次开始可用空间大于 3 GiB，未触发低于 2 GiB 的自有进程停止门。

- RED：`test_fresh_runtime_maps_reuse_only_same_root_syntax_facts` 观察到当前字节读取 2 次、模块枚举 2 次、AST parse 2 次，目标为 1；`logs/pr245-packs-performance-20261030/red.log` 保存 `assert 2 == 1`。
- GREEN：同一用例 1 passed；两个 fresh map 仍分别保存 facts，读取／枚举次数不减，parse 为 1。
- 新增失效测试覆盖完整 bytes、同尺寸恢复 mtime、绝对根和 parser 对象；既有测试继续覆盖 package context、当前模块新增／删除、invalid syntax、dynamic import、loaded/search shadow、异常清理与跨 runtime 返回等价。
- `test_pack_import_facts.py`：17 passed。
- 原 import policy guard：13 passed。
- 原 dependency closure＋runtime identity：14 passed、1 skipped；skip 为原环境条件，不改写为 PASS。
- ordered AST oracle：2 passed；危险源码 marker 未执行，当前源码变化仍拒绝。
- `ruff check`、`isort --check-only`、`black --check` 对两个 Python changed files 均 PASS，复用现有工具缓存且未安装依赖。

原语义调用数在 after profile 中保持：6 次 `runtime_identity`、12 次 `build_policy`、18 次 `module_files`、6 次 `verify_policy`、56 次 `check`、56 次 `publish` 和 281 次 `save`。没有减少 freshness、验证或保存 checkpoint。

## 性能观测

基线和候选均运行同一个真实 `test_complete_ordered_validation_oracle_and_changed_source`，每次仅 1 个 case，使用 stdlib `cProfile` 与 `/usr/bin/time`；完整 profile 与排序结果位于 `logs/pr245-packs-performance-20261030/`。

| 指标 | 基线 29e86d18 | 本候选 | 观测差异 |
| --- | ---: | ---: | ---: |
| cProfile total | 11.766500s | 9.517778s | -2.248722s |
| wall | 11.96s | 9.64s | -2.32s |
| `runtime_identity` cumulative | 2.032377s | 1.188100s | -0.844277s |
| `build_policy` cumulative | 1.153541s | 0.317266s | -0.836275s |
| `_import_facts` cumulative | 0.954045s | 0.140937s | -0.813108s |
| 实际 AST parse | 270 | 45 | -225 |

这是一次本机受控 profile，不是统计 benchmark，也不保证 Linux runner、完整 7,874 个 main scope 或 45 分钟 CI 一定通过。PR245 run `40936193000` 的超时与缺少两 worker final result 保持原失败归属；CI252 的约 35 分钟通过只属于其原候选，不认证本候选。

## 源码身份

| 文件 | 修改前 SHA-256 | 当前 SHA-256 | 状态 |
| --- | --- | --- | --- |
| `pack_dependencies.py` | `9cc86db6ee09dab6305b2451bc954a0d24350a10e4341278078eebf87cf25e50` | 同左 | 未改；全部 fresh identity 读取保持 |
| `pack_import_policy.py` | `55a546097966d21ef8b83524892c36cb6713e022ea8e00af93f952b58630b50e` | `6540057dea749eedf2ca2064eedfb8bac1e2d24e09f725bd51fbd588d149155f` | 有界纯语法 LRU |
| `catalog.py` | `c8d4919772db4971487658a571975e1d2018a760d38e29b0ee84d66c66a6cc36` | 同左 | 未改；56 check／281 save 保持 |
| `test_pack_import_facts.py` | `b5ea119dbcc61bc77aec2026d9d2e965e6875e6bdbe80cbc0dbb978fe5d18660` | `9ca0f9cef80c778d4de69a4b11251e4eb8705e3cd341465f94b17091fe88eb2a` | freshness／失效／等价回归 |
| `test_capabilities_ast.py` | `304f4be80a7978f217c4a10b2b82a03892a07644f9d9518303cbd7bdfeb2ddeb` | 同左 | ordered oracle 未改 |

`pack_import_policy.py` 自身 hash 变化会合理改变 `import_guard_sha256` 及其派生冻结资源身份；不能把新旧 runtime identity 或冻结包称为全字节相同。相同候选内部六次 policy 输出与 ordered validation 结果等价由当前测试／profile证明。

## 未验证与剩余风险

- 新候选完整 Research Web Checks、Project Constraints、macOS Bootstrap 和真实 PR245 CI 尚未执行；不得称 CI 已修复或 merge-ready。
- 远端 Linux 调度、并行 worker 时长与文件系统缓存差异仍未知；本地 profile 只证明热点减少。
- 相关两文件的实际 mypy 仍为 **17 errors in 7 files**（均来自既有跟随导入路径，当前两个 changed files 无直接报错）；与既有 17／7 债务一致，但未做完整 baseline 差分，状态保持 BLOCKED，不能称 mypy PASS。
- 未安装依赖、未改 workflow／timeout／runner／测试清单／CI 配额、public API、schema、数据算法、Source capture、Store locking 或独立 T4 worktree。

## 增量验证收口

`.agents/runtime/leon-engineering/manifest.json` 的 14 个受管文件逐项 SHA-256 核验通过，framework `0.19.3`／source `f853b1b2`。完整 9 文件 changed set 的 Router 为 L4，原因是新增测试路径按 unknown boundary 失败关闭；本地五门全部实测 PASS：

- `research-web-architecture`：84 passed，5.00s；
- `project-constraints-local`：最终 violations 0，0.25s；
- `research-web-verification-full`：118 passed，5.18s；
- `documentation-governance`：violations 0，0.33s；
- `python-file-index`：最终 current，1.41s。

首轮 Python index 因新增 helper 如实 FAIL，按 `validation_failure` 重规划后由原生成器更新；首轮 Project Constraints 因缺模块文档和 README review receipt 如实 FAIL，再次重规划并补真实“结构／README 不变”说明后通过。两个失败日志与三份计划均保留，未改 checker。最终 schema-v2 receipt 机械校验 `valid=true`，但 `project-constraints`／`research-web-checks` 两个远端 merge gate 在本候选均为 BLOCKED，因此总结果仍为 `BLOCKED`、`mergeReady=false`、`releaseReady=false`；不能把本地 L4 闭包写成远端 CI 已通过。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"只在原pack import policy内增加以完整fresh源码和parser身份绑定的有界纯语法facts缓存；依赖identity、模块枚举、源码读取、来源核验、六次runtime、56验证、281保存及唯一DSH边界保持，无新API、权限、服务、数据schema或图节点。","diagrams":[]} -->
