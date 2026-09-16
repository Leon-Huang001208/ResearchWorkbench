# Benchmark Format & Annotation Guide

## Gold Dataset Format

All benchmark datasets use **JSON Lines** (`.jsonl`) format — one JSON object per line.

### Event Extraction Benchmark (`datasets/event_extraction_v1.jsonl`)

Each line is a `BenchmarkCase` JSON object:

```json
{
  "case_id": "ee_v1_001",
  "input_text": "中文财经新闻全文...",
  "source_type": "news",
  "gold": {
    "event_type": "policy",
    "subject_ids": ["600000.SH"],
    "thesis": "政策利好推动银行板块估值修复",
    "impact_path": ["降准 → 银行净息差扩大 → 银行股估值修复"],
    "bullish_companies": ["600000.SH", "601398.SH"],
    "bearish_companies": [],
    "score": 0.7,
    "confidence": 0.6,
    "diffusion_stage": "early_awareness",
    "industry_impacts": ["finance"],
    "market_regime": null
  }
}
```

### Subject Mapping Benchmark (`datasets/subject_mapping_v1.jsonl`)

Same `BenchmarkCase` format, but focused on testing the event → industry chain → A-share subject mapping pipeline. Cases emphasize different mapping scenarios:

- **Direct code mention**: text explicitly includes stock codes
- **Company name only**: text mentions company names without codes
- **Indirect impact**: text mentions an industry/policy without naming specific companies

## Annotation Guide

### event_type

| Value | Description | Example Triggers |
|-------|-------------|-----------------|
| `earnings` | 财报/业绩相关 | 一季报、年报、营收、净利润 |
| `policy` | 政策/监管相关 | 降准、新规、补贴、国务院 |
| `product` | 产品/技术相关 | 发布新品、量产、技术突破 |
| `merger_acquisition` | 并购重组 | 收购、并购、重组 |
| `rating_change` | 评级变动 | 上调、减持、买入评级 |
| `supply_chain` | 供应链相关 | 断供、涨价、缺货 |
| `macro` | 宏观经济 | GDP、CPI、利率、社融 |

### subject_ids

A-share stock codes in `NNNNNN.SH` or `NNNNNN.SZ` format (Shanghai/Shenzhen). Only include codes that are **directly mentioned or unambiguously derivable** from the text.

### thesis

One-sentence investment logic summary. Should capture: what happened → why it matters → what the trade is.

### impact_path

Causal chain from event to stock price impact. Each element is one step in the chain.

### industry_impacts

From the standardized list: `semiconductor`, `new_energy`, `ai`, `pharmaceutical`, `consumer`, `finance`, `real_estate`, `auto`.

### diffusion_stage

| Value | Description |
|-------|-------------|
| `discovery` | First report, very few aware |
| `early_awareness` | Some coverage, not mainstream |
| `theme_trading` | Active trading on the theme |
| `institutional_coverage` | Sell-side reports appearing |
| `consensus` | Broad market agreement |
| `decay` | Theme fading, diminishing returns |

## Evaluation Metrics

### Event Type Accuracy

Simple accuracy: `correct / total`

### Subject ID Precision / Recall / F1

- **Precision**: Of all predicted subject IDs, what fraction are in the gold set?
- **Recall**: Of all gold subject IDs, what fraction were predicted?
- **F1**: Harmonic mean of precision and recall

### Thesis Similarity

Keyword-overlap based similarity (Jaccard coefficient of token sets):

```
similarity = |tokens(predicted) ∩ tokens(gold)| / |tokens(predicted) ∪ tokens(gold)|
```

### Grouped Metrics

Results are broken down by `event_type` and `source_type` for granular analysis.

## Research Method Evals (`datasets/research_methods_v1.jsonl`)

该数据集是独立于 Research Web 产品 API 和工程 Harness 的固定合成证据集。它恰好包含三个
版本化场景：来源冲突、产业链比较和陌生领域验证。每个场景包含 4–8 条带稳定
`evidence_id`、`source_tier`、`stance` 与 `as_of` 的证据；至少一条反方证据且至少覆盖两种来源层级。

运行器为 `python -m benchmarks.research_methods`。CLI 复用项目 `ModelGatewayImpl` 与当前
`TASK_REASONING` 路由；共用 OpenAI-compatible provider 在 SDK 不可用时使用既有 `httpx` 后备，
不会复制评测专用模型客户端或回退到其他 provider。一次完整运行固定执行 63 次 `reasoning` 调用：

- 3 个在所有方法间复用的 baseline；
- 10 个 Method × 3 个场景的 single 变体；
- 10 个 Method × 3 个场景的 combined 变体。

所有变体共享相同结构化输出契约，使用 `temperature=0`、固定随机顺序和相同 token 上限。
评分只读取可观察字段：有效证据 ID、来源分层、反证、决定变量、因果步骤、专家冲突、跨域
失效条件、实验样本、停止条件和决策阈值，不使用 judge model 或隐藏思维链。

原始请求对应的模型输出仅写入私有目录
`~/.research-workbench/research-evals/<run-id>/`（目录 `0700`、文件 `0600`）。仓库结果目录
`benchmarks/results/research_methods_v1/` 只保存逐项分数、请求/响应 SHA-256、模型标识、token
成本代理、延迟和汇总，不保存 Prompt、证据正文或模型正文。任一调用失败或结构化输出无效时，
整轮失败关闭且不产生晋级候选。

single 相对同场景 baseline 必须质量提高，同时平均 token 与延迟均不超过 baseline 的 110%，
且该方法关键 rubric 在三个 single 场景均非零，才会列为人工审阅候选。combined 只用于组合
分析；运行器不会自动修改 `method_policy.recommended`。
