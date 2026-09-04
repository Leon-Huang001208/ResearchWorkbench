# Research Workbench 数据源架构设计

## 概述

Research Workbench 不是简单的"爬虫系统"，而是**多源证据融合 + 事件驱动投研 + 量化验证系统**。

核心原则：

```
巨潮告诉你：公司正式发生了什么（事实）
知丘告诉你：市场和研究员怎么理解（认知）
新闻告诉你：什么时候开始扩散（催化）
Wind 告诉你：基本面数据是否支持（基本面）
天软告诉你：最终有没有赚钱（交易验证）
AKShare 告诉你：免费也能先跑起来（低成本底座）
```

---

## 数据源六层分类

```text
A. 官方披露层（Official Disclosure）
   - 巨潮资讯网 / 交易所公告
   - 内容：公告、年报、季报、回购、减持、定增、重组、处罚、诉讼、重大合同
   - 定位：事实锚点 / Event Ground Truth
   - 可信度：最高

B. 研究解释层（Research & Interpretation）
   - 知丘研报 / 公众号 / 会议纪要
   - 内容：行业逻辑、产业链映射、专家观点、预期差、催化剂
   - 定位：解释层 / Thesis Layer / Impact Path
   - 可信度：需交叉验证
     - 正式研报 → 高可信度
     - 会议纪要 → 中可信度，标注"非公开信息"
     - 公众号文章 → 参考级，偏向媒体观点

C. 实时催化层（Real-Time Catalyst）
   - 财联社 / 中国证券网 / 新闻快讯
   - 内容：市场催化、热点、情绪、事件扩散时间线
   - 定位：Trigger / Sentiment / Timeline
   - 可信度：快但噪声大

D. 免费结构化数据层（Free Structured Data）
   - AKShare / 深证信 / 中证指数网 / 国证指数网
   - 内容：行情、指数、成分股、估值、行业分类、基础财务
   - 定位：免费数据补充 / MVP 数据底座
   - 可信度：中等，作为 Wind 不可用时的主力

E. 专业终端数据层（Professional Terminal Data）
   - Wind / iFinD
   - 内容：高质量财务、行情、宏观、行业、估值、一致预期、机构预测
   - 定位：标准化金融数据库 / 机构级校验源
   - 可信度：高

F. 量化与高频数据层（Quant & High-Frequency Data）
   - 天软 / 交易所行情库
   - 内容：Tick / 分钟线 / 复权行情 / 因子库
   - 定位：回测底座 / 因子底座 / 量化研究底座
   - 可信度：最高（量化级精度）
```

---

## 核心设计：双层证据 + 多源关联

### 事件对象数据模型

同一个事件，关联多类证据源：

```json
{
  "event_id": "evt_20260520_001",
  "event_type": "major_contract",
  "subject_id": "300xxx.SZ",
  "event_date": "2026-05-20",
  "official_sources": ["cninfo_announcement_xxx"],
  "research_sources": ["zq_report_xxx"],
  "meeting_sources": ["zq_minutes_xxx"],
  "media_sources": ["zq_wechat_xxx", "cls_news_xxx"],
  "structured_sources": ["wind_financial_xxx"],
  "market_reaction_sources": ["tinysoft_event_window_xxx"],
  "impact_path": [
    "公司中标储能项目",
    "订单确认收入预期提升",
    "储能系统集成景气度改善",
    "PCS/温控/消防供应链扩散"
  ],
  "confidence": 0.86
}
```

### 各数据源在事件中的角色

```text
巨潮公告 → official_evidence     = true, confidence_boost = high
知丘研报 → research_evidence     = true, contains_thesis  = true
知丘纪要 → meeting_evidence      = true
知丘公众号 → media_evidence       = true
新闻快讯 → catalyst_evidence     = true
Wind    → structured_evidence    = true
天软    → market_reaction_evidence = true
```

---

## 具体案例：一个"重大合同"事件的完整传导

```text
巨潮公告：
  某公司披露中标 8 亿元储能项目

知丘研报：
  该订单说明公司从设备供应商转向系统集成商，毛利率可能改善

知丘公众号：
  储能板块开始扩散，市场关注 PCS、电池、温控、消防

知丘会议纪要：
  专家说下游需求排产超预期，二季度订单可能继续释放

Wind 数据验证：
  公司当前 PE 处于历史 30% 分位，ROE 连续两个季度改善
  一致预期未来两年营收增速 25%+

天软回测验证：
  公告后 T+1 涨幅 5.2%
  T+5 超额收益（vs 沪深300）8.1%
  成交额放大 2.5 倍
  同类事件历史胜率 62%，T+5 平均超额 3.4%
  但高估值分位下胜率下降至 48%

系统输出：
  事件置信度 0.86
  影响路径：个股 → 储能系统集成 → PCS/温控/消防供应链
  历史验证：该类事件有正超额收益，当前估值分位风险可控
```

---

## 数据管道架构

```text
                         ┌────────────────────┐
                         │     事件 / 主题     │
                         └─────────┬──────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
  官方事实层                  研究解释层                  实时催化层
  巨潮 / 交易所               知丘研报/公众号/纪要          财联社 / 新闻
        │                          │                          │
        └──────────────┬───────────┴──────────────┬───────────┘
                       ▼                          ▼
                文档知识层                   事件抽取层
           Markdown / Chunk / RAG       Assertion / Event / Evidence
                       │                          │
                       └──────────┬───────────────┘
                                  ▼
                           事件知识库
                                  │
                                  │  evidence_linking
                                  │  （按公司、行业、主题、时间窗口关联）
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
      Wind 结构化财务        天软量价行情          AKShare/深证信补充
      估值/财务/预期         回测/因子/交易过滤      免费数据/MVP
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  ▼
                           信号 / 回测 / 前端
```

---

## 数据源到模块/表的映射

```text
巨潮
  → documents
  → document_chunks
  → assertions
  → events
  → evidence_links

知丘
  → documents
  → document_chunks
  → assertions
  → events
  → theses
  → evidence_links
  → impact_paths

Wind
  → market_data_daily
  → financial_statements
  → valuation_metrics
  → consensus_forecasts
  → index_constituents
  → industry_classification
  → factor_inputs

天软
  → price_bars_daily
  → price_bars_intraday
  → tick_data
  → limit_status
  → suspension_status
  → adjusted_prices
  → event_window_returns
  → backtest_prices
```

---

## Wind 接入设计

### 定位

```text
Wind = Structured Financial Truth
```

Wind 不负责解释事件，但负责回答：

```text
- 这个公告事件发生前，公司估值贵不贵？
- 这个研报逻辑是否和财务趋势一致？
- 这个主题扩散后，行业指数有没有确认？
- 一致预期和实际业绩偏差有多大？
```

### 接入方式

Wind 不是爬虫，而是 **Adapter / Connector**：

```text
data_layer/adapters/wind/

WindAdapter
  ├── daily_quotes
  ├── financial_statements
  ├── valuation
  ├── consensus_forecast
  ├── industry_classification
  ├── index_constituents
  ├── fund_flow
  └── macro_data
```

### 服务模块

```text
个股页：
  - PE/PB/PS/ROE/毛利率/净利率
  - 营收/利润/现金流
  - 机构一致预期
  - 行业分类
  - 历史估值分位

信号实验室：
  - 价值因子 / 质量因子 / 成长因子
  - 动量因子 / 波动率因子 / 资金流因子

回测：
  - 日频行情 / 复权价格
  - 指数基准 / 行业中性
  - 停牌/涨跌停过滤
```

---

## 天软接入设计

### 定位

```text
天软 = Quant Data / Backtest Engine Data Source
```

天软不适合做 RAG，也不适合直接做事件解释。它最适合支撑：

### 事件研究

```text
- 公告日 T0
- T+1 / T+3 / T+5 / T+20 收益
- 相对行业收益 / 相对沪深300/中证500收益
- 成交额放大倍数 / 换手率变化
- 是否涨停 / 是否一字板 / 是否可买入
```

### 择时

```text
- 量价因子 / 资金行为
- 板块扩散 / 市场宽度 / 拥挤度
```

### 接入位置

```text
data_layer/adapters/tinysoft/
signal_lab/features/
signal_lab/labels/
signal_lab/backtests/
timing_engine/
```

---

## 数据源冲突解决规则

当多个源提供同一数据时：

| 数据类型 | 优先级 | 说明 |
|----------|--------|------|
| 日行情 | Wind > 天软 > AKShare | Wind 作为金融数据库优先 |
| 复权价格 | 天软 > Wind | 天软复权更精确 |
| 财务报表 | Wind > AKShare | Wind 数据质量更高 |
| 估值指标 | Wind > AKShare | 同上 |
| 行业分类 | Wind > 申万 > 中信 | 按研究需求可配置 |
| 指数成分股 | 中证/国证指数网 > Wind | 官方来源优先 |
| 分钟/Tick | 天软独占 | 只有天软提供 |

---

## 数据源优先级（实施路线）

### P0：知丘已有数据源跑通 ✅

```text
- 研报 / 公众号 / 会议纪要
- AKShare：行情 / 财务 / 指数 / 行业
- 现有 ingestion / event / RAG / 前端
```

知丘已经在框架里，能最快产生"AI 投研"的内容价值。

### P1：巨潮公告接入

```text
- 公告元数据 / Dashboard 实时监控 ✅
- PDF 下载 / Markdown/文本转换能力 ✅
- DocumentEnvelope 正文增强 / DocumentV1 入口 ✅
- 公告事件抽取 / 官方证据链回补 API ✅
```

巨潮补"事实可靠性"。当前巨潮注册源默认开启 `fetch_attachment_text=True`，
采集公告列表后会下载 PDF 附件并做 Markdown/文本转换；通过 `timeout`、
`max_attachment_bytes` 和 `trust_env=False` 控制下载风险。已有 `DocumentV1`
可通过 `/api/assets/official-evidence/backfill-cninfo` 触发 KnowledgePipeline
回补，生成官方事件证据。

### P2：知丘 + 巨潮 Evidence Linking

```text
- 同公司 / 同行业 / 同主题 / 同事件窗口
- 事件对象增加 official_evidence、research_evidence、meeting_evidence、media_evidence 字段
- impact_path 传导链条
```

这是系统区别于普通爬虫系统的核心能力。

### P3：Wind 接入

```text
- 日行情 / 财务报表 / 估值指标
- 行业分类 / 指数成分股 / 一致预期
```

Wind 补"结构化金融质量"。

### P4：天软接入

```text
- 高质量历史行情 / 复权价格 / 分钟线
- 涨跌停/停牌 / 事件窗口收益 / 回测可交易性
```

天软补"量化验证和真实回测"。

### P5：多源融合

```text
同一事件：
  巨潮官方公告
  + 知丘研报解释
  + 新闻催化
  + Wind 财务估值
  + 天软量价验证
```

---

## 前端展示设计

### 个股页

```text
600519.SH 贵州茅台

┌─ 官方公告 ─────────────────────────────┐
│  年度报告 / 分红公告 / 股东大会决议     │
└────────────────────────────────────────┘

┌─ 知丘研报 ─────────────────────────────┐
│  白酒行业深度：高端酒批价企稳           │
│  贵州茅台渠道改革跟踪                   │
└────────────────────────────────────────┘

┌─ 知丘公众号 ───────────────────────────┐
│  市场对春节动销的讨论                   │
│  渠道库存变化解读                       │
└────────────────────────────────────────┘

┌─ 会议纪要 ─────────────────────────────┐
│  白酒渠道专家交流纪要                   │
│  经销商反馈纪要                         │
└────────────────────────────────────────┘

┌─ 系统抽取事件 ─────────────────────────┐
│  分红提升 / 批价企稳 / 渠道库存下降     │
│  春节动销改善                           │
└────────────────────────────────────────┘

┌─ 财务估值（Wind） ─────────────────────┐
│  PE 28.5x | 历史分位 45%               │
│  ROE 32% | 一致预期营收增速 15%        │
└────────────────────────────────────────┘

┌─ 量价反应（天软） ─────────────────────┐
│  最新事件 T+5 超额 +2.3%               │
│  成交额变化 +180%                       │
└────────────────────────────────────────┘

┌─ 影响传导 ─────────────────────────────┐
│  贵州茅台 → 高端白酒 → 白酒指数         │
│  → 消费复苏主题                         │
└────────────────────────────────────────┘

┌─ 回测验证 ─────────────────────────────┐
│  同类事件历史胜率 58%                   │
│  T+5 平均超额 2.1%                     │
│  T+20 平均超额 4.3%                    │
└────────────────────────────────────────┘
```

---

## 关键设计原则

1. **文档型数据源**（巨潮、知丘、财联社、中国证券网）走 Document → Chunk → RAG → Event pipeline
2. **结构化数据源**（Wind、天软、AKShare）走 MarketData → FinancialData → Factor → Backtest pipeline
3. **事件对象是证据交汇点**：一个事件关联多源证据，而非每个源各自产生孤立事件
4. **巨潮不替代知丘，而是形成"官方事实 + 研究解释"的双层证据系统**
5. **Wind 作为 Adapter，不是 Crawler**
6. **天软不做 RAG 文档源**，只做行情、因子、回测、事件窗口收益
7. **AKShare 在 Wind 不可用时作为主力结构化数据源**，不只是"免费补充"

---

## 一句话总结各源定位

```text
巨潮 = 事实层       → "公司正式说了什么"
知丘 = 认知层       → "研究员和产业专家怎么解释"
新闻 = 催化层       → "市场什么时候开始反应"
Wind = 基本面层     → "财务、估值、预期是否支持"
天软 = 交易验证层   → "价格、成交、回测是否验证"
AKShare = 免费底座  → "低成本先把系统跑通"
```
