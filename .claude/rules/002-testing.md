---
name: Testing Standards
description: AlphaFoundry 测试规范 - pytest 测试规范
---

# 测试规范

## 概述

AlphaFoundry 使用 pytest 作为测试框架，确保代码质量和功能正确性。

---

## 测试目录结构

```
tests/
├── unit/           # 单元测试
│   ├── core/
│   ├── data_layer/
│   ├── knowledge_layer/
│   ├── reasoning/
│   ├── reporting/
│   ├── signal_lab/
│   └── app/
├── integration/    # 集成测试
├── contract/       # 契约测试
└── conftest.py     # pytest 配置和 fixtures
```

---

## 命名约定

### 测试文件命名

- 单元测试文件：`test_<module_name>.py`
- 集成测试文件：`test_<feature>_integration.py`
- 测试文件放在与源代码对应的目录结构中

**示例**：
- 源代码：`core/services/asset_analysis_service.py`
- 测试文件：`tests/unit/core/services/test_asset_analysis_service.py`

### 测试函数命名

- 格式：`test_<what_is_being_tested>_<condition>`
- 使用描述性的名称，说明测试的内容和条件

**示例**：
```python
def test_create_signal_generates_valid_id()
def test_validate_signal_rejects_low_confidence()
def test_backtest_calculates_correct_total_return()
```

---

## 测试编写规范

### 基本结构

每个测试应该包含三个部分：

1. **Arrange**（安排）- 设置测试环境和数据
2. **Act**（行动）- 执行要测试的操作
3. **Assert**（断言）- 验证结果是否符合预期

**示例**：
```python
def test_feature_builder_computes_all_features(prices_data):
    # Arrange
    builder = FeatureBuilder()
    builder.add_group(PriceVolumeFeatures())
    
    # Act
    features = builder.compute_features(prices_data)
    
    # Assert
    assert not features.empty
    assert "price_change" in features.columns
```

### 使用 fixtures

在 `conftest.py` 中定义可重用的 fixtures：

```python
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def prices_data():
    """测试用价格数据"""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    return pd.DataFrame({
        "close": 100.0 + np.random.randn(100).cumsum(),
        "volume": np.random.randint(100000, 1000000, 100)
    }, index=dates)

@pytest.fixture
def sample_signal():
    """测试用 AlphaSignal"""
    from core.contracts import AlphaSignal
    return AlphaSignal(
        signal_id="test_001",
        subject_id="600519.SH",
        thesis="测试信号",
        score=0.8,
        confidence=0.7
    )
```

### Mock 外部依赖

对外部依赖（如数据库、API、模型网关）使用 mock：

```python
from unittest.mock import Mock, patch

def test_asset_analysis_service_with_mock_adapter():
    # Arrange
    mock_adapter = Mock()
    mock_adapter.get_price_data.return_value = {
        "close": 100.0,
        "volume": 1000000
    }
    
    service = AssetAnalysisService(adapter=mock_adapter)
    
    # Act
    snapshot = service.generate_snapshot("600000.SH")
    
    # Assert
    mock_adapter.get_price_data.assert_called_once_with("600000.SH")
```

---

## 运行测试

### 基本命令

```bash
# 运行所有测试
pytest

# 运行特定目录的测试
pytest tests/unit/core/

# 运行特定文件的测试
pytest tests/unit/core/services/test_asset_analysis_service.py

# 运行特定测试函数
pytest tests/unit/core/services/test_asset_analysis_service.py::test_create_snapshot
```

### 常用选项

```bash
# 显示详细输出
pytest -v

# 显示 print 输出
pytest -s

# 只运行失败的测试
pytest --lf

# 显示覆盖率报告
pytest --cov=core --cov=data_layer --cov=reporting

# 生成 HTML 覆盖率报告
pytest --cov=core --cov=data_layer --cov=reporting --cov-report=html
```

---

## 测试覆盖目标

- 核心业务逻辑：> 80% 覆盖
- 数据契约：> 90% 覆盖
- CLI 命令：> 70% 覆盖
- Signal Lab 模块：> 75% 覆盖

---

## 测试检查清单

提交代码前确认：
- [ ] 新增代码包含对应的单元测试
- [ ] 所有现有测试通过
- [ ] 测试覆盖率没有显著下降
- [ ] 测试使用适当的 fixtures
- [ ] 外部依赖被正确 mock
- [ ] 测试描述清晰明确

