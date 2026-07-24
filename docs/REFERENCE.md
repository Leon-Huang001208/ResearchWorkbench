# AlphaFoundry 参考手册

## 目录

1. [CLI 命令](#cli-命令)
2. [REST API](#rest-api)
3. [Python API](#python-api)
4. [数据采集器](#数据采集器)
5. [信号实验室](#信号实验室)
6. [项目结构详解](#项目结构详解)
7. [常见问题](#常见问题)

---

## CLI 命令

### 0. data - 统一数据命令组（推荐）

**新增于 2026-06-02**。统一替代分散的 `af crawl` / `af ingest` / `af knowledge` 命令。

旧命令保留为别名，可继续使用但建议迁移。

#### `af data list` — 列出所有数据源

```bash
af data list
# 显示所有已注册的 connector 及支持的 datasets
```

#### `af data ingest` — 执行数据摄入

```bash
af data ingest --source cls --dataset telegram --days 2
af data ingest -s akshare -d stock_daily --codes "600519.SH" --start-date 2026-01-01 --end-date 2026-06-01
af data ingest -s wind -d daily_quotes --codes "600519.SH" --days 5
af data ingest -s cnstock -d news --max-items 50
```

| 参数 | 必需 | 说明 |
|------|------|------|
| `--source`, `-s` | ✅ | 数据源标识（cls, akshare, wind, cnstock, zq, yahoo） |
| `--dataset`, `-d` | ✅ | 数据集（telegram, news, flash, stock_daily, daily_quotes, ...） |
| `--start-date` | ❌ | 开始日期 YYYY-MM-DD |
| `--end-date` | ❌ | 结束日期 YYYY-MM-DD |
| `--codes` | ❌ | 证券代码，逗号分隔 |
| `--days` | ❌ | 最近 N 天（与 start-date/end-date 互斥） |
| `--max-items` | ❌ | 最大抓取数量 |

#### `af data backfill` — 历史数据回填

```bash
af data backfill -s cls --days 30
```

#### `af data validate` — 校验已有数据

```bash
af data validate -s akshare -d stock_daily
af data validate -s wind -d daily_quotes --start-date 2026-05-01
```

#### `af data status` — 查看数据状态

```bash
af data status              # 所有数据源概览
af data status -s akshare   # 单个数据源详情
```

#### `af data file` — 摄入单个文件

```bash
af data file -f report.pdf -t report -s "券商研报"
```

#### `af data schedule` — 采集调度器管理

```bash
af data schedule start      # 启动后台调度器
af data schedule stop       # 停止调度器
af data schedule status     # 查看调度器状态
```

#### `af data workers` — 知识加工 Worker 管理

```bash
af data workers start       # 启动 Worker（默认 1 个）
af data workers start -n 4  # 启动 4 个 Worker
af data workers stop        # 停止所有 Worker
af data workers status      # 查看 Worker 状态
```

---

### 1. analyze - 资产分析

生成资产分析快照。

#### 基本用法

```bash
af analyze --asset <资产代码>
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--asset` | ✅ | 资产代码，例如：600000.SH, 000001.SZ |
| `--output`, `-o` | ❌ | 输出文件路径，支持 .md 和 .docx |
| `--as-of` | ❌ | 指定快照时间，ISO 格式，例如：2025-05-10 |
| `--use-mock` / `--no-mock` | ❌ | 是否使用模拟数据，默认 `--no-mock` |

#### 使用示例

```bash
# 基本分析
af analyze --asset 600000.SH

# 输出报告
af analyze --asset 600000.SH --output report.md
```

---

### 2. scenario - 情景分析

生成多情景分析报告。

#### 基本用法

```bash
af scenario --topic <研究主题>
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--topic`, `-t` | ✅ | 研究主题，例如："人工智能产业发展" |
| `--output`, `-o` | ❌ | 输出文件路径，支持 .md |
| `--subject`, `-s` | ❌ | 主题 ID，可多次指定 |

#### 使用示例

```bash
af scenario --topic "人工智能产业发展对股票市场的影响"
af scenario --topic "美联储政策走向" --output scenario.md
```

---

### 3. ingest - 数据摄入

摄入文档并提取断言和事件。

#### 基本用法

```bash
af ingest --file <文件路径>
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--file`, `-f` | ✅ | 输入文件路径，支持 .pdf, .txt, .md |
| `--source-type`, `-t` | ❌ | 来源类型：report, news, filing, note |
| `--source-name`, `-s` | ❌ | 来源名称，例如："券商研报" |
| `--title` | ❌ | 文档标题 |

#### 使用示例

```bash
af ingest --file report.pdf --source-type report --source-name "券商研报"
```

---

### 4. signal - 信号管理

管理投资信号。

#### 子命令

- `signal create` - 创建信号
- `signal list` - 列出信号
- `signal validate` - 验证信号
- `signal promote` - 升级信号状态
- `signal candidate` - 生成交易候选

#### 使用示例

```bash
# 创建信号
af signal create --asset 600519.SH --thesis "白酒行业景气度回升" --confidence 0.8

# 列出信号
af signal list --status draft

# 验证信号
af signal validate --signal-id signal_123

# 升级信号
af signal promote --signal-id signal_123 --to-status review
```

---

### 5. review - 审核管理

管理审核队列。

#### 子命令

- `review list` - 列出待审核项目
- `review approve` - 批准断言/事件/信号
- `review reject` - 拒绝断言/事件/信号
- `review stats` - 查看审核统计

#### 使用示例

```bash
af review list
af review approve assertion_1234 --reviewer "研究员A"
af review stats
```

---

### 6. backtest - 回测

运行信号回测。

#### 基本用法

```bash
af backtest --signal <信号ID> --initial-capital 1000000
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--signal` | ✅ | 信号 ID |
| `--initial-capital` | ❌ | 初始资金，默认 1000000 |
| `--start-date` | ❌ | 回测开始日期 |
| `--end-date` | ❌ | 回测结束日期 |

#### 使用示例

```bash
af backtest --signal signal_123 --initial-capital 1000000
```

---

### 7. report - 报告生成

生成各类研究报告。

#### 子命令

- `report asset` - 资产分析报告
- `report valuation` - 估值报告
- `report weekly` - 每周回顾报告
- `report full` - 完整研究报告

#### 使用示例

```bash
af report asset --asset 600519.SH --output asset_report.md
af report weekly --output weekly_review.md
af report full --asset 600519.SH --output full_report.md
```

---

### 8. akshare - AKShare 数据管理

管理 AKShare 数据源。

#### 子命令

- `akshare quotes` - 获取行情数据
- `akshare financial` - 获取财务数据
- `akshare news` - 获取新闻数据
- `akshare stock-list` - 获取股票列表

#### 使用示例

```bash
af akshare quotes --asset 600519.SH --start-date 2025-01-01
af akshare financial --asset 600519.SH
af akshare news --asset 600519.SH --limit 10
```

---

### 9. memory - 记忆管理

管理学习记忆。

#### 子命令

- `memory episode` - 记录市场事件
- `memory failure` - 记录失败案例
- `memory search` - 搜索相似案例
- `memory weekly` - 生成每周回顾

#### 使用示例

```bash
af memory search --thesis "新能源销量超预期" --limit 5
af memory weekly --output weekly_review.md
```

---

### 10. timing - 择时分析

运行择时分析。

#### 使用示例

```bash
af timing --signal signal_123
```

---

### 11. knowledge - Knowledge Worker 管理

管理知识加工 Worker 进程的启停和状态查询。

#### 子命令

- `knowledge start` - 启动 Knowledge Worker（后台独立进程）
- `knowledge stop` - 停止 Knowledge Worker（SIGTERM 优雅关闭）
- `knowledge status` - 查看 Worker 状态（PID、心跳）

#### 使用示例

```bash
# 启动 Knowledge Worker
af knowledge start

# 查看状态
af knowledge status

# 停止 Knowledge Worker
af knowledge stop
```

#### 配置环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KNOWLEDGE_WORKER_POLL_INTERVAL` | 3 | 轮询间隔（秒） |
| `KNOWLEDGE_WORKER_BATCH_SIZE` | 10 | 每批出队数量 |
| `KNOWLEDGE_WORKER_MAX_CONCURRENCY` | 8 | item 级并发数 |
| `KNOWLEDGE_WORKER_SHUTDOWN_TIMEOUT` | 30 | 优雅关闭超时（秒） |

---

### 12. seed_factor_data - 因子数据播种

种子数据管线脚本，为因子研究系统播种市场数据、财务数据和因子定义。

#### 基本用法

```bash
# AKShare only (default, with rate limiting)
python scripts/seed_factor_data.py --stock-count 200

# Wind WSD (fast, requires Wind Excel plugin)
python scripts/seed_factor_data.py --stock-count 200 --source wind

# Auto (Wind first, fallback to AKShare)
python scripts/seed_factor_data.py --stock-count 200 --source auto
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--stock-count` | ❌ | 播种股票数量，默认 200 |
| `--symbols` | ❌ | 逗号分隔的特定股票代码，如 `600519.SH,000858.SZ` |
| `--source` | ❌ | 日行情数据源：`akshare`（默认）、`wind`（Wind Excel 插件）、`auto`（Wind 优先，不可用时降级 AKShare） |
| `--delay` | ❌ | API 请求间延迟（秒），默认 2.0，用于限流控制 |
| `--max-retries` | ❌ | 每次 AKShare API 调用最大重试次数，默认 3 |
| `--resume` | ❌ | 断点续传 JSON 文件路径，从中断处恢复 |
| `--date-start` | ❌ | 日行情起始日期 (YYYY-MM-DD)，默认 2024-01-01 |
| `--date-end` | ❌ | 日行情截止日期 (YYYY-MM-DD)，默认 2026-05-31 |
| `--skip-ingest` | ❌ | 跳过 Phase 1（数据已存在于 DB） |
| `--no-akshare-direct` | ❌ | 使用摄入服务而非直接 AKShare 调用 |
| `--skip-financials` | ❌ | 跳过 Phase 3（财务数据和 VALUE/QUALITY/GROWTH 因子） |

#### 使用示例

```bash
# 控制 AKShare 限流
python scripts/seed_factor_data.py --stock-count 200 --delay 3.0 --max-retries 5

# 断点续传（中断后恢复）
python scripts/seed_factor_data.py --stock-count 200 --source auto
# Ctrl+C 中断后:
python scripts/seed_factor_data.py --stock-count 200 --source auto --resume .ai/checkpoints/seed_auto_200.json

# 纯 Wind 数据源 + 特定股票
python scripts/seed_factor_data.py --symbols 600519.SH,000858.SZ --source wind

# 仅计算因子（跳过数据摄入）
python scripts/seed_factor_data.py --skip-ingest
```

#### 断点续传机制

- Wind/auto 模式自动生成 checkpoint 文件到 `.ai/checkpoints/`
- 每 10 只股票保存一次，支持 Ctrl+C 中断后恢复
- checkpoint 记录已完成股票列表和已保存行数
- 手动断点路径通过 `--resume` 指定

#### 重试策略

- **AKShare**: 指数退避重试（5s → 10s → 20s → 40s，上限 60s）
- **限流检测**: 自动识别 "频率"/"rate limit"/"429"/"throttle" 关键词，限流时额外等待 10s×attempt
- **Wind WSD**: 3 次重试（3s → 6s → 12s，上限 30s），根据日期跨度动态调整超时

---

## REST API

### 基础信息

- **Base URL**: `http://localhost:8000`
- **API 文档**: `http://localhost:8000/docs`
- **健康检查**: `http://localhost:8000/health`

### 认证

当前版本无需认证。

---

### 仪表盘 API

#### GET /api/dashboard

获取仪表盘数据。

**响应示例**:

```json
{
  "summary": {
    "total_documents": 1234,
    "total_events": 567,
    "total_signals": 89,
    "pending_reviews": 12
  },
  "recent_news": [...],
  "market_status": {...},
  "top_signals": [...]
}
```

---

### 搜索 API

#### POST /api/search

全局搜索。

**请求体**:

```json
{
  "query": "新能源",
  "types": ["event", "signal", "document"],
  "limit": 20
}
```

**响应示例**:

```json
{
  "results": [
    {
      "type": "event",
      "id": "event_123",
      "title": "新能源销量超预期",
      "relevance": 0.95
    }
  ]
}
```

---

### 资产分析 API

#### POST /api/assets/analysis-card

生成资产分析卡片，包含基本信息、K线、成交量、MACD、资金流向、股东、财务、行业、事件和宏观敏感性等数据。

**请求体**:

| 字段 | 必需 | 说明 |
| --- | --- | --- |
| `canonical_id` | ✅ | 资产代码，例如 `600519.SH` |
| `as_of` | ❌ | 指定分析时间，ISO 格式 |
| `time_range` | ❌ | K线时间范围：`1M` / `3M` / `6M` / `1Y` / `2Y` / `3Y` / `5Y` / `ALL`，默认 `1Y` |

**请求示例**:

```json
{
  "canonical_id": "600519.SH",
  "time_range": "2Y"
}
```

**响应示例**:

```json
{
  "canonical_id": "600519.SH",
  "as_of": "2026-06-03T00:00:00Z",
  "current_price": 1600.0,
  "price_bars": [
    {
      "date": "2026-06-03",
      "open": 1580.0,
      "high": 1610.0,
      "low": 1570.0,
      "close": 1600.0,
      "volume": 1000000,
      "ma5": 1590.0,
      "boll_upper": 1660.0,
      "macd_dif": 1.25
    }
  ],
  "financial": {...},
  "capital_flow": {...}
}
```

#### GET /api/assets/{canonical_id}

获取资产最新分析快照。

---

### 基金智能 API

#### POST /api/funds/ingest

导入结构化基金 rows。当前支持 `master`、`nav`、`holdings`、`managers` 四类数据集；CSV 文件导入由服务层 `FundDataIngestionService.ingest_csv()` 或后续脚本/管理页调用。

**请求示例**:

```json
{
  "dataset": "master",
  "source": "api",
  "rows": [
    {
      "symbol": "000001.OF",
      "name": "Alpha Growth",
      "fund_type": "equity",
      "latest_size": "12.5"
    }
  ]
}
```

**响应示例**:

```json
{
  "run_id": "3db1f1a2-4cc4-4754-81bc-9b0d33f7f7ad",
  "dataset": "master",
  "fetched": 1,
  "saved": 1
}
```

#### GET /api/funds/{symbol}

获取基金详情，包含基金主数据、最新净值、收益风险指标、基金经理和最新披露持仓。

**响应示例**:

```json
{
  "master": {
    "symbol": "000001.OF",
    "name": "Alpha Growth",
    "fund_type": "equity"
  },
  "latest_nav": {
    "symbol": "000001.OF",
    "trading_day": "2026-06-24",
    "unit_nav": 1.2,
    "accumulated_nav": 1.5
  },
  "performance": {
    "total_return": 0.2,
    "max_drawdown": -0.05
  },
  "latest_holdings": []
}
```

#### GET /api/funds/{symbol}/exposure

根据基金最新披露持仓返回单基金股票、行业和主题暴露。

#### POST /api/funds/portfolio/exposure

按基金组合权重计算底层股票、行业和主题穿透。

**请求示例**:

```json
{
  "positions": {
    "000001.OF": 0.6,
    "000002.OF": 0.4
  }
}
```

---

### 报告项目 API

报告项目 API 管理 `report_projects/<项目名>/` 下的一组项目资产：Word 模板、Excel 底稿、`section_config.yaml`、可选 `prompt_templates.md`、生成目录和运行日志目录。

#### GET /api/report-projects/

列出所有报告项目。

**响应字段要点**:

| 字段 | 说明 |
| --- | --- |
| `word_placeholders` | 从 Word 正文、页眉、页脚 XML 中按首次出现顺序提取的占位符 |
| `section_config` | 解析后的 YAML 配置 |
| `section_config_source` | 原始 YAML 文本，可在工作台编辑 |
| `prompt_templates_source` | 原始 Markdown Prompt 模板文本 |
| `excel_sheets` | Excel 工作表维度和样例单元格摘要 |
| `generated_reports` | 已生成 DOCX 列表 |

#### PUT /api/report-projects/{slug}/source

保存报告项目源码文件。

**请求体**:

```json
{
  "source_kind": "prompt_templates",
  "content": "# Prompt 模板库\n\n## 人工智能\n```text\n检索 Query：人工智能 新闻\n\n写作要求：严格依据 evidence。\n```"
}
```

`source_kind` 支持：

| 值 | 写入文件 |
| --- | --- |
| `section_config` | 项目的 `section_config.yaml` |
| `prompt_templates` | 项目的 `prompt_templates.md`；如果项目尚未绑定，会创建 `config/prompt_templates.md` 并写回 `project.yaml` |

#### POST /api/report-projects/{slug}/render

生成项目 DOCX。

默认 `generate_from_config=true`，后端会按以下顺序执行：

```text
section_config.yaml
→ prompt_templates.md
→ evidence 检索
→ ModelGateway 生成占位符正文
→ Word 占位符替换
→ 图表生成和 DOCX 图片嵌入
→ runs/*.json 运行日志
```

**请求体**:

```json
{
  "placeholders": {
    "title": "华安ETF周报"
  },
  "generate_from_config": true,
  "lookback_days": 7
}
```

| 字段 | 必需 | 说明 |
| --- | --- | --- |
| `placeholders` | ❌ | 手工占位符覆盖值；非空值优先于自动生成 |
| `generate_from_config` | ❌ | 是否从 YAML + Prompt 模板自动生成，占默认 `true` |
| `lookback_days` | ❌ | evidence 检索窗口，1-90 天，默认 7 |

**响应示例**:

```json
{
  "success": true,
  "project_name": "华安ETF周报",
  "file_name": "2026-06-08_153000_华安ETF周报.docx",
  "download_url": "/api/report-projects/华安ETF周报/download/2026-06-08_153000_华安ETF周报.docx",
  "preview_url": "/api/report-projects/华安ETF周报/preview/2026-06-08_153000_华安ETF周报.docx",
  "generated_placeholder_count": 21,
  "evidence_count": 42,
  "warnings": []
}
```

#### GET /api/report-projects/{slug}/preview/{file_name}

把已生成 DOCX 转换为轻量 HTML 预览。预览支持正文段落、表格和图片；它用于快速检查内容，不替代最终 Word 版式验收。

#### GET /api/report-projects/{slug}/download/{file_name}

下载已生成 DOCX。

---

### 数据摄入 API

#### POST /api/ingest/file

上传文件并摄入。

**请求体**: `multipart/form-data`

- `file`: 文件
- `source_type`: 来源类型
- `source_name`: 来源名称

**响应示例**:

```json
{
  "status": "success",
  "document_id": "doc_123",
  "extracted_assertions": 5,
  "extracted_events": 2
}
```

#### POST /api/ingest/pull-sources

从实时源拉取数据。

**响应示例**:

```json
{
  "status": "success",
  "ingested_count": 45
}
```

---

### 事件 API

#### GET /api/events

获取事件列表。

**查询参数**:

- `event_type`: (可选) 事件类型过滤
- `limit`: (可选) 返回数量限制
- `offset`: (可选) 分页偏移

#### GET /api/events/{event_id}

获取单个事件详情。

#### POST /api/events/{event_id}/approve

批准事件。

#### POST /api/events/{event_id}/reject

拒绝事件。

#### POST /api/events/{event_id}/generate-signal

从事件生成信号。

---

### 信号 API

#### GET /api/signals

获取信号列表。

**查询参数**:

- `status`: (可选) 状态过滤
- `limit`: (可选) 返回数量限制

#### GET /api/signals/{signal_id}

获取单个信号详情。

#### POST /api/signals

创建信号。

**请求体**:

```json
{
  "subject_id": "600519.SH",
  "thesis": "白酒行业景气度回升",
  "confidence": 0.8,
  "horizon": "20d"
}
```

#### POST /api/signals/{signal_id}/validate

验证信号。

#### POST /api/signals/{signal_id}/promote

升级信号状态。

---

### 回测 API

#### POST /api/backtest/signal

运行信号回测。

**请求体**:

```json
{
  "signal_id": "signal_123",
  "initial_capital": 1000000,
  "start_date": "2025-01-01",
  "end_date": "2025-05-10"
}
```

**响应示例**:

```json
{
  "total_return": 0.15,
  "annual_return": 0.35,
  "sharpe_ratio": 1.8,
  "max_drawdown": 0.08,
  "win_rate": 0.62
}
```

---

### 信号实验室 API

#### POST /api/signal-lab/features

计算特征。

**请求体**:

```json
{
  "asset_id": "600519.SH",
  "feature_groups": ["price_volume", "valuation"],
  "start_date": "2025-01-01",
  "end_date": "2025-05-10"
}
```

#### POST /api/signal-lab/labels

计算标签。

#### POST /api/signal-lab/score-signal

信号评分。

---

### Wind Excel API

Wind Excel 适配器通过 xlwings → AppleScript → macOS Excel Wind 插件获取专业金融数据。所有端点以 `/api/wind` 为前缀。

#### GET /api/wind/health

检查 Wind Excel 连接状态。

**响应**:
```json
{
  "available": true,
  "message": "Wind 已连接"
}
```

#### POST /api/wind/consensus

获取一致预期数据（净利润、EPS、营收、目标价、评级）。

**请求**:
```json
{
  "codes": ["600519.SH"],
  "trade_date": "2025-06-01"
}
```

**响应**:
```json
{
  "success": true,
  "data": [{"code": "600519.SH", "trade_date": "2025-06-01", "cons_net_profit": 1e10, "cons_eps": 5.0}],
  "count": 1
}
```

#### POST /api/wind/margin-trading

获取融资融券数据。

**请求**:
```json
{
  "codes": ["600519.SH"],
  "start_date": "2025-06-01",
  "end_date": "2025-06-05"
}
```

#### POST /api/wind/block-trades

获取龙虎榜数据。请求格式同 margin-trading。

#### POST /api/wind/prices

获取日行情数据（OHLCV + adj_close + adj_factor + vwap + 振幅）。请求格式同 margin-trading。

#### POST /api/wind/financials

获取财务报表数据。

**请求**:
```json
{
  "codes": ["600519.SH"],
  "report_date": "2024-12-31",
  "statement_type": "annual"
}
```

#### POST /api/wind/industry

获取行业分类数据。

---

### 动态多因子 API

动态多因子 REST API 提供因子定义管理、因子值存取、因子评估查询和动态权重管理。所有端点以 `/api/factors` 为前缀。

#### GET /api/factors/definitions

列出已注册的因子定义。

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `category` | string | 按类别过滤 |
| `factor_ids` | string | 逗号分隔的因子 ID 列表 |

**响应**:
```json
{
  "success": true,
  "data": [{"factor_id": "pe_ttm", "name": "PE TTM", "category": "value", "direction": "negative"}],
  "count": 1
}
```

#### POST /api/factors/definitions

注册或更新因子定义。

**请求**:
```json
[{
  "factor_id": "pe_ttm",
  "name": "PE TTM",
  "category": "value",
  "direction": "negative",
  "description": "Trailing PE"
}]
```

#### GET /api/factors/values

查询因子值（支持点日期查询或范围查询）。

**查询参数**: `as_of_date`, `factor_ids`, `subject_ids`, `start_date`, `end_date`, `limit` (默认 10000)

#### POST /api/factors/values

批量存储因子值。

**请求**:
```json
{
  "values": [{"factor_id": "pe_ttm", "subject_id": "600519.SH", "as_of_date": "2024-12-31", "value": 25.5, "source": "wind"}]
}
```

#### GET /api/factors/evaluations

查询因子评估记录（IC, RankIC, decile spread 等）。

#### POST /api/factors/evaluations

批量存储因子评估指标。

#### GET /api/factors/weights/latest

获取最新的动态因子权重。查询参数: `metric` (默认 "rank_ic")。

#### POST /api/factors/weights

保存动态因子权重快照。

#### GET /api/factors/weights/history

查询动态权重历史。查询参数: `metric`, `limit` (默认 50)。

#### GET /api/factors/available-dates

获取有因子数据的日期列表。

#### GET /api/factors/categories

获取所有已注册的因子类别。例如: `["value", "momentum", "quality", "growth"]`

**请求**:
```json
{
  "codes": ["600519.SH"]
}
```

#### POST /api/wind/fund-flow

获取资金流向数据。请求格式同 margin-trading。

#### POST /api/wind/holders

获取持有人数据。

**请求**:
```json
{
  "codes": ["600519.SH"],
  "report_date": "2024-12-31"
}
```

---

### 结果日志 API

#### GET /api/outcomes

获取结果列表。

#### POST /api/outcomes

记录结果。

**请求体**:

```json
{
  "signal_id": "signal_123",
  "outcome": "win",
  "return_pct": 0.08,
  "notes": "按计划止盈"
}
```

#### GET /api/outcomes/similar

搜索相似案例。

**查询参数**:

- `thesis`: 论点文本
- `limit`: 返回数量限制

---

### 记忆 API

#### GET /api/memory/failures

获取失败记忆。

#### GET /api/memory/episodes

获取市场事件记忆。

#### POST /api/memory/weekly-report

生成每周回顾报告。

---

### 治理 API

#### GET /api/governance/audit-log

获取审计日志。

#### GET /api/governance/versions

获取版本历史。

---

### 监控 API

#### GET /api/monitoring/health

获取健康状态。

#### GET /api/monitoring/metrics

获取监控指标。

#### GET /api/monitoring/alerts

获取告警列表。

---

### 系统 API

#### GET /api/system/health

获取系统健康状态，包含队列深度、Worker 心跳和数据库状态。

**响应示例**:

```json
{
  "status": "ok",
  "queue_depth": 42,
  "pending": 30,
  "processing": 8,
  "completed": 1234,
  "failed": 3,
  "worker_heartbeats": {
    "knowledge_worker": "2025-05-19T10:30:00Z"
  },
  "timestamp": "2025-05-19T10:30:05Z"
}
```

#### GET /api/system/health/minimal

轻量健康检查，不查询数据库，仅返回 Worker 心跳。

**响应示例**:

```json
{
  "status": "ok",
  "worker_heartbeats": {
    "knowledge_worker": "2025-05-19T10:30:00Z"
  },
  "timestamp": "2025-05-19T10:30:05Z"
}
```

#### GET /api/system/workers/status

聚合返回所有后台 Worker 的实时状态和队列统计，用于 Dashboard 监控面板。

**响应示例**:

```json
{
  "workers": [
    {
      "name": "knowledge_worker",
      "type": "knowledge",
      "pid": 68198,
      "alive": true,
      "last_heartbeat": null,
      "activity": null
    }
  ],
  "scheduler": {
    "name": "crawl_scheduler",
    "pid": 39323,
    "alive": true,
    "last_heartbeat": null,
    "activity": null
  },
  "queue_stats": {
    "pending": 2735,
    "processing": 58,
    "completed": 463,
    "failed": 1
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `workers` | array | Knowledge Worker 列表，PID 文件检测活性 |
| `workers[].name` | string | Worker 名称 |
| `workers[].type` | string | Worker 类型（`knowledge`） |
| `workers[].pid` | int\|null | 进程 PID |
| `workers[].alive` | bool | 进程是否存活 |
| `workers[].last_heartbeat` | number\|null | 最后心跳时间戳（跨进程为 null，Phase 2 支持） |
| `workers[].activity` | string\|null | 当前活动描述 |
| `scheduler` | object | Crawl Scheduler 状态 |
| `queue_stats` | object | 摄入队列统计 |
| `processing_stats` | object | 处理统计（今日/7天/30天/总计/昨日同期/7日均值） |

#### GET /api/system/status-bar

获取仪表盘状态栏动态数据（git 分支、数据库类型、LLM provider、文档数等）。

**响应示例**:

```json
{
  "git_branch": "master",
  "db_type": "postgresql",
  "llm_provider": "deepseek-v4-flash",
  "document_count": 12345,
  "error_count": 3,
  "warning_count": 12
}
```

---

### Knowledge Worker API

管理 Knowledge Worker 进程（`workers/knowledge_worker.py`）的启停和状态查询。

#### GET /api/knowledge/status

获取 Knowledge Worker 运行状态。

**响应示例**:

```json
{
  "available": true,
  "running": true,
  "pid": 12345,
  "pid_file": "/path/to/logs/knowledge_worker.pid"
}
```

#### POST /api/knowledge/start

启动 Knowledge Worker 进程（后台子进程）。

**响应示例**:

```json
{
  "success": true,
  "message": "Knowledge worker process started"
}
```

#### POST /api/knowledge/stop

停止 Knowledge Worker 进程（发送 SIGTERM）。

**响应示例**:

```json
{
  "success": true,
  "message": "Knowledge worker stopped",
  "pid": 12345
}
```

---

### 实时 API

#### GET /api/realtime/stream

SSE (Server-Sent Events) 端点，推送实时系统事件到前端。

**事件类型**:

| 事件类型 | 说明 |
|----------|------|
| `document_parsed` | 文档处理完成 |
| `event_created` | 新事件创建 |
| `assertion_created` | 新断言创建 |
| `queue_status` | 队列状态更新 |
| `worker_heartbeat` | Worker 心跳 |

**使用示例**:

```javascript
const evtSource = new EventSource('/api/realtime/stream');
evtSource.addEventListener('event_created', (e) => {
  const data = JSON.parse(e.data);
  console.log('New event:', data);
});
```

---

### PDF Admin API

PDF 转换管理接口，支持三种策略自动降级 (MinerU → MarkItDown → RawText)。

#### POST /api/admin/pdf/convert

触发指定 PDF 的转换。

**请求体**:

```json
{
  "pdf_id": "pdf_001",
  "strategy": "auto"
}
```

**参数说明**:

| 参数 | 必需 | 说明 |
|------|------|------|
| `pdf_id` | ✅ | PDF artifact ID |
| `strategy` | ❌ | 首选策略: `auto`, `mineru`, `markitdown`, `raw_text` (默认 `auto`) |

**响应示例**:

```json
{
  "pdf_id": "pdf_001",
  "success": true,
  "strategy_used": "mineru",
  "error_message": "",
  "page_count": 5,
  "token_count": 1000,
  "quality_score": 0.85,
  "has_tables": true,
  "has_images": false,
  "has_code_blocks": true
}
```

#### GET /api/admin/pdf/stats

获取 PDF 转换统计。

**响应示例**:

```json
{
  "total_pdfs": 10,
  "pending_conversion": 3,
  "converted": 5,
  "failed_conversion": 2,
  "by_status": {"success": 5, "error": 2, "pending": 3}
}
```

#### GET /api/admin/pdf/pending

列出待转换的 PDF。

**查询参数**:

- `limit`: 返回数量上限 (默认 50, 最大 200)

**响应示例**:

```json
{
  "items": [
    {
      "pdf_id": "pdf_001",
      "file_name": "report.pdf",
      "source_type": "zhiqiu_reports",
      "conversion_strategy": "",
      "status": "pending",
      "created_at": "2025-05-10T00:00:00"
    }
  ],
  "count": 1
}
```

> 注意：待转换列表直接查询 `pdf_artifact_v1` 表，字段名使用 `parse_version`（映射为 `conversion_strategy`）和 `parse_status`（映射为 `status`）。

#### POST /api/admin/pdf/retry

重试失败的 PDF 转换。

**请求体**:

```json
{
  "limit": 10
}
```

**参数说明**:

- `limit`: 每次重试的最大数量 (1-100, 默认 10)

**响应示例**:

```json
{
  "total": 2,
  "success": 1,
  "failed": 1,
  "results": [...]
}
```

---

### 市场数据 API

Market Data API 提供股票结构化数据的同步和查询接口，由 `app/api/routes/market_data.py` 实现。

#### POST /api/market-data/stocks/sync

同步股票列表到 `stock_master` 表。

**请求体**:

```json
{"limit": 5000}
```

**参数说明**:

| 参数 | 必填 | 说明 |
|------|------|------|
| `limit` | ❌ | 限制同步数量 |

**响应示例**:

```json
{
  "run_id": "uuid",
  "fetched": 5000,
  "saved": 5000
}
```

#### POST /api/market-data/daily-bars/sync

同步日行情到 `stock_daily_bar` 表。

**请求体**:

```json
{
  "symbols": ["600519.SH", "000001.SZ"],
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

**参数说明**:

| 参数 | 必填 | 说明 |
|------|------|------|
| `symbols` | ✅ | 股票代码列表 |
| `start_date` | ✅ | 开始日期 |
| `end_date` | ✅ | 结束日期 |

**响应示例**:

```json
{
  "run_id": "uuid",
  "fetched": 50,
  "saved": 50
}
```

#### GET /api/market-data/{symbol}/daily-bars

查询某只股票的日行情数据。

**查询参数**:

| 参数 | 必填 | 说明 |
|------|------|------|
| `start_date` | ❌ | 开始日期 (YYYY-MM-DD) |
| `end_date` | ❌ | 结束日期 (YYYY-MM-DD) |
| `limit` | ❌ | 最大返回条数 (默认 500) |

**响应示例**:

```json
{
  "symbol": "600519.SH",
  "count": 2,
  "bars": [
    {
      "trade_date": "2024-01-15",
      "open": 1700.0,
      "high": 1720.0,
      "low": 1690.0,
      "close": 1715.0,
      "volume": 1000000,
      "amount": 1700000000.0,
      "turnover": 0.8
    }
  ]
}
```

#### GET /api/market-data/etl-runs

查询最近的 ETL 运行记录。

**查询参数**:

| 参数 | 必填 | 说明 |
|------|------|------|
| `limit` | ❌ | 最大返回条数 (默认 50) |

**响应示例**:

```json
{
  "count": 1,
  "runs": [
    {
      "run_id": "uuid",
      "job_name": "ingest_stock_master",
      "source": "akshare",
      "status": "success",
      "started_at": "2024-01-15T15:15:00Z",
      "finished_at": "2024-01-15T15:15:10Z",
      "items_fetched": 5000,
      "items_normalized": 5000,
      "items_saved": 5000,
      "error_message": null
    }
  ]
}
```

---

## Python API

### 1. 资产分析服务

```python
from datetime import datetime, UTC
from core.services import AssetAnalysisService
from data_layer.repositories import AssetSnapshotRepositoryImpl
from data_layer.repositories.base import get_db

with get_db() as db:
    repo = AssetSnapshotRepositoryImpl(db)
    service = AssetAnalysisService(repo, use_mock=False)
    snapshot = service.generate_snapshot("600000.SH", datetime.now(UTC))

    print(f"PE TTM: {snapshot.valuation.get('pe_ttm')}")
    print(f"收盘价: {snapshot.price_volume.get('close_price')}")
```

---

### 2. 数据摄入服务

```python
from core.services import IngestService, DocumentClassifier, DocumentChunker
from core.services import EntityExtractor, EventExtractor
from data_layer.repositories.base import get_db

with get_db() as db:
    ingest_service = IngestService(db)
    
    # 从文件摄入
    result = ingest_service.ingest_file(
        file_path="report.pdf",
        source_type="report",
        source_name="券商研报"
    )
    
    print(f"摄入文档: {result.document_id}")
    print(f"提取断言: {result.extracted_assertions}")
    print(f"提取事件: {result.extracted_events}")
```

---

### 3. 情景服务

```python
from core.services import ScenarioService

service = ScenarioService()
scenario_set = service.generate_scenario_set("人工智能产业发展对股票市场的影响")

for scenario in scenario_set.scenarios:
    print(f"情景: {scenario.title}")
    print(f"概率: {scenario.probability}")
    print(f"关键假设: {scenario.key_assumptions}")
```

---

### 4. 信号服务

```python
from core.services import SignalService
from data_layer.repositories.base import get_db

with get_db() as db:
    service = SignalService(db)

    # 创建信号
    signal = service.create_signal(
        subject_id="600519.SH",
        thesis="白酒行业景气度回升",
        horizon="20d",
        confidence=0.8,
    )

    # 验证信号
    validation = service.validate_signal(signal.signal_id)

    # 生成交易候选
    candidate = service.generate_trade_candidate(signal)
```

---

### 5. 事件型 Alpha 信号

```python
from core.contracts import EventAlphaSignal

signal = EventAlphaSignal(
    signal_id="event_sig_001",
    subject_id="300000.SZ",
    horizon="20d",
    thesis="AI推理需求扩散至国产服务器链",
    confidence=0.82,
    event_id="event_gpt6_launch",
    event_type="global_ai_model_launch",
    impact_path=[
        "OpenAI新模型",
        "推理需求上升",
        "ASIC和液冷需求提升",
        "A股服务器链映射",
    ],
    industry_impacts=["ASIC", "液冷", "IDC", "铜连接"],
    diffusion_stage="early_awareness",
    market_regime="AI成长",
)
```

---

### 6. RAG 检索服务

```python
from core.services import RAGRetrievalService
from data_layer.repositories.base import get_db

with get_db() as db:
    rag_service = RAGRetrievalService(db)
    
    # 语义搜索
    results = rag_service.search(
        query="新能源产业链影响",
        limit=10
    )
    
    for result in results:
        print(f"标题: {result.title}")
        print(f"相关性: {result.relevance}")
    
    # RAG 增强生成
    answer = rag_service.query(
        question="新能源汽车销量增长对哪些股票有利？",
        context_k=5
    )
    print(answer)
```

---

### 7. 报告生成器

```python
from core.services import ReportGenerator
from data_layer.repositories.base import get_db

with get_db() as db:
    generator = ReportGenerator(db)
    
    # 资产分析报告
    asset_report = generator.generate_asset_report("600519.SH")
    generator.save_report(asset_report, "asset_report.md")
    
    # 估值报告
    valuation_report = generator.generate_valuation_report("600519.SH")
    generator.save_report(valuation_report, "valuation_report.md")
    
    # 每周回顾
    weekly_report = generator.generate_weekly_report()
    generator.save_report(weekly_report, "weekly_review.md")
```

#### 报告项目生成服务

```python
from pathlib import Path

import yaml

from reporting.projects.generation import ReportProjectGenerationService
from reporting.projects.project_manager import ReportProjectManager

manager = ReportProjectManager(projects_root=Path("report_projects"))
project = manager.get_project("华安ETF周报")
section_config = yaml.safe_load(project.section_config_path.read_text(encoding="utf-8"))
prompt_templates = project.prompt_templates_path.read_text(encoding="utf-8")

service = ReportProjectGenerationService()
result = service.generate_placeholders(
    project=project,
    section_config=section_config,
    prompt_templates_source=prompt_templates,
    manual_placeholders={"title": "华安ETF周报"},
    lookback_days=7,
)

print(result.placeholders)
print(result.sections[0].evidence_count)
```

配置口径：

- `section_config.yaml` 的 `placeholders:` 绑定 Word 占位符、Prompt 模板、静态值或 Excel 来源。
- `prompt_templates.md` 每个 `##` 标题是一个模板名；`检索 Query` 用于找事实材料，`写作要求` 用于约束最终正文。
- 模型调用通过 `ModelGatewayImpl.chat(task="reporting")`，未配置 reporting task route 时回落到 default。
- 运行日志由 `/api/report-projects/{slug}/render` 写入项目 `runs/` 目录，包含 evidence count、模型、token、图表和 warnings。

---

### 8. 结果日志服务

```python
from core.services import OutcomeJournalService, FailureMemoryService
from data_layer.repositories.base import get_db

with get_db() as db:
    outcome_service = OutcomeJournalService(db)
    failure_service = FailureMemoryService(db)
    
    # 记录结果
    outcome = outcome_service.record_outcome(
        signal_id="signal_123",
        outcome="win",
        return_pct=0.08,
        notes="按计划止盈"
    )
    
    # 搜索相似案例
    similar = outcome_service.search_similar(
        thesis="白酒行业景气度回升",
        limit=5
    )
    
    # 记录失败
    failure = failure_service.record_failure(
        signal_id="signal_456",
        failure_type="timing_error",
        root_cause="在高拥挤阶段追高",
        corrective_action="提高crowding blocker权重"
    )
```

---

### 9. 认知 Agent 黑板

```python
from cognitive_agents import AgentView, CognitiveBlackboard

blackboard = CognitiveBlackboard()

blackboard.add_view(AgentView(
    view_id="view_fundamental_001",
    agent_name="fundamental_agent",
    agent_role="fundamental",
    target_id="300308.SZ",
    event_id="event_ai_inference",
    view="bullish",
    thesis="800G需求超预期，盈利弹性提升",
    reasoning=["订单能见度提高", "产能利用率改善"],
    evidence_refs=["assertion_001"],
    confidence=0.72,
))

blackboard.add_view(AgentView(
    view_id="view_flow_001",
    agent_name="flow_agent",
    agent_role="sentiment",
    target_id="300308.SZ",
    event_id="event_ai_inference",
    view="bearish",
    thesis="机构仓位过高，短期交易拥挤",
    evidence_refs=["assertion_002"],
    confidence=0.64,
))

conflicts = blackboard.find_conflicts()
print(conflicts[0].summary)
```

---

### 10. Timing Engine 择时决策

```python
from timing_engine import MetaTimingEngine, TimingModelScore
from core.contracts.timing_engine import MarketRegime, TimingAction

engine = MetaTimingEngine()

decision = engine.evaluate(
    [
        TimingModelScore(
            model_name="regime",
            score=0.82,
            confidence=0.80,
            rationale="AI成长风格重新占优",
        ),
        TimingModelScore(
            model_name="flow",
            score=0.76,
            confidence=0.70,
            rationale="资金开始流入AI产业链",
        ),
        TimingModelScore(
            model_name="theme_diffusion",
            score=0.81,
            confidence=0.75,
            rationale="主题从光模块扩散到铜连接和液冷",
        ),
        TimingModelScore(
            model_name="crowding",
            score=0.24,
            confidence=0.70,
            rationale="交易拥挤度仍低",
        ),
    ],
    signal_id="event_sig_001",
    market_regime=MarketRegime.AI_GROWTH,
)

print(decision.action)  # TimingAction.ENTER / WAIT / REDUCE / EXIT
print(decision.readiness_score)
print(decision.blockers)
```

---

### 11. Memory & Learning 事件记忆

```python
from memory_learning import LearningJournal, MarketEpisode, FailureMemory
from datetime import datetime

journal = LearningJournal()

journal.record_episode(MarketEpisode(
    episode_id="episode_gpt6_001",
    event_id="event_gpt6_launch",
    event_type="ai_model_launch",
    market_regime="ai_growth",
    event_date=datetime(2025, 1, 15),
    initial_reaction="光模块和铜连接上涨",
    outcome_horizon="30d",
    outcome_return=0.18,
    outcome_excess_return=0.11,
    timing_action="enter",
    lesson="AI推理叙事在AI成长regime下扩散速度快",
))

journal.record_failure(FailureMemory(
    failure_id="failure_crowding_001",
    source_id="event_sig_001",
    failure_type="timing_error",
    root_cause="高拥挤阶段追高",
    corrective_action="提高crowding blocker权重",
    failure_date=datetime(2025, 2, 20),
))

summary = journal.summarize_event_type("ai_model_launch")
print(summary["average_excess_return"])

# 搜索相似案例
similar = journal.search_similar(thesis="AI模型发布影响", limit=5)
```

---

### 12. 模拟交易服务

```python
from core.services import PaperTradingService, PortfolioService
from data_layer.repositories.base import get_db

with get_db() as db:
    paper_trading = PaperTradingService(db)
    portfolio_service = PortfolioService(db)
    
    # 创建模拟账户
    account = paper_trading.create_account(
        name="测试账户",
        initial_capital=1000000
    )
    
    # 下单
    order = paper_trading.place_order(
        account_id=account.account_id,
        signal_id="signal_123",
        subject_id="600519.SH",
        action="buy",
        quantity=100,
        price=1800.0
    )
    
    # 获取组合持仓
    portfolio = portfolio_service.get_portfolio(account.account_id)
    print(portfolio.holdings)
    
    # 计算盈亏
    pnl = portfolio_service.calculate_pnl(account.account_id)
    print(f"总盈亏: {pnl.total_pnl_pct:.2%}")
```

---

## 数据采集器

### AKShare 采集器

AKShare 是开源数据源，用于在 iFinD 不可用时自动降级使用。

#### 模块结构

```
data_layer/crawlers/akshare/
├── __init__.py       # 导出 AkShareAdapter 和 AkShareConfig
├── base.py          # BaseAkShareFetcher 基类
├── config.py        # AkShareConfig 配置
├── market.py        # 市场数据采集器
├── financial.py     # 财务数据采集器
├── news.py          # 新闻数据采集器
├── macro.py         # 宏观数据采集器
└── utils.py         # 工具函数
```

#### 使用示例

```python
from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig
from datetime import date, timedelta

config = AkShareConfig()
adapter = AkShareAdapter(config)

# 获取股票列表
stocks = adapter.market.get_stock_list(limit=100)
print(f"获取 {len(stocks)} 只股票")

# 获取历史行情
end_date = date.today()
start_date = end_date - timedelta(days=365)

market_data = adapter.market.get_historical_data(
    symbol="600519.SH",
    start_date=start_date,
    end_date=end_date,
    period="daily",
    adjust="qfq"  # 前复权
)

for md in market_data:
    print(f"{md.timestamp}: {md.close}")

# 获取财务摘要
financial = adapter.financial.get_financial_abstract("600519.SH")
print(financial)

# 获取新闻
news = adapter.news.fetch_stock_news("600519.SH", days=30, limit=10)
for n in news:
    print(f"{n.publish_time}: {n.title}")
```

### 财联社采集器

采集财联社电报。

```python
from data_layer.crawlers.cls import CLSCrawler

crawler = CLSCrawler()
news = crawler.fetch_latest(limit=50)
```

### 中国证券网采集器

采集中国证券网新闻。

```python
from data_layer.crawlers.cnstock import CNStockCrawler

crawler = CNStockCrawler()
news = crawler.fetch_latest(limit=50)
```

### 知丘采集器

采集知丘研报、公众号、会议纪要。

```python
from data_layer.crawlers.zq import ZQCrawler

crawler = ZQCrawler()
reports = crawler.fetch_reports(limit=50)
articles = crawler.fetch_articles(limit=50)
notes = crawler.fetch_meeting_notes(limit=50)
```

### 采集编排器

统一编排多个采集器。

```python
from core.services import CrawlOrchestrator, CrawlScheduler
from data_layer.repositories.base import get_db

with get_db() as db:
    orchestrator = CrawlOrchestrator(db)
    
    # 运行所有采集器
    results = orchestrator.run_all()
    
    # 查看结果
    for source, count in results.items():
        print(f"{source}: {count} 条")
    
    # 启动调度器（后台运行）
    scheduler = CrawlScheduler(orchestrator)
    scheduler.start()
```

---

## 信号实验室

### 1. 特征工程

```python
import pandas as pd
import numpy as np
from datetime import date, timedelta
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import (
    PriceVolumeFeatures,
    ValuationFeatures,
    FinancialFeatures,
    FundFlowFeatures,
    IndustryFeatures,
    MacroFeatures
)

# 创建特征构建器
builder = FeatureBuilder()

# 添加特征组
builder.add_group(PriceVolumeFeatures())
builder.add_group(ValuationFeatures())
builder.add_group(FinancialFeatures())

# 准备价格数据
end_date = date.today()
start_date = end_date - timedelta(days=365)
dates = pd.date_range(start=start_date, end=end_date, freq="D")

# 计算所有特征
features = builder.compute_features(prices)

print(f"总特征数: {len(builder.get_all_feature_names())}")
print(features.head())
```

#### 价量特征

```python
from signal_lab.features.groups.price_volume import (
    PriceChangeFeature,
    MovingAverageFeature,
    RSIFeature,
    MACDFeature,
    VolatilityFeature
)

pv_group = PriceVolumeFeatures()
pv_group.add_feature(PriceChangeFeature(period=1))
pv_group.add_feature(PriceChangeFeature(period=5))
pv_group.add_feature(MovingAverageFeature(window=10))
pv_group.add_feature(MovingAverageFeature(window=20))
pv_group.add_feature(RSIFeature(window=14))
pv_group.add_feature(MACDFeature())
pv_group.add_feature(VolatilityFeature(window=20))
```

#### 估值特征

```python
from signal_lab.features.groups.valuation import (
    PEFeature,
    PBFeature,
    PSFeature,
    DividendYieldFeature
)

val_group = ValuationFeatures()
val_group.add_feature(PEFeature())
val_group.add_feature(PBFeature())
val_group.add_feature(PSFeature())
val_group.add_feature(DividendYieldFeature())
```

---

### 2. 标签工程

```python
from signal_lab.labels import RelativeReturnLabeler, EventDrivenLabeler

# 相对收益标签
labeler = RelativeReturnLabeler(horizon=20, forward=True)
labels = labeler.compute(prices)

print(f"标签数: {len(labels.dropna())}")
print(labels.head())

# 事件驱动标签
event_labeler = EventDrivenLabeler(
    post_horizon=20,
    pre_horizon=5
)
event_labels = event_labeler.compute(prices, events)
```

---

### 3. 信号评分与排名

```python
from core.services import SignalService
from signal_lab.scoring import (
    SignalScorer,
    CompositeScorer,
    ConfidenceScorer,
    StrengthScorer,
    HistoricalWinRateScorer,
    MarketTimingScorer
)
from signal_lab.scoring import SignalRanker
from data_layer.repositories.base import get_db

with get_db() as db:
    service = SignalService(db)
    
    # 创建组合评分器
    scorer = CompositeScorer(
        scorers=[
            ConfidenceScorer(weight=0.3),
            StrengthScorer(weight=0.2),
            HistoricalWinRateScorer(weight=0.3),
            MarketTimingScorer(weight=0.2)
        ]
    )
    
    # 获取信号列表
    signals = service.list_signals(status="draft")
    
    # 评分
    scored_signals = []
    for signal in signals:
        score = scorer.score(signal)
        scored_signals.append((signal, score))
    
    # 排名
    ranker = SignalRanker()
    ranked = ranker.rank(scored_signals)
    
    for signal, score, rank in ranked:
        print(f"{rank}. {signal.subject_id} - 评分: {score:.3f} - {signal.thesis[:30]}...")
```

---

### 4. 回测

```python
from signal_lab.backtests import SimpleBacktester, EventStudyBacktester

# 简单回测
backtester = SimpleBacktester(
    initial_capital=1000000,
    position_size=0.1,
    stop_loss=0.08,
    take_profit=0.15
)

result = backtester.run(prices, [signal])

print(f"总收益率: {result.total_return:.2%}")
print(f"年化收益率: {result.annual_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
print(f"胜率: {result.win_rate:.2%}")
print(f"交易次数: {result.num_trades}")

# 事件研究回测
import pandas as pd

events_df = pd.DataFrame({
    "event_date": ["2025-01-02", "2025-02-05", "2025-03-10"],
    "event_type": ["ai_model_launch", "export_control", "policy_announcement"],
})

event_backtester = EventStudyBacktester(horizon=20)
event_result = event_backtester.run(
    prices,
    events=events_df,
    benchmark=benchmark_prices
)

print(f"事件数: {event_result.metadata['event_count']}")
print(f"平均超额收益: {event_result.metadata['average_excess_return']:.2%}")
print(f"胜率: {event_result.win_rate:.2%}")
print(f"D+20 衰减收益: {event_result.metadata['decay_by_day'][20]:.2%}")
```

---

## 项目结构详解

### 完整目录树

```
AlphaFoundry/
├── app/                          # 应用层
│   ├── __init__.py
│   ├── api/                      # FastAPI 后端 API
│   │   ├── __init__.py
│   │   ├── main.py               # API 入口点
│   │   ├── models.py             # API 请求/响应模型
│   │   └── routes/               # API 路由
│   │       ├── audit.py          # 审计 API
│   │       ├── dashboard.py      # 仪表盘 API
│   │       ├── governance.py     # 治理 API
│   │       ├── ingest.py         # 数据摄入 API
│   │       ├── memory.py         # 记忆 API
│   │       ├── monitoring.py     # 监控 API
│   │       ├── outcome_journal.py # 结果日志 API
│   │       ├── pipeline.py       # 管道 API
│   │       ├── report.py         # 报告 API
│   │       ├── scenarios.py      # 情景 API
│   │       ├── search.py         # 搜索 API
│   │       ├── signal_lab.py     # 信号实验室 API
│   │       ├── system.py         # 系统健康检查 API
│   │       └── realtime.py       # 实时 SSE 推送 API
│   ├── cli/                      # 命令行工具
│   │   ├── __init__.py
│   │   ├── main.py               # CLI 入口点
│   │   └── commands/             # CLI 命令
│   │       ├── __init__.py
│   │       ├── akshare.py        # AKShare 命令
│   │       ├── ingest.py         # 数据摄入命令
│   │       ├── memory.py         # 记忆命令
│   │       ├── review.py         # 审核命令
│   │       ├── signal.py         # 信号命令
│   │       └── timing.py         # 择时命令
│   └── web/                      # Web 工作台界面
├── core/                         # 核心层
│   ├── __init__.py
│   ├── contracts/                # Pydantic 数据契约
│   │   ├── __init__.py
│   │   ├── assertions.py         # 断言结构
│   │   ├── assets.py             # 资产定义结构
│   │   ├── backtest.py           # 回测结构
│   │   ├── dashboard.py          # 仪表盘结构
│   │   ├── decision_console.py   # 决策控制台结构
│   │   ├── documents.py          # 文档结构（旧版）
│   │   ├── documents_v1.py       # 文档结构 v1
│   │   ├── events.py             # 事件结构
│   │   ├── governance.py         # 治理结构
│   │   ├── ids.py                # 全局 ID 定义
│   │   ├── industry_chain.py     # 产业链结构
│   │   ├── ingestion.py          # 摄入结构
│   │   ├── monitoring.py         # 监控结构
│   │   ├── outcome_journal.py    # 结果日志结构
│   │   ├── outcomes.py           # 结果结构
│   │   ├── paper_trading.py      # 模拟交易结构
│   │   ├── portfolio.py          # 组合结构
│   │   ├── raw_storage.py        # 原始存储结构
│   │   ├── replay.py             # 回放结构
│   │   ├── reporting.py          # 报告结构
│   │   ├── retrieval.py          # 检索结构
│   │   ├── review_framework.py   # 审查框架结构
│   │   ├── scenarios.py          # 情景分析结构
│   │   ├── signals.py            # 信号定义结构
│   │   ├── timing_engine.py      # 择时引擎结构
│   │   └── traces.py             # 推理追踪结构
│   ├── interfaces/               # 核心接口定义
│   │   └── repository.py         # 仓储接口
│   ├── model_gateway/            # 模型网关
│   │   ├── __init__.py
│   │   └── providers/            # 模型提供商
│   │       └── volcano.py        # 火山引擎提供商
│   ├── observability/            # 可观测性（日志、指标、追踪）
│   │   ├── __init__.py
│   │   └── metrics.py            # 指标定义
│   ├── services/                 # 业务服务
│   │   ├── __init__.py
│   │   ├── asset_analysis_service.py         # 资产分析服务
│   │   ├── audit_service.py                   # 审计服务
│   │   ├── closed_loop_service.py            # 闭循环服务
│   │   ├── crawl_orchestrator.py             # 采集编排器
│   │   ├── crawl_scheduler.py                # 采集调度器
│   │   ├── crawler_ingestion_bridge.py       # 采集摄入桥接
│   │   ├── dashboard_service.py              # 仪表盘服务
│   │   ├── data_tier_service.py              # 数据层服务
│   │   ├── decision_console_service.py       # 决策控制台服务
│   │   ├── deduplication_service.py          # 去重服务
│   │   ├── document_chunker.py               # 文档分块
│   │   ├── document_classifier.py            # 文档分类
│   │   ├── document_enrichment.py            # 文档丰富
│   │   ├── entity_extractor.py               # 实体提取
│   │   ├── event_auto_signal_generator.py    # 事件自动信号生成
│   │   ├── event_extractor.py                # 事件提取
│   │   ├── event_ingestion_service.py        # 事件摄入服务
│   │   ├── failure_memory_service.py         # 失败记忆服务
│   │   ├── governance_service.py             # 治理服务
│   │   ├── graph_data_service.py             # 图数据服务
│   │   ├── historical_replay_service.py      # 历史回放服务
│   │   ├── ingest_service.py                 # 摄入服务
│   │   ├── ingestion_queue_service.py        # 摄入队列服务
│   │   ├── monitoring_service.py             # 监控服务
│   │   ├── news_feature_service.py           # 新闻特征服务
│   │   ├── outcome_journal_service.py        # 结果日志服务
│   │   ├── outcome_service.py                # 结果服务
│   │   ├── paper_trading_service.py          # 模拟交易服务
│   │   ├── pipeline_service.py               # 管道服务
│   │   ├── portfolio_service.py              # 组合服务
│   │   ├── rag_retrieval.py                  # RAG 检索
│   │   ├── raw_storage_service.py            # 原始存储服务
│   │   ├── replay_service.py                 # 回放服务
│   │   ├── report_generator.py               # 报告生成器
│   │   ├── review_service.py                 # 审查服务
│   │   ├── scenario_data_service.py          # 情景数据服务
│   │   ├── scenario_service.py               # 情景服务
│   │   ├── search_service.py                 # 搜索服务
│   │   ├── signal_service.py                 # 信号服务
│   │   ├── signal_validator_impl.py          # 信号验证实现
│   │   ├── summary_generator.py              # 摘要生成器
│   │   ├── system_event_bus.py               # 系统事件总线
│   │   ├── taxonomy_service.py               # 分类服务
│   │   ├── thesis_generator_service.py       # 论点生成服务
│   │   ├── thesis_review_service.py          # 论点审查服务
│   │   └── timing_engine_service.py          # 择时引擎服务
│   └── settings/               # 配置管理
│       └── config.py           # Settings (模型网关/LLM提取/数据库/日志等)
├── data_layer/                 # 数据层
│   ├── __init__.py
│   ├── adapters/               # 数据适配器
│   │   ├── __init__.py
│   │   ├── akshare_adapter.py # AKShare 适配器
│   │   ├── data_source_router.py # 数据源路由器
│   │   └── wind/               # Wind Excel 适配器
│   │       ├── __init__.py
│   │       ├── exceptions.py  # Wind 自定义异常
│   │       ├── client.py      # Wind Excel 客户端 (xlwings)
│   │       ├── formulas.py    # Wind 公式生成器 (~75个)
│   │       └── wind_adapter.py # Wind 数据适配器 (8种数据类型)
│   ├── crawlers/              # 数据采集器
│   │   ├── __init__.py
│   │   ├── akshare/           # AKShare 采集器
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # BaseAkShareFetcher 基类
│   │   │   ├── config.py     # AkShareConfig 配置
│   │   │   ├── financial.py  # 财务数据采集器
│   │   │   ├── macro.py      # 宏观数据采集器
│   │   │   ├── market.py     # 市场数据采集器
│   │   │   ├── news.py       # 新闻数据采集器
│   │   │   └── utils.py      # 工具函数（clean_symbol, parse_date 等）
│   │   ├── cls/              # 财联社采集器
│   │   ├── cnstock/          # 中国证券网采集器
│   │   └── zq/               # 知丘采集器
│   ├── parsers/              # 解析器
│   ├── normalizers/          # 归一化器
│   └── repositories/         # 仓储实现
├── knowledge_layer/          # 知识层
│   ├── entity_resolution/    # 实体解析
│   ├── assertions/           # 断言管理
│   ├── events/               # 事件管理
│   ├── extraction/           # 并发 LLM 提取 (文本切分 + 并发抽取器)
│   └── retrieval/            # 向量检索
├── reasoning/                # 推理层
│   ├── evidence/             # 证据链管理
│   ├── scenarios/            # 情景分析
│   ├── skeptic/              # 怀疑论验证
│   └── traces/               # 推理追踪
├── cognitive_agents/         # 认知 Agent 插件层
│   ├── __init__.py
│   ├── contracts.py          # 统一观点契约（AgentView, BlackboardConflict）
│   └── blackboard.py         # 认知黑板（CognitiveBlackboard）
├── timing_engine/            # 择时层
│   ├── __init__.py
│   ├── contracts.py          # 择时契约（TimingModelScore, TimingDecision）
│   └── meta.py              # Meta 择时引擎
├── memory_learning/          # 记忆与学习层
│   ├── __init__.py
│   ├── contracts.py          # 记忆契约（MarketEpisode, StrategyMemory, FailureMemory）
│   └── journal.py           # 学习日志（LearningJournal）
├── reporting/                # 报告层
│   ├── composer/             # 报告合成
│   ├── templates/            # 报告模板
│   └── projections/          # 输出投影（Markdown, Word）
├── signal_lab/               # 信号实验室
│   ├── __init__.py
│   ├── features/             # 特征工程
│   │   ├── base.py          # Feature, FeatureGroup 基类
│   │   ├── builder.py       # FeatureBuilder
│   │   └── groups/          # 特征组实现
│   │       ├── price_volume.py
│   │       ├── valuation.py
│   │       ├── financial.py
│   │       ├── fund_flow.py
│   │       ├── industry.py
│   │       └── macro.py
│   ├── labels/               # 标签工程
│   │   ├── base.py          # Labeler 基类
│   │   ├── relative_return.py
│   │   └── event_driven.py
│   ├── scoring/              # 信号评分
│   │   ├── scorer.py        # SignalScorer, CompositeScorer
│   │   └── ranker.py        # SignalRanker
│   └── backtests/            # 回测引擎
│       ├── base.py          # Backtester, BacktestResult 基类
│       └── simple.py        # 简单回测实现
├── ingestion/                 # 结构化摄入模块
│   ├── __init__.py            # 导出 KnowledgePipeline
│   ├── knowledge_pipeline.py  # 6 步知识处理管道
│   └── structured_event_ingestion.py  # 结构化事件摄入器
├── storage/                  # 存储层
│   └── migrations/           # Alembic 数据库迁移
├── alembic/                  # Alembic 配置
├── scripts/                  # 脚本工具
│   ├── seed_factor_data.py   # 因子数据播种（双数据源+限流+断点续传）
│   ├── backup_db.py          # 数据库备份脚本
│   ├── restore_db.py         # 数据库恢复脚本
│   ├── bootstrap_db.py       # 数据库初始化脚本
│   ├── import_real_data.py   # 导入真实数据脚本
│   ├── minimal_reingest_bootstrap.py  # 最小重摄入引导脚本
│   ├── backfill_from_objects.py        # 从对象存储回填脚本
│   ├── rebuild_derived_state.py        # 重建派生状态脚本
│   ├── start_all.sh           # 一键启动脚本
│   └── stop_all.sh            # 一键停止脚本
├── workers/                   # 后台 Worker
│   └── knowledge_worker.py    # 知识处理 Worker
├── benchmarks/               # 基准数据
├── examples/                 # 示例代码
├── tests/                    # 测试
│   ├── unit/                 # 单元测试
│   │   ├── core/
│   │   ├── data_layer/
│   │   │   └── crawlers/
│   │   │       └── test_akshare.py
│   │   └── ...
│   └── integration/          # 集成测试
├── docs/                     # 文档
│   ├── REFERENCE.md          # 本文档
│   ├── ARCHITECTURE.md       # 架构文档
│   ├── FILE_GUIDE.md         # 文件指南
│   ├── CHANGELOG.md          # 更新日志
│   ├── backup_restore.md     # 备份恢复文档
│   ├── DATA_SOURCES.md       # 数据源文档
│   └── ...
├── data/                     # 数据目录
├── logs/                     # 日志目录
├── backups/                  # 备份目录
├── .claude/                  # Claude 配置
├── .env.example              # 环境变量示例
├── .env                      # 环境变量（不提交到 git）
├── .gitignore                # Git 忽略
├── pyproject.toml            # 项目配置（black, isort, ruff, pytest, mypy error-code debt list）
├── pytest.ini                # Pytest 配置
├── alembic.ini               # Alembic 配置
├── auto_ingest_service.py    # 自动摄入服务
├── insert_real_data.py       # 插入真实数据脚本
├── view_db.py                # 数据库查看工具
├── smoke_runner.py           # 冒烟测试运行器
├── report_cli.py             # 报告 CLI 工具
└── README.md                 # 项目 README
```

---

## 常见问题

### Q: 如何运行完整演示？

```bash
python examples/test_simple.py
python examples/test_signal_lab_simple.py
python scripts/smoke_runner.py
```

### Q: 如何运行测试？

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行特定测试
pytest tests/unit/data_layer/crawlers/test_akshare.py

# 查看覆盖率
pytest --cov=core --cov=data_layer --cov-report=html
```

默认测试环境会设置 `ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS=1`，避免单元测试加载 embedding 模型。运行时本地 embedding 支持 `ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH=/path/to/model` 指向已下载模型目录；未设置本地路径时，sentence-transformers 只读本机 Hugging Face cache，只有设置 `ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD=1` 才允许联网下载。需要真实服务的 API smoke 测试默认跳过，设置 `ALPHAFOUNDRY_RUN_LIVE_API_TESTS=1` 后才会访问 `127.0.0.1:8000`；浏览器 E2E smoke 默认跳过，设置 `ALPHAFOUNDRY_RUN_LIVE_E2E_TESTS=1` 后才会运行。

### Q: 必须使用数据库吗？

- **默认模式**：需要配置数据库（推荐 PostgreSQL）
- **零配置模式**：可以使用 SQLite，无需额外配置
- **演示模式**：如果需要快速测试，可以使用模拟数据

### Q: 支持哪些输出格式？

- Markdown (.md)
- Word (.docx)

### Q: AKShare 是什么？

AKShare 是开源金融数据接口，用于在 iFinD 不可用时自动降级使用。它提供：
- 股票历史行情
- 财务数据
- 新闻数据
- 股票列表
- 指数数据

### Q: 如何备份数据？

```bash
python scripts/backup_db.py --output backups/
```

详细文档请参考 `docs/backup_restore.md`。

### Q: 如何启动 Web 服务？

```bash
uvicorn app.api.main:app --reload
```

或后台运行：

```bash
nohup python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 > logs/web_server.log 2>&1 &
```

或使用一键启动脚本（启动 API + 调度器 + Knowledge Worker）：

```bash
bash scripts/start_all.sh
```

停止所有服务：

```bash
bash scripts/stop_all.sh
```

然后访问：http://127.0.0.1:8000/

### Q: 如何启动自动数据采集？

```bash
python auto_ingest_service.py
```

或后台运行：

```bash
python auto_ingest_service.py --daemon
```

### Q: 如何查看数据库内容？

```bash
# 查看统计信息
python view_db.py stats

# 查看最新事件
python view_db.py events

# 查看最新文档
python view_db.py docs

# 自定义 SQL 查询
python view_db.py query "SELECT * FROM canonical_event LIMIT 5"
```

---

## 相关资源

- **[README.md](../README.md)** - 项目概述与快速开始
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 架构文档
- **[FILE_GUIDE.md](FILE_GUIDE.md)** - 文件指南
- **[CHANGELOG.md](CHANGELOG.md)** - 更新日志
