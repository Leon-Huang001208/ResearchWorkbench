
# Yahoo Finance 集成使用指南

## 概述

Yahoo Finance 作为 Research Workbench 的补充数据源，提供全球市场数据服务：

- **美股**：AAPL, MSFT, GOOGL 等
- **港股**：00700.HK, 00005.HK 等
- **ETF**：SPY, QQQ 等
- **指数**：^GSPC (S&amp;P 500), ^DJI (道琼斯), ^IXIC (纳斯达克)
- **外汇和商品**

## 安装依赖

Yahoo Finance 是可选依赖，需要手动安装：

```bash
pip install yfinance
```

## 快速开始

### 1. 使用 Yahoo 专用协调器（推荐）

```python
from data_layer.coordinator.yahoo_coordinator import get_yahoo_coordinator

# 获取协调器
coordinator = get_yahoo_coordinator()

# 检查可用性
if coordinator.is_available():
    print("Yahoo Finance 可用")
else:
    print("Yahoo Finance 不可用，请先安装 yfinance")
```

### 2. 获取美股历史数据

```python
# 获取苹果公司近一年的数据
result = coordinator.fetch_historical_data(
    symbol="AAPL",
    period="1y",
    interval="1d"
)

if result.success:
    for data in result.data:
        print(f"{data.timestamp.date()}: {data.close}")
else:
    print(f"获取失败: {result.error_message}")
```

### 3. 获取港股数据

```python
# 获取腾讯控股数据（Yahoo 格式）
result = coordinator.fetch_historical_data(
    symbol="00700.HK",
    period="6mo"
)

# 或者使用 AkShare 格式，会自动转换
result = coordinator.fetch_historical_data(
    symbol="hk00700",
    period="6mo"
)
```

### 4. 获取股票基本信息

```python
info = coordinator.fetch_stock_info("AAPL")
if info["success"]:
    stock_info = info["info"]
    print(f"公司名称: {stock_info['name']}")
    print(f"当前价格: {stock_info['current_price']}")
    print(f"市值: {stock_info['market_cap']}")
    print(f"PE 比率: {stock_info['pe_ratio']}")
```

### 5. 批量获取多只股票

```python
symbols = ["AAPL", "MSFT", "GOOGL", "00700.HK"]
results = coordinator.fetch_batch_historical_data(
    symbols=symbols,
    period="1y"
)

for symbol, result in results.items():
    if result.success:
        print(f"{symbol}: {len(result.data)} 条数据")
    else:
        print(f"{symbol}: 失败 - {result.error_message}")
```

### 6. 获取财务报表

```python
from data_layer.crawlers.yahoo import YahooAdapter

yahoo = YahooAdapter()

# 获取利润表
income_stmt = yahoo.fundamental.get_income_statement("AAPL")
print(income_stmt)

# 获取资产负债表
balance_sheet = yahoo.fundamental.get_balance_sheet("AAPL")

# 获取现金流量表
cash_flow = yahoo.fundamental.get_cash_flow("AAPL")
```

### 7. 获取分红和拆股历史

```python
# 分红历史
dividends = yahoo.fundamental.get_dividends("AAPL")
print(dividends)

# 拆股历史
splits = yahoo.fundamental.get_splits("AAPL")
print(splits)
```

### 8. 获取新闻数据

```python
from data_layer.crawlers.yahoo import YahooAdapter

yahoo = YahooAdapter()
news = yahoo.news.get_news("AAPL", limit=10)

for item in news:
    print(f"标题: {item.title}")
    print(f"时间: {item.publish_time}")
    print(f"链接: {item.url}")
    print("-" * 50)
```

## 使用 Yahoo Adapter 直接操作

```python
from data_layer.adapters.yahoo_adapter import YahooAdapter

adapter = YahooAdapter()

# 检查可用性
if adapter.is_available():
    # 获取行情
    quotes = await adapter.fetch_stock_quotes(
        "AAPL",
        period="1y",
        interval="1d"
    )

    # 获取股票信息
    info = await adapter.fetch_stock_info("AAPL")

    # 获取财务报告
    financial = await adapter.fetch_financial_report("AAPL")

    # 获取新闻
    news = await adapter.fetch_news("AAPL", limit=10)

    # 获取分红
    dividends = await adapter.fetch_dividends("AAPL")
```

## Symbol 格式说明

### Yahoo 原生格式

- **美股**：`AAPL`, `MSFT`, `GOOGL`
- **港股**：`00700.HK`, `00005.HK`, `00001.HK`
- **A股**：`600519.SS` (上交所), `000001.SZ` (深交所)
- **指数**：`^GSPC` (S&amp;P 500), `^DJI` (道琼斯), `^IXIC` (纳斯达克)

### 自动转换

协调器支持自动转换 AkShare/BaoStock 格式为 Yahoo 格式：

- `sh600519` → `600519.SS`
- `sz000001` → `000001.SZ`
- `hk00700` → `00700.HK`
- `sh.600519` (BaoStock) → `600519.SS`

## Interval 支持的 K线间隔

- 分钟级：`1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`
- 小时级：`1h`
- 日级：`1d`, `5d`
- 周/月级：`1wk`, `1mo`, `3mo`

## Period 支持的时间段

- `1d`, `5d`
- `1mo`, `3mo`, `6mo`
- `1y`, `2y`, `5y`, `10y`
- `ytd` (年初至今)
- `max` (最大历史)

## 反爬虫策略

Yahoo Finance 有反爬机制，我们已经集成了：

1. **智能延迟**：请求间隔自动调整
2. **速率限制**：每分钟/每小时请求数限制
3. **失败重试**：指数退避重试
4. **User-Agent 轮换**：模拟真实浏览器

建议：
- 单次请求数据量不要过大（使用 `period="5y"` 而不是一次性获取所有历史）
- 批量获取时使用 `get_batch_historical_data`（效率更高）
- 考虑本地缓存数据（未来版本会实现）

## 健康检查

```python
from data_layer.coordinator.yahoo_coordinator import get_yahoo_coordinator

coordinator = get_yahoo_coordinator()
health = coordinator.health_check()
print(health)
```

健康的返回示例：
```python
{
    "status": "healthy",
    "source": "yahoo",
    "data_count": 5,
    "timestamp": "2024-05-14T10:30:00"
}
```

## 注意事项

1. **数据延迟**：Yahoo Finance 免费版有数据延迟（美股~15分钟，港股~20分钟），不适合高频交易
2. **稳定性**：Yahoo Finance 是非官方 API，可能会变更或失效
3. **请求限制**：虽然有反爬策略，仍需合理控制请求频率
4. **A股数据**：A股数据建议优先使用 AkShare/BaoStock，Yahoo 作为补充
5. **复权处理**：Yahoo 的 `auto_adjust` 参数自动处理拆股和分红，与 AkShare 的前复权类似

## 与现有系统集成

### 在 Dashboard Service 中使用

```python
from data_layer.coordinator.yahoo_coordinator import get_yahoo_coordinator

async def get_us_market_data():
    coordinator = get_yahoo_coordinator()

    # 获取 S&amp;P 500 指数
    result = coordinator.fetch_historical_data("^GSPC", period="6mo")

    if result.success:
        # 转换为与现有系统兼容的格式
        market_data = []
        for d in result.data:
            market_data.append({
                "date": d.timestamp.date().isoformat(),
                "open": d.open,
                "high": d.high,
                "low": d.low,
                "close": d.close,
                "volume": d.volume,
                "source": "yahoo"
            })
        return market_data
    else:
        return []
```

### 多源数据对比

```python
from data_layer.coordinator.multi_source_coordinator import get_coordinator
from data_layer.coordinator.yahoo_coordinator import get_yahoo_coordinator

# 获取 A股数据（AkShare/BaoStock）
cn_coordinator = get_coordinator()
cn_result = cn_coordinator.fetch_historical_data("600519.SH", period="6mo")

# 获取美股数据（Yahoo）
us_coordinator = get_yahoo_coordinator()
us_result = us_coordinator.fetch_historical_data("AAPL", period="6mo")
```

## 常见问题

**Q: Yahoo Finance 请求失败怎么办？**

A: 可能是触发了反爬机制，建议：
- 等待一段时间后重试
- 减少请求频率
- 检查网络连接

**Q: 能获取实时数据吗？**

A: 免费版有延迟，不适合实时交易，适合回测和分析。

**Q: A股数据优先用哪个源？**

A: A股优先用 AkShare/BaoStock，Yahoo 作为补充或对比校验。

**Q: Yahoo Finance 数据稳定吗？**

A: Yahoo Finance API 是非官方的，可能会变更，但 yfinance 社区会跟进更新。

## 进一步参考

- [yfinance GitHub](https://github.com/ranaroussi/yfinance)
- [Yahoo Finance 官网](https://finance.yahoo.com)

