"""structured_output 工具单元测试.

验证 Pydantic schema → OpenAI strict JSON Schema 转换、Anthropic tool schema
转换、以及 retry_structured_parse 的重试与兜底逻辑。

对应 deep-research-report.md 第一阶段 structured_output 改造。
"""

import json
from typing import List, Optional

import pytest
from pydantic import BaseModel

from core.model_gateway.structured_output_utils import (
    _dereference,
    _enforce_strict,
    parse_json_content,
    pydantic_to_anthropic_tool_schema,
    pydantic_to_openai_json_schema,
    retry_structured_parse,
)


class Inner(BaseModel):
    x: int
    y: Optional[float] = None


class Outer(BaseModel):
    name: str
    items: List[Inner]
    note: Optional[str] = None


class _FakeResponse:
    """模拟 ModelResponse，只含 content 字段."""

    def __init__(self, content: str):
        self.content = content


class TestOpenAiJsonSchema:
    """OpenAI strict mode schema 转换测试."""

    def test_dereference_expands_refs(self):
        raw = Outer.model_json_schema()
        defs = raw.get("$defs", {})
        deref = _dereference(raw, defs)
        # items.items 应被展开为 Inner 的完整 schema，不再含 $ref
        items_schema = deref["properties"]["items"]["items"]
        assert "$ref" not in items_schema
        assert items_schema["type"] == "object"
        assert "x" in items_schema["properties"]

    def test_enforce_strict_injects_additional_properties_false(self):
        raw = Outer.model_json_schema()
        defs = raw.get("$defs", {})
        deref = _dereference(raw, defs)
        strict = _enforce_strict(deref)
        # 顶层 object
        assert strict["additionalProperties"] is False
        # 嵌套 Inner object 也注入
        inner = strict["properties"]["items"]["items"]
        assert inner["additionalProperties"] is False

    def test_full_schema_has_no_refs(self):
        schema = pydantic_to_openai_json_schema(Outer)
        dumped = json.dumps(schema)
        assert "$ref" not in dumped
        assert schema["additionalProperties"] is False

    def test_anyof_for_optional_handled(self):
        schema = pydantic_to_openai_json_schema(Outer)
        note_schema = schema["properties"]["note"]
        assert "anyOf" in note_schema
        # anyOf 子 schema 递归处理
        assert all("type" in s for s in note_schema["anyOf"])


class TestAnthropicToolSchema:
    """Anthropic tool schema 转换测试."""

    def test_tool_definition_structure(self):
        tool = pydantic_to_anthropic_tool_schema(Outer, description="test tool")
        assert tool["name"] == "structured_output"
        assert tool["description"] == "test tool"
        assert "input_schema" in tool
        # input_schema 是 Pydantic 原生 JSON Schema，含 $defs
        assert "$defs" in tool["input_schema"]

    def test_custom_tool_name(self):
        tool = pydantic_to_anthropic_tool_schema(Outer, tool_name="my_tool")
        assert tool["name"] == "my_tool"


class TestParseJsonContent:
    """JSON 解析容错测试."""

    def test_plain_json(self):
        assert parse_json_content('{"a": 1}') == {"a": 1}

    def test_json_with_code_fence(self):
        assert parse_json_content('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_with_bare_fence(self):
        assert parse_json_content('```\n{"a": 1}\n```') == {"a": 1}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_content("not json at all")


class _SimpleModel(BaseModel):
    name: str
    value: int


class TestRetryStructuredParse:
    """重试与兜底逻辑测试."""

    def test_succeeds_on_first_try(self):
        calls = {"n": 0}

        def chat_fn(messages, **kw):
            calls["n"] += 1
            return _FakeResponse('{"name": "a", "value": 1}')

        result = retry_structured_parse(chat_fn, [{"role": "user", "content": "hi"}], _SimpleModel)
        assert result.name == "a"
        assert result.value == 1
        assert calls["n"] == 1

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        def chat_fn(messages, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return _FakeResponse("not json")
            return _FakeResponse('{"name": "b", "value": 2}')

        result = retry_structured_parse(
            chat_fn, [{"role": "user", "content": "hi"}], _SimpleModel, max_retries=2
        )
        assert result.name == "b"
        assert calls["n"] == 2

    def test_all_retries_fail_returns_empty_construct(self):
        def chat_fn(messages, **kw):
            return _FakeResponse("still not json")

        result = retry_structured_parse(
            chat_fn, [{"role": "user", "content": "hi"}], _SimpleModel, max_retries=1
        )
        # 返回空对象（model_construct），不抛异常
        assert isinstance(result, _SimpleModel)

    def test_appends_correction_message_on_retry(self):
        captured_messages = []

        def chat_fn(messages, **kw):
            captured_messages.append(list(messages))
            return _FakeResponse("not json")

        retry_structured_parse(
            chat_fn, [{"role": "user", "content": "hi"}], _SimpleModel, max_retries=1
        )
        # 第二次调用应追加了 assistant + user 纠正消息
        assert len(captured_messages) == 2
        assert len(captured_messages[1]) > len(captured_messages[0])
        # 最后一条是纠正提示
        assert (
            "schema" in captured_messages[1][-1]["content"].lower()
            or "json" in captured_messages[1][-1]["content"].lower()
        )
