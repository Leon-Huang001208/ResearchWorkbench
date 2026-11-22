# 三市场指数数据合同

`index_set=global-v1` 是独立的九指数集合，固定身份复用
`market_scoring/profiles.py` 的 SSE、CSI300、CHINEXT、SP500、NASDAQ、DJI、HSI、HSCEI、HSTECH。
默认三个入口为 SSE、SP500、HSI。作者、定义页面与行情供应商分别保存；全部是价格指数，
不使用 ETF、全收益指数或跨指数替代。旧 core-v1 固定12和 terminal-v2 固定24合同保持。

`POST /api/research/market/refresh` 显式传入
`{"sections":["indices"],"index_set":"global-v1"}`，沿既有账号、同源、用户动作和幂等门执行。
原 `GET /api/research/market` 只投影本账号 `sections["indices:global-v1"]` 缓存，
不取源、不调用模型、不创建研究任务、不启用日程。完整结果沿原 market-cache 保存及恢复；
缺口结果遵循原部分结果策略，保留当前进程部分投影且不替换上次完整缓存。
不把新九指数封包写入既有 core-v1 固定12 ResearchWarehouse profile，不改仓表。

`datahub/providers_global_indices.py` 使用 DataHub 既有注册腾讯历史端点与 httpx 依赖：
固定 `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get`，固定九符号，单响应1MiB、并发3，
每指数一次请求。CN为sh000001/sh000300/sz399006，US为us.INX/us.IXIC/us.DJI，
HK为hkHSI/hkHSCEI/hkHSTECH。请求 `day,,,100,qfq` 保持原注册合同，
响应只接受原生 `day`，拒绝以 qfqday/hfqday 替换；最多160条。
响应唯一data key和qt代码均须匹配固定symbol；日期按对应市场本地时区严格递增。
币种和时区来自冻结九指数身份映射，价格单位为指数点；不声称供应商另行返回了币种验证证据。
原 Yahoo chart parser 保持独立校验 symbol/INDEX/币种/时区，但本机 query1/query2 均HTTP403，
不把它作为线上无益重试或把其失败隐藏。来源目录的Yahoo符号是独立路由，实际行source_symbol以Tencent为准。
网络、HTTP、身份、JSON、非有限数字、日期或 OHLC 冲突均返回结构化 gap，日志只有标识和稳定错误码。
顶层 JSON 必须是对象，null／数组／字符串均为 `invalid_tencent_schema`，单指数坏响应只形成该行缺口，
不会中断其他指数成功结果；取消仍真实向上传播，不用宽泛异常吞取消或编程错误。
无认证、厂商登录、后台重试或来源自动更新。公开接口可达不证明再分发许可；本功能标明个人参考用途。

每行保存真实 `price/change/change_pct/as_of/quote_trade_date`；腾讯qt[3,4,30,31,32]
提供报价/昨收/时间/涨跌/涨跌幅，昨收与同源前日bar交叉核对，冲突显示gap。
Yahoo解析器不误用区间起点chartPreviousClose。`daily_bars` 保存源原生 open/high/low/close/volume 和 date，
timestamp为源日期在市场本地午夜的bar桶坐标，不冒充源端提供的秒级成交时间。
缺字段仍为 null，零量保留，不从收盘价补 OHL。当天日线始终单列 `partial_daily_bar`，
`last_closed_bar` 指向严格早于采集本地日的最后日线；这是保守关闭政策，不以今日收市钟点猜测最终修订。
少于20条关闭日线显式缺口。源指数成交量保持 `source_reported_volume`，不能当可交易指数股数。

`source/daily_source` 保存来源URL、符号、币种、单位、时区、取得时间、规范响应摘要、
unadjusted/price_index、first_observed 和 `historical_pit_verified=false`。
三市场各自报价日与时区独立，不套上海交易日给美国、香港加上日期异常。
本数据不能解锁六轴生产评分、历史PIT、回测或自动日程。

定点离线测试：`tests/research_web/test_global_market_indices.py`。真实公开源可用性、
离线测试、CI、认证页面和部署是不同证据，均须绑定各自执行身份。
