# Research Workbench

Research Workbench 当前交付的是本地优先的 **Research Web**：一个由 FinGPT、Claw、数据能力和研究框架组成的研究工作台。

当前 Web 入口为 `app.research_web.main:app`。Research Web 通过 FastAPI 轻量适配层连接专属 DSH；**DSH 是唯一的研究引擎**，负责研究执行循环、会话历史、Skill 与子 Agent。Research Web 不启动旧 API 生命周期，也不要求 PostgreSQL、pgvector 或桌面预览。

> 当前产品阶段为 **Web-only**。桌面打包历史仍被保留，但桌面 sidecar、Tauri、安装包和原生桌面 CI 不属于普通 Research Web 的安装或验收前提。

## 快速开始

### 前置条件

- Python 3.12
- Node.js 22.19+（22 系列）或 24.x
- Git
- Windows 另需安装 Visual Studio 2022 Build Tools 的 “Desktop development with C++” 工作负载，以构建 DSH 所需的原生模块

Wind、iFinD、Office 等本机或厂商能力均为可选项；缺少它们不会阻止 Research Web 启动。

### 安装

在仓库根目录使用与平台对应的公开安装入口：

```bash
# macOS
./setup-web.sh
```

```bat
:: Windows
setup-web.cmd
```

跨平台底层入口：

```bash
python scripts/setup_web.py
```

安装器创建 checkout 专属 `.venv`，使用带哈希的 Web 依赖锁，验证随包 CJPY，构建固定 DSH，并启动 Research Web 所需服务。它不会依赖全局 Python 或 Node 包，也不会安装数据库、桌面 sidecar 或 Tauri。

可在安装后检查运行环境：

```bash
rwb web doctor
rwb web doctor --json
```

Windows 请将 `rwb` 替换为 `rwb.cmd`。

## 启动与管理服务

Research Web 管理专属 DSH 运行时（3081）和 Web 服务（8088）。从仓库根目录运行：

```bash
rwb web start
rwb web status
rwb web restart
rwb web stop
```

服务启动后访问 [http://127.0.0.1:8088/#/fingpt](http://127.0.0.1:8088/#/fingpt)。`start` 是幂等的；服务由项目管理器后台运行，命令结束或终端关闭不会停止它。`stop` 与 `restart` 只处理命令指纹和归属均匹配的项目进程，不会接管用户已有的运行时或端口占用进程。

## 模型、数据与迁移

### 模型配置

在产品的 **Settings（设置）→ Model（模型服务）** 中配置模型。模型密钥只由本机设置与操作系统凭据库处理，不写入代码包、安装清单、日志或旧数据迁移结果。

### 旧 Research Web 数据迁移

从旧研究目录迁移前，先查看不写入的摘要：

```bash
rwb migrate-research-data --dry-run
```

确认后执行迁移：

```bash
rwb migrate-research-data
```

该操作复制研究会话、附件、能力版本、数据集和产物，但不会复制凭据。迁移完成并完成恢复验证后，如需将来源目录保留为只读备份，可显式使用 `--archive-source`。

### 运行时目录与日志

Research Web 使用用户私有目录保存运行状态与数据：

- `~/.research-workbench/research-web/`：研究会话、附件、数据集、产物和其他产品数据。
- `~/.research-workbench/run/`：受管服务的 PID 与命令归属状态。
- `~/.research-workbench/logs/`：受管运行时与 Web 服务日志。
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

## 文档

- [Research Web 当前架构](docs/architecture/research-web/README.md)：当前产品的唯一架构入口、运行边界与阅读路径。
- [Development Map](docs/DEVELOPMENT_MAP.md)：源码、测试、安装与文档更新职责。
- [Research Web DataHub](docs/research-web-datahub.md)：数据源目录、连接状态、Provider 与查询边界。
- [Changelog](docs/CHANGELOG.md)：变更历史。
- [Desktop Packaging History](docs/desktop_packaging.md)：保留的桌面打包历史与重新开启桌面工作的验收边界。
- [Research Web 一键本地安装](docs/research-web-installation.md)：完整安装前提、固定制品与跨平台安装门禁。

## 历史功能

旧 `app.api.main:app` FastAPI 工作台、量化业务、数据库迁移与 PostgreSQL/pgvector 架构仍保留在仓库中，供历史兼容和维护参考；它们不是当前 Research Web 的启动、使用或开发前提。请以本 README 和 [Research Web 当前架构](docs/architecture/research-web/README.md) 为准。

## 许可证

MIT License
