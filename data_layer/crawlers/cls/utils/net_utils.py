"""网络请求工具模块"""
import random
import time
from typing import Optional
import requests

def random_delay(
    base_delay: float = 1.5,
    jitter: float = 0.8,
    min_delay: float = 0.1
) -> None:
    """通用随机延迟函数"""
    delay = base_delay + random.uniform(-jitter * 0.5, jitter)
    delay = max(min_delay, delay)
    time.sleep(delay)

def retry_request(
    session: requests.Session,
    url: str,
    method: str = "get",
    max_retries: int = 3,
    retry_delay_min: float = 2.0,
    retry_delay_max: float = 5.0,
    **kwargs
) -> Optional[requests.Response]:
    """带重试机制的通用请求函数"""
    for attempt in range(max_retries):
        try:
            if method.lower() == "post":
                response = session.post(url, **kwargs)
            else:
                response = session.get(url, **kwargs)

            if response.status_code == 200:
                return response
            else:
                print(f"[request] Status {response.status_code}, attempt {attempt + 1}")
        except Exception as e:
            print(f"[request] Error: {e}, attempt {attempt + 1}")

        if attempt < max_retries - 1:
            delay = random.uniform(retry_delay_min, retry_delay_max)
            time.sleep(delay)

    return None
