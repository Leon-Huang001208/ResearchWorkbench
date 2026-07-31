# AlphaFoundry 项目规则

- 默认使用中文回答。
- 修改文件前必须先读取；所有代码必须记录日志并包含错误处理。
- 修改 skill 时，必须同步更新该 skill 的文档。
- 安装 Python 包前必须先征得用户同意并说明用途。

## 桌面端跨平台交付（强制）

适用于 `src-tauri/`、`desktop/`、`scripts/desktop/`、桌面配置/路径、sidecar、安装包、自动更新、Excel/Wind 集成，以及任何可能影响桌面端运行的改动。

1. Mac 本地开发与测试不能证明 Windows 可用；不得据此宣称 Windows 已验证。
2. 每次相关改动都必须在原生 Windows CI runner 上运行构建与测试，至少覆盖：依赖安装、Python sidecar 构建、Tauri Windows 安装包构建、基础启动/健康检查。
3. 发布前必须在真实 Windows 环境完成安装级冒烟测试；涉及 Excel/Wind、系统权限、升级或安装器时，该测试不可省略。
4. 发行版本必须在各目标平台原生构建 sidecar；不得把 macOS 二进制用于 Windows，或反过来使用。
5. 具体流程、支持矩阵和验收清单以 `docs/desktop_packaging.md` 的“跨平台开发与发布验证流程”为准；相关改动须同步更新该文档。
