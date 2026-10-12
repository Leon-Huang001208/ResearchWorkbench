# Foreign Native private-ledger lifecycle repair

hostPlatform=macos；taskKind=Web 功能修复；hostAcceptance=BLOCKED；aggregateAcceptance=BLOCKED。
基线 d2a0015cb；批准计划 70e6c54e7。实现只在指定 foreign-native-root-ledger worktree，
没有真实 Docker、产品服务、安装依赖、真实 HOME/checkouts 写入、全局、远端或 cleanup。
物理安装与 Native/Docker 同根往返由主任务负责，本报告不宣称整体 goal 完成。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Reuses the existing private Native ledger reader and target lifecycle lease for call-local different-root observations, preserving deployment topology and persistent contracts.","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The existing single Web and DSH engines and authentication exchange remain; this change concerns host lifecycle ownership checks only.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Updates existing architecture, installation, runtime and security authorities and their evidence without adding competing documentation or diagrams.","diagrams":[]} -->

首次 RED：approved Python、PYTHONPATH=.，test_docker_runtime.py/test_web_bootstrap.py，
--confcutdir=tests/research_web -q；2 failed、359 passed，86.63s。两失败均完整异根 pair 下
runtime_ownership_unknown；Native.status 没有 mock idle，container 执行仅 RecordingRunner。
最初定向正向 2 passed，1.13s；新增 hostile/scope 19 passed，2.70s；连同未知 restart、
normal Native bridge、manager capture 与真实安装缺失 preflight 22 passed，2.62s。

中间 closest 1 failed、360 passed，238.38s：新增 OS-current-user discovery 与旧实时端口
测试的“未知”前提不一致。closest catalog 添加 tmp_path 下有限 locator monkeypatch，
显式异根 fixture 才提供完整私有 pair；原未知产品拒绝断言不改成成功。定向复核 20 passed，
2.72s。此隔离是测试 seam，不提供生产 override 或 allow-unknown。

实现保留两种权限：只读 current facts 与真实 target lease 下写观察。候选仅 pwd 当前 UID
标准 product root；parent/root/record FD、canonical distinct 私有根、完整同 project/data pair、
exact signature/PID/start/listener、controller/scope/lease identity 共同约束。观察变化不刷新，
finally 清除并关闭 FD。Web data association 仍依赖原可信私有 launch ledger；未读取进程
环境或 auth，不宣称 crypto/envroot 独立证明或抵御同 UID 任意篡改。force restart 先核验，
未知 pair 保留健康 container；stop/rollback 保留精确 ID、stopped binding conflict 不 recreate。

正常桥测试使用真实 owned-environment classifier fixture与现有 manager reader，执行桥为
显式同步 runner fixture；不宣称真实安装或跨 checkout 进程验收。首次 Native 切换测试实际
执行缺失安装 preflight 并证明未停止健康 Docker；成功安装后的切换属于主任务物理验收。

中间 expanded catalog 3 failed、1041 passed，229.54s：旧 Native fixture 缺少原桥对象的
ports 属性，补齐 fixture 合同后，8 模块（closest 7 + test_protocol）1076 passed，243.12s，
`logs/foreign-native-ledger/python-final.log`。这份证据早于最终 FIFO pin 预检和 manager
本次 spawn PID 限定，不冒充最终源。后者的定向模块 83 passed、214 deselected，15.95s。
其中保留一次单模块导入顺序导致的 fixture alias 泄漏失败：manager 在 OS probe monkeypatch
后首次导入，别名残留；改为 fixture 在 patch 前导入 manager，并成对显式 patch/restore，
未改变生产 validator。正常 bridge child 后 RootA/record/PID 变化、目标 unknown slot 在
control/spawn/switch 前出现、外来/伪造/丢失 lease 与 FIFO 拒绝均有实际断言。

源码冻结 11 个 Python 文件（4 生产 + 7 最近测试）相对 d2 binary diff SHA-256：
`2bc8102fe877af732a4c0c11ef5ceeb98e49f1667ec1bef0f70cbd89db1075eb`。
逐文件 SHA 在 `logs/foreign-native-ledger/source-frozen.json`。冻结后完整 Python v2 终态
1079 passed，233.74s；命令 runner 总时长 234.153020375s，exit=0，四生产文件
前后 SHA 完全相同。日志 `python-final-v2.log`、实测元数据 `python-record-v2.json`。

完整 changed set 为 27 路径（包括批准 spec/plan 和当前生成索引/报告），现有 planner 保留
unexpected_behavior/validation_failure，requiredLevel=L4，unknown_impact_boundary 不删除。
11 kernel manifest hash 全 PASS，未改 policy/stage/kernel。L0 governance/index、L1
architecture（72 tests，7.450771167s）、L2 Project Constraints（最终 0.190877083s）、
Docker contract（14 tests，0.296884375s）、L4 JS full（100 tests，8.621046709s）均 PASS。
上述 gates 的原日志和总时长分别见 local-records/js-records/constraints-final-record。
首次 constraints 缺 README review 与现有 owner 模块说明，实际 FAIL 后同步既有文档；
不为此调整机械规则。最终 doc-sync 1.957274167s、architecture-check 0.353672s、
governance 0.126582s、index 0.988510875s、diff-check 0.099538792s 全 PASS，见
`logs/foreign-native-ledger/doc-records-final.json`。

11 changed Python 的 scoped Ruff 0.16.10、Black 26.10.0、isort 9.0.2 最终 PASS。
mypy 2.4.0 正常项目配置四入口及其导入闭包仍 FAIL：57 条/19 文件。工具起初缺
pydantic 插件；仅只读复用 approved 产品 venv site-packages，未安装依赖。三条新类型
诊断已修，不新增 ignore；最终四入口同配置与 d2 的 207 源码传递基线均为 57，
file+message 多重集一致，无新增/删除。历史 16 入口 59 条不是本次四入口 57 条。
早期基线抽取的 plugin-missing 和受输出 buffer 限制的 missing-file 属于诊断环境/提取失败，
不计作类型 RED；有界 archive 完整提取后真实基线耗时 7.5809855s，FAIL 保留。
最终质量与归因见 quality-records.json/quality-mypy.log/mypy-comparison-final.json。

stdlib missing-environment 与 owned-classification Native bridge 都消费 shared reader；hint
仅为内存事实比较，在 child 前后与 controller 真实 lease 下重新 capture 后比较，不因 ports
为空而放弃已观察 pair。manager 目标新增 ledger 必须属于该 scope 的真实 spawn PID，
外来 owned-looking 记录也拒绝。record FD 在 open 前验普通私有文件/大小，以 NONBLOCK
避免 FIFO 或替换阻塞，open 前后身份必须相同。

CI/物理门 NOT_RUN；未执行任何 remote operation。receipt 仍须以全部 local 终态和
四个 external NOT_RUN 构建为 BLOCKED、mergeReady=false、releaseReady=false。

最终 Python 原命令：`PYTHONPATH=. /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_docker_runtime.py tests/research_web/test_web_bootstrap.py tests/research_web/test_web_contract.py tests/research_web/test_service_manager.py tests/research_web/test_runtime_mode.py tests/research_web/test_setup_web.py tests/research_web/test_cli_lazy.py tests/research_web/test_protocol.py --confcutdir=tests/research_web -q`。
Python 四个必选 gate 共用该完整闭包证据/总时长，不把时长求和或虚构独立单 gate 计时。

独立 spec review 后补成功 Docker→Native 选择集成：
`test_installed_native_switch_uses_pair_reader_preflight_and_mode_cas` 正/反两例实际走
NativeRuntime→_native_probe→manager._installation_diagnosis；manifest、lock hash、owned
marker、build-lock 由原校验器消费，底层 package/Node/已验证 DSH 资产事实明确为 unit
fixture。验证 preflight→exact Docker stop→mode CAS，ID 保留、无 autostart/rm；lock
不匹配在 stop 前拒绝，2 passed，2.16s，不宣称真正安装。真实子进程 bridge 测试 shim
另把 child 的 pwd 用户 HOME fact 限定临时目录，保持真实 socket/PID 事实，避免 unit 读取
日常标准 ledger。v3 后最近三 catalog 481 passed、208.19s，记录 python-review-final.log，
这份结果发生在以下两项 Important 修复前。

独立 Python/security review 两项 Important 的真实 RED：7 failed、299 deselected，
1.67s，review-spawn-red.log。两例 Popen 后/第二登记丢锁未收尾 child；四例本次 state
同内容 inode、完整 argv、start 或 listener 变化未拒绝；一例未知记录 rollback 进入了
terminate spy。修复仅在 manager 现有 spawn/state writer/ready/stop 链保存真实 Popen、
本次 writer FD 与 lease/scope；owned-listen 一次建立完整事实，不通过重复登记刷新。
首次/第二登记失败用已有 child 句柄调用原 cleanup 并保留原异常；未知 record 的普通
rollback 拒绝，原 health 错误保持。7 条原 RED 变为 7 passed，0.67s；补合法
closed→owned-listen、重复登记/变化恢复仍拒绝、rollback 原错后 9 passed，0.75s，
review-spawn-final.log。新增 retained FD 的一个 mypy narrow 已修，当前仍 57 既有诊断。

v4 冻结快照 source-frozen-v4.json，11 Python diff SHA
`5eecfdbcfc5637a538bb80d981b32963b1f0ae4bb7d9aa903e6e3af1c5230d10`；manager SHA
`46bada65b7c98a96fcbbd736984872b1dd2207075a320e3e2f082726be098472`，另外三个生产
文件维持初始 SHA。旧 1079/481 和前一 receipt 均不能作为 v4 的全部 gate PASS；v4
当前只在等待必要 manager/runtime/auth/smoke 闭包及最终 gate/receipt 终态。

v4 相关 manager/docker/runtime-mode/auth/protocol 闭包最终 737 passed，112.89s，
runner 113.257683834s，sourceUnchanged=true；日志 python-spawn-review.log。独立 Python
确认两项修复，Security 另指出 target 未知槽拒绝没有永久 poison，v4 不可提交。
新的真实 RED 为 manager/Docker 未知槽出现→拒绝→删除→检查重新通过：2 failed、1
legitimate exact stop passed，0.95s，monotonic-red.log；不合法 exited child 的后续相同事实
恢复另为 1 failed，0.93s，monotonic-exit-red.log。三项均实际行为失败，不是环境错误。

最小修复复用 shared observer 的内存 invalid 位：`_invalidate()` 统一撤销已捕获 scope，
manager target 拒绝、Docker target/lease 拒绝和 own-child 不合法退出均不再自动恢复；
预先验证的精确 stopping/stopped 退出保持合法。合并上述和 spawn 负例 13 passed，
0.86s，monotonic-green.log；其中 legal exact stop 没有被错误 poison。没有持久标志、新
框架或权限开关，finally 原清理保留。

v5 新冻结 source-frozen-v5.json，11 Python binary diff SHA-256
`9ad34c839d196f3d5c992543c0838a3036b6ee6700224a9b7eeae2e8f2b323c4`。4 生产 SHA：
service_manager `40ff9ac8e2a4c63dd73c618e7b8db8bca268a919a543e40ce7323c67d481ebdc`；
bootstrap `a5c49e2213cd01bc827dd39acfface81f12a0b4b8da4273bca9d86e759216004`；
docker_runtime `cfc5ddff0b2a357da22dffcc6d4f94fd34dffd0cc9cde98e9b13f38e38cd784d`；
web_bootstrap `153e1ca1cf121a697c6647b35fb14322267f876cae32470925b60a5b01624441`。
v4/更早 counts 不移动为 v5 gate PASS；v5 最新必要闭包运行中，尚不宣称完成。

v5 九模块完整闭包最终 1099 passed、252.47s，runner 252.90128725s，sourceUnchanged=true，
python-v5-final.log/python-v5-record.json。v5 L0 index 与 doc-sync 真实 FAIL（生成索引 stale），
其他 selected JS/constraints/gov PASS；已用现有 generator 更新，保留失败与 signal，不改门。
最后独立 Python review 指出 Docker target-slot 的非 missing OSError 没有 poison；真实
RED 1 failed、312 deselected、0.70s，target-io-red.log，原 issue 是 docker_io、恢复后
同 scope 真的重新通过。最小 fix 只在该 lstat 边界先 `_invalidate()` 再原样 raise；
现有 `_guard` 继续 docker_io，绝不把 I/O 当 missing。manager target reader 的 I/O
已投影 invalid 并统一 poison，共享 current 的 I/O 也撤销；未扩通用 guard。
合并对应回归 14 passed、299 deselected、3.04s，target-io-green.log。

v6 source-frozen-v6.json 的 11 Python diff SHA
`4cd65575147bb16d6a0efc95455e00998fe5dac246605c00e198bbfe35ffa7be`；只在 v5 基础上
改变 Docker 生产源 3 行和最近 IO 测试。Docker SHA
`bbb4fd30af10d6eed40e8185622f947883fe840d6b4c81dde5ac32028dca3bde`，其余三生产 SHA
与 v5 相同。独立 Python/security 已对 v6 正式 APPROVE；其独立 IO 用例 PASS，不能把
此前 review 的批准转移到新源。本报告当前等待 v6 受影响 runtime 闭包和最终 metadata 终态。

v6 验证亲和：仅补验改变的 Docker/runtime-mode catalog；service-manager、installation、
critical-smoke gate 的相关源与 v5 九模块检查相同，按明确源亲和复用 v5 证据，不声称又跑
全量 1099。scoped quality、完整 changed-set doc/constraints、当前 planner/kernel/receipt
分别核对当前 v6；各历史 1079/481/737/1099 count 始终保持各自真实冻结源与总时长。

最终 v6：Docker/runtime-mode 两模块 375 passed，105.85s，runner 106.296889083s，exit=0，
11 文件 sourceUnchanged=true；python-v6-final.log/python-v6-record.json。这里没有把旧全量
改写成 1100 或声称重新执行全量。当前 11 changed Python Ruff/Black/isort PASS，实际
耗时 0.084930792/0.248406/0.238972916s；mypy FAIL 57，与 d2 同范围正常配置多重集
完全一致（无新增/删除），1.2320275s，v6-quality-records/v6-mypy-comparison.json。
11 kernel hash PASS；当前 27 路径 plan-v6.json 为 L4，仍保留两 signal/unknown boundary。
v6 governance/index/constraints/doc-sync/diff-check 分别 PASS，0.1528495/1.161478125/
0.169229625/1.665279792/0.101014083s，v6-local-records.json。L1 architecture、L2 Docker
contract、L4 JS full 复用同 JS/source-contract 内容的 v5 PASS 72/14/100 项；其日志保留
原运行时间与范围，不求和不伪造独立时长。

本地 source-only 交付的完整回执为 receipt-v6.json：10 selected local PASS，4 external
NOT_RUN（Project Constraints、Research Web Checks、macOS Bootstrap、Docker CI），
result=BLOCKED、mergeReady=false、releaseReady=false。实际物理安装、两模式同数据根
往返和真机验收均未由 worker 执行；原 Task 1–12、全部历史报告和其他 worktree 保留。
`validate_verification_receipt.mjs` 对 plan-v6/receipt-v6 实际 exit=0、valid=true；没有绕过
先前 receipt 字段错误或 selected CI 未运行的 BLOCKED 状态。
