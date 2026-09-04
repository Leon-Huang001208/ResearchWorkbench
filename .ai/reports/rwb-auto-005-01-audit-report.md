# RWB-AUTO-005 审计报告：现有爬虫和数据源覆盖情况

**审计日期**: 2026-05-13
**任务ID**: rwb-auto-005-01
**状态**: ✅ 完成

---

## 1. 执行摘要

本次审计对 Research Workbench 现有的数据爬虫和 Web UI 各板块的数据来源进行了全面梳理，识别出仍在使用模拟数据的模块，并按优先级列出了需要接入真实数据的功能。

**主要发现**:
- 数据库中确实有真实数据：20 条事件、15 条信号、15 条回测结果
- **关键 Bug**: DashboardService 中板块数据回退逻辑有问题，即使有真实的上涨板块数据，但只要没有下跌板块就会回退到模拟数据
- 市场概览的真实数据获取代码路径是正常的，只是被这个 Bug 拦截了
- 资产分析默认仍使用 Mock 数据
- 产业链图谱和事件传播路径有获取真实数据的代码，但前端有硬编码的模拟数据回退

---

## 2. 现有爬虫覆盖范围

| 爬虫名称 | 目录位置 | 数据类型 | 状态 |
|---------|---------|------|------|
| AKShare | `data_layer/crawlers/akshare/` | 股票行情、财务数据、资金流向 | ✅ 可用 |
| 财联社 (CLS) | `data_layer/crawlers/cls/` | 实时新闻、电报 | ✅ 可用 |
| 中国证券网 (CNStock) | `data_layer/crawlers/cnstock/` | 行业新闻、公告 | ✅ 可用 |
| 知丘 (ZQ) | `data_layer/crawlers/zq/` | 研报解析 | ✅ 可用 |

---

## 3. 数据库实际数据情况

检查结果（2026-05-13）:

| 表名 | 数量 | 说明 |
|-----|------|------|
| DocumentV1（文档） | 0 条 | 文档表是空的 |
| CanonicalEvent（事件） | 20 条 | ✅ 有真实事件数据 |
| AlphaSignal（信号） | 15 条 | ✅ 有真实信号数据 |
| Entity（实体） | 0 条 | 实体表是空的 |
| EntityMention（实体提及） | 0 条 | 实体提及表是空的 |
| SignalOutcome（回测结果） | 15 条 | ✅ 有真实回测数据 |

✅ **关键发现**: DashboardDataRepository 可以正常从事件中获取新闻数据，从信号中获取板块数据。

---

## 4. Web UI 各模块数据来源状态表

### Dashboard 板块
| 模块名称 | 数据来源 | 状态 | 说明 |
|---------|---------|------|------|
| 市场概览（新闻） | DocumentV1/CanonicalEvent | 🐛 有 Bug | 代码路径正常，但被 Bug 拦截 |
| 市场概览（板块） | AlphaSignal industry_impacts | 🐛 有 Bug | 只要有一个方向没有数据就回退到模拟 |
| Today - 新事件 | CanonicalEvent | ✅ 正常 | 代码路径存在，依赖数据库中有数据 |
| Today - 高优先级论题 | AlphaSignalDB | ✅ 正常 | 代码路径存在，依赖数据库中有数据 |
| Today - 异常流向 | IndustryChainRepository | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Research Queue - 待处理断言 | ReviewRepository | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Research Queue - 缺失证据 | ReviewRepository | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Research Queue - 待映射审查 | ReviewRepository | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Candidate Board - Top 候选 | AlphaSignalDB + ReadinessScorer | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Learning - 最近失败 | SignalOutcomeDB | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Learning - 最佳表现事件类型 | SignalOutcomeDB 聚合 | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |
| Learning - 每周经验 | WeeklyLessonRepository | ⚠️ 部分真实 | 代码路径存在，依赖数据库中有数据 |

### 其他板块
| 模块名称 | 数据来源 | 状态 | 说明 |
|---------|---------|------|------|
| 资产分析 | Mock / AKShare / iFinD | ⚠️ 默认 Mock | UI 默认选择 "Mock 数据" |
| 产业链图谱 | GraphDataService + 前端模拟回退 | ⚠️ 部分真实 | API 有真实数据路径，但前端有硬编码模拟回退 |
| 事件传播路径 | GraphDataService + 前端模拟回退 | ⚠️ 部分真实 | API 有真实数据路径，但前端有硬编码模拟回退 |
| 信号管理 | AlphaSignalDB | ✅ 真实数据 | 从数据库读取 |
| 回测结果 | SignalOutcomeDB | ✅ 真实数据 | 从数据库读取 |
| 审核队列 | ReviewRepository | ✅ 真实数据 | 从数据库读取 |
| 记忆学习 | FailureMemory + WeeklyLesson | ✅ 真实数据 | 从数据库读取 |
| 文档摄入 | DocumentV1 + 各爬虫 | ✅ 真实数据 | 已实现 |
| Signal Lab | 特征/标签/回测引擎 | ✅ 真实数据 | 已实现 |

---

## 5. 关键 Bug 分析

### Bug 1: 板块数据回退逻辑过于严格

**位置**: `core/services/dashboard_service.py` 第 293 行

**问题代码**:
```python
# 如果没有真实板块数据，回退到模拟
if not top_up_sectors or not top_down_sectors:  # ❌ 这里有问题
    mock_up, mock_down = self._get_mock_sectors()
    if not top_up_sectors:
        top_up_sectors = mock_up
    if not top_down_sectors:
        top_down_sectors = mock_down
    has_real_sectors = False
```

**问题说明**:
- 当前代码要求**同时**有上涨板块和下跌板块才使用真实数据
- 但实际情况可能是只有上涨或只有下跌
- 在我们的测试数据中，只有上涨板块数据，没有下跌板块，导致整体回退到模拟数据

**修复方案**:
- 只要有其中一个方向的数据就应该使用真实数据
- 另一个方向可以是空列表，而不是回退到模拟

---

## 6. 仍在使用模拟数据的模块清单

### P0 - 立即修复
1. **市场概览板块数据回退逻辑** (`core/services/dashboard_service.py`)
   - 问题: 只要有一个方向没有板块数据就回退到模拟
   - 影响: 即使有真实数据也显示不出来

### P0 - 快速修复
2. **资产分析默认数据源** (`app/web/templates/index.html` 第 232 行)
   - 问题: `<option value="mock" selected>` 默认选中 Mock
   - 影响: 新用户默认看不到真实数据

### P1 - 高优先级
3. **产业链图谱前端模拟数据** (`app/web/static/app.js` 第 1421-1435 行)
   - 问题: `renderIndustryGraph` 函数中有硬编码的 mockNodes 和 mockLinks
   - 影响: 即使 API 返回空，前端会显示模拟数据，而不是显示空状态提示

---

## 7. 数据源接入优先级排序

### P0 - 立即修复
1. ✅ 修复 DashboardService 板块数据回退逻辑 Bug
2. 修改资产分析默认数据源为 "自动（推荐）"
3. 移除产业链图谱前端硬编码的模拟数据

### P1 - 高优先级
4. 增强 Dashboard 各板块的空数据状态提示，引导用户摄入数据
5. 添加各板块的 "刷新数据" 按钮
6. 优化自动刷新调度

### P2 - 中优先级
7. 为产业链图谱构建默认行业数据
8. 添加更多爬虫数据源
9. 增强数据新鲜度监控

---

## 8. 现有数据摄入机制分析

### DashboardService 中的自动摄入
在 `core/services/dashboard_service.py:596-629` 中有一个自动摄入触发机制：
- 当检测到 `CanonicalEvent` 数量为 0 时，会启动一个后台线程
- 尝试触发 CLS、CNStock、ZQ 三个爬虫的摄入
- 问题: 依赖本地服务器运行在 `127.0.0.1:8000`，如果用户没有启动服务器则无法工作

### 各爬虫的 API 入口
- CLS: `POST /api/ingest/cls`
- CNStock: `POST /api/ingest/cnstock`
- ZQ: `POST /api/ingest/zq`

---

## 9. 建议实施路径

### 阶段 1: 修复关键 Bug（Task 005-02）
1. 修复 DashboardService 板块数据回退逻辑
2. 修改资产分析默认数据源为 "自动"
3. 移除产业链图谱前端模拟数据回退
4. 确保所有 Dashboard 板块正确处理空数据

### 阶段 2: 增强自动数据获取（Task 005-03 ~ 005-08）
5. 优化产业链图谱真实数据构建
6. 实现更可靠的自动实时数据刷新系统
7. 增强空数据状态提示，引导用户使用摄入功能

### 阶段 3: 全面测试和验证（Task 005-09）
8. 端到端测试所有模块

---

## 10. 附录: 关键代码位置参考

| 功能模块 | 文件位置 | 说明 |
|---------|---------|------|
| DashboardService | `core/services/dashboard_service.py` | 仪表盘数据聚合 |
| DashboardDataRepository | `data_layer/repositories/dashboard_data.py` | 仪表盘专用数据仓储 |
| GraphDataService | `core/services/graph_data_service.py` | 图谱数据服务 |
| Dashboard API | `app/api/routes/dashboard.py` | 仪表盘 API |
| Graph API | `app/api/routes/graph.py` | 图谱 API |
| 前端主逻辑 | `app/web/static/app.js` | Web UI 逻辑 |
| 前端模板 | `app/web/templates/index.html` | HTML 模板 |
| CLS 爬虫 | `data_layer/crawlers/cls/cls.py` | 财联社爬虫 |
| CNStock 爬虫 | `data_layer/crawlers/cnstock/` | 中国证券网爬虫 |
| ZQ 爬虫 | `data_layer/crawlers/zq/` | 知丘研报爬虫 |
| AKShare 爬虫 | `data_layer/crawlers/akshare/` | AKShare 数据爬虫 |

---

**审计完成**: 2026-05-13
**下一步**: 开始执行 Task 005-02，修复关键 Bug！
