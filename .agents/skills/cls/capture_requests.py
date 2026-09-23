"""捕获财联社电报页面的网络请求"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("启动浏览器...")
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 监听所有网络请求
        api_calls = []

        async def handle_response(response):
            if "api/sw" in response.url and response.status == 200:
                print(f"\n[API 响应] {response.url}")
                try:
                    data = await response.json()
                    print(f"内容: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
                    api_calls.append({
                        "url": response.url,
                        "request": {
                            "method": response.request.method,
                            "headers": dict(response.request.headers),
                            "post_data": await response.request.post_data() if response.request.post_data else None
                        },
                        "response": data
                    })
                except Exception as e:
                    print(f"解析失败: {e}")
                    text = await response.text()
                    print(f"响应文本: {text[:200]}")

        page.on("response", handle_response)

        print("访问电报页面...")
        await page.goto("https://www.cls.cn/telegraph", wait_until="networkidle", timeout=60000)

        print("\n等待 5 秒让页面加载...")
        await asyncio.sleep(5)

        print("\n尝试选择日期...")
        # 尝试点击日期选择器或进行一些交互
        try:
            await page.click("text=电报", timeout=5000)
            await asyncio.sleep(2)
        except:
            pass

        print("\n再等待 5 秒...")
        await asyncio.sleep(5)

        print(f"\n捕获到 {len(api_calls)} 个 API 请求")

        if api_calls:
            with open("captured_requests.json", "w", encoding="utf-8") as f:
                json.dump(api_calls, f, ensure_ascii=False, indent=2)
            print("已保存到 captured_requests.json")

        print("\n按 Enter 关闭浏览器...")
        input()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
