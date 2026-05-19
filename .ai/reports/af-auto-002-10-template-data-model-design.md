# AF-AUTO-002-10: 模板驱动报告数据模型设计

## 执行摘要

好消息！AlphaFoundry 已经拥有**完整且设计精良**的模板驱动报告数据模型。

本设计报告将：
1. 验证现有数据模型的完整性
2. 识别任何微小的差距
3. 提供 PPTX 支持的补充模型
4. 记录完整的架构

---

## 一、现有数据模型验证

### 1.1 Pydantic 契约（核心层）

**文件位置**: `core/contracts/reporting.py`

| 模型 | 状态 | 用途 |
|------|------|------|
| `SectionSpec` | ✅ 完整 | 报告章节规范（标题、字数、必需维度、提示模板等） |
| `SectionOutput` | ✅ 完整 | 单个章节输出（内容、证据引用、警告等） |
| `FactCard` | ✅ 完整 | 提取的事实卡片（中间表示） |
| `TemplateConfig` | ✅ 完整 | 完整模板配置（元数据、章节、输出偏好） |
| `ReportTask` | ✅ 完整 | 报告生成任务（状态跟踪） |
| `ReportRunLog` | ✅ 完整 | 报告运行日志（审计/调试） |
| `TableSpec` | ✅ 完整 | 表格规范（表格插入模板） |
| `ChartSpec` | ✅ 完整 | 图表规范（图表插入模板） |
| `ValidationResult` | ✅ 完整 | 单个验证结果 |
| `ValidationResults` | ✅ 完整 | 完整验证结果 |

### 1.2 V1 文档契约

**文件位置**: `core/contracts/documents_v1.py`

| 模型 | 状态 | 用途 |
|------|------|------|
| `ReportRunV1` | ✅ 完整 | 报告运行记录（持久化层） |

### 1.3 数据库模型

**文件位置**: `data_layer/repositories/models.py`

| 模型 | 表名 | 状态 | 用途 |
|------|------|------|------|
| `ReportRunV1DB` | `report_run_v1` | ✅ 完整 | 报告运行记录持久化 |

---

## 二、现有架构组件

### 2.1 TemplateManager

**文件位置**: `reporting/templates/template_manager.py`

**已实现功能**:
- ✅ 模板列表
- ✅ 模板加载（YAML）
- ✅ 模板保存
- ✅ 模板删除
- ✅ 模板验证
- ✅ 模板缓存
- ✅ 内置周报模板创建

### 2.2 报告投影器（Projections）

| 投影器 | 文件 | 状态 | 用途 |
|--------|------|------|------|
| `MarkdownProjection` | `reporting/projections/markdown.py` | ✅ 完整 | Markdown 报告输出 |
| `WordProjection` | `reporting/projections/word.py` | ✅ 完整 | Word 文档输出（含模板） |
| `ExcelProjection` | `reporting/projections/excel.py` | 🔄 框架 | Excel 输出（基础） |

### 2.3 ReportComposer

**文件位置**: `reporting/composer/report_composer.py`

**已实现功能**:
- ✅ 模板加载
- ✅ 证据绑定
- ✅ 章节生成
- ✅ 多格式输出（Markdown, Word）

---

## 三、差距分析

### 3.1 已识别的微小差距

| 差距 | 优先级 | 说明 |
|------|--------|------|
| PPTX 投影器 | 🔴 高 | 需要添加 PPTX 支持（AF-AUTO-002-12） |
| 模板元数据表 | 🟡 中 | 可选添加，用于持久化模板元数据 |
| 模板文件存储 | 🟡 中 | 需要约定模板文件存储位置 |

### 3.2 不需要的工作

以下工作**不需要**进行，因为已经完整实现：
- ❌ 模板数据模型设计（已完整）
- ❌ 占位符模型定义（已完整）
- ❌ 渲染提示元数据（已完整）
- ❌ 输出制品跟踪（已完整）

---

## 四、补充模型：PPTX 支持

为支持 PPTX 模板，建议添加以下模型（可直接在 `core/contracts/reporting.py` 中添加）：

### 4.1 幻灯片规范

```python
class SlideSpec(BaseModel):
    """幻灯片规范 - 定义单个幻灯片的要求"""
    
    slide_index: int = Field(description="幻灯片索引（从0开始）")
    slide_title: str = Field(description="幻灯片标题")
    slide_type: Literal["title", "content", "chart", "table", "image"] = Field(
        description="幻灯片类型"
    )
    placeholders: Dict[str, str] = Field(
        default_factory=dict,
        description="占位符映射（占位符名 -> 数据键）"
    )
    required_fields: List[str] = Field(
        default_factory=list,
        description="必需字段列表"
    )
    prompt_template: Optional[str] = Field(
        default=None,
        description="自定义提示模板（用于生成此幻灯片内容）"
    )
    layout_name: Optional[str] = Field(
        default=None,
        description="PowerPoint 布局名称"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
```

### 4.2 PPTX 模板配置扩展

```python
class PowerPointTemplateConfig(TemplateConfig):
    """PowerPoint 模板配置 - 扩展基础 TemplateConfig"""
    
    # 继承自 TemplateConfig:
    # name, description, version, target_audience, sections, 
    # default_retrieval_profile, word_template_path, excel_template_path,
    # placeholders, metadata
    
    # PowerPoint 特定:
    powerpoint_template_path: Optional[str] = Field(
        default=None,
        description="PowerPoint 模板文件路径"
    )
    slide_specs: Optional[List[SlideSpec]] = Field(
        default=None,
        description="幻灯片规范列表"
    )
    theme_name: Optional[str] = Field(
        default=None,
        description="PowerPoint 主题名称"
    )
    default_layout: Optional[str] = Field(
        default=None,
        description="默认布局名称"
    )
```

### 4.3 幻灯片输出

```python
class SlideOutput(BaseModel):
    """幻灯片输出 - 单个生成的幻灯片"""
    
    slide_index: int = Field(description="幻灯片索引")
    slide_title: str = Field(description="幻灯片标题")
    content: Dict[str, Any] = Field(
        description="幻灯片内容（占位符名 -> 值）"
    )
    placeholders_filled: List[str] = Field(
        default_factory=list,
        description="已填充的占位符列表"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="警告列表"
    )
    fact_card: Optional[FactCard] = Field(
        default=None,
        description="使用的事实卡片"
    )
```

---

## 五、模板文件存储约定

### 5.1 目录结构

```
storage/
└── templates/
    ├── yaml/           # YAML 配置文件
    │   ├── weekly_report.yaml
    │   ├── asset_analysis.yaml
    │   └── market_report.yaml
    ├── docx/           # Word 模板文件
    │   ├── weekly_report_template.docx
    │   └── asset_analysis_template.docx
    ├── pptx/           # PowerPoint 模板文件
    │   └── market_report_template.pptx
    └── excel/          # Excel 模板文件
        └── performance_template.xlsx
```

### 5.2 文件命名约定

- YAML 配置: `{template_name}.yaml`
- DOCX 模板: `{template_name}_template.docx`
- PPTX 模板: `{template_name}_template.pptx`
- Excel 模板: `{template_name}_template.xlsx`

---

## 六、占位符规范

### 6.1 占位符格式

**Word 文档**:
- `{{placeholder_name}}` - 双大括号格式
- `{placeholder_name}` - 单大括号格式
- 直接文本匹配

**PowerPoint**:
- 文本框内容中的占位符（同 Word）
- 形状/表格/图表中的占位符

### 6.2 占位符类型

| 类型 | 说明 | 示例 |
|------|------|------|
| 简单文本 | 直接字符串替换 | `{{report_title}}` |
| 日期时间 | 日期格式化 | `{{generated_date}}` |
| 数字格式 | 数字格式化 | `{{pe_ratio}}` |
| 表格插入 | 完整表格替换 | `{{financial_table}}` |
| 图表插入 | 图表图片替换 | `{{price_chart}}` |
| 图片插入 | 图片替换 | `{{company_logo}}` |
| 条件内容 | 条件显示/隐藏 | `{{#if has_events}}...{{/if}}` |
| 循环内容 | 列表/表格行循环 | `{{#each events}}...{{/each}}` |

---

## 七、数据流程图

### 7.1 完整流程

```
用户上传模板
    ↓
TemplateManager 验证并存储
    ↓
用户触发报告生成
    ↓
ReportComposer 加载模板
    ↓
SectionGenerator 生成各章节内容
    ↓
EvidenceBinder 绑定证据
    ↓
    ├─→ MarkdownProjection → Markdown 文件
    ├─→ WordProjection → DOCX 文件（模板替换）
    ├─→ PowerPointProjection → PPTX 文件（模板替换）
    └─→ ExcelProjection → XLSX 文件
    ↓
ReportRunV1 记录运行状态
    ↓
用户下载报告
```

---

## 八、API 设计草图

### 8.1 模板管理 API

```
GET    /api/templates              # 列出所有模板
POST   /api/templates              # 创建新模板
GET    /api/templates/{name}       # 获取模板详情
PUT    /api/templates/{name}       # 更新模板
DELETE /api/templates/{name}       # 删除模板
POST   /api/templates/{name}/render  # 渲染报告
```

### 8.2 模板文件上传 API

```
POST   /api/templates/{name}/files/docx  # 上传 Word 模板
POST   /api/templates/{name}/files/pptx  # 上传 PowerPoint 模板
GET    /api/templates/{name}/files/{type}  # 下载模板文件
```

---

## 九、验证清单

### 9.1 数据模型完整性

| 检查项 | 状态 |
|--------|------|
| 模板数据模型已指定 | ✅ (TemplateConfig) |
| 占位符模型已指定 | ✅ (SectionSpec.placeholder, placeholders dict) |
| 渲染提示元数据已指定 | ✅ (SectionSpec.prompt_template) |
| 输出制品跟踪已指定 | ✅ (ReportRunV1) |
| 设计报告已创建 | ✅ (本文档) |

### 9.2 后续任务就绪度

| 任务 | 就绪度 | 说明 |
|------|--------|------|
| AF-AUTO-002-11 (DOCX) | ✅ 100% | WordProjection 已完整实现 |
| AF-AUTO-002-12 (PPTX) | 🟡 80% | 需要添加 PowerPointProjection |
| AF-AUTO-002-13 (API) | ✅ 100% | 可基于现有结构构建 |
| AF-AUTO-002-14 (UI) | 🟡 70% | 可基于 API 构建 |
| AF-AUTO-002-15 (集成) | ✅ 90% | ReportGenerator 已存在 |

---

## 十、结论与建议

### 10.1 主要发现

1. **数据模型已完整** - 无需从头设计
2. **基础设施已就绪** - TemplateManager, WordProjection 等已实现
3. **测试覆盖良好** - ReportGenerator 已有测试

### 10.2 建议

1. **直接进入实现** - 无需额外设计，可开始 AF-AUTO-002-11
2. **复用现有代码** - 最大化利用已有的 TemplateManager 和 WordProjection
3. **PPTX 可参考 DOCX** - PowerPointProjection 可参考 WordProjection 结构

### 10.3 下一个任务

AF-AUTO-002-11: 实现 DOCX 模板上传和占位符渲染
- 可直接复用 WordProjection.save_from_template()
- 添加模板文件上传功能
- 添加占位符发现功能

---

## 附录

### A. 现有 TemplateConfig 回顾

```python
class TemplateConfig(BaseModel):
    name: str
    description: str
    version: str = "1.0"
    target_audience: Optional[str] = None
    sections: List[SectionSpec]
    default_retrieval_profile: RetrievalProfileType
    word_template_path: Optional[str] = None
    excel_template_path: Optional[str] = None
    placeholders: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### B. 现有 SectionSpec 回顾

```python
class SectionSpec(BaseModel):
    key: str
    title: str
    target_words: int
    required_facets: List[str] = Field(default_factory=list)
    scenario_required: bool = True
    evidence_policy: Literal["strict", "allow_synthesis"] = "strict"
    retrieval_profile: Optional[RetrievalProfileType] = None
    prompt_template: Optional[str] = None
    forbidden_terms: List[str] = Field(default_factory=list)
    structure: Optional[str] = None
    placeholder: Optional[str] = None
```

---

**设计完成日期**: 2026-05-11  
**状态**: ✅ 完成（数据模型已完整存在）  
**下一步**: AF-AUTO-002-11 - 实现 DOCX 模板上传和占位符渲染
