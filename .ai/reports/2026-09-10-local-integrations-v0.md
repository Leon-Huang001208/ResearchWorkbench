# 本机集成真实诊断 v0

## 范围

- 将 `#/settings/local` 改为五类本机能力诊断控制台，每项独立显示发现、授权、验证和可调用状态。
- 新增专用安全投影及幂等探测 API；ResearchService 负责管理器生命周期。
- macOS 区分 Office 应用、xlwings 桥、Wind 终端和 WindAddin；普通同花顺客户端不作为 iFinD 证据。
- 保留 DataHub `/data/connections`、`local_cache` 和数据源页行为；WindPy 与 iFinD 数据接口不作为本机等权检测行。

## 安全与限制

- 探测只读取标准应用位置、已知注册信息和模块可用性，不启动厂商软件。
- 前端投影不包含命中路径、环境变量、注册表值、命令参数或秘密；异常只记录安全错误类型。
- v0 尚未实现文件夹同步、浏览器扩展配对、本地 MCP 授权和 Office/Wind 真实操作验证；Windows 仅通过依赖注入覆盖/注册路径测试，没有原生验收。

## 验证证据

- `conda run -n base python -m pytest tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q`
- `conda run -n base python -m pytest tests/research_web/test_local_integrations.py tests/research_web/test_api.py tests/research_web/test_connection_center.py --confcutdir=tests/research_web -q`
- `node --test tests/javascript/research_web_local_integrations_ui.test.mjs tests/javascript/research_web_settings_ui.test.mjs tests/javascript/research_web_connections_ui.test.mjs tests/javascript/research_web_ui.test.mjs`

以上命令在实现期间分别通过 5 项、52 项和 57 项测试；最终交付检查结果以本任务提交前的实际命令为准。
