
import requests
import json

def test_api():
    session = requests.Session()

    # 先访问主页获取 cookie
    print("1. 访问主页...")
    try:
        r = session.get("https://www.cnstock.com", timeout=10)
        print(f"   状态码: {r.status_code}")
        print(f"   Cookie: {dict(r.cookies)}")
    except Exception as e:
        print(f"   错误: {e}")

    # 测试原来的 API
    api_list = [
        "https://api.cnstock.com/www/news_list/channelNewsList",
        "https://api.cnstock.com/search/news"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://www.cnstock.com",
        "Referer": "https://www.cnstock.com/"
    }

    for api in api_list:
        print(f"\n2. 测试 API: {api}")
        try:
            payload = {"nodeId": "10232", "pageNum": 1, "pageSize": 10}
            r = session.post(api, json=payload, headers=headers, timeout=10)
            print(f"   状态码: {r.status_code}")
            print(f"   响应: {r.text[:200]}")
        except Exception as e:
            print(f"   错误: {e}")

    # 尝试直接访问新闻列表页面
    print("\n3. 访问新闻列表页面...")
    try:
        r = session.get("https://www.cnstock.com/news_list", headers={"User-Agent": headers["User-Agent"]}, timeout=10)
        print(f"   状态码: {r.status_code}")
        print(f"   内容长度: {len(r.text)}")

        # 搜索可能的 API 端点
        keywords = ["api", "news", "list", "channel"]
        for kw in keywords:
            if kw in r.text.lower():
                print(f"   包含关键词: {kw}")

        # 保存 HTML 供分析
        with open("c:/Users/H01402/.claude/skills/cnstock/scripts/output/page.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("   HTML 已保存到 output/page.html")

    except Exception as e:
        print(f"   错误: {e}")

if __name__ == "__main__":
    test_api()
