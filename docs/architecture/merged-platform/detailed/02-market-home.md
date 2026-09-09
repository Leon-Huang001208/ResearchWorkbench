# 全市场首页实施说明

## 职责

全市场首页只聚合事实，不放 AI 摘要、研究任务、自选、Agent 状态或系统健康。页面固定为全球背景、A 股状态、市场主线、重要事件、资产异动五个区块，共享同一个 `MarketHomeSnapshot` 时间语义。

## 接口与状态

| 接口 | 用途 | 关键规则 |
|---|---|---|
| `API-MKT-001 GET /api/market-home` | 当前交易日聚合读模型 | 返回 `200/206`；每个事实含来源、时间和新鲜度 |
| `API-MKT-002 GET /api/market-home/snapshots/{trading_day}` | 历史页面 | 只读取不可变 close 快照 |
| `API-MKT-003 GET /api/market-home/events` | 区块失效 SSE | 只推区块修订号，客户端重读聚合接口 |

交易状态严格使用 `pre_open/open/lunch_break/closed/non_trading_day`。盘中读取 live 投影，盘后生成不可变快照。行情 SLA 为 30 秒、聚合 60 秒、事件 15 秒；超时展示 `stale/unavailable`，不伪造零值。

## 市场主线

主线规则版本化保存，输入为涨幅、成交额相对 20 日中位数、上涨家数占比和已验证事件密度。各分项先按同行百分位归一，再生成 `leading/weakening` 排名；API 必须同时返回总分、分项、规则版本和样本范围。

## 实施图

- `D01-01`：功能和页面职责。
- `D01-02`：接口、Service、Repository 和表所有权。
- `D01-03`：当前首页请求与 SSE 失效时序。
- `D01-04`：交易日和 close 快照状态机。
- `D01-05`：来源、质量门、主线计算和读模型数据流。

