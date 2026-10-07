# Research Workbench 架构总览

本页只维护系统级边界。Research Web 的模块、协议、数据文件、安全和接口细节统一从 [Research Web 当前架构](architecture/research-web/README.md) 进入；旧平台的完整历史说明已归档。

## 当前产品边界

Research Workbench 当前交付的是本地优先的 Research Web，Native 与 Docker 只是同一产品的两种互斥部署：

```text
浏览器原生 UI
    ↓ 同源 HTTP / SSE
Research Web FastAPI Host（8088）
    ├─ 会话、文件、能力、DataHub、框架、集成与运维投影
    └─ 私有 RPC / WebSocket
         ↓
项目专属 DSH Runtime（3081）
    └─ 唯一研究执行循环、历史、Skill、Tool 与子 Agent
```

- 入口：`app.research_web.main:app`。
- DSH 是唯一研究引擎；Research Web 不创建第二套 Agent 编排、聊天正文库或研究事实库。
- Native 以两个宿主进程运行 Web 与 DSH；Docker 以一个非 root 容器运行两者，仅向宿主回环发布 Web 8088，DSH 3081 留在容器内。`rwb runtime` 先按私有模式记录选择，再由 `rwb web` 按进程或容器归属管理；同一数据目录只允许顺序使用。
- Host 与 Runtime 保持回环访问边界；两种模式都不接管未知进程、容器或端口。
- macOS 启动链用私有 `install/endpoints.json` 记录健康后接受的实际回环端口。
  Native/Docker/最终模式选择共用 `run/lifecycle.lock`；元数据写锁在生命周期锁内短时获取。
  Docker 内部端口固定，只有宿主 Web 端口参与分配；可信控制 origin 的成对变更保留原 token。
- Docker 安装摘要绑定不可变 image ID、依赖锁、DSH/CJPY 与 Compose；公开启动和 Doctor 必须验证该已接受构建。构建候选使用独立 tag，启动等待真实健康后才发布选择；失败只回滚本次创建且再次确认归属的容器。
- Docker `/state` 使用私有 tmpfs，`/state/runtime` 在每次启动/重启由原认证链重建；日志单独持久绑定到 `/state/logs`，凭据仍为 `/run/rwb-secrets/private`。旧宿主状态保留，不迁移或自动清理；共享数据与 Native 路径不变。
- 当前产品不要求 PostgreSQL、pgvector、Tauri、桌面 sidecar 或旧 `app/api` 生命周期。
- 当前阶段为 Web-only；只有修改桌面专属路径或用户重新开启桌面工作时，才应用桌面原生 CI 和安装级烟测。

## 主要子系统

| 子系统 | 源码 | 职责 | 权威文档 |
| --- | --- | --- | --- |
| Web Host 与协议 | `app/research_web/*.py` | API、SSE、会话投影、文件和安全边界 | [系统与运行时](architecture/research-web/README.md) |
| 双运行时入口 | `research_workbench_entrypoint/`、`runtimes/research_web.json`、`scripts/setup_web.py` | stdlib 模式选择、统一依赖合同和两条安装链 | [安装指南](research-web-installation.md) |
| Docker 部署 | `Dockerfile`、`compose.yaml`、`docker/` | 固定镜像、单容器监督、健康和隔离挂载 | [部署与职责](architecture/research-web/01-system.md) |
| 原生 UI | `app/research_web/ui/` | 产品壳、研究、能力、设置和运维页面 | [UI 合同](research-web-ui.md) |
| DataHub | `app/research_web/datahub/`、`integrations/` | 静态目录、Provider、动态选源、探测和会话快照 | [DataHub](research-web-datahub.md) |
| 研究框架 | `app/research_web/frameworks/` | Gold／Dollar 专用定义、采集、快照、评分与 Bot 绑定 | [研究框架](architecture/research-web/08-research-frameworks.md) |
| 能力与方法 | `app/research_web/capabilities/`、`skills/` | Skill、Method、Tool、Workflow 的版本与发现 | [能力管理](architecture/research-web/07-capabilities.md) |
| MCP 与自动化 | `mcp_registry/`、`mcp_runtime/`、`automation/` | 目录、受控安装/调用和定时执行 | [Research Web 架构](architecture/research-web/README.md) |
| 报告 Workflow | `report_workflows/` | 模板、底稿、运行、Excel 刷新和独立交付 | [文件与交付](architecture/research-web/03-data-files.md) |

## 数据与信任边界

- DSH 原生日志持有研究正文和执行事件；产品索引只保存归属、状态、版本、文件和审计指针。
- 用户上传、DataHub 快照、能力资源和产物使用产品数据根内的受控相对路径；普通 API 不接受任意本机路径。
- Native 密钥只进入产品设置和宿主凭据库；Docker 使用独立私有容器凭据目录，不自动跨模式迁移。迁移、日志、快照和浏览器响应均不得回填秘密。
- DataHub 的登记、配置、授权、探测、适配和当前可调用是不同事实；目录存在不等于真实连接已验证。
- 框架快照绑定方法版本和 revision；旧会话不得混用新快照。

## 兼容平台

仓库仍保留 `app/api/`、`app/web/`、`core/`、`services/`、`data_layer/`、`storage/`、`signal_lab/` 等旧模块化单体代码，用于历史兼容、桌面维护和既有数据流程。它们是实际代码，但不是当前 Research Web 的启动链或新增能力默认依赖。

兼容平台的文件级历史说明位于 [归档](archive/README.md)；仍需维护的模块合同位于 `docs/modules/`、`DATA_STORAGE.md` 和各专项文档。任何把兼容代码重新接入当前产品的工作都必须先更新本边界和 Research Web 架构清单。

## 文档与验证

- [Development Map](DEVELOPMENT_MAP.md) 映射源码区域、权威文档和测试。
- [文档门禁](research-web-documentation.md) 校验文档分类、权威唯一性、链接、退役命令、生成索引和 Research Web 架构清单。
- `.ai/reports/` 保存每次任务的真实命令、结果和架构影响；`CHANGELOG.md` 只保留用户可见变化。
