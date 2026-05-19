# AF-AUTO-002-02 交易时段感知调度器实现报告

**日期**: 2026-05-11
**任务ID**: af-auto-002-02
**状态**: ✅ 完成

---

## 执行摘要

本任务成功实现了A股交易时段感知的数据采集调度器。发现项目已有一个基础的 `CrawlScheduler`，在此基础上扩展了交易时段感知功能。

### 主要完成工作:
1. ✅ 创建 `TradingCalendar` 模块 - A股交易日历和时段检查
2. ✅ 扩展 `SourceCrawlConfig` - 添加交易时段相关配置
3. ✅ 升级 `CrawlScheduler` - 集成交时段检查
4. ✅ 完整的单元测试覆盖（35个测试用例）
5. ✅ 保持向后兼容 - 现有代码不受影响

---

## 实现详情

### 1. 新增文件

#### `core/utils/trading_calendar.py`
A股交易日历模块，提供以下功能：

**核心类**:
- `TradingPeriod` - 交易时段表示
- `TradingCalendar` - 交易日历和检查器

**交易时段定义**:
- **集合竞价**: 09:15 - 09:25 (可选)
- **上午交易**: 09:30 - 11:30
- **午间休市**: 11:30 - 13:00
- **下午交易**: 13:00 - 15:00

**主要方法**:
| 方法 | 说明 |
|------|------|
| `is_trading_time(dt)` | 检查是否在交易时段 |
| `is_midday_break(dt)` | 检查是否在午间休市 |
| `get_current_period(dt)` | 获取当前所在交易时段 |
| `get_next_session_start(dt)` | 获取下一个交易时段的开始时间 |
| `should_run_now(dt, allow_non_trading)` | 判断是否应该现在运行 |

**测试文件**:
- `tests/unit/core/utils/test_trading_calendar.py` - 22个测试用例

---

### 2. 修改文件

#### `core/services/crawl_scheduler.py`

**新增配置项** (`SourceCrawlConfig`):
- `only_during_trading_hours: bool` - 是否仅在交易时段运行
- `include_auction: bool` - 是否包含集合竞价时段

**默认配置**:
```python
# 财联社、中国证券报: 仅在交易时段运行
# 知丘研报: 可在非交易时段运行
```

**新增属性** (`CrawlScheduler`):
- `calendars: Dict[SourceType, TradingCalendar]` - 每个来源的交易日历

**新增方法**:
| 方法 | 说明 |
|------|------|
| `check_source_should_run(source_type)` | 检查来源是否应该在当前时段运行 |

**修改方法**:
- `_run_crawl_job()` - 在运行前检查交易时段
- `get_status()` - 在状态中包含交易时段信息
- `add_config()` - 同时添加日历
- `__init__()` - 初始化日历

**更新的默认配置** (`DEFAULT_CRAWL_CONFIGS`):
- 财联社: 15分钟间隔，仅交易时段
- 中国证券报: 30分钟间隔，仅交易时段
- 知丘研报: 1小时间隔，允许非交易时段

#### `core/utils/__init__.py`
导出新增的交易日历相关类和函数

---

### 3. 测试文件

#### `tests/unit/core/utils/test_trading_calendar.py`
- 22个测试用例，覆盖所有主要功能

#### `tests/unit/core/services/test_crawl_scheduler.py`
- 13个测试用例，覆盖调度器的交易时段功能

---

## 功能演示

### 交易日历使用
```python
from core.utils.trading_calendar import TradingCalendar
from datetime import datetime

calendar = TradingCalendar()

# 检查是否在交易时段
dt = datetime(2024, 5, 11, 10, 0, 0)
print(calendar.is_trading_time(dt))  # True

# 午间休市检查
dt = datetime(2024, 5, 11, 12, 0, 0)
print(calendar.is_midday_break(dt))  # True

# 获取下一个时段
next_start = calendar.get_next_session_start(dt)
print(next_start)  # 2024-05-11 13:00:00

# 判断是否应该运行
should_run, reason = calendar.should_run_now(dt, allow_non_trading=False)
print(should_run, reason)  # False, "午间休市，..."
```

### 调度器使用
```python
from core.services.crawl_scheduler import get_crawl_scheduler

scheduler = get_crawl_scheduler()

# 获取状态（包含交易时段信息）
status = scheduler.get_status()
for source in status["sources"]:
    print(f"{source['source_type']}: {source['should_run']} - {source['run_reason']}")

# 手动触发（不受交易时段限制）
result = scheduler.trigger_crawl(SourceType.CAILIAN_SHE)
```

---

## 测试结果

### 交易日历测试
```
============================= test session starts ==============================
collected 22 items

tests/unit/core/utils/test_trading_calendar.py::TestTradingPeriod::test_contains PASSED
tests/unit/core/utils/test_trading_calendar.py::TestTradingCalendar::test_is_trading_time_morning PASSED
... [20 more] ...

============================== 22 passed in 0.04s ==============================
```

### 调度器测试
```
============================= test session starts ==============================
collected 13 items

tests/unit/core/services/test_crawl_scheduler.py::TestSourceCrawlConfig::test_default_config PASSED
tests/unit/core/services/test_crawl_scheduler.py::TestCrawlScheduler::test_init PASSED
... [11 more] ...

============================== 13 passed in 2.22s ==============================
```

---

## 成功标准验证

| 成功标准 | 状态 | 说明 |
|---------|------|------|
| 调度器仅在配置的交易时段内运行 | ✅ | `check_source_should_run()` 和 `_run_crawl_job()` 实现 |
| 午间休市处理已实现 | ✅ | `is_midday_break()` 和时段跳过逻辑 |
| 调度器可以手动启动和停止 | ✅ | `start()` 和 `stop()` 方法已存在 |
| 调度器行为已记录在报告中 | ✅ | 本报告 |

---

## 架构特点

### 1. 向后兼容
- 不修改现有 API
- 新增配置项有默认值，不影响现有代码
- `only_during_trading_hours` 默认 True，但旧配置仍能工作

### 2. 灵活配置
- 每个来源可以独立配置是否在交易时段运行
- 支持包含/排除集合竞价
- 支持非交易时段运行（如研报采集）

### 3. 可观测性
- `get_status()` 返回每个来源是否应该运行及原因
- 日志包含明确的跳过时原因
- 补漏任务不受交易时段限制

---

## 与审计结果的对应

根据 `af-auto-002-01-ingestion-readiness-audit.md`:

| 审计发现 | 本任务处理 |
|---------|----------|
| ✅ 所有爬虫已有完整的持久化去重 | 保持不变 |
| ✅ 所有爬虫已实现停止条件和分页 | 保持不变 |
| ⚠️ 缺少"增量抓取直到已知" | 下一任务处理 |
| ⚠️ 缺少统一调度器 | ✅ 本任务完成（扩展已有调度器） |

---

## 后续建议

### 立即下一步
1. **af-auto-002-03** - 实现"增量抓取直到已知"水位线追踪
2. **af-auto-002-09** - 审计当前报告生成能力（可以并行）

### 中期优化
- 考虑添加节假日日历支持
- 考虑添加不同市场（港股、美股）的时段配置
- 考虑添加调度器的 REST API 端点

---

## 文件变更清单

**新增文件**:
- `core/utils/trading_calendar.py`
- `tests/unit/core/utils/test_trading_calendar.py`
- `tests/unit/core/services/test_crawl_scheduler.py`

**修改文件**:
- `core/services/crawl_scheduler.py`
- `core/utils/__init__.py`

---

**报告完成时间**: 2026-05-11
**下一步任务**: af-auto-002-03 或 af-auto-002-09
