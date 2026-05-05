---
name: Signal Lab Standards
description: AlphaFoundry Signal Lab 开发规范 - 特征、标签、评分、回测
---

# Signal Lab 开发规范

## 概述

Signal Lab 是 AlphaFoundry 的信号研究模块，提供特征工程、标签生成、信号评分和回测功能。

---

## 模块结构

```
signal_lab/
├── __init__.py
├── features/          # 特征工程
│   ├── base.py        # 基类：Feature, FeatureGroup
│   ├── builder.py     # FeatureBuilder
│   └── groups/        # 特征组实现
│       ├── price_volume.py
│       ├── valuation.py
│       ├── financial.py
│       ├── fund_flow.py
│       ├── industry.py
│       └── macro.py
├── labels/            # 标签生成
│   ├── base.py        # 基类：Labeler
│   ├── relative_return.py
│   └── event_driven.py
├── scoring/           # 信号评分
│   ├── scorer.py      # SignalScorer, CompositeScorer
│   └── ranker.py      # SignalRanker
└── backtests/         # 回测引擎
    ├── base.py        # 基类：Backtester, BacktestResult
    └── simple.py      # 简单回测实现
```

---

## 特征开发规范

### Feature 基类

```python
from abc import ABC, abstractmethod
import pandas as pd
from typing import Any


class Feature(ABC):
    """特征基类"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """计算特征
        
        Args:
            data: 输入数据，通常包含 OHLCV 等
            **kwargs: 额外参数
            
        Returns:
            pd.Series: 特征值序列，索引与输入对齐
        """
        pass
```

### 实现自定义 Feature

```python
import pandas as pd
import numpy as np
from signal_lab.features.base import Feature


class PriceChangeFeature(Feature):
    """价格变化特征"""
    
    def __init__(self, period: int = 1):
        super().__init__(
            name=f"price_change_{period}d",
            description=f"{period}日价格变化率"
        )
        self.period = period
    
    def compute(self, data: pd.DataFrame, **kwargs) -> pd.Series:
        """计算价格变化率"""
        return data["close"].pct_change(periods=self.period)
```

### FeatureGroup 使用

```python
from signal_lab.features.base import FeatureGroup
from signal_lab.features.groups.price_volume import (
    PriceChangeFeature,
    MovingAverageFeature
)


class PriceVolumeFeatures(FeatureGroup):
    """价量特征组"""
    
    def __init__(self):
        super().__init__("price_volume")
        self.add_feature(PriceChangeFeature(period=1))
        self.add_feature(PriceChangeFeature(period=5))
        self.add_feature(MovingAverageFeature(window=10))
        self.add_feature(MovingAverageFeature(window=20))
```

### FeatureBuilder 使用

```python
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import PriceVolumeFeatures, ValuationFeatures


# 创建 builder
builder = FeatureBuilder()

# 添加特征组
builder.add_group(PriceVolumeFeatures())
builder.add_group(ValuationFeatures())

# 计算所有特征
features = builder.compute_features(price_data)

# 查看可用特征
print(builder.get_all_feature_names())
```

---

## 标签开发规范

### Labeler 基类

```python
from abc import ABC, abstractmethod
import pandas as pd
from typing import Any


class Labeler(ABC):
    """标签生成基类"""
    
    @abstractmethod
    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """计算标签
        
        Args:
            data: 输入数据，通常包含价格序列
            **kwargs: 额外参数
            
        Returns:
            pd.Series: 标签序列，索引与输入对齐
        """
        pass
```

### 实现自定义 Labeler

```python
import pandas as pd
from signal_lab.labels.base import Labeler


class RelativeReturnLabeler(Labeler):
    """相对收益标签生成器"""
    
    def __init__(self, horizon: int = 20, forward: bool = True):
        self.horizon = horizon
        self.forward = forward
    
    def compute(self, data: pd.DataFrame, **kwargs) -> pd.Series:
        """计算未来收益"""
        if isinstance(data, pd.Series):
            prices = data
        else:
            prices = data["close"]
        
        if self.forward:
            # 未来收益作为标签
            future_returns = prices.pct_change(periods=self.horizon).shift(-self.horizon)
            return future_returns
        else:
            # 历史收益
            return prices.pct_change(periods=self.horizon)
```

---

## 评分开发规范

### SignalScorer 基类

```python
from abc import ABC, abstractmethod
from core.contracts import AlphaSignal


class SignalScorer(ABC):
    """信号评分基类"""
    
    @abstractmethod
    def score(self, signal: AlphaSignal, **kwargs) -> float:
        """对信号进行评分
        
        Args:
            signal: AlphaSignal 对象
            **kwargs: 额外参数
            
        Returns:
            float: 评分，范围 [0.0, 1.0]
        """
        pass
```

### 实现自定义 Scorer

```python
from core.contracts import AlphaSignal
from signal_lab.scoring.scorer import SignalScorer


class ConfidenceScorer(SignalScorer):
    """基于置信度的评分器"""
    
    def score(self, signal: AlphaSignal, **kwargs) -> float:
        """返回信号的置信度作为评分"""
        if signal.confidence is not None:
            return signal.confidence
        return 0.5  # 默认值
```

### CompositeScorer 使用

```python
from signal_lab.scoring import CompositeScorer, ConfidenceScorer, StrengthScorer


# 创建组合评分器
scorer = CompositeScorer(
    scorers=[ConfidenceScorer(), StrengthScorer()],
    weights=[0.5, 0.5]
)

# 评分
score = scorer.score(signal)
```

---

## 回测开发规范

### BacktestResult 数据类

```python
from dataclasses import dataclass
import pandas as pd
from typing import Dict, Any


@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float = 0.0
    annual_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    returns: pd.Series = pd.Series()
    positions: pd.Series = pd.Series()
    equity_curve: pd.Series = pd.Series()
    metadata: Dict[str, Any] = None
```

### 简单回测使用

```python
from signal_lab.backtests import SimpleBacktester
from core.contracts import AlphaSignal


# 创建回测器
backtester = SimpleBacktester(
    initial_capital=1000000,
    position_size=0.1
)

# 运行回测
signals = [signal1, signal2, signal3]
result = backtester.run(price_data, signals)

# 查看结果
print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2%}")
```

---

## Signal Lab 检查清单

开发新特征/标签/评分器时确认：
- [ ] 继承正确的基类
- [ ] 实现所有抽象方法
- [ ] 包含 docstring 和描述
- [ ] 处理边界情况（空数据、NaN）
- [ ] 添加对应的单元测试
- [ ] 在 __init__.py 中导出
- [ ] 添加使用示例

