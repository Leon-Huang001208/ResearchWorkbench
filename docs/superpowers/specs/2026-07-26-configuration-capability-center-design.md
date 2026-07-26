# 配置目录与环境能力中心设计

## 目标

在既有“系统配置”页面内增加一个只读的配置目录与环境能力诊断层。它必须与现有配置卡片、健康总览、首次配置引导、编辑弹窗、连接测试、配置锁定和首启向导协同工作；本阶段不创建第二个设置页面，也不改变现有配置持久化路径。

## 范围

本阶段交付两项能力：

1. 后端以稳定、脱敏的 API 契约提供配置目录（catalog），为每个现有分区和字段声明标签、数据类型、配置范围、适用平台、是否敏感、是否需要重启、是否支持连接测试及对应环境变量键。
2. 后端以稳定、脱敏的 API 契约提供当前环境摘要（environment）：系统、架构、运行模式、配置/数据/日志目录，以及不读取用户秘密值的能力检测结果；前端把它显示在现有系统配置页的健康总览下方。

“配置目录”是后续动态表单和导入/导出配置的唯一元数据来源。本阶段保留既有手写表单和保存逻辑，避免重写已经具备锁定、秘密值和可访问性保护的 UI。

## 非目标

- 不自动下载、安装、启动或升级 PostgreSQL、pgvector、Excel、Wind 或 iFinD。
- 不扫描注册表、用户目录、进程或网络来寻找凭据；不返回数据库 URL、API Key、密码或环境变量的具体值。
- 不在此阶段把手写表单替换为动态表单，也不改变 `/api/config/{section}` 的更新契约。
- 不把 Windows CI 的临时 PostgreSQL 检测误作为用户机器的实际安装状态。

## 后端边界与数据契约

`ConfigurationService` 新增两个只读、无副作用的方法：

- `get_catalog()`：从独立的 `services/configuration_catalog.py` 读取常量目录，返回所有六个已存在分区的描述符。目录不读取 `.env`，不依赖运行平台。
- `get_environment()`：通过 `platform`、`shutil.which` 和受控的 Python 模块发现生成摘要。异常必须记录类型化日志，并降级为 `unknown` 或 `not_detected`，绝不使配置页不可用。

`GET /api/config` 在原有 `sections`、`readiness`、`environment_locked_fields` 字段外增加：

```json
{
  "catalog": {
    "sections": [
      {
        "key": "database",
        "label": "数据库",
        "scope": "global",
        "platforms": ["macos", "windows"],
        "restart_required": true,
        "testable": true,
        "fields": [
          {
            "key": "database_url",
            "label": "数据库连接地址",
            "kind": "secret",
            "environment_keys": ["DATABASE_URL"]
          }
        ]
      }
    ]
  },
  "environment": {
    "platform": "macos",
    "architecture": "arm64",
    "runtime_mode": "desktop",
    "paths": {"config": "…", "data": "…", "logs": "…"},
    "capabilities": [
      {
        "key": "postgresql_client",
        "label": "PostgreSQL 客户端",
        "status": "available",
        "detail": "已检测到 psql 命令。",
        "remediation": []
      }
    ]
  }
}
```

目录字段只暴露名称和行为元数据。路径可显示给桌面用户用于排障，但必须经过 `Path.resolve()`，不暴露 `.env` 内容或机密。`data_dir=None` 时返回 `null`，前端显示“当前模式不使用本地数据目录”。

能力状态限定为 `available`、`not_detected`、`not_applicable`、`unknown`。首批检测项：

- `postgresql_client`：`psql` 是否可从当前 `PATH` 找到；这只表示客户端可用，不表示数据库服务或 pgvector 已可用。真实数据库状态继续复用现有 `/api/setup/readiness` 与数据库连接测试。
- `ifind_python_sdk`：iFinD Python SDK 是否可导入；仅作为本机依赖提示，不读取账户配置。
- `wind_excel`：Windows 显示“需要在 Windows Excel 中单独验证”；macOS 显示“不适用”。不在此阶段探测 COM 或打开 Excel。

所有 `/api/config` 既有 Origin/CSRF 保护不变。生产 Web 模式继续拒绝本地配置控制面，不能因诊断接口绕过。

## 前端协同设计

在 `data-config-health-summary` 后、`data-config-onboarding` 前新增 `data-config-environment-diagnostics` 区块。它是系统配置页的一部分，使用现有加载、刷新和错误呈现流程：

- 顶部显示“当前环境：macOS / Apple Silicon / desktop”等非敏感摘要。
- 显示配置、数据、日志目录；空数据目录用安全的中文说明代替。
- 每项能力使用 `available`、`not_detected`、`not_applicable`、`unknown` 四种样式与后端说明/修复建议。
- 刷新现有配置页时同时刷新诊断；不另发会修改状态的请求。
- 现有健康统计、卡片状态、数据库运行时状态、首次配置引导与弹窗逻辑不改写。诊断层只读且不能拦截卡片点击或首启向导焦点。

前端从 `snapshot.catalog` 读取展示标签的回退值和字段数量，用于逐步验证目录契约；当前表单、锁定规则和请求体仍以现有实现为准。这样可避免与刚加入的上下文配置锁发生双重管理。

## 错误处理与日志

- 环境检测每个能力独立隔离；一个导入/路径检测失败不能丢掉其它能力或整个配置快照。
- 日志只写能力键、平台和异常类型，禁止记录路径之外的配置值与任何秘密。
- API 遇到配置服务错误仍返回现有的安全 `500 配置读取失败` 文案。
- 前端缺少新增字段时降级为不显示诊断区块，不能阻塞旧版后端的配置表单。

## 验收

1. 配置快照包含六个分区的目录描述，且不含 `.env` 值、数据库 URL、密码或 API Key。
2. macOS 与 Windows 能各自获得正确的平台/架构摘要；平台专属 Wind 提示正确区分“不适用”和“需要验证”。
3. `psql`、iFinD SDK 缺失或探测异常时，快照仍可成功返回并给出安全状态。
4. 现有卡片、健康总览、首次配置引导、数据库运行时状态和上下文锁测试继续通过。
5. 新诊断区块可由已有“重新检测配置”刷新，并通过前端静态/语法测试。
