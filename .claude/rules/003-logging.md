---
name: Logging Standards
description: AlphaFoundry 日志规范 - 使用 core/observability 日志系统
---

# 日志规范

## 概述

AlphaFoundry 使用 `core/observability` 模块提供统一的日志系统，确保日志格式一致且可配置。

---

## 基本使用

### 获取 logger

```python
from core.observability import get_logger

logger = get_logger(__name__)
```

### 日志级别使用指南

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| `DEBUG` | 详细的调试信息，仅在开发时有用 | `logger.debug(f"Processing {len(data)} rows")` |
| `INFO` | 一般信息，流程关键节点 | `logger.info("Signal validation completed")` |
| `WARNING` | 警告信息，不影响执行但需注意 | `logger.warning("Low confidence score, consider reviewing")` |
| `ERROR` | 错误信息，需要处理 | `logger.error(f"Failed to fetch data: {e}", exc_info=True)` |

### 日志记录示例

```python
from core.observability import get_logger

logger = get_logger(__name__)

def process_signal(signal):
    logger.debug(f"Processing signal: {signal.signal_id}")
    
    try:
        # 处理信号
        result = validate_signal(signal)
        logger.info(f"Signal {signal.signal_id} processed successfully")
        return result
    except Exception as e:
        logger.error(f"Error processing signal {signal.signal_id}: {e}", exc_info=True)
        raise
```

---

## 结构化日志约定

### 使用结构化消息

```python
# 好的做法
logger.info(
    "Backtest completed",
    extra={
        "total_return": result.total_return,
        "sharpe_ratio": result.sharpe_ratio,
        "num_trades": result.num_trades
    }
)

# 避免
logger.info(f"Backtest completed: return={result.total_return}, sharpe={result.sharpe_ratio}")
```

### 日志中包含关键信息

对于重要操作，确保日志包含：
- 操作名称
- 涉及的实体 ID（如 signal_id, subject_id）
- 关键参数和结果
- 耗时（如需要）

```python
import time
from core.observability import get_logger, record_metric

logger = get_logger(__name__)

def generate_snapshot(asset_id):
    start_time = time.time()
    logger.info(f"Starting snapshot generation for {asset_id}")
    
    try:
        snapshot = do_generate_snapshot(asset_id)
        
        duration = time.time() - start_time
        record_metric("snapshot_generation_time", duration, {"asset_id": asset_id})
        
        logger.info(
            f"Snapshot generated successfully for {asset_id}",
            extra={"duration_seconds": duration}
        )
        return snapshot
    except Exception as e:
        logger.error(f"Snapshot generation failed for {asset_id}: {e}", exc_info=True)
        raise
```

---

## Metrics 使用

### 记录指标

```python
from core.observability import record_metric, increment_counter

# 记录计时器
record_metric("backtest_execution_time", duration_seconds, tags={"strategy": "mean_reversion"})

# 递增计数器
increment_counter("signals_created", tags={"status": "approved"})
```

---

## 日志检查清单

- [ ] 每个模块使用 `get_logger(__name__)` 获取 logger
- [ ] 使用适当的日志级别
- [ ] 异常时使用 `exc_info=True` 记录堆栈跟踪
- [ ] 重要操作记录开始和结束
- [ ] 关键指标使用 `record_metric` 或 `increment_counter`
- [ ] 避免在日志中记录敏感信息（密码、密钥等）
- [ ] 日志消息清晰明确，包含必要的上下文

