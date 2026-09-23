
"""测试财联社 API - 使用 %20 (URL编码空格) 作为 keyword"""
import requests
import json

session = requests.Session()

# 先访问主页获取 cookies
base_url = "https://www.cls.cn"
api_url = "https://www.cls.cn/api/sw"

print("访问主页...")
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://www.cls.cn',
    'Referer': 'https://www.cls.cn/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Connection': 'keep-alive'
}

resp = session.get(base_url, headers=headers, timeout=30)
print(f"主页状态: {resp.status_code}")

# 尝试 API 请求
date_str = "2026-04-26"
page_url = f"{base_url}/telegraph?date={date_str}"
session.get(page_url)  # 先访问带日期的页面

headers.update({
    'Referer': page_url,
    'Content-Type': 'application/json;charset=UTF-8'
})

params = {
    'app': 'CailianpressWeb',
    'os': 'web',
    'sv': '8.4.6',
    'sign': '9f8797a1f4de66c2370f7a03990d2737'
}

# 使用 %20 (URL编码空格) 作为 keyword
data = {
    'type': 'telegram',
    'keyword': '%20',
    'page': 1,
    'rn': 100,
    'date': date_str
}

print(f"\n--- 测试 keyword = '%20' ---")
print(f"请求数据: {json.dumps(data, ensure_ascii=False)}")

try:
    resp = session.post(api_url, params=params, json=data, headers=headers, timeout=30)
    print(f"状态: {resp.status_code}")
    result = resp.json()
    print(f"响应: {json.dumps(result, ensure_ascii=False)[:500]}")

    if result.get('errno') == 0 and 'data' in result:
        news_data = result['data'].get('telegram', {})
        if news_data and isinstance(news_data.get('data'), list):
            news_list = news_data['data']
            total_num = news_data.get('total_num', 0)
            print(f"\n✓ 成功！获取到 {len(news_list)} 条新闻，总数: {total_num}")

            if news_list:
                print(f"\n第一条新闻示例:")
                print(f"  id: {news_list[0].get('id')}")
                print(f"  time: {news_list[0].get('time')}")
                print(f"  descr: {news_list[0].get('descr', '')[:100]}...")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
