# Research Workbench

Research Workbench 当前交付的是本地优先的 **Research Web**：一个由 FinGPT、Claw、数据能力和研究框架组成的研究工作台。

当前 Web 入口为 `app.research_web.main:app`。Research Web 通过 FastAPI 轻量适配层连接专属 DSH；**DSH 是唯一的研究引擎**，负责研究执行循环、会话历史、Skill 与子 Agent。Research Web 不启动旧 API 生命周期，也不要求 PostgreSQL、pgvector 或桌面预览。

> 当前产品阶段为 **Web-only**。桌面打包历史仍被保留，但桌面 sidecar、Tauri、安装包和原生桌面 CI 不属于普通 Research Web 的安装或验收前提。

当前交付优先 macOS Native；Windows/Linux 和 Docker 保留实现、暂缓产品验收。固定 DSH 已更新为 0.2.1-alpha.1 的 Fork 提交 `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`，安装版本由 `runtimes/research_web.json` 决定。空实例默认 `deepseek-flash`，已有模型 ID 和会话保留，不自动重写或更新已运行的生产实例。

架构阅读从 Settings →「架构文档」或[交互图册](outputs/research-web-architecture/index.html)开始，按产品总览、部署、子系统、关键流程和 API 逐层展开；模块入口关联权威说明、源码与测试。

## 快速开始

### 前置条件

- Docker 模式（实现保留，本阶段暂缓验收）：宿主 Python 3.12 解释器用于公开安装入口和统一 `rwb` CLI，另需 Docker Desktop、可用的 Engine 与 Compose v2；无需宿主 Node，也无需全局第三方 Python 包，镜像内使用锁定的 Python 3.12、Node 24 和固定 DSH。当前 Windows Docker 凭据目录 ACL 无法由实现证明时会以 `docker_credentials_acl_unverified` 失败关闭，不能据此宣称 Windows 已验收。
- Native 模式：宿主 Python 3.12、Node.js 22.19+（22 系列）或 24.x、Git；Windows 另需 Visual Studio 2022 Build Tools 的 “Desktop development with C++” 工作负载。

Wind、iFinD、Office 等本机或厂商能力均为可选项；缺少它们不会阻止 Research Web 启动。

### 安装

当前 macOS 阶段使用下述 Native 入口；以下 Docker 命令保留供未来恢复验收时使用：

```bash
./setup-web.sh --runtime docker
./rwb web doctor
```

当前 Native 入口；`./setup-web.sh` 无参数也默认 Native：

```bash
./setup-web.sh --runtime native
```

Windows Docker 对应入口（真实 Windows Docker 生命周期尚未验收）：

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

Native 安装器创建 checkout 专属 `.venv`；Docker 安装器构建受管镜像，使用单容器内的 DSH 与 Web。两者消费同一带哈希 Web 锁、随包 CJPY 和固定 DSH 合同，不安装数据库、桌面 sidecar 或 Tauri。Docker 构建需要网络拉取固定基础镜像和 DSH 依赖；本机未完成真实 Docker 构建与生命周期验收，不能把源码/模拟测试视为镜像可运行的证明。

可在安装后检查运行环境：

```bash
./rwb web doctor
./rwb web doctor --json
```

Windows 请将 `./rwb` 替换为 `rwb.cmd`。

## 启动与管理服务

Research Web 对两种模式使用同一 `rwb web` 命令。Native 管理 DSH（3081）和 Web（8088）两个宿主进程；Docker 在单容器内运行两者，仅向宿主回环发布 8088。先查看当前选择：

```bash
./rwb runtime status --json
```

仅在需要切换时二选一；若当前受管模式仍在运行，须显式允许先停止：

```bash
./rwb runtime use docker --stop-current
```

```bash
./rwb runtime use native --stop-current
```

从仓库根目录运行：

```bash
./rwb web start
./rwb web status
./rwb web logs --tail 100
./rwb web stop
```

Native 可在确认没有活动研究时普通重启；Docker 运行中无法认证证明研究空闲，必须显式 `--force`，这会中断研究：

```bash
# 仅 Native
./rwb web restart
```

```bash
# 仅 Docker，显式中断研究
./rwb web restart --force --no-open
```

服务启动后访问 [http://127.0.0.1:8088/#/fingpt](http://127.0.0.1:8088/#/fingpt)。`start` 是幂等的；终端关闭不会停止受管服务。切换、停止和重启都要求可验证的本项目所有权，不接管未知进程或容器。Docker 模式暂不承诺宿主 Office/Wind/Tabbit 等本机集成可用；能力目录出现不等于已配置或可调用。具体升级、修复、凭据与数据目录见[安装指南](docs/research-web-installation.md)。

网页打不开时，先运行 `./rwb web status` 和 `./rwb web doctor --json`。即使 checkout 的 `.venv` 缺失或损坏，这两个只读诊断入口也会报告 Python 环境问题并提示运行公开安装器；该后备入口不会启动或停止服务。正常启动会等 DSH、Web API、首页和主静态模块就绪后再打开浏览器。模型密钥未配置时仍可打开设置页，Doctor 会单独报告模型问题。

## 模型、数据与迁移

### 模型配置

在产品的 **Settings（设置）→ Model（模型服务）** 中配置固定 Runtime 支持的 DeepSeek 模型。API Key 留空保留、填写替换、独立按钮清除；已有会话保留选模，任务运行时拒绝配置变更。保存、Runtime 可达与真实生成分别展示，生成测试由用户显式发起。

macOS Native 的模型凭据由产品 overlay 挂载的固定用途桥接存入系统 Keychain，按规范化 data home 隔离；不回退环境、旧凭据 YAML 或 `.env`，也不把 Keychain 值复制到文件。不迁移旧模型 Key，需在该实例设置页重新录入。Host 浏览器认证 record 保留固定 DSH 的受控文件实现，和模型 Key 分开。其他平台或 Keychain 不可用时模型失败关闭，设置页与 Host 认证仍可使用；其他平台系统模型存储尚未验证。

Docker相关通用业务凭据隔离实现保留；本阶段不交付Docker模型凭据后端，不把Native系统存储保证泛化到容器。

DataHub 连接凭据按规范化 data home 隔离系统凭据服务；不同实例互不读取、覆盖或清除。旧全局记录不自动迁移或回退，已有非秘密配置保留，升级后请在所属实例设置页重新录入数据源凭据；旧记录不会被删除。

### 旧 Research Web 数据迁移

从旧研究目录迁移前，先查看不写入的摘要：

```bash
./rwb migrate-research-data --dry-run
```

确认后执行迁移：

```bash
./rwb migrate-research-data
```

该操作复制研究会话、附件、能力版本、数据集和产物，但不会复制凭据。迁移完成并完成恢复验证后，如需将来源目录保留为只读备份，可显式使用 `--archive-source`。

### 运行时目录与日志

Research Web 使用用户私有目录保存运行状态与数据：

- `~/.research-workbench/research-web/`：两种模式顺序使用的同一研究会话、附件、数据集、产物和其他产品数据；切换前必须停止当前运行时。
- `~/.research-workbench/run/`：Native 受管进程的 PID 与命令归属状态；Docker 使用独立容器状态目录和归属标签，不复用 Native 认证/PID 文件。
- `~/.research-workbench/logs/`：受管运行时与 Web 服务日志。
- `~/.research-workbench/install/runtime.json`：当前选择与安装身份；Docker 的私有状态位于 `run/docker/<installation-id>/`，凭据位于 `secrets/docker/<installation-id>/`，均不等同于产品数据目录。
- `~/.research-workbench/runtime/dsh/<commit>/`：固定提交的项目私有 DSH 源码与构建来源。
- `~/.research-workbench/install/manifest.json`：安装摘要与诊断状态。
- `logs/setup-web.log`：仓库内的一键安装日志。

这些目录均服务于当前用户和当前项目管理器；不要将其中的状态文件、日志或安装清单作为跨机器配置复制手段。

## 产品导航

当前主导航由以下页面组成：

- **FinGPT**：研究对话入口与会话管理。
- **Claw**：可使用 Workflow、资料和产物的研究空间。
- **Asset Observation（资产观察）**：按需查看资产相关数据。
- **Research Workbench（研究台）**：市场、资产、基金、行业与文档的工作台入口。
- **Capability Center（能力中心）**：Skill、Method、Tool、Workflow 与数据能力目录。
- **Research Frameworks（研究框架）**：独立的研究框架与快照驱动分析。
- **Operations and Usage（运行与用量）**：只读聚合模型用量、Agent、工具、DataHub、服务健康与存储情况。
- **Settings（设置）**：通用、模型服务、数据源、本机集成与架构文档。

DataHub 是 Research Web 进程内的数据目录、白名单路由、Provider 适配和会话快照层；它不是第二个研究引擎或全局行情数据库。页面展示的来源状态会区分“已登记”“已配置”“依赖就绪”和“当前可调用”，避免把可发现能力误当作已验证的数据连接。

## 开发与平台验收

MacBook Pro 负责项目功能开发、macOS 本地验收与 GitHub macOS CI。Windows 和 Linux 真机分别负责已有功能的本平台适配、本地验收与对应 GitHub CI，不承担功能开发。其他平台待验收不阻塞当前宿主任务，已验证支持范围仍以各平台实际证据为准。详见 [Agent 任务路由指南](docs/AGENT_WORKFLOW.md)。

## 文档

- [文档门户](docs/README.md)：按入门、架构、开发、运维、参考和历史组织的唯一索引。
- [Research Web 当前架构](docs/architecture/research-web/README.md)：当前产品的唯一架构入口、运行边界与阅读路径。
- [Research Web 一键本地安装](docs/research-web-installation.md)：完整安装前提、固定制品与跨平台安装门禁。

## 历史功能

旧 `app.api.main:app` FastAPI 工作台、量化业务、数据库迁移与 PostgreSQL/pgvector 架构仍保留在仓库中，供历史兼容和维护参考；它们不是当前 Research Web 的启动、使用或开发前提。请以本 README 和 [Research Web 当前架构](docs/architecture/research-web/README.md) 为准。

## 许可证

MIT License

能力详情的数据准入范围独立于模型健康：硬条件缺失阻断，可选条件缺失按声明省略章节；旧快照与资源全集不代表当前执行授权。当前Mac验证不扩展成其他平台或所有供应商品牌支持。


## 单一兼容模型连接

设置页支持固定 DeepSeek 官方目录及一种 OpenAI Chat Completions 兼容文本/流式连接。兼容连接显式配置非秘密 base URL 和模型 ID，专用 Key 与官方 Key 隔离；本机无Key模式不读取凭据。模型工具能力未经实测时保持未验证；保存、Runtime应用、真实生成与真实账户验收各自留证，不承诺全品牌支持。
