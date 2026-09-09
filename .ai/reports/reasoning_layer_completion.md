# Reasoning Layer TODO Completion

**任务**: rwb-auto-001-03 (Complete Reasoning Layer TODOs)
**日期**: 2026-05-11
**状态**: Completed

## Summary

已完成推理层的全部 4 个 TODO 项。

## TODO Completion

### 1. ✅ LLM Hypothesis Generation (scenarios/builder.py)

**状态**: Already implemented with safe fallback

- 代码已支持通过 `model_gateway` 进行 LLM 假设生成
- 当 `model_gateway` 不可用时，自动回退到规则生成 ( `_build_by_rules` )
- 规则生成提供 3 个标准假设：基准、乐观、悲观

### 2. ✅ Assertion Query Support (evidence/collector.py)

**状态**: Implemented

**改动**:
- 当 `assertion_repo` 可用时，遍历 `state.subject_ids`
- 使用 `get_by_subject()` 查询每个主体的断言
- 将断言 ID 收集到 `state.retrieved_assertion_ids`
- 添加去重逻辑

### 3. ✅ Event Query Support (evidence/collector.py)

**状态**: Implemented

**改动**:
- 当 `event_repo` 可用时，遍历 `state.subject_ids`
- 使用 `get_by_entity()` 查询关联到每个主体的事件
- 将事件信息收集到 `state.retrieved_events`
- 包含字段：event_id, title, event_time (ISO 格式)

### 4. ✅ Temporal Correlation Check (skeptic/reviewer.py)

**状态**: Implemented

**改动**:
- 添加 `datetime` 和 `timedelta` 导入
- 检查 `state.retrieved_events` 中的事件时效性
- 阈值设置为 90 天
- 当发现旧事件时，向 `skeptic_notes` 添加警告

## Files Modified

| File | Change |
|------|--------|
| reasoning/evidence/collector.py | Added assertion and event query logic |
| reasoning/skeptic/reviewer.py | Added temporal correlation check |
| reasoning/scenarios/builder.py | No change - already implemented |

## Test Results

- 推理层相关测试：42 个通过，5 个失败（失败与本次改动无关，是测试数据缺少必需字段）
- 核心功能已正常工作

## Notes

失败的测试是由于 `tests/unit/test_scenario_graph_data.py` 中的 `_make_event()` 函数创建 `CanonicalEvent` 时缺少必需字段（`source_type`, `source_name`, `title`），这是预先存在的问题，与本次改动无关。
