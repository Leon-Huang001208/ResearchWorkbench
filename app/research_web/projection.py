"""Pure projection of native DSH events; no parallel research execution model."""

import json
import logging

log = logging.getLogger(__name__)


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
    plan, plan_turn = None, None
    messages: dict = {}
    activities: dict = {}
    partials: dict = {}
    tool_started: dict = {}
    question_calls: dict = {}
    question_history = []
    turn_started, duration_ms = None, 0
    status, error, tokens = "idle", None, 0
    input_tokens, output_tokens, usage_observed = 0, 0, False
    title = None
    for entry in sorted(entries, key=lambda row: row["event"]["seq"]):
        event = entry["event"]
        data, kind, seq = event["data"], event["type"], event["seq"]
        timestamp = event.get("time")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            timestamp = None
        if kind == "todo/write":
            todos = data.get("todos")
            valid = (
                isinstance(todos, list)
                and len(todos) <= 100
                and all(
                    isinstance(item, dict)
                    and isinstance(item.get("content"), str)
                    and 0 < len(item["content"]) <= 10000
                    and item.get("status") in {"pending", "in_progress", "completed"}
                    for item in todos
                )
            )
            if not valid:
                log.warning("research_plan_event_invalid")
            plan = {
                "turn": plan_turn,
                "seq": seq,
                "status": "available" if valid else "invalid",
                "history_complete": plan_turn is not None,
                "items": (
                    [{"content": item["content"], "status": item["status"]} for item in todos]
                    if valid
                    else []
                ),
            }
        elif kind == "user/message":
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
                if usage:
                    observed_input = usage.get("inputTokens")
                    observed_output = usage.get("outputTokens")
                    observed_total = usage.get("totalTokens")
                    if isinstance(observed_input, (int, float)) and not isinstance(
                        observed_input, bool
                    ):
                        input_tokens += max(0, int(observed_input))
                        usage_observed = True
                    if isinstance(observed_output, (int, float)) and not isinstance(
                        observed_output, bool
                    ):
                        output_tokens += max(0, int(observed_output))
                        usage_observed = True
                    if isinstance(observed_total, (int, float)) and not isinstance(
                        observed_total, bool
                    ):
                        tokens += max(0, int(observed_total))
                        usage_observed = True
                    elif usage_observed:
                        tokens += max(0, int(observed_input or 0)) + max(
                            0, int(observed_output or 0)
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
            tool_started[aid] = timestamp
            activities[aid] = {
                "id": aid,
                "type": "tool",
                "title": data["name"],
                "status": "running",
                "detail": data.get("arguments", ""),
            }
            if data["name"] == "ask_user_question":
                try:
                    args = data.get("arguments")
                    args = json.loads(args) if isinstance(args, str) else args
                    items = args.get("questions") if isinstance(args, dict) else None
                    if (
                        not isinstance(items, list)
                        or not items
                        or any(
                            not isinstance(item, dict)
                            or not isinstance(item.get("id"), str)
                            or not isinstance(item.get("question"), str)
                            for item in items
                        )
                    ):
                        raise ValueError("question_history_invalid")
                    question_calls[aid] = items
                except (ValueError, TypeError):
                    log.warning("research_question_history_call_unavailable")
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
                status=(
                    "failed"
                    if data.get("error") or message.get("isError") or block.get("isError")
                    else "completed"
                ),
                detail=content_text(
                    message.get("content")
                    if message.get("role") == "tool"
                    else block.get("content")
                ),
            )
            started = tool_started.get(aid)
            if aid in question_calls and row["status"] == "completed":
                try:
                    value = json.loads(row["detail"])
                    answers = value.get("answers") if isinstance(value, dict) else None
                    items = question_calls[aid]
                    if (
                        not isinstance(answers, list)
                        or len(answers) != len(items)
                        or any(
                            not isinstance(answer, dict)
                            or not isinstance(answer.get("id"), str)
                            or not isinstance(answer.get("selected"), list)
                            or any(not isinstance(choice, str) for choice in answer["selected"])
                            or not isinstance(answer.get("custom", ""), str)
                            for answer in answers
                        )
                        or {a["id"] for a in answers} != {item["id"] for item in items}
                    ):
                        raise ValueError("question_history_invalid")
                    question_history.append(
                        {"id": aid, "seq": seq, "items": items, "answers": answers}
                    )
                except (ValueError, TypeError):
                    log.warning("research_question_history_answer_unavailable")
            if started is not None and timestamp is not None and timestamp > started:
                row["duration_ms"] = timestamp - started
            if row.get("title") == "research_run_script" and row["status"] == "completed":
                try:
                    script = json.loads(row["detail"])
                    outcome = script.get("status") if isinstance(script, dict) else None
                    if outcome != "completed":
                        row["status"] = "cancelled" if outcome == "cancelled" else "failed"
                except (ValueError, TypeError):
                    row["status"] = "failed"
        elif kind == "turn/start":
            plan, plan_turn = None, data.get("turn")
            status, error = "running", None
            turn_started = timestamp
        elif kind == "turn/end":
            if turn_started is not None and timestamp is not None and timestamp > turn_started:
                duration_ms += timestamp - turn_started
            turn_started = None
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
        "research_plan": plan,
        "messages": sorted(
            (message for message in messages.values() if message["text"]),
            key=lambda row: row["seq"],
        ),
        "activities": list(activities.values()),
        "question_history": question_history,
        "status": status,
        "usage": (
            {
                "tokens": tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            if usage_observed
            else {}
        ),
    }
    if error:
        if "no API key" in error:
            error = "DeepSeek 尚未授权：请在设置中填写 API Key，然后发送下一条消息继续。"
        result["error"] = error
    if title:
        result["title"] = title
    if duration_ms:
        result["duration_ms"] = duration_ms
    return result
