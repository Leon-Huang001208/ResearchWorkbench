"""Pure projection of native DSH events; no parallel research execution model."""

import json


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def project(entries: list[dict]) -> dict:
    messages: dict = {}
    activities: dict = {}
    partials: dict = {}
    status, error, tokens = "idle", None, 0
    title = None
    for entry in sorted(entries, key=lambda row: row["event"]["seq"]):
        event = entry["event"]
        data, kind, seq = event["data"], event["type"], event["seq"]
        if kind == "user/message":
            # Skill/system injected context is not a human message in the UI.
            source = data.get("source")
            if (
                source
                and isinstance(source, dict)
                and source.get("kind") not in {None, "human", "user"}
            ):
                continue
            mid = str(data.get("id", f"user-{seq}"))
            messages[mid] = {
                "id": mid,
                "role": "user",
                "text": content_text(data.get("content")),
                "seq": seq,
            }
        elif kind in {"assistant/chunk", "assistant/message"}:
            mid = f"assistant-{data.get('turn')}-{data.get('step')}"
            if kind == "assistant/message":
                messages[mid] = {
                    "id": mid,
                    "role": "assistant",
                    "text": content_text(data.get("message", {}).get("content")),
                    "seq": seq,
                }
                partials.pop(mid, None)
                usage = data.get("usage") or {}
                tokens += (
                    usage.get(
                        "totalTokens", usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
                    )
                    or 0
                )
            elif mid not in messages:
                chunk = data["chunk"]
                blocks = partials.setdefault(mid, {"seq": seq, "blocks": {}})["blocks"]
                index = chunk.get("index", 0)
                if chunk["type"] == "text-delta":
                    blocks[index] = blocks.get(index, "") + chunk.get("text", "")
                elif chunk["type"] == "block-end" and chunk.get("block", {}).get("type") == "text":
                    blocks[index] = chunk["block"].get("text", "")
        elif kind == "tool/call":
            aid = data["callId"]
            activities[aid] = {
                "id": aid,
                "type": "tool",
                "title": data["name"],
                "status": "running",
                "detail": data.get("arguments", ""),
            }
        elif kind == "tool/result":
            message = data.get("message", {})
            block: dict = next(
                (b for b in message.get("content", []) if b.get("type") == "tool-result"), {}
            )
            aid = message.get("source", {}).get("callId") or block.get("toolCallId", f"tool-{seq}")
            row = activities.setdefault(
                aid, {"id": aid, "type": "tool", "title": message.get("name", "工具结果")}
            )
            row.update(
                status="failed" if data.get("error") or block.get("isError") else "completed",
                detail=content_text(block.get("content")),
            )
            if row.get("title") == "af_run_script" and row["status"] == "completed":
                try:
                    script = json.loads(row["detail"])
                    outcome = script.get("status") if isinstance(script, dict) else None
                    if outcome != "completed":
                        row["status"] = "cancelled" if outcome == "cancelled" else "failed"
                except (ValueError, TypeError):
                    row["status"] = "failed"
        elif kind == "turn/start":
            status, error = "running", None
        elif kind == "turn/end":
            reason = data.get("reason", {})
            status = {
                "completed": "completed",
                "aborted": "cancelled",
                "interrupted": "interrupted",
                "error": "failed",
                "blocked": "blocked",
                "max-tokens": "incomplete",
            }.get(reason.get("kind"), "interrupted")
            if status == "failed":
                error = reason.get("error", {}).get("message", "DSH 执行失败")
            for activity in activities.values():
                if activity.get("status") == "running":
                    activity["status"] = "interrupted"
        elif kind == "session/title":
            title = data.get("title")
    for mid, partial in partials.items():
        messages[mid] = {
            "id": mid,
            "role": "assistant",
            "text": "\n".join(partial["blocks"][key] for key in sorted(partial["blocks"])),
            "seq": partial["seq"],
        }
    result = {
        "messages": sorted(
            (message for message in messages.values() if message["text"]),
            key=lambda row: row["seq"],
        ),
        "activities": list(activities.values()),
        "status": status,
        "usage": {"tokens": tokens} if tokens else {},
    }
    if error:
        if "no API key" in error:
            error = "DeepSeek 尚未授权：请在设置中填写 API Key，然后发送下一条消息继续。"
        result["error"] = error
    if title:
        result["title"] = title
    return result
