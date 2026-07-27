# 周报生成中心页面优化设计

日期：2026-06-12

## 背景

当前“华安ETF周报”详情页把生成报告、占位符配置、YAML 片段、Prompt 模板、Excel 映射、项目检查放在同一工作台层级。页面能力完整，但默认视角更像“模板配置后台”，用户在生成一篇周报时需要先理解 Word 占位符、Section 配置和 Prompt 源码，流程显得繁杂。

已有后端链路保持不变：

- `report_config.yaml` 定义统一占位符与生成规则。
- `prompt_templates.md` 定义写作模板与检索 Query。
- `/api/report-projects/{slug}/render` 执行配置解析、证据检索、逐段生成、Word 替换、图表/表格嵌入和 runs 日志落盘。

本次优化目标是调整页面信息架构，不削弱现有配置能力。

## 设计目标

1. 让“生成周报”成为页面第一目标，进入详情页后用户第一眼看到生成动作、生成条件和最近产物。
2. 引入轻量三步状态条，表达“数据 → 内容 → 输出”的生成前状态，但不强制用户走多步向导。
3. 将模板、占位符、Prompt、YAML 等维护能力保留在高级区，默认折叠，预检失败或主动维护时再展开。
4. 保留现有后端接口与报告项目目录结构，优先做前端信息架构收敛，降低改动风险。

## 页面结构

详情页从“报告模板工作台”调整为“周报生成中心”。第一屏包含四个区域：

1. 顶部生成 Hero
   - 显示报告项目名称，例如“华安ETF周报”。
   - 显示报告周期、占位符数量、证据检索回溯天数。
   - 主按钮为“生成报告”。
   - 次级动作为“预览最近版本”“下载文档”。
   - 下载按钮仅在存在最近生成文件时可用。

2. 轻量状态条
   - 三段固定状态：“数据就绪”“内容就绪”“输出就绪”。
   - 数据就绪汇总 Word 模板、主 Excel、配套数据、Section 配置。
   - 内容就绪汇总占位符映射、AI 文本段落、检索关键词和 Prompt 绑定。
   - 输出就绪汇总最近产物、预览地址、下载地址、run log。
   - 状态条用于解释生成前条件，不作为必须点击的向导步骤。

3. 最近生成与生成前检查
   - 最近生成卡片显示文件名、生成时间、证据条数、警告数、预览、下载。
   - 生成前检查显示素材齐全度、段落映射、检索样本、风险提示。
   - 预检通过时不展开细节；存在问题时展示问题列表，并提供“进入高级维护”入口。

4. 高级维护
   - 默认折叠，标题为“高级维护：模板、占位符、Prompt、YAML”。
   - 展开后保留现有工作台能力：占位符选择、字段表单、YAML 当前片段、Prompt 源码、Excel 映射、保存当前占位符、保存源码。
   - 高级区内部可继续沿用当前组件，但视觉上降级为维护区，而不是主流程。

## 用户流程

默认生成流程：

1. 用户进入报告详情页。
2. 页面自动展示当前报告周期、回溯天数和预检状态。
3. 若预检通过，用户点击“生成报告”。
4. 生成完成后，页面更新最近生成卡片，并启用“预览最近版本”“下载文档”。
5. 用户可打开预览、下载 Word，或查看证据调试与 run log。

需要维护时：

1. 预检提示某些段落缺配置，或用户主动展开高级维护。
2. 用户选择占位符，编辑字段表单。
3. 页面继续显示 YAML / Prompt 片段用于对照。
4. 用户保存当前占位符或源码。
5. 返回顶部重新生成。

## 前端改动范围

主要涉及：

- `app/web/static/js/templates.js`
- `app/web/static/style.css`
- `app/web/templates/index.html`
- `tests/unit/test_report_template_workbench_frontend.py`

建议实现时新增或重组以下前端函数：

- `renderReportGenerationCenter(template)`：渲染详情页主结构。
- `buildGenerationReadiness(template)`：统一产出数据、内容、输出三类状态。
- `renderGenerationHero(template, readiness)`：渲染顶部生成动作区。
- `renderGenerationStatusStrip(readiness)`：渲染三段轻量状态条。
- `renderRecentGenerationPanel(template)`：渲染最近生成文件与操作。
- `renderAdvancedMaintenance(template)`：包裹现有工作台维护能力。

现有函数如 `renderTemplateAssetChecklist`、`renderTemplatePlaceholderMap`、`renderSelectedPlaceholderEditor`、`renderTemplateExcelMapping` 可以优先复用，减少行为变化。

## 数据与接口

本设计不要求新增后端接口。页面可继续使用现有字段：

- `report_project.word_placeholders`
- `report_project.report_config`
- `report_project.report_config_source`
- `report_project.prompt_templates_source`
- `report_project.excel_sheets`
- `report_project.data_assets`
- `report_project.generated_reports`
- `/api/report-projects/{slug}/render`
- `/api/report-projects/{slug}/preview/{file_name}`
- `/api/report-projects/{slug}/download/{file_name}`
- `/api/report-projects/{slug}/runs/{file_name}`

如果实现时发现最近生成卡片缺少 `download_url` 或 `preview_url`，前端可根据 `slug` 和 `file_name` 拼接现有 URL，不新增 API。

## 状态与错误处理

- 预检通过：主按钮启用，状态条使用通过态，检查详情默认收起。
- 预检警告：主按钮仍可用，但显示警告数量和“查看问题”入口。
- 预检阻断：主按钮禁用或二次确认，明确列出阻断项，并提供展开高级维护入口。
- 生成中：主按钮进入 loading 状态，避免重复提交。
- 生成失败：保留错误 toast，并在最近生成区域显示失败摘要；不清空上一份成功产物。
- 没有最近生成文件：预览和下载按钮禁用，文案显示“尚未生成”。

所有错误仍通过现有前端 toast 与后端日志处理；本次设计不改变日志落盘路径。

## 测试策略

更新静态前端测试，覆盖：

- 页面包含“周报生成中心”主区域。
- 顶部存在“生成报告”“预览最近版本”“下载文档”动作。
- 存在“数据就绪”“内容就绪”“输出就绪”状态条。
- 高级维护区域默认折叠，并包含占位符、YAML、Prompt、Excel 映射相关节点。
- 现有生成、下载、run log、证据调试入口仍保留。

如实现涉及 DOM 结构较大调整，补充一次本地浏览器截图检查，确认桌面宽屏和较窄视口下没有文字重叠。

## 非目标

- 不重写后端报告生成服务。
- 不改变 `report_projects` 目录结构。
- 不移除 YAML / Prompt 源码编辑能力。
- 不把轻量状态条做成强制多步向导。
- 不新增复杂权限、审批或任务队列能力。
