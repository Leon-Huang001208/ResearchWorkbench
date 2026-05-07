
"""择时模型基类和共享上下文。"""
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from timing_engine.contracts import TimingModelName, TimingModelScore, MarketRegime


class TimingContext(BaseModel):
    """择时模型的共享输入上下文。"""
    signal_id: str | None = None
    market_regime: MarketRegime = "unknown"
    # 市场数据
    price_data: dict = Field(default_factory=dict)       # 量价数据快照
    flow_data: dict = Field(default_factory=dict)         # 资金流数据
    sentiment_data: dict = Field(default_factory=dict)    # 情绪指标
    macro_data: dict = Field(default_factory=dict)        # 宏观数据
    # 黑板观点
    agent_views: list[dict] = Field(default_factory=list)  # 从黑板获取的 AgentView
    # 事件信号
    event_signal: dict | None = None                       # EventAlphaSignal 的 dict 表示
    # 产业链
    diffusion_data: dict = Field(default_factory=dict)     # 主题传播数据


class BaseTimingModel(ABC):
    """择时模型抽象基类。"""
    model_name: TimingModelName  # 对应 contracts 中的 9 个模型名
    
    @abstractmethod
    def score(self, context: TimingContext) -> TimingModelScore:
        """根据市场上下文计算择时评分。"""
        pass

