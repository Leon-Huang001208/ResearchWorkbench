# Research Web 能力与平台证据

Docker文本研究本轮新增模型私有文件后端与受管跨语言绑定的源码回归；这不认证新镜像、
实际设置保存、真实模型请求、重启续问或重建持久化。旧空ID容器仅保留经原完整守卫核验
的生命周期控制，不据此获得新模型能力；文件权限不等于系统Keychain/加密库。平台能力
投影和真实文本证据后续逐项记录，不用旧c1健康或普通绿色CI替代。

支持按能力、系统和运行方式声明。Doctor 的 `available` 表示代码具有当前实现，`unsupported` 表示明确边界，`not_verified` 表示必要安全证明缺失；`validated=false` 不会随操作系统推导为通过。实际验收由任务回执和下表的证据决定。

## 当前证据身份

阶段一候选 `78df0448d65bc77ebf66366fd8fc6eb074bff320` 已通过 [macos-14 干净安装与健康检查](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/37566792823)，合并提交为 `c24a8a161674678d572bf9ac35fab30489b40605`。该 CI 证明固定 DSH 构建、安装、3081/8088 健康及 Doctor；不证明真实模型调用、厂商授权或所有能力。架构阅读有独立 Mac 浏览器及人工图审证据，详见阶段一交付记录。

阶段二候选/合并 `205d2a170d9ece9c2751e014b63abe326510ab9c`、PR #83 已闭合 Mac Native；[Mac Bootstrap 37587972966](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/37587972966) 的实际 checkout `4bd5a6d8660ba7072da37878ce73396b8370fbab` 为 c24/205 的 PR preview。模型与厂商调用仍未验证。用户明确目前只有 Mac，Windows/Linux 真机及其 CI 保留 NOT_RUN；Windows目标版本仍待对应设备确认，Server2022不证明Win10。Mac Docker 独立任务的真实证据见下节，未借用 Native 结果。

Task14 本地集成保留 macOS Native 公开停止成功后最多 45 秒的原端口释放等待，
异根 Native 私有账本在真实 lifecycle lease 内的调用范围认证与复查，以及 Docker
私有 state tmpfs 和独立持久日志 bind。未知归属、同根写者和失效观察仍拒绝；这些
实现与本地合同测试不提升下表的支持或验收状态。目标源码的物理往返、最终合并源码的
新镜像构建及各平台 CI 证据必须分别绑定实际提交，不能把历史 PASS 当作当前候选已验收。

Docker DSH builder 的[命令局部并发 8 / 单请求期限 120 秒](research-web-installation.md)
不提升本表任何平台状态；当前候选真实下载、镜像构建和运行健康仍须独立取得证据。

## 能力支持矩阵

`待验` = NOT_RUN；`有实现`仍须实际验收；`不支持`不以弱化安全检查实现。Mac Native 证据只属于上列实际快照与候选；后续复用须核对受影响输入。

| 能力 | macOS Native | Windows Native（目标版本待定） | Linux Native | Linux Docker amd64 / arm64 | macOS Docker Desktop | Windows Docker |
| --- | --- | --- | --- | --- | --- | --- |
| 安装、固定 DSH 构建 | 阶段二清洁 CI PASS | 待真机、Windows CI | 待真机、Linux CI | 两架构待 Linux 设备 dispatch | 独立安装 PASS（镜像快照5e1b） | 凭据 ACL 门阻断 |
| 启动、停止、重启、Doctor | 阶段二 CI 与独立重启 PASS | 待验 | 待验 | 健康/重启/端口释放待验 | 独立启动/重启/Doctor/停止与端口释放 PASS（宿主fb9） | ACL 阻断，不声明 ready |
| 模型系统存储 | Keychain 桥接有实现，真实调用依授权配置 | 不支持：仅 Mac Native 实施 | 不支持：仅 Mac Native 实施 | 不支持：未实施模型系统存储桥接 | 不支持：未实施模型系统存储桥接 | 不支持 |
| DataHub 凭据 | Native keyring 有实现、授权逐项验收 | keyring 有实现、待验 | keyring 有实现、待验 | 私有文件后端有实现、待验 | 私有文件后端有实现、待验 | DACL 未证明，失败关闭 |
| 数据源及授权 | 按 Provider 实际状态；未配置非可调用 | 待验、厂商授权单列 | 待验、厂商授权单列 | 不从依赖安装推导授权 | 不从依赖安装推导授权 | ACL 阻断 |
| 研究脚本严格沙箱 | 真实 sandbox-exec 文件生成与会话外写入拒绝 PASS（Native快照985/205） | 不支持 | 不支持 | 不支持 | Linux 容器中不支持 | 不支持 |
| 文件生成与交付 | 有实现，真实生成路径按任务验收 | 待验 | 待验 | 待验 | 容器文件I/O与重建保留 PASS；研究脚本不支持 | ACL 阻断 |
| 架构阅读与导航 | 阶段二 Native 浏览器完整阅读 PASS（源码3df） | 安全 POSIX reader 不支持；501 | POSIX 实现、待验 | POSIX 实现、待验 | Docker真实Chrome阅读/固定版本链接 PASS | 生命周期 ACL 阻断；不以容器能力证明宿主 |
| Office / Wind / Tabbit | 各集成依本机安装、授权和验证 | Windows 真机逐项验收 | 厂商支持与实现边界逐项交接 | 宿主集成不支持 | 宿主集成不支持 | 宿主集成不支持 |
| 数据持久化与模式切换 | 有实现，独立目录/归属验收 | 待验 | 待验 | down/up 与数据保留待验 | down/up非秘密文件保留 PASS；双已安装模式切换 NOT_RUN | ACL 阻断；不迁移秘密 |
| 安装升级与恢复 | 安全受管 repair 有实现、按任务验收 | 真机升级待验 | 真机升级待验 | 旧镜像恢复、所有权与持久数据待验 | 安全恢复合同有测试；实际产品升级 NOT_RUN | ACL 阻断 |

## 安全边界与平台交接

- Linux Docker 历史健康、重启与持久化失败必须以最新候选重新复现，不能凭已存在脚本标为修复。Mac Docker Desktop 结果单独记录，不冒充 Linux 真机或 Linux CI。
- Windows Docker 保留 `docker_credentials_acl_unverified`，须在 Windows 真机实现并验证 DACL/重解析点/所有权安全后才能开启。不得 chmod 假装 ACL 已证明。
- 非 macOS 研究沙箱保留 `research_sandbox_unsupported`，不得无沙箱执行；需要支持时由对应平台提供严格隔离实现与攻击回归。
- Windows 文档保留 `documentation_platform_unsupported`；Native reader 必须证明 no-follow、单硬链接、大小上限和文件身份，不能退回普通 Path.read_bytes。
- Docker Desktop 不挂载宿主 Keychain、Office/Wind 凭据或 GUI/CLI；文件可见不证明本机集成可用。

Windows/Linux 设备任务从 GitHub 主线取得源码，确认目标 OS/版本/架构、实际 `git rev-parse HEAD`，先本机安装与关键路径，再对 exact SHA dispatch 自身平台 workflow。每项回执包含候选、实际 checkout、runner/machine 平台、运行方式和缺口；不得复制其他平台虚拟环境或原生二进制。缺设备时继续交接 NOT_RUN；其他平台独立完成不受阻，本产品跨平台发布仍 NOT_READY。

## macOS Native task smoke

显式平台任务通过 `supplementalGateIds` 选择 `macos-native-research-web`，不是无条件扩大每个 Web 小改的门禁。使用本任务独立目录与端口完成锁定依赖安装、固定 DSH 构建、start/Doctor 双服务 owned/ready、restart/stop/端口释放、研究沙箱实际执行与会话外写入拒绝、非秘密文件保留和 Settings 架构阅读。模型调用、厂商授权与跨模式迁移未执行时单列 NOT_RUN，不从上述结果推导通过。机器证据记录 macos 与实际源码快照。

## macOS Docker Desktop task smoke

显式选择 `macos-docker-desktop`，使用唯一任务镜像、安装身份、Compose 项目、私有 data/state/credentials 和独立回环端口。验证锁定镜像实际 Linux 架构、认证 DSH/Web 健康、Docker Doctor 能力边界、restart、down/up 后非秘密数据保留、最终停止和端口释放。该门属于 macOS 宿主 Docker Desktop，不能替代 Linux 原生设备或 Linux Docker CI，也不证明模型系统存储、研究沙箱或 Office/Wind/Tabbit。

## macOS Docker Desktop 当前证据

真机 macOS 14.6.1/23G93 arm64，Docker Desktop 4.94.0、Engine29.8.2，实际镜像 Linux arm64。公开安装器 adapter 的安装快照 `5e1b790b581bca01bc73583a0720b50f664e5941`，不可变镜像 `sha256:7dc3942fbddc81f3c4d34d0e860117a086c6cb8a8637eec10624dcd551333ee7`；最新宿主 controller 验证候选 `fb9ec4fb978d04caf6e6fca03ba90f49decdd64e`。镜像确含安装快照的controller，不宣称最后宿主提交已重新构建镜像：最终差异仅host stop默认等待；Supervisor/DSH/Web/healthcheck/依赖/Compose的执行输入未变，scoped reuse另有哈希与差异证据。

独立回环端口18092/13086完成实际install、双服务认证ready、Doctor、root/static/index/Atlas HTTP200；最新host restart16.773秒、stop1.953秒，精确down/up后容器生成的非秘密文件SHA保持；真实Chrome架构入口/分类/图返回及文档、源码、测试固定链接均200。最终stop2.962秒、owned容器移除、两family端口释放；保留测试数据/凭据，未更新日常实例或操作foreign容器。构建使用本机既有无凭据代理作为运输条件，锁、CA与签名保持。CI与机器回执归档在阶段三报告，报告提交与验证候选身份分开。

模型付费生成、厂商数据授权、真实产品升级、双已安装模式迁移、真实凭据存取仍NOT_RUN；非Mac严格脚本沙箱与宿主Office/Wind/Tabbit等保持明确不支持。Windows/Linux真机及其产品CI继续NOT_RUN，总体跨平台发布NOT_READY。
