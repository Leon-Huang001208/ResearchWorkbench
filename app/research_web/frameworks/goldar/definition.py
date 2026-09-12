"""Immutable Goldar research method definition."""

from ..base import FrameworkDefinition

DEFINITION = FrameworkDefinition.model_validate(
    {
        "slug": "gold",
        "name": "黄金研究框架",
        "domain": "commodity",
        "version": "1.0.0",
        "source_revision": "758ae3848d",
        "question": "黄金当前由哪组实际利率、美元、避险需求与实物资金力量共同定价？",
        "chain": ["宏观状态", "定价驱动", "供需与资金", "持仓与期权", "情景与配置"],
        "counter_evidence": [
            "实际利率与美元同时转强",
            "ETF 与央行资金共同转弱",
            "价格强势但持仓和期权结构不确认",
        ],
        "sections": [
            {"id": "overview", "label": "总览", "question": "当前结论、置信度与下一项验证是什么？"},
            {
                "id": "drivers",
                "label": "定价驱动",
                "question": "实际利率、美元、通胀与波动各贡献多少？",
            },
            {"id": "supply", "label": "供需与资金", "question": "实物需求与资金流是否确认价格？"},
            {"id": "cycle", "label": "周期与宏观", "question": "当前处于哪类政策和增长通胀组合？"},
            {
                "id": "positioning",
                "label": "持仓与期权",
                "question": "拥挤度与期权压力是否构成反证？",
            },
            {
                "id": "allocation",
                "label": "情景与配置",
                "question": "黄金在不同冲击下提供何种分散化？",
            },
            {
                "id": "evidence",
                "label": "事件与证据",
                "question": "哪些证据已确认，哪些数据仍有缺口？",
            },
        ],
        "method": (
            "先用确定性指标形成因子贡献，再按支持、拖累、反证和数据缺口解释状态。"
            "任一关键输入缺失、过期或口径冲突时，状态降级为待核验。"
        ),
    }
)
