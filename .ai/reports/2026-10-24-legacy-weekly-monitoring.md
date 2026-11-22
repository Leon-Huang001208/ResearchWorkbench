# Legacy 华安等待结束领域操作（离线）

宿主为 macOS，任务为 Web 功能开发；只准备源码与临时目录离线验收。没有部署、真实业务数据读写、Native 请求、Excel、模型、新会话或包安装。

## 交付范围

- `catalog.py` 新增显式 `open_for_maintenance`，通过正常 `cls(..., _maintenance=True)` 初始化公共字段，仅打开既存私有根、索引和锁；不 mkdir、不 reconcile。普通运行入口保持原路径，不使用 `__new__` 绕过初始化。
- `legacy_monitoring.py` 为可被后续受管操作员调用的窄领域操作。默认 dry-run；仅华安 historical_acceptance、legacy unknown、无新 sender 协议/attempt、原 Run 整体 digest 与 SID/version/owner/冻结 context/snapshot/contract hash 全匹配才具备资格。owner_check 必须传实时 primary owner resolver。
- apply 只改变 Workflow `status=cancelled`、`monitoring_disposition=ended_by_user` 并增加审计 receipt。失败、unknown、admission、原时间、SID/version、全部冻结文件和原 receipt 保留。receipt 明示 `native_cancelled=false`；不调用任何 cancel、interrupt、service.send 或会话创建。
- catalog 锁内 reload/CAS/原子保存，正常返回也重读并匹配 intended digest。写失败锁内读回 old/new/third digest；new 先重新 fsync 目录并再次匹配真实值，持续失败明确 committed_unconfirmed（同 operation 重试仍不谎报成功）；old 抛出保存失败，third 明确 indeterminate；不回写旧 catalog。
- CLI 固定 profile `weekly-legacy-monitoring-v1`，默认仅预览，逐项 expected 参数，无任意 JSON 编辑或 force。`--apply` 在打开文件前明确返回 `weekly_monitoring_operator_required`。

## 已执行验证

批准解释器为 `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python`；复用已批准 `etf-excel-first-20261023/.venv/lib/python3.12/site-packages`，没有安装依赖。最初只使用主仓 venv 时缺 pytest，命令真实失败；此后采用主会话提供的路径。

```
PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages /Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python logs/weekly-admission/run_offline_tests.py --confcutdir=tests/research_web -q -o addopts= tests/research_web/test_legacy_weekly_monitoring.py --junitxml=logs/weekly-admission/monitoring-domain.xml
```

73 passed（真实 legacy schema、空锁兼容与 receipt 一致性修正后定点重跑）。使用已有 main 脚本隔离 xlwings；断言 Office 入口禁止。JUnit 位于 `logs/weekly-admission/monitoring-domain.xml`。定点 ruff check 四个 Python 文件通过，black/isort 四文件格式化已执行；最后两源再次 ruff、black --check 和 isort --check-only 通过。本次未重跑其他116项回归。

覆盖：不 reconcile 未索引保护目录、不创建缺失根、预览无改写、证据逐字段与冻结字节保留、同 operation 幂等/不同 operation 拒绝、已结束后证据变化拒绝、身份变化、新协议、attempt、disabled owner、符号链接/锁权限/哈希拒绝、保存前失败、提交后失败和第三状态。

## MONITORING-SPEC-1 真实 schema 修正

此前测试夹具错误地要求运行记录含绝对 `path`。主会话只读现场核实：目标 legacy runtime 记录仅含 `run_ref="runs/{id}"`，因此原校验会拒绝真正目标。现在工作目录完全按 catalog 的 indexed run ID 固定为 `catalog.root/runs/{id}`；严格要求 `run_ref` 字符串字节相等，不接受绝对、空、不同 Run、`.`、`..` 或反斜杠引用。仅在旧记录额外存在 `path` 时检查其与固定根完全一致，冲突拒绝，不用该字段解析或选择任意文件系统路径。

主夹具已改为仅 `run_ref`、无 `path`；原完整保留/幂等测试基于该真实 schema。新增11项恶意引用、双字段冲突和一致兼容字段测试，变异后重新绑定完整Run digest，确保路径门本身发挥作用。所有操作仍在临时目录，不读取或修改真实 Run、权限、模型或服务。

## 既有空锁格式兼容

主会话真实只读预检安全拒绝后，核实旧 `catalog.lock` 为原 `_exclusive` 的 `a+b` 配合 umask022 创建的 0644 空文件。此前把锁和秘密索引同样要求0600会拒绝原合法格式。现在仅锁独立接受组/其他用户只读位：要求既存、空、普通文件、单硬链接、当前属主、无符号链接祖先、父目录私有，且禁止组/其他用户写入（0o022）。索引仍要求私有权限，其他路径门保持。

构造、每次 `_exclusive`、`_reload`、`_save` 共用同一锁验证。首次检查的 dev/ino/mode/uid/nlink/size 绑定到实例；打开使用 O_NOFOLLOW、不创建、不截断，打开后 fstat 和路径再次检查均须一致，防止检查/打开之间替换。新增8项离线测试：0644空锁不改权限/身份可预览；0664、非空、symlink、非私有父目录拒绝；打开前、打开后和reload前替换拒绝。未 chmod 生产目录或锁，未通过修改现场绕过校验。

## Receipt 幂等一致性修正

独立 Python 质量评审发现：此前重建原Run会移除整个 receipt，仅校验原Run digest，故 receipt 内 run_id/session_id/version/owner_id/disposition 独立变化可能被幂等分支接受。现在逐字段绑定 expected 的全部身份、固定 profile、operation_id、原Run digest、ended_by_user 与 native_cancelled=false；receipt字段集合封闭，version类型为int，previous_control必须精确对应原 needs_attention/无disposition/保留updated_at。ended_at必须为有限正数，且不早于有效的原updated_at；不使用当前墙钟阻断时钟回拨后的合法幂等。

新增29项离线回归，参数化篡改 receipt 身份、语义、时间、原控制状态与附加字段，全部要求同operation拒绝且catalog字节不变；已receipt仍先检查owner撤权、冻结快照变化和新增claim。正常相同operation继续返回原receipt，不创建新时间或原生操作。此门是领域一致性校验，不声称抵御同UID任意改写全部磁盘证据的攻击。

## 明确保留缺口

受管升级接入尚未实现，CLI apply 不可用。尚无 supervisor EX → admission EX → operator EX、当前源码/服务精确归属、primary owner现场、Native本SID及全子Agent idle、未知 journal/claim 检查的完整操作员验收；没有 GET 刷新旧 Host 缓存或原 Operations.idle 运行证据。这些均为 NOT_RUN，不得据 dry-run 声称生产阻塞已解除。

后续已授权的独立结束等待动作须在三锁和现场前置门满足后调用领域方法；返回后 catalog 锁已释放，仍保留三锁，窄 GET 刷新旧 Host，再执行未放宽原 Operations.idle。若仍有真实任务 active 或 witness 未知，升级 deferred，已明确授权的结束等待 receipt 保留，不回退用户决定、不忽略 active。常驻 apply 仍需用户单独批准。
