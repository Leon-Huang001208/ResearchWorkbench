# 研究场景与 Seek Alpha 静态对照目录

首建自选或新增导入目标只刷新当前账户列表metadata，保留原观察/草稿，不创建场景或触发额外取数、模型。

自选CSV仅维护原资产列表，不创建或发送研究场景；不把名称匹配、导入成功或列表轮询设置当作来源/模型/方法授权，见[自选导入](research-web-watchlist-import.md)。

本模块位于 `app/research_web/scenarios/`，版本 `1.0.0`。它只提供只读参考与研究合同选择，执行、历史、冻结与报告质量仍归既有 ResearchService／能力目录／唯一 DSH。目录不调用供应商、模型、MCP，不创建会话、文件或投递任务。应用原有 logging handler 负责把标准 logger 事件写入 `logs/`，本模块不配置额外日志目的地。

## 参考证据范围

观察日为 **2026-10-26**，只认证以下静态证据。

| 来源 | 保留范围 | 数量 | 原文件 SHA-256 |
| --- | --- | --- | --- |
| `https://seek-alpha.cn/skills` | 从已登录目录提取的去重名称；`catalog_names_only`，不保留页面、账号信息或私有内容 | 62 | `b6832ef98ee84d5b6f344d37c07a8268067876f361c48c4fcdbbf6c13ec1664f` |
| `https://seek-alpha.cn/api/mcp/tools-meta` | 公开工具定义的精确名称、分组、成本、internal、参数名称与类型；正文为简短转述 | 78 | `b1b474d8a3a9698f7c8976aa28d5f64b7d48530376a1207257cfab6916a64763` |

工具元数据另有 12 个分组（含 all）、10 个成本 tier、9 个组合包、1 个内部工具。发布的 initialCredits=2000 仅为供应商元数据，不代表当前用户余额。逐工具原始定义摘要使用 UTF-8 JSON、`ensure_ascii=False`、`sort_keys=True`、`separators=(',', ':')`；整文件摘要绑定原始字节。

`baseline.json` 为 140 项逐项映射，保留稳定 ID、来源、领域、RWB 候选能力、候选源码身份、实现路线及尚未核实的数据／权限／schema 依赖。路线枚举为 `reuse`、`native`、`managed_mcp`、`declared_dependency`、`deferred`；它表示实现方向，而非当前执行状态。现有源码只能说明复用候选，供应商数据库、模型与 RWB 数据是否等价必须另证。全部项固定 `status=unverified`、`callable=false`、`runtime_verified=false`、`quality_passed=false`。

四个专有形态工具 `technical_analysis`、`run_morphology`、`etf_view`、`query_morphology_signals` 保留华创模型许可依赖；RWB 技术指标不代表模型等价。`query_financial_db` 保留 `internal=true`／`internal_only`／`deferred`，不能从公开定义获得 SQL 或数据库权限。

九个组合包可按精确 `pack_*` 工具名追溯；各分路窗口、数据语义和覆盖分开核对。深研提交为 20，状态、列表与停止各 1，总费用取决于真实调用次数，不能称为总价 20。`generate_video` 的 `cost=200` 保留；desc 的 480p=200、720p=300 与 use 的 480p=100、720p=300 存在冲突，因此不作确定报价。

## 首批八个场景

`contracts.json` 保存完整中文合同、输入说明、步骤、原工具家族、样例、期望草稿、覆盖及缺失数据处理。

| 稳定 ID | 中文名称 | 既有能力候选 | 核心数据要求 |
| --- | --- | --- | --- |
| `company-onepager` | 公司一页纸 | `company-research` | 公司披露、财务、估值 |
| `industry-onepager` | 行业一页纸 | `industry-research` | 分类版本、行业统计、行业材料 |
| `fundamentals` | 基本面分析 | `company-research` | 财务、披露、估值与会计口径 |
| `technicals` | 技术面分析 | `chanlun` | 同版本复权 OHLCV、公司行动、交易日历；不覆盖专有形态模型 |
| `news-query` | 新闻查询 | `finance-news-event-research` | 获准新闻原文及发布时间 |
| `news-transmission` | 新闻传导分析 | `finance-news-event-research`、`industry-chain-research` | 原文、时间及产业链证据 |
| `research-prep` | 调研前置 | `company-research` | 披露、历史调研与获准研究材料 |
| `historical-review` | 历史复盘 | `event-review` | 事件、复权行情、基准及历史可得性 |

共同输入为 `subject={kind, identity, name?}`、`question`（问题及背景）、`as_of`（ISO 自然日截止）、`material_ids`（已选材料身份）。`kind` 为 `stock|industry|topic`，各场景限定可用种类。股票使用带市场的身份，例如 `600600.SH`／`0700.HK`／`AAPL.US`；行业使用分类命名空间身份，例如 `SW:801080`。展示名不能代替身份。`historical-review` 另需 `window_start`，且不晚于截止日。未知字段、无效日期、任意文件路径或 URL 材料身份拒绝。

新闻查询允许独立主题与空 `material_ids`，覆盖只代表当前选择和实际检索。其他场景缺材料列出 `materials_missing`。缺任何硬数据依赖时输出缺口与 `incomplete`，不编造、不静默替源、不付费补调，不把首次观察冒充历史 PIT。场景合同只要求后续原链生成带来源的研究草稿与覆盖／缺口台账；正式报告须继续通过原 canonical report 和质量门。

## 纯读取与选择 API

```python
from app.research_web.scenarios import (
    ScenarioError, get_scenario, read_catalog, read_scenarios, select_scenario,
)

catalog = read_catalog()  # 每次返回独立副本
contract = get_scenario("company-onepager")
result = select_scenario(
    "company-onepager",
    {
        "subject": {"kind": "stock", "identity": "600600.SH"},
        "question": "基于已选材料核对业务驱动与风险",
        "as_of": "2026-10-26",
        "material_ids": ["selected-material-id"],
    },
    capability_qualification=host_capability_facts,
    evidence_eligibility=host_evidence_facts,
    owner_id=authenticated_owner_id,
)
```

两张资格表及 `owner_id` **只能由 Host 根据当前已鉴权目录、材料归属及真实冻结证据构建，HTTP 请求不得直接自报**。能力表为 `{capability_slug: {owner_id, available: bool}}`；证据表为 `{required_data_id: {owner_id, eligible: bool}}`。Host 必须在形成布尔值前验证准确能力版本、工具／数据准入、来源归属、证券／期间／截止／单位／频率、冻结身份及适用 PIT 资格。这里只接受严格 `True`，不从文字、技能名、静态映射或凭据存在推断。

缺失、不可用、他人资格分别产生 `*_missing`、`*_unverified`、`*_foreign` 缺口；未知能力或数据身份拒绝整个资格输入。即使 `eligible_for_draft=true`，输出的 `frozen`、`send_authorized`、`runtime_verified`、`quality_passed`、`auto_send` 仍全部为 false；下一步的准备、冻结、发送授权和质量认证须由原 Host 流程分别完成。当前代码不执行上述流程。

`read_catalog(path=...)` 的可选路径只用于内部验证／部署检查，绝不能接收 HTTP 路径；替代位置仍必须匹配代码固定摘要。不可读、过大或篡改的参考均拒绝，不回退空目录。稳定错误码为 `scenario_catalog_unreadable`、`scenario_baseline_invalid`、`scenario_unknown`、`scenario_inputs_invalid`、`scenario_qualification_invalid`。日志仅含固定错误码，不包含私有输入、目录全文、路径或来源内容。

## 验证与后续边界

聚焦测试为 `tests/research_web/test_research_scenarios_catalog.py`，兼容 stdlib unittest 与项目 pytest。验证覆盖原始名称／工具身份／费用／internal／参数／摘要，140 项静态边界与副本隔离，八场景选择、日期和资料输入，未知／缺失／他人资格，读取失败、超限与只读副作用边界。

本模块不新增依赖、运行器、API、UI 或服务。Web 安装、原生页面与实际 DSH／MCP／供应商执行须由集成任务按原门另验。静态对照和本地测试不表示功能全量对齐或质量验收通过。

## Host三页功能集成

纯目录合同保持不变。实际场景选择、冻结、发送、资讯筛选及撤权边界见[三页场景交接](research-web-scenario-handoffs.md)，包版本与实际执行准入分别报告。
