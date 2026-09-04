# RWB-AUTO-002-01 实时数据摄取就绪情况审计

**审计日期**: 2026-05-11
**任务ID**: rwb-auto-002-01
**状态**: ✅ 完成

---

## 执行摘要

本次审计对三个数据来源（财联社、中国证券网、知丘）的实时数据摄取系统进行了全面检查。

**关键发现**:
1. ✅ 所有爬虫都已有完整的持久化去重系统
2. ✅ 所有爬虫都已实现停止条件和分页逻辑
3. ✅ 报告生成系统架构完整，支持模板和多格式输出
4. ⚠️ 当前缺少"增量抓取直到已知"的水位线追踪
5. ⚠️ 当前缺少统一的调度器

---

## 1. 财联社 (CLS) 审计

### 1.1 架构概览

**文件位置**: `data_layer/crawlers/cls/cls.py`

**核心类**:
- `CLSTelegramCrawler` - 主爬虫类
- `CLSConfig` - 配置类
- `DeduplicationStore` - 通用去重存储（`utils/deduplication.py`）

### 1.2 去重机制

| 特性 | 状态 | 说明 |
|------|------|------|
| 持久化去重 | ✅ 已实现 | 使用 JSON 状态文件 |
| 按 ID 去重 | ✅ 已实现 | 使用 `telegram.id` 作为键 |
| 跳过已处理 | ✅ 已实现 | `skip_existing` 配置 |
| 内容预览保存 | ✅ 已实现 | 保存标题和内容预览 |

**状态文件结构**:
```json
{
  "processed_items": {
    "电报ID": {
      "first_seen": "ISO时间戳",
      "title": "标题",
      "content_preview": "内容预览"
    }
  }
}
```

### 1.3 停止条件

| 条件 | 状态 | 说明 |
|------|------|------|
| 最大页数限制 | ✅ 已实现 | `max_pages` 配置（默认 150） |
| 连续空页检测 | ✅ 已实现 | `max_empty_pages` 配置（默认 7） |
| 日期范围限制 | ✅ 已实现 | `start_date` / `end_date` |
| "直到已知"检测 | ❌ 未实现 | 需要水位线追踪 |

**当前停止逻辑**（`_get_all_day_telegrams`）:
```python
if new_count == 0 or current_all_telegrams_count == last_all_telegrams_count:
    consecutive_empty_pages += 1
    if consecutive_empty_pages >= self.config.max_empty_pages:
        break
```

### 1.4 反爬策略

| 特性 | 状态 |
|------|------|
| 随机 User-Agent 轮换 | ✅ 已实现 |
| Cookie 预热 | ✅ 已实现 |
| 请求延迟 + 抖动 | ✅ 已实现 |
| 分页延迟 | ✅ 已实现 |
| 重试机制 | ✅ 已实现 |

**延迟配置**:
```python
delay: float = 1.5              # 基础延迟（秒）
delay_jitter: float = 0.8       # 抖动范围
page_delay: float = 1.0         # 分页延迟
page_delay_jitter: float = 0.5  # 分页抖动
```

---

## 2. 中国证券网 (CNStock) 审计

### 2.1 架构概览

**文件位置**: `data_layer/crawlers/cnstock/cnstock.py`

**核心类**:
- `CnstockCrawler` - 主爬虫类
- `CnstockConfig` - 配置类
- `CnstockStateManager` - 状态管理器

### 2.2 去重机制

| 特性 | 状态 | 说明 |
|------|------|------|
| 持久化去重 | ✅ 已实现 | 使用 JSON 状态文件 |
| 按文章 ID 去重 | ✅ 已实现 | 使用 `article_id` 或 `contId` |
| 跳过已处理 | ✅ 已实现 | `skip_existing` 配置 |

**状态文件结构**:
```json
{
  "processed_articles": {
    "文章ID": {
      "first_seen": "ISO时间戳",
      "title": "标题",
      "url": "链接"
    }
  }
}
```

### 2.3 停止条件

| 条件 | 状态 | 说明 |
|------|------|------|
| 最大页数限制 | ✅ 已实现 | `max_pages` 配置（默认 5） |
| 日期范围限制 | ✅ 已实现 | `start_date` / `end_date` |
| "直到已知"检测 | ❌ 未实现 | 需要水位线追踪 |

### 2.4 反爬策略

| 特性 | 状态 |
|------|------|
| WAF 检测与冷却 | ✅ 已实现 |
| 自适应延迟（基于失败率） | ✅ 已实现 |
| 定时长休息 | ✅ 已实现（每 5 页） |
| 超长长休息 | ✅ 已实现（每 15 页） |
| 顶出检测与账号切换 | ✅ 已实现（继承自 ZQ） |

**延迟层级**:
- 成功时: 3-7 秒随机
- 重试时: 8-15 秒随机
- 失败时: 20-40 秒随机

---

## 3. 知丘 (ZQ) 审计

### 3.1 架构概览

**文件位置**: `data_layer/crawlers/zq/`

**核心组件**:
```
zq/
├── report.py          # 研报爬虫（PDF优先）
├── news.py            # 新闻爬虫
├── meeting.py         # 会议爬虫
└── zhiqiu/
    ├── base_fetcher.py        # 基类（核心逻辑）
    ├── client.py              # API 客户端
    ├── account_manager.py     # 账号管理
    ├── progress_tracker.py    # 进度追踪
    ├── ejection_detector.py   # 顶出检测
    ├── anti_scrape.py         # 反爬策略
    └── processors/
        ├── report_processor.py  # 研报处理
        ├── news_processor.py    # 新闻处理
        └── meeting_processor.py # 会议处理
```

### 3.2 去重机制

| 特性 | 状态 | 说明 |
|------|------|------|
| 持久化去重 | ✅ 已实现 | 基类 `BaseStateManager` |
| 按 OBJID 去重 | ✅ 已实现 | 使用 `OBJID` 或 `id` |
| 跳过已处理 | ✅ 已实现 | `skip_existing` 配置 |
| PDF 元数据保存 | ✅ 已实现 | 保存 `pdfNAME` |

**状态文件结构**:
```json
{
  "processed_reports": {
    "OBJID": {
      "first_seen": "ISO时间戳",
      "title": "标题",
      "pdfNAME": "PDF文件名"
    }
  }
}
```

### 3.3 PDF 优先摄取

| 特性 | 状态 | 说明 |
|------|------|------|
| PDF 下载支持 | ✅ 已实现 | `enable_pdf` 配置 |
| PDF 元数据记录 | ✅ 已实现 | 保存 `pdfNAME` |
| PDF 转 Markdown | ⚠️ 部分实现 | 需要外部转换器支持 |
| 回退机制 | ✅ 已实现 | PDF 失败时使用文本 |

**报告处理器** (`zhiqiu/processors/report_processor.py`):
- AI 核心观点提取 (`enable_viewpoint`)
- AI 关注公司提取 (`enable_companies`)
- AI 摘要提取 (`enable_core`)

### 3.4 高级特性

| 特性 | 状态 |
|------|------|
| 多账号轮换 | ✅ 已实现 |
| 账号失败锁定 | ✅ 已实现（300 秒） |
| 进度持久化 | ✅ 已实现 |
| 顶出自动检测与恢复 | ✅ 已实现 |

---

## 4. 报告生成系统审计

### 4.1 架构概览

**文件位置**: `reporting/`

**核心组件**:
```
reporting/
├── composer/              # 报告合成引擎
│   ├── report_composer.py      # 主合成器
│   ├── report_pipeline.py      # 流水线
│   ├── section_generator.py    # 章节生成
│   ├── evidence_binder.py      # 证据绑定
│   ├── fact_card_builder.py    # 事实卡构建
│   └── validator.py            # 验证器
├── projections/          # 输出生成器
│   ├── markdown.py            # Markdown 输出
│   ├── word.py                # Word 输出（支持模板）
│   └── excel.py               # Excel 输出
└── templates/            # 模板管理
    └── template_manager.py    # 模板管理器
```

### 4.2 模板系统

**核心类**: `TemplateManager` (`templates/template_manager.py`)

| 特性 | 状态 | 说明 |
|------|------|------|
| YAML 模板加载 | ✅ 已实现 | 支持 `.yaml` 模板文件 |
| 模板缓存 | ✅ 已实现 | 避免重复加载 |
| 模板验证 | ✅ 已实现 | 检查必填字段 |
| 章节定义 | ✅ 已实现 | `SectionSpec` 支持 |
| 占位符定义 | ✅ 已实现 | 支持自定义占位符 |
| 提示模板 | ✅ 已实现 | `prompt_template` 字段 |

**内置模板示例**: `weekly_report`（周报）

### 4.3 输出生成器

#### Word 输出 (`projections/word.py`)

| 特性 | 状态 | 说明 |
|------|------|------|
| 基础 Word 生成 | ✅ 已实现 | 简单模式 |
| 模板占位符替换 | ✅ 已实现 | 支持 `{{placeholder}}`, `{placeholder}` |
| 表格插入 | ✅ 已实现 | `TableSpec` 支持 |
| 图表插入 | ✅ 已实现 | 支持图片字节插入 |
| 页眉页脚替换 | ✅ 已实现 | 完整支持 |

#### Markdown 输出 (`projections/markdown.py`)
- ✅ 已实现

#### Excel 输出 (`projections/excel.py`)
- ✅ 已实现

#### PowerPoint 输出
- ❌ 未实现（待开发）

---

## 5. 差距分析

### 5.1 当前状态 vs 需求

| 需求 | 当前状态 | 差距 |
|------|----------|------|
| 持久化去重 | ✅ 已实现 | 无 |
| 分页停止 | ✅ 已实现 | 无 |
| 反爬策略 | ✅ 已实现 | 无 |
| 报告模板 | ✅ 已实现 | 无 |
| Word 输出 | ✅ 已实现 | 无 |
| Excel 输出 | ✅ 已实现 | 无 |
| **"增量抓取直到已知"** | ⚠️ 部分实现 | 需要水位线追踪 |
| **PPTX 输出** | ❌ 未实现 | 需要开发 |
| **统一调度器** | ❌ 未实现 | 需要开发 |
| **摄取监控 API** | ❌ 未实现 | 需要开发 |

### 5.2 关键差距详述

#### 差距 1: "增量抓取直到已知" 水位线追踪

**问题**: 当前去重是"全量"的，需要遍历所有已处理 ID。

**期望**: 记录最后一次抓取的"水位线"，遇到已知 ID 立即停止。

**建议方案**:
```python
# 水位线状态示例
{
  "watermarks": {
    "cls": {
      "last_seen_id": "123456",
      "last_seen_time": "2026-05-11T10:30:00",
      "fetch_complete": false
    },
    "cnstock": { ... },
    "zq": { ... }
  }
}
```

#### 差距 2: 统一调度器

**问题**: 当前爬虫都是独立的 CLI 工具，没有统一调度。

**期望**:
- 交易时段感知（仅在 A 股交易时段运行）
- 中午休市暂停
- 手动启动/暂停控制
- 调度状态 API

#### 差距 3: PPTX 输出

**问题**: 当前只支持 Markdown/Word/Excel，缺少 PPTX。

**期望**: 与 Word 类似的模板系统，支持 PPTX 占位符替换。

---

## 6. 建议优先级

### P0 - 必须立即做
1. **rwb-auto-002-02** - 实现交易时段感知调度器
2. **rwb-auto-002-03** - 实现"增量抓取直到已知"逻辑

### P1 - 应该尽快做
3. **rwb-auto-002-12** - 实现 PPTX 模板上传和占位符渲染
4. **rwb-auto-002-07** - 审计并扩展摄取数据库架构

### P2 - 可以后续做
5. **rwb-auto-002-04** - 强化反爬策略（当前已经很好）
6. **rwb-auto-002-06** - PDF 转 Markdown 转换管道（已部分实现）

---

## 7. 结论

Research Workbench 的数据摄取和报告生成系统已经**非常成熟**，核心功能完整度约为 **85%**。

**主要优势**:
- ✅ 三个数据源都有企业级的爬虫实现
- ✅ 去重、状态管理、反爬策略都很完善
- ✅ 报告模板系统设计优良
- ✅ Word/Excel 输出已就绪

**主要待完善**:
- ⚠️ 需要统一调度器
- ⚠️ 需要"增量直到已知"的水位线优化
- ⚠️ 需要 PPTX 输出

---

**审计完成时间**: 2026-05-11
**下一步任务**: rwb-auto-002-02 (调度器实现) 或 rwb-auto-002-09 (报告能力审计)
