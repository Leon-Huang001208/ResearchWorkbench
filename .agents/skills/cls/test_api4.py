"""测试财联社 API - 尝试 keyword 的其他表示方式"""
import requests
import json

session = requests.Session()

# 先访问主页获取 cookies
base_url = "https://www.cls.cn"
api_url = "https://www.cls.cn/api/sw"

print("访问主页...")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

resp = session.get(base_url, headers=headers, timeout=30)
print(f"主页状态: {resp.status_code}")

# 尝试 API 请求
headers.update({
    "Accept": "application/json, text/plain, */*",
    "Origin": base_url,
    "Referer": f"{base_url}/telegraph",
})

params = {
    "app": "CailianpressWeb",
    "os": "web",
    "sv": "8.4.6",
    "sign": "9f8797a1f4de66c2370f7a03990d2737"
}

# 尝试各种方式
test_cases = [
    ("不传 keyword 参数", {"type": "telegram", "page": 1, "rn": 20, "date": "2026-04-27"}),
    ("传 null", {"type": "telegram", "keyword": None, "page": 1, "rn": 20, "date": "2026-04-27"}),
    ("传 false", {"type": "telegram", "keyword": False, "page": 1, "rn": 20, "date": "2026-04-27"}),
    ("传 0", {"type": "telegram", "keyword": 0, "page": 1, "rn": 20, "date": "2026-04-27"}),
    ("传 空列表", {"type": "telegram", "keyword": [], "page": 1, "rn": 20, "date": "2026-04-27"}),
    ("传 空对象", {"type": "telegram", "keyword": {}, "page": 1, "rn": 20, "date": "2026-04-27"}),
]

for name, data in test_cases:
    print(f"\n--- 测试 {name} ---")
    print(f"请求数据: {repr(data)}")

    try:
        resp = session.post(api_url, params=params, json=data, headers=headers, timeout=30)
        print(f"状态: {resp.status_code}")
        result = resp.json()
        if "errno" in result and result["errno"] == 0:
            print(f"✓ 成功！获取到 {result['data']['telegram']['total_num']} 条数据")
            break
        elif "code" in result and result["code"] != 0:
            print(f"错误: {result.get('msg', result.get('error', '未知错误'))}")
        elif "error" in result:
            print(f"错误: {result['error']}")
        else:
            print(f"响应: {json.dumps(result, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"错误: {e}")
