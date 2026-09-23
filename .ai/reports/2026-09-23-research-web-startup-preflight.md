# Research Web 启动前置诊断

## 状态

本地实现与 L0–L4 验收完成；两个必需外部 CI gate 尚未运行，机械 receipt 保持 `blocked`。

## 问题与根因

- 复现命令：`./rwb web start --no-open`。
- 修改前结果：服务管理器在 Doctor 已报告 `environment_not_owned`、`cjpy_not_ready` 时仍创建 Runtime，等待 35 秒后仅返回 DSH 启动超时。
- 根因：`WebServiceManager.start()` 没有消费已存在的 Doctor 安装事实，安装失败与运行时健康失败被合并成同一个超时表象。

## 实现

- `start()` 在任何 spawn 前复用 Doctor 的安全化安装投影。
- 安装未就绪时记录稳定日志事件，返回精确 issue code、macOS/Windows 安装器入口和 Doctor 复核命令。
- 为 service-manager 源码与直接回归测试增加精确增量验收路由，避免测试文件误落入未知 L4，同时确保纯生产改动会运行对应 Python 测试。

## 已观察证据

- TDD RED：新回归测试在 `_spawn(runtime)` 处失败，证明启动前门缺失。
- TDD GREEN：`tests/research_web/test_service_manager.py` 30 项通过。
- 原始 CLI 复验：未就绪安装在 2.98 秒内返回 `environment_not_owned, cjpy_not_ready`，没有创建服务。
- 验收规划：政策变更本身保持 L4；初次 L2 Project Constraints 真实失败并以 `validation_failure` 重新规划。
- L0：文档治理 0 violations；Python 文件索引 verified。
- L1：verification policy 27/27、receipt 16/16、incremental skill 5/5、Research Web architecture 62/62、service manager 30/30。
- 独立审查发现完整 Doctor 会在归属确认前触发健康请求；修复后 `start()` 仅调用纯安装诊断，回归测试把 Runtime/Web health 与 spawn 均设为调用即失败并已通过。
- 审查后的首轮 Black 检查发现测试文件需格式化；已运行 Black 机械修正，最终生产与测试文件 Black 检查通过，service-manager 30/30 复验通过。
- 服务状态复核为 3081/8088 均 stopped，`git diff --check` 通过。
- 审查修复后的首轮 L0 发现 Python 文件索引因新增 `_installation_diagnosis` 过期；已运行受管生成器更新索引，并保留该 validation failure 作为重新规划依据。
- 最终提交前 fresh closure：Project Constraints `violations: []`；protocol 19/19；L4 local 75/75；policy 27/27；receipt 16/16；incremental skill 5/5；architecture 62/62；service-manager 30/30。
- 同一独立审查者复核修复后无 Critical、Important 或 Minor 问题；仅因 `project-constraints` 与 `research-web-checks` 外部门未运行，结论为暂不可合并。

## 架构判断

进程拓扑、HTTP API、DSH 协议、Tabbit 授权、框架与集成协调器关系均未改变；变更只把既有安装事实提升为进程创建前的失败关闭门。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Startup now consumes existing Doctor installation facts before spawning processes; runtime topology and API relationships remain unchanged.","diagrams":[]} -->
