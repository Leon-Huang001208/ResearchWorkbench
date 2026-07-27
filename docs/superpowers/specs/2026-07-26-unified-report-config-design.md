# 统一报告配置模型设计

## 目标

每个项目只使用一份
`config/report_config.yaml`；`config/prompt_templates.md` 继续作为独立的
Prompt 内容库。前端、API、生成前检查和报告渲染均使用同一个 YAML 模型，
没有兼容适配或运行时回退路径。

## 非目标

- 不把 Markdown Prompt 合并到 YAML。
- 不改变 Prompt 标题到 `prompt_template` 引用的现有关系。
- 不改变 Word/PPT、Excel、图表或表格的业务能力。

## 统一模型

- 顶层保留 `name`、`assets`、`defaults`、`charts`、`tables`、`placeholders`。
- 每个 `placeholder` 保留 `type`、`mode`、`prompt_template`、`retrieval`、
  `components`、`data_source`、`writing_structure`、校验与长度约束。
- 富文本、段落样式、可见条件与图表网格放入统一的可选 `rendering` 块。
- `prompt_template` 继续引用 `prompt_templates.md` 中同名的二级标题；
  Markdown 是 Prompt 的唯一正文来源。

## 单一运行链路

1. 项目加载只解析 `report_config.yaml`，校验为统一模型。
2. 编译计划、生成前检查、段落编辑和报告生成都消费同一个
   `UnifiedReportConfig` 归一化对象。
3. Word/PPT 渲染根据统一占位符的 `type` 和可选 `rendering` 字段分发。
4. 前端只保留一个报告配置源、一个段落草稿状态和一个保存入口。

## 文件策略

项目目录中只保留 `config/report_config.yaml` 作为 YAML 配置来源，
`project.yaml` 的 `report_config` 指向该文件。

## API 与用户体验

- 项目 API 只返回 `report_config`、`report_config_source` 与
  `prompt_templates_source`。
- 上传与保存接口只接受 `report_config` YAML 和 `prompt_templates` Markdown。
- 配置页面只显示“报告配置”和“Prompt 模板”。

## 验证

- 单元测试：统一模型解析、Prompt 引用、默认值、检索、
  Excel/图表/表格与富文本字段。
- API 测试：上传、读取、保存响应仅包含统一字段。
- 渲染测试：普通段落、复合段落、固定字段、表格、图表及富文本样式。
- 项目级冒烟：对现有报告项目执行生成前检查和一次受控渲染。

## 成功标准

任意报告项目目录中只有 `report_config.yaml` 与
`prompt_templates.md` 两个配置来源；代码、API、UI 和运行日志中均不再出现
配置分支或回退选择。
