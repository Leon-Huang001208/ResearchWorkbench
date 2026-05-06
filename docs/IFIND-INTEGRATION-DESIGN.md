# iFinD 数据源接入架构设计

> **文档版本：** v1.0  
> **作者：** 架构师 🏛️  
> **日期：** 2026-05-06  
> **状态：** 待评审  

---

## 1. 设计目标

1. **跨平台**：macOS 和 Windows 均可运行，无需用户手动切换
2. **统一入口**：上层代码只面对 `IFinDAdapter`，不感知后端差异
3. **可降级**：首选后端不可用时自动降级到备选后端
4. **可观测**：所有调用、错误、降级事件均有日志和指标

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                      上层业务（Analysis Pipeline）                  │
│              调用 IFinDAdapter.fetch_stock_quotes() 等             │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                       IFinDAdapter（统一入口）                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  BackendRouter                                              │ │
│  │  - 读取 IFIND_BACKEND 配置（auto / python_sdk / http_api）  │ │
│  │  - auto 模式：macOS → HTTP API 优先，Windows → SDK 优先     │ │
│  │  - 健康检查 + 自动降级                                      │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                             │                                    │
│              ┌──────────────┴──────────────┐                     │
│              ▼                             ▼                     │
│  ┌─────────────────────┐    ┌──────────────────────┐            │
│  │  IFinDSDKClient     │    │  IFinDHTTPClient      │            │
│  │  (Python SDK 后端)   │    │  (HTTP API 后端)       │            │
│  │                     │    │                       │            │
│  │  依赖：iFinD 包      │    │  依赖：httpx           │            │
│  │  平台：Win / Linux   │    │  平台：跨平台           │            │
│  │  需要：iFinD 终端运行 │    │  需要：账号密码         │            │
│  └─────────────────────┘    └──────────────────────┘            │
│              │                             │                     │
│              └──────────┬──────────────────┘                     │
│                         ▼                                        │
│              ┌─────────────────────┐                             │
│              │  IFinDClient        │                             │
│              │  (Protocol 接口)     │                             │
│              └─────────────────────┘                             │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   数据映射层（IFinDMapper）                        │
│     iFinD 原始数据 → AssetAnalysisSnapshot 8 个维度               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 接口定义

### 3.1 IFinDClient Protocol

两个后端 Client 必须实现此 Protocol，保证行为一致：

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class IFinDClient(Protocol):
    """iFinD 客户端协议 - SDK 和 HTTP 后端必须实现"""

    async def login(self) -> bool:
        """登录认证，返回是否成功"""
        ...

    async def logout(self) -> None:
        """登出并释放资源"""
        ...

    async def is_alive(self) -> bool:
        """健康检查：后端是否可用"""
        ...

    async def history(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
        frequency: str = "day",
    ) -> list[dict]:
        """
        历史行情查询
        
        Args:
            codes: 证券代码列表，如 ["600519.SH"]
            indicators: 指标列表，如 ["ths_open_stock", "ths_close_stock"]
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"
            frequency: "day" | "week" | "month"
        """
        ...

    async def realtime(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """实时行情查询"""
        ...

    async def basic(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """基础数据查询（股票资料、行业分类等）"""
        ...

    async def financial(
        self,
        codes: list[str],
        indicators: list[str],
        report_date: str | None = None,
    ) -> list[dict]:
        """财务数据查询"""
        ...

    async def date_serial(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """日期序列数据查询（以时间维度提取基本面）"""
        ...

    async def data_pool(
        self,
        report_name: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """专题报表数据池查询"""
        ...

    async def edb_query(
        self,
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """宏观经济数据库查询"""
        ...
```

### 3.2 IFinDSDKClient（Python SDK 后端）

```python
class IFinDSDKClient:
    """
    Python SDK 后端实现
    
    依赖：iFinD Python 包（pip install iFinD）
    平台：Windows / Linux（需运行 iFinD 终端）
    
    内部封装：
    - THS_iFinDLogin → login()
    - THS_History → history()
    - THS_Realtime → realtime()
    - THS_Basic → basic()
    - THS_Financial → financial()
    - THS_DateSerial → date_serial()
    - THS_DataPool → data_pool()
    - THS_EdbQuery → edb_query()
    """
    
    def __init__(self, username: str, password: str): ...
    
    async def login(self) -> bool:
        """
        调用 THS_iFinDLogin(username, password)
        返回 0 表示成功，其他为错误码
        """
        ...
    
    async def is_alive(self) -> bool:
        """
        检查 iFinD 终端进程是否存在 + SDK 连接是否存活
        """
        ...
```

### 3.3 IFinDHTTPClient（HTTP API 后端）

```python
class IFinDHTTPClient:
    """
    HTTP API 后端实现
    
    依赖：httpx（异步 HTTP 客户端）
    平台：跨平台（macOS 优先选择）
    
    认证流程：
    1. POST /login 传入 username/password
    2. 获取 token，后续请求携带 Authorization: Bearer <token>
    3. token 过期前自动刷新
    """
    
    def __init__(self, username: str, password: str, base_url: str): ...
    
    async def login(self) -> bool:
        """
        POST {base_url}/login
        Body: {"username": "...", "password": "..."}
        Response: {"token": "...", "expires_in": 7200}
        """
        ...
    
    async def is_alive(self) -> bool:
        """
        GET {base_url}/health 或轻量级请求确认 token 有效
        """
        ...
```

### 3.4 IFinDAdapter（统一入口，改造现有 stub）

```python
class IFinDAdapter(BaseDataAdapter):
    """
    iFinD 数据适配器 - 统一入口
    
    职责：
    1. 根据 IFIND_BACKEND 配置选择后端 Client
    2. 调用 Client 获取原始数据
    3. 通过 IFinDMapper 映射为 AssetAnalysisSnapshot
    4. 封装为 DocumentEnvelope 返回
    """
    
    def __init__(self, settings: Settings):
        super().__init__(source_type="ifind")
        self._client = self._create_client(settings)
        self._mapper = IFinDMapper()
        self._logged_in = False
    
    def _create_client(self, settings: Settings) -> IFinDClient:
        """根据配置创建后端 Client"""
        ...
    
    # ── 业务方法（替换现有 stub）──
    
    async def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]: ...
    
    async def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[AssetAnalysisSnapshot]: ...
    
    async def fetch_fund_flow(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]: ...
    
    async def fetch_industry_classification(
        self, codes: list[str]
    ) -> list[AssetAnalysisSnapshot]: ...
    
    async def fetch_macro_indicators(
        self, indicators: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]: ...
    
    # ── DataAdapter 接口实现 ──
    
    def fetch(self, **kwargs) -> list[DocumentEnvelope]: ...
    def parse(self, source, **kwargs) -> DocumentEnvelope: ...
```

---

## 4. BackendRouter 路由逻辑

### 4.1 后端选择策略

```
IFIND_BACKEND = "auto" 时的决策树：

┌─────────────────────────────────┐
│   检测当前操作系统               │
└──────────────┬──────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   macOS             Windows / Linux
       │               │
       ▼               ▼
  首选 HTTP API    首选 Python SDK
       │               │
       ▼               ▼
  HTTP 健康检查    SDK 健康检查
       │               │
   ┌───┴───┐       ┌───┴───┐
   ▼       ▼       ▼       ▼
  可用    不可用   可用    不可用
   │       │       │       │
   ▼       ▼       ▼       ▼
  HTTP    降级     SDK    降级
  API    → SDK?   后端   → HTTP
          │              API
          ▼
    SDK 可用？          │
    ├─ 是 → SDK        │
    └─ 否 → 抛异常     │
                        ▼
                   HTTP 可用？
                   ├─ 是 → HTTP
                   └─ 否 → 抛异常
```

### 4.2 降级规则

| 场景 | 首选后端 | 降级后端 | 行为 |
|:---|:---|:---|:---|
| macOS + auto | HTTP API | 无（SDK 不可用） | HTTP 不可用时直接报错 + 提示 |
| Windows + auto | Python SDK | HTTP API | SDK 不可用时降级到 HTTP |
| Linux + auto | Python SDK | HTTP API | SDK 不可用时降级到 HTTP |
| 显式 python_sdk | Python SDK | 无 | SDK 不可用时直接报错 |
| 显式 http_api | HTTP API | 无 | HTTP 不可用时直接报错 |

### 4.3 macOS 特殊处理

macOS 上 iFinD Python SDK 不可用（官方不支持），`auto` 模式下：

1. **直接选择 HTTP API**，不尝试 SDK
2. 若 HTTP API 也不可用，抛出 `IFinDUnavailableError`，附带提示：
   > "iFinD Python SDK 不支持 macOS，当前 HTTP API 也不可用。请检查网络连接或尝试在 Windows 环境运行。"

---

## 5. 数据映射

### 5.1 iFinD 函数 → 6大数据域 映射表

| # | 数据域 | iFinD 函数 | 说明 | 关键参数 |
|:--|:---|:---|:---|:---|
| 1 | A股行情（日K） | `history()` | 历史行情函数，frequency="day" | indicators: ths_open_stock, ths_high_stock, ths_low_stock, ths_close_stock, ths_vol_stock |
| 2 | 财务报表 | `financial()` + `date_serial()` | financial 取报表数据，date_serial 按时间序列取 | indicators: ths_eps_basic_stock, ths_roe_stock, ths_net_profit_stock 等 |
| 3 | 资金流向 | `data_pool()` + `basic()` | 专题报表取资金流，basic 取主力资金 | report_name: "资金流向", indicators: ths_mf_net_amount_stock 等 |
| 4 | 行业分类/指数 | `basic()` | 基础数据函数取行业分类 | indicators: ths_industry_stock, ths_index_stock 等 |
| 5 | 宏观经济指标 | `edb_query()` | EDB 宏观经济数据库 | indicators: CPI, PPI, M2 等 EDB 指标代码 |
| 6 | 研报全文 | `data_pool()` + 外部爬取 | 专题报表取研报摘要，全文需外部爬取 | report_name: "研究报告" |

### 5.2 iFinD 原始数据 → AssetAnalysisSnapshot 映射规则

`AssetAnalysisSnapshot` 的 8 个维度与数据域的对应关系：

```
┌───────────────────────┐     ┌──────────────────────────────────────┐
│  AssetAnalysisSnapshot│     │  数据来源                            │
├───────────────────────┤     ├──────────────────────────────────────┤
│  financial            │ ◄── │  数据域2: 财务报表                    │
│  fund_flow            │ ◄── │  数据域3: 资金流向                    │
│  price_volume         │ ◄── │  数据域1: A股行情（日K）              │
│  valuation            │ ◄── │  数据域1 + 2: 行情 × 财务计算        │
│  shareholder          │ ◄── │  数据域2: 财务报表（股东部分）        │
│  industry             │ ◄── │  数据域4: 行业分类/指数               │
│  event_impact         │ ◄── │  数据域6: 研报全文（事件提取）        │
│  macro_exposure       │ ◄── │  数据域5: 宏观经济指标                │
└───────────────────────┘     └──────────────────────────────────────┘
```

### 5.3 各维度映射细节

#### 5.3.1 `financial`（财务维度）

```
iFinD financial() 返回
    → ths_eps_basic_stock     → financial["eps"]
    → ths_roe_stock           → financial["roe"]
    → ths_net_profit_stock    → financial["net_profit"]
    → ths_revenue_stock       → financial["revenue"]
    → ths_gross_margin_stock  → financial["gross_margin"]
    → ths_debt_ratio_stock    → financial["debt_ratio"]
    → ths_current_ratio_stock → financial["current_ratio"]
```

#### 5.3.2 `fund_flow`（资金流向维度）

```
iFinD data_pool("资金流向") 返回
    → 主力净流入              → fund_flow["main_net_inflow"]
    → 超大单净流入            → fund_flow["super_large_net_inflow"]
    → 大单净流入              → fund_flow["large_net_inflow"]
    → 中单净流入              → fund_flow["medium_net_inflow"]
    → 小单净流入              → fund_flow["small_net_inflow"]
```

#### 5.3.3 `price_volume`（量价维度）

```
iFinD history() 返回
    → ths_open_stock   → price_volume["open"]
    → ths_high_stock   → price_volume["high"]
    → ths_low_stock    → price_volume["low"]
    → ths_close_stock  → price_volume["close"]
    → ths_vol_stock    → price_volume["volume"]
    → ths_turnover_stock → price_volume["turnover"]
    → 计算均线(MA5/MA20/MA60) → price_volume["ma5"] / ["ma20"] / ["ma60"]
```

#### 5.3.4 `valuation`（估值维度）

```
由 price_volume + financial 联合计算
    → 市盈率 PE = close / eps          → valuation["pe"]
    → 市净率 PB = close / bps          → valuation["pb"]
    → 市销率 PS = close / sps          → valuation["ps"]
    → EV/EBITDA                        → valuation["ev_ebitda"]
    → 股息率                            → valuation["dividend_yield"]
```

#### 5.3.5 `shareholder`（股东维度）

```
iFinD financial() 返回（股东相关指标）
    → 前十大股东            → shareholder["top10_holders"]
    → 机构持仓比例          → shareholder["institutional_holding_pct"]
    → 股东户数变化          → shareholder["holder_count_change"]
    → 大股东增减持          → shareholder["major_shareholder_trades"]
```

#### 5.3.6 `industry`（行业维度）

```
iFinD basic() 返回
    → 申万行业分类          → industry["sw_industry"]
    → 证监会行业分类        → industry["csrc_industry"]
    → 所属概念板块          → industry["concept_boards"]
    → 同行业排名            → industry["industry_rank"]
```

#### 5.3.7 `event_impact`（事件影响维度）

```
iFinD data_pool("研究报告") 返回
    → 研报标题 + 评级       → event_impact 中追加 "研报: {title} | 评级: {rating}"
    → 重大事件标签          → event_impact 中追加事件标签

注意：此维度为 list[str]，每条为一个事件/研报摘要
```

#### 5.3.8 `macro_exposure`（宏观暴露维度）

```
iFinD edb_query() 返回
    → CPI 同比              → macro_exposure["cpi_yoy"]
    → PPI 同比              → macro_exposure["ppi_yoy"]
    → M2 同比               → macro_exposure["m2_yoy"]
    → PMI                   → macro_exposure["pmi"]
    → LPR                   → macro_exposure["lpr"]
    → 社融规模              → macro_exposure["social_financing"]
    → 行业景气度            → macro_exposure["industry_pmi"]
```

---

## 6. IFinDMapper 设计

```python
class IFinDMapper:
    """
    iFinD 原始数据 → AssetAnalysisSnapshot 映射器
    
    职责：
    1. 将 iFinD Client 返回的原始 dict 转换为 AssetAnalysisSnapshot
    2. 计算衍生指标（估值、均线等）
    3. 生成 canonical_id 和 as_of 时间戳
    """
    
    def map_quotes(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> AssetAnalysisSnapshot: ...
    
    def map_financial(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> AssetAnalysisSnapshot: ...
    
    def map_fund_flow(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> AssetAnalysisSnapshot: ...
    
    def map_industry(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> AssetAnalysisSnapshot: ...
    
    def map_macro(
        self, indicators: list[str], raw_data: list[dict], as_of: datetime
    ) -> AssetAnalysisSnapshot: ...
    
    def map_research_report(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> AssetAnalysisSnapshot: ...
```

**映射规则核心原则：**

1. **缺失字段不报错**：iFinD 返回的字段可能不全，缺失的维度保持 `default_factory=dict` 的空 dict
2. **指标名标准化**：iFinD 的 `ths_xxx_stock` 格式转换为简短的 snake_case
3. **canonical_id 生成**：`ifind:{code}:{as_of.strftime("%Y%m%d")}:{domain_hash}`
4. **evidence_refs 记录**：每次映射记录原始数据指纹，便于溯源

---

## 7. 错误处理与降级策略

### 7.1 错误分类

| 错误类型 | 错误类 | 场景 | 处理策略 |
|:---|:---|:---|:---|
| 认证失败 | `IFindAuthError` | 账号密码错误、token 过期 | 重试 1 次（重新登录），仍失败则抛出 |
| 网络不可达 | `IFindNetworkError` | HTTP API 请求超时/连接拒绝 | 降级到备选后端（如果有） |
| SDK 终端离线 | `IFindTerminalOfflineError` | iFinD 终端未运行 | 降级到 HTTP API，或提示启动终端 |
| 配额耗尽 | `IFindQuotaExhaustedError` | API 调用次数达到上限 | 告警 + 缓存兜底 |
| 数据缺失 | `IFindDataMissingError` | 请求的指标/代码不存在 | 记录警告，返回空维度 |
| 平台不支持 | `IFindPlatformError` | macOS 上使用 SDK | 抛出明确错误提示 |

### 7.2 降级决策流程

```
调用 IFinDAdapter 方法
         │
         ▼
   ┌─────────────┐
   │ 首选后端调用 │
   └──────┬──────┘
          │
    ┌─────┴─────┐
    ▼           ▼
  成功        失败
    │           │
    ▼           ▼
  返回     检查错误类型
              │
    ┌─────────┼──────────┐
    ▼         ▼          ▼
  网络错误  认证错误   配额/终端错误
    │         │          │
    ▼         ▼          ▼
 有备选？  重新登录   有备选？
    │     后重试       │
  ┌─┴─┐    │        ┌─┴─┐
  ▼   ▼    ▼        ▼   ▼
 是   否  重试     是   否
  │   │    │       │    │
  ▼   ▼    ▼       ▼    ▼
降级 抛出 成功?   降级  告警+
调用 异常  │      调用 缓存
        ┌─┴─┐
        ▼   ▼
       是   否
        │    │
        ▼    ▼
      返回  降级/抛出
```

### 7.3 配额管理

```python
class IFinDQuotaManager:
    """
    配额管理器
    
    职责：
    1. 记录每次 API 调用
    2. 当日调用次数接近限额时发出 WARNING
    3. 超过限额时阻断请求并告警
    """
    
    # 建议配置
    DAILY_QUOTA_WARNING_THRESHOLD = 0.8   # 80% 时告警
    DAILY_QUOTA_HARD_LIMIT = 1.0          # 100% 时阻断
    
    def check_quota(self) -> bool: ...
    def record_call(self, api_name: str, cost: int = 1) -> None: ...
    def get_remaining(self) -> int: ...
```

### 7.4 缓存兜底

当配额耗尽或后端完全不可用时，使用本地缓存作为最后兜底：

- **缓存 key**：`ifind:{domain}:{code}:{date}`
- **缓存时间**：行情数据 T+0 过期，财务数据 7 天过期，宏观数据 30 天过期
- **缓存存储**：SQLite 表 `ifind_cache`，存储序列化后的 `AssetAnalysisSnapshot`
- **降级行为**：返回缓存数据 + `metadata["from_cache"] = True` + `metadata["cache_age"] = "2h30m"`

---

## 8. 登录生命周期管理

```
┌──────────────────────────────────────────────────────┐
│                  IFinDAdapter 生命周期                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  初始化 ──→ login() ──→ 业务调用 ──→ logout()       │
│                  │                      │             │
│                  ▼                      ▼             │
│           认证成功/失败           上下文退出时         │
│                  │               自动 logout          │
│                  ▼                                    │
│         token 刷新定时器                              │
│         (HTTP: 过期前 5min 刷新)                      │
│         (SDK: 心跳保活)                              │
│                                                      │
│  推荐：使用 async with 上下文管理器                    │
│                                                      │
│  async with IFinDAdapter(settings) as adapter:       │
│      data = await adapter.fetch_stock_quotes(...)    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 9. 模块文件结构

```
data_layer/
└── adapters/
    └── ifind/
        ├── __init__.py              # 导出 IFinDAdapter
        ├── adapter.py               # IFinDAdapter 统一入口
        ├── client_protocol.py       # IFinDClient Protocol 定义
        ├── sdk_client.py            # IFinDSDKClient 实现
        ├── http_client.py           # IFinDHTTPClient 实现
        ├── backend_router.py        # BackendRouter 后端选择 + 降级
        ├── mapper.py                # IFinDMapper 数据映射
        ├── quota.py                 # IFinDQuotaManager 配额管理
        ├── cache.py                 # IFinDCache 缓存兜底
        └── exceptions.py            # 自定义异常类
```

现有 `data_layer/adapters/ifind_adapter.py` 保留为兼容入口，内部委托给 `ifind/adapter.py`。

---

## 10. 配置项汇总

| 配置项 | 环境变量 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|:---|
| IFIND_USERNAME | `IFIND_USERNAME` | str | "" | iFinD 账号 |
| IFIND_PASSWORD | `IFIND_PASSWORD` | str | "" | iFinD 密码 |
| IFIND_BACKEND | `IFIND_BACKEND` | Literal | "auto" | 后端选择：auto / python_sdk / http_api |
| IFIND_HTTP_BASE_URL | `IFIND_HTTP_BASE_URL` | str | "https://quantapi.10jqka.com.cn" | HTTP API 基础 URL |
| IFIND_CACHE_TTL_QUOTES | — | int | 0 | 行情缓存 TTL（秒），0=不缓存 |
| IFIND_CACHE_TTL_FINANCIAL | — | int | 604800 | 财务缓存 TTL（7天） |
| IFIND_CACHE_TTL_MACRO | — | int | 2592000 | 宏观缓存 TTL（30天） |
| IFIND_DAILY_QUOTA | — | int | 10000 | 每日 API 调用限额 |
| IFIND_REQUEST_TIMEOUT | — | int | 30 | 单次请求超时（秒） |
| IFIND_RETRY_TIMES | — | int | 2 | 失败重试次数 |

---

## 11. ADR：架构决策记录

### ADR-001：双后端而非单后端

**决策**：采用 SDK + HTTP 双后端架构，而非只选一种。

**原因**：
- SDK 优势：数据更全（高频/快照）、延迟更低、无需网络
- SDK 劣势：macOS 不支持、需安装终端
- HTTP 优势：跨平台、零依赖、部署简单
- HTTP 劣势：部分数据类型可能不可用、有网络延迟

**结论**：两者互补，auto 模式让用户无感切换。

### ADR-002：Protocol 而非 ABC

**决策**：`IFinDClient` 使用 `typing.Protocol` 而非 `abc.ABC`。

**原因**：
- SDK 和 HTTP 实现没有共同状态，不需要继承
- Protocol 支持结构化子类型（鸭子类型），更灵活
- 两个 Client 可以独立演进，不需要共同基类

### ADR-003：异步优先

**决策**：所有 Client 方法使用 `async def`。

**原因**：
- HTTP 请求天然异步
- SDK 调用可通过 `asyncio.to_thread()` 包装同步函数
- 上层 Pipeline 已是异步架构
- 避免阻塞事件循环

### ADR-004：映射层独立

**决策**：`IFinDMapper` 作为独立类，不嵌入 Client。

**原因**：
- 映射逻辑与数据获取逻辑正交
- 两个后端返回的原始数据格式可能不同，Mapper 可分别处理
- 便于单元测试（mock 原始数据即可）
- 未来新增数据域时只需修改 Mapper

---

## 12. 风险与待确认项

| # | 风险 | 影响 | 缓解措施 | 状态 |
|:--|:---|:---|:---|:--|
| 1 | HTTP API 可能不支持所有 SDK 函数 | 部分数据域在 macOS 上不可用 | 文档标注各数据域的平台支持矩阵 | 待验证 |
| 2 | HTTP API 的具体端点和参数未公开 | 实现时可能需要逆向 | 联系同花顺获取正式文档 | 待确认 |
| 3 | 免费用户数据范围限制（5年） | 历史回测受限 | 配置中标注数据范围，超范围请求返回警告 | 已知 |
| 4 | EDB 宏观数据免费用户不可用 | 宏观暴露维度为空 | 降级为可选维度，告警提示 | 已知 |
| 5 | 研报全文需要外部爬取 | 增加实现复杂度 | 第一期仅支持研报摘要，全文留作后续迭代 | 已确认 |

---

## 13. 实施建议

### Phase 1：最小可用（1-2 天）
- 实现 `IFinDHTTPClient`（HTTP API 后端）
- 实现 `IFinDAdapter` 统一入口
- 实现 `IFinDMapper`（行情 + 财务 2 个维度）
- 实现 `BackendRouter`（auto 模式 + HTTP 优先）

### Phase 2：SDK 集成（1 天）
- 实现 `IFinDSDKClient`（Windows 环境测试）
- 完善 `BackendRouter` 降级逻辑
- 实现 `IFinDQuotaManager`

### Phase 3：全维度 + 缓存（2 天）
- 补全 6 大数据域映射
- 实现 `IFinDCache`
- 集成测试

---

> **架构师评语**：这个架构能撑三年吗？  
> —— 双后端 + Protocol + Mapper 的分层设计，为未来新增数据源（Wind、Choice 等）留了扩展空间。IFinDClient Protocol 可直接复用为通用数据源协议。假设同花顺不改变 API 契约，三年内只需在 Mapper 层适配新指标即可。
