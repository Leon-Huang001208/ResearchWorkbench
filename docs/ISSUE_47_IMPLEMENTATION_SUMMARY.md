# Issue #47: 回测视角 - 实现总结

## 概述

Issue #47 实现了回测视角的完整功能，确保在回测时不会意外使用未来信息，并提供消息面特征和数据分层管理。

## 完成的工作

### 1. 核心契约扩展 (`core/contracts/backtest.py`)

新增完整的回测相关契约：

**数据分层枚举：
- `DataTier` - 数据分层（热/温/冷/归档）

**时间可用性：
- `TimeAvailability` - 时间可用性模型，确保不使用未来信息
  - `published_at` - 发布时间
  - `crawl_time` - 抓取时间
  - `available_time` - 可用时间 = max(published_at, crawl_time)
  - `event_time` - 事件发生时间
  - `is_available_at(query_time)` - 检查在某个时间点是否可用
  - `get_tier(reference_time)` - 获取数据层级

**历史回放：
- `HistoricalReplayQuery` - 历史回放查询
- `HistoricalEvent` - 历史事件（包含时间可用性信息）
- `HistoricalEventStream` - 历史事件流

**消息面特征：
- `NewsFeatureType` - 特征类型枚举
  - MENTION_COUNT, EVENT_COUNT, SENTIMENT_SCORE
  - POSITIVE_INTENSITY, NEGATIVE_INTENSITY
  - SOURCE_WEIGHTED_SIGNAL, THEME_HEAT
  - ANALYST_OPINION_TREND, NEWS_RESONANCE
- `NewsFeatureQuery` - 特征查询
- `NewsFeatureValue` - 特征值
- `NewsFeatureSet` - 特征集合

**事件-技术对齐：
- `EventTechAlignmentRequest` - 对齐请求
- `EventTechAlignment` - 对齐结果

**视图上下文：
- `ViewContext` - 视图上下文（报告/回测）
- `RetrievalConfig` - 检索配置（根据视图调整）

### 2. 历史回放服务 (`core/services/historical_replay_service.py`)

提供时间旅行视角的核心服务：

**核心功能：
- `query(HistoricalReplayQuery)` - 历史回放查询
- `get_available_at(entity_id, query_time, lookback_days)` - 获取某个实体在某个时间点可见的所有事件
- `check_time_travel_safety(data_id, data_time, analysis_time)` - 检查时间旅行安全性
- `get_retrieval_config(view_context)` - 获取合适的检索配置

**特性：
- 严格时间过滤 - 确保查询时间之后可用的信息
- 多维度过滤（实体、行业、来源、事件类型
- 内置示例数据用于演示
- 支持通过时间安全校验防止未来信息泄露

### 3. 消息面特征服务 (`core/services/news_feature_service.py`)

计算新闻相关的特征：

**核心功能：
- `compute_features(NewsFeatureQuery)` - 计算消息面特征
- `get_entity_feature_ts(entity_id, feature_type, start, end)` - 获取实体特征时间序列
- `_compute_sentiment(events)` - 计算情绪
- `_compute_positive_intensity(events)` - 计算正面强度
- `_compute_negative_intensity(events)` - 计算负面强度
- `_compute_theme_heat(events)` - 计算主题热度

**支持的特征类型：
- 提及次数统计
- 事件统计
- 情绪分数
- 正面/负面强度
- 主题热度
- 来源加权信号

**时间粒度支持：
- 1h, 4h, 1d, 1w, 1mo

### 4. 数据分层服务 (`core/services/data_tier_service.py`)

管理热/温/冷/归档数据的管理：

**核心功能：
- `get_data_tier(time_availability, reference_time)` - 获取数据所属层级
- `get_tier_for_age(age_days)` - 根据年龄获取层级
- `should_migrate(data_id, time_availability, reference_time)` - 检查是否应该迁移
- `record_access(data_id, access_time)` - 记录数据访问
- `get_access_frequency(data_id, window_days)` - 获取访问频率
- `get_tier_summary()` - 获取各层数据统计
- `get_tier_retention_policy(tier)` - 获取层级保留策略

**数据分层规则：
- HOT (热数据) - <= 7天，高频访问，无压缩，SSD存储
- WARM (温数据) - <= 7-30天，中频访问，LZ4压缩，SSD存储
- COLD (冷数据) - <= 365天，低频访问，Gzip压缩，HDD存储
- ARCHIVED (归档数据) - >365天，长期存储，Gzip压缩，冷存储

### 5. 报告与回测视角分离

**报告视角 (ViewContext.REPORT：
- 最大回顾 30天
- 最低可靠性分数 0.5
- 允许观点源
- 不强制可用时间检查

**回测视角 (ViewContext.BACKTEST：
- 最大回顾 3650天（10年）
- 最低可靠性分数 0.0
- 允许观点源
- 强制可用时间检查（保证不会使用未来信息

### 6. 单元测试 (`tests/unit/test_issue47.py`)

完整的测试覆盖：

**测试类：
- TestTimeAvailability - 时间可用性测试
- TestHistoricalReplayService - 历史回放服务测试
- TestNewsFeatureService - 消息面特征服务测试
- TestDataTierService - 数据分层服务测试
- TestViewContextSeparation - 视图分离测试
- TestIntegration - 集成测试

**测试数量：
- 19 个测试，全部通过

## 设计特性

### 时间旅行安全

**三层防护：
1. 数据记录每个数据点的可用时间
2. 查询时强制检查数据是否在查询时间之前可用
3. 提供安全检查API

### 数据分层策略

**按年龄分层：
- 最近7天：热数据 - 高频访问
- 7-30天：温数据 - 中频访问
- 30-365天：冷数据 - 低频访问
- >365天：归档数据 - 长期存储

**访问统计：
- 记录数据访问频率
- 可以用于优化分层策略

### 视图上下文感知

**分离关注点：
- 报告：快速响应，使用最近高可靠性
- 回测：严格历史真实，防止未来函数

## 验收标准对照

Issue #47 的所有验收标准已达成：
- [x] 能清晰解释 available_time 在回测中的作用
- [x] 能定义一版 historical replay query 逻辑
- [x] 能列出首批消息面特征候选
- [x] 能说明与技术面数据如何时间对齐

## 使用示例

### 基本历史回放

```python
from datetime import datetime, timedelta
from core.contracts.backtest import HistoricalReplayQuery, ViewContext
from core.services.historical_replay_service import HistoricalReplayService

service = HistoricalReplayService()

# 假设我们现在回测到 7天前
backtest_time = datetime.utcnow() - timedelta(days=7)

query = HistoricalReplayQuery(
    query_time=backtest_time,
    entity_ids=["600519.SH"],
    lookback_days=30,
    max_items=50,
)

# 回测结果
result = service.query(query)

for event in result.events:
    # 所有事件都确保在 backtest_time 时已可用！
    print(f"Event: {event.title}")
```

### 计算消息面特征

```python
from datetime import datetime, timedelta
from core.contracts.backtest import NewsFeatureQuery, NewsFeatureType
from core.services.news_feature_service import NewsFeatureService

service = NewsFeatureService()

now = datetime.utcnow()
query = NewsFeatureQuery(
    entity_id="600519.SH",
    feature_types=[
        NewsFeatureType.MENTION_COUNT,
        NewsFeatureType.SENTIMENT_SCORE,
    ],
    start_time=now - timedelta(days=30),
    end_time=now,
    time_bucket="1d",
)

features = service.compute_features(query)

for feature in features:
    print(f"{feature.feature_type}: {feature.value} at {feature.timestamp}")
```

### 数据分层管理

```python
from datetime import datetime, timedelta
from core.contracts.backtest import TimeAvailability
from core.services.data_tier_service import DataTierService

service = DataTierService()

now = datetime.utcnow()
data_time = now - timedelta(days=15)
ta = TimeAvailability(
    crawl_time=data_time,
    available_time=data_time,
)

tier = service.get_data_tier(ta, now)
print(f"Data tier: {tier}")

# 应该返回 DataTier.WARM
```

### 回测视角 vs 报告视角

```python
from core.contracts.backtest import ViewContext, RetrievalConfig
from core.services.historical_replay_service import HistoricalReplayService

service = HistoricalReplayService()

# 报告视角 - 最近数据，宽松时间检查
report_config = service.get_retrieval_config(ViewContext.REPORT)
print(f"Report view: {report_config.max_lookback_days} days")

# 回测视角 - 完整历史，严格时间检查
backtest_config = service.get_retrieval_config(ViewContext.BACKTEST)
print(f"Backtest view: {backtest_config.max_lookback_days} days")
```

## 文件清单

新增文件：
- core/contracts/backtest.py - 回测相关契约
- core/services/historical_replay_service.py - 历史回放服务
- core/services/news_feature_service.py - 消息面特征服务
- core/services/data_tier_service.py - 数据分层服务
- tests/unit/test_issue47.py - Issue #47 单元测试
- docs/ISSUE_47_IMPLEMENTATION_SUMMARY.md - 本文档

修改文件：
- core/contracts/__init__.py - 新增契约导出

## 下一步

- Issue #48: TBD（后续需求

## 总结

Issue #47 提供了完整的回测视角功能：

1. **时间可用性模型 - 确保不会使用未来信息
2. **历史回放查询 - 在任意时间点的信息可见性
3. **消息面特征 - 新闻相关特征计算
4. **数据分层管理 - 热/温/冷/归档
5. **视图分离 - 报告 vs 回测视角

所有功能已实现并测试通过，共包含 19个单元测试，全部通过！
