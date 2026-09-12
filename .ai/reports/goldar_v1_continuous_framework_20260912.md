# Goldar V1 连续研究框架交付报告

## 结果

- 将黄金详情从七个独立页签收敛为一张连续研究画布，保留七个语义锚点与旧 `?tab=` 深链兼容。
- 使用 Lieflat Basics F2、F9、F6、F5 四张图承担价格、驱动贡献、需求同比和期权压力比较；周期、配置、事件和证据改用紧凑结构，不再堆图。
- 新增黄金专用版本化定义、严格快照契约、内容 revision、大小限制、链接拒绝、原子写入和旧 V0 快照保留迁移。
- 新增页面 Bot：默认解释模式无工具；用户显式深度验证时新建受限 DSH 会话并调用 `framework-research`。两种模式都绑定精确快照 revision，不能写回评分或快照。
- 资产观察边界不变。个股、基金、债券、外汇和商品详情没有迁入框架页。

## 可扩展边界

`frameworks/base.py` 只共享框架元数据、来源、缺口和区块新鲜度协议。黄金方法、因果链、反证、字段、状态门和页面 renderer 保持专用。后续黄金逻辑通过新增版本和迁移演进；Dollar 或行业框架各建独立专用包，至少两个真实框架出现重复后才抽取共用 schema 或组件。

## 变更—证据清单

| 源变更 | 测试 | 文档 | 证据 / 结果 |
| --- | --- | --- | --- |
| `app/research_web/frameworks/`：定义、契约、存储、API、DSH 绑定 | `tests/research_web/test_frameworks.py` | `docs/architecture/research-web/08-research-frameworks.md`、API/安全/数据文件文档 | 框架测试 6 项通过；精确 revision、迁移、链接拒绝、双预设和生命周期均有断言 |
| `ui/frameworks*`、`ui/app.mjs`、`ui/core.mjs`、`ui/appearance.css`：连续画布、四图、Bot、路由控制 | `tests/javascript/research_web_frameworks_ui.test.mjs`、Goldar E2E、Research Web JS 全套 | `docs/research-web-ui.md`、`docs/research-web-appearance.md` | JS 263/263（另 1 跳过）；10 组视口及 13 张截图通过人工查看 |
| `launch_runtime.py`、两个框架 preset、`framework-research` Skill、能力种子 | `test_runtime_launch.py`、`test_sell_side_report_skill.py`、能力准入测试 | Runtime、能力、Tabbit 边界文档 | Python 聚焦 107 项通过；定向 Ruff/Black/isort/mypy 通过 |
| `main.py`、`service.py`：路由与单一生命周期装配 | 框架 API 测试及既有 `test_api.py` | 架构、开发地图、架构清单与 review record | 架构门禁 `violations: []`；未增加第二 Runtime |

完整变更范围为：上述源文件；`tests/research_web/test_capabilities.py`、`test_capabilities_admission.py`、`test_sell_side_report_skill.py` 和两个 JavaScript/E2E 测试；`docs/ARCHITECTURE.md`、`docs/DEVELOPMENT_MAP.md`、Research Web 架构/能力/UI/外观/Runtime/安全/API/数据文件文档；本报告；`outputs/goldar-v1/` 浏览器证据。没有修改桌面目录、依赖清单、数据库迁移、秘密或用户主工作树中的未提交文件。

## 已执行验证

- Python 聚焦：`107 passed`，覆盖框架、Runtime staging、Skill、能力快照和准入。
- JavaScript Research Web 全套：`263 passed, 1 skipped, 0 failed`。
- Goldar 浏览器：浅/深色 × 1440、1280、1024、768、390 共 10 组视口通过；无 document/main 横向溢出，锚点 44px，键盘导航与 reduced-motion 通过，console/page error 为空。
- Python 定向格式与静态检查：Ruff、Black、isort 全部通过；框架包 mypy `9 source files` 无问题。
- Research Web 架构完整性：`violations: []`。
- `git diff --check` 通过。

浏览器证据位于 `outputs/goldar-v1/verification.json` 及同目录截图。

## 未通过的仓库基线与限制

- Research Web Python 全套实际执行为 `877 passed, 4 skipped, 22 failed`。失败未记作通过；抽查明确包含当前环境缺少 `matplotlib`、`bs4`、`httpx2`，以及依赖本机来源/凭据可调用状态的既有测试。遵守项目约束，本轮未安装依赖，也未为无关基线改实现。
- 仓库全量 Ruff、Black、isort 与跨模块 mypy 仍有既有债务：Ruff 8347 项、Black 163 个文件、isort 多个非本任务文件、跨模块 mypy 24 项。所有本任务修改的 Python 文件已通过定向门禁。
- 当前黄金数据仍是明确标注的离线确定性 seed；真实 Goldhub、CFTC、宏观、期权等采集器未在本轮接通，页面不发布实时市场结论。
- 未涉及桌面端，也没有执行桌面或 Windows 安装级验证。
