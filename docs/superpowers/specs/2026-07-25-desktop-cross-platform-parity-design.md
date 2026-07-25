# 桌面端 macOS Apple Silicon / Windows x64 功能等价设计

**日期：** 2026-07-25

## 背景与目标

AlphaFoundry 的目标桌面平台固定为：

- macOS Apple Silicon（`aarch64-apple-darwin`）
- Windows x64（`x86_64-pc-windows-msvc`）

两端必须使用同一份前端、FastAPI/Python 业务逻辑、数据模型、运行时配置语义和 Tauri 壳配置；Windows 不只是“能够打开应用”，还必须支持 Excel、Wind 工作簿自动化、报告文件夹打开和 Office 文档预览等正式桌面能力。

本设计不将既有 Python 业务逻辑迁移到 Rust。Tauri 继续负责窗口、安装包、sidecar 生命周期和原生权限；Python sidecar 继续承载投研、AI、文档、数据库和数据源能力。

## 非目标

- 不支持 Intel Mac、Linux 或 Windows ARM。
- 不在本阶段捆绑 PostgreSQL、Microsoft Office 或 Wind 客户端/插件；它们仍是用户安装的前置条件。
- 不改变 Web 部署模式的配置和运行语义。
- 不以 GitHub-hosted runner 的构建成功替代真实 Windows 环境中的 Excel/Wind 验收。

## 架构

```text
共享前端 Web UI
        │ HTTP / 本地回环
共享 FastAPI、服务层、数据模型、PostgreSQL
        │
平台能力接口（唯一允许了解操作系统差异的边界）
   ├── macOS Apple Silicon：Excel / Wind / Word 实现
   └── Windows x64：Excel COM / Wind / Word 实现
        │
Tauri 2 + 原生 Python sidecar + 对应安装包
```

平台条件不得散落在路由、服务或前端。共享层通过平台能力接口请求操作；适配器将系统错误翻译为稳定的领域状态。前端只根据后端返回的能力状态显示操作、准备提示或恢复建议，不读取用户目录、不持有密钥、也不自行判断操作系统。

## 配置与路径的单一来源

后端是所有桌面运行时配置的权威来源：

- `core/settings/runtime.py` 解析运行模式、`.env` 位置和后端地址。
- `core/settings/registry.py` 定义可配置字段及其是否是密钥、是否需要重启。
- `core/settings/paths.py` 解析用户数据根目录及日志、对象、缓存、Wind 工作簿等派生路径。

桌面数据目录保持下列规范，且始终允许通过 `ALPHAFOUNDRY_DESKTOP_DATA_DIR` 覆盖：

| 平台 | 数据目录 |
| --- | --- |
| macOS Apple Silicon | `~/Library/Application Support/AlphaFoundry` |
| Windows x64 | `%LOCALAPPDATA%\\AlphaFoundry` |

用户可编辑的 `.env`、日志、对象存储、报告项目和 Wind 工作簿全部位于该数据根目录或由它派生；源码目录、Tauri bundle 目录和 PyInstaller 临时目录不得保存可变用户数据。Windows 继续提供从旧 `%APPDATA%\\AlphaFoundry` 的一次性、非覆盖式迁移。

共享配置字段不放在前端。前端只经由本地 API 读取已脱敏的描述信息、写入允许修改的值，并明确展示“环境变量锁定”和“重启后生效”状态。

## 平台能力契约

新增一个小且显式的桌面平台服务边界，例如 `services/desktop_platform/`：

- `capabilities.py`：定义 `DesktopCapabilities` 与每项能力的状态、诊断信息和修复提示。
- `office.py`：定义 Excel 工作簿打开、保存、隐藏、计算、Word PDF 导出和目录展示的抽象接口。
- `macos_office.py`：仅包含 Apple Event、`open` 和 macOS Excel 相关实现。
- `windows_office.py`：仅包含 Windows Excel COM、Explorer 和 Word 自动化相关实现。
- `factory.py`：根据受支持的平台选择实现；未知平台返回明确的 unsupported 能力，而不是导入失败或隐式降级。

能力模型至少覆盖：

| 能力 | 成功条件 | 常见不可用状态 |
| --- | --- | --- |
| Excel 自动化 | Excel 可启动并可打开工作簿 | `office_not_installed`、`office_busy`、`office_permission_denied` |
| Wind | Excel 中 Wind 插件已安装、登录并能刷新公式 | `wind_addin_missing`、`wind_login_required`、`wind_formula_timeout` |
| Word 预览 | 可通过 Microsoft Word 或已配置后备引擎导出 PDF | `word_not_installed`、`preview_engine_unavailable` |
| 文件夹展示 | 能安全定位输出目录或选中输出文件 | `operation_failed` |

所有状态都必须携带面向用户的中文消息和用于日志/测试的稳定状态码。路由层将已知状态映射为结构化响应；只把意外异常记日志并返回通用错误。不可用的 Office/Wind 能力不得导致桌面后端、报告生成的非 Office 功能或应用主窗口无法启动。

## Excel / Wind 的双端策略

工作簿文件结构、Wind 公式生成、快照解析、健康指标和业务数据模型保持共享。只把 Excel 进程控制从 `services/wind_realtime_workbook.py`、`services/wind_workbook_manager.py` 中抽离。

两个适配器均应满足同一工作流：

1. 检测 Excel、Wind 插件和登录状态。
2. 创建或迁移共享格式的工作簿。
3. 打开工作簿、写入/刷新 Wind 公式、轮询业务字段并保存。
4. 以稳定状态码报告 Excel 忙碌、受保护视图、COM/Apple Event 权限和 Wind 超时。

Windows 的实现以已安装的桌面版 Excel 与 COM/xlwings 为基础；macOS 保留其 Excel/xlwings 和必要的 Apple Event 行为。macOS 专属的 `osascript` 只存在于 macOS 适配器，Windows 专属的 COM 参数只存在于 Windows 适配器。Wind 自动启动的默认值由能力可用性和用户设置决定，不再以 `platform.system() == "Darwin"` 决定。

## 依赖与打包

`pyproject.toml` 必须明确桌面所需依赖，不能依赖开发机手工安装。依赖分为：

- 所有桌面平台的公共依赖（含共享 Excel 操作库）。
- macOS Apple Silicon 适配器依赖。
- Windows x64 适配器依赖（含 COM 所需包）。
- 开发与测试依赖。

使用 Python 环境标记或明确的 desktop extras，以便 macOS 和 Windows 原生 CI 可重复安装各自依赖。`scripts/desktop/build_sidecar.py` 必须从该声明构建，并显式收集动态导入的 Office/平台模块和所需数据文件；sidecar 名称必须仍严格对应原生 target triple。不得交叉复制 macOS sidecar 到 Windows，或反过来复制。

根目录的 `package.json` 与锁文件必须受版本控制，供本地与 CI 均以 `npm ci` 安装同一 Tauri CLI 版本。

## Tauri、启动与安全

Tauri 的公共配置保持单一版本；平台差异只使用 Tauri 的 `bundle.macOS`、`bundle.windows` 配置及生成的发布配置。安装包包含对应平台的 sidecar，Tauri 仅通过受控的 sidecar 名称启动它。

桌面后端只监听 `127.0.0.1` 或 `localhost`，端口冲突时绝不终止未知进程。启动器统一注入：

- `ALPHAFOUNDRY_RUN_MODE=desktop`
- `ALPHAFOUNDRY_BACKEND_URL`
- 用户数据、日志与对象目录的默认值

首次启动仍会生成配置模板，但不应静默降级到 SQLite；必须配置 PostgreSQL + pgvector。打包端到端健康检查使用隔离的、可重复的测试 PostgreSQL 配置或受控的健康检查模式，不能伪造“Windows 已启动”。

## 验证和发布

每次修改以下内容时，CI 必须自动运行：`src-tauri/**`、`desktop/**`、`scripts/desktop/**`、`core/settings/**`、平台适配器、sidecar 打包依赖、安装包和 Excel/Wind 集成。

验证分三层：

1. **共享测试：** 业务、API、配置与平台能力状态的单元测试；每个适配器可用 mock 验证同一契约。
2. **原生 CI：** `macos-14` 构建 Apple Silicon sidecar/桌面包；`windows-2022` 构建 Windows x64 `.exe`/MSI。两端均安装锁定依赖、构建 sidecar、验证目标文件名、构建 Tauri bundle，并执行可重复的基本启动/`/health` 检查。
3. **真实设备发布门禁：** 以 CI 产物在真实 macOS Apple Silicon 和真实 Windows x64 上安装。Windows 必须验证 Office、Wind 插件登录、公式刷新、报告目录打开、Word 预览、用户目录、日志、卸载与升级；macOS 做对应验证。CI 无法代替拥有授权 Office/Wind 的真实设备。

发布 workflow 与验证 workflow 使用同一目标矩阵。Release 只上传经 native CI 通过的 macOS Apple Silicon 和 Windows x64 产物；签名、公证、MSI 签名和自动更新作为各平台的发布前门禁。

## 迁移顺序

1. 合并并完善现有双平台原生 CI 基础：根 Node 清单、Windows x64 matrix、sidecar/安装包验证。
2. 定义平台能力 DTO、工厂和契约测试，前端改为读取能力 API。
3. 抽离 Excel/Wind 控制逻辑，先保持 macOS 行为不变，再实现 Windows COM 适配器。
4. 迁移 Word 预览、文件夹展示和其他系统调用至同一服务边界。
5. 在真实 Windows 设备完成 Office/Wind 安装级验收，记录版本、插件和结果。
6. 启用 Windows MSI 签名、macOS 签名/公证和安全的 updater 发布。

每一步都可独立验证和回滚。只有通过对应平台的原生 CI 与真实设备门禁，才可声明该能力在该平台受支持。

## 验收标准

1. 任一共享业务功能的代码修改不需要复制到 macOS/Windows 两套实现。
2. 任何操作系统分支均位于平台适配器、打包或 CI 层；前端不含操作系统判断。
3. 两端可从干净环境以锁定依赖构建正确 target triple 的 sidecar 与安装包。
4. 两端的 Excel/Wind 工作流以同一 API、状态码和工作簿格式运行；缺少前置条件时返回可诊断状态而非崩溃。
5. macOS Apple Silicon 与 Windows x64 CI 均通过后，仍完成各自真实设备的安装级冒烟，Windows 包含已登录 Wind/Excel 的验证。
