"""测试财联社 API"""
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

data = {
    "type": "telegram",
    "keyword": " ",
    "page": 1,
    "rn": 100,
    "date": "2026-04-26"
}

print("\n请求 API...")
resp = session.post(api_url, params=params, json=data, headers=headers, timeout=30)
print(f"API 状态: {resp.status_code}")
print(f"响应头: {dict(resp.headers)}")
print(f"\n响应内容:")
print(resp.text[:500])
