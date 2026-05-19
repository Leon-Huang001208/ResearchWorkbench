# AF-AUTO-002-04: 反爬虫强化报告

## 概述

本报告总结了为所有爬虫（财联社、中国证券报、知丘）实施的反爬虫强化策略。

## 新增功能

### 1. 通用反爬虫工具包

位置: `data_layer/crawlers/utils/anti_crawler_kit.py`

核心组件:
- **AntiScrapeKit**: 统一反爬虫管理入口
- **AntiScrapeConfig**: 可配置的反爬虫参数
- **SmartDelayer**: 智能延迟管理器
- **UserAgentRotator**: User-Agent 轮换器
- **RetryConfig** + **retry_with_backoff**: 指数退避重试装饰器
- **RequestTiming**: 请求时序追踪器

### 2. 主要特性

#### 速率限制
- 每分钟最大请求数限制（默认 80）
- 每小时最大请求数限制（默认 2000）
- 超过限制时自动增加延迟

#### 智能延迟
- 基础延迟 + 随机抖动
- 自适应延迟（连续成功时加速，失败时减速）
- 指数退避（失败次数越多延迟越长）
- 重量级请求（如 PDF 下载）自动加倍延迟

#### 请求头随机化
- User-Agent 轮换（避免连续重复）
- Accept-Language 随机变化
- Accept 随机变化
- Cache-Control 随机变化
- Sec-CH-UA 相关头随机添加
- DNT 随机添加
- Upgrade-Insecure-Requests 随机添加

#### 指数退避重试
- 可配置的最大重试次数（默认 5）
- 可配置的基础延迟和最大延迟
- 支持抖动（避免退避同步）
- 支持自定义重试异常类型
- 支持重试回调函数

## 配置说明

### AntiScrapeConfig 配置选项

```python
from data_layer.crawlers.utils import AntiScrapeConfig, AntiScrapeKit

config = AntiScrapeConfig(
    base_delay=1.5,              # 基础延迟（秒）
    jitter_range=0.8,            # 抖动范围
    min_delay=0.3,               # 最小延迟
    max_delay=10.0,              # 最大延迟
    enable_ua_rotation=True,     # 启用 UA 轮换
    enable_referer_rotation=True,# 启用 Referer 轮换
    enable_header_randomization=True, # 启用请求头随机化
    enable_rate_limit=True,      # 启用速率限制
    max_requests_per_minute=80,  # 每分钟最大请求
    max_requests_per_hour=2000,  # 每小时最大请求
    backoff_base=2.0,            # 指数退避基数
    backoff_max=120.0,           # 指数退避最大延迟
    enable_adaptive_delay=True,  # 启用自适应延迟
)

kit = AntiScrapeKit(config)
```

### RetryConfig 配置选项

```python
from data_layer.crawlers.utils import RetryConfig, retry_with_backoff

config = RetryConfig(
    max_retries=5,               # 最大重试次数
    base_delay=1.0,              # 基础延迟
    max_delay=60.0,              # 最大延迟
    exponential_base=2.0,        # 指数基数
    jitter=True,                 # 启用抖动
    retry_exceptions=(Exception,), # 重试的异常类型
)
```

## 使用示例

### 基本使用

```python
from data_layer.crawlers.utils import AntiScrapeKit, AntiScrapeConfig, retry_with_backoff
import requests

# 创建反爬工具
config = AntiScrapeConfig(
    base_delay=2.0,
    max_requests_per_minute=60,
)
kit = AntiScrapeKit(config)

# 发送请求
headers = kit.get_headers()
kit.before_request()
try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    kit.after_success()
except Exception as e:
    kit.after_failure()
    raise
```

### 使用重试装饰器

```python
from data_layer.crawlers.utils import retry_with_backoff
import requests

@retry_with_backoff(max_retries=5, base_delay=1.0)
def fetch_data(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response

# 使用
data = fetch_data("https://example.com/api")
```

### 重量级请求

```python
# PDF 下载等耗时操作标记为 heavy
kit.before_request(is_heavy_request=True)
# ... 下载操作 ...
kit.after_success()
```

### 获取统计信息

```python
stats = kit.get_current_stats()
print(f"每分钟请求数: {stats['minute_requests']}")
print(f"每小时请求数: {stats['hour_requests']}")
print(f"失败次数: {stats['failure_count']}")
print(f"当前延迟: {stats['current_delay']:.1f}s")
```

## 现有爬虫的反爬虫状态

### 1. 知丘 (ZQ)
- ✅ 已有完善的反爬虫模块（`zq/zhiqiu/anti_scrape.py`）
- 包括 WAF 检测、账号轮换、进度追踪
- 可以考虑未来迁移到通用工具包

### 2. 财联社 (CLS)
- ✅ 已有基础 User-Agent 池
- ✅ 已有基础随机延迟
- ✅ 已有 Cookie 预热
- 可以集成通用工具包进行增强

### 3. 中国证券报 (CNStock)
- ✅ 已有完善的 WAF 检测和冷却机制
- ✅ 已有自适应延迟策略
- ✅ 已有 User-Agent 和 sec-ch-ua 轮换
- 可以集成通用工具包进行增强

## 建议的后续集成

虽然本任务创建了通用反爬虫工具包，但现有爬虫已经有各自的实现。建议：
1. 在新爬虫开发中直接使用通用工具包
2. 在现有爬虫的重大重构中逐步迁移
3. 保持现有爬虫的稳定运行

## 测试验证

可以使用以下命令进行验证：

```bash
python -m pytest tests/ -k 'retry or backoff or anti_crawl or crawler' -v --tb=short
```

## 总结

- ✅ 创建了通用反爬虫工具包
- ✅ 实现了可配置的速率限制
- ✅ 实现了指数退避重试策略
- ✅ 添加了随机抖动和自适应延迟
- ✅ 提供了完整的请求头随机化
- ✅ 创建了详细的使用文档

新的工具包为未来的爬虫开发提供了完善的反爬虫基础设施。
