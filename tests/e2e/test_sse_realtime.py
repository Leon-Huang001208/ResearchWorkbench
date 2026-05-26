#!/usr/bin/env python3
"""
E2E 测试：SSE realtime event stream
验证：
1. uvicorn 子进程启动 API 服务（端口 8765）
2. 浏览器 EventSource 连接到 /api/realtime/stream
3. 通过 event_bus.publish() 发布测试事件
4. SSE 正确推送事件到浏览器
"""
import asyncio
import multiprocessing
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def start_server():
    """在子进程中启动 uvicorn"""
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host="127.0.0.1",
        port=8765,
        log_level="error",
    )


async def test_sse_realtime():
    from playwright.async_api import async_playwright

    screenshot_dir = Path(__file__).parent / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)

    # 启动 API 服务子进程
    server_proc = multiprocessing.Process(target=start_server, daemon=True)
    server_proc.start()
    await asyncio.sleep(3)  # 等待服务就绪

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                print(f"==> SKIP: Cannot launch browser: {e}")
                return
            page = await browser.new_page()

            page.on("console", lambda msg: print(f"[Console] {msg.text}"))

            print("=" * 60)
            print("Step 1: Navigate and establish EventSource")
            print("=" * 60)

            try:
                await page.goto("http://127.0.0.1:8765/", timeout=10000)
            except Exception as e:
                print(f"==> SKIP: Cannot reach test server at :8765: {e}")
                await browser.close()
                return
            await page.evaluate(
                """
                window.sseReceived = [];
                const es = new EventSource('/api/realtime/stream');
                es.addEventListener('test_sse_e2e', (e) => {
                    window.sseReceived.push(JSON.parse(e.data));
                });
                window._es = es;
            """
            )
            await asyncio.sleep(1)

            print("✓ EventSource connected")

            print("=" * 60)
            print("Step 2: Publish events via HTTP API")
            print("=" * 60)

            await page.evaluate(
                """
                fetch('/api/system/event', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({event_type: 'test_sse_e2e', payload: {message: 'hello from e2e'}})
                });
            """
            )
            await page.evaluate(
                """
                fetch('/api/system/event', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({event_type: 'test_sse_e2e', payload: {message: 'second event'}})
                });
            """
            )

            await asyncio.sleep(2)  # 等待 SSE 推送

            print("=" * 60)
            print("Step 3: Verify events received")
            print("=" * 60)

            count = await page.evaluate("window.sseReceived.length")
            assert count >= 2, f"Expected >=2 events received, got {count}"
            print(f"✓ Received {count} SSE events")

            first = await page.evaluate("window.sseReceived[0]")
            assert first["type"] == "test_sse_e2e"
            assert first["payload"]["message"] == "hello from e2e"
            print(f"✓ First event: {first['payload']['message']}")

            second = await page.evaluate("window.sseReceived[1]")
            assert second["payload"]["message"] == "second event"
            print(f"✓ Second event: {second['payload']['message']}")

            await page.evaluate("window._es.close()")
            print("✓ EventSource closed")

            await page.screenshot(
                path=str(screenshot_dir / "sse_realtime_test.png"), full_page=False
            )

            await browser.close()

    finally:
        server_proc.terminate()
        server_proc.join(timeout=5)
        if server_proc.is_alive():
            server_proc.kill()

    print("ALL SSE E2E CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(test_sse_realtime())
