"""事件提取器 - 从文本中提取结构化事件信号参数。

优先使用 ModelGateway (LLM) 进行深度提取；
若 LLM 不可用，回退到基于关键词的简单提取。
"""
from __future__ import annotations

import asyncio
import json
import re

from pydantic import BaseModel, Field

from core.interfaces import ModelGateway
from core.observability import get_logger

logger = get_logger(__name__)


class ExtractedSignalParams(BaseModel):
    """从文本中提取的信号参数。"""

    event_type: str = "unknown"
    subject_ids: list[str] = Field(default_factory=list)
    thesis: str = ""
    impact_path: list[str] = Field(default_factory=list)
    bullish_companies: list[str] = Field(default_factory=list)
    bearish_companies: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    diffusion_stage: str = "unknown"
    industry_impacts: list[str] = Field(default_factory=list)
    market_regime: str | None = None


# ── A 股公司代码模式 ──────────────────────────────────
_A_SHARE_PATTERN = re.compile(r"\b(\d{6})\.(SH|SZ)\b", re.IGNORECASE)

# ── 事件类型关键词字典 ────────────────────────────────
_EVENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "earnings": [
        "业绩",
        "营收",
        "净利润",
        "一季报",
        "中报",
        "三季报",
        "年报",
        "财报",
        "盈利",
        "亏损",
        "扭亏",
        "增收",
    ],
    "policy": [
        "政策",
        "法规",
        "监管",
        "批复",
        "补贴",
        "减税",
        "新规",
        "国务院",
        "发改委",
        "证监会",
        "银保监",
        "降准",
        "降息",
    ],
    "product": [
        "发布",
        "上市",
        "量产",
        "获批",
        "新品",
        "投产",
        "突破",
        "技术突破",
        "研发",
    ],
    "merger_acquisition": [
        "收购",
        "并购",
        "重组",
        "合并",
        "分拆",
        "借壳",
    ],
    "rating_change": [
        "上调",
        "下调",
        "增持",
        "减持",
        "买入",
        "卖出",
        "评级",
        "目标价",
        "券商",
    ],
    "supply_chain": [
        "供应",
        "断供",
        "缺货",
        "涨价",
        "降价",
        "产能",
        "库存",
    ],
    "macro": [
        "GDP",
        "CPI",
        "PMI",
        "利率",
        "汇率",
        "通胀",
        "通缩",
        "降息",
        "加息",
        "社融",
    ],
}

# ── 行业关键词 ─────────────────────────────────────
_INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "semiconductor": ["芯片", "半导体", "光刻", "EDA", "晶圆", "封测"],
    "new_energy": ["新能源", "光伏", "风电", "储能", "锂电", "充电桩"],
    "ai": ["人工智能", "AI", "大模型", "算力", "GPU", "智能"],
    "pharmaceutical": ["医药", "创新药", "仿制药", "CRO", "医疗器械"],
    "consumer": ["消费", "白酒", "乳制品", "零售", "品牌"],
    "finance": ["银行", "保险", "券商", "信托", "金融"],
    "real_estate": ["房地产", "地产", "房价", "土地"],
    "auto": ["汽车", "新能源车", "智能驾驶", "整车"],
}

# ── 影响方向关键词 ──────────────────────────────────
_BULLISH_KEYWORDS = [
    "利好",
    "增长",
    "上涨",
    "突破",
    "超预期",
    "新高",
    "获批",
    "放量",
    "强势",
    "增持",
    "上调",
]
_BEARISH_KEYWORDS = [
    "利空",
    "下跌",
    "下滑",
    "不及预期",
    "亏损",
    "暴雷",
    "减持",
    "下调",
    "退市",
    "违规",
]


class EventExtractor:
    """从文本中提取事件信号参数。"""

    def __init__(self, model_gateway: ModelGateway | None = None):
        self._gateway = model_gateway
        logger.info(
            "EventExtractor initialized",
            llm_available=model_gateway is not None,
        )

    async def extract(self, text: str) -> ExtractedSignalParams:
        """从文本中提取信号参数。

        优先使用 LLM，失败则回退到关键词提取。
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to EventExtractor")
            return ExtractedSignalParams()

        # 尝试 LLM 提取
        if self._gateway is not None:
            try:
                result = await self._extract_via_llm(text)
                if result is not None:
                    logger.info(
                        "LLM event extraction succeeded",
                        event_type=result.event_type,
                        subject_count=len(result.subject_ids),
                    )
                    return result
            except Exception as exc:
                logger.warning(
                    "LLM extraction failed, falling back to keyword extraction",
                    error=str(exc),
                )

        # 回退到关键词提取
        result = self._extract_via_keywords(text)
        logger.info(
            "Keyword event extraction completed",
            event_type=result.event_type,
            subject_count=len(result.subject_ids),
        )
        return result

    async def _extract_via_llm(self, text: str) -> ExtractedSignalParams | None:
        """使用 LLM 提取事件信号参数。"""
        system_prompt = (
            "你是一个专业的 A 股事件分析引擎。请从以下文本中提取结构化的事件信号参数。\n"
            "你必须返回 JSON 格式，包含以下字段：\n"
            "- event_type: 事件类型 (earnings/policy/product/merger_acquisition/"
            "rating_change/supply_chain/macro/other)\n"
            "- subject_ids: 相关 A 股主体代码列表 (如 600000.SH)\n"
            "- thesis: 研究论点 (一句话总结该事件的投资逻辑)\n"
            "- impact_path: 影响路径 (从事件到股价的传导链条, 字符串数组)\n"
            "- bullish_companies: 利好公司代码列表 (字符串数组)\n"
            "- bearish_companies: 利空公司代码列表 (字符串数组)\n"
            "- score: 投资机会评分 (浮点数 0.0-1.0)\n"
            "- confidence: 置信度 (浮点数 0.0-1.0)\n"
            "- diffusion_stage: 主题扩散阶段 (discovery/early_awareness/"
            "theme_trading/institutional_coverage/consensus/decay/unknown)\n"
            "- industry_impacts: 受影响行业列表 (字符串数组)\n"
            "- market_regime: 当前市场环境 (ai_growth/dividend_defensive/"
            "risk_off/hot_money_theme/institutional_trend/"
            "liquidity_bull/bear_rebound/unknown)\n\n"
            "所有数组字段都必须返回 JSON 数组格式，即使只有一个元素。\n"
            "只返回 JSON，不要包含其他文字。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text[:2000]},  # 截断过长文本
        ]

        response = await asyncio.to_thread(
            self._gateway.chat,
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            task="extraction",
        )

        content = response.content.strip()
        # 清理 markdown 代码块标记
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)

        # 验证并构造 ExtractedSignalParams
        def _ensure_list(value):
            """Ensure value is a list; wrap single string in list, return [] for None."""
            if value is None:
                return []
            if isinstance(value, str):
                return [value] if value.strip() else []
            if isinstance(value, list):
                return value
            return []

        return ExtractedSignalParams(
            event_type=data.get("event_type", "unknown"),
            subject_ids=_ensure_list(data.get("subject_ids")),
            thesis=data.get("thesis", ""),
            impact_path=_ensure_list(data.get("impact_path")),
            bullish_companies=_ensure_list(data.get("bullish_companies")),
            bearish_companies=_ensure_list(data.get("bearish_companies")),
            score=max(0.0, min(1.0, float(data.get("score", 0.5)))),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            diffusion_stage=data.get("diffusion_stage", "unknown"),
            industry_impacts=_ensure_list(data.get("industry_impacts")),
            market_regime=data.get("market_regime"),
        )

    def _extract_via_keywords(self, text: str) -> ExtractedSignalParams:
        """基于关键词的简单提取（LLM 不可用时的 fallback）。"""
        # 1. 提取 A 股代码
        subject_ids = [m.group(0).upper() for m in _A_SHARE_PATTERN.finditer(text)]

        # 2. 判断事件类型
        event_type = "other"
        max_hits = 0
        for etype, keywords in _EVENT_TYPE_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > max_hits:
                max_hits = hits
                event_type = etype

        # 3. 判断影响行业
        industry_impacts = []
        for industry, keywords in _INDUSTRY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                industry_impacts.append(industry)

        # 4. 判断多空方向
        bullish_count = sum(1 for kw in _BULLISH_KEYWORDS if kw in text)
        bearish_count = sum(1 for kw in _BEARISH_KEYWORDS if kw in text)

        # 5. 计算分数
        if bullish_count + bearish_count > 0:
            raw_score = bullish_count / (bullish_count + bearish_count)
            # 映射到 0.3-0.8 区间（保守估计）
            score = 0.3 + raw_score * 0.5
        else:
            score = 0.5

        # 6. 置信度基于信息丰富程度
        confidence = 0.4
        if subject_ids:
            confidence += 0.1
        if event_type != "other":
            confidence += 0.1
        if industry_impacts:
            confidence += 0.1
        confidence = min(0.8, confidence)

        # 7. 生成简单论点
        thesis = f"基于{event_type}类事件的文本分析"
        if subject_ids:
            thesis += f"，涉及主体：{'、'.join(subject_ids[:3])}"
        if bullish_count > bearish_count:
            thesis += "，整体偏利好"
        elif bearish_count > bullish_count:
            thesis += "，整体偏利空"

        # 8. 构建影响路径
        impact_path = []
        if event_type != "other":
            impact_path.append(f"事件类型: {event_type}")
        if industry_impacts:
            impact_path.append(f"影响行业: {', '.join(industry_impacts)}")

        return ExtractedSignalParams(
            event_type=event_type,
            subject_ids=subject_ids,
            thesis=thesis,
            impact_path=impact_path,
            bullish_companies=[],
            bearish_companies=[],
            score=score,
            confidence=confidence,
            diffusion_stage="unknown",
            industry_impacts=industry_impacts,
            market_regime=None,
        )
