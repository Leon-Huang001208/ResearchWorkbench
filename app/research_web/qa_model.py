"""Server-side model connection for the AlphaDesk worker."""

import asyncio
import json
import os
from pathlib import Path

import httpx

from .client import RuntimeFailure
from .model_credentials import DockerModelStore, docker_backend, execute
from .qa_acceptance import reserve

MAX_MODEL_EVENT = 1024 * 1024
MAX_MODEL_OUTPUT = 256 * 1024


def _credential(root, ref):
    backend = None
    if os.environ.get("RWB_MODEL_BACKEND") == "docker-encrypted":
        root = Path("/run/rwb-secrets")
        backend = docker_backend(
            root / "models", Path("/run/rwb-model-key"), os.environ["RWB_MODEL_INSTANCE_ID"]
        )
    elif os.environ.get("RWB_DSH_STAGED") == "1":
        if os.environ.get("RESEARCH_CREDENTIAL_HOME") != "/run/rwb-secrets/private":
            raise ValueError("model_credential_binding_invalid")
        root = Path("/run/rwb-secrets")
        backend = DockerModelStore("/run/rwb-secrets/private")
    return execute(root, {"op": "resolve", "ref": ref}, backend)["value"]


async def connection(service, row):
    provider = row["model_provider"]
    service.assert_session_model_profile(row)
    ref, uncertain, cleared = service._model_plane(provider)
    if service.store.data.get(uncertain):
        raise RuntimeFailure("模型配置结果未知", "model_configuration_uncertain")
    if provider == "deepseek-official":
        base = "https://api.deepseek.com"
        model = row["model"]
        needs_key = True
    elif provider == "openai-compatible":
        config = service.compatible_connection()
        if not config or row.get("model_connection_binding") != {
            name: config[name] for name in ("base_url", "protocol", "credential_mode")
        }:
            raise RuntimeFailure("模型连接已改变，请新建问答", "model_connection_changed")
        base, model = config["base_url"], row["model"]
        needs_key = config["credential_mode"] == "api_key"
    else:
        raise RuntimeFailure("问答暂不支持该模型连接", "qa_model_unsupported")
    key = None
    if needs_key:
        if service.store.data.get(cleared):
            raise RuntimeFailure("模型凭据未配置", "model_credentials_missing")
        try:
            key = await asyncio.to_thread(_credential, service.store.root, ref)
        except Exception:  # noqa: BLE001 - credential backend details are private
            raise RuntimeFailure("模型凭据不可用", "model_credential_backend_unavailable") from None
        if not key:
            raise RuntimeFailure("模型凭据未配置", "model_credentials_missing")
    return base.rstrip("/") + "/chat/completions", model, key, provider


async def stream_model(client, config, params, emit):
    endpoint, model, key, provider = config
    messages, max_tokens = params.get("messages"), params.get("maxTokens")
    if not isinstance(messages, list) or not messages or len(messages) > 100:
        raise ValueError("qa_model_messages_invalid")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
        raise ValueError("qa_model_token_limit")
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True}
    if provider == "deepseek-official":
        body["thinking"] = {"type": "disabled"}
    if params.get("tools"):
        body["tools"] = params["tools"]
    headers = {"Authorization": "Bearer " + key} if key else {}
    reserve(config, max_tokens)
    text, reasoning, tools, observed, size = [], [], {}, False, 0
    async with client.stream("POST", endpoint, headers=headers, json=body) as response:
        response.raise_for_status()
        pending = b""
        async for chunk in response.aiter_bytes():
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if len(line) > MAX_MODEL_EVENT:
                    raise ValueError("qa_model_event_limit")
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    observed = True
                    continue
                payload = json.loads(data)
                if payload.get("error"):
                    raise ValueError("qa_model_provider_error")
                choices = payload.get("choices", [])
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("finish_reason") in {"stop", "tool_calls"}:
                    observed = True
                if choice.get("finish_reason") in {"length", "content_filter"}:
                    raise ValueError("qa_model_response_incomplete")
                delta = choice.get("delta") or {}
                for field, target in (("content", text), ("reasoning_content", reasoning)):
                    value = delta.get(field)
                    if value:
                        if not isinstance(value, str):
                            raise ValueError("qa_model_response_invalid")
                        size += len(value.encode("utf-8"))
                        if size > MAX_MODEL_OUTPUT:
                            raise ValueError("qa_model_output_limit")
                        target.append(value)
                        if field == "content":
                            await emit(value)
                for item in delta.get("tool_calls", []):
                    index = item["index"]
                    if type(index) is not int or not 0 <= index < 8:
                        raise ValueError("qa_model_tool_limit")
                    call = tools.setdefault(
                        index,
                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    call["id"] += item.get("id") or ""
                    for field, value in (item.get("function") or {}).items():
                        if field not in call["function"] or not isinstance(value, str):
                            raise ValueError("qa_model_tool_invalid")
                        size += len(value.encode("utf-8"))
                        call["function"][field] += value
                    if size > MAX_MODEL_OUTPUT:
                        raise ValueError("qa_model_output_limit")
            if len(pending) > MAX_MODEL_EVENT:
                raise ValueError("qa_model_event_limit")
    if not observed or pending.strip() not in {b"", b"data: [DONE]"}:
        raise ValueError("qa_model_response_incomplete")
    result = {"content": "".join(text), "toolCalls": [tools[i] for i in sorted(tools)]}
    if reasoning:
        result["reasoningContent"] = "".join(reasoning)
    return result


def model_client():
    return httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10), follow_redirects=False)
