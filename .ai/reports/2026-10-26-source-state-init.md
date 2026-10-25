# 真实 Host 冷启动来源状态初始化

## 同 PR 首次 CI 修补：目录序列化成本

候选 ecef 的 Checks40226600173 达40分钟上限取消，Python仅57%，无完整汇总；完整日志14.5MB持续推进，不认证无失败。Mac40226753690与Constraints40226600281已通过但不跨候选复用。真实四项API profile中Service构造16.666秒/目录16.506秒，880次save占10.714秒，约1120万次JSON逐片段write；依赖扫描4次0.935秒，不能将扫描假设当根因。独立评审确认该定位。

最小修补把 `json.dump` 改为相同参数的 `stream.write(json.dumps(...))`，保留保存时点、临时文件、flush/fsync、replace、错误类型和清理；不共享Service、不跨Host缓存、不合并事务。新增UTF-8/嵌套字节一致及单次write断言在修复前2 failed/4 passed，fsync/replace/序列化失败保全原索引均保留。后续完整回归、profile对照、静态、评审及新候选CI另留实际证据，不从本段推断已通过。

修补后完整 capabilities/resident/API 335 passed，283.40秒；Ruff/Black/isort/Mypy、文档治理及索引检查通过，独立内容评审 APPROVED。同样4项真实API的顺序单次、非profile对照为旧7.659秒/新6.462秒，仅是本机小样本，不能由profile热点或约16%墙钟变化推导整个CI已满足40分钟。编码期间会短暂持有完整JSON字符串，未扩张索引内容；新候选完整CI仍需实跑。

## 问题和修复边界

PR237 将 resident 的来源活动见证改为严格读取 `source_requests`。真实 `ResearchService` 却只在首次来源执行或取消时，由 `research_web_sources.request_state` 懒创建请求和取消登记表。尚未发生来源操作的真实 Host 会因属性缺失把空闲归约为未知。原 b800 的 Wind 清理未确认是另一项现场问题，本补丁不能给旧进程补证。

修复仅把这两张已有内存登记表移到真实服务构造阶段初始化；来源执行、取消、清理和 tombstone 仍复用原对象和流程。不改 resident 的未知拒绝，不创建虚假见证，不增加持久格式、路由、依赖或执行恢复能力。

相关 Mypy 检查还发现同文件原有的 `report_context` 嵌套索引类型债务。已用 base `4c72ed43` 的原文件 shadow 验证相同诊断，不把它写成新增回归；仅为立即构造的字典增加精确 `cast(dict[str, object], ...)`，不改变赋值、验证分支或运行值，也不关闭诊断。原失败输出保留。

## 失败复现

独立 worktree 基于 `4c72ed4349c087cf0b7d037d7133b84201a76d5f`。真实服务构造、真实 resident HTTP 投影、真实来源请求登记及取消流程保留，只有 Native/凭据后端/来源正文等待边界使用内存或无网络夹具。

编辑前两项确实失败：冷 Host 的 `active` 为 `None` 而非 `False`；请求登记表不存在。初版属性断言失败及随后 HTTP 级失败都保留于 `logs/source-state-init/red*`。修复后两项通过，来源等待时为忙、取消后登记表清空且原 tombstone 保留，未删旧拒绝断言。

## 验证状态

已执行定点 RED→GREEN；真实 resident/来源读取/活动见证/完整 API 四模块 342 passed（747.32 秒），随后只增加类型恒等 cast 和测试客户端关闭后，resident/reader/活动/协议四模块 210 passed（17.28 秒）。两组有重叠，不能相加为独立覆盖数。完整 API 已登记原 Checks 同一步，原缺失/异常见证负例保留。

Ruff、Black、isort 及两个修改 Python 文件的 Mypy 通过；原类型债务的 base/current 失败输出未覆盖。Router JavaScript 113 passed，文档治理、完整变更约束和生成索引检查通过。独立内容评审 APPROVED，无 P1/P2；最终候选绑定、完整 Git 绑定 Router 回执及同候选三项 CI 以交付日志认证，本文不提前标记远端检查通过。

该源码修复任务未部署、未执行服务停启、Office、供应商或模型，也未重放旧 Run、开启日程。上层执行准备另做了自有文件的 Word 环境检查，不代表周报成稿。Windows/Linux 原生产品验收保留交接状态。实际维护由既有唯一恢复任务负责。

## 结构决定

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"仅提前初始化原Host来源请求及取消内存表，严格活动归约和真实来源生命周期保持，不增加接口、权限或业务节点。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"原唯一DSH和Host控制关系保持；修复冷启动字段生命周期，不修改模型提交、执行恢复、控制器或维护协议。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"两张登记表按真实服务实例构造，不改变租户数据根、账号权限或持久格式，其他未知见证与旧现场拒绝保持。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"自动化仍复用同一Host，修复仅初始化原来源内存登记，不改变调度、授权、冻结执行或模型提交合同，也不启动任何计划。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只向原Python检查步骤登记真实API回归，旧用例和CI节点、runner、超时保持，现场恢复及模型质量仍独立验收。","diagrams":[]} -->
