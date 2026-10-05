# Research Web 启动、诊断与恢复稳定性设计

## 状态与决策

- 设计于 2026-09-29 获用户批准。
- 模型服务未配置或不可用不阻止 Research Web 启动；Web 与设置页必须仍可访问，Doctor 单独报告模型问题。
- 当前阶段保持 Web-only。Windows Web 自动验证继续暂停，不运行也不声明通过。

## 背景与当前证据

现有服务管理器已经具备 PID 命令签名、固定 3081/8088、DSH 认证健康检查、启动失败回滚、独立进程 session、stale dead-PID 清理，以及 DSH ready 后才启动 Web、Web health 通过后才打开浏览器的基本顺序。2026-09-23 的 restart/刷新稳定性工作也已经把活动研究判断改为 DSH 权威状态，并修复前端连接中投影。本设计保留这些现有边界，不重新实现第二套管理器；它们仍须在本轮最终验收中重新证明。

本轮在当前 `master` 上重新得到以下事实：

1. checkout 的 `.venv` 目录存在但缺少可执行 Python；`./rwb web status` 与 `./rwb web doctor --json` 均在进入 CLI 前退出，只返回“Python 环境不存在”。
2. 绕过包装器、用保留环境直接调用管理器时，Doctor 能报告 `environment_not_owned`，说明诊断逻辑存在但统一入口无法到达。
3. 当前 Doctor 能显示 Node `v25.9.0`，却只检查可执行文件是否存在，没有把安装合同不支持的 Node major 单独诊断出来。
4. 旧 state 记录指向已经退出的 PID；现有管理器能够确认 PID 不存在并清理 state，这一安全行为应保留。
5. 一个保留环境没有 pytest，另一个 pytest 因 `pluggy._manager` 缺失而无法加载，证明“环境缺失”“环境残缺”“依赖损坏”必须是不同诊断。
6. 当前 Web health 只检查 `/api/research/runtime` 的 `connected=true`，不能证明首页和关键静态资源可读取。
7. 已归属但无响应的进程会被 `start` 复用，然后等待超时；普通 `start` 不会协调恢复这种卡死状态。
8. Doctor 在读取 service state 发生异常时会把两个服务统一投影为 stopped，丢失 PID、归属、权限或状态损坏的真实原因。

## 目标

1. `./rwb web start` 在受支持且安装完整的环境中稳定建立 DSH、Web、首页和关键静态资源的可访问状态，随后才打开浏览器。
2. `./rwb web status` 与 `./rwb web doctor --json` 在 checkout Python 环境缺失或损坏时仍可作为统一诊断入口。
3. 所有生命周期判断使用同一个事实链：state → PID → 命令归属 → 端口 → 协议/HTTP → ready。
4. 死亡进程留下的 stale state 可恢复；归属明确但失去健康的进程可有界重建；归属不明的 PID 或端口始终失败关闭。
5. 错误投影能区分 Python、Node/DSH、端口、PID/state、权限、Runtime 文件、配置、模型、代理/网络、DSH health、Web/API/静态资源 health。
6. 后台进程在启动终端退出后继续运行，正常 stop/restart 不残留旧进程或陈旧状态。

## 非目标

- 不新增常驻系统守护进程、登录项、数据库或公开网络监听。
- 不自动安装 Python、Node 或其他依赖；安装仍只由公开 `setup-web` 入口执行。
- 不通过真实模型生成请求验证 API Key，不产生潜在计费；模型目录或现有只读 Runtime 事实只能证明配置/目录状态。
- 不接管、复用或终止无法证明属于当前 Research Workbench checkout 的进程。
- 不改变 DSH 源码、3080 服务、秘密存储、活动研究重启门禁或 `--force` 的显式语义。
- 不重做已经交付的会话目录并发和前端渐进加载修复。

## 选定方案

采用“轻量启动前诊断 + 单一服务探测模型 + 生命周期协调恢复”。

不采用以下方案：

- **只修 `service_manager.py`**：`.venv` 缺失时包装器仍在管理器加载前失败，Doctor 无法成为标准入口。
- **把 PID 或端口当作健康**：无法区分僵死进程、foreign listener 与真实协议 ready，违背目标的事实链。
- **引入常驻守护进程**：会新增安装、升级、权限、开机启动和跨平台维护面，当前目标不需要。
- **启动失败后无条件 kill/restart**：可能误杀 PID 重用或 foreign listener，破坏现有 fail-closed 所有权边界。

## 架构与组件

### 1. 轻量启动前诊断

在稳定入口包内增加仅使用 Python 标准库的 bootstrap 模块，并由 `rwb`、`rwb.cmd` 在 checkout `.venv` 缺失、无可执行 Python 或无法完成最小导入时调用。包装器使用与安装器一致的系统 Python 发现规则；若机器上连可用系统 Python 都没有，则由 shell/batch 返回稳定的 `python_runtime_unavailable` 文本错误和安装指引。

bootstrap 只处理以下公开动作：

- `web status`：返回 checkout 环境事实，以及通过 state、PID、loopback 端口和有界 HTTP 请求能够安全确认的服务事实。
- `web doctor [--json]`：返回安全化诊断 schema、稳定 issue code 和 `setup-web` 修复入口。
- 其他命令（包括 `web start/restart/stop`）：失败并返回明确的 Python 环境 issue；不尝试用未受管 Python 启动产品服务。

bootstrap 不读取凭据、auth cookie、用户正文或日志正文，不执行安装，不清理 state，不杀进程。正常 `.venv` 可用时仍委托既有 `research_workbench_entrypoint`，避免形成第二套完整 CLI。

Python 环境至少区分：

- `python_environment_missing`：预期解释器不存在；
- `python_environment_incomplete`：目录存在但解释器、ownership marker 或关键结构缺失；
- `python_environment_unusable`：解释器存在但启动或最小入口导入失败；
- `python_runtime_unavailable`：系统也没有可用于 bootstrap/安装的 Python。

### 2. 单一服务探测模型

在 `app/research_web/service_manager.py` 内建立一个只读 service probe，供 `status`、`doctor`、`start`、`restart` 和 rollback 复用。每个服务保留兼容字段 `running`、`healthy`、`pid`、`port`，同时增加以下事实：

```text
state: missing | valid | stale | invalid
process: missing | alive | inaccessible
ownership: owned | foreign | unknown
port: closed | listening
protocol: not_run | passed | failed
ready: true | false
issues: [stable_code, ...]
```

探测顺序严格固定：

1. 有界、安全地读取 state 并验证 schema、项目根、数据根、command fingerprint 与 signature。
2. 检查 PID 是否存在并排除 zombie。
3. 对存活 PID 核对实际命令行归属；无法读取命令行不是 owned。
4. 检查 loopback 端口是否监听，但不把监听者自动归属于 state PID。
5. owned Runtime 执行带认证的 `session/list` 协议检查。
6. owned Web 检查 Runtime API、首页和固定关键静态资源。
7. 只有前置事实均通过才设置 `ready=true`。

probe 本身只读，不清理或改写 state。`status` 不再把异常压缩为 stopped，Doctor 逐服务保留 probe 结果；一个 state 损坏不会抹掉另一个服务的事实。stale 或损坏 state 只由持有 lifecycle lock 的修改命令协调处理。

### 3. 启动与恢复协调器

所有修改生命周期的命令使用无新依赖的跨平台排他锁，防止两个 `start/restart/stop` 同时改写 state。锁记录仅包含安全 owner PID 与时间；只有确认 owner PID 已死亡时才允许恢复 stale lock。锁争用返回 `lifecycle_busy`，不等待到用户误以为命令卡死。

`start` 对每个组件执行 reconcile：

- **ready owned**：幂等复用，不更换 PID。
- **dead + stale state**：确认 PID 不存在且端口关闭后原子移除 state，再启动。
- **invalid state without a live PID or listener**：把原文件原子隔离为权限 `0600` 的有界诊断副本，再重建；隔离只保留最近一份，不把命令或路径复制到 CLI 输出。
- **alive owned but unhealthy**：有界停止并再次确认归属，然后重建。Runtime 重建前先停止 owned Web，避免 Web 持有旧 Runtime 连接；之后按正常顺序恢复二者。
- **state invalid with live/unknown PID or listening port**：返回 `state_invalid_live_pid` 或 `state_invalid_port_listening`，不清理、不终止。
- **port listening without a ready owned service**：返回 `port_in_use_unknown`，不复用、不终止。
- **进程在等待 ready 期间提前退出**：立即返回 `runtime_process_exited` 或 `web_process_exited`，不等满健康超时。
- **进程仍存活但超时**：返回 `runtime_health_timeout` 或对应 Web readiness issue，并指向对应日志。

启动失败只回滚本次创建或本次确认归属后重建的进程。既有 ready 服务和 foreign/unknown 进程不进入 rollback。

### 4. Web ready 与浏览器时机

Runtime ready 仍以已认证 DSH `session/list` 为准。Web ready 改为三项均通过：

1. `/api/research/runtime` HTTP 2xx、JSON schema 有效、`connected=true` 且 `health_check_passed=true`；
2. `/` HTTP 200，并含当前 Research Web 壳的稳定标记；
3. `/static/app.mjs` HTTP 200、内容类型和最小内容标记正确。

检查使用直接 loopback HTTP，不继承 HTTP(S) 代理。只有 Runtime 与 Web 均 `ready=true` 后才调用 `webbrowser.open`。浏览器调用返回 false 或抛出异常时，服务保持运行，结果包含 `browser_open_failed` warning 和可复制 URL；不能把已健康服务回滚成不可用。

### 5. 安装、Node、模型与代理诊断

安装诊断继续复用 manifest、Web lock、CJPY、固定 DSH commit/closure 和 runtime build lock。Node 版本规则提取为安装器与 Doctor 共用的标准库合同：只接受 Node 22.19+ 的 22 系列或 Node 24.x，拒绝 23、25+ 和无法解析的版本，避免两个入口再次漂移。诊断补充：

- Node 可执行文件不存在：`node_unavailable`；
- Node 版本不能解析：`node_version_invalid`；
- Node major 不在当前安装合同支持范围：`node_version_unsupported`；
- Runtime build/auth/control 文件缺失、损坏或权限不安全时使用各自稳定 issue，不合并为 `dsh_not_ready`；
- 私有目录/state/lock 无法安全读取或写入时使用 `permission_denied` 或更具体的安全 issue。

当 Web ready 时，Doctor 从现有 Runtime API 和模型目录读取非计费事实：

- provider/model 未设置：`model_configuration_missing` warning；
- credential 未配置：`model_credential_missing` warning；
- 模型目录请求失败或返回 provider failure：`model_catalog_unavailable` warning。

上述模型 warning 不影响 `start` 成功、Web ready 或 Doctor 的安装 `ok`；Doctor 另给出 `product_ready` 与 `model_ready`，避免一个 `ok` 同时承担安装、服务和模型三种语义。

代理诊断只判断是否设置了代理、loopback 是否明确绕过及直接 loopback 探测是否成功，不输出代理 URL：

- 配置代理但 `NO_PROXY/no_proxy` 未覆盖 `127.0.0.1` 与 `localhost`：`loopback_proxy_bypass_missing` warning；
- 直接 loopback 失败时归入相应端口/HTTP health issue；代理 bypass warning 作为并列配置事实，不把未经观察的失败归因给代理。

## CLI 与 JSON 合同

`status` 人类输出按 Runtime/Web 分别显示：state、process、ownership、port、protocol 和 ready，并在末尾列出稳定 issues 与 URL。`doctor --json` 保留现有安全字段，并新增：

```json
{
  "schema_version": 2,
  "installation_ok": false,
  "product_ready": false,
  "model_ready": false,
  "issues": [],
  "warnings": [],
  "services": {
    "runtime": {},
    "web": {}
  }
}
```

兼容期继续提供旧 `ok`、`running`、`healthy`、`pid`、`port`；`ok` 保持安装是否就绪的既有含义。所有 issue/warning code 使用 allowlist，不把异常正文、命令行、路径、环境变量值、Cookie、Token 或文件正文写入 JSON。

CLI 错误由带 `code`、安全 message 和可选 role 的 `ServiceManagerError` 生成。人类输出包含下一步命令；机器输出只含稳定字段。`status`、`doctor` 与 `doctor --json` 只要成功形成诊断投影就退出 0，问题通过稳定字段表达；只有 CLI 自身无法形成投影时才非零。`start/restart/stop` 未完成请求动作时保持非零。这样调用方不需要从 stderr 猜测诊断，同时自动化仍能从 `installation_ok/product_ready/model_ready` 判断状态。

## 错误处理与日志

- 每个 lifecycle 决策记录结构化事件、role、issue code、阶段和耗时；不记录 secrets、完整环境或日志正文。
- health polling 保存最后一个稳定失败类别，但只在最终失败或状态变化时记录，避免每 250 ms 刷屏。
- state 清理、锁恢复、spawn、ready、browser open、rollback 和 stop 均有成功/失败日志。
- 错误必须保留底层 exception chaining，但 CLI 只显示安全化信息。
- 读取日志只作为用户后续定位入口；状态机不通过模糊日志文本决定进程归属。

## 测试设计

### 1. RED → GREEN 单元与合同测试

1. `rwb` / `rwb.cmd` 与 bootstrap：
   - `.venv` 缺失、目录残缺、解释器不可启动、最小入口导入失败；
   - `status` 和 `doctor --json` 仍返回对应稳定 code；
   - `start/restart/stop` 不使用 fallback Python 操作服务；
   - JSON 不泄漏路径、代理值或凭据；
   - 正常环境仍委托既有入口。
2. service probe：
   - state missing/valid/stale/invalid；PID dead/alive/zombie/inaccessible；owned/foreign/unknown；端口 closed/listening；协议成功/失败；
   - 单项异常不抹掉另一服务事实；兼容字段与新增字段一致。
3. reconcile：
   - 幂等 start 保持 PID；dead stale 恢复；owned unhealthy 有界重建；Runtime 重建带动 owned Web 重连；
   - foreign PID、未知 listener、state invalid live PID 均失败关闭且 kill 调用为零；
   - lifecycle lock 竞争与 stale lock 恢复；rollback 只触及本次 owned 创建集合。
4. readiness：
   - Runtime ready 后才 spawn Web；Runtime API、首页、`app.mjs` 任一失败均不打开浏览器；
   - 浏览器只在完整 ready 后打开；browser open 失败返回 warning 且服务保持 ready。
5. Doctor 分类：
   - Python、Node major、DSH closure/build lock、权限、端口、PID/state、Runtime/Web health、模型配置、模型目录、代理分别得到不同 code；
   - 模型 warning 不改变 `product_ready`；没有真实模型生成调用。

### 2. 真实 macOS 生命周期验收

在隔离数据根和备用端口先完成破坏性故障注入，再对默认公开入口做最终验收：

1. `./setup-web.sh --no-start` 从干净 checkout 完成，Doctor 安装事实通过。
2. `./rwb web start --no-open` 后 3081/8088、Runtime API、首页、关键静态资源通过；启动命令退出后后台 PID 继续存在。
3. 重复 start 保持 PID；stop → start 更换 PID且旧进程退出；普通 restart 更换两个 PID且旧端口释放。
4. 终止 owned Web 后 start 只恢复需要的组件；终止 owned DSH 后 start 安全恢复 Runtime 与 Web 连接。
5. stale state、模拟电脑重启后的 dead PID state、无 live PID/listener 的损坏 state、foreign live PID、带 listener 的损坏 state 和外部端口占用分别得到预期恢复或 fail-closed 结果。
6. 浏览器首次打开、显式刷新和 restart 后刷新均能加载；观察一段稳定窗口，首页和关键资源请求无间歇失败或无限 loading。
7. API Key 未配置时 Web 仍 ready、设置页可用、Doctor 报模型 warning。
8. 最终 `status`、`doctor --json`、PID、端口、HTTP 与 DSH 协议事实一致；最终 stop 后 owned PID 与端口全部消失。

默认用户数据和默认 state 的故障注入必须先备份并可恢复；未知进程或端口只观察、不终止。测试结束恢复用户原始服务运行意图。

### 3. 增量、安装与远端验收

- 根据最终完整 changed set 运行 `scripts/plan_verification.mjs`，按 L0→L4 执行全部返回项并校验 receipt。
- 因为会修改公开包装器、安装/启动契约和跨平台入口，必须核对 `requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py`、`docs/research-web-installation.md` 与 `.github/workflows/research-web-bootstrap.yml`；未变化项也由安装 CI 证明兼容。
- 本地 macOS 验收后，只有在发布获得独立授权并通过 Actions budget 门时，才运行远端 Project Constraints、Research Web Checks 与 GitHub `macos-14` Bootstrap。
- Windows Web 自动验证按当前政策暂停；静态合同和单元测试不等于原生 Windows 验证。

## 文档与交付物

实现时同步：

- `docs/architecture/research-web/01-system.md`：bootstrap、probe、ready 与恢复状态机；
- `docs/architecture/research-web/02-research-runtime.md`：DSH/Web health 与 lifecycle；
- `docs/architecture/research-web/05-security-validation.md`：所有权、锁、fail-closed 与安全输出；
- `docs/research-web-installation.md`：统一诊断入口、issue code 与修复动作；
- `README.md`、`docs/DEVELOPMENT_MAP.md`：公开诊断入口、源码/测试映射和修复路径；
- `docs/generated/py_file_index.md`、`docs/architecture/research-web/architecture-map.json`：登记新增 bootstrap 与共享诊断源码；
- `docs/architecture/research-web/readme-review.json`：记录 README 已同步本次公开 CLI 行为；
- `.ai/reports/`：RED/GREEN、故障注入、真实生命周期、浏览器、规划器、receipt 和未验证外部门。

任何未实际执行的浏览器、干净安装、CI 或 Windows 检查都保留为未验证，不能从单元测试推断通过。
