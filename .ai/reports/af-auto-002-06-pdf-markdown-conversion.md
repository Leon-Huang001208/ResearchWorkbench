# AF-AUTO-002-06: PDF 到 Markdown 转换管道

## 概述

本任务完成了可插拔的 PDF 转换策略层，支持原始文本提取回退和可选的 Markdown 转换策略。

## 新增文件

### 1. `data_layer/crawlers/utils/pdf_converter.py`

PDF 转换工具模块，提供完整的转换框架：

#### 核心组件

| 组件 | 说明 |
|------|------|
| `PDFConversionResult` | 转换结果数据类 |
| `PDFConversionStrategy` | 转换策略抽象基类 |
| `RawTextStrategy` | 原始文本提取策略（pdfplumber） |
| `MarkItDownStrategy` | MarkItDown 转换策略（可选） |
| `PDFConverter` | 转换器主类 - 策略管理和调用 |

#### 便捷函数

| 函数 | 说明 |
|------|------|
| `get_converter()` | 获取全局转换器实例 |
| `convert_pdf()` | 便捷转换函数 |
| `convert_and_save()` | 转换并保存结果 |

### 2. 更新 `data_layer/crawlers/utils/__init__.py`

导出新的 PDF 转换相关组件。

## 修改文件

### 1. `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py`

#### 新增参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enable_pdf_conversion` | `False` | 是否启用 PDF 转换 |
| `markdown_dir` | `"markdown"` | Markdown 输出目录 |
| `raw_text_dir` | `"raw_text"` | 原始文本输出目录 |

#### 输出 JSON 新增字段

| 字段 | 说明 |
|------|------|
| `markdownPath` | Markdown 文件相对路径（如果转换） |
| `rawTextPath` | 原始文本文件相对路径（如果转换） |
| `pdfConversionStrategy` | 使用的转换策略名称 |

## 转换策略

### 策略优先级

1. **markitdown** - 如果可用，优先使用（需要安装 markitdown）
2. **raw_text** - 总是可用（基于 pdfplumber）

### 回退机制

- 如果首选策略不可用，自动回退到次选策略
- 如果某策略转换失败，回退到原始文本提取
- 即使转换失败，也会保留错误信息并尝试提取原始文本

## 目录结构

```
{output_dir}/
├── reports.json              # 研报数据
├── pdfs/                     # PDF 文件
│   ├── {broker}/
│   │   └── {report}.pdf
│   └── ...
├── pdf_metadata/             # PDF 元数据
│   └── {obj_id}_metadata.json
├── markdown/                 # Markdown 输出
│   └── {report}.md
└── raw_text/                 # 原始文本输出
    └── {report}_raw.txt
```

## 使用示例

### 基本使用

```python
from data_layer.crawlers.utils import convert_pdf

# 转换单个 PDF
result = convert_pdf("path/to/report.pdf")
if result.success:
    print(f"使用策略: {result.strategy_used}")
    print(f"原始文本长度: {len(result.raw_text)}")
    print(f"Markdown 长度: {len(result.markdown)}")
```

### 转换并保存

```python
from data_layer.crawlers.utils import convert_and_save

result, paths = convert_and_save(
    pdf_path="path/to/report.pdf",
    output_dir="output/markdown",
    save_raw=True,
    save_markdown=True,
)

if result.success:
    print(f"保存的文件: {paths}")
```

### ZQ 爬虫集成

```python
from data_layer.crawlers.zq.zhiqiu.processors.report_processor import ReportProcessor

processor = ReportProcessor(client)

# 启用 PDF 下载和转换
df, new_reports, skipped, stopped = processor.process(
    data=api_response,
    output_file="output/reports.json",
    enable_pdf=True,
    enable_pdf_conversion=True,  # 启用转换
    pdf_dir="pdfs",
    markdown_dir="markdown",
    raw_text_dir="raw_text",
    output_dir="output",
)
```

### 自定义转换器

```python
from data_layer.crawlers.utils import PDFConverter, PDFConversionStrategy

# 创建自定义转换器
class MyStrategy(PDFConversionStrategy):
    def is_available(self) -> bool:
        # 检查是否可用
        return True
    
    def convert(self, pdf_path: str) -> PDFConversionResult:
        # 实现转换逻辑
        pass
    
    def get_name(self) -> str:
        return "my_strategy"

# 注册自定义策略
converter = PDFConverter()
converter.register_strategy(MyStrategy())
```

### 查看可用策略

```python
from data_layer.crawlers.utils import get_converter

converter = get_converter()
print("可用策略:", converter.get_available_strategies())
```

## 可选依赖

为了启用 MarkItDown 策略，可以安装：

```bash
pip install markitdown
```

## 成功标准

- ✅ PDF 摄入策略抽象已实现
- ✅ Markdown 转换输出与原始文本分开存储
- ✅ 外部转换器不可用时回退路径正常工作
- ✅ 转换策略报告已创建

## 下一步建议

- **AF-AUTO-002-07**: 审计和扩展数据库 schema 以支持存储转换结果元数据
- **AF-AUTO-002-08**: 添加摄入监控和管理端点
