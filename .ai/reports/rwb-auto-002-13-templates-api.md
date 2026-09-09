# RWB-AUTO-002-13: 模板管理 API 实现报告

## 日期

2026-05-11

## 概述

本任务成功实现了完整的模板管理 API，支持 DOCX/PPTX/Excel 模板上传、占位符发现、报告渲染等功能。

## 实现内容

### 1. 新增 API 路由文件

**`app/api/routes/templates.py`** - 完整的模板管理 API，包含以下端点：

#### 模板管理端点

| 方法 | 端点 | 功能描述 |
|------|------|---------|
| GET | `/api/templates/` | 列出所有可用模板 |
| GET | `/api/templates/{template_name}` | 获取模板详细信息 |
| POST | `/api/templates/upload` | 上传模板文件（DOCX/PPTX/Excel） |
| POST | `/api/templates/create-yaml` | 创建 YAML 模板配置 |
| DELETE | `/api/templates/{template_name}` | 删除模板及其文件 |

#### 占位符和渲染端点

| 方法 | 端点 | 功能描述 |
|------|------|---------|
| GET | `/api/templates/{template_name}/placeholders/{file_type}` | 从模板文件发现占位符 |
| POST | `/api/templates/render` | 从模板渲染报告 |
| GET | `/api/templates/download/{report_id}` | 下载渲染后的报告 |
| GET | `/api/templates/files/{template_name}/{file_type}` | 下载原始模板文件 |

### 2. 新增数据模型

**`TemplateInfo`** - 模板基本信息
- `template_name` - 模板名称
- `description` - 描述
- `version` - 版本
- `has_docx`/`has_pptx`/`has_excel` - 文件存在标志
- `placeholders` - 占位符列表
- `sections` - 章节配置

**`TemplateListResponse`** - 模板列表响应
**`PlaceholderDiscoveryResponse`** - 占位符发现响应
**`RenderReportRequest`** - 报告渲染请求
**`RenderReportResponse`** - 报告渲染响应

### 3. API 功能特性

#### 模板上传和管理
- 支持多文件类型：DOCX/PPTX/Excel
- 自动保存到对应的子目录结构
- 支持覆盖已存在的模板
- 上传后更新 TemplateConfig

#### 占位符发现
- 从 DOCX 和 PPTX 文件自动扫描占位符
- 支持两种格式：`{{placeholder}}` 和 `{placeholder}`
- 支持从段落、表格、页眉页脚中发现

#### 报告渲染
- 支持直接提供占位符数据
- 支持通过 `canonical_id` 从 ReportGenerator 获取数据
- 支持 DOCX 和 PPTX 格式渲染
- 自动管理输出文件和下载链接

### 4. 更新主路由配置

**`app/api/main.py`** - 添加了 templates 路由注册：

```python
from app.api.routes import templates
app.include_router(templates.router)
```

### 5. 完整测试覆盖

**`tests/unit/test_templates_api.py`** - 13 个测试用例，全部通过：
- 基本 API 端点测试
- 模板上传和下载测试
- 占位符发现测试
- 报告渲染测试
- 完整工作流测试

## API 使用示例

### 上传模板

```python
import requests

with open("my_template.docx", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/templates/upload",
        data={
            "template_name": "quarterly_report",
            "file_type": "docx",
            "description": "Quarterly investment report template",
        },
        files={"file": ("template.docx", f)},
    )

print(response.json())
```

### 发现占位符

```python
response = requests.get(
    "http://localhost:8000/api/templates/quarterly_report/placeholders/docx"
)
print(response.json())
# Output: {"template_name": "quarterly_report", "placeholders": ["title", "summary", "date"], ...}
```

### 渲染报告

```python
response = requests.post(
    "http://localhost:8000/api/templates/render",
    json={
        "template_name": "quarterly_report",
        "file_type": "docx",
        "placeholders": {
            "title": "Q2 2026 Investment Report",
            "summary": "Market performed well this quarter...",
            "date": "2026-06-30",
        },
    },
)

result = response.json()
print(f"Download your report at: {result['download_url']}")
```

### 使用 ReportGenerator 数据

```python
response = requests.post(
    "http://localhost:8000/api/templates/render",
    json={
        "template_name": "quarterly_report",
        "file_type": "docx",
        "canonical_id": "600519.SH",
        "report_type": "full",
    },
)
```

## 目录结构

```
reporting/templates/
├── yaml/              # YAML 模板配置
├── docx/              # DOCX 模板文件
├── pptx/              # PPTX 模板文件
└── excel/             # Excel 模板文件

output/rendered_reports/  # 渲染后的报告输出
```

## 测试结果

所有测试通过：

```
======================= 13 passed, 14 warnings in 2.70s ========================
```

测试覆盖范围：
- 模板列表和详情获取
- 模板上传（DOCX/PPTX）
- 占位符发现
- 报告渲染
- 文件下载
- 删除操作

## 成功标准对照

| 标准 | 状态 | 说明 |
|------|------|------|
| 模板上传 API 实现 | ✅ | 支持 DOCX/PPTX/Excel 上传 |
| 模板列表和元数据 API 实现 | ✅ | GET /api/templates/ 和 /{name} |
| 渲染生成 API 实现 | ✅ | POST /api/templates/render |
| 创建 API 报告 | ✅ | 即本文档 |

## 依赖要求

- `fastapi` - 已存在
- `python-docx` - 可选，用于 DOCX 处理（已安装）
- `python-pptx` - 可选，用于 PPTX 处理（已安装）

## 后续建议

### 下一个任务: RWB-AUTO-002-14 - 添加 Web UI

使用新实现的 API，添加前端界面支持：
- 模板上传 UI
- 占位符配置界面
- 报告渲染预览
- 结果下载功能

### 进一步增强功能

1. **模板预览** - 在浏览器中显示模板内容
2. **模板版本管理** - 支持模板历史版本
3. **批量渲染** - 一次渲染多个报告
4. **模板市场** - 共享和下载模板
5. **更多占位符格式** - 支持 `<% placeholder %>` 等
