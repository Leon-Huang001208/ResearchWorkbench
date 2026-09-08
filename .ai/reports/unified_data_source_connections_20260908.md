# 统一数据源连接中心交付报告

- 任务 ID：`unified-connections-20260908-01`
- 日期：2026-09-08
- 范围：Research Web（8088）连接中心；不涉及 Tauri、sidecar、安装包或桌面应用
- 分支：`codex/unified-data-source-connections`

## 交付内容

- 22 个 DataHub 来源按专业数据源、API 数据源、公开来源和本机集成统一展示。
- 设置页采用来源列表与同页详情，移动端转为上下布局；模型配置默认折叠，数据源入口无需越过完整模型表单。
- MySQL、iFinD、知丘、天软、Tushare、Tavily、Bing 与 Wind 使用统一配置 API；秘密只进入系统凭据库，响应和本地 JSON 不回填秘密。
- Wind Client API 只检查当前会话，不代为登录；Excel 在没有真实工作簿心跳时保持未验证。iFinD Python SDK 探测受控登录并在 `finally` 中登出。
- 旧 `.env` 迁移提供脱敏预览、显式二次确认、Keyring 回读以及文件和秘密的补偿回滚。
- Runtime 和能力目录读取统一连接状态；缺秘密、损坏配置或凭据库故障均按单来源闭合，不会误注册工具或拖垮完整目录。

## 自动化证据

- `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web --confcutdir=tests/research_web -q`：483 passed、3 skipped、1 个 Starlette 弃用警告，74.84s。
- `node --test tests/javascript/research_web*.test.mjs`：176 passed、1 skipped。
- `node --check app/research_web/ui/{app,core,connections}.mjs`：三项通过。
- 变更 Python 文件执行 Ruff、Black check、isort check：全部通过。
- `mypy --python-version 3.12 --follow-imports skip <变更 Python 文件>`：13 个源文件通过。项目默认 `python_version=3.11` 与当前 NumPy 类型存根的 3.12 `type` 语法不兼容；强制递归全模块时另会遇到既有 `core/observability` 结构化日志类型债务，因此没有把该失败误报为全模块通过。
- `node scripts/check_research_architecture.mjs --project . --base HEAD`：无违规；接口 Atlas 由清单重新生成，122 个唯一 HTTP 操作、124 项源码声明。
- `python scripts/check_doc_sync.py --project . --base HEAD`：无违规。
- `git diff --check`：通过；限定扫描未发现对话中泄露的旧口令、主机或 `ALIYUN_DB_PASSWORD` 被写入源码、测试、文档或交付报告。
- Harness 运行时校验无漂移；任务 `unified-connections-20260908-01` 已记录 `completed/passed`，最终 `harness-enforce` 通过。
- 定向安全回归覆盖 Keyring 变更后回读失败、迁移替换后失败、损坏单来源配置、探测异常与超时、无密码 MySQL。

## 浏览器验收

使用仓库 Playwright CLI 和隔离的临时 `RESEARCH_DATA_HOME` 验收：

- 390×844、768×1024、1280×720、1440×900 均无横向溢出；390 与 768 下连接中心可见触控目标最小 44px。
- 22 个来源全部渲染；MySQL、Wind、iFinD、公开未适配来源和旧配置迁移详情切换符合契约。
- Wind 详情无账号密码输入；iFinD 展示账号池和 SDK/HTTP 选择；未适配来源不渲染虚假表单。
- MySQL 保存、留空保留、失败和删除通过浏览器路由模拟验证；密码输入在成功和失败等待前均被清空。
- 深色和浅色主题均检查；键盘 Tab 可到达来源按钮，焦点轮廓为 2px。
- 视觉回执位于 `outputs/unified-connections/`。隔离服务未承诺 DSH 在线，因此模型目录出现的 503 仅作为预期运行环境状态记录，不计为连接中心错误。

## 未验证与风险

- 未使用真实 MySQL、Wind、iFinD 或 Excel 授权环境；厂商连通性和真实工作簿心跳未验证，也未宣称可用。
- iFinD HTTP 登录协议没有仓库内可验证契约，当前明确返回 `http_probe_not_implemented`，不会标记健康。
- Wind/iFinD 尚未完成 DataHub Provider 的来源继续显示“尚未适配”，即使组件或登录探测通过也不会进入 Runtime。
- 本轮为网页服务跨操作系统契约，不包含桌面端或 Windows 安装级验证。
