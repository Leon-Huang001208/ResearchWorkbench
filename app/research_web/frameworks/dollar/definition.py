"""Immutable Q-P-g-M-X dollar liquidity method definition."""

from ..base import FrameworkDefinition

DEFINITION = FrameworkDefinition.model_validate(
    {
        "slug": "dollar",
        "name": "美元流动性研究框架",
        "domain": "macro-liquidity",
        "version": "1.0.0",
        "source_revision": "2c210b45577905c0e8ec5f9c061e7069a6cb3b96",
        "question": "美元流动性当前由总量、资金价格、财政水流、融资管道与跨境需求中的哪一环主导？",
        "chain": ["Q 总量", "P 价格", "g 财政", "M 管道", "X 跨境", "资产传导"],
        "counter_evidence": [
            "净流动性代理改善但准备金继续收缩",
            "政策利率稳定但 SOFR−IORB 与融资失败同步恶化",
            "美国境内偏松但广义美元与海外融资压力走强",
        ],
        "sections": [
            {"id": "overview", "label": "总览", "question": "当前偏松、偏紧还是仍需核验？"},
            {
                "id": "quantity",
                "label": "Q 总量水库",
                "question": "联储资产、准备金和逆回购如何改变可用水位？",
            },
            {
                "id": "price",
                "label": "P 资金价格",
                "question": "政策路径、曲线和实际利率如何定价资金？",
            },
            {
                "id": "fiscal",
                "label": "g 财政水流",
                "question": "TGA、发行和结算正在注入还是抽走流动性？",
            },
            {"id": "plumbing", "label": "M 融资管道", "question": "回购、交易商与交割链是否顺畅？"},
            {
                "id": "cross-border",
                "label": "X 跨境美元",
                "question": "美元、汇率与海外官方需求是否放大压力？",
            },
            {
                "id": "evidence",
                "label": "传导与证据",
                "question": "流动性如何传导到资产，哪些缺口仍未解决？",
            },
        ],
        "method": (
            "分别计算Q、P、g、M、X五个标准化信号后等权合成；均值高于0.15为偏松，"
            "低于-0.15为偏紧，其余为中性。WALCL减TGA减ON RRP仅作为净流动性代理，"
            "不是会计恒等式；任一维度不可计算时只显示已知小计与可能区间并标记待核验。"
        ),
    }
)
