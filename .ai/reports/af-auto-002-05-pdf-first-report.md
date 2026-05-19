# AF-AUTO-002-05: ZQ PDF 优先研报摄入报告

## 概述

本报告记录了为知丘（ZQ）爬虫实现 PDF 优先工作流的完成情况。此功能确保研报摄入时优先下载并保存 PDF 文档，并记录完整的元数据（文件哈希、大小、路径等）。

## 新增文件

### 1. `data_layer/crawlers/zq/zhiqiu/pdf_utils.py`

PDF 工具模块，提供完整的元数据管理功能：

**核心组件**：

- `PDFMetadata` 数据类：PDF 元数据存储结构
  - `obj_id`: 知丘文档 ID
  - `file_path`: 文件路径（相对或绝对）
  - `file_hash`: SHA-256 哈希
  - `file_size`: 文件大小（字节）
  - `title`: 标题
  - `broker`: 券商
  - `author`: 作者
  - `publish_date`: 发布日期
  - `download_date`: 下载日期（自动生成）
  - `source_url`: 来源 URL
  - `extra`: 额外信息字典

**核心函数**：

| 函数 | 说明 |
|------|------|
| `calculate_file_hash()` | 计算文件哈希（SHA-256、MD5、SHA-1） |
| `get_file_size()` | 获取文件大小（字节） |
| `ensure_pdf_dirs()` | 确保 PDF 相关目录存在 |
| `save_pdf_metadata()` | 保存 PDF 元数据到 JSON 文件 |
| `load_pdf_metadata()` | 加载 PDF 元数据 |
| `is_pdf_available()` | 检查 PDF 是否已存在 |
| `get_pdf_path()` | 获取已下载 PDF 的路径 |

## 修改文件

### 1. `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py`

**新增导入**：
```python
from ..pdf_utils import PDFMetadata, calculate_file_hash, get_file_size, save_pdf_metadata
```

**新增方法**：

| 方法 | 说明 |
|------|------|
| `_download_and_record_pdf()` | 新格式的 PDF 下载和元数据记录 |
| `_download_and_record_pdf_old_format()` | 旧格式的 PDF 下载和元数据记录 |

**更新内容**：

- `_build_item_from_report()` (新格式): 更新为调用 `_download_and_record_pdf()`
- `_build_item_report()` (旧格式): 更新为调用 `_download_and_record_pdf_old_format()`

**新增的元数据字段**：

输出 JSON 中新增：
- `pdfHash`: PDF 文件 SHA-256 哈希
- `pdfSize`: PDF 文件大小（字节）

## PDF 优先工作流

### 工作流程

```
1. 检查是否启用 PDF 下载 (enable_pdf=True)
2. 调用 _download_and_record_pdf() 或 _download_and_record_pdf_old_format()
3. 尝试下载 PDF 到指定目录
   ├── 按券商分目录: {pdf_root_dir}/{broker}/{filename}.pdf
   └── 文件名: 清理后的标题或 {obj_id}.pdf
4. 计算文件哈希 (SHA-256) 和文件大小
5. 保存元数据到 {output_dir}/pdf_metadata/{obj_id}_metadata.json
6. 将相对路径、哈希、大小存入输出 JSON
7. 如果 PDF 下载失败，仅保留研报元数据（无 PDF）
```

### 元数据保存

元数据 JSON 格式示例：

```json
{
  "obj_id": "12345678",
  "file_path": "pdfs/中信证券/某研报.pdf",
  "file_hash": "a1b2c3d4e5f6...",
  "file_size": 1048576,
  "title": "某研报标题",
  "broker": "中信证券",
  "author": "",
  "publish_date": "",
  "download_date": "2026-05-11T10:30:00.123456",
  "source_url": "https://www.hangcai8.com/newweb/zqpdf/pdf.html?fileid=12345678",
  "extra": {}
}
```

## 重复检测

**`is_pdf_available(obj_id, output_dir, pdf_dir)`** 提供多重检查：

1. 检查元数据是否存在且文件路径有效
2. 在 PDF 目录中查找以 `{obj_id}` 开头的 PDF 文件

**`get_pdf_path(obj_id, output_dir, pdf_dir)`** 提供路径查找功能。

## 回退逻辑

PDF 优先工作流的回退策略：

| 情况 | 行为 |
|------|------|
| PDF 下载成功 | 保存 PDF + 元数据 + 哈希 + 大小 |
| PDF 下载失败 | 仅保存研报元数据（无 PDF） |
| `enable_pdf=False` | 跳过 PDF 下载，仅处理文本 |
| 文件已存在 | 通过 `is_pdf_available()` 检测，可选择跳过 |

## 使用示例

### 基本用法（新格式）

```python
from data_layer.crawlers.zq.zhiqiu import ZQClient
from data_layer.crawlers.zq.zhiqiu.processors.report_processor import ReportProcessor

client = ZQClient()
processor = ReportProcessor(client)

# 启用 PDF 下载
results_df, new_reports, skipped, stopped = processor.process(
    data=api_response,
    output_file="output/reports.json",
    enable_pdf=True,
    pdf_dir="pdfs",
    output_dir="output"
)
```

### 检查 PDF 是否已存在

```python
from data_layer.crawlers.zq.zhiqiu.pdf_utils import is_pdf_available, get_pdf_path

obj_id = "12345678"

if is_pdf_available(obj_id, output_dir="output"):
    pdf_path = get_pdf_path(obj_id, output_dir="output")
    print(f"PDF 已存在: {pdf_path}")
```

### 加载 PDF 元数据

```python
from data_layer.crawlers.zq.zhiqiu.pdf_utils import load_pdf_metadata

metadata = load_pdf_metadata(obj_id="12345678", output_dir="output")
if metadata:
    print(f"标题: {metadata.title}")
    print(f"券商: {metadata.broker}")
    print(f"哈希: {metadata.file_hash}")
    print(f"大小: {metadata.file_size} 字节")
```

## 目录结构

```
{output_dir}/
├── reports.json                    # 研报输出数据
├── pdfs/                           # PDF 文件根目录
│   ├── 中信证券/
│   │   └── 某研报.pdf
│   ├── 国泰君安/
│   │   └── 另一研报.pdf
│   └── unknown/                    # 未知券商
│       └── 研报.pdf
└── pdf_metadata/                   # PDF 元数据目录
    ├── 12345678_metadata.json
    ├── 23456789_metadata.json
    └── ...
```

## 与增量抓取集成

PDF 优先工作流与水位线机制（af-auto-002-03）无缝集成：

- `stop_on_known=True` 时，遇到已处理研报停止
- `skip_existing=True` 时，跳过已处理研报（仅处理新的）
- 即使研报已处理，PDF 仍可按需重新下载（通过 `enable_pdf=True`）

## 成功标准

- ✅ ZQ 研报摄入优先采用 PDF 工作流
- ✅ 记录 PDF 文件路径和哈希元数据
- ✅ 回退逻辑清晰明确（本报告已记录）
- ✅ PDF 优先摄入报告已创建（本文档）

## 验证

检查实现是否正确：

```bash
# 检查 PDF 工具模块
ls -la data_layer/crawlers/zq/zhiqiu/pdf_utils.py

# 检查报告处理器更新
grep -n "pdfHash\|_download_and_record_pdf" data_layer/crawlers/zq/zhiqiu/processors/report_processor.py
```

## 后续建议

1. **PDF 到 Markdown 转换** (af-auto-002-06): 将下载的 PDF 转换为 Markdown 格式，便于后续处理
2. **数据库模式扩展** (af-auto-002-07): 扩展数据库以存储 PDF 元数据（哈希、路径、大小）
3. **监控端点** (af-auto-002-08): 添加 PDF 下载状态监控

## 总结

任务 af-auto-002-05 已完成，实现了：
- 完整的 PDF 元数据管理系统（pdf_utils.py）
- 新旧两种数据格式的 PDF 优先工作流
- 哈希计算和元数据持久化
- 清晰的回退策略
