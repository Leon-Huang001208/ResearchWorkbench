from types import SimpleNamespace

from core.model_gateway.providers.openai_compatible import OpenAICompatibleProvider


def test_chat_does_not_promote_reasoning_content_to_final_answer():
    message = SimpleNamespace(
        content=None,
        reasoning_content="这是模型的内部分析过程，不是最终答案。",
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(total_tokens=42),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: response),
        )
    )
    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider._provider_name = "deepseek"
    provider._client = client

    result = provider.chat(messages=[{"role": "user", "content": "生成正文"}])

    assert result.content.startswith("Error:")
    assert "内部分析过程" not in result.content
