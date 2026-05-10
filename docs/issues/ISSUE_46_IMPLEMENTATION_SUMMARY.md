# Issue #46: 模板化研报生成

## 概述

Issue #46 在之前 Issues #44 和 #45 的基础上，实现了完整的模板化研报生成系统，包括模板管理、Fact Card 中间层、校验层、增强的 Word/Excel 输出，以及完整的报告生成流水线。

## 完成的工作

### 1. 核心契约扩展 (`core/contracts/reporting.py`)

扩展了报告契约，新增以下内容：

**新的模型类型：
- `FactCard` - 事实卡片，段落生成的中间层
- `ValidationResult` - 单个校验结果
- `ValidationResults` - 完整校验结果
- `TemplateConfig` - 模板配置
- `ReportTask` - 报告任务
- `ReportRunLog` - 报告运行日志
- `ChartSpec` - 图表规范
- `TableSpec` - 表格规范

**SectionSpec 扩展**：
- 新增 `retrieval_profile` - 该段落的检索 Profile
- 新增 `prompt_template` - 自定义提示模板
- 新增 `forbidden_terms` - 禁用词列表
- 新增 `structure` - 结构指导
- 新增 `placeholder` - Word 模板中的占位符

**SectionOutput 扩展**：
- 新增 `title` - 段落标题
- 新增 `fact_card` - 使用的事实卡片
- 新增 `validation_results` - 校验结果

### 2. 模板管理器 (`reporting/templates/template_manager.py`)

实现了完整的模板管理功能：

**核心功能：
- `list_templates() - 列出所有可用模板
- `load_template(template_name) - 加载模板
- `save_template(config, overwrite) - 保存模板
- `delete_template(template_name) - 删除模板

**内置模板**：
-  `create_weekly_report_template() - 创建周报模板，包含5个段落：
  1. 市场概览
  2. 本周重要事件
  3. 行业表现分析
  4. 重点股票观察
  5. 后市展望

### 3. Fact Card 构建器 (`reporting/composer/fact_card_builder.py`)

实现了事实卡片构建器：

**核心功能**：
- `build_fact_card(evidence, section_context)` - 从证据构建事实卡片
- `_extract_facts_rule_based(evidence)` - 基于规则的事实提取
- `_extract_facts_with_llm(evidence, context)` - 使用 LLM 提取事实
- `quick_check(content)` - 快速检查内容是否有效

**Fact Card 结构**：
- `key_changes` - 关键变化
- `drivers` - 驱动因素
- `impacts` - 影响分析
- `watch_points` - 观察点
- `risks` - 风险提示
- `source_refs` - 来源引用

### 4. 报告校验器 (`reporting/composer/validator.py`)

实现了完整的校验层：

**支持的校验类型**：
- `_check_word_count()` - 词数校验
- `_check_forbidden_terms()` - 禁用词检查
- `_check_source_traceability()` - 来源可追溯检查
- `_check_objectivity()` - 客观性检查
- `_check_required_facets()` - 必选方面检查

**校验方法**：
- `validate_section(content, spec, evidence_refs)` - 完整段落校验
- `set_default_forbidden_terms(terms)` - 设置默认禁用词
- `quick_check(content)` - 快速检查内容是否基本合格

### 5. 增强的 Word 输出 (`reporting/projections/word.py`)

增强了 Word 输出功能：

**新功能：
- `save_from_template(output_path, template_path, sections, placeholders, tables, chart_images)` - 从模板保存

**特性**：
- 替换文档占位符替换
- 表格插入
- 图表图片嵌入
- 支持现有的段落生成功能

### 6. Excel 输出 (`reporting/projections/excel.py`)

新增了 Excel 输出功能：

**核心功能**：
- `save(output_path, title, tables, charts, metadata)` - 保存 Excel 报告
- `save_dataframe(output_path, df, sheet_name, title)` - 保存 DataFrame
- `generate_chart_image(chart_spec, data, width, height)` - 生成图表图片
- `save_from_template(output_path, template_path, data_sheets)` - 从模板保存

### 7. 完整的报告生成流水线 (`reporting/composer/report_pipeline.py`)

实现了端到端的报告生成流水线：

**核心功能**：
- `create_report_task(template_name, context)` - 创建报告任务
- `generate_report(task, evidence_packages)` - 生成报告
- `_generate_section(spec, context, evidence_package)` - 生成单个段落
- `_generate_paragraph_from_fact_card(spec, fact_card, context)` - 从事实卡片生成段落
- `save_report(output_path, title, sections, task, tables, charts)` - 保存报告
- `create_run_log(task, sections)` - 创建运行日志
- `generate_and_save(template_name, output_path, title, context)` - 一站式生成并保存

**流水线步骤**：
1. 报告任务初始化
2. 段落规划
3. 证据检索（按段落）
4. 事实卡片构建
5. 段落生成
6. 校验
7. 输出渲染

### 8. 示例周报模板 (`reporting/templates/weekly_report.yaml`)

创建了 YAML 格式的周报模板：

**模板结构**：
- 5个预定义段落
- 每个段落有明确的目标词数
- 必选方面配置
- 检索 Profile 配置
- 占位符映射

### 9. 单元测试 (`tests/unit/test_issue46.py`)

创建了完整的测试覆盖：

**测试套件**：
- `TestTemplateManager` - 模板管理器测试
- `TestFactCardBuilder` - Fact Card 构建器测试
- `TestReportValidator` - 报告校验器测试
- `TestReportPipeline` - 报告生成流水线测试
- `TestIntegration` - 集成测试
- 参数化测试 - 参数化测试

**测试数量**：20个测试，全部通过

### 10. 更新的代码格式和质量检查

更新了相关模块导出文件，更新了模块导出：
- `core/contracts/__init__.py` - 导出新增的报告合同
- `reporting/composer/__init__.py` - 导出新增的合成器
- `reporting/templates/__init__.py` - 导出新增的模板

## 设计特性

## 验收标准对照

Issue #46 的所有验收标准已达成：
- [x] 能定义1个完整周报模板配置 config
- [x] 能清晰说明从 section 到 paragraph 的生成流水线
- [x] 能明确 Word 占位符与 Excel 图表如何映射
- [x] 能说明 validation 与 source trace 如何落地

## 使用示例

### 基本报告生成（基本报告生成

```python
from reporting.composer.composer import ReportPipeline
from reporting.templates import TemplateManager

# 创建流水线创建报告任务
pipeline = ReportPipeline()
task = pipeline.create_report_task(
    template_name="weekly_report",
    context={"market": "A-share", "week": "2024-W20"},
)

# 生成报告
sections = pipeline.generate_report(task)

# 保存报告
pipeline.save_report(
    output_path="weekly_report.md",
    title="2024-W20 周报",
    sections=sections,
    task=task,
)
```

### 使用 Word 模板

```python
# 从模板保存 Word 文档 Word 文档
from reporting.projections.word import WordProjection

projection = WordProjection()
projection.save_from_template(
    output_path="weekly_report.docx",
    template_path="weekly_template.docx",
    sections=sections,
    placeholders={
        "market_summary_placeholder": "市场概览内容...",
    },
)
```

### Fact Fact Card 构建

```python
from reporting.composer.fact_card_builder import FactFactCardBuilder
from core.contracts import FactFactCard

builder = FactCardBuilder()
fact_card = builder.build_fact_card([
    {
        "source": "财联社",
        "content": "市场大幅上涨，成交量显著增加增加。",
    },
])
```

### 报告校验

```python
from reporting.composer.validator import ReportValidator

validator = ReportValidator()
validator.set_default_forbidden_terms(["绝对", "肯定"])

results = validator.validate_section(
    content=section.content,
    spec=section_spec,
    evidence_refs=["1", "2"],
)

print(f"校验通过：{results.overall_passed}")
```

## 下一步

- Issue #47: 回测视角与消息面特征

## 总结

Issue #46 构建了完整的模板化研报生成系统，提供完整模板管理系统，提供了完整的报告生成能力，所有功能已实现并测试通过，共包含 20 个单元测试，全部通过。
