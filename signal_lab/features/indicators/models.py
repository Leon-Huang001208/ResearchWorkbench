from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class TechnicalIndicators:
    """技术指标计算结果"""

    symbol: str
    date: str  # 计算日期

    # 趋势指标
    ma: Optional[Dict[str, Optional[float]]] = (
        None  # {"ma5": 1393.83, "ma10": ..., "ma20": ..., "ma60": ...}
    )
    ema: Optional[Dict[str, Optional[float]]] = None  # {"ema12": ..., "ema26": ...}
    macd: Optional[Dict[str, Optional[float]]] = None  # {"dif": ..., "dea": ..., "macd_bar": ...}
    sar: Optional[float] = None
    dmi: Optional[Dict[str, Optional[float]]] = (
        None  # {"plus_di": ..., "minus_di": ..., "adx": ...}
    )
    trix: Optional[float] = None

    # 动量指标
    rsi: Optional[Dict[str, Optional[float]]] = None  # {"rsi6": ..., "rsi14": ...}
    kdj: Optional[Dict[str, Optional[float]]] = None  # {"k": ..., "d": ..., "j": ...}
    wr: Optional[float] = None
    cci: Optional[float] = None
    roc: Optional[float] = None

    # 波动指标
    boll: Optional[Dict[str, Optional[float]]] = None  # {"upper": ..., "middle": ..., "lower": ...}
    atr: Optional[float] = None

    # 成交量指标
    obv: Optional[float] = None
    vwap: Optional[float] = None

    # 元数据
    provider: str = "unknown"  # 用了哪个provider: "talib" / "pandas_ta" / "builtin"
