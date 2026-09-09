# Research Web 设置分页交付报告

- 日期：2026-09-09
- 范围：Research Web 设置界面与 Hash 路由
- 合入目标：主目录 `ResearchWorkbench`（`master`，未提交、未推送）
- 来源工作区：`.worktrees/settings-pagination-v0`
- 合入前备份：`/tmp/research-workbench-settings-merge-20260909-3df21314`

## 交付内容

- 设置拆为通用、模型服务、数据源、本机集成和架构文档五个规范 Hash 子页，每次只渲染当前页。
- 桌面在现有产品导航内使用 200px 粘滞分类栏；760px 以下改为可横向滚动且不低于 44px 的触控标签。
- `#/settings` 和非法子页回退至通用；旧 `#/settings?connection=<id>` 深链继续兼容，并按来源归入数据源或本机集成。
- 数据源页只显示专业、API 和公开来源；本机集成页只显示本机分组。迁移入口仅在数据源页保留。
- 刷新按子页读取模型运行时或连接状态；通用和架构文档页不显示刷新。
- 模型与连接表单、秘密清除、移除、探测、账号池和迁移仍使用原控制器与 API 契约。

## 主目录与 8088 验证

- `node --check app/research_web/ui/{settings,app,core,connections}.mjs`：通过。
- 分页、连接、路由与架构相关 JavaScript 测试：94 通过，零失败。
- `node --test tests/javascript/research_web*.test.mjs`（`RWB_TEST_PYTHON=/Users/leon/opt/anaconda3/bin/python`）：186 通过、1 跳过、1 失败；失败项只检查仓库相对 `.venv/bin/python`，而主目录当前没有该解释器。
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/research_web --confcutdir=tests/research_web -q`：566 通过、3 跳过、2 失败、1 个清理错误。失败分别来自缺失 `.venv/bin/python`、当前解释器未安装 `pymysql`，以及既有报告工作流测试清理时事件循环已关闭；本轮没有修改 Python 源码或依赖。
- `node scripts/check_research_architecture.mjs --project . --base HEAD`：零违规。
- `/Users/leon/opt/anaconda3/bin/python scripts/check_doc_sync.py --project . --base HEAD`：通过。
- `node .agents/project-constraints.mjs --project /Users/leon/Desktop/Projects/ResearchWorkbench`：零违规。
- `git diff --check`：通过；分页增量的高置信敏感信息扫描为零命中文件。
- `git apply --reverse --check /tmp/research-workbench-settings-merge-20260909-3df21314/main-working-tree.patch`：通过，证明合入前主目录已有的受跟踪改动仍完整存在。
- 8088 的 `/static/app.mjs`、`/static/settings.mjs` 与 `appearance.css` 已直接回读到新路由、五分类导航、200px 桌面设置栏及 44px 移动标签；静态响应为 `Cache-Control: no-store`。

## 8088 浏览器冒烟

- 在 `http://127.0.0.1:8088` 实际查看了通用、模型服务、数据源、本机集成和架构文档五页；每页顶部与正文标题随当前分类切换，设置导航始终只标记一个当前页。
- 通用页只显示外观；模型页显示 DSH 状态与模型表单；数据源页显示 21 个专业/API/公开来源；本机集成页只显示 `local` 分组及 Excel、Wind、iFinD、报告工作流的平台检测状态；架构页只显示只读文档入口。
- 非法路由 `#/settings/not-a-real-section` 安全渲染通用页；旧 `#/settings?connection=local_cache` 进入本机集成，旧 `#/settings?connection=mysql` 进入数据源并选中 MySQL。
- 检查只读取同源页面与状态，没有提交模型配置、连接表单、探测或迁移。结束时已把浏览器返回 `#/settings/general`。
- 8088 直接从主目录按请求读取静态文件，因此无需重启即可生效；没有执行 `rwb web restart`，避免在主目录 `.venv` 缺失时中断当前可用服务。

## 架构与风险

- 后端 API、凭据库、DataHub、Runtime 和数据库结构未变，架构拓扑标记为未变。
- 本轮不涉及 Tauri、sidecar、安装包或 Windows 运行时，未执行桌面与 Windows 验证。
- 未安装或更新任何依赖。
- 未提交、推送、清理隔离 worktree，也未改写主目录无关文件。
