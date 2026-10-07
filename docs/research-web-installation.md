# Research Web Native / Docker 安装与运行

Docker Doctor schema 1 的 volumes 类型为 data=bind、state=tmpfs、logs=bind、credentials=bind；logs 是新增的固定非秘密字段，verified 仍要求实际 inspect 成功，不改变安装或生命周期。

私有状态目录拒绝时，既有日志现在记录固定原因、检查阶段与变化字段名；不输出目录名、
路径或身份数值。该诊断不修复权限或重试启动，不改变依赖与一键安装流程。
源码测试不能代替新镜像的真实启动与 macOS 干净安装CI证据。
身份变化日志还区分完整root/runtime所有权对方向及parent/other_ancestor/leaf相对位置；
混合或未知变化仍拒绝，具体挂载根与认证写入层必须另行取证，不能由此自动修复。

Docker `/state` 改为私有 tmpfs（UID/GID 10001、0700、1 MiB，rw/nosuid/nodev/noexec）。
`/state/runtime` 由原严格 guard 创建；停止后丢弃，每次启动/重启由原链正常重建认证。
宿主 `run/docker/<installation-id>/logs` 独立绑定 `/state/logs`，controller 在正常生命周期
私有创建/验证该子目录，Compose 禁止自动创建宿主路径。supervisor 产品日志仍在 data-root/logs。
旧 host state/runtime 保留，不迁移认证、不自动删除旧停止容器；不符合新挂载合同的旧实例拒绝。
[Docker tmpfs](https://docs.docker.com/engine/storage/tmpfs/) 在 Docker VM 中可能进入 swap，
不能声称秘密绝不落盘。现有 CI 直接 Compose fixture 同步准备 state/logs，不扩展验收平台。

DSH 已发布运行子树内的 `doc/docs` 同名代码目录可保留（例如 yaml 的 `dist/doc`）。仅明确、
无 glob/negative 的包目录声明建立该例外；包顶层文档、任意层级测试/fixture/cache 等继续排除，
第三方 tarball 的其他运行资产选择保持原合同。真实镜像启动仍须单独验收。

Docker DSH 资产派生保留根 `node_modules` 与 `.pnpm/node_modules` 中指向已选生产包的相对别名，
供固定 DSH 从虚拟 Profile 锚点查找 optional peer。不会递归复制 `.pnpm`、引入未选开发包或新增
TypeScript 依赖；损坏或越界的生产依赖、非规范模块根、别名冲突和资产越界仍失败关闭。

Docker公开构建现在允许stdout/stderr各2MiB并流式保存脱敏进度；普通命令仍64KiB。超限或非零仍明确失败，不接受候选镜像。日志须保留在私有任务目录，不上传；本地合同通过不代表真实镜像或生命周期验收。

Docker dsh-builder 从固定 Node24.19.0 stage 同时复制 binary 和完整 headers，使用
npm_config_nodedir=/usr/local 供 fs-ext/node-gyp 本地编译，避免额外下载 headers。只在builder
设置，最终runtime无headers/nodedir ENV；不更改锁、官方APT源、TLS/签名或全局代理。
这项源码修补为一次真实重建提供新依据；先前失败日志保留，最终镜像/生命周期仍须主任务实测。

Docker CLI 可使用本机已设置的 credentials-free loopback HTTP_PROXY/HTTPS_PROXY（http或https、
localhost/回环IP、显式有效端口）；不支持SOCKS、认证URL、非回环或path/query/fragment。
大小写重复须校验后相等；两者空禁用，空/非空冲突拒绝。NO_PROXY只接受有界host/IP/CIDR/
wildcard列表并补localhost/127.0.0.1/::1；严格边界见安全清单。status/Doctor/安全stop仍可用，
不安全配置过滤并提示warning；install/build明确返回docker_proxy_configuration_invalid，纠正
本机pair/冲突后重试，不静默直连。Doctor.proxy只显示安全状态，不返回地址或列表。
仅Docker host CLI继承；Native诊断环境不放宽、不向Compose/provider/镜像写宿主127代理。
Docker Desktop Engine/build代理与CLI传输分层，真实combined构建由对应主任务验证；不改TLS、
签名、软件源、全局配置或用户Dockerconfig。HTTPS换源无必要且未授权。

正常 Native auto-start 公开入口先建立/复用精确 checkout-owned `.venv`，用该 Python -I
重执行同一 setup_web.py 与原参数；sys.prefix 与已有 marker 防重复，不依赖宿主全局 Web 包。
check-only、Docker、no-start 保留 host 路径。Web 依赖就绪后，实际 manager 持原 LifecycleLock
创建 canonical 根，继续 DSH/build-lock/manifest 与正常安装门，再借同一实际 lease 启动。
证明不序列化；root/lease/原监听变化或未知新增 writer 拒绝。no-start/失败退出后不继承 fresh，
已有根重装也不认领；直接 rwb start 到不存在 custom 根仍受 build-lock 前置限制，正常
installer auto-start 是连接创建与就绪的入口。源码 fixture 不替代 main 的新 HOME 完整实测。

失败恢复先清理本次新建容器或停止本次启动的既有停止容器，再恢复端点/origin；既有容器
保留。安装摘要只在发布 inode 与字节均匹配时回滚，否则报告 recovery_unverified。

Native fresh 启动在失败后另核验本次事务的恢复基线；同一 lease/根 inode、原外来监听
身份和本次全部子进程退出均可证明时恢复原 origin/端点。否则保留事务标记与原启动错误，
附加受控恢复诊断，停止重试；该恢复基线不授予新分配权限。

Docker-only 安装缺少 Native 环境时，忙端口须核验监听归属：已证明的其他实例监听与受管
Docker 服务可继续，未知 Native 写者拒绝；无关宿主 3081 监听不阻塞 Docker 幂等启动。

可识别 Web/DSH 的其他 checkout 也可能通过环境/配置使用同一数据根；稳定 PID 或不同
源码路径不足以证明数据根不同，未知时返回 runtime_ownership_unknown。缺端点/账本的既有
根会核验旧默认8088/3081，显式新端口不能绕过。setup --no-start 或 Doctor 已创建 canonical
research-web/runtime 后，根已存在，不满足本次 start 成功 mkdir 的 fresh 证明；若日常默认
监听是数据根未知的 Web/DSH，该组合会真实拒绝，而不是自动避让成功。
此时保留数据根和账本，由所属安装在明确授权后走正常 stop，或另对由启动器首次创建的
全新独立研究根做隔离验收；后者不替代 canonical 同根 Native/Docker 往返与安装后自动启动验收。

macOS 公开安装、start/restart 已接入私有端点记录与成对内部 origin 事务。
依赖锁保持不变，不移动、复制或轮换控制 token，也不迁移用户数据或凭据。

`--web-port <1..65535>` 可用于安装器和 `rwb web start/restart`；Native 另支持
`--runtime-port <1..65535>`，两端口必须不同。Docker 使用后者返回
`docker_runtime_port_unsupported`。显式占用返回 `endpoint_port_in_use`，不改用别的端口。
无显式参数时优先复用成功端点，再使用默认 Web 8088／Native Runtime 3081；目标运行记录
已证明静止时可分配其他回环候选。有明确 bind 失败证据、且本次对象退出/清理证明完整时，
最多执行三次启动尝试；健康/认证失败、未知归属与回滚失败不触发盲重试。
实际地址由 `web status --json`／Doctor 报告；只读诊断、logs、mode选择和 `--no-start`
均不分配端口或重绑控制 URL。Docker 容器内 8088／3081 固定，只选择宿主 Web 发布端口。
停止后出现无关宿主监听不作为停止该监听者的授权。

当前限制：已有停止 Docker 容器需要换 host Web 绑定时返回 `docker_stopped_port_conflict`，
保留原容器与接受镜像，不隐式 recreate。真实 macOS 双模式往返、镜像及干净安装 CI 未由本地
fixture 证明；Windows/Linux 本轮未验收。

## 支持范围

当前是本地 Web 产品，支持 Native 与 Docker 两条安装路径；不安装 Tauri、桌面 sidecar、数据库或桌面安装包。两种模式使用同一源码、`runtimes/research_web.json`、Web 依赖锁、固定 DSH 与顺序共享的产品数据目录。前置条件按模式区分：

- Docker（推荐新安装）：宿主 Python 3.12 解释器用于公开安装入口和统一 `rwb` CLI，另需 Docker Desktop、运行中的 Engine、Compose v2、构建时可访问固定基础镜像及 DSH 依赖的网络；无需宿主 Node，也无需全局第三方 Python 包。容器使用固定 Python 3.12、Node 24 和非 root 用户。Windows 的 Docker 凭据目录 ACL 尚无可证明的安全准备/验证路径，当前以 `docker_credentials_acl_unverified` 失败关闭，不能称为 Windows Docker 已可用或已验收。
- Native：Python 3.12、Node.js 22.19+（22 系列）或 24.x、Git；Node 23 和 25+ 不受支持。
- Windows Native：Visual Studio 2022 Build Tools 的 “Desktop development with C++” 工作负载；固定 DSH 的
  `fs-ext` 原生模块需要本机编译，安装器不会静默安装或修改系统工具链

Wind、iFinD、Office 等厂商/系统软件是可选能力，缺失不阻止 Web 主体启动。模型密钥、`CJ_KEY`、
Cookie 和账号只在本机设置页录入，不进入代码包、安装清单或日志。

## 公开入口

macOS Docker 推荐入口：

```bash
./setup-web.sh --runtime docker
./rwb web doctor
```

macOS Native 替代入口；无参数 `./setup-web.sh` 也默认 Native：

```bash
./setup-web.sh --runtime native
```

Windows Docker 对应入口（当前 ACL 门仍可能失败关闭）：

```bat
setup-web.cmd --runtime docker
rwb.cmd web doctor
```

Windows Native 替代入口：

```bat
setup-web.cmd --runtime native
```

跨平台底层入口：

```bash
python scripts/setup_web.py --runtime native
```

`--runtime` 缺省为 `native`，包括 shell、`.cmd` 和底层 Python 入口；不会因 Docker 已安装而改变旧调用语义。Docker 安装路径会做只读 preflight、构建受管镜像并核验镜像身份；只有已验证的项目安装身份且当前运行时/端口无冲突时才发布安装摘要和选择 Docker。`--no-start` 仅跳过启动，不代表镜像已实际健康运行。Docker 安装摘要为 `~/.research-workbench/install/docker-manifest.json`，与 Native 安装清单分开。

Docker 构建使用每次独立的候选 tag；接受摘要记录不可变 image ID，后续 start/Doctor 不依赖
`research-workbench:local` 当前指向。摘要通过私有文件、长度、无 alias 和字段校验，再核对
Web 锁、Compose、Python/Node 与 CJPY/DSH 构建合同；缺失、损坏或合同不一致会失败关闭。
默认启动有界等待容器健康检查证明 DSH/Web 同时 ready；starting 超时、unhealthy 或退出都
不会发布成功模式或打开浏览器。失败只删除本次新建且重新确认归属的容器，保留既有容器、
数据和凭据。显式 `--no-start` 仍允许仅接受已验证构建，不宣称实际 ready。
候选启动或发布失败保留先前接受的镜像；模式提交失败时恢复先前摘要。已有容器使用其他
image ID 时，普通安装返回 `docker_upgrade_requires_container_disposition`。显式 `--repair`
可在确认旧受管容器停止、端口空闲后再次检查归属，并用非 force 的精确 ID 删除该停止容器；
并发启动时删除失败关闭。旧接受摘要和旧不可变镜像、产品数据、凭据始终保留到候选接受，
失败时可按旧接受合同重新 start。若同时修改了锁或 Compose，需要恢复旧合同后才能按旧镜像
启动；不会用不匹配的新合同启动旧镜像。`--no-start` 同样要求显式 repair 才处置旧容器。
相关错误为 `docker_manifest_missing`、`docker_manifest_invalid`、`docker_build_contract_mismatch`、
`docker_image_mismatch`、`docker_ready_timeout`、`docker_services_unhealthy`、`docker_rollback_failed`。

Compose `up` 自身非零或超时后也执行一次有界恢复核对。新建调用使用临时配置写入一次性
launch label，只有启动前不存在、label/安装归属/候选image全部匹配的精确容器才清理；
并发或无法确认的实例保留，原启动issue后追加 `docker_rollback_unverified`。清理执行失败
追加 `docker_rollback_failed`，不覆盖原up错误或自动重试删除。`--no-recreate` 保留既有停止容器。

下述 `.venv` 和宿主 Node 说明仅适用于 Native。Native 默认流程会检查前置条件、创建项目自有 `.venv`、按哈希锁安装 Web 依赖、校验并安装随包
`cjpy==0.5.2`、构建固定 DSH、启动 3081/8088 并打开浏览器。可用参数：

- `--check-only`：只检查，不写入。
- `--repair`：Native 只修复带本项目所有权标记的 `.venv` 或 DSH 目录；复用 `.venv` 前以 15 秒上限
  验证其中的 pip 可响应，失败时把旧环境保留为 `.venv.failed-<id>` 后原子创建新环境；未知目录
  仍拒绝覆盖。
- `--no-start`：安装完成但不启动服务。

Docker `--repair` 重复有界构建和镜像身份验证，不删除产品数据、未知容器或 Native 环境。Docker 安装可能因远端镜像、APT、npm/pnpm 或 GitHub 网络失败；不得把 `--check-only` 成功或本机源码测试当作完整构建成功。

## 模式、生命周期和目录归属

安装后先查看当前模式；仅需切换时使用 `runtime use`，不要把两个方向当成连续安装步骤：

```bash
./rwb runtime status --json
```

```bash
./rwb runtime use docker --stop-current
```

```bash
./rwb runtime use native --stop-current
```

选定 Docker 后，可分别运行这些生命周期与诊断命令：

```bash
./rwb web start --no-open
./rwb web status --json
./rwb web doctor --json
./rwb web logs --tail 100
```

Docker 在运行中无法认证证明研究空闲；重启必须显式 `--force`，会中断研究：

```bash
./rwb web restart --force --no-open
```

停止当前受管服务：

```bash
./rwb web stop
```

Windows 将入口写为 `rwb.cmd runtime status --json`、`rwb.cmd runtime use docker --stop-current`、`rwb.cmd web doctor --json` 等对应命令；这些是接口说明，不表示本轮已在真实 Windows 上跑通 Docker。`runtime use` 默认不停止当前服务；存在运行中的旧模式时必须显式提供 `--stop-current`，且仅在旧进程/容器归属可验证时停止。未知端口占用、无法确认的 PID/容器、活动研究或状态异常均失败关闭；不要手动改模式记录来绕过。运行时选择保存在私有 `install/runtime.json`，无需 `.venv` 即可路由 Docker 命令；Native 命令仍进入 Native 环境。

两种模式依次使用 `~/.research-workbench/research-web/` 中的同一会话、资料、附件和产物，绝不能同时写入。Native 的 PID、认证和运行状态位于 `~/.research-workbench/run/`；Docker 的临时状态位于容器 `/state/runtime`，持久日志位于宿主 `run/docker/<installation-id>/logs`，容器归属由项目、服务、安装身份、镜像、挂载及端口核对，不复用 Native 的状态/认证文件。Docker 凭据存于 `secrets/docker/<installation-id>/` 并单独 bind mount 到容器；Native 仍使用宿主系统凭据库，模式切换不复制或迁移密码/令牌。Compose 只将宿主 `127.0.0.1:8088` 发布给浏览器；DSH 3081 仍留在单容器内部回环。容器以非 root、只读根文件系统、受限能力和显式可写挂载运行。

Docker 的挂载根与实际私有目录不同：`/state` 是私有 tmpfs，DSH 状态和认证实际位于
`/state/runtime`；`/run/rwb-secrets` 仍是凭据 bind 根，File backend 显式使用
`RESEARCH_CREDENTIAL_HOME=/run/rwb-secrets/private`。supervisor 以容器 UID 10001 在首次
认证、健康探测和子进程启动前创建 0700 私有叶，重启时重建状态、验证并复用凭据。Docker Desktop 可能把
宿主创建的 bind 根呈现为 UID 0；不会因此放宽私有叶 owner/权限/no-follow 检查，也不会
chmod/chown 挂载根。`LOG_DIR=/state/logs` 单独绑定原宿主日志子目录，避免导入期日志创建
影响状态叶。用户 data-root 与 Native 路径不变，Inspector 严格执行新的完整挂载合同。

首次 mkdir 还可能使固定 bind 根的可见 UID/GID 从 0:0 变为容器用户。Docker-only 准备器
仅对缺失的 `/run/rwb-secrets/private`、`/data/research-web/logs` 分阶段：
保留 no-follow 父目录FD安全创建0700叶，固定父节点的dev/inode/mode和路径/FD一致性必须
保持，创建阶段仅允许可信root→当前UID/GID映射；随后重新进入原完整严格校验，确认新叶
仍为本次创建对象，才访问认证/凭据或启动进程。已有叶及自定义路径无此创建例外。

Docker 容器无法等同宿主系统集成环境：Office/Wind、宿主凭据库、Tabbit 等需要 GUI、驱动、会话或本机 CLI 的能力不得仅因目录可见就标记为可调用。模型密钥须在选定模式中重新配置；Doctor/日志输出不应包含秘密或用户文件正文。`./rwb web logs --tail 100` 为有界尾部；Docker 的 `--follow` 最多读取 300 秒，每条输出流上限 64 KiB，超时或超限会结束读取，退出读取不停止服务。Doctor 的稳定 `issues` 可用于定位：`docker_cli_missing`、`docker_daemon_unavailable`、`docker_compose_missing`、`docker_architecture_unsupported`、`docker_port_8088_occupied`、`docker_port_3081_conflict`、`docker_ownership_mismatch`、`docker_build_not_ready`、`docker_data_home_unsafe`、`docker_credentials_acl_unverified`、`docker_services_unhealthy`、`runtime_stop_current_required`。按代码修复前置环境或停止已确认归属的旧模式，再重试；不要删除未知容器或修改状态文件。

升级时先 `web stop`，更新受审源码和锁后用对应 `--runtime` 重建/安装，执行 Doctor、status 和实际启动验证；不能把旧安装摘要视为新代码证明。修复用同一模式的 `--repair`，先保留现有数据并核对所有权。卸载运行部分可停止服务、移除自己受管的镜像/容器或 Native `.venv`；产品数据、Docker 私有凭据和 Native 系统凭据默认保留，需先另行备份并取得明确授权才清理。没有自动执行跨模式凭据迁移或破坏性卸载。

安装器只会在当前 `.venv` 能从 checkout 加载 `app.research_web.main:app` 后写入 `installed` 清单；
该 Web import readiness 最多等待 300 秒，用于完成云盘/FileProvider 冷文件的首次读取。超时或导入
失败返回 `python_web_import_failed`，不会把仅依赖已安装但当前 Web 入口不可加载的环境标记为完成。
开始修改安装器自有环境前，旧成功清单会被原子替换为 `installing`；任一步失败都保留该非完成
状态，Doctor 与 start 因而不能继续信任上一次安装的陈旧 `installed` 证据。

Node 选择顺序为：调用方显式传入、`RESEARCH_NODE_BINARY`、可执行的 Codex bundled Node、PATH。
安装器会把选中 Node 的目录放在 npm/Corepack/DSH 构建子进程 PATH 首位，避免版本检查使用 Node 24
而原生模块实际由 PATH 中的 Node 25 构建。Node 23 与 25+ 仍关闭失败，不会自动下载替代运行时。

安装完成后可运行：

```bash
./rwb web doctor
./rwb web doctor --json
./rwb web start --no-open
./rwb web status
./rwb web stop
```

Windows 将 `./rwb` 换成 `rwb.cmd`。Doctor 的 JSON 只包含版本、摘要、端口和健康状态，不输出路径、
环境变量值、凭据或用户文件正文。
若 checkout `.venv` 缺失、所有权标记不完整或解释器不可用，顶层 `--help`、`web status` 与
`web doctor --json` 仍由仅使用系统 Python 标准库的受限入口提供帮助或安全诊断；该入口拒绝
`start/restart/stop`，不读取 Runtime Cookie，也不改写 PID/state。系统 Python 也缺失时，入口返回
`python_runtime_unavailable` 并提示重新运行公开安装器。
该限制只适用于选中的 Native 模式：stdlib bootstrap 先选择部署模式，Docker 命令在 Native
环境缺失或损坏时仍可路由。Native 的 `web status --json` 同样提供 schema 2 的安全事实；
工作树复用公共 checkout 的 `.venv` 时按该环境所属根验证安装标记，不回退导入全局产品包。
Doctor schema 2 区分 `installation_ok`、`product_ready` 与 `model_ready`。服务状态按 state、真实 PID、
启动身份与命令归属、监听 PID、DSH 协议、Web HTTP 逐级核对；PID 文件或开放端口单独存在都不构成
ready。Node 22.19+（22 系列）或 24.x 由安装器与 Doctor 使用同一版本合同核对，其他版本或畸形
输出报告独立 issue。模型配置、凭据或目录问题只列入 warning，不阻止 Web 与设置页启动；Doctor 不
通过真实生成请求测试模型密钥。
`start` 在已确认死亡且端口关闭时恢复 stale state；归属明确但不健康的 DSH 只有在只读核对确认
没有活动研究后，才按 Web → DSH 的停止顺序重建。活动研究存在或无法核对时拒绝自动停止，并提示
显式 `rwb web restart --force`。随后依次等待 DSH、Web Runtime API、首页与 `/static/app.mjs`，
并复查最终产品就绪状态；未就绪时返回非零退出码和具体健康 issue，不会误报启动成功或打开浏览器。
归属不明的 PID、监听者或
损坏且仍可能活动的 state 会失败关闭，不接管或终止未知进程。生命周期操作由同一排他锁串行化；
浏览器打开失败会返回 `browser_open_failed` warning 和可复制 URL，已健康服务继续运行。
`rwb web start` 会在创建 3081/8088 子进程前复用 Doctor 的安装检查。若 checkout `.venv` 不受安装器
所有、锁摘要不符、CJPY/Node/DSH 未就绪，命令立即列出稳定 issue code，并提示重新运行上述安装器；
它不会先创建候选 Runtime 再等待健康超时。
安装成功还会从已验证 DSH state 原子刷新 `research-web/runtime/build-lock.json`；Doctor 返回
`dsh.runtime_lock_matches`，锁缺失或与当前 commit/closure/文件数不符时报告
`dsh_runtime_lock_mismatch`，不会把“安装清单有效”误报成 Runtime 可启动。
锁路径逐级拒绝符号链接和 Windows reparse point；POSIX 使用 no-follow 目录描述符完成 0600 原子
替换并拒绝 hardlink，Doctor 以相同边界有界读取。写锁前会把当前用户拥有的产品 data home 收紧为
0700；未知 owner 或 alias 不自动修复。closure 文件数只接受 JSON 整数，不接受浮点等价值。

## 依赖与固定制品

- `.venv` 位于 checkout 根目录，只由安装器管理，不写入全局 Python。
- `requirements/web.in` 是 Web 直接依赖；`requirements/web.lock` 是 Python 3.12、macOS/Windows 通用、
  带哈希的解析结果。用户端只消费锁文件。
- 根项目包以 `--no-deps` 安装，避免把历史 PostgreSQL、LangGraph、量化和桌面依赖引入 Web 环境。
- `vendor/cjpy/0.5.2/` 保存批准的 Apache-2.0 wheel、来源、许可证与闭合哈希清单；禁止回退到
  PyPI 的旧版 CJPY。`vendor/dsh-tabbit/0.3.4/` 的归档、MIT License 与 manifest 同样属于固定供应
  闭包。仓库属性禁止 Git 在 Windows checkout 改写这两个制品目录的字节，确保同一清单摘要可在
  macOS 与 Windows 验证。
- DSH 只从 `Leon-Huang001208/deepseek-harness` 获取提交
  `c919b2a460753859665db3f60143d525fb9140cf`，使用 `pnpm@11.7.0` 和 frozen lockfile 构建。
  Git clone、固定提交 checkout 与后续干净工作树校验都使用同一组命令级配置：
  `core.longpaths=true`、`core.autocrlf=false` 和 `core.eol=lf`，因此 Windows 不依赖机器级 Git
  长路径或换行配置。固定提交包含 Git symlink；Windows 额外统一使用 `core.symlinks=false`，接受 Git
  官方的普通文件表示但仍拒绝其他修改。首次启动会先用固定 DSH 模板
  初始化 `web` Profile，再写入已校验的 Tabbit bundle；
  不能依赖开发机残留的 `profiles/web/package.json`。
  Windows Node 构建只额外继承 PowerShell 模块、Program Files、ProgramData、系统盘与 Common
  Program Files 的标准发现路径，使 `node-gyp`/MSBuild 能定位并运行用户已经安装的 Visual Studio
  工具链；密钥和其他应用环境变量仍不进入子进程。
  安装器固定闭包文件数，首次成功构建后将当前安装目录对应的闭包摘要写入受管标记和安装清单，
  后续 Doctor 按该本机证明检测篡改。CSS Modules 会把绝对构建目录影响到产物摘要，因此不把任意用户目录误声明为
  同一全局摘要。GitHub 不可达、提交/来源/文件数不符，或本机证明后续不匹配时，安装关闭失败，不使用任意本机 DSH。
  DSH 构建子进程使用用户私有数据目录中的 Corepack shim；嵌套构建也固定解析 `pnpm@11.7.0`，不依赖全局 pnpm。

安装清单写入用户私有 `~/.research-workbench/install/manifest.json`，仅记录代码提交、Python/Node
版本、Web 锁摘要、CJPY 版本/摘要、DSH 提交/闭包和诊断状态。安装日志位于仓库 `logs/setup-web.log`。
安装子进程只透传平台基础变量和标准 `HTTP(S)_PROXY` / `ALL_PROXY` / `NO_PROXY` 网络配置；Git 可使用宿主的
SOCKS 代理，pip 与 Corepack/Node 仅保留其支持的 HTTP/HTTPS 代理。大小写代理变量采用同一协议过滤，
被过滤时日志只记录变量数量，不记录代理值，也不修改宿主环境。macOS 构建原生 Node
模块时，安装器通过 `xcrun` 发现当前 SDK 的 libc++ 头文件，不写系统路径。`CJ_KEY`、模型密钥及其他应用秘密不会传给安装命令。

## 天软状态

安装成功只证明 `cjpy==0.5.2`、`requests` 与 `urllib3` 可导入。没有 `CJ_KEY` 时，天软必须显示
“依赖已安装但待配置”，`configured=false`、`callable=false`；保存后的 Key 在每次探测和查询时从
系统凭据库动态读取，不要求重启。认证、权限、限流和厂商不可达分别显示，不能把依赖安装成功当作
真实数据成功。

## 后续迭代门禁

任何 Web 功能、Python/Node 依赖、DSH、CJPY、启动或配置流程变更，都必须重新核对本文件、
`requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py` 和 Doctor。仓库级
`.github/workflows/research-web-bootstrap.yml` 对相关 PR 与主分支更新在干净的 GitHub `macos-14`
runner 上运行公开安装入口、构建固定 DSH、启动 3081/8088、检查 Doctor，并验证无凭据天软不会
误报可调用。本机 macOS 验证必须先通过，但不能替代该远端干净环境门。Windows Web workflow 仅
保留手动入口：当 policy 选择 Windows gate 时，必须在 Windows 真机 checkout 待验 ref，从该机以
`git rev-parse HEAD` 的 exact SHA 发起 GitHub `windows-2022`；Mac 不发起该 workflow。GitHub Windows
结果与 Windows 真机安装、升级、用户目录、Office/Excel/Wind 结果分别记录，任一未运行均不得标记为
通过。该边界不改变桌面/Tauri/sidecar 的独立 Windows 门禁。
Bootstrap 的 macOS 验收还要求 Doctor schema 2 的安装/产品 ready、双服务 ready，以及首页和主
静态模块实际可读取；本机运行和单元测试不能替代该干净 runner 的结果。

维护者更新直接依赖后，用 Python 3.12 重新生成锁：

```bash
uv pip compile requirements/web.in \
  --universal \
  --python-version 3.12 \
  --generate-hashes \
  --no-strip-markers \
  --output-file requirements/web.lock
```

提交前必须从干净 checkout 运行一键安装；不能以开发机已有 `.venv` 或全局模块作为交付证据。
