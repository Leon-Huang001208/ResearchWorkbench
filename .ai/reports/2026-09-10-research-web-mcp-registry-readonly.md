# Research Web Phase 2A：只读 MCP Registry

## 结果与范围

Phase 2A 在 Research Web 的 Tool 工作区增加功能开关保护的只读 MCP 市场。实现由以下已提交
变更组成：

- `6ef01be0`：只读 Registry 后端；
- `17ce754a`、`16ef91e1`、`6a46bb34`：安全边界与内容摘要修正；
- `d9e3f725`、`2cb72ccd`：MCP 市场 UI 及异步请求归属修正；
- `50d7b067`：详情请求归属、包事实文案和最终 sink 单次转义；
- `c6c3697b`、`f87d8f2c`：Registry 安全传输、Unicode plain-text 规范化与包事实字段；
- 本报告所在 Task 3 提交：文档、架构、API Atlas 和浏览器证据。

本阶段不增加依赖，不安装、启用或调用 MCP server，不执行 Publisher CLI，也不改变 DSH
Runtime。阶段 2B 的安装/授权/运行时及阶段 2C 的 Automation/外发尚未实施。

## 组件与边界

- `app/research_web/mcp_registry/` 聚合官方和用户显式配置的私有 Registry；身份固定为
  `(registry_id, server_name, version)`，同名不合并。
- 官方适配器固定 `/v0.1`，游标按不透明值传递。ETag、同步时间、游标与最后成功目录原子提交；
  上游失败只返回 `stale` 缓存，不以空结果覆盖。
- Bearer/OAuth 秘密仅由系统凭据库服务 `ResearchWorkbench.MCPRegistry` 持有。缓存和 API 保存并
  返回经过 schema 校验、长度限制和纯文本处理的规范化目录元数据，包括名称、描述、包及远程元数据，
  以支持浏览与离线降级；字符串保持 Unicode plain text，拒绝 control/surrogate，数据层不做 HTML
  entity escape，UI 只在最终 HTML sink 转义一次。它们不保存 token 或原始上游响应体；日志不记录
  凭据、第三方描述或原始上游响应体。
- Registry 默认只允许 HTTPS；HTTP 仅允许 `auth=none` 且 host 精确为 `127.0.0.1`、`localhost` 或
  `::1` 的显式 loopback，OAuth 授权/token 端点始终要求 HTTPS，HTTP 客户端不跟随重定向。
- `#/skills?kind=tool&view=market` 展示 Registry、搜索、离线缓存、版本卡片和详情。第三方字段只
  作为文本，不渲染 HTML、不加载远程图标；包类型识别和不可变引用分别由
  `package_type_supported` / `immutable_reference` 表达，不作 Stage 2A 可安装承诺。搜索或 Registry
  替换结果集会使旧详情请求失效，迟到详情不渲染且当前输入/选择焦点保留。
- Publisher preview/validate 只返回规范 `server.json`、SHA-256、完整外部 CLI argv 和
  `executed:false`，由用户在应用外完成官方 CLI 登录与发布。

## 开关与发布顺序

`RESEARCH_MCP_REGISTRY_ENABLED` 默认为关闭。合入并通过 CI 后可单独开启只读 Registry；出现
目录或上游问题时可关闭该开关，不影响能力目录、报告 Workflow、DataHub 或研究会话。阶段 2B、
2C 必须继续使用各自独立开关，不由本次交付提前开启。

## 实际验证

- `node --test tests/javascript/*.test.mjs`
  - 235 项：234 passed、1 skipped、0 failed。
- `PYTHONPATH=/tmp/rwb-pytest-shim .venv/bin/python -m pytest -q tests/research_web/test_mcp_registry.py tests/research_web/test_api.py -k 'mcp or registry or publisher'`
  - 68 passed、25 deselected。
- `PYTHONPATH=/tmp/rwb-pytest-shim .venv/bin/python -m pytest -q tests/research_web`
  - 642 passed、4 skipped、13 failed、1 error；失败均位于既有环境边界：沙箱子解释器缺少
    `docx`/`openpyxl`、当前环境缺少 `pymysql`，以及既有 report workflow integration 事件循环
    fixture 错误。MCP Registry 聚焦测试全绿，未为完整套件安装依赖或改动无关代码。
- `.venv/bin/python -m ruff check app/research_web/mcp_registry tests/research_web/test_mcp_registry.py`
  - passed。
- `.venv/bin/python -m black --check app/research_web/mcp_registry tests/research_web/test_mcp_registry.py`
  - 9 files unchanged。
- `.venv/bin/python -m isort --check-only app/research_web/mcp_registry tests/research_web/test_mcp_registry.py`
  - passed。
- `.venv/bin/python -m mypy --follow-imports=skip --ignore-missing-imports app/research_web/mcp_registry`
  - 8 source files passed。按项目默认 import traversal 的首次运行另暴露既有
    `core/observability/{tracer,metrics}.py` 13 项 Logger 关键字参数类型债务，未改动该范围。
- `.venv/bin/python scripts/check_doc_sync.py --project . --base a95532d7`
  - passed；内部 Research architecture gate 为 0 violations。
- `node scripts/check_research_architecture.mjs --project . --base a95532d7`
  - 0 violations。
- `node --test tests/javascript/research_web_architecture.test.mjs`
  - 52 passed。
- `node scripts/build_research_web_api_atlas.mjs .`
  - 137 declarations、135 unique operations、9 categories；`/mcp/` 归类为 MCP Registry。
- Archify `validate`、`deliver`、`visual-check`
  - 图 02 showcase 9/9，0 errors、0 warnings；1440/1600/1920/2048 containment 通过。
  - 人工查看同哈希的 1440 与 2048 Light/Dark 四张截图，未见遮挡、裁剪或穿线。
- `node tests/e2e/research_web_mcp_marketplace.mjs`
  - 1440/1280/768/390 × Light/Dark 共 8 个组合通过，列数分别为 4/3/2/1，无横向溢出。
  - 覆盖 route/type isolation、Registry selector、搜索、stale/offline、客户端包类型与不可变引用
    两项事实，以及恶意 fixture 描述完整字面值仍作为可见纯文本且未生成 `img`/`script` 节点；搜索
    和 Registry 替换结果集时迟到详情被抑制、上下文焦点保留。dialog、Escape、遮罩、焦点恢复和
    reduced-motion 通过；0 浏览器错误、0 写请求、0 安装、0 Publisher 执行。fixture 为本地确定性
    服务，不访问公网 Registry。
- `node --check tests/e2e/research_web_mcp_marketplace.mjs`、
  `node --check scripts/build_research_web_api_atlas.mjs`、`git diff --check`
  - passed。

浏览器截图及 receipt 位于 `outputs/research-web-mcp-marketplace/`；架构 HTML、deliver receipt、
visual-check receipt 与四张人工查看截图位于 `outputs/research-web-architecture/`。

最终安全与请求归属修复后另实际执行：

- `PYTHONPATH=/tmp/rwb-pytest-shim .venv/bin/python -m pytest tests/research_web/test_mcp_registry.py tests/research_web/test_api.py --confcutdir=tests/research_web -q -o addopts='' --tb=short --show-capture=no`
  - 108 passed。
- `node --test tests/javascript/research_web_mcp_marketplace.test.mjs tests/javascript/research_web_architecture.test.mjs`
  - 70 passed、0 failed、0 skipped。
- `node tests/e2e/research_web_mcp_marketplace.mjs`
  - 8 个 viewport/theme 组合通过、0 写请求；receipt 中 `thirdPartyTextExact`、
    `supersededDetailSuppressed` 与 `resultContextFocusPreserved` 均为 `true`。
- API Atlas 重建仍为 137 declarations、135 unique operations、9 categories，生成物无变化；文档同步
  与 Research architecture checker 均为 0 violations，`git diff --check` 通过。
- 最终修复没有新增路由、模块节点、持久目录或跨模块依赖，因此未重新运行 Archify
  validate/deliver/visual-check；图 02 继续准确表达既有拓扑。

## 未验证与剩余工作

- 未验证公网 Registry、真实私有 Registry 鉴权、外部 Publisher CLI 登录/发布或远端 CI。
- 未执行 Windows/Linux 浏览器或桌面/Tauri/原生通知检查；本批是 Web-only。
- 未实现 MCP 安装、OAuth 运行授权、工具调用、schema 快照、DSH Runtime 重启/回滚。
- 未实现 Automation、日程、运行恢复、MCP 无人值守授权或 SMTP/Webhook/群机器人交付。
