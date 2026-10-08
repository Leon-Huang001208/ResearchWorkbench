# Task14 c1 当前 master 本地集成

宿主 macOS；任务为 Task14 既有功能集成，验收范围为本平台本地源码验证。
指定 c1 worktree 的合并父节点为当前 master
`b0ed27b75aa915346f6cf1f1db984623dfe25f14` 和旧目标集成
`2348aa454279b763ae32140ef27c3c342e5f4ec9`；共同基线
`205d2a170d9ece9c2751e014b63abe326510ab9c`。
本报告不认证旧物理镜像为当前候选，不执行远端、Docker、依赖安装或全局配置。

## 两侧保留映射

目标侧保留动态端口、EndpointStore CAS/restore 新 revision、ControlOriginTransaction
保留 token、实际 lease 中的 fresh-root 父/根 FD、Foreign Native Ledger 调用内观察和
实际进程/记录身份、Web 三项探测 3 秒预算、Native public stop 后最多 45 秒释放等待。
上述功能由既有启动器、manager 和 supervisor 实现，不新增部署节点或放宽 guard。

当前 master 侧保留第三方已发布目录中的嵌套运行实现、publish negative 目录规则、
Engine HostConfig.Tmpfs 投影和 macOS Docker 停止后的有界端口释放等待。
Compose 同时保留 UID/GID 10001 私有 tmpfs、noexec/1 MiB 状态 profile，以及独立持久
日志 bind。检查正常容器和临时 control-preparer 时均核验固定选项、RW、来源和归属。
自动合并重复的 inspect tmpfs 字段及旧字符串 validator 已去重，仍使用严格语义 parser。

原 d292634868 属性同步后来被 5f6615861 从 master 源码移除；历史报告保留其当时
不足以修复状态 bind 的失败结论。初始指令误要求保留该方案，本轮曾短暂恢复并做本地
RED/GREEN；父任务依据撤回证据纠正后，仅撤回本轮新增 function/calls/tests，最终源码
保持当前 master 的实现。状态使用严格 tmpfs 创建，凭据/产品日志保留既有首建 guard；
不把曾恢复的 11 项测试当作最终源码证明，不重写历史报告。

## 实际过程与未完成项

受管 verification runtime 14 个文件逐项 SHA-256 核对通过。当前 c1 dirty changed set
已用 plan v4 初步审计 common205 基线（130 路径、L4、17 本地门），后续交付以当前
master b0ed 为真实基线重新规划。CI/真机状态未认证，候选提交后还须重新绑定。

首次冲突组合后 Docker/staged 两模块运行：111 FAIL、312 PASS、141.14 秒；旧 tmpfs
validator 与新 profile 叠加导致大批 ownership 拒绝，失败保留，不把后续运行称作首次 PASS。
新增 bind 同步回归 RED 2 FAIL，精确恢复后 GREEN 2 PASS；恢复原 d292 回归后一并
执行为 11 PASS。随后 50 项聚焦检查 46 PASS/4 FAIL，40 项严格投影检查 37 PASS/3 FAIL；
尚有两侧测试预期重叠与 fixture 私有祖先模式问题需收敛，未把失败跳过。

工具发现：原 Web venv 不提供 Ruff/Black module，两个 `python -m` 命令失败；未安装依赖。
使用已有 `/private/tmp/rwb-stage1-test-992c74ec/bin` 工具后，六个当前冲突关联 Python 文件
Ruff PASS；Black --check 报五个文件需要格式化，后续验证另记。

最终重叠测试按当前 master 已发布合同调整：第三方 installed publish payload 不重新套用
workspace files 声明；嵌套运行子树可保留，顶层 doc/docs 与全部层级 Git/cache 元数据仍
排除，workspace negative 目录、secret fixture、越界依赖/别名/asset 负面门保持。
Engine 明确 Mounts 的正面用例改为完整三项或完全省略，部分列表由既有负面回归拒绝。
旧停止立即 OK 用例改为证明容器已经停止、外来 Web listener 保留、等待仍超时且不 rm。
旧 fixture 用私有 0700 run/docker 祖先替换递归 mkdir 的默认 0755，不改锁 validator。

全模块复查曾在不同根 Native pair 生命周期用例重现另一个真实集成失败：Docker stop
等待错误包含容器内部 DSH 端口。只中断本轮自己的 pytest PID 33537；174.11 秒时为
84 PASS/1 FAIL，完整日志保留于 `logs/task14-c1/docker-staged-after-resolution.log`。
新真实临时 runtime listener 回归 RED 1 FAIL；唯一源修改将等待目标改为原 inspect 已
验证的宿主 Web port。GREEN 相关闭包为 42 PASS/30.03 秒，映射 Web 持续占用仍超时，
内部外来 listener 保持 alive，不停止或接管。

最终 DSH staging 独立 75 PASS/2.27 秒；计划中 JS 合同 220 PASS/10.27 秒，Docker JS
15 PASS/0.316 秒。当前 master 完整 101 路径 Project Constraints 与 common205 历史
131 路径架构审计均为零 violations；文档治理 595 文件/88 current、Python index 和
Atlas --check 通过。初始 constraints 调用端误读不存在的 ok 字段导致退出 1，原零
violations 结果保留；改用正式 violations.length 判定后退出 0，未修改检查器。

当前完整 changed set 的 28 个 Python 文件 Ruff/Black/isort 全通过。实际版本为
0.16.10/26.10.0/9.0.2。mypy 2.4.0 的三个直接冲突源检查为 FAIL 8 条；原工具环境缺
pydantic 插件的初始失败保留，之后仅在命令环境只读引用已有产品 venv site-packages。
当前 master b0ed 的同版本/配置、176 源码/config Git archive 诊断同样 FAIL 8 条，
去掉行号后的 file/message 多重集完全相同；不把无新增错误称为 mypy PASS。

源冻结 V2 为 `logs/task14-c1/source-freeze-v2.json`，34 个源码/测试/构建路径：
docker_runtime.py 为 `1137d0105f9f155d96b7707e2667bd97c4b270a0562d6656d4319c31e9420ed2`，
对应 Docker 测试为 `5ed2ff01d55f9ad8b7a49b165a9d41901d6cf2b7cbeb2eec57fae34a50774fa4`。
原 Task1–12 的 a1d2087/eeb530c 均实际为 MERGE_HEAD 的祖先；本轮不删提交或旧 worktree。

V2 源码的完整 Python 依赖闭包实际为 **1524 PASS / 1 SKIPPED / 1 warning，387.04 秒**；
跳过项为既有 `test_local_integrations.py` 原生 Windows runner fixture，Mac 不冒充执行。
warning 为既有 Starlette/AnyIO BlockingPortal 弃用。15 个去重模块同时覆盖全部选中
Python 本地门及 endpoint/origin/CLI/bootstrap 近处依赖，不把 staging 的 75 项重复相加。
该次验证对应的 34 条 V2 源码冻结 SHA-256 已复核零变化，不提升为后续 V3 的完整验证。

独立 spec 评审发现 P1：stop 初始 inspect 只核对 owner/image/mount，端口映射到停止后
才由 `_status` 核验，因此错误的 0.0.0.0 绑定曾被先 stop；无 endpoint 的 Legacy 映射
也会先等待默认 8088。两项最近回归均 RED FAIL。V3 在原停止入口先调用原只读 `_status`
认证并恢复实际 host port，再固定 RAM-only ports 与 container ID/image 快照；停止前与
每次 poll 沿原 inspect/status 再核验，变化即拒绝，不写 mode/endpoint/CAS。
错误 mapping 保持原容器运行且不 stop/rm；真实 Legacy 动态 reservation 保持原监听并
超时；两种显式/Legacy 的晚期合法 loopback mapping 替换也拒绝。
首个相关 GREEN 10 PASS/27.51 秒，晚期 mapping 补充两例 2 PASS/2.18 秒。

V3 冻结 `logs/task14-c1/source-freeze-v3.json` 仅两项源码/测试哈希变化：
docker_runtime.py 为 `b4778362e0a2a3a548403b7f61e2d51c84975eda3242c2a662c8834863f04452`；
Docker 测试为 `ed9772f5aee9bcadb2038ad82130e02a5c21fe10a81f618593882e7caac630dd`。
其余 32 条与 V2 相同，V2 原日志及失败不覆盖。V3 精确执行完整 runtime-mode 与相关
installation 三模块 closure，其他本地门只在源/测试身份和依赖路径未变化时保留 V2
affinity；文档/索引/架构/完整变更约束重新检查。三份生产源的 mypy 仍 FAIL 8 条。
V3 完整三模块实际 **569 PASS / 295.09 秒**，JUnit 明确 Docker 352、runtime-mode 97、
setup 120，零 skipped/warning。实际命令为：

```bash
python -m pytest --confcutdir=tests/research_web tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py tests/research_web/test_setup_web.py -q --tb=short --junitxml=logs/task14-c1/v3-runtime-mode-setup.xml
```

V3 证据在 `v3-runtime-mode-setup.log` 与同名 XML；该命令重新证明 runtime-mode 及
installation 两个必需本地门。容器 supervisor、Native manager/launch、protocol、
local integrations、endpoint/control-origin/bootstrap/CLI 等另外 12 个 V2 模块的
源与测试字节未变；V3 仅改 host Docker stop 的验证/等待顺序，其相关公开 switch 与
安装调用链已经纳入上述三模块，不把其他平台/镜像/运行实例证据借作本地源码 PASS。
原 220 JS contract 的策略/受管 kernel/图文生成器及测试输入未变；Docker JS 15 项另在
V3 重新执行（0.271 秒）。V3 文档、Python index、Atlas、完整 101 路径约束与当前/共同
基线架构均重新检查通过。mypy 当前 V3 与真实 b0ed baseline 的 8 条错误多重集仍相等，
结果仍为 FAIL。两个当前修改 Python 文件 Ruff/Black/isort 重新通过，其余 26 项沿 V2。

## 实际最终命令与证据

解释器为已存在的原 Web venv：
`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`；
Node 为 `/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。
每次 pytest 均显式 `--confcutdir=tests/research_web`，未安装 SQLAlchemy 或其他依赖。

```bash
python -m pytest --confcutdir=tests/research_web tests/research_web/test_service_manager.py tests/research_web/test_local_integrations.py tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py tests/research_web/test_platform_capabilities.py tests/research_web/test_setup_web.py tests/research_web/test_container_supervisor.py tests/research_web/test_runtime_launch.py tests/research_web/test_protocol.py tests/research_web/test_runtime_endpoints.py tests/research_web/test_control_origin.py tests/research_web/test_cli_lazy.py tests/research_web/test_web_bootstrap.py tests/research_web/test_web_contract.py -q --tb=short
python -m pytest --confcutdir=tests/research_web tests/research_web/test_staged_runtime.py -q --tb=short
node --test tests/javascript/verification_policy.test.mjs tests/javascript/verification_receipt.test.mjs tests/javascript/incremental_validation_skill.test.mjs tests/javascript/verification_platform_task_entry.test.mjs tests/javascript/verification_delivery_summary.test.mjs tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs
node --test tests/javascript/docker_runtime_contract.test.mjs
node scripts/plan_verification.mjs --project . --base b0ed27b75aa915346f6cf1f1db984623dfe25f14 --task-context .ai/reports/2026-10-08-task14-c1-task.json --signal validation_failure
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node scripts/build_research_web_api_atlas.mjs --check
node scripts/check_research_architecture.mjs --project . --base b0ed27b75aa915346f6cf1f1db984623dfe25f14
node scripts/check_research_architecture.mjs --project . --base 205d2a170d9ece9c2751e014b63abe326510ab9c
```

以上 `python`/`node` 是上述实际绝对二进制的简称；Python 命令环境含当前 worktree
`PYTHONPATH=.` 与已存在工具目录 PATH。实际原始记录分别为
`logs/task14-c1/planned-python-closure.log`、`staged-final.log`、`planned-js.log`、
`docker-js-contract.log`、`plan-master-escalated.json`、`architecture-master-final.json`、
`architecture-common205.json`、`documentation-governance-final.json`。
Project Constraints 通过正式导出 `checkProjectConstraints` 消费 planner 的全部 changedFiles，
结果在 `constraints-master-summary.json`；未用手选路径缩减门。

V3 独立 SPEC 复审已 APPROVE，原 P1 关闭；审查者再次实跑四项错误/Legacy/晚期映射回归
4 PASS/0.26 秒，并复核两项冻结 SHA，没有剩余规格发现。Python/质量复审及本地 merge
commit 仍待父任务后续步骤；准备态 task/plan 绑定的是真实已有 b0ed HEAD
与 dirty source，不当作新 merge commit 验收，真实提交后必须重新绑定。

## V4 无受管容器停止分支

V3 spec/quality 已批准后，质量审查另指出空容器时误等待默认/记录 Web port。已核对
原 accepted Goal 2348 的 stop：只等待实际剩余 owned 容器，空集合沿 `_status([])` 返回
ok/ownership=absent；205/b0ed 的旧端口等待曾保守拒绝外部监听，但批准的端点设计将
释放检查限定为实际 host publication，不能把默认或持久端口当作容器所有权。
V4 仅在正常 availability/精确枚举与原 `_status` 完成后、确实没有容器时提前返回原
absent 状态。不新增端口探测、停止或释放权限，不清理外部监听，不改 mode/endpoint。

缺失与已持久 endpoint 的真实外部 Web listener 两项 RED 均 FAIL
`runtime_ports_not_released`；最小分支修复后相关 14 项 GREEN PASS/27.48 秒，显式证明
外部 listener alive、无 port probe、无 stop/rm，mode/endpoint 精确保持。
V4 源码 SHA 为 `df4e5c3d8e08bdde825932dfd5f0b5aa5ae5e2e8f533cabbd6fd42c1d2e965b8`，
测试 SHA 为 `b82ecd3d932abac4d8babd7e620e13cbf5b8bd0d44066455010477bca81ea1ce`；
`source-freeze-v4.json` 中另外 32 项保持。V4 两文件 Ruff/Black/isort 再通过。
旧 V2/V3 日志与冻结对象均保留，不追改为 V4 PASS。

V4 的独立 SPEC/第二阶段 QUALITY 均 APPROVE，reviewer 再次独立 8 PASS/0.45 秒及
两个文件格式检查通过、哈希匹配。完整 runtime-mode pair 实际 **451 PASS/163.17 秒**，
其中 Docker 354、runtime-mode 97；日志为 `v4-runtime-mode.log` 与对应 XML。
当前 master b0ed 草稿 plan v4 完整 101 路径/L4/17 local IDs；原 Goal
4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7 草稿完整 327 路径/L4/22 local IDs。
两侧保留同五个 CI IDs，不删 Windows/Linux 交接。原 Goal 全 327 路径 constraints 与
架构均零 violations；不是以 101/131 路径结果替代。原 Goal 的 credential-backend、
runtime-contract、API、UI 四个 local IDs 本 worker 尚未实际运行，需父任务补证；
repository-cross-platform-contracts 已包含在本轮实际 220 JS 合同命令中。
父任务另实读核对 c1 相对 2348 的 app/research_web、app/cli、core、requirements、
runtimes、tests/javascript 及 API/credential/runtime_contract 测试 diff 全空，可作为
旧 extra gates 的精确输入 affinity；这是父任务的核对，不是本 worker 的当前重跑。
后续仍需真正 merge commit 后重新绑定 plan/receipt，阅读 SHA 在后续 doc commit 指向
已存在 merge，不写未来或自包含 SHA。当前本地提交不会证明物理镜像或远端 CI。
GitHub macOS 安装 CI、当前 fresh 镜像及真实生命周期由父任务处理；Windows/Linux 保留
对应设备交接，不从 Mac 本地测试推导支持。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"组合既有动态端点与实际lease调用内证明、私有tmpfs日志挂载、发布资产过滤和端口释放等待；部署节点、DSH唯一引擎、认证与严格owner/no-follow边界不变。","diagrams":[]} -->
