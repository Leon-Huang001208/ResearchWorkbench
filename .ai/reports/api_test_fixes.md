# API 测试修复报告

**任务**: af-auto-001-01b (Fix API test failures)
**日期**: 2026-05-11
**状态**: 完成

## 问题分析

API 测试失败主要有两个问题：

1. **异步方法 Mock 问题**: `AssetAnalysisService.generate_snapshot` 是异步方法，但测试使用了普通 `MagicMock`
2. **Datetime 类型问题**: `AssetAnalysisSnapshot.as_of` 字段需要 `datetime` 对象，但测试传入了 ISO 格式字符串

## 修复内容

### 修复的测试
- `test_analyze_asset`: 
  - 使用 `datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc)` 替代字符串
  - 使用 `AsyncMock` 替代 `MagicMock` 用于异步方法
- `test_analyze_with_as_of`:
  - 使用 `datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)` 替代字符串
  - 使用 `AsyncMock` 替代 `MagicMock` 用于异步方法

## 测试结果

### 修复前
```
FAILED tests/unit/test_api.py::TestAssetsAPI::test_analyze_asset
FAILED tests/unit/test_api.py::TestAssetsAPI::test_analyze_with_as_of
```

### 修复后
```
23 passed, 14 warnings in 2.93s
```

**所有 API 测试通过！**

## 修改文件

- `tests/unit/test_api.py`: 修复了两个资产分析测试用例

## 备注

- 其他 API 测试（Scenarios、Review、Signals、Ingest、Pipeline、Graph）无需修改，本身就是通过的
- 虽然有一些 DeprecationWarning（关于 FastAPI lifespan），但不影响测试运行
