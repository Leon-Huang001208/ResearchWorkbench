# 桌面端首次启动与数据库就绪状态设计

## 目标

让 macOS Apple Silicon 和 Windows x64 的 AlphaFoundry 桌面用户，在 PostgreSQL 或 pgvector 尚未就绪时仍可启动应用、完成配置，并获得不泄露敏感信息的明确修复指引。用户连接到已有 PostgreSQL 后，重启应用即可进入完整工作台。

本期不安装 PostgreSQL、不创建系统服务、不引入云数据库，也不迁移现有 API Key/密码到系统凭据库。这些属于后续独立阶段，不能阻塞当前已有用户配置的使用。

## 用户体验

首次以桌面模式启动时，应用展示欢迎页和环境检查：

1. 显示后端本身已启动。
2. 使用当前保存的 `DATABASE_URL` 检查 PostgreSQL 可连接、可执行 `SELECT 1`，以及是否启用 `vector` 扩展。
3. 全部通过时，用户进入完整工作台。
4. 任一检查失败时，欢迎页显示失败类别和对应的跨平台安装/修复指引，并提供“打开数据库配置”和“暂时跳过”。
5. “暂时跳过”可浏览配置控制面，但所有依赖数据库的业务和调度器保持不可用；系统配置页持续显示数据库未就绪。
6. 用户在数据库配置卡片输入连接 URL 后点击“测试连接”；测试成功再保存。保存提示“重启应用后生效”，避免错误宣称当前 SQLAlchemy 引擎已切换。

欢迎页采用已确认的“欢迎页 + 持续状态”模式：主动引导但不把用户锁死在向导中。

## 架构

### 桌面降级运行状态

新增只读的运行就绪状态，区分：

- `ready`：数据库和 pgvector 可用；按现有逻辑初始化 schema 并启动数据库依赖的调度器。
- `setup_required`：仅桌面模式允许。数据库连接失败、目标数据库不存在或 `vector` 扩展缺失时进入该状态。
- `failed`：非桌面模式维持现有 fail-fast 语义；不能为了 Web/生产环境的配置问题而继续提供业务 API。

在 `setup_required` 下，FastAPI 仍提供静态页面、`/health`、`/api/config/*` 和新的首次启动检查接口；启动流程跳过 schema 初始化和会访问数据库的自动调度器。运行状态只记录安全类别和建议文案，不保存异常文本、用户名、主机名、端口、密码或完整连接串。

### 数据库预检服务

新增一个独立服务模块，输入候选数据库 URL、超时和平台信息，输出结构化检查结果。它不修改全局 `settings`、现有 SQLAlchemy `engine` 或 `.env`。

检查顺序固定：

1. 复用现有 URL 校验，仅接受 PostgreSQL psycopg URL。
2. 用临时 SQLAlchemy engine 建立连接，并执行 `SELECT 1`。
3. 查询 `pg_extension`，确认扩展名 `vector` 已安装。
4. 关闭临时连接和 engine。

失败分类固定为：`invalid_url`、`connection_failed`、`database_unavailable`、`pgvector_missing`、`unexpected_error`。HTTP 响应只包含类别、用户可见的中文说明和可选修复步骤；详细异常仅写入本地 `logs/`。

现有 `POST /api/config/database/test` 改为调用此服务，因此系统配置页和首次启动页使用完全相同的真实检查标准。

### API 与前端

新增受现有 loopback 配置保护的只读 API：

- `GET /api/setup/readiness`：返回桌面运行状态、数据库预检结果和安全修复步骤。

候选 URL 的测试统一复用现有、受 CSRF 保护的 `POST /api/config/database/test`。欢迎页先取得现有配置 token，再调用该端点；它只测试提交 URL，不写入 `.env`。这样系统配置页和首次启动页始终使用完全相同的真实检查标准。

前端在桌面检测到 `setup_required` 时优先显示欢迎覆盖层。它会读取就绪接口、显示每一项状态，允许打开现有“数据库”配置模态框或跳过。系统配置卡片的数据库状态采用真实预检结果，而不是“URL 已填写”作为已就绪的依据。网页开发和生产模式不显示该桌面欢迎页。

### 配置和平台边界

仍使用当前的每操作系统用户数据目录与 `.env`：Windows `%LOCALAPPDATA%\\AlphaFoundry\\.env`，macOS `~/Library/Application Support/AlphaFoundry/.env`。进程环境变量优先级最高，页面对其锁定字段保持不可编辑。

本期不会自动安装 PostgreSQL、pgvector、iFinD、Wind 或任何系统组件。失败提示根据 macOS/Windows 说明安装 PostgreSQL 15+、启用 `CREATE EXTENSION IF NOT EXISTS vector`，然后回到配置页连接已有实例。

敏感字段的原值继续不返回给前端；错误和欢迎页不得回显 URL 或异常详情。凭据系统安全库迁移是第二期工作，届时要单独设计旧 `.env` 的无损迁移、回退和 Windows/macOS 原生验证。

## 错误处理与可观测性

- 预检服务捕获 SQLAlchemy/驱动异常，映射为安全错误码，并记录错误类型、检查阶段和平台到现有 `logs/`。
- 只有桌面模式允许数据库不可用时降级；web-dev/web-prod 继续启动失败，防止服务器在错误配置下静默运行。
- 在 `setup_required` 下不启动自动调度器，避免任何后台任务在未配置数据库时持续失败。
- `/health` 在配置模式返回 HTTP 200 且明确 `persistence.status=setup_required`，保证 Tauri 可打开配置界面；完整工作台不能仅凭该 200 状态判断数据库已可用。

## 测试与验收

先写失败测试，再实现最小代码。至少覆盖：

1. 预检成功：临时连接执行 `SELECT 1` 且发现 `vector`。
2. URL 无效、网络/认证失败、缺少 `vector`、未知错误都映射为无敏感信息的结果。
3. 数据库不可用时桌面启动进入 `setup_required`，不会调用 schema 初始化或数据库调度器。
4. 数据库不可用时 web-dev/web-prod 仍 fail-fast。
5. 配置 API 的数据库测试改为真实预检，并且不写入 `.env`。
6. 首次启动前端在 `setup_required` 时显示欢迎层；“打开数据库配置”和“暂时跳过”可用；未就绪状态不会被“已填写 URL”伪装为就绪。
7. 现有配置安全测试继续保证 URL、密码、用户名和异常详情不出现在 API 响应或前端 DOM。
8. macOS 与 Windows CI 均继续原生构建 sidecar、启动 PostgreSQL + pgvector、执行 `/health` 与 Tauri 包构建；新增无数据库配置模式的 sidecar 健康检查契约测试。

发布前仍需在真实 Windows x64 安装包中验证：没有 PostgreSQL 时可以进入向导；连接已有 PostgreSQL + pgvector 后重启进入完整工作台。

## 不在本期范围

- PostgreSQL/pgvector 的静默下载、安装、升级、卸载或服务管理。
- 托管数据库、账号登录、团队工作区与共享配置。
- macOS Keychain / Windows Credential Manager 的凭据迁移。
- 改造所有业务路由以支持无数据库工作；配置模式只保证配置与诊断入口可用。
