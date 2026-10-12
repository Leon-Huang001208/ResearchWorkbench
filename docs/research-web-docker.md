# Mac mini Docker 开发与独立部署

G0/G1 的入口是 `rwb-docker`（亦可用 `./rwb docker`）。管理员在 mini 的受控终端执行，
宿主只使用 POSIX shell 与 Docker CLI/Engine/buildx；Python、Node、Git、编译器及测试工具
在镜像中。当前仅交付 Mac Docker Desktop arm64 的基座，实际验收见任务报告。
Native、Windows cmd 和 `python scripts/setup_web.py` 保留 legacy 单实例合同与独立账本。
不要混用两套管理器、共享它们的业务数据或复制 Native PID/auth/Keychain。

## 从干净 checkout 建立环境

在 mini 的终端进入对应短期分支/worktree；开发容器挂载执行入口所在的 worktree。
无宿主 Python/Node 前置条件，首次构建需联网下载既有锁定依赖及项目已有 dev 工具。

```sh
./rwb-docker bootstrap
./rwb-docker build
./rwb-docker dev task register
./rwb-docker dev task up
./rwb-docker dev task exec -- python -m pytest tests/research_web/test_docker_manager.py --confcutdir=tests/research_web -q
./rwb-docker dev task exec -- node --test tests/javascript/docker_runtime_contract.test.mjs
./rwb-docker stage candidate register --port 18088
./rwb-docker stage candidate up
./rwb-docker stage candidate doctor
./rwb-docker stage candidate stop
./rwb-docker dev task rebuild
```

单步 stage 首装也可用：

```sh
./setup-web.sh --runtime docker --environment stage --instance candidate --web-port 18088
```

`register` 登记新实例；同目标重复登记核验后保留原固定镜像，冲突 image/port/worktree 拒绝。
后续 `up/status/doctor/stop` 使用原登记。
`build` 创建新的候选与开发镜像，不改变任何已登记镜像；重新运行 build 使用 BuildKit 缓存。
`register --image sha256:…` 只接受本 daemon 内存在的不可变 Linux arm64 image ID。
image ID 是本地内容身份，尚不等于发布到 registry 的 manifest digest；G2 实施 digest 提升/回退。
`rebuild` 只适用于 dev，精确删除已认证的开发容器并从同一登记镜像重建，保留源码与四个卷。
开发工具更新后，显式 `dev task rebuild --image sha256:…` 验证新开发镜像身份并记录旧image；
stage/prod无此更新捷径。`dev task stop` 后可 `dev task cleanup`：仅移除所属停止开发容器，
退休该预留以便新task/worktree使用3GiB池，保留四卷与账本；同目标 `register` 重新准入激活。
不提供全局 prune、批量停止、清空数据或生产迁移。停止正在执行的研究会中断任务；G1 无任务排空协议。
重复构建后，候选可显式 `stage candidate stop` → `stage candidate replace-image --image sha256:…`
→ `stage candidate up`；核验旧目标及新固定镜像，保留四卷和上一image。只更新已停止stage，
不提升prod、不实施registry digest发布或数据迁移；生产提升/回退由G2另交付。

MacBook 经已配置的受控 SSH/远程编辑器连接 mini，代码和工作进程必须实际位于 mini。
例如在 MacBook 执行 `ssh <mini-private-host>`，再进入 mini worktree 运行上列命令。
不要挂载 MacBook 源码经文件同步到 mini；代码交换继续使用 GitHub 与短期分支。
此说明不表示已配置/验收 SSH、VPN 或关闭 MacBook 后的常驻恢复；G5 逐项实测。

## 环境、数据和管理权限

| 目标 | 源码 | 内存硬上限 | 端口 | 数据/凭据/日志/cache/网络 |
| --- | --- | --- | --- | --- |
| dev TASK | 对应 worktree 可写 bind；Git common dir 单独挂载 | 全部 dev 预留合计 3GiB | 默认不发布 | `rwb-dev-TASK-管理根指纹-*` |
| stage INSTANCE | 固定候选 image ID，源码在镜像内 | 合计 2GiB | 显式独立回环端口 | `rwb-stage-INSTANCE-管理根指纹-*` |
| prod INSTANCE | 固定验收 image ID，源码在镜像内 | 默认每实例 2GiB；总池 6GiB | 显式独立回环端口 | `rwb-prod-INSTANCE-管理根指纹-*` |

每实例四个独立命名卷：data → `/data/research-web`（含 DSH home、业务文件与产品日志），
logs → `/state/logs`，credentials → `/run/rwb-secrets`，cache → `/cache`。
身份账本在 `~/.local/share/rwb-docker/ENV-INSTANCE.json`，保留环境、实例、镜像、源码SHA、
DSH提交、资源、网络、卷、端口及实际容器ID/config。`RWB_DOCKER_HOME` 可指定私有绝对管理根；
不要移动、手改或放宽账本。Docker VM/命名卷的物理持久存储归 Docker Desktop，不是宿主源码。
新卷由固定限额 initializer 初始化 UID/GID 10001、0700，不复制日常数据或秘密。

运行容器为非 root、只读根文件系统，drop ALL capabilities、no-new-privileges，
CPU 2、PIDs 256、swap 上限与内存相同，日志 10MiB×3；临时空间 `/tmp` 256MiB、
home 128MiB、认证 `/state` 1MiB。stage/dev 禁用既有 Automation 开关，均不连接生产 DSH。
每个实例独立 Docker bridge；默认仍有出站网络，不能当作研究代码的安全沙箱。
不对外发布 DSH 3081，不默认暴露开发终端、Docker API 或公网 Web。

宿主 shell 持一个管理根锁串行化配额准入与生命周期。停止的登记实例仍保留预算，防止
重新启动突破池上限；prod 池额外为瞬时控制器预留 256MiB，当前默认最多两个 2GiB实例，
剩余额度留给后续入口/固定服务。发现其他管理根的同环境容器或资源身份不匹配时拒绝。
卷/网络 labels、容器 ID、image/config/mounts 和网络归属在操作前核验；dev 重建不删除卷。
共享 Docker daemon 是共同故障域，不承诺抵御管理员/daemon 管理者篡改。

Web、DSH、研究代码与 dev 均不获得 Docker socket。只有 transient 管理镜像获得 socket，
只由拥有 daemon 权限的管理员调用；控制器自身只读 root、256MiB、CPU .5、PIDs64、
tmpfs64MiB，管理日志写 `logs/`。任何能调用该入口/修改其源码的人都拥有管理员权，
管理代码从所选管理员worktree只读加载到瞬时工具容器；该挂载只属于控制平面，
stage/prod业务容器仍只有不可变镜像和自身数据卷。
不能把它提供给受邀业务用户或不可信 PR。

## 24GB 初始预算与构建器

规划：宿主与余量约8GiB，Docker VM上限16GiB。VM内生产/入口/生产重任务合计6GiB、
开发3GiB、BuildKit3GiB、stage2GiB、VM/daemon余量2GiB。
这是待测预算，宿主8GiB不是硬保留，生产6GiB不是每个人的额度。
实际 VM 容量须用 `docker info --format '{{.MemTotal}}'` 核验；Docker Desktop Resources
设置调整和引擎重启是独立宿主操作。VM未达到16GiB时请错峰停用stage/dev/构建器，
不能声称满足整套并行预算。G6 才验证混合30分钟负载与容量。

所有镜像构建显式使用 `rwb-dev-builder` 的 docker-container driver。
初始3GiB已实测：原4GiB heap编译持续内存回收；2GiB和2.25GiB heap完整编译均OOM。
因此冷构建实测配置临时借用stage的2GiB，BuildKit memory=memory-swap=5GiB，
stage与冷构建互斥，成功/失败退出均精确核验并停止builder。冷构建期间预算为生产6+dev3+
builder5+stage0+VM余量2=16GiB；常规运行阶段builder停止，stage可按2GiB启用。
旧已登记3GiB builder用 `./rwb-docker builder-cold-budget` 受管升级，未手改账本或扩大其他池。
CPU仍为 CFS quota/period=200000/100000、
PIDs256、日志10MiB×3、`worker.oci.max-parallelism=2`，缓存仅用所属命名卷。
标准 BuildKit worker 需要 privileged，它仅属于管理员构建平面；业务容器不继承该权。
首次创建拒绝同名未知 builder/container，后续核验记录ID及限额后使用；不改默认builder。
BuildKit必须留出自身内存，重构建与stage错峰。不要通过全局 prune 或停止他实例解决问题。
固定 DSH源码、原Node4GiB heap、完整TypeScript与打包检查均保留，不交付失败的降低heap适配。
受管入口同时核对所有实际运行容器硬上限与VM实际内存，保留2GiB余量；未知无限额容器拒绝。
本轮约8GiB VM只能错峰构建、开发与stage，不能宣称16GiB整机并行预算已生效。

本机如使用系统已配置的无凭据回环代理，可只为当前命令设置 `HTTP_PROXY/HTTPS_PROXY`
（相同地址）及本地 `NO_PROXY`；不要把代理、供应商密钥或宿主环境写进镜像。
Docker Desktop transport与buildx客户端认证网络是两层，daemon pull成功不代表buildx认证可达。
构建器只自动使用 Docker Desktop 既有内部代理；其他代理配置明确拒绝，需管理员处理。

核验实际限额：

若固定 DSH 的大包下载失败后 pnpm 仍返回成功，而 staging 守卫拒绝缺失资产，
使用 `./rwb-docker build --refresh-dsh` 明确绕过 dsh-builder 阶段缓存重新构建。
仍沿用 frozen lock、固定源码、完整检查和同一限额 builder；不跳过缺失包或削弱 staging。
该操作重新下载/编译 DSH，仍需 stage/dev 错峰，不删除已有缓存或其他实例。

```sh
docker inspect buildx_buildkit_rwb-dev-builder0 --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuPeriod}} {{.HostConfig.PidsLimit}}'
./rwb-docker dev task doctor
./rwb-docker stage candidate doctor
docker stats --no-stream
```

## 下一阶段入口与真实缺口

### G2A 模型凭据（实现与验收进行中）

新镜像支持显式 `./rwb-docker stage candidate enable-model-credentials`。先停止候选，
通过 `replace-image --image sha256:…` 选择本轮镜像，再执行初始化和 `up`。
初始化由限额 128MiB 的无网络管理 helper 在容器内生成随机主密钥；秘密不经过管理员参数或环境。
它保留现有 credentials 卷，在其中创建 `/run/rwb-secrets/models`，并增加独立
`model_key` 命名卷，业务运行时只读挂载到 `/run/rwb-model-key`。
账本生成稳定随机实例身份；所有实例内部路径相同也不会共享凭据命名空间。
已有密文或部分初始化不得自动重置；缺少主密钥、身份不匹配或记录损坏明确失败。

固定 DSH 的两个模型 ref 继续使用产品 Python `-I -B` 私有 stdio 桥；Host 认证 record
仍走原有锁和生命周期。模型密文采用已有锁定依赖 cryptography 的 AES-256-GCM，
每次写入使用随机 96-bit nonce，认证数据绑定版本、实例身份、service 和 ref。
设置页显示本实例加密存储；留空保留、明确清除、活动任务拒绝和提交未知阻断保持原语义。
Native macOS 仍用 Keychain，绝不自动读取或迁移旧 Key。

最小恢复需要 **对应实例的 credentials 密文卷、model_key 卷（主密钥和身份文件）、
以及管理账本的实例身份和资源关联**。丢失任一项不能重新生成密钥恢复密文。
清除一个模型 Key 保留主密钥；stop/replace-image/up 保留这些卷。
完整备份流程、生产迁移、多人授权和公网入口不在 G2A 范围。
真实生成必须在设置页录入 Key 并运行“测试真实生成”，以 DSH 完成和非空文本为证；
保存、configured 或容器健康不证明生成成功。当前验收状态见本轮 `.ai/reports`。

`./rwb-docker stage candidate credential-probe` 要求候选和 builder 停止，使用该候选固定镜像，
在候选已有 2GiB 登记预算内串行运行 128MiB helper。A/B 独立四个夹具卷，同样的容器内路径，
通过同一 JavaScript/Python 私有桥验证保存、B 初始缺失、A 不受 B 保存/清除影响，
并拒绝错实例身份和错主密钥。仅返回布尔断言；夹具身份/资源关联保存在管理账本，
夹具卷保留以供审阅，不作为两个完整 stage 或真实供应商验收。

- G2：Docker模型凭据后端尚未交付，现有通用业务文件凭据目录不证明模型Key可用。
  不读取/迁移Native Keychain，不调用真实供应商；加密凭据、registry digest发布/回退另实施。
- G3：Linux研究脚本 strict sandbox 仍失败关闭，容器实例隔离不等于任意代码沙箱。
  完整任务期全机重研究配额、排队/恢复、文档处理限额及攻击回归未实施。
- G4：固定 `workspace_id=research` 及实例级共享设置仍保持现状，无受邀账号/鉴权路由。
  多实例资源隔离不是多人登录授权；不得据首页200称为多人隔离完成。
- G5：无公网域名/TLS/认证入口、迁移、备份恢复或无人值守电源/登录恢复证据。
- G6：典型供应商研究、混合负载、容量与RPO/RTO仍待实测。

Windows/Linux原生及同平台产品CI、模型付费生成、Office/Wind等本机集成保持 NOT_RUN。
本地 Docker Desktop 健康不替代 GitHub macOS 干净安装门，不触发无关桌面打包。
