"""
Ask service：提问优先联网查询的统一问答内核.

流程：联网搜索 → 格式化为参考资料 → 注入 LLM prompt → 生成带引用的答案。
无论内部有无资料，每次提问都先联网（符合"始终先联网再综合"语义）。
无 API key 时降级为不联网直答，并在答案前标注"[未联网]"。
"""

from typing import Any

from pydantic import BaseModel, Field

from core.interfaces import ModelGateway, WebSearchResult
from core.observability import get_logger
from services.web_search_service import WebSearchService

logger = get_logger(__name__)

# 系统提示词：要求基于参考资料回答、标注引用、未查到时如实说明
_ASK_SYSTEM_PROMPT = (
    "你是一个严谨的投研助理。请基于下方【参考资料】回答用户问题。"
    "在用到某条资料的句子末尾标注对应编号，如 [1]、[2]。"
    "若参考资料不足以回答，请如实说明「未在联网资料中找到相关内容」，"
    "不要编造。回答应专业、简洁、贴合 A 股投研场景。"
)


class AskResult(BaseModel):
    """问答结果."""

    answer: str = Field(description="模型生成的答案（带引用）")
    sources: list[WebSearchResult] = Field(default_factory=list, description="引用的搜索结果")
    online: bool = Field(description="是否实际联网")
    model: str = Field(default="", description="使用的模型名")


class AskService:
    """统一问答内核：联网搜索 + LLM 生成."""

    def __init__(
        self,
        model_gateway: ModelGateway,
        web_search: WebSearchService,
    ) -> None:
        self._model_gateway = model_gateway
        self._web_search = web_search

    def ask(
        self,
        question: str,
        *,
        max_results: int = 5,
        temperature: float = 0.3,
        task: str = "default",
        fetch_content: bool | None = None,
        **kwargs: Any,
    ) -> AskResult:
        """提问并获取带引用的答案.

        Args:
            question: 用户问题.
            max_results: 联网搜索最大结果数.
            temperature: 生成温度.
            task: ModelGateway 任务路由键.
            fetch_content: 是否补抓网页正文，None 用 WebSearchService 默认.
            **kwargs: 透传给 ModelGateway.chat 的额外参数.

        Returns:
            AskResult，含答案、来源、是否联网。
        """
        logger.info("ask request", question=question[:80], max_results=max_results)

        # 1. 始终先联网搜索
        results = self._web_search.search(
            question, max_results=max_results, fetch_content=fetch_content
        )
        online = len(results) > 0

        # 2. 组装 prompt
        context = self._web_search.format_for_prompt(results)
        if online:
            user_content = f"【参考资料】\n{context}\n\n【问题】\n{question}"
        else:
            # 降级：无 key 或搜索失败，不联网直答并标注
            user_content = (
                "[未联网] 未能获取联网搜索结果（可能未配置搜索 API key 或搜索失败），" f"以下基于模型自身知识回答，可能过时：\n\n【问题】\n{question}"
            )

        messages = [
            {"role": "system", "content": _ASK_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # 3. 调 ModelGateway 生成
        try:
            resp = self._model_gateway.chat(
                messages,
                temperature=temperature,
                task=task,
                **kwargs,
            )
            answer = resp.content
            model_name = resp.model_name
        except Exception as e:
            logger.error("ask model call failed", error=str(e))
            return AskResult(
                answer=f"生成答案失败：{e}",
                sources=results,
                online=online,
                model="",
            )

        logger.info(
            "ask complete",
            online=online,
            source_count=len(results),
            model=model_name,
        )
        return AskResult(answer=answer, sources=results, online=online, model=model_name)
