# Oil Paragraph Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate the weekly crude-oil paragraph as a concise causal market commentary while keeping shared Prompt constraints domain-neutral.

**Architecture:** Keep global `defaults.generation_constraints` unchanged. Put oil-specific narrative rules and evidence selection entirely under the `原油` placeholder and its matching Prompt block, then lock the boundary with a deterministic configuration test.

**Tech Stack:** YAML report configuration, Markdown Prompt templates, Python/pytest, PyYAML.

---

### Task 1: Lock the shared/local configuration boundary

**Files:**
- Create: `tests/unit/test_oil_report_prompt_config.py`
- Read: `report_projects/华安ETF周报/config/section_config.yaml`
- Read: `report_projects/华安ETF周报/config/prompt_templates.md`

- [ ] **Step 1: Write the failing configuration contract test**

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SECTION_CONFIG = ROOT / "report_projects" / "华安ETF周报" / "config" / "section_config.yaml"
PROMPT_TEMPLATES = ROOT / "report_projects" / "华安ETF周报" / "config" / "prompt_templates.md"


def test_oil_prompt_is_causal_and_does_not_pollute_shared_constraints():
    config = yaml.safe_load(SECTION_CONFIG.read_text(encoding="utf-8"))
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    common_constraints = "\n".join(config["defaults"]["generation_constraints"])
    oil = config["placeholders"]["原油"]
    oil_structure = "\n".join(oil["writing_structure"])
    oil_prompt = prompt_source.split("## 原油\n", 1)[1].split("\n## ", 1)[0]

    for oil_only_term in ["OPEC+", "原油库存", "霍尔木兹", "布伦特", "WTI"]:
        assert oil_only_term not in common_constraints

    assert "交易主线" in oil_structure
    assert "支撑因素" in oil_structure
    assert "压制因素" in oil_structure
    assert "不强行覆盖" in oil_structure
    assert "3—5" in oil_structure
    assert "具体事实、数字和事件必须来自 Evidence" in oil_structure
    assert "不得输出来源括号" in oil_structure
    assert "直接解释本周国际油价变动" in oil_prompt

    retrieval = oil["retrieval"]
    assert retrieval["top_k"] == 6
    assert "EIA原油库存" in retrieval["keywords"]
    assert "OPEC+" in retrieval["keywords"]
    assert "2040年" in retrieval["exclude"]
    assert "航空煤油" in retrieval["exclude"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest -q tests/unit/test_oil_report_prompt_config.py`

Expected: FAIL because the current oil structure is checklist-based and has no explicit relevance exclusions.

### Task 2: Replace the oil-only structure and retrieval configuration

**Files:**
- Modify: `report_projects/华安ETF周报/config/section_config.yaml:553-573`
- Test: `tests/unit/test_oil_report_prompt_config.py`

- [ ] **Step 1: Replace only the `原油` placeholder configuration**

Keep `defaults.generation_constraints` byte-for-byte unchanged. Set the oil-local retrieval and writing structure to:

```yaml
  原油:
    title: 原油
    type: paragraph
    confirmed: true
    mode: evidence_ai
    prompt_template: 原油
    query_mode: retrieval_query_embedded
    target_words: 300
    max_words: 300
    min_news_count: 3
    retrieval:
      keyword_profile: 石油
      top_k: 6
      keywords:
      - 原油
      - 国际油价
      - 布伦特原油
      - WTI原油
      - EIA原油库存
      - 美国原油库存
      - 成品油库存
      - OPEC+
      - 原油产量
      - 减产
      - 增产
      - 炼厂开工率
      - 原油需求
      - 霍尔木兹海峡
      exclude:
      - 2040年
      - 航空煤油
      - 航油长期预测
      - 企业提价
      - 金银铜锡
      - 化工原料成本
      - 泛能源转型
    writing_structure:
    - 首句判断本周国际油价整体方向，并概括市场交易主线发生了什么变化
    - 围绕最重要的需求端材料，分别说明油价的主要支撑因素与压制因素；材料不足时允许使用审慎的定性连接，但不得补造具体事实或数字
    - 说明供给、库存或 OPEC+ 政策如何影响供需格局，只写本周有 Evidence 支撑的重点，不强行覆盖每个维度
    - 说明地缘政治风险及风险溢价是上升、回落还是保持稳定；没有直接材料时省略具体事件
    - 最后综合供需、宏观与地缘因素形成审慎判断，并列出后续观察变量，不预测具体价格点位
    - 全段只选择 3—5 条与本周国际油价直接相关的高质量材料；具体事实、数字和事件必须来自 Evidence
    - 保持一个自然段，不得输出来源括号、引用编号、Evidence 编号、标题、列表或解释过程
    params:
      param: 原油
```

- [ ] **Step 2: Run the configuration test**

Run: `pytest -q tests/unit/test_oil_report_prompt_config.py`

Expected: FAIL only on the old Markdown Prompt block.

### Task 3: Replace the oil-only Prompt template and verify

**Files:**
- Modify: `report_projects/华安ETF周报/config/prompt_templates.md:46-52`
- Test: `tests/unit/test_oil_report_prompt_config.py`
- Test: `tests/unit/test_report_projects_api.py`

- [ ] **Step 1: Replace only the `## 原油` Prompt block**

````text
## 原油

```text
检索 Query：查找报告期内能够直接解释本周国际油价变动的材料。优先选择布伦特和 WTI 周度走势、美国原油及成品油库存、炼厂开工与季节性需求、OPEC+ 产量政策、主要产油国供应变化、美元与全球增长预期，以及会改变原油风险溢价的地缘事件。排除长期航油需求预测、企业产品涨价和与本周油价缺乏直接关系的泛能源新闻。

写作要求：写成一段约300字的周度因果分析，不写成新闻清单。先判断本周油价方向与交易主线，再说明需求端的支撑与压制因素，随后分析供给、库存或 OPEC+ 政策以及地缘风险溢价变化，最后形成审慎综合判断并列出后续观察变量。只选择3—5条最相关材料，不强行覆盖缺少 Evidence 的维度。具体事实、数字和事件必须来自 Evidence；材料不足时可以使用定性连接和审慎判断，但不得补造事实、数字、政策或价格点位。不得输出来源括号、引用编号、Evidence 编号、标题、列表或解释过程。
```
````

- [ ] **Step 2: Run focused tests**

Run: `pytest -q tests/unit/test_oil_report_prompt_config.py tests/unit/test_report_projects_api.py`

Expected: PASS.

- [ ] **Step 3: Validate configuration syntax and unchanged shared constraints**

Run:

```bash
python -c "from pathlib import Path; import yaml; p=Path('report_projects/华安ETF周报/config/section_config.yaml'); yaml.safe_load(p.read_text(encoding='utf-8')); print('yaml ok')"
git diff -- report_projects/华安ETF周报/config/section_config.yaml report_projects/华安ETF周报/config/prompt_templates.md
```

Expected: `yaml ok`; diff contains oil-local changes only and no edit under `defaults.generation_constraints`.

- [ ] **Step 4: Run lint and full focused regression suite**

Run:

```bash
ruff check tests/unit/test_oil_report_prompt_config.py
pytest -q tests/unit/test_report_generation_jobs.py tests/unit/test_report_projects_api.py tests/unit/test_report_template_workbench_frontend.py tests/unit/test_openai_compatible_provider.py tests/unit/test_oil_report_prompt_config.py
```

Expected: all checks and tests pass.
