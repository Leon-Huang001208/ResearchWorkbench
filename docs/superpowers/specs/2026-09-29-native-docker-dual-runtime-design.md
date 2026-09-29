# Research Workbench Native + Docker 双运行时设计

## 背景与目标

Research Workbench 当前交付的是本地优先的 Research Web。公开入口
`setup-web.sh`、`setup-web.cmd` 和 `scripts/setup_web.py` 创建 checkout 专属
`.venv`，安装带哈希的 `requirements/web.lock`，构建固定提交的 DSH，然后由
`rwb web` 管理两个回环进程：DSH `127.0.0.1:3081` 与 FastAPI
`127.0.0.1:8088`。

本设计在不删除或弱化该 Native 路径的前提下增加正式 Docker Runtime。最终产品仍是
一套 Research Workbench、一套源码、一套依赖事实源和一个 `rwb` 用户入口；Docker
只是另一种安装与进程生命周期实现，不是第二套产品或业务实现。

目标包括：

1. 普通用户可显式选择 Docker Mode，避免在宿主安装 Node、编译 DSH 原生模块或维护
   checkout `.venv`；Native Mode 继续服务开发、调试和宿主能力集成。
2. `rwb runtime` 提供模式查询与安全切换，`rwb web` 在两种模式下保持稳定语义。
3. 两种模式共享研究会话、附件、数据集、产物、能力状态及需要共享的 DSH 持久数据，
   但不共享 PID、容器状态、auth、overlay、build lock 或运行日志所有权。
4. Docker image 直接消费现有 Python lock 与固定 DSH/pnpm lock，不维护第二份业务依赖清单。
5. Doctor、日志、安装器、验证路由、条件 CI 和用户文档理解当前 runtime，并继续区分
   核心运行健康与宿主能力是否可用。

## 当前实现审计

### 安装与入口

- `setup-web.sh` 与 `setup-web.cmd` 只负责选择 Python 3.12 并调用
  `scripts/setup_web.py`。
- `SetupWebInstaller` 在仓库内创建 `.venv`，按 `requirements/web.lock` 安装 Python
  依赖，验证 vendored CJPY，克隆并构建固定 DSH，然后写入
  `~/.research-workbench/install/manifest.json`。
- `rwb` 与 `rwb.cmd` 当前必须先找到 checkout `.venv`；因此仅增加 Click 子命令仍不能
  让“没有 Native 安装的 Docker 用户”使用统一 CLI。

### 服务生命周期

- `WebServiceManager` 生成 DSH 与 Web 的命令、写入 PID/命令指纹、验证归属、检查端口、
  创建后台进程、等待健康、停止和回滚。
- DSH 必须先健康并建立受限 auth record，Web 才启动；Web 通过 auth record 调用 DSH。
- DSH 与 Web 的内部 URL、auth authority 和 DSH CLI 当前均假定同一主机上的 loopback。
- `status`、`stop` 与 `restart` 只操作 PID、命令签名、项目根和数据根同时匹配的进程；
  未知端口占用失败关闭。

### 目录分类

当前 canonical home 为 `~/.research-workbench`：

| 路径 | 分类 | 双运行时策略 |
| --- | --- | --- |
| `research-web/` 下的会话、附件、数据集、产物与能力状态 | 持久用户数据 | Native 与 Docker 共享 |
| `research-web/runtime/home/` | DSH Profile、session/history 等持久运行数据 | 两种模式顺序共享 |
| `research-web/runtime/work/` | DSH 工作目录 | 两种模式顺序共享；禁止并发使用 |
| `research-web/runtime/auth.json` | 短期认证状态 | 不再作为 Docker 状态位置 |
| `research-web/runtime/overlay.yml` | 源码与运行模式相关的生成配置 | 按 runtime 隔离 |
| `research-web/runtime/build-lock.json` | Native 安装与 DSH 构建证据 | Native 保持原位；Docker 使用独立 image/build 证据 |
| `run/*.json` | Native PID 与命令归属 | 保持 Native；Docker 使用 `run/docker/` |
| `logs/*.log` | Native 进程日志 | 保持 Native；Docker 日志由 Compose 提供 |
| `install/manifest.json` | Native 安装摘要 | 保持兼容；Docker 使用独立安装摘要 |
| 系统凭据库 | secrets | Native 保持现有实现；Docker 使用私有文件 backend |

### 验证现状

- `.agents/verification-policy.json` 是唯一 changed-file 路由真源。
- 服务管理器与安装器已经分别映射到 focused Python tests，并因公开安装与服务生命周期
  影响升级到 L4/full-delivery。
- 当前 `Dockerfile`、`compose.yaml`、`docker/**` 与新的 runtime 路径会落入
  `unknown_path`。正式实现必须增加明确规则和合同测试，不能依赖 fallback 长期存在。
- 基线 Node 合同测试为 147/147；本机没有可用 pytest 环境，且本任务未获新依赖安装授权。
- 本机为 macOS arm64，但 Docker CLI/daemon 尚未安装，因此本地容器 build/start 证据目前不可得。

## 方案比较

### 方案 A：单容器 + 宿主轻量 bootstrap（选定）

一个容器内运行 DSH 与 Web，DSH 保持只监听容器 loopback，Web 监听容器
`0.0.0.0:8088` 并映射到宿主 `127.0.0.1:8088`。容器 PID 1 使用专用 supervisor
按现有顺序启动、检查与停止两个子进程。宿主 stdlib-only bootstrap 在 `.venv` 不存在时
仍能读取模式、调用 Compose、执行 status/doctor/logs 与安全切换。

优点：保留现有 loopback/auth 契约；容器边界最少；可复用 process specification 和健康逻辑；
Docker 用户无需宿主 Node、DSH build toolchain 或 `.venv`。缺点：容器内需要一个很小的双进程
supervisor，但其职责仅是进程生命周期，不承载业务逻辑。

### 方案 B：Web 与 DSH 双容器（不采用）

该方案需要把 DSH 从 loopback 改为容器网络监听，并重新设计 auth authority、Cookie、auth file
共享与网络暴露。它在首个 Docker Runtime 中引入不必要的安全和协议变化，且两个组件本来就是
一个按顺序启动、共同升级的产品 Runtime。

### 方案 C：宿主 Native manager 混合管理容器进程（不采用）

该方案让宿主 PID manager 同时理解本机进程和 Docker 容器，使 ownership、恢复、端口冲突和
升级状态交叉。Docker 用户仍依赖完整 Native 环境，违背 Runtime 解耦目标。

## 总体架构

```text
setup-web.sh / setup-web.cmd / python scripts/setup_web.py
                           │
                           ▼
                  Runtime mode bootstrap
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       Native installer          Docker installer
       .venv + fixed DSH         image + compose
              │                         │
              └────────────┬────────────┘
                           ▼
                         rwb
                           │
                     Runtime Router
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       NativeRuntime              DockerRuntime
       WebServiceManager          Compose controller
              │                         │
        3081 + 8088          one container: 3081 + 8088
              └────────────┬────────────┘
                           ▼
        ~/.research-workbench/research-web persistent data
```

运行时抽象位于进程与安装边界，不进入 FastAPI 业务代码。Research Web routes、Service、
DataHub、框架、能力、会话和 DSH 工具不得出现散落的 `if docker` 分支。

## 组件设计

### 1. Runtime mode store

在既有 `~/.research-workbench/install/` 中增加独立、版本化的 runtime mode record。它至少包含：

- schema version；
- `mode: native | docker`；
- 随机生成且持久的 installation ID，用于 Compose project/label ownership；
- 最后修改时间与写入方版本；
- Docker image/install 摘要的引用，不包含凭据或用户内容。

文件缺失时必须返回 `native`，且不得因读取失败静默改写。写入采用现有私有目录、普通文件、
无 alias/reparse point、`0600` 与原子替换边界。未知 mode、损坏文件或不安全路径失败关闭。

`install/manifest.json` 继续只描述 Native 安装。Docker 安装摘要写入单独文件，记录 code commit、
image ID、Python/Node 主版本、Web lock 摘要、DSH commit/closure、Compose schema 与构建时间；
不记录 secret、完整宿主路径或容器环境。

### 2. Host bootstrap 与统一 CLI

宿主继续要求 Python 3.12，因为公开安装器已经以它作为跨平台底层入口；Docker Mode 不要求宿主
Node、C++ build tools、DSH 或 checkout `.venv`。

`rwb`/`rwb.cmd` 先调用一个只依赖 Python 标准库的 bootstrap：

1. 解析项目根和 runtime mode record；
2. 对 `runtime ...` 以及 Docker Mode 的 `web ...` 使用 stdlib controller；
3. 对 Native Mode 的 `web ...` 和全部既有命令 `exec` 到 checkout `.venv` 中现有
   `research_workbench_entrypoint`；
4. Native mode 缺 `.venv` 时保持现有明确错误和安装指引；
5. Docker mode 不得导入 Click、FastAPI、structlog 或其他 Web lock 包。

新增稳定命令：

```text
rwb runtime status [--json]
rwb runtime use native [--stop-current]
rwb runtime use docker [--stop-current]
rwb web start [--no-open]
rwb web stop
rwb web restart [--force] [--no-open]
rwb web status [--json]
rwb web doctor [--json]
rwb web logs [--follow] [--tail N]
```

既有文本输出保持人类可读；现有 Doctor JSON 字段保留并只做 additive 扩展。Docker status 中
`services.runtime/web` 仍存在，端口仍为 3081/8088；PID 不可用时为 `null`，并增加安全化的
container state、runtime mode 与 ownership 事实，不返回容器环境或 secret mount 内容。

### 3. Runtime 接口与实现

Runtime controller 的公共能力为：

```text
preflight
install
start
stop
restart
status
doctor
logs
health
```

`NativeRuntime` 是现有 `SetupWebInstaller` 与 `WebServiceManager` 的薄适配，不复制其 PID、
命令签名、auth、健康或失败回滚实现。现有类可按职责小幅提取共享 process specification，
但 Native 默认路径、manifest、错误码与命令行为保持兼容。

`DockerRuntime` 只负责：Docker/Compose 预检、Compose project ownership、build/up/down/restart、
容器状态、health、日志与 Docker 安装摘要。所有 subprocess 使用参数数组、明确 cwd、timeout、
最小环境和结构化日志；stderr 经安全摘要后进入错误，不记录完整环境。

两种实现都返回同一内部 status/doctor 数据结构，由 CLI formatter 输出。FastAPI 本身不选择 runtime。

### 4. Docker image 与 Compose

新增：

```text
Dockerfile
compose.yaml
.dockerignore
docker/entrypoint.sh
docker/supervisor.py
docker/healthcheck.py
```

镜像设计：

1. 固定 Python 3.12 patch image 与受支持 Node 24 patch image；最终基础为 slim Debian。
2. multi-stage 复制 Node/Corepack，并在 builder 中直接使用 `requirements/web.lock --require-hashes`、
   vendored CJPY、固定 DSH commit 和 DSH 自身 `pnpm-lock.yaml --frozen-lockfile`。
3. Python 依赖安装到 image venv；不生成 `requirements/docker.txt`。
4. DSH commit、pnpm version、closure 和 Python/Node 版本与现有安装 contract 保持一个机器真源；
   Dockerfile 无法避免的 base tag 表示由合同测试机械比对，不能独立漂移。
5. runtime stage 只复制应用、venv、固定 DSH build、vendored runtime resources 和必要静态文件；
   不复制 `.git`、测试产物、`.venv`、日志、报告、用户目录、凭据或本机配置。
6. 运行用户为固定非 root UID/GID。entrypoint 在启动前验证 bind mount 可写性和私有权限，
   不用 root 自动修复任意宿主文件。
7. 容器内 DSH 仍绑定 `127.0.0.1:3081`；Web 绑定 `0.0.0.0:8088`。Compose 只发布
   `127.0.0.1:8088:8088`，不发布 3081。
8. image `HEALTHCHECK` 同时核对已认证 DSH session/list 与 Web runtime API；任一失败即 unhealthy。

Compose project 名由 installation ID 派生，controller 同时核对 Compose labels、image labels 和
数据根标识。`stop/restart/logs` 不得对仅同名但 ownership 不匹配的容器操作。

### 5. 容器 supervisor

`docker/entrypoint.sh` 只验证必要环境并 `exec` Python supervisor，使 supervisor 成为 PID 1。
Supervisor 使用从 Native manager 提取的共享 process specification，但采用容器生命周期：

1. 创建 Docker 私有 runtime state 目录；
2. 启动 DSH，等待 auth 与真实健康；
3. 启动 Web，等待 `/api/research/runtime`；
4. 保持前台，监控任一子进程异常退出；
5. 接收 SIGTERM/SIGINT 后先停 Web、再停 DSH，等待有界时间后才 SIGKILL；
6. 启动中任一步失败时回滚本轮子进程并返回非零；
7. 子进程 stdout/stderr 写容器 stdout/stderr，供 `docker compose logs` 统一读取。

Supervisor 不实现安装、业务路由、研究协议、session 存储或第二套 health 语义。

### 6. 数据、状态与切换

Compose 通过 controller 提供的非秘密环境挂载：

- canonical `~/.research-workbench/research-web` → `/data/research-web`；
- `~/.research-workbench/run/docker/<installation-id>` → `/state`；
- `~/.research-workbench/secrets/docker/<installation-id>` → `/run/rwb-secrets`。

Docker 的 auth、overlay、容器启动 lock 与 health state 写入 `/state`；Native 继续使用当前 PID 和
状态文件。`DSH_HOME` 指向共享数据根中的既有持久 home，因此顺序切换保留 session/profile；
同时运行被切换门和端口门共同禁止。

`rwb runtime use TARGET` 的确定性算法：

1. 验证 target 值与 target preflight；target 不可用时不停止当前 runtime。
2. 读取 mode record，并独立检查 Native ownership state、Compose ownership state 和 8088/3081。
3. 若当前或另一 runtime 正在运行且未传 `--stop-current`，返回稳定错误码并不改 mode。
4. 传入 `--stop-current` 时，只停止 ownership 完全匹配的当前 runtime；无法证明归属则失败关闭。
5. 等待两个端口释放并复核服务已停；超时或未知占用不写 mode。
6. 原子写入 target mode；`use` 本身不自动启动 target，避免切换与启动失败形成半状态。
7. 后续 `rwb web start` 只启动已选择 runtime。

相同 target 的 `use` 为幂等操作。CI 始终显式传 mode/flags，不依赖 prompt；本设计不增加交互式
选择器，避免已有无参数安装突然等待输入。

### 7. Secrets 与宿主能力

禁止把 secret 放入 Dockerfile、build arg、image layer、Compose committed value、容器环境、
Docker label、安装摘要或日志。

Docker 使用专用私有文件 credential backend：

- 宿主目录逐级验证为当前用户拥有、普通目录、无 symlink/reparse point，POSIX 为 `0700`；
- credential 文件使用不可预测 ID、`0600`、原子写入，索引不保存 secret value；
- 容器只挂载当前 installation ID 的目录；路径可由 inspect 看到，内容不能通过 inspect 获得；
- Web Settings 通过现有 credential store 接口读写该 backend，不把 value 返回浏览器；
- 可选只读 Compose secret file 可在启动时导入内存，但不复制进 canonical 数据或安装摘要；
- 日志只记录 provider、operation、结果和稳定错误码。

Native 继续使用操作系统 keyring。Docker Doctor 必须把核心 runtime health 与 capability 分开：

- Docker Engine/Compose/container/Web/DSH/data/volume 可健康；
- Wind、iFinD、Office COM、本机浏览器、Windows SDK、宿主 keyring 等默认报告
  `unavailable_in_docker` 或 `host_bridge_not_configured`；
- 这些可选能力缺失不阻止核心 Research Web 启动，也不能被伪报为 callable。

### 8. Setup 集成与诊断

公开入口增加：

```text
setup-web.sh --runtime native|docker
setup-web.cmd --runtime native|docker
python scripts/setup_web.py --runtime native|docker
```

兼容规则：

- 未传 `--runtime` 时仍为 `native`；现有 `--repair`、`--no-start`、`--check-only` 保持语义。
- `--runtime native` 走当前完整安装流程。
- `--runtime docker` 不创建或删除 `.venv`，不要求宿主 Node/C++ build tools；它检查 Docker、
  构建 image、写 Docker install 摘要和 mode record，并按 `--no-start` 决定是否启动。
- 已显式传 runtime 时不询问；CI 全部显式传入。

Docker preflight 使用稳定 issue code 区分：

```text
docker_cli_missing
docker_daemon_unavailable
docker_compose_missing
docker_architecture_unsupported
docker_data_home_unsafe
docker_port_8088_occupied
docker_port_3081_conflict
docker_ownership_mismatch
docker_build_not_ready
```

错误文本提供平台对应 remediation，但不自动安装 Docker Desktop、改变系统配置或删除容器/volume。

### 9. Doctor、status、health 与 logs

Native Doctor 现有字段与判断保持不变，只增加 `runtime_mode: native` 和安全化 runtime 摘要。

Docker Doctor 至少报告：

- runtime mode 与 mode record 安全性；
- Docker CLI、daemon、Compose 版本和支持架构；
- image ID/labels 与安装摘要匹配；
- Compose ownership 与 container state/health；
- Web 8088 与内部 DSH 3081 健康；
- canonical data bind 与 Docker state/secret mounts 是否匹配；
- 端口状态；
- host integrations 的明确 unavailable/未配置状态。

Doctor JSON 保持 path-free、credential-free，并保留现有 `schema_version`、`ok`、`issues`、
`services`、`python`、`node`、`cjpy`、`dsh`、`data`。Docker 不适用的 Native 字段用明确
`applicable: false` 扩展说明，不用虚假版本填充。`ok` 只表示所选 runtime 核心可启动/健康；
可选 host capability 单独汇总。

`rwb web logs`：

- Native 从已知 `logs/runtime.log` 与 `logs/web.log` 有界读取，拒绝 alias，不扫描任意路径；
- Docker 调用当前 installation ID 对应的 `docker compose logs`；
- `--tail` 有上下限，默认有界；`--follow` 显式进入持续输出；
- 不读取或输出 credential files、完整环境、auth Cookie 或 Docker inspect Env。

## 依赖单一事实源

1. Python direct dependency 继续只在 `requirements/web.in` 定义，锁定只在
   `requirements/web.lock`；Native 与 Docker 都使用同一 lock 和 hash 校验。
2. CJPY 继续使用同一 vendored wheel/manifest 与摘要。
3. DSH remote、commit、pnpm version、closure count 与受支持 Python/Node 版本移入现有
   `runtimes/` 下的机器可读 runtime contract；Native installer、service manager、Docker build
   helper、Doctor 和测试共同读取。
4. DSH 自身 Node package 依赖继续由固定提交内的 `pnpm-lock.yaml` 管理。
5. Docker base image tag/digest 是平台制品选择，不复制业务 dependency manifest；合同测试保证其
   Python/Node 主版本与 runtime contract 相符。
6. 不新增 `requirements/docker.txt`、`requirements/native.txt` 或第二份 pnpm lock。

## 验证路由与 CI

### Verification Router

在 `.agents/verification-policy.json` 增加明确组件：

- Docker packaging：`Dockerfile`、`compose.yaml`、`.dockerignore`、`docker/**`；
- runtime mode/router/bootstrap；
- Docker/Native runtime tests；
- Docker workflow；
- setup/launcher/service manager/requirements 继续保留既有高风险规则。

新路径不能继续出现 `unknown_path`。策略仍按 complete changed set、耦合、风险、平台和 runtime
合并：纯 Docker 文档只走文档闭包；Dockerfile/Compose 至少走 packaging contracts 和 container
smoke；runtime router、setup、dependency 或 CI 变更保持 L4/full-delivery。Docker 路由不能引入
Desktop/Tauri gates。

### 条件 Docker CI

新增 Docker workflow，只在 Docker packaging、runtime router/bootstrap、setup、Web lock、固定
DSH contract 或自身 workflow 变化时触发；设置 concurrency、cancel-in-progress、timeout 和三天
最小工件。

CI 顺序：

1. `docker compose config`；
2. buildx 构建 `linux/amd64` 与 `linux/arm64`；
3. 对 amd64 与 arm64（QEMU）分别执行必要的 startup/health smoke；
4. HTTP 8088 与内部已认证 DSH health；
5. stop、restart、幂等 start；
6. 写入一条无秘密 persistence fixture，down/up 后读取；
7. down 后确认容器消失、数据仍存在、端口释放；
8. 保存安全化 Doctor、Compose config 摘要和 health receipt；失败时保存容器日志，先做 secret
   pattern/redaction 检查。

普通 Research Web PR 不形成 Native × Docker × macOS × Windows 全矩阵。现有 GitHub macOS
Native Bootstrap 保留；Windows Web 仍由用户实机/手动 workflow 提供证据，Docker CI 不替代
Windows Native 或 macOS Native。多架构 Linux container 证据只证明对应 Docker image，不证明
Docker Desktop 宿主集成。

## 测试策略

### 单元与合同

1. runtime mode record：缺失默认 native、不安全路径、损坏 schema、原子写和 installation ID。
2. bootstrap：无 `.venv` 的 Docker 命令可用；Native/legacy 命令正确委派；Windows/POSIX 参数
   保真；未知命令和错误 exit code 传播。
3. switching：target preflight、运行中默认拒绝、`--stop-current`、未知 ownership、端口未释放、
   写入顺序和幂等。
4. Docker controller：CLI/daemon/Compose 分类、命令参数、timeout、ownership labels、状态投影、
   日志边界和无 secret 输出。
5. supervisor：启动顺序、DSH 失败不启动 Web、Web 失败回滚 DSH、信号顺序、子进程异常退出和
   health。
6. setup：无参数继续 native；显式 docker 不触碰 `.venv`；`--check-only` 不写入；`--no-start`
   不启动；错误码稳定。
7. Doctor schema：Native backward compatibility、Docker additive fields、capability 与 core health
   分离、path/credential-free。
8. credential backend：目录与文件权限、alias/reparse point、原子写、浏览器不回显、日志无值。
9. dependency contract：Docker/Native 使用同一 Web lock、CJPY、DSH/pnpm contract 与 base 主版本。
10. verification policy/workflow contract：新路径无 fallback、正确 tests/CI、无 Desktop gate、条件
    paths 和成本治理不漂移。

### 本机 macOS 验收

在不安装新依赖的当前环境先完成所有可运行静态/Node/stdlib tests。要声明 Docker Mode 通过，仍需
用户明确授权安装/启用 Docker Desktop，或在已经具备 Docker 的 macOS arm64 主机执行：

```text
setup-web.sh --runtime docker --no-start
rwb runtime status --json
rwb web start --no-open
rwb web doctor --json
rwb web restart --no-open
rwb web logs --tail 100
rwb web stop
```

再完成 Native 回归：现有无参数 setup、start/status/doctor/restart/stop 行为与数据保持。切换测试
必须创建无秘密研究 fixture，Native → Docker → Native 每次都验证读取一致，同时确认 PID/auth/state
互不误判。

### 远端与证据

- 从真实 changed set 生成 L0–L4 plan，逐项执行并创建严格 receipt。
- Python 变更必须有 RED→GREEN、相关 pytest、文档、`.ai/reports` 和完整性检查。
- 本地完成不替代 Project Constraints、Research Web Checks、macOS Native Bootstrap 与条件 Docker
  workflow。
- 未执行的 Windows 实机、Docker Desktop host integration 或远端 gate 明确记为未验证/blocked。
- 发布、push、dispatch 与 cleanup 仍受 `docs/actions-budget.md` 和用户授权约束。

## 分阶段实施

### Phase 1：Docker MVP

建立 runtime contract、Dockerfile、Compose、entrypoint/supervisor、healthcheck 和 Docker packaging
tests。先证明 build、up、DSH/Web health、restart、down；Native 文件与默认行为不变。

### Phase 2：Runtime abstraction

提取共享 process specification，建立 NativeRuntime/DockerRuntime controller 和统一 status model。
Native manager 继续拥有原 PID/ownership 实现；Docker controller 只拥有 Compose lifecycle。

### Phase 3：统一 CLI

加入 stdlib bootstrap、mode store、`rwb runtime`、Docker 路由和 `rwb web logs`。完成安全切换与
无 `.venv` Docker CLI 合同。

### Phase 4：Setup integration

`setup-web.*` 和 `scripts/setup_web.py` 支持 `--runtime`，加入 Docker detection、安装摘要、错误
remediation 和 non-interactive 行为；无参数继续 Native。

### Phase 5：Persistence、secrets 与 switching

完成 Docker credential backend、共享数据/隔离状态挂载、Native ↔ Docker fixture 往返、
ownership/端口冲突与失败恢复测试。

### Phase 6：Minimal Acceptance、CI 与文档

更新 policy、planner contracts、条件 Docker workflow、README、安装/架构/安全/开发地图、
architecture map、README review receipt 与任务证据；执行完整规划闭包和获准的远端交付。

每个 Phase 必须产生可独立验证、可回滚的提交。后续 Phase 不能以掩盖前一 Phase 未完成验收为条件。

## 错误处理与恢复

- Docker target preflight 失败不改变当前 mode，也不停止健康 Native 服务。
- build 失败保留旧健康 image 与 mode，不能把半成品写成 installed。
- Docker start 失败由 Compose/supervisor 清理本轮容器，不删除 named/bind data 或 secret。
- runtime switch 只有在旧 runtime 已确认停止后写 mode；mode 写入失败不自动启动另一 runtime，
  并输出可重复的恢复命令。
- Native state、Docker ownership 或端口事实互相矛盾时失败关闭，Doctor 同时报告冲突来源。
- down/repair/uninstall 默认不删除 canonical data、secret 或 Docker volume；任何数据删除属于独立
  破坏性任务，必须另获明确授权。
- 容器内任一核心子进程退出即使 container unhealthy/退出，不能只保留另一个进程伪报可用。

## 文档与治理

实现时至少同步：

- `README.md`：Docker 推荐快速开始，同时保留 Native；
- `docs/research-web-installation.md`：两种安装、切换、目录、升级、卸载、diagnosis；
- `docs/ARCHITECTURE.md` 与 Research Web deployment/runtime 文档：双 runtime、不变的产品边界；
- `docs/DEVELOPMENT_MAP.md` 与 `docs/AGENT_WORKFLOW.md`：源码、测试、验证路由；
- `docs/actions-budget.md`：条件 Docker CI 与平台证据含义；
- architecture map、部署图与任务级 architecture review receipt；
- `.ai/reports`：审计、RED/GREEN、验证 plan/receipt、未验证项和风险。

README 快速开始优先展示：

```bash
./setup-web.sh --runtime docker
./rwb web doctor
```

紧接着保留 Native：

```bash
./setup-web.sh --runtime native
```

Windows 使用 `.cmd` 等价入口。不得把 Docker 测试写成 Native、Windows 实机或宿主能力已经验证。

## 回滚

代码回滚时：

1. runtime mode record 缺失/忽略后仍回到 Native 默认；
2. Native manifest、`.venv`、PID、日志与原有命令保持可用；
3. Docker Compose、image 和 state 可停止并保留数据；
4. 新增 policy/workflow 与代码一起回滚，不能留下引用不存在验证器的规则；
5. 不自动删除 Docker images、volumes、secret directory 或 canonical data。

## 非目标

- Kubernetes、Swarm、生产集群、云部署、NAS 自动部署或远程多用户服务。
- PostgreSQL、pgvector、旧 API lifecycle、Desktop/Tauri/sidecar 重引入。
- 把 Docker compatibility 当作 Windows/macOS Native compatibility。
- 为 Docker 复制 Research Web、DataHub、框架、能力、session 或 dependency manifests。
- 自动安装 Docker Desktop、修改系统 daemon、处理付费 registry 或发布公共 image。
- 在未获得用户授权时 push、dispatch、发布、迁移或删除数据。

## 决策摘要

1. Docker MVP 使用单容器，保留 DSH loopback/auth 安全边界。
2. Docker 用户的统一 CLI 由宿主 Python 3.12 stdlib bootstrap 提供，不依赖 Native `.venv`。
3. 未配置 runtime mode 时永远保持 Native，避免升级破坏。
4. 运行中默认拒绝切换；只有显式 `--stop-current` 才能停止并切换，`use` 不自动启动目标。
5. 研究数据与 DSH 持久 home 顺序共享，PID/auth/overlay/build evidence 按 runtime 隔离。
6. Native 用系统 keyring；Docker 用私有文件 credential backend，secret 不进入 image、Compose 值、
   环境、inspect 或日志。
7. Docker 相关路径正式进入 Verification Router 和条件多架构 CI；Native macOS gate 保留，
   Windows 实机与宿主集成证据继续独立。
