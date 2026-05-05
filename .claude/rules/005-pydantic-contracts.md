---
name: Pydantic Contracts Standards
description: AlphaFoundry Pydantic 契约规范 - Pydantic v2 模型规范
---

# Pydantic 契约规范

## 概述

AlphaFoundry 使用 Pydantic v2 定义核心数据契约，确保类型安全和数据验证。

---

## 契约文件位置

所有契约定义在 `core/contracts/` 目录：

```
core/contracts/
├── __init__.py          # 导出所有契约
├── ids.py               # CanonicalId 和其他 ID 类型
├── documents.py         # DocumentEnvelope 等
├── assets.py            # AssetAnalysisSnapshot
├── events.py            # CanonicalEvent
├── assertions.py        # Assertion
├── scenarios.py         # ScenarioSet, ScenarioHypothesis
├── traces.py            # ReasoningTrace
├── reporting.py         # SectionSpec, SectionOutput
└── signals.py           # AlphaSignal, TradeCandidate
```

---

## 模型定义规范

### 基本结构

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


class AlphaSignal(BaseModel):
    """Alpha 信号 - 表示一个投资信号"""
    
    # 必需字段
    signal_id: str = Field(..., description="信号唯一标识符")
    subject_id: str = Field(..., description="标的资产标识符")
    thesis: str = Field(..., description="信号论点")
    
    # 可选字段带默认值
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="评分")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="置信度")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    # 列表和字典
    evidence_refs: List[str] = Field(default_factory=list, description="证据引用列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    @field_validator('score', 'confidence')
    @classmethod
    def validate_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Value must be between 0.0 and 1.0')
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "signal_id": "signal_001",
                    "subject_id": "600519.SH",
                    "thesis": "看好白酒股",
                    "score": 0.8,
                    "confidence": 0.7
                }
            ]
        }
    }
```

---

## 字段规范

### Field 使用

- 所有字段使用 `Field()` 提供描述
- 必需字段使用 `...` 表示
- 可选字段使用 `Optional[T]` 和默认值
- 数值字段添加验证（`ge`, `le`, `gt`, `lt`）

### 常用字段类型

| 类型 | 使用场景 | 示例 |
|------|----------|------|
| `str` | 标识符、文本 | `signal_id: str` |
| `Optional[str]` | 可选字符串 | `source: Optional[str] = None` |
| `float` | 数值、评分 | `score: float` |
| `datetime` | 时间戳 | `created_at: datetime` |
| `List[T]` | 列表 | `evidence_refs: List[str]` |
| `Dict[str, Any]` | 字典 | `metadata: Dict[str, Any]` |

### 默认值

- 使用 `default_factory` 用于可变类型（列表、字典）
- 使用 `default` 用于不可变类型

```python
# 正确
evidence_refs: List[str] = Field(default_factory=list)
metadata: Dict[str, Any] = Field(default_factory=dict)
created_at: datetime = Field(default_factory=datetime.utcnow)

# 避免 - 可变默认值问题
evidence_refs: List[str] = Field(default=[])
```

---

## 验证器使用

### 字段验证器

```python
from pydantic import field_validator

class AlphaSignal(BaseModel):
    score: Optional[float] = None
    
    @field_validator('score')
    @classmethod
    def validate_score(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('score must be between 0.0 and 1.0')
        return v
```

### 模型验证器

```python
from pydantic import model_validator

class BacktestResult(BaseModel):
    total_return: float
    annual_return: Optional[float] = None
    
    @model_validator(mode='after')
    def calculate_annual_return(self) -> 'BacktestResult':
        if self.annual_return is None and self.total_return is not None:
            # 计算年化收益
            self.annual_return = calculate_annualized_return(self.total_return)
        return self
```

---

## Pydantic v1/v2 兼容性

### 处理兼容性问题

对于可能需要同时支持 v1 和 v2 的代码：

```python
try:
    # Pydantic v2
    from pydantic import BaseModel, Field, field_validator, model_validator
    PYDANTIC_V2 = True
except ImportError:
    # Pydantic v1
    from pydantic import BaseModel, Field, validator as field_validator
    from pydantic import root_validator as model_validator
    PYDANTIC_V2 = False

# 使用时的兼容性包装
if PYDANTIC_V2:
    # v2 specific code
else:
    # v1 specific code
```

### 通用方法

```python
def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, 'model_dump'):
        return model.model_dump()  # v2
    else:
        return model.dict()         # v1

def model_copy(model: BaseModel, **kwargs) -> BaseModel:
    if hasattr(model, 'model_copy'):
        return model.model_copy(**kwargs)  # v2
    else:
        return model.copy(**kwargs)         # v1
```

---

## 契约导出

在 `core/contracts/__init__.py` 中导出所有契约：

```python
from .ids import CanonicalId
from .documents import DocumentEnvelope
from .assets import AssetAnalysisSnapshot
from .events import CanonicalEvent
from .assertions import Assertion
from .scenarios import ScenarioSet, ScenarioHypothesis
from .traces import ReasoningTrace
from .reporting import SectionSpec, SectionOutput
from .signals import AlphaSignal, TradeCandidate

__all__ = [
    'CanonicalId',
    'DocumentEnvelope',
    'AssetAnalysisSnapshot',
    'CanonicalEvent',
    'Assertion',
    'ScenarioSet',
    'ScenarioHypothesis',
    'ReasoningTrace',
    'SectionSpec',
    'SectionOutput',
    'AlphaSignal',
    'TradeCandidate',
]
```

---

## 契约检查清单

- [ ] 每个契约类有清晰的 docstring
- [ ] 所有字段使用 `Field()` 并提供 description
- [ ] 数值字段有适当的范围验证
- [ ] 可变默认值使用 `default_factory`
- [ ] 验证器使用 `@classmethod`
- [ ] 模型在 `__init__.py` 中导出
- [ ] 包含至少一个 example

