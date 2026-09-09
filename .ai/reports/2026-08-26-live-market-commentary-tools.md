# 实时市场点评 Tool 演示

## 范围

- 在不执行数据库迁移、不持久化 Workflow Run 的前提下，复用 AKShare 公开数据源。
- AlphaFoundry 的原生 Tool 读取指数、全 A 宽度、行业板块和新闻；DSH 只负责 Skill。

## 实现

- `LiveAkShareMarketCommentaryTools` 以延迟导入方式调用既有 AKShare 采集器。
- `AkShareNewsFetcher` 在旧新浪/东方财富入口没有数据时，回退到 AKShare 当前支持的财新主新闻流。
- 获取失败会记录错误并抛出稳定的 Tool 不可用错误；工作流随后保留失败/阻断状态，不产生伪造产物。

## 已验证

- 本机公开数据源：指数 562 条、同花顺行业板块 90 条、全 A 行情 5,549 条、财新新闻流 100 条。
- `pytest tests/unit/test_runtime_kernel.py tests/unit/data_layer/crawlers/test_akshare_news.py -q`：9 passed。

## 限制

- 此报告未声明真实 DSH 模型生成已完成；其验证仍需仅进程级的 DeepSeek 凭据和重启隔离 DSH Host。
