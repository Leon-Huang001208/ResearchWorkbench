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
