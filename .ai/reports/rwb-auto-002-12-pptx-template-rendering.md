# RWB-AUTO-002-12: PPTX 模板上传和占位符渲染实现报告

## 日期

2026-05-11

## 概述

本任务实现了 PPTX（PowerPoint）模板上传、占位符发现和模板渲染功能，与已有的 DOCX 功能保持一致。

## 实现内容

### 1. PowerPointProjection 类 (`reporting/projections/powerpoint.py`)

新增 `PowerPointProjection` 类，提供以下功能：

- **基本演示文稿生成** (`save()`)
  - 标题幻灯片
  - 内容幻灯片（支持多个 SectionOutput）
  - 元数据展示
  - 警告信息展示

- **基于模板的渲染** (`save_from_template()`)
  - 加载 PPTX 模板文件
  - 替换文本框和表格中的占位符
  - 支持 `{{placeholder}}` 和 `{placeholder}` 格式
  - 支持添加表格和图表图片

- **占位符替换** (`_replace_placeholders_in_presentation()`)
  - 遍历所有幻灯片的所有形状
  - 检查文本框和表格
  - 保持原始格式

### 2. TemplateManager 增强 (`reporting/templates/template_manager.py`)

新增 `discover_placeholders_from_pptx()` 方法：

- 从 PPTX 模板中自动发现占位符
- 支持从文本框、表格、页眉页脚中提取
- 使用与 DOCX 相同的占位符识别逻辑

### 3. 新增测试文件 (`tests/unit/test_powerpoint_projection.py`)

- 测试基本演示文稿生成功能
- 测试模板渲染功能
- 测试错误处理（缺少依赖、文件不存在等）
- 测试表格和占位符替换

### 4. 现有测试更新 (`tests/unit/test_template_manager.py`)

- 新增 PPTX 占位符发现测试
- 确保 PPTX 文件管理与其他类型一致

## 功能特性

### 占位符格式

支持两种占位符格式：
- `{{placeholder_name}}` - 双大括号格式
- `{placeholder_name}` - 单大括号格式

### 文件管理

PPTX 模板文件存储在 `reporting/templates/pptx/` 目录，命名为 `{template_name}_template.pptx`。

### 向后兼容性

- 如果依赖 `python-pptx` 未安装，会抛出明确的 `ImportError`
- 所有测试在缺少依赖时都会正确跳过
- 不影响现有功能的正常使用

## 测试覆盖

| 测试文件 | 测试数量 | 结果 |
|---------|---------|-----|
| test_powerpoint_projection.py | 9 | ✅ 全部通过 |
| test_template_manager.py (PPTX 相关) | 3 | ✅ 全部通过 |
| test_word_projection.py (现有) | 10 | ✅ 全部通过 |

## 依赖说明

新增依赖：
- `python-pptx >= 0.6.21` (可选，但推荐安装)

已安装的版本：
- `python-pptx 1.0.2`
- `XlsxWriter 3.2.9` (由 python-pptx 引入)

## 使用示例

### 保存 PPTX 模板

```python
from reporting.templates.template_manager import TemplateManager

tm = TemplateManager()

# 保存 PPTX 模板文件
with open("my_template.pptx", "rb") as f:
    tm.save_template_file("my_template", "pptx", f.read())
```

### 发现占位符

```python
# 从 PPTX 模板发现占位符
placeholders = tm.discover_placeholders_from_pptx("my_template")
print(f"发现占位符: {placeholders}")
```

### 渲染报告

```python
from reporting.projections.powerpoint import PowerPointProjection
from core.contracts import SectionOutput

projection = PowerPointProjection()

template_path = tm.get_template_file_path("my_template", "pptx")
output_path = "output.pptx"

sections = [
    SectionOutput(
        key="executive_summary",
        title="Executive Summary",
        content="Q2 results were strong...",
    ),
]

placeholders = {
    "title": "Q2 Investment Report",
    "date": "2026-05-11",
}

projection.save_from_template(
    output_path,
    template_path,
    sections,
    placeholders=placeholders,
)
```

## 成功标准对照

| 标准 | 状态 | 说明 |
|-----|-----|------|
| PPTX 模板可以上传 | ✅ | 通过 `save_template_file()` 支持 |
| 占位符可以发现或声明 | ✅ | 通过 `discover_placeholders_from_pptx()` 支持 |
| 渲染的 PPTX 输出可以生成 | ✅ | 通过 `PowerPointProjection.save_from_template()` 支持 |
| 创建 PPTX 模板渲染报告 | ✅ | 即本文档 |

## 下一步建议

下一个任务是 RWB-AUTO-002-13：添加模板管理 API，为这些功能提供 Web 访问接口。
