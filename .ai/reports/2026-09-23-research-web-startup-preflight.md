# Research Web 启动前置诊断

## 状态

P0 启动稳定性切片已完成并发布：本地 L0–L4、真实一键安装、生命周期、浏览器旅程及远端 macOS/Windows 干净环境均已通过。

## 问题与根因

- 复现命令：`./rwb web start --no-open`。
- 修改前结果：服务管理器在 Doctor 已报告 `environment_not_owned`、`cjpy_not_ready` 时仍创建 Runtime，等待 35 秒后仅返回 DSH 启动超时。
- 根因：`WebServiceManager.start()` 没有消费已存在的 Doctor 安装事实，安装失败与运行时健康失败被合并成同一个超时表象。
- 授权安装首次失败为 `node_version_unsupported`：`rwb` 使用 Codex bundled Node 24，而安装器错误读取 PATH Node 25。
- Node 修复后首次启动仍失败：安装器已证明新 DSH 闭包，但保留旧 `runtime/build-lock.json`，Doctor 仍误报 `ok:true`。

## 实现

- `start()` 在任何 spawn 前复用 Doctor 的安全化安装投影。
- 安装未就绪时记录稳定日志事件，返回精确 issue code、macOS/Windows 安装器入口和 Doctor 复核命令。
- 为 service-manager 源码与直接回归测试增加精确增量验收路由，避免测试文件误落入未知 L4，同时确保纯生产改动会运行对应 Python 测试。
- 安装器使用显式参数 → `RESEARCH_NODE_BINARY` → 可执行 Codex bundled Node → PATH 的选择顺序，并把选中 Node 置于构建子进程 PATH 首位。
- 安装事务用已验证 DSH state 原子刷新 0600 Runtime build lock；Doctor 校验该锁并投影 `runtime_lock_matches` / `dsh_runtime_lock_mismatch`。

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
- 公开安装入口 `./setup-web.sh --no-start` 在锁定依赖、CJPY 0.5.2、Node 24.19.0 与固定 DSH 上通过；Doctor `ok:true` 且 `runtime_lock_matches:true`。
- 实际生命周期通过：首次 start、幂等 start、restart、stop→start、Runtime SIGTERM 后仅重建 3081、外部 3081 占用时拒绝且不误杀。
- HTTP 根页面 200，Runtime API `connected=true`、`health_check_passed=true`；Codex 内置浏览器可见 FinGPT、研究输入、模型目录、发送按钮与 Skill 入口，刷新后的异步 catalog 最终恢复可用状态。
- 安装与安全修复后的本地闭包：policy 28/28、service-manager 34/34、setup-web 30/30、architecture 62/62、protocol 19/19、L4 local 75/75、Project Constraints 0 violations；Ruff、isort、diff-check、Black 通过。
- 增量策略对安装脚本与测试使用显式 `research-web-installation` L4 路由，必跑 setup-web Python 回归，并新增原生 macOS/Windows `research-web-bootstrap` 外部门；最终计划无 unknown/uncovered risk。
- 第二轮独立审查发现 Runtime build-lock 父目录 alias 与浮点文件数可绕过；新增 POSIX no-follow dir-fd / Windows reparse 安全边界、严格四字段与整数校验，并以 runtime/data-parent symlink 和浮点负测锁定。
- 最终定点复核进一步发现构造器 `.resolve()` 会抹去预先存在的 data alias；data_home/data_root 现保留未解析绝对路径并在 IO 前逐级拒绝 alias，对应构造前 writer/reader 负测通过。
- 首次远端 Bootstrap 的 macOS 安装成功但启动门失败；clean runner 上嵌套 DSH 目录先创建了 0755 data home，新 parent-private 门按设计拒绝。repair 在写锁前仅把当前用户拥有的产品 data home 收紧为 0700，并新增回归；不放宽 alias/owner 边界。
- repair commit `b36fb0ee6be4cd13b19b89311adfed82bc129f9d` 已发布到 `origin/master`。Project Constraints run `35836550928`、Research Web Checks run `35836550964` 均成功。
- Research Web Bootstrap run `35836550986` 的 macOS job 首次即成功；Windows 首次冷启动在异常慢 runner 上超过固定 35 秒窗口而失败，同一 run 的 failed-job 原位重跑（attempt 2）在全新 Windows runner 上 8 分 50 秒成功。首次失败及重跑成功均保留为证据，没有把失败记录改写成一次通过。
- 独立 Windows local integrations run `35835140845` 成功；最终远端 Bootstrap 同时包含 macOS 与 Windows 安装、启动、Doctor、HTTP 与清理成功证据。

## 远端集成结果

- 本功能分支基线之后 `origin/master` 前进到 `e3193f4f`；`iteration-delivery --prepare` 已无损集成并保留 `.ai/reports/2026-09-23-codex-token-ab.md`。
- merged result 使用 19 个真实 changed files 重新生成 plan/receipt 并重跑全部本地 L0–L4；publish 后三个必需外部门均通过。
- 当前实现远端提交为 `b36fb0ee6be4cd13b19b89311adfed82bc129f9d`；本报告与 receipt 的收尾提交只记录已发生的交付证据，不改变运行时行为。

## 架构判断

进程拓扑、HTTP API、DSH 协议、Tabbit 授权、框架与集成协调器关系均未改变；变更把既有安装事实提升为进程创建前的失败关闭门，并让安装器、启动器和 Runtime lock 消费同一已验证 Node/DSH 闭包。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Startup now consumes existing Doctor installation facts before spawning processes; runtime topology and API relationships remain unchanged.","diagrams":[]} -->
