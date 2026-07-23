"""
LLM 相关 API 路由
"""

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/llm", tags=["llm"])


class LlmGenerateRequest(BaseModel):
    """LLM生成请求"""

    prompt: str
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(2000, ge=1, le=8000)
    model: str = "gpt-4o-mini"


class LlmGenerateResponse(BaseModel):
    """LLM生成响应"""

    success: bool
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None


class LlmAskRequest(BaseModel):
    """联网问答请求"""

    question: str
    max_results: int = Field(5, ge=1, le=10)
    fetch_content: bool = True
    temperature: float = Field(0.3, ge=0.0, le=1.0)


class LlmAskSource(BaseModel):
    """联网问答来源"""

    title: str
    url: str
    snippet: str = ""
    source: str = ""


class LlmAskResponse(BaseModel):
    """联网问答响应"""

    success: bool
    answer: str
    online: bool
    model: str = ""
    sources: list[LlmAskSource] = []


@router.post("/generate", response_model=LlmGenerateResponse, summary="LLM文本生成")
async def llm_generate(request: LlmGenerateRequest):
    """
    使用LLM生成文本内容
    """
    try:
        import os

        from openai import OpenAI

        # 从环境变量获取API密钥
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not api_key:
            # 如果没有配置API密钥，返回模拟数据
            logger.warning("OPENAI_API_KEY not configured, returning mock content")
            mock_content = f"""
这是模拟生成的内容，基于您的提示词：
{request.prompt[:100]}...

如果需要真实生成内容，请在环境变量中配置OPENAI_API_KEY。
            """.strip()
            return LlmGenerateResponse(
                success=True,
                content=mock_content,
                model=request.model,
                usage={
                    "prompt_tokens": 0,
                    "completion_tokens": len(mock_content),
                    "total_tokens": len(mock_content),
                },
            )

        # 初始化OpenAI客户端
        client = OpenAI(api_key=api_key, base_url=base_url)

        # 调用API
        response = client.chat.completions.create(
            model=request.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的金融分析师，擅长撰写券商研究报告。输出内容要专业、严谨，符合A股市场的实际情况。",
                },
                {"role": "user", "content": request.prompt},
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        content = (response.choices[0].message.content or "").strip()

        return LlmGenerateResponse(
            success=True,
            content=content,
            model=response.model,
            usage=(
                {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                if response.usage
                else None
            ),
        )

    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="OpenAI library not installed. Please install it with: pip install openai",
        )
    except Exception as e:
        logger.exception("Failed to generate LLM content")
        raise HTTPException(status_code=500, detail=f"Failed to generate content: {str(e)}")


@router.post("/ask", response_model=LlmAskResponse, summary="联网查询后回答")
async def llm_ask(request: LlmAskRequest):
    """
    联网查询后回答问题（始终先联网再综合）。

    无论内部是否有资料，每次提问都先联网搜索，将结果注入 prompt 后生成带引用的答案。
    未配置搜索 API key 时降级为不联网直答。
    """
    try:
        from services.ask_factory import build_ask_service

        service = build_ask_service()
        result = service.ask(
            request.question,
            max_results=request.max_results,
            fetch_content=request.fetch_content,
            temperature=request.temperature,
        )
        sources = [
            LlmAskSource(title=s.title, url=s.url, snippet=s.snippet, source=s.source)
            for s in result.sources
        ]
        return LlmAskResponse(
            success=True,
            answer=result.answer,
            online=result.online,
            model=result.model,
            sources=sources,
        )
    except Exception as e:
        logger.exception("Failed to answer with web search")
        raise HTTPException(status_code=500, detail=f"Failed to answer: {str(e)}")
