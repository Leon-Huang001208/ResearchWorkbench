# 2026-09-08 专用研究能力去独有化接入

## 范围与来源

本轮只改造 Research Web 能力中心。受审输入来自
`/Users/leon/Desktop/zhengyan-research-skills`，按自有或已授权内容处理；输入目录未迁移、删除或
修改。用户界面与可发现 Skill 不保留来源品牌、厂商 Agent 配置或独立路由卡片；本内部报告保留
来源路径用于维护追溯。改造后的源码、协议、测试和后续版本责任归 ResearchWorkbench 维护。

本轮不修改桌面安装器、运行权限、第三方依赖、API 请求字段或能力类型；没有安装依赖、启动
线上研究、发布、推送，也没有触碰桌面原目录。macOS Research Web 测试不能作为桌面或 Windows
验证证据。

## 去独有化决策

- 保留五个原有通用 Skill 和四个 Workflow 的稳定 ID、历史版本与职责；新增五个窄边界专用
  Skill，使内置目录成为 10 Skill + 4 Workflow。
- 新增研报增量分析、金融事件研究、产业链与主题研究、业绩与一致预期、宏观与跨资产；正反
  触发边界写入各包 frontmatter、描述和分类，由现有原生 Skill discovery 路由。
- 不接入原输入中的研究 router，也不接入厂商专属 Agent 展示配置。能力中心现有动态卡片、详情、
  分类、选择和搜索已能消费新增目录，因此没有修改 UI 产品源码。
- `app/research_web/skills/_shared/evidence-protocol.md` 是不可单独调用的品牌中立协议单一源码。
  `seeds.py` 在构建时把相同字节复制到五个专用包的
  `references/evidence-protocol.md`，每个不可变版本保存自己的资源哈希。
- 五个专用 Skill 使用 `default_formats=[]`，默认聊天回答；只有用户明确要求文件且 Runtime 实际
  暴露相应工具时才生成并核验文件。四项研究只声明 `web_search`，研报能力另声明
  `research_run_script`；DataHub 和文件工具不是必然前提。
- 决定性原文、完整正文、一致预期或附件不可访问时明确输出“证据不足”或“无法判断”；搜索摘要
  只作发现线索。所有行动含义均保持条件化、可定位和非个性化。
- 研报 PDF 使用既有 `research_helpers.read_pdf`。结构化摘要校验与 SVG 知识图谱脚本已重写为
  研究沙箱内 Python，不依赖 `SKILL_DIR`、Poppler、shell、subprocess 或安装指令。v1 不裁剪 PDF
  原页；不能建立有来源定位的可靠关系时不生成 SVG，并声明视觉证据受限。
- 能力检查新增 `runtime_incompatible_script`。即使脚本已确认哈希、没有安装行为，导入
  `subprocess` 或引用受检宿主进程入口也不能发布；检查过程不执行脚本。

## 文件与提交证据

| 范围 | 主要文件 | 实现提交 |
| --- | --- | --- |
| 进程入口检查 | `capabilities/catalog.py`、`test_capabilities_safety.py` | `24e93e8f`、`61381f96`、`16d03129` |
| 声明式种子、四项专用 Skill、共享协议与会话快照 | `capabilities/seeds.py`、`skills/_shared/`、四个专用 Skill、能力/会话测试 | `c6642248`、`e7be62c0` |
| 研报增量 Skill、校验与 SVG 脚本 | `skills/sell-side-report-reader/`、`test_sell_side_report_skill.py` | `c1613b36`、`81172738`、`48b012eb`、`92a3802b` |
| 能力中心 UI 回归、架构/开发映射与内部记录 | `tests/javascript/research_web_capabilities_ui.test.mjs`、本轮文档 | 本报告所在提交；最终 SHA 记录于任务交接 |

`GET /capabilities` 的响应模型与路径未变，只增加五个内置条目；检查响应模型未变，issue code
集合新增 `runtime_incompatible_script`。没有产生或覆盖既有内置版本。

## 实际验证

所有命令在隔离 worktree
`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/zhengyan-research-capabilities`
执行，使用项目既有 `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv`，未安装依赖。

- 能力聚焦 pytest：`166 passed, 2 skipped, 1 warning`。覆盖目录、元数据、导入/导出、资源哈希、
  会话快照、脚本安全、降级情景、结构化摘要和 SVG。
- 两项 skip 均来自 `test_capabilities_native.py`：当前未提供 `DSH_SOURCE_ROOT`，因此未运行固定
  DSH 源码的原生 discovery/工具注册集成；不是通过项。
- JavaScript/UI：`47 passed`。新增测试通过项目 Python 环境实例化产品
  `CapabilityCatalog`，从 `list(kind="skill")` 获取真实种子目录，再交给现有页面函数验证十个
  唯一内置 Skill、分类、中文/技术 ID 搜索、详情、放入草稿，以及不存在
  `zhengyan-research-router` 卡片。解释器按 `RWB_TEST_PYTHON`、当前仓库 `.venv`、worktree
  所属项目 `.venv`、激活虚拟环境查找；均不可用时明确失败，不回退到手写元数据。
- `ruff check` 通过；本分支能力变更涉及的 9 个 Python 文件均通过 `black --check` 和
  `isort --check-only`。`test_capabilities_native.py` 的纯格式修复记录在 `40b47235`。
- 能力产品源码四文件的聚焦 mypy 通过。全 `app/research_web` mypy 仍在本任务未修改的
  `asset_workspace.py`、`report_workflows/migration.py`、`report_studio.py` 报 3 项既有错误；
  不把聚焦结果表述为全模块通过，也不在本轮扩展修复范围。
- `scripts/check_doc_sync.py --base 491c5529` 通过，架构门禁无 violation；能力拓扑复用既有发布、
  原生发现、沙箱和会话快照，因此没有重绘十张架构图。
- `scripts/check_task_completion.py` 与 `git diff --check` 通过。

## 已知限制与后续验收

- 缺少 `DSH_SOURCE_ROOT`，原生 DSH 集成两项保持未验证；最终环境提供固定源码后应重跑。
- 本轮没有运行真实模型、网络研究或能力中心浏览器交互；UI 证据是 Node 组件/应用事件回归，不
  等同于 live 浏览器验收。
- v1 没有 PDF 原页裁剪或 OCR。图片不可读、正文受限、缺一致预期、无实时工具、或因果关系无
  定位时必须降级，不应补造结论或图表。
- 本轮不涉及桌面、安装器、Windows CI 或真实 Windows 安装级冒烟；不得据此宣称桌面/Windows
  支持已验证。
- 原输入目录继续仅作为受审来源保存；后续协议与 Skill 版本应在 ResearchWorkbench 内维护，
  不建立双向同步或隐式覆盖机制。
