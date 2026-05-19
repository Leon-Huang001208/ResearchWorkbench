# AF-AUTO-002-09: 当前报告生成能力审计报告

## 执行摘要

本次审计发现 AlphaFoundry 已具备较为完整的报告生成基础设施，包括：

- ✅ 完整的 Pydantic 契约定义（SectionSpec, TemplateConfig 等）
- ✅ 模板管理器（TemplateManager）支持 YAML 模板加载和存储
- ✅ WordProjection 支持从 DOCX 模板渲染报告，含占位符替换
- ✅ MarkdownProjection 支持 Markdown 格式输出
- ✅ ExcelProjection 框架已准备
- ✅ ReportComposer 提供一键报告生成接口
- ✅ 现有 API 端点支持报告生成和下载
- ✅ 测试覆盖率良好

本报告将详细分析现有能力、限制点和可复用模块。

---

## 一、当前报告 API 行为分析

### 1.1 API 端点概览

**文件位置**: `app/api/routes/report.py`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/report/generate` | POST | 生成资产研究报告 |
| `/api/report/download/{report_id}` | GET | 下载研报 PDF |
| `/api/report/performance` | GET | 获取绩效报告数据（JSON） |
| `/api/report/performance/download` | GET | 下载绩效报告（JSON 文件） |

### 1.2 请求/响应模型

**ReportGenerateRequest**:
```python
canonical_id: str          # 资产 ID
report_type: str = "full" # full/summary/valuation
as_of: datetime = None    # 分析时间点
```

**ReportGenerateResponse**:
```python
report_id: str
canonical_id: str
report_type: str
generated_at: datetime
download_url: str
content: str               # Markdown 格式内容
```

### 1.3 现有限制

1. **输出格式**: 当前 API 声称返回 PDF，但实际只返回 Markdown
2. **模板支持**: 当前未使用模板系统，使用硬编码字符串生成
3. **存储**: report_store 是内存字典，非持久化
4. **绩效报告**: 直接查询数据库并返回 JSON，未使用报告生成系统

---

## 二、当前 ReportGenerator 能力与限制

### 2.1 核心实现

**文件位置**: `core/services/report_generator.py`

**类结构**:
```python
class ReportGenerator:
    async def generate(canonical_id, report_type, as_of) -> Dict
    async def get_report_content(report_id) -> str
    _generate_summary_report(snapshot) -> str
    _generate_valuation_report(snapshot) -> str
    _generate_full_report(snapshot) -> str
```

### 2.2 支持的报告类型

| 类型 | 说明 |
|------|------|
| `summary` | 投资摘要报告 - 核心指标、事件、建议 |
| `valuation` | 估值分析报告 - 估值指标、价格区间、结论 |
| `full` | 完整投资研究报告 - 包含全部 6 个章节 |

### 2.3 当前限制

| 限制项 | 说明 |
|--------|------|
| **硬编码模板** | 所有报告内容通过字符串拼接生成，无模板系统 |
| **单一数据源** | 仅依赖 AssetAnalysisService 的 snapshot |
| **无配置化** | 章节内容、格式无法通过配置调整 |
| **内存存储** | 生成的报告仅存储在内存，重启丢失 |
| **无版本控制** | 无报告版本、历史记录功能 |
| **无并发控制** | 无任务队列、异步生成能力 |

---

## 三、报告契约与数据模型分析

### 3.1 核心契约定义

**文件位置**: `core/contracts/reporting.py`

| 模型类 | 用途 | 状态 |
|--------|------|------|
| `SectionSpec` | 定义报告章节规范（标题、字数、必需维度等） | ✅ 完整 |
| `SectionOutput` | 单个章节的输出结果（内容、证据、警告等） | ✅ 完整 |
| `FactCard` | 提取的事实卡片（中间层，可验证） | ✅ 完整 |
| `TemplateConfig` | 完整模板配置（元数据、章节列表、输出偏好） | ✅ 完整 |
| `ReportTask` | 报告生成任务（状态跟踪） | ✅ 完整 |
| `ReportRunLog` | 报告生成运行日志（审计/调试） | ✅ 完整 |
| `TableSpec` | 表格规范 | ✅ 完整 |
| `ChartSpec` | 图表规范 | ✅ 完整 |

### 3.2 SectionSpec 关键字段

```python
key: str                    # 章节唯一标识
title: str                  # 章节标题
target_words: int          # 目标字数
required_facets: List[str] # 必需维度
scenario_required: bool    # 是否需要情景分析
evidence_policy: Literal["strict", "allow_synthesis"]
prompt_template: str       # 自定义提示模板
placeholder: str           # Word 模板占位符名称
```

### 3.3 TemplateConfig 关键字段

```python
name: str
description: str
version: str
sections: List[SectionSpec]
word_template_path: Optional[str]    # DOCX 模板路径
excel_template_path: Optional[str]   # Excel 模板路径
placeholders: Dict[str, str]         # 章节 key -> 占位符映射
```

---

## 四、模板工作流复用点分析

### 4.1 TemplateManager 完整功能

**文件位置**: `reporting/templates/template_manager.py`

| 功能 | 方法 | 状态 |
|------|------|------|
| 列出模板 | `list_templates()` | ✅ 可用 |
| 加载模板 | `load_template(template_name)` | ✅ 可用 |
| 保存模板 | `save_template(config, overwrite)` | ✅ 可用 |
| 删除模板 | `delete_template(template_name)` | ✅ 可用 |
| 验证模板 | `_validate_template(config)` | ✅ 可用 |
| 缓存管理 | `clear_cache()` | ✅ 可用 |

**内置模板**:
- `weekly_report` - 每周市场分析报告模板（包含 5 个章节）

### 4.2 WordProjection 模板渲染能力

**文件位置**: `reporting/projections/word.py`

**核心方法**:
```python
save_from_template(
    output_path,
    template_path,
    sections: List[SectionOutput],
    placeholders: Optional[Dict[str, str]] = None,
    tables: Optional[List[TableSpec]] = None,
    chart_images: Optional[Dict[str, bytes]] = None,
)
```

**占位符格式支持**:
- `{{placeholder}}`
- `{placeholder}`
- `placeholder`

**替换位置**:
- 段落
- 表格单元格
- 页眉/页脚

**高级功能**:
- 表格插入到指定占位符
- 图表图片插入到指定占位符
- 保留原始格式（粗体、斜体、下划线、颜色、字体大小）

### 4.3 MarkdownProjection

**文件位置**: `reporting/projections/markdown.py`

功能完整，支持:
- 标题层级
- 元数据 YAML 头
- 证据引用列表
- 警告提示

### 4.4 ExcelProjection

**文件位置**: `reporting/projections/excel.py`

框架已准备，可扩展。

---

## 五、文件清单与用途说明

### 5.1 核心模块

| 文件路径 | 用途 | 复用优先级 |
|----------|------|-----------|
| `core/contracts/reporting.py` | 报告数据契约 | 🔴 高 - 必需 |
| `core/services/report_generator.py` | 现有资产研报生成器 | 🟡 中 - 参考 |
| `reporting/templates/template_manager.py` | 模板管理器 | 🔴 高 - 必需 |
| `reporting/projections/word.py` | Word 文档生成/模板渲染 | 🔴 高 - 必需 |
| `reporting/projections/markdown.py` | Markdown 文档生成 | 🟡 中 - 可选 |
| `reporting/projections/excel.py` | Excel 文档生成 | 🟢 低 - 可选 |
| `reporting/composer/report_composer.py` | 报告合成器（整合模板+生成） | 🔴 高 - 必需 |
| `reporting/composer/section_generator.py` | 章节生成器 | 🟡 中 - 参考 |
| `reporting/composer/evidence_binder.py` | 证据绑定器 | 🟡 中 - 参考 |
| `reporting/composer/fact_card_builder.py` | 事实卡片构建器 | 🟡 中 - 参考 |
| `reporting/composer/report_pipeline.py` | 报告流水线 | 🟡 中 - 参考 |
| `reporting/composer/validator.py` | 验证器 | 🟢 低 - 可选 |

### 5.2 API 与 CLI

| 文件路径 | 用途 |
|----------|------|
| `app/api/routes/report.py` | 报告 API 端点 |
| `app/cli/commands/report.py` | 报告 CLI 命令 |

### 5.3 测试文件

| 文件路径 | 用途 | 状态 |
|----------|------|------|
| `tests/unit/test_report_generator.py` | ReportGenerator 单元测试 | ✅ 完整 (5 个测试) |

---

## 六、现有测试覆盖分析

### 6.1 test_report_generator.py

**测试用例**:

| 测试名 | 覆盖内容 |
|--------|---------|
| `test_generate_summary_report` | 生成摘要报告 |
| `test_generate_valuation_report` | 生成估值报告 |
| `test_generate_full_report` | 生成完整报告 |
| `test_get_report_content` | 获取报告内容 |
| `test_get_report_content_not_found` | 获取不存在报告的错误处理 |

**覆盖质量**: 🟢 良好 - 覆盖主要流程和错误路径

---

## 七、架构扩展建议

### 7.1 为 AF-AUTO-002-10~15 的扩展点

基于现有架构，建议按以下方式扩展：

```
AF-AUTO-002-10: 设计模板驱动报告数据模型
    ↓ 复用现有契约，仅需补充 PPTX 相关
AF-AUTO-002-11: 实现 DOCX 模板上传与渲染
    ↓ 直接复用 WordProjection.save_from_template()
AF-AUTO-002-12: 实现 PPTX 模板上传与渲染
    ↓ 新增 PPTXProjection（类似 WordProjection）
AF-AUTO-002-13: 添加模板管理 API
    ↓ 复用 TemplateManager + 新增 API 端点
AF-AUTO-002-14: 添加 Web UI
    ↓ 基于 API 构建
AF-AUTO-002-15: 集成现有 ReportGenerator
    ↓ 桥接旧有快照数据到新模板系统
```

### 7.2 PPTXProjection 设计建议

参考 WordProjection 结构，使用 `python-pptx` 库：

```python
class PPTXProjection:
    def save_from_template(
        self,
        output_path,
        template_path,
        sections: List[SectionOutput],
        placeholders: Optional[Dict[str, str]] = None,
        images: Optional[Dict[str, bytes]] = None,
    ):
        # 实现占位符替换
        # 支持文本框、表格、图表占位符
```

---

## 八、增量开发建议

### 8.1 第一阶段：增强模板管理 API（AF-AUTO-002-13 可先做）

**复用模块**:
- TemplateManager (100% 复用)
- 现有 API 框架

**新增端点**:
```
GET    /api/templates              # 列出所有模板
POST   /api/templates              # 上传/创建模板
GET    /api/templates/{name}       # 获取模板详情
PUT    /api/templates/{name}       # 更新模板
DELETE /api/templates/{name}       # 删除模板
POST   /api/templates/{name}/render # 从模板渲染报告
```

### 8.2 第二阶段：DOCX 模板上传（AF-AUTO-002-11）

**复用模块**:
- WordProjection (100% 复用)
- TemplateManager (100% 复用)

**新增功能**:
- DOCX 模板文件上传存储
- 模板占位符扫描/发现
- 占位符预览 API

### 8.3 第三阶段：PPTX 支持（AF-AUTO-002-12）

**新增模块**:
- PPTXProjection（参考 WordProjection）

### 8.4 第四阶段：集成现有 ReportGenerator（AF-AUTO-002-15）

**桥接层设计**:
```python
# 将旧有 AssetSnapshot 转换为模板占位符数据
def snapshot_to_placeholders(snapshot) -> Dict[str, str]:
    return {
        "asset_id": snapshot.canonical_id,
        "pe_ttm": str(snapshot.valuation.get("pe_ttm", "N/A")),
        # ... 更多映射
    }
```

---

## 九、成功标准检查

| 标准 | 状态 |
|------|------|
| 当前报告 API 行为已记录 | ✅ 完成 |
| 当前 ReportGenerator 能力与限制已记录 | ✅ 完成 |
| 模板工作流复用点已识别 | ✅ 完成 |
| 报告能力审计已创建 | ✅ 完成 |

---

## 十、总结

### 10.1 现有优势

1. **完整契约**: SectionSpec, TemplateConfig 等模型设计完善
2. **模板管理**: TemplateManager 功能完整，支持 YAML 配置
3. **Word 渲染**: WordProjection 已支持模板占位符替换
4. **多格式**: Markdown, Word, Excel 框架均已准备
5. **测试良好**: 核心功能有测试覆盖

### 10.2 主要差距

1. **API 未集成**: 现有 /api/report 未使用模板系统
2. **无 PPTX 支持**: 缺少 PowerPoint 模板渲染
3. **无模板上传 UI**: 用户无法上传自定义 DOCX/PPTX 模板
4. **存储未持久化**: 模板、报告都在内存

### 10.3 复用建议

| 模块 | 复用方式 |
|------|---------|
| TemplateManager | 100% 直接复用 |
| WordProjection | 100% 直接复用 |
| MarkdownProjection | 100% 直接复用 |
| ReportComposer | 参考设计，或直接复用 |
| SectionGenerator | 参考设计 |
| reporting/* 契约 | 100% 直接复用 |

---

**审计完成时间**: 2026-05-11
**审计人**: Claude Code
