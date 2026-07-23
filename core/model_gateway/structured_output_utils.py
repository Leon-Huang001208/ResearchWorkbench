"""
结构化输出工具 - 让 model_gateway 的 structured_output 可靠化.

背景：原有两个 provider 的 structured_output 都是"prompt 注入 + 手动 json.loads"，
解析失败直接返回 model_construct() 空对象。报告编译器依赖严格 JSON Schema 约束
（大纲、事实抽取、引用绑定），必须保证结构化输出可靠。

本模块提供三类能力：
1. pydantic_to_openai_json_schema: 转 OpenAI strict mode 兼容 schema
   （展开 $ref、注入 additionalProperties:false、处理 union/optional）。
2. pydantic_to_anthropic_tool_schema: 转 Anthropic tool input_schema。
3. retry_structured_parse: 通用"调用→解析→失败重试"循环，支持多级回退。

设计依据：deep-research-report.md 第一阶段 structured_output 改造要求。
"""

import json
from typing import Any, Callable, Type, TypeVar

from pydantic import BaseModel

from core.observability import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# OpenAI strict mode 要求的额外字段键
_ADDITIONAL_PROPS_FALSE = {"additionalProperties": False}


def _dereference(schema: Any, defs: dict[str, Any]) -> Any:
    """递归展开 JSON Schema 中的 $ref.

    OpenAI strict mode 不支持 $ref，必须把定义内联展开。
    """
    if isinstance(schema, dict):
        # 处理 $ref
        if "$ref" in schema:
            ref_path = schema["$ref"]
            # 形如 "#/$defs/SomeModel" 或 "#/$defs/A/properties/B"
            # 去掉前导 #/ 后按 / 切分，跳过 "$defs" 段，在 defs dict 内逐级取值
            parts = [p for p in ref_path.lstrip("#").lstrip("/").split("/") if p]
            # 跳过 "$defs" 这一段，从实际定义键开始
            if parts and parts[0] == "$defs":
                parts = parts[1:]
            target: Any = defs
            found = True
            for part in parts:
                if isinstance(target, dict) and part in target:
                    target = target[part]
                else:
                    found = False
                    break
            if not found:
                # 找不到引用目标，返回原 schema 去掉 $ref
                return {k: v for k, v in schema.items() if k != "$ref"}
            # 递归展开目标（目标可能自身含 $ref），合并其余键
            merged = dict(_dereference(target, defs))
            for k, v in schema.items():
                if k != "$ref":
                    merged[k] = v
            return merged
        # 递归处理所有子节点
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "$defs":
                # $defs 在 strict mode 下需保留但内部也要展开
                result[key] = {k: _dereference(v, defs) for k, v in value.items()}
            else:
                result[key] = _dereference(value, defs)
        return result
    if isinstance(schema, list):
        return [_dereference(item, defs) for item in schema]
    return schema


def _enforce_strict(schema: Any) -> Any:
    """注入 OpenAI strict mode 要求的约束.

    - 每个 object 类型注入 additionalProperties: false
    - 处理 anyOf（optional 字段会被 pydantic 编为 anyOf[type, null]）
    """
    if isinstance(schema, dict):
        # anyOf 分支：对每个非 null 子 schema 递归注入
        if "anyOf" in schema:
            schema["anyOf"] = [_enforce_strict(s) for s in schema["anyOf"]]
        # 处理 properties + type=object
        if schema.get("type") == "object" and "properties" in schema:
            schema["additionalProperties"] = False
            schema["properties"] = {k: _enforce_strict(v) for k, v in schema["properties"].items()}
        # 处理 array items
        if schema.get("type") == "array" and "items" in schema:
            schema["items"] = _enforce_strict(schema["items"])
        # 处理 $defs 内部
        if "$defs" in schema:
            schema["$defs"] = {k: _enforce_strict(v) for k, v in schema["$defs"].items()}
        return schema
    return schema


def _strip_title_recursively(schema: Any) -> Any:
    """OpenAI strict mode 不允许 properties 内的子 schema 带 title.

    为稳妥起见，移除所有非顶层 title（保留顶层 schema 的 title 不影响）。
    """
    if isinstance(schema, dict):
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "title":
                # 跳过 title 字段（strict mode 对嵌套 title 敏感）
                continue
            result[key] = _strip_title_recursively(value)
        return result
    if isinstance(schema, list):
        return [_strip_title_recursively(item) for item in schema]
    return schema


def pydantic_to_openai_json_schema(schema: Type[BaseModel]) -> dict[str, Any]:
    """将 Pydantic 模型转为 OpenAI strict mode 兼容的 JSON Schema.

    OpenAI strict mode 要求：
    - 所有 $ref 必须展开（不支持引用）
    - 每个 object 必须 additionalProperties: false
    - 不能有嵌套 title（部分端点要求）

    Args:
        schema: Pydantic BaseModel 子类

    Returns:
        兼容 OpenAI response_format json_schema 的 schema dict
    """
    raw = schema.model_json_schema()
    defs = raw.get("$defs", {})
    deref = _dereference(raw, defs)
    # 移除顶层 $defs（已展开）和 title
    if "$defs" in deref:
        # 保留 $defs 但 strict mode 实际不使用；为干净起见移除
        deref.pop("$defs", None)
    strict = _enforce_strict(deref)
    strict = _strip_title_recursively(strict)
    return strict


def pydantic_to_anthropic_tool_schema(
    schema: Type[BaseModel],
    tool_name: str = "structured_output",
    description: str = "Return the structured output.",
) -> dict[str, Any]:
    """将 Pydantic 模型转为 Anthropic tool use 的 tool definition.

    Anthropic tool use 通过 tools=[...] + tool_choice 强制模型返回结构化输入，
    比 prompt 注入更可靠。input_schema 支持 $ref（Anthropic 原生支持），无需展开。

    Args:
        schema: Pydantic BaseModel 子类
        tool_name: tool 名称
        description: tool 描述

    Returns:
        Anthropic tool definition dict
    """
    return {
        "name": tool_name,
        "description": description,
        "input_schema": schema.model_json_schema(),
    }


def _strip_json_fences(content: str) -> str:
    """去除模型输出常见的 markdown json 代码围栏."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def parse_json_content(content: str) -> Any:
    """解析模型输出为 JSON，去除围栏后容错.

    Args:
        content: 模型原始输出文本

    Returns:
        解析后的 Python 对象

    Raises:
        json.JSONDecodeError: 解析失败
    """
    cleaned = _strip_json_fences(content)
    return json.loads(cleaned)


def retry_structured_parse(
    chat_fn: Callable[..., Any],
    messages: list[dict[str, str]],
    output_schema: Type[T],
    max_retries: int = 2,
    **chat_kwargs: Any,
) -> T:
    """通用"调用 chat → 解析 JSON → 失败重试"循环.

    用于 prompt 注入回退路径：解析失败时不立即返回空对象，而是把上一次坏输出
    追加为 assistant 消息，并提示模型只返回符合 schema 的 JSON，最多重试 max_retries 次。

    Args:
        chat_fn: provider 的 chat 方法，签名兼容 (messages, **kwargs) -> ModelResponse
        messages: 初始消息列表
        output_schema: 目标 Pydantic 模型
        max_retries: 最大重试次数
        **chat_kwargs: 透传给 chat_fn 的额外参数（temperature/model 等）

    Returns:
        解析成功的 output_schema 实例；全部失败则返回 model_construct() 空对象。
    """
    schema_hint = json.dumps(output_schema.model_json_schema(), ensure_ascii=False)
    current_messages = list(messages)
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = chat_fn(messages=current_messages, **chat_kwargs)
            content = getattr(response, "content", "") or ""
            data = parse_json_content(content)
            return output_schema(**data)
        except Exception as e:  # noqa: BLE001 - 重试需捕获所有解析/校验错误
            last_error = e
            logger.warning(
                "structured output parse failed, retrying",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=str(e),
            )
            if attempt < max_retries:
                # 追加坏输出 + 纠正提示，引导模型修正
                bad_content = ""
                try:
                    bad_content = getattr(response, "content", "") or ""  # type: ignore[name-defined]
                except Exception:  # pragma: no cover  # noqa: BLE001
                    bad_content = ""
                current_messages = current_messages + [
                    {"role": "assistant", "content": bad_content},
                    {
                        "role": "user",
                        "content": (
                            "上一次输出无法解析为符合 schema 的 JSON，请只返回"
                            f"严格匹配该 schema 的 JSON（不要任何解释或代码围栏）：{schema_hint}"
                        ),
                    },
                ]

    # 全部失败：返回空对象兜底，并记录错误
    logger.error(
        "structured output parse failed after retries, returning empty construct",
        error=str(last_error),
    )
    return output_schema.model_construct()
