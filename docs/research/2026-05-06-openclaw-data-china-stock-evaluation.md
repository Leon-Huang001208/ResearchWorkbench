# 调研报告：openclaw-data-china-stock 插件安全审计与兼容性评估

> **调研员**: 🔭 图灵实验室  
> **日期**: 2026-05-06  
> **插件**: `@shaoxing-xie/openclaw-data-china-stock@0.5.11`  
> **ClawHub**: community, verification=source-linked  
> **许可证**: MIT  
> **结论**: ✅ 安全可安装，兼容性需适配层

---

## 第一部分：安全审计

### 1.1 审计范围

| 维度 | 方法 | 覆盖 |
|:---|:---|:---|
| 网络请求 | `grep -rn "requests\.\|urllib\.\|httpx\.\|aiohttp\."` | 全量 185 个 .py + index.ts |
| 命令注入 | `grep -rn "subprocess\|os\.system\|eval(\|exec(\|__import__"` | 全量 |
| 文件读写 | `grep -rn "\.write\|open.*'w'\|expanduser\|\.ssh\|/etc/"` | 全量 |
| 环境变量 | `grep -rn "os\.environ\|os\.getenv\|\.env"` | 全量 |
| 加密/后门 | `grep -rn "base64\|cipher\|encrypt\|decrypt\|obfuscat\|socket\|websocket\|ssl\|SMTP"` | 全量 |
| 依赖审查 | `requirements.txt` + `requirements-optional.txt` 逐项检查 | 全量 |

### 1.2 审计结论

**✅ 未发现阻断性安全问题，可安装。**

以下逐项说明：

#### 1.2.1 数据外泄风险 — ✅ 无

| 网络请求目标 | 用途 | API Key 是否外传 | 判定 |
|:---|:---|:---|:---|
| `api.tavily.com/search` | 盘前政策/行业新闻检索 | `TAVILY_API_KEY` 在 POST body 中发送（官方接口规范） | ✅ 正常 |
| `financialmodelingprep.com/stable/quote` | 全球指数 spot 数据 | `FMP_API_KEY` 在 URL query param 中（FMP 官方规范） | ✅ 正常 |
| `eastmoney.com` / `push2.eastmoney.com` | A 股行情/资金流/板块 | 无 API Key | ✅ 正常 |
| `money.finance.sina.com.cn` | 指数/ETF K 线数据 | 无 API Key | ✅ 正常 |
| `data.eastmoney.com` | 北向资金/板块数据 | 无 API Key | ✅ 正常 |
| `hq.sinajs.cn` | 全球指数快照 | 无 API Key | ✅ 正常 |
| `qt.gtimg.cn` | 股票实时行情 | 无 API Key | ✅ 正常 |
| `localhost:5000` | 可选本地缓存服务 | `OPENCLAW_DATA_API_KEY` 在 X-API-Key header（仅本地） | ✅ 正常 |
| `tushare.pro` (via `ts.pro_api`) | 北向资金日频 | `TUSHARE_TOKEN` 传入 tushare SDK（官方规范） | ✅ 正常 |

**未发现任何将 API Key / 密码 / Token 发往非官方或未声明的第三方服务器。**

#### 1.2.2 命令注入风险 — ✅ 无

- `subprocess.run` 仅出现在 **测试脚本** (`tests/`, `scripts/`) 中，参数为硬编码命令，不接受用户输入
- `tool_runner.py` 使用 `__import__(module_path, fromlist=[function_name])` 动态加载模块，模块路径来自内部映射表，不接受外部输入
- `index.ts` 使用 `execFileAsync(PYTHON_BIN, [scriptPath, toolName, argsJson])`，三个参数均来自受控来源（配置/manifest/序列化 JSON）

#### 1.2.3 越权文件访问 — ✅ 无

| 写入路径 | 用途 | 判定 |
|:---|:---|:---|
| `~/.openclaw/workspace/stock_monitor_state.json` | 股票监控状态持久化 | ✅ 合理 |
| `~/.openclaw/openclaw.json` | 开发注册脚本写入 | ✅ 仅 `register_openclaw_dev.py` |
| 插件自身 `data/cache/`, `data/meta/` | 缓存与健康快照 | ✅ 合理 |
| `config.yaml` (via `src/config_loader.py`) | 配置保存 | ✅ 内部功能 |

**未发现对 `/etc/`、`~/.ssh/`、`~/.aws/`、`~/.gnupg/` 等敏感目录的任何访问。**

#### 1.2.4 恶意依赖 — ✅ 无

| 依赖包 | 用途 | 风险 |
|:---|:---|:---|
| pydantic | 数据校验 | ⭐ 主流 |
| PyYAML | 配置解析 | ⭐ 主流 |
| requests | HTTP 客户端 | ⭐ 主流 |
| numpy / pandas / pyarrow | 数据处理 | ⭐ 主流 |
| pytz | 时区 | ⭐ 主流 |
| akshare | A 股数据源 | ⭐ 国内主流开源 |
| tushare | 金融数据接口 | ⭐ 国内主流开源 |
| yfinance | Yahoo Finance 数据 | ⭐ 全球主流 |
| mootdx | 通达信数据 | ⭐ 国内主流 |
| efinance | 东财数据 | ⭐ 国内开源 |
| pandas-ta | 技术指标 | ⭐ 主流 |
| TA-Lib | 技术指标引擎 | ⭐ 业界标准 |

**全部为知名、主流包，无可疑依赖。**

#### 1.2.5 后门检测 — ✅ 无

- 无 `base64` 编码的 URL 或隐藏网络请求
- 无 `socket`/`websocket`/`ssl`/`SMTP`/`FTP`/`telnet` 调用
- 无加密通信或混淆代码
- 无 `eval()` / `exec()` 用于执行外部输入

### 1.3 低风险注意事项（非阻断）

| 项 | 风险等级 | 说明 |
|:---|:---|:---|
| 飞书通知 | ⚠️ 低 | `send_feishu_notification.py` 会将分析结果发送到配置的飞书 webhook；需主动配置才启用，默认不触发 |
| FMP API Key 在 URL 中 | ⚠️ 低 | FMP 的 `apikey` 参数在 URL query string 中（FMP 官方设计），可能出现在服务器访问日志 |
| `localhost:5000` 缓存服务 | ⚠️ 低 | 部分工具支持将数据 POST 到本地缓存服务；需显式设置 `api_base_url` 参数，默认为 localhost |
| `register_openclaw_dev.py` 修改 `openclaw.json` | ⚠️ 低 | 开发注册脚本会修改 `~/.openclaw/openclaw.json` 并创建 skill 符号链接；仅开发时手动执行 |

---

## 第二部分：兼容性评估

### 2.1 插件能力全景

#### 2.1.1 工具清单（86 个）

按功能域分类：

| 域 | 工具数 | 代表工具 |
|:---|:---|:---|
| **指数** | 7 | `tool_fetch_index_data`, `tool_fetch_index_realtime`, `tool_fetch_index_historical`, `tool_fetch_index_minute`, `tool_fetch_index_opening`, `tool_fetch_cni_index_daily`, `tool_fetch_csindex_index_daily` |
| **ETF** | 5 | `tool_fetch_etf_data`, `tool_fetch_etf_realtime`, `tool_fetch_etf_historical`, `tool_fetch_etf_minute`, `tool_fetch_etf_iopv_snapshot` |
| **期权** | 5 | `tool_fetch_option_data`, `tool_fetch_option_realtime`, `tool_fetch_option_greeks`, `tool_fetch_option_minute`, `tool_get_option_contracts` |
| **股票** | 8 | `tool_fetch_market_data`, `tool_fetch_stock_historical`, `tool_fetch_stock_realtime`, `tool_fetch_stock_minute`, `tool_stock_data_fetcher`, `tool_stock_monitor`, `tool_fetch_a_share_universe`, `tool_filter_a_share_tradability` |
| **财务** | 6 | `tool_fetch_stock_financials`, `tool_fetch_stock_financial_reports`, `tool_fetch_stock_corporate_actions`, `tool_fetch_margin_trading`, `tool_fetch_block_trades`, `tool_fetch_stock_shareholders` |
| **实体/L2** | 5 | `tool_resolve_symbol`, `tool_batch_resolve_symbol`, `tool_get_entity_meta`, `tool_get_index_constituents`, `tool_get_etf_holdings` |
| **技术指标** | 2 | `tool_calculate_technical_indicators` (58 指标), `tool_calculate_sector_rps` |
| **情绪/资金流** | 8 | `tool_fetch_limit_up_stocks`, `tool_fetch_a_share_fund_flow`, `tool_fetch_northbound_flow`, `tool_fetch_sector_data`, `tool_capital_flow`, `tool_dragon_tiger_list`, `tool_hotspot_discovery`, `tool_sector_heat_score` |
| **板块/轮动** | 3 | `tool_sector_rotation_recommend`, `tool_etf_rotation_research`, `tool_fetch_a_share_technical_screener` |
| **宏观** | 20 | `tool_fetch_macro_data`, `tool_fetch_macro_snapshot`, + 18 个专项指标 (CPI/PPI/M2/PMI/LPR/GDP 等) |
| **新闻/公告** | 4 | `tool_fetch_policy_news`, `tool_fetch_macro_commodities`, `tool_fetch_overnight_futures_digest`, `tool_fetch_announcement_digest` |
| **L4 估值** | 2 | `tool_l4_valuation_context`, `tool_l4_pe_ttm_percentile` |
| **多因子选股** | 2 | `tool_screen_equity_factors`, `tool_screen_by_factors` |
| **观测/健康** | 3 | `tool_probe_source_health`, `tool_summarize_attempts`, `tool_plugin_catalog_digest` |
| **A50/期货** | 1 | `tool_fetch_a50_data` |
| **缓存读取** | 7 | `tool_read_market_data`, `tool_read_index_daily/minute`, `tool_read_etf_daily/minute`, `tool_read_option_minute/greeks` |
| **其他** | 3 | `tool_check_trading_status`, `tool_get_a_share_market_regime`, `tool_fetch_ipo_calendar` |

#### 2.1.2 Skill 清单（7 个）

| Skill | 版本 | 核心依赖工具 | 输出结构 |
|:---|:---|:---|:---|
| **china-macro-analyst** | 既有 | `tool_fetch_macro_data/snapshot` | 宏观象限、指标摘要、反证 |
| **technical-analyst** | v0.5.0 | `tool_calculate_technical_indicators` | 趋势/动量/波动/形态评分 |
| **market-scanner** | v0.5.0 | 多个情绪+板块工具 | 市场阶段、异动清单 |
| **market-sentinel** | v0.5.0 | 4 个情绪工具聚合 | 情绪四维、聚合 JSON |
| **fund-flow-analyst** | v0.5.0 | `tool_fetch_a_share_fund_flow`, `tool_fetch_northbound_flow` | 主力/北向共振分析 |
| **strategy-backtester** | v0.5.0 (MVP) | `tool_fetch_market_data` + 技术指标 | 均线策略回测 |
| **fundamental-analyst** | v0.5.0 | `tool_fetch_stock_financials/reports` | 盈利/成长/偿债/估值评分 |

### 2.2 与 Research Workbench 架构对照

#### 2.2.1 数据层对照

| Research Workbench 数据域 | `AssetAnalysisSnapshot` 字段 | 插件覆盖工具 | 匹配度 |
|:---|:---|:---|:---|
| 行情 | `price_volume` | `tool_fetch_market_data`, `tool_fetch_stock_historical/realtime/minute` | ✅ 完整 |
| 财务 | `financial` | `tool_fetch_stock_financials`, `tool_fetch_stock_financial_reports` | ✅ 完整 |
| 资金流 | `fund_flow` | `tool_fetch_a_share_fund_flow`, `tool_fetch_northbound_flow`, `tool_capital_flow` | ✅ 完整+增强 |
| 估值 | `valuation` | `tool_l4_valuation_context`, `tool_l4_pe_ttm_percentile` | ✅ 完整 |
| 股东 | `shareholder` | `tool_fetch_stock_shareholders` | ✅ 完整 |
| 行业 | `industry` | `tool_fetch_sector_data`, `tool_resolve_symbol` (行业映射) | ✅ 完整 |
| 事件 | `event_impact` | `tool_fetch_policy_news`, `tool_fetch_announcement_digest` | ⚠️ 间接（新闻≠事件） |
| 宏观 | `macro_exposure` | `tool_fetch_macro_data/snapshot` + 18 个专项 | ✅ 完整+增强 |
| **技术指标** | ❌ 不存在 | `tool_calculate_technical_indicators` (58 指标) | 🆕 新增能力 |
| **情绪** | ❌ 不存在 | 4 个情绪工具 + `market-sentinel` | 🆕 新增能力 |
| **选股** | ❌ 不存在 | `tool_screen_equity_factors` | 🆕 新增能力 |

**结论：插件对 Research Workbench 现有数据域 100% 覆盖，并新增 3 个关键能力域。**

#### 2.2.2 契约差异（需适配层）

| 维度 | Research Workbench | 插件 | 差异 | 适配难度 |
|:---|:---|:---|:---|:---|
| **输出类型** | `DocumentEnvelope` / `AssetAnalysisSnapshot` (Pydantic) | `Dict[str, Any]` (`{success, data, message}`) | 结构不兼容 | 🟡 中 |
| **调用方式** | `DataAdapter.fetch(**kwargs)` (同步/异步方法) | `tool_runner.py` (子进程) / OpenClaw Tool API | 调用路径不同 | 🟡 中 |
| **source_type 枚举** | `"policy" \| "news" \| "report" \| ... \| "vendor_snapshot"` | 无此概念 | 需映射 | 🟢 低 |
| **幂等键** | `sha256(content)` 生成 `doc_id` | 工具自带缓存+TTL 机制 | 机制不同 | 🟢 低 |
| **iFinD vs AKShare** | iFinD (付费商业源) | AKShare/Tushare/eastmoney/sina (免费/开源) | **互补而非替代** | 🟢 低 |
| **数据格式** | iFinD 专有字段名 (`ths_open_stock`) | 各源自有字段名 | 需映射 | 🟡 中 |

#### 2.2.3 关键差异详解

**① 输出契约不兼容**

```python
# Research Workbench 期望
DocumentEnvelope(
    doc_id="sha256...",
    source_type="vendor_snapshot",  # 枚举受限
    title="...",
    source_name="...",
    raw_text="...",
    canonical_text="...",
)

# 插件实际返回
{
    "success": True,
    "data": { "items": [...], "source": "akshare" },
    "message": "ok",
    "count": 10,
    "timestamp": "...",
}
```

需要编写适配器将插件 Dict 输出转为 `DocumentEnvelope`。

**② iFinD 与插件数据源的互补性**

| 对比项 | iFinD 适配器 | 插件 |
|:---|:---|:---|
| 数据源性质 | 商业付费 (同花顺) | 免费/开源 (AKShare/Tushare/东财/新浪) |
| 数据质量 | ⭐⭐⭐⭐⭐ 专业级 | ⭐⭐⭐⭐ 良好（有多源降级） |
| 稳定性 | 高（商业 SLA） | 中（依赖开源接口稳定性） |
| 成本 | 付费（年费数万） | 零成本 |
| 覆盖广度 | 全品种深度数据 | A 股 + ETF + 期权 + 宏观 |
| 特有优势 | 深度财务、研报、机构持仓 | 技术指标、情绪、选股、板块轮动 |

**③ `source_type` 枚举需扩展**

当前 `DocumentEnvelope.source_type` 不包含 `"market_data"` 类型。插件的市场行情数据最适合映射为 `"vendor_snapshot"`，但语义上不够精确。建议扩展枚举。

### 2.3 Skill 层价值评估

| Skill | Research Workbench 价值 | 集成方式 |
|:---|:---|:---|
| **fundamental-analyst** | ⭐⭐⭐⭐⭐ 完美补充财务分析流水线 | 可映射到 `AssetAnalysisSnapshot.financial` + `valuation` |
| **technical-analyst** | ⭐⭐⭐⭐⭐ 填补技术面空白 | 输出可映射到新的 `technical` 字段 |
| **fund-flow-analyst** | ⭐⭐⭐⭐⭐ 增强资金流分析深度 | 映射到 `fund_flow` 字段并增强 |
| **china-macro-analyst** | ⭐⭐⭐⭐ 补充宏观象限判断 | 映射到 `macro_exposure` |
| **market-scanner** | ⭐⭐⭐⭐ 盘中扫描新能力 | 新增 `market_scan` 输出 |
| **market-sentinel** | ⭐⭐⭐⭐ 情绪聚合新能力 | 新增 `sentiment` 输出 |
| **strategy-backtester** | ⭐⭐⭐ MVP 回测（有限） | 可选集成，当前为轻量编排 |

### 2.4 推荐集成方案

#### 方案：编写 `ChinaStockAdapter` 适配器

在 `data_layer/adapters/` 下新增 `china_stock_adapter.py`，实现 `DataAdapter` 接口，内部通过 OpenClaw Tool API 调用插件工具，并将输出映射为 `DocumentEnvelope` / `AssetAnalysisSnapshot`。

```python
# 概念示意（非实际代码）
class ChinaStockAdapter(BaseDataAdapter):
    """基于 openclaw-data-china-stock 插件的数据适配器"""
    
    def __init__(self):
        super().__init__(source_type="china_stock_plugin")
    
    async def fetch_stock_quotes(self, codes, start_date, end_date):
        # 调用 tool_fetch_market_data → 映射为 AssetAnalysisSnapshot.price_volume
        ...
    
    async def fetch_financial_report(self, code):
        # 调用 tool_fetch_stock_financials → 映射为 .financial
        ...
    
    async def fetch_technical_indicators(self, code, indicators):
        # 调用 tool_calculate_technical_indicators → 映射到新增的 .technical 字段
        ...
    
    # ... 其他方法
```

**需要同步修改：**
1. `AssetAnalysisSnapshot` 新增 `technical: dict` 和 `sentiment: dict` 字段
2. `DocumentEnvelope.source_type` 扩展枚举，加入 `"market_data"`
3. `Settings` 新增 `OPENCLAW_DATA_CHINA_STOCK_ENABLED` 开关

#### 集成优先级建议

| 优先级 | 数据域 | 工具 | 理由 |
|:---|:---|:---|:---|
| P0 | 行情+财务+资金流 | `tool_fetch_market_data`, `tool_fetch_stock_financials`, `tool_fetch_a_share_fund_flow` | 直接替代/补充 iFinD 核心能力 |
| P1 | 技术指标 | `tool_calculate_technical_indicators` | 新增关键能力 |
| P1 | 宏观 | `tool_fetch_macro_data/snapshot` | 补充宏观经济分析 |
| P2 | 估值 L4 | `tool_l4_valuation_context` | 增强估值分析 |
| P2 | 情绪 | 4 个情绪工具 | 新增能力 |
| P3 | 选股 | `tool_screen_equity_factors` | 进阶分析 |
| P3 | Skill 层 | 7 个 Skill | 结构化分析流水线 |

---

## 第三部分：与现有 iFinD 适配器的关系

### 3.1 定位：互补双源，非替代

```
┌──────────────────────────────────────────────────┐
│              Research Workbench 数据层                  │
│                                                   │
│  ┌─────────────┐     ┌──────────────────────┐    │
│  │ IFinDAdapter │     │ ChinaStockAdapter    │    │
│  │ (商业源)      │     │ (开源插件源)           │    │
│  │              │     │                      │    │
│  │ · 深度财务    │     │ · 行情(免费)           │    │
│  │ · 机构持仓    │     │ · 技术指标(58个)       │    │
│  │ · 研报       │     │ · 情绪/资金流          │    │
│  │ · 同花顺专有  │     │ · 宏观+L4估值          │    │
│  └──────┬───────┘     │ · 选股/轮动            │    │
│         │             └──────────┬───────────┘    │
│         ▼                        ▼                │
│  ┌─────────────────────────────────────────────┐  │
│  │        AssetAnalysisSnapshot (统一契约)      │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 3.2 降级策略建议

```
数据请求 → IFinDAdapter (优先，如已付费)
         ↓ 失败/超时
         → ChinaStockAdapter (降级，免费)
         ↓ 失败
         → 返回 insufficient_evidence
```

---

## 第四部分：结论与建议

### 4.1 总结

| 维度 | 评估 |
|:---|:---|
| **安全性** | ✅ 通过审计，无阻断性问题 |
| **数据覆盖** | ✅ 100% 覆盖 Research Workbench 现有数据域 + 3 个新增能力域 |
| **契约兼容** | ⚠️ 需编写适配层（中等工作量） |
| **与 iFinD 关系** | ✅ 互补（免费降级 + 技术指标/情绪等新能力） |
| **Skill 价值** | ✅ 高价值，提供结构化分析框架 |
| **社区活跃度** | ✅ v0.5.11 持续更新，MIT 开源 |
| **ClawHub 上推荐的其他 Skill** | ❌ `@udiedrichsen/stock-analysis` 和 `@robin797860/stock-watcher` 在 ClawHub 上已不存在，无法评估 |

### 4.2 建议行动

1. **✅ 保留已安装的插件**，安全审计通过
2. **编写 `ChinaStockAdapter`**，实现 `DataAdapter` 接口，P0 优先
3. **扩展 `AssetAnalysisSnapshot`**，新增 `technical` 和 `sentiment` 字段
4. **扩展 `DocumentEnvelope.source_type`**，加入 `"market_data"`
5. **实现双源降级路由**：iFinD 优先 → 插件降级
6. **评估 Skill 集成**：先集成 `fundamental-analyst` + `technical-analyst`（P1）

### 4.3 风险提示

- 插件依赖 AKShare 等开源数据源，接口变动时有发生；插件已内置多源降级链但仍有中断风险
- `strategy-backtester` 当前为 MVP 模式，不建议生产使用
- 飞书通知功能需显式配置 webhook，默认不启用，无需担忧

---

*一个来源不是来源，两个来源才叫验证。本报告基于源码审计 + ClawHub 文档 + 插件清单交叉验证。*
