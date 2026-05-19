# AF-AUTO-005-02 修复报告：移除模拟数据依赖

**修复日期**: 2026-05-13  
**任务ID**: af-auto-005-02  
**状态**: ✅ 完成

---

## 1. 执行摘要

本任务成功修复了 AlphaFoundry 中阻止真实数据显示的关键 Bug，并移除了不必要的模拟数据依赖。

**主要成就**:
- ✅ 修复了 DashboardService 板块数据回退逻辑过于严格的 Bug
- ✅ 修改资产分析默认数据源为 "自动（推荐）"
- ✅ 移除产业链图谱前端硬编码的模拟数据
- ✅ 验证了市场概览现在能正确显示真实数据

---

## 2. 修复详情

### 修复 1: DashboardService 板块数据回退逻辑

**问题文件**: `core/services/dashboard_service.py` 第 293 行

**原始问题代码**:
```python
# 如果没有真实板块数据，回退到模拟
if not top_up_sectors or not top_down_sectors:  # ❌ 只要有一个方向没有就回退
    mock_up, mock_down = self._get_mock_sectors()
    if not top_up_sectors:
        top_up_sectors = mock_up
    if not top_down_sectors:
        top_down_sectors = mock_down
    has_real_sectors = False
```

**问题说明**:
- 原始代码要求**同时**有上涨板块和下跌板块才使用真实数据
- 但实际情况经常是只有上涨或只有下跌
- 在我们的测试数据中，只有上涨板块数据，没有下跌板块，导致整体回退到模拟数据

**修复后代码**:
```python
# 只要有一个方向有板块数据就使用真实数据，另一个方向可以是空的
# 只有当两个方向都没有数据时才回退到模拟
if not top_up_sectors and not top_down_sectors:  # ✅ 只有两个都没有才回退
    mock_up, mock_down = self._get_mock_sectors()
    top_up_sectors = mock_up
    top_down_sectors = mock_down
    has_real_sectors = False
```

**修复效果**:
- 现在只要有一个方向有真实数据就会使用真实数据
- 另一个方向可以是空列表，不会影响整体判断

---

### 修复 2: 资产分析默认数据源

**问题文件**: `app/web/templates/index.html` 第 233 行

**原始代码**:
```html
<option value="mock" selected data-i18n="asset.source_mock">Mock 数据</option>
<option value="auto" data-i18n="asset.source_auto">自动（推荐）</option>
```

**修复后代码**:
```html
<option value="mock" data-i18n="asset.source_mock">Mock 数据</option>
<option value="auto" selected data-i18n="asset.source_auto">自动（推荐）</option>
```

**修复效果**:
- 新用户默认会看到真实数据而不是模拟数据
- 用户仍然可以手动选择使用 Mock 数据（如果需要）

---

### 修复 3: 移除产业链图谱前端硬编码模拟数据

**问题文件**: `app/web/static/app.js` 第 1421-1438 行

**原始代码**:
```javascript
const mockNodes = [
    { id: 'up1', label: '上游1', group: 'upstream' },
    { id: 'up2', label: '上游2', group: 'upstream' },
    { id: 'mid1', label: '中游1', group: 'midstream' },
    { id: 'mid2', label: '中游2', group: 'midstream' },
    { id: 'down1', label: '下游1', group: 'downstream' },
    { id: 'down2', label: '下游2', group: 'downstream' },
];
const mockLinks = [
    { source: 'up1', target: 'mid1', label: '供应' },
    { source: 'up2', target: 'mid1', label: '供应' },
    { source: 'mid1', target: 'down1', label: '供应' },
    { source: 'mid2', target: 'down1', label: '替代' },
    { source: 'mid2', target: 'down2', label: '依赖' },
];

const nodes = data.nodes?.length ? data.nodes : mockNodes;
const links = data.edges?.length ? data.edges : mockLinks;
```

**修复后代码**:
```javascript
const nodes = data.nodes || [];
const links = data.edges || [];

// 如果没有数据，显示空状态提示
if (!nodes.length) {
    container.innerHTML = '<div class="empty-state">暂无产业链数据</div>';
    return;
}
```

**修复效果**:
- 移除了硬编码的模拟数据
- 当没有真实数据时，显示友好的空状态提示
- 用户能清楚知道当前没有数据，而不是看到假数据

---

## 3. 验证结果

运行 `scripts/test_fix.py` 的测试结果:

```
1️⃣ 测试 get_market_overview_section...
[info] Using real data for market overview: news=True, sectors=True

📰 全球新闻: 5 条
   1. 央行宣布降准0.5个百分点，释放长期资金约1万亿元... (真实)
   2. 国资委要求央企加大科技创新投入，2026年研发投入增速不低于15%... (真实)
   3. 贵州茅台2026年Q1净利润同比增长18.2%，超出市场预期... (真实)

📈 上涨板块: 5 个
   1. 白酒: +10.00% (真实)
   2. 消费: +10.00% (真实)
   3. 业绩: +10.00% (真实)

📉 下跌板块: 0 个

📊 数据来源标识:
   uses_real_news: True
   uses_real_sectors: True
   last_updated: 2026-05-13 09:14:36.483444+00:00

✅ 检查结果:
✅ 新闻数据使用真实数据！
✅ 板块数据使用真实数据！

🎉 所有修复正常工作！Dashboard 现在会显示真实数据！
```

---

## 4. 修改文件清单

| 文件 | 修改说明 |
|-----|---------|
| `core/services/dashboard_service.py` | 修复板块数据回退逻辑 |
| `app/web/templates/index.html` | 修改资产分析默认数据源为 "自动" |
| `app/web/static/app.js` | 移除产业链图谱硬编码模拟数据 |

---

## 5. 今日板块时间范围说明

测试中发现 Today 板块的新事件为 0，这是正常的：
- today_cutoff 设置为过去 24 小时
- 数据库中的事件创建时间是 2026-05-10
- 当前日期是 2026-05-13，超过了 24 小时窗口
- 如果摄入更新的事件，就会正常显示

---

## 6. 后续建议

虽然关键问题已修复，但仍有可以改进的地方：

1. **空状态优化**: 为各板块添加更友好的空状态提示，引导用户使用数据摄入功能
2. **手动刷新按钮**: 添加一键刷新按钮，让用户可以主动触发数据摄入
3. **自动刷新调度**: 优化后台自动刷新逻辑，确保数据持续更新
4. **产业链默认数据**: 为常见行业构建默认的产业链图谱数据

---

**修复完成**: 2026-05-13  
**下一步**: 继续执行剩余任务！
