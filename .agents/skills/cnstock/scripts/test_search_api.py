
import requests
import json

def test_search():
    session = requests.Session()

    # 先访问主页
    session.get("https://www.cnstock.com", timeout=10)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://www.cnstock.com",
        "Referer": "https://www.cnstock.com/"
    }

    # 测试原来的搜索 API
    print("1. 测试原搜索 API: /search/news")
    try:
        payload = {"type": "0", "word": "人工智能", "activeKey": "0", "pageNum": 1}
        r = session.post("https://api.cnstock.com/search/news", json=payload, headers=headers, timeout=10)
        print(f"   状态码: {r.status_code}")
        print(f"   响应: {r.text[:300]}")
    except Exception as e:
        print(f"   错误: {e}")

    # 试试可能的变体
    variants = [
        "/searchNews",
        "/search/newsList",
        "/newsSearch",
        "/api/search/news",
    ]

    print("\n2. 测试可能的 API 路径变体:")
    for path in variants:
        try:
            url = f"https://api.cnstock.com{path}"
            r = session.post(url, json=payload, headers=headers, timeout=5)
            print(f"   {path:<20} -> {r.status_code}")
            if r.status_code == 200 and r.text:
                print(f"      响应: {r.text[:200]}")
        except Exception:
            pass

if __name__ == "__main__":
    test_search()
