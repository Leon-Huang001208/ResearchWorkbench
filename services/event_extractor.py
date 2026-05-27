"""事件提取器 - 从文本中提取结构化事件信号参数。

仅使用 ModelGateway (LLM) 进行深度提取，LLM 不可用时返回空结果。
"""
from __future__ import annotations

import asyncio
import json

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


class EventExtractor:
    """从文本中提取事件信号参数。"""

    LLM_TIMEOUT_SEC = 120  # LLM 调用最大等待时间
    FALLBACK_MODEL = "deepseek-v4-pro"

    def __init__(self, model_gateway: ModelGateway | None = None):
        self._gateway = model_gateway
        logger.info(
            "EventExtractor initialized",
            llm_available=model_gateway is not None,
        )

    async def extract(self, text: str) -> ExtractedSignalParams:
        """从文本中提取信号参数。仅使用 LLM，LLM 不可用时返回空结果。"""
        if not text or not text.strip():
            logger.warning("Empty text provided to EventExtractor")
            return ExtractedSignalParams()

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
                logger.error(
                    "LLM extraction failed after retry, returning empty result",
                    error=str(exc),
                )

        logger.warning("No LLM available or extraction failed, returning empty result")
        return ExtractedSignalParams()

    async def _call_llm(self, messages, model=None):
        """调用 LLM，可指定模型。"""
        return await asyncio.wait_for(
            asyncio.to_thread(
                self._gateway.chat,
                messages=messages,
                model=model,
                temperature=0.1,
                max_tokens=4096,
                task="extraction" if model is None else None,
            ),
            timeout=self.LLM_TIMEOUT_SEC,
        )

    async def _extract_via_llm(self, text: str) -> ExtractedSignalParams | None:
        """使用 LLM 提取事件信号参数，flash 失败则用 pro 重试。"""
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

        try:
            response = await self._call_llm(messages)
            return self._parse_llm_response(response.content)
        except Exception:
            logger.warning(
                "Primary extraction model failed, retrying with fallback model",
                fallback_model=self.FALLBACK_MODEL,
            )
            response = await self._call_llm(messages, model=self.FALLBACK_MODEL)
            return self._parse_llm_response(response.content)

    @staticmethod
    def _parse_llm_response(content: str) -> ExtractedSignalParams:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)

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
