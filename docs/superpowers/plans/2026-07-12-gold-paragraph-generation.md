# Gold Paragraph Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Huaan ETF weekly report produce a deterministic Excel-backed gold market review and a natural, evidence-grounded gold analysis paragraph matching the causal style of the approved reference.

**Architecture:** Keep numeric market review and narrative analysis as separate placeholders. Route `黄金市场回顾` through the existing `excel_commodity_market_review` generator, while `黄金` continues through the shared evidence AI pipeline with gold-specific retrieval terms, causal writing structure, and output constraints stored only in project configuration.

**Tech Stack:** Python, pytest, YAML, Markdown prompt templates, existing `ReportProjectGenerationService`.

---

### Task 1: Lock the gold configuration contract with a failing test

**Files:**
- Create: `tests/unit/test_gold_report_prompt_config.py`
- Read: `report_projects/华安ETF周报/config/section_config.yaml`
- Read: `report_projects/华安ETF周报/config/prompt_templates.md`

- [ ] **Step 1: Write the failing configuration test**

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SECTION_CONFIG = ROOT / "report_projects" / "华安ETF周报" / "config" / "section_config.yaml"
PROMPT_TEMPLATES = ROOT / "report_projects" / "华安ETF周报" / "config" / "prompt_templates.md"


def test_gold_review_is_excel_backed_and_analysis_is_causal():
    config = yaml.safe_load(SECTION_CONFIG.read_text(encoding="utf-8"))
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    common_constraints = "\n".join(config["defaults"]["generation_constraints"])
    review = config["placeholders"]["黄金市场回顾"]
    gold = config["placeholders"]["黄金"]
    structure = "\n".join(gold["writing_structure"])
    gold_prompt = prompt_source.split("## 黄金\n", 1)[1].split("\n## ", 1)[0]

    assert review["type"] == "excel_commodity_market_review"
    assert review["data_source"] == {
        "kind": "gold",
        "workbook": "周报数据.xlsx",
        "sheet": "黄金",
    }
    for gold_only_term in ["央行购金", "实际利率", "黄金ETF", "国际金价"]:
        assert gold_only_term not in common_constraints
    assert "整体方向和节奏" in structure
    assert "核心驱动" in structure
    assert "传导" in structure
    assert "不强行覆盖" in structure
    assert "后续" in structure
    assert config["defaults"]["retrieval"]["top_k"] == 10
    assert "top_k" not in gold["retrieval"]
    assert "美元指数" in gold["retrieval"]["keywords"]
    assert "实际利率" in gold["retrieval"]["keywords"]
    assert "不得重复前文价格数字" in gold_prompt
    assert "不得输出来源括号" in gold_prompt
    assert "直接解释本周国际金价" in gold_prompt
```

- [ ] **Step 2: Run the test and confirm the current configuration fails**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_gold_report_prompt_config.py -q
```

Expected: FAIL because `黄金市场回顾` is still `paragraph`, the gold retrieval keyword list is absent, and the approved output constraints are not in the prompt.

- [ ] **Step 3: Commit the failing test only after observing the expected failure**

```bash
git add tests/unit/test_gold_report_prompt_config.py
git commit -m "test: define gold report prompt contract"
```

### Task 2: Configure deterministic review and causal gold analysis

**Files:**
- Modify: `report_projects/华安ETF周报/config/section_config.yaml:513-543`
- Modify: `report_projects/华安ETF周报/config/prompt_templates.md:166-182`
- Test: `tests/unit/test_gold_report_prompt_config.py`
- Test: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Replace the gold market review configuration**

Set `黄金市场回顾` to:

```yaml
  黄金市场回顾:
    title: 黄金市场回顾
    type: excel_commodity_market_review
    data_source:
      kind: gold
      workbook: 周报数据.xlsx
      sheet: 黄金
    params:
      param: 黄金
```

- [ ] **Step 2: Replace the gold analysis retrieval and writing structure**

Keep the shared evidence pipeline and configure only the `黄金` placeholder:

```yaml
  黄金:
    title: 黄金
    type: paragraph
    confirmed: true
    mode: evidence_ai
    prompt_template: 黄金
    query_mode: retrieval_query_embedded
    target_words: 300
    max_words: 300
    min_news_count: 5
    retrieval:
      keyword_profile: 黄金
      keywords:
      - 黄金
      - 国际金价
      - 伦敦金
      - COMEX黄金
      - 美联储
      - 降息预期
      - 加息预期
      - 非农就业
      - 美国通胀
      - 美元指数
      - 美债收益率
      - 实际利率
      - 央行购金
      - 黄金ETF
      - 期货持仓
      - 避险需求
      - 地缘政治
    writing_structure:
    - 首句概括本周国际金价的整体方向和节奏，例如震荡上行、先抑后扬、低位反弹或高位回落
    - 选择证据最充分且解释力最强的因素作为核心驱动，说明宏观数据或政策预期如何改变市场对美联储政策的判断
    - 说明上述预期如何通过美元指数、美债收益率或实际利率影响黄金的配置吸引力，形成清晰传导链
    - 根据材料补充央行购金、ETF或期货资金、避险需求、地缘风险、通胀预期或仓位变化等辅助因素；材料不足时不强行覆盖
    - 末句判断本周行情性质，并列出后续最值得关注的二至四项变量，不预测具体价格点位
    params:
      param: 黄金
```

- [ ] **Step 3: Replace the `## 黄金` prompt block**

Use:

````text
## 黄金

```text
检索 Query：检索能够直接解释本周国际金价变化的材料，重点关注美联储政策预期、美国就业与通胀数据、美元指数、美债收益率和实际利率，并根据证据补充央行购金、黄金ETF或期货资金、避险需求及地缘政治变化。

写作要求：写成一个可直接放入周报的自然段。先判断本周国际金价的整体方向和节奏，再选择解释力最强的核心驱动，说明其如何影响政策预期并通过美元、利率或资金行为传导至金价；其余因素只在 Evidence 充分时补充，不得逐条罗列材料。结尾概括行情性质，并列出后续关注变量。具体事实、数字和事件必须来自 Evidence；不得重复前文价格数字，不得输出 Evidence 编号、来源括号、分析过程、标题、列表、投资建议或具体价格预测。
```
````

- [ ] **Step 4: Run focused tests**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_gold_report_prompt_config.py tests/unit/test_report_projects_api.py -q
```

Expected: PASS with zero failures.

- [ ] **Step 5: Commit the configuration change**

```bash
git add report_projects/华安ETF周报/config/section_config.yaml report_projects/华安ETF周报/config/prompt_templates.md tests/unit/test_gold_report_prompt_config.py
git commit -m "fix: improve gold weekly report generation"
```

### Task 3: Generate and inspect the real gold output

**Files:**
- Read: `report_projects/华安ETF周报/config/section_config.yaml`
- Read: `report_projects/华安ETF周报/config/prompt_templates.md`
- Read: `report_projects/华安ETF周报/data/周报数据.xlsx`
- Verify: `logs/`

- [ ] **Step 1: Run a gold-only generation using the real project configuration**

Run a Python snippet that loads `ReportProjectManager().get_project("华安ETF周报")`, narrows the loaded section configuration to `黄金市场回顾` and `黄金`, and calls `ReportProjectGenerationService.generate_placeholders(...)` with the current report period.

Expected: `黄金市场回顾` is generated by provider `excel` with zero Evidence; `黄金` is generated by the reporting model using evidence candidates.

- [ ] **Step 2: Inspect the generated analysis against the approved style**

Confirm all of the following:

- The first sentence states a weekly direction and rhythm.
- One core driver is clearly prioritized.
- The paragraph contains a readable causal transmission chain.
- Secondary factors appear only when supported.
- The final sentence identifies future monitoring variables.
- There are no Evidence identifiers, source parentheses, duplicated market-review prices, headings, or lists.

- [ ] **Step 3: Run final static and regression verification**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m ruff check tests/unit/test_gold_report_prompt_config.py
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_gold_report_prompt_config.py tests/unit/test_report_projects_api.py -q
```

Expected: Ruff reports `All checks passed!`; pytest reports zero failures.

- [ ] **Step 4: Restart AlphaFoundry and verify health**

Run:

```bash
bash scripts/desktop/restart_app.sh
HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= https_proxy= http_proxy= all_proxy= curl --silent --show-error --fail --max-time 3 http://127.0.0.1:8765/health
```

Expected: the restart script reports AlphaFoundry healthy and `/health` returns `{"status":"ok", ...}`.
