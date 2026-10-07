# Research Web 能力与平台证据

支持按能力、系统和运行方式声明。Doctor 的 `available` 表示代码具有当前实现，`unsupported` 表示明确边界，`not_verified` 表示必要安全证明缺失；`validated=false` 不会随操作系统推导为通过。实际验收由任务回执和下表的证据决定。

## 当前证据身份

阶段一候选 `78df0448d65bc77ebf66366fd8fc6eb074bff320` 已通过 [macos-14 干净安装与健康检查](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/37566792823)，合并提交为 `c24a8a161674678d572bf9ac35fab30489b40605`。该 CI 证明固定 DSH 构建、安装、3081/8088 健康及 Doctor；不证明真实模型调用、厂商授权或所有能力。架构阅读有独立 Mac 浏览器及人工图审证据，详见阶段一交付记录。

新任务证据随 `.ai/reports` 的候选/实际 checkout 更新；旧证据仅在相关代码与合同未改变时复用。当前没有 Windows/Linux 真机身份或访问配置，Windows 目标系统版本待设备任务确认；Windows Server 2022 CI 即使成功也不证明 Windows 10。

## 能力支持矩阵

`待验` = NOT_RUN；`有实现`仍须实际验收；`不支持`不以弱化安全检查实现。Mac 原生旧证据只属于上列候选。

| 能力 | macOS Native | Windows Native（目标版本待定） | Linux Native | Linux Docker amd64 / arm64 | macOS Docker Desktop | Windows Docker |
| --- | --- | --- | --- | --- | --- | --- |
| 安装、固定 DSH 构建 | 上列 CI PASS；新候选另验 | 待真机、Windows CI | 待真机、Linux CI | 两架构待 Linux 设备 dispatch | 独立隔离安装待验 | 凭据 ACL 门阻断 |
| 启动、停止、重启、Doctor | 上列健康 CI PASS；新候选另验 | 待验 | 待验 | 健康/重启/端口释放待验 | 健康/重启/端口释放待验 | ACL 阻断，不声明 ready |
| 模型系统存储 | Keychain 桥接有实现，真实调用依授权配置 | 不支持：仅 Mac Native 实施 | 不支持：仅 Mac Native 实施 | 不支持：未实施模型系统存储桥接 | 不支持：未实施模型系统存储桥接 | 不支持 |
| DataHub 凭据 | Native keyring 有实现、授权逐项验收 | keyring 有实现、待验 | keyring 有实现、待验 | 私有文件后端有实现、待验 | 私有文件后端有实现、待验 | DACL 未证明，失败关闭 |
| 数据源及授权 | 按 Provider 实际状态；未配置非可调用 | 待验、厂商授权单列 | 待验、厂商授权单列 | 不从依赖安装推导授权 | 不从依赖安装推导授权 | ACL 阻断 |
| 研究脚本严格沙箱 | macOS sandbox-exec 实现，实际任务待验 | 不支持 | 不支持 | 不支持 | Linux 容器中不支持 | 不支持 |
| 文件生成与交付 | 有实现，真实生成路径按任务验收 | 待验 | 待验 | 待验 | 待验 | ACL 阻断 |
| 架构阅读与导航 | 阶段一 Mac 阅读 PASS；新边界另验 | 安全 POSIX reader 不支持；501 | POSIX 实现、待验 | POSIX 实现、待验 | POSIX 实现、待验 | 生命周期 ACL 阻断；不以容器能力证明宿主 |
| Office / Wind / Tabbit | 各集成依本机安装、授权和验证 | Windows 真机逐项验收 | 厂商支持与实现边界逐项交接 | 宿主集成不支持 | 宿主集成不支持 | 宿主集成不支持 |
| 数据持久化与模式切换 | 有实现，独立目录/归属验收 | 待验 | 待验 | down/up 与数据保留待验 | 隔离目录 down/up 待验 | ACL 阻断；不迁移秘密 |
| 安装升级与恢复 | 安全受管 repair 有实现、按任务验收 | 真机升级待验 | 真机升级待验 | 旧镜像恢复、所有权与持久数据待验 | 同左，本机独立验收 | ACL 阻断 |

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


## 单一兼容文本/流式模型连接的证据范围

settings-model-loop在macOS Native正常受管fixed DSH中验证新增LlmAdapter、私有非秘密配置通道及两个系统凭据ref。产品API保存、合成生成和真正Host/DSH冷重启恢复，以及真实Mac Keychain合成隔离/清理通过；合成模型端点不代表真实新增供应商、工具/图片或其他平台通过。无Key模式不使用系统库，API Key模式仍要求本平台已获准系统后端且无环境/旧文件回退。

本聊天模型连接任务仅macOS Native；项目其他平台任务与整体支持矩阵继续保留，不从此任务授权自动执行Docker/Windows/Linux。Docker内localhost是容器，不能套用本机模型地址；未验的寻址、模型后端、ACL、严格沙箱和本机能力仍未验证/不支持。Linux Docker与Windows exact-SHA手动CI由对应设备任务执行，本任务不dispatch、不迁移生产。
