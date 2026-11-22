"""One bounded private worker process per admitted AlphaDesk turn."""

import asyncio
import json
import os
import shutil
from pathlib import Path

from .client import RuntimeFailure

FRAME_LIMIT = 1024 * 1024
WORKER = Path(__file__).with_name("qa_worker") / "worker.mjs"


async def run_worker(request, callbacks, event):
    node = os.environ.get("RESEARCH_NODE_BINARY") or shutil.which("node")
    if not node or not WORKER.is_file():
        raise RuntimeFailure("问答执行器未安装", "qa_worker_unavailable")
    process = await asyncio.create_subprocess_exec(
        node,
        str(WORKER),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={"PATH": str(Path(node).parent)},
        limit=FRAME_LIMIT + 1,
    )

    async def send(value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        if len(raw) > FRAME_LIMIT:
            raise ValueError("qa_worker_frame_limit")
        process.stdin.write(raw + b"\n")
        await process.stdin.drain()

    async def delta(identifier, content):
        await send({"type": "delta", "id": identifier, "content": content})

    async def dispatch(identifier, method, params):
        async def emit(content):
            await delta(identifier, content)

        result = await callbacks[method](params, emit)
        await send({"type": "result", "id": identifier, "result": result})

    async def exchange():
        await send({"type": "start", **request})
        last_id = 0
        pending = None
        try:
            while True:
                reader = asyncio.create_task(process.stdout.readline())
                try:
                    if pending is not None:
                        ready, _ = await asyncio.wait(
                            {reader, pending}, return_when=asyncio.FIRST_COMPLETED
                        )
                        if pending in ready:
                            await pending
                            pending = None
                    raw = await reader
                finally:
                    if not reader.done():
                        reader.cancel()
                        await asyncio.gather(reader, return_exceptions=True)
                if not raw:
                    break
                if len(raw) > FRAME_LIMIT + 1:
                    raise ValueError("qa_worker_frame_limit")
                frame = json.loads(raw)
                kind = frame["type"]
                if kind == "event":
                    await event(frame["event"], frame["data"])
                elif kind == "call":
                    if pending is not None:
                        if not pending.done():
                            raise ValueError("qa_worker_overlapping_callbacks")
                        await pending
                    identifier, method = frame["id"], frame["method"]
                    if (
                        type(identifier) is not int
                        or identifier <= last_id
                        or method not in callbacks
                    ):
                        raise ValueError("qa_worker_callback_invalid")
                    last_id = identifier
                    pending = asyncio.create_task(dispatch(identifier, method, frame["params"]))
                elif kind == "done":
                    if pending is not None:
                        await pending
                    process.stdin.close()
                    if await process.wait() == 0:
                        return
                    break
                elif kind == "failed":
                    break
                else:
                    raise ValueError("qa_worker_frame_invalid")
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
        raise RuntimeFailure("问答执行器未确认完成", "qa_worker_failed")

    try:
        async with asyncio.timeout(900):
            await exchange()
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
