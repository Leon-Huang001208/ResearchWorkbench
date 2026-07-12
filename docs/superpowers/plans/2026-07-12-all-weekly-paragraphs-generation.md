# All Weekly Paragraphs Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every Huaan ETF weekly-report paragraph its own topic anchor, driver vocabulary, causal writing structure, and Prompt while preserving deterministic fields and Excel market reviews.

**Architecture:** Keep the shared generation constraints limited to factual grounding and output safety. Configure each paragraph in `section_config.yaml`; keep each retrieval query and writing instruction in its matching `prompt_templates.md` block; reuse the existing generic subject-anchor, focused-excerpt, hybrid retrieval, and reranking implementation.

**Tech Stack:** Python, pytest, YAML, Markdown Prompt templates, existing `ReportProjectGenerationService`.

---

## File responsibilities

- `report_projects/华安ETF周报/config/section_config.yaml`: paragraph type, length, subject anchors, ranking drivers, exclusions, and writing order.
- `report_projects/华安ETF周报/config/prompt_templates.md`: one independent retrieval query and writing instruction for each AI paragraph.
- `tests/unit/test_all_weekly_prompt_configs.py`: complete contract for all 19 AI paragraph configurations and the four deterministic placeholders.
- `tests/unit/test_report_projects_api.py`: existing generation, cleaning, deterministic review, and retrieval regression coverage.
- `tests/unit/test_gold_report_prompt_config.py`: existing subject-anchor and focused-excerpt behavior.
- `tests/unit/test_oil_report_prompt_config.py`: existing oil-specific configuration boundary.

### Task 1: Add the full configuration contract

**Files:**
- Create: `tests/unit/test_all_weekly_prompt_configs.py`
- Read: `report_projects/华安ETF周报/config/section_config.yaml`
- Read: `report_projects/华安ETF周报/config/prompt_templates.md`

- [ ] **Step 1: Write the failing full-contract test**

Create the following test. The first dictionary is the exact topic and driver contract for every paragraph not already covered by the gold and oil tests.

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SECTION_CONFIG = ROOT / "report_projects" / "华安ETF周报" / "config" / "section_config.yaml"
PROMPT_TEMPLATES = ROOT / "report_projects" / "华安ETF周报" / "config" / "prompt_templates.md"

EXPECTED = {
    "中国宏观": {
        "subjects": ["中国经济", "国内宏观", "中国宏观"],
        "drivers": ["PMI", "CPI", "PPI", "社会融资", "货币政策", "财政政策", "房地产"],
        "markers": ["宏观环境", "核心驱动", "传导", "后续"],
    },
    "人工智能": {
        "subjects": ["人工智能", "生成式AI", "大模型", "AI算力"],
        "drivers": ["资本开支", "AI芯片", "数据中心", "模型", "应用", "监管"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "电子": {
        "subjects": ["半导体", "消费电子", "电子元器件", "PCB", "存储芯片"],
        "drivers": ["库存", "价格", "终端需求", "先进制程", "国产替代", "资本开支"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "航天": {
        "subjects": ["商业航天", "卫星", "运载火箭", "航天器"],
        "drivers": ["发射", "订单", "产能", "技术验证", "政策", "卫星应用"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "电力设备新能源": {
        "subjects": ["光伏", "风电", "储能", "电网", "锂电池", "新能源车"],
        "drivers": ["装机", "招标", "产能", "价格", "出口", "技术迭代", "电网投资"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "消费": {
        "subjects": ["社会消费", "零售", "食品饮料", "家电", "旅游消费"],
        "drivers": ["居民收入", "消费信心", "销量", "价格", "渠道库存", "促消费政策"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "金融地产": {
        "subjects": ["银行", "保险", "券商", "房地产", "房企"],
        "drivers": ["利率", "息差", "信贷", "成交", "销售", "融资", "房地产政策"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "医药生物": {
        "subjects": ["创新药", "医疗器械", "生物科技", "CXO", "医疗服务"],
        "drivers": ["临床", "审批", "医保", "授权交易", "需求", "研发", "商业化"],
        "markers": ["产业主线", "核心变化", "产业链", "后续"],
    },
    "海外市场": {
        "subjects": ["美股", "欧洲股市", "日本股市", "全球股市", "海外市场"],
        "drivers": ["美联储", "欧洲央行", "日本央行", "美债收益率", "美元指数", "风险偏好"],
        "markers": ["方向和节奏", "核心驱动", "传导", "市场分化", "后续"],
    },
    "港股科技": {
        "subjects": ["恒生科技", "港股科技", "港股互联网", "港股半导体"],
        "drivers": ["南向资金", "海外流动性", "平台经济", "业绩", "估值", "风险偏好"],
        "markers": ["方向和节奏", "核心驱动", "传导", "板块分化", "后续"],
    },
    "港股央企红利": {
        "subjects": ["港股央企红利", "港股高股息", "央企红利", "恒生央企"],
        "drivers": ["南向资金", "股息率", "利率", "银行", "能源", "通信", "公用事业"],
        "markers": ["方向和节奏", "核心驱动", "传导", "板块分化", "后续"],
    },
    "美国": {
        "subjects": ["美国经济", "美国宏观", "美联储", "美国通胀", "美国就业"],
        "drivers": ["非农", "CPI", "消费", "GDP", "美元指数", "美债收益率", "财政政策"],
        "markers": ["宏观环境", "核心驱动", "传导", "后续"],
    },
    "欧洲": {
        "subjects": ["欧元区", "欧洲经济", "欧洲央行", "德国经济", "法国经济"],
        "drivers": ["通胀", "经济增长", "利率", "欧元", "财政政策", "能源风险"],
        "markers": ["宏观环境", "核心驱动", "传导", "后续"],
    },
    "日本": {
        "subjects": ["日本经济", "日本央行", "日本通胀", "日元", "日本国债"],
        "drivers": ["工资", "通胀", "利率", "日元汇率", "国债收益率", "财政政策"],
        "markers": ["宏观环境", "核心驱动", "传导", "后续"],
    },
    "美国新闻": {
        "subjects": ["美国", "美联储", "美股", "美元", "美债"],
        "drivers": ["政策", "经济数据", "市场", "关税", "地缘政治"],
        "markers": ["一至两件", "直接影响"],
    },
    "欧洲新闻": {
        "subjects": ["欧洲", "欧元区", "欧洲央行", "欧元", "欧债"],
        "drivers": ["政策", "经济数据", "市场", "财政", "地缘政治"],
        "markers": ["一至两件", "直接影响"],
    },
}


def prompt_block(source: str, name: str) -> str:
    return source.split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]


def test_every_ai_paragraph_has_unique_retrieval_structure_and_prompt():
    config = yaml.safe_load(SECTION_CONFIG.read_text(encoding="utf-8"))
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    common = "\n".join(config["defaults"]["generation_constraints"])

    assert config["defaults"]["retrieval"]["top_k"] == 10
    for name, expected in EXPECTED.items():
        paragraph = config["placeholders"][name]
        retrieval = paragraph["retrieval"]
        structure = "\n".join(paragraph["writing_structure"])
        block = prompt_block(prompt_source, name)

        assert set(expected["subjects"]).issubset(retrieval["subject_keywords"]), name
        assert set(expected["drivers"]).issubset(retrieval["keywords"]), name
        assert "top_k" not in retrieval, name
        for marker in expected["markers"]:
            assert marker in structure, (name, marker)
        assert "不得逐项罗列" in block or "不罗列" in block, name
        assert "Evidence" in block, name

    for section_only_term in ["AI芯片", "卫星应用", "息差", "日元汇率", "南向资金"]:
        assert section_only_term not in common

    a_share = config["placeholders"]["A股市场回顾"]
    llm_component = next(
        component for component in a_share["components"] if component["type"] == "llm_writing"
    )
    assert set(["A股", "沪深股市", "中国股市"]).issubset(
        llm_component["retrieval"]["subject_keywords"]
    )
    assert set(["板块轮动", "市场热点", "资金", "政策", "景气度", "风险偏好"]).issubset(
        llm_component["retrieval"]["keywords"]
    )
    assert "不重复前文指数和成交额数字" in prompt_block(prompt_source, "A股市场回顾")


def test_deterministic_and_composite_placeholders_keep_their_generation_modes():
    config = yaml.safe_load(SECTION_CONFIG.read_text(encoding="utf-8"))
    placeholders = config["placeholders"]

    assert placeholders["开始日期"]["type"] == "field"
    assert placeholders["结束日期"]["type"] == "field"
    assert placeholders["黄金市场回顾"]["type"] == "excel_commodity_market_review"
    assert placeholders["原油市场回顾"]["type"] == "excel_commodity_market_review"
    assert placeholders["A股市场回顾"]["mode"] == "data_template_plus_evidence_ai"
```

- [ ] **Step 2: Run the contract and verify the current configuration fails**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py -q
```

Expected: FAIL on missing `subject_keywords`, missing dedicated driver lists, and generic writing structures.

### Task 2: Configure macro, regional, and market paragraphs

**Files:**
- Modify: `report_projects/华安ETF周报/config/section_config.yaml`
- Test: `tests/unit/test_all_weekly_prompt_configs.py`

- [ ] **Step 1: Configure macro and regional retrieval blocks**

For `中国宏观`, `美国`, `欧洲`, and `日本`, set `subject_keywords` and `keywords` to the exact `subjects` and `drivers` values in `EXPECTED`. Use this exact writing structure for each, substituting only the geographic label in the first line:

```yaml
writing_structure:
- 首句判断本周目标经济体宏观环境或政策取向的主要变化
- 选择证据最充分且解释力最强的数据、政策决定或官员表态作为核心驱动
- 说明核心驱动如何传导至增长、通胀、利率、汇率或风险偏好，只写 Evidence 支撑的链条
- 根据材料补充财政、产业或外部风险等次要因素；材料不足时不强行覆盖
- 末句总结当前阶段，并列出后续最值得关注的二至四项变量
```

In the actual YAML replace `目标经济体` with `中国`, `美国`, `欧洲`, or `日本` respectively.

- [ ] **Step 2: Configure the A-share Evidence component**

Inside the `A股市场回顾` component whose type is `llm_writing`, set:

```yaml
retrieval:
  keyword_profile: A股市场回顾
  subject_keywords:
  - A股
  - 沪深股市
  - 中国股市
  keywords:
  - 板块轮动
  - 市场热点
  - 资金
  - 政策
  - 景气度
  - 风险偏好
writing_structure:
- 接在固定开头之后，概括本周最重要的市场热点和板块轮动，不得写成新闻清单
- 选择一个有充分 Evidence 支撑的政策、产业、资金或景气变化作为核心驱动
- 说明核心驱动如何影响风险偏好和板块表现，不重复前文指数和成交额数字
- 末句给出审慎趋势判断和后续观察变量，不构成投资建议
```

- [ ] **Step 3: Configure overseas and Hong Kong market blocks**

For `海外市场`, `港股科技`, and `港股央企红利`, set the exact `subjects` and `drivers` values from `EXPECTED`, then use:

```yaml
writing_structure:
- 首句概括本周目标市场的整体方向和节奏
- 选择宏观、政策、资金或业绩中证据最充分的因素作为核心驱动
- 说明核心驱动如何传导至估值、流动性、风险偏好和市场表现
- 概括内部市场分化或板块分化，只写 Evidence 支撑的方向，不得逐项罗列
- 末句总结行情性质，并列出后续最值得关注的二至四项变量
```

Replace `目标市场` with `海外市场`, `港股科技板块`, or `港股央企红利板块`.

- [ ] **Step 4: Run the contract to observe that remaining industry/news sections still fail**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py -q
```

Expected: FAIL first on an unconfigured industry or news paragraph, not on the macro/market sections changed in this task.

### Task 3: Configure all industry paragraphs

**Files:**
- Modify: `report_projects/华安ETF周报/config/section_config.yaml`
- Test: `tests/unit/test_all_weekly_prompt_configs.py`

- [ ] **Step 1: Add exact industry anchors and drivers**

For `人工智能`, `电子`, `航天`, `电力设备新能源`, `消费`, `金融地产`, and `医药生物`, copy the exact `subjects` and `drivers` arrays from `EXPECTED` into `retrieval.subject_keywords` and `retrieval.keywords`.

- [ ] **Step 2: Replace every industry writing structure**

Use this exact structure in all seven industry blocks:

```yaml
writing_structure:
- 首句提炼本周最重要的产业主线，不得写成新闻清单
- 选择供给、需求、政策、技术、价格或资本开支中证据最充分的核心变化
- 说明核心变化如何影响产业链环节、订单、成本、渗透率或景气度，形成清晰产业链传导
- 根据 Evidence 补充一至两个次要变化，不机械罗列公司新闻，材料不足时不强行覆盖
- 末句总结行业所处阶段，并列出后续最需要验证的二至四项变量
```

- [ ] **Step 3: Run the contract to verify only news Prompt/config work remains**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py -q
```

Expected: FAIL on `美国新闻` or `欧洲新闻`, or on Prompt blocks not yet rewritten.

### Task 4: Configure news briefs and rewrite all independent Prompts

**Files:**
- Modify: `report_projects/华安ETF周报/config/section_config.yaml`
- Modify: `report_projects/华安ETF周报/config/prompt_templates.md`
- Test: `tests/unit/test_all_weekly_prompt_configs.py`

- [ ] **Step 1: Configure the two news briefs**

Copy the `subjects` and `drivers` arrays for `美国新闻` and `欧洲新闻` from `EXPECTED`. Add this structure to both:

```yaml
writing_structure:
- 从本周 Evidence 中选择重要性最高的一至两件事，不罗列低重要性新闻
- 每件事只写关键事实，以及对经济、政策、权益、债券、汇率或风险偏好的直接影响
- 保持约100字，不扩展完整宏观分析，不写后续预测
```

- [ ] **Step 2: Rewrite every non-commodity Prompt block with exact category wording**

Use the following exact writing instructions. Preserve each block name and write an independent retrieval query containing every section's `subjects` and `drivers` from `EXPECTED`.

Macro and regional blocks (`中国宏观`, `美国`, `欧洲`, `日本`):

```text
写作要求：写成一个可直接放入周报的自然段。先判断本周宏观环境或政策取向，再选择解释力最强的数据、政策决定或官员表态作为核心驱动，说明其如何传导至增长、通胀、利率、汇率或风险偏好；其他因素只在 Evidence 充分时补充，不得逐项罗列候选维度。结尾总结当前阶段并列出后续关注变量。具体事实、数字和事件必须来自 Evidence，不得输出来源括号、Evidence 编号、标题、列表、分析过程或投资建议。
```

Industry blocks (`人工智能`, `电子`, `航天`, `电力设备新能源`, `消费`, `金融地产`, `医药生物`):

```text
写作要求：写成一个可直接放入周报的行业分析自然段。先提炼本周最重要的产业主线，再选择供给、需求、政策、技术、价格或资本开支中解释力最强的核心变化，说明其对产业链、订单、成本、渗透率或景气度的传导；其他因素只在 Evidence 充分时补充，不得逐项罗列候选维度或机械拼接公司新闻。结尾判断行业所处阶段并列出后续验证变量。具体事实、数字和事件必须来自 Evidence，不得输出来源括号、Evidence 编号、标题、列表、分析过程或投资建议。
```

Market blocks (`海外市场`, `港股科技`, `港股央企红利`):

```text
写作要求：写成一个可直接放入周报的市场分析自然段。先概括本周市场方向与节奏，再选择宏观、政策、资金或业绩中解释力最强的核心驱动，说明其如何传导至估值、流动性、风险偏好和市场表现；内部市场或板块分化只写 Evidence 支撑的重点，不得逐项罗列候选维度。结尾总结行情性质并列出后续关注变量。具体事实、数字和事件必须来自 Evidence，不得输出来源括号、Evidence 编号、标题、列表、分析过程或投资建议。
```

News blocks (`美国新闻`, `欧洲新闻`):

```text
写作要求：写成约100字的单段新闻快讯。从本周 Evidence 中只选择重要性最高的一至两件事，写清关键事实及其对经济、政策、权益、债券、汇率或风险偏好的直接影响；不罗列低重要性新闻，不扩展完整宏观分析，不写后续预测。具体事实和事件必须来自 Evidence，不得输出来源括号、Evidence 编号、标题、列表、分析过程或投资建议。
```

For `A股市场回顾`, replace the current recommendation wording with:

```text
写作要求：接在 Excel 固定市场表现之后写成一个自然段。概括本周最重要的市场热点与板块轮动，选择一个有充分 Evidence 支撑的政策、产业或景气变化解释风险偏好，不重复前文指数和成交额数字，不得逐项罗列候选热点。具体事实必须来自 Evidence，不得输出来源括号、Evidence 编号、标题、列表、分析过程或投资建议。
```

- [ ] **Step 3: Run all configuration tests**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py tests/unit/test_gold_report_prompt_config.py tests/unit/test_oil_report_prompt_config.py -q
```

Expected: PASS with zero failures.

### Task 5: Verify generation logic and representative real outputs

**Files:**
- Test: `tests/unit/test_report_projects_api.py`
- Verify: `report_projects/华安ETF周报/config/section_config.yaml`
- Verify: `report_projects/华安ETF周报/config/prompt_templates.md`
- Verify: `logs/`

- [ ] **Step 1: Run static and regression verification**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m ruff check reporting/projects/generation.py tests/unit/test_all_weekly_prompt_configs.py tests/unit/test_gold_report_prompt_config.py tests/unit/test_oil_report_prompt_config.py
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_all_weekly_prompt_configs.py tests/unit/test_gold_report_prompt_config.py tests/unit/test_oil_report_prompt_config.py tests/unit/test_report_projects_api.py -q
```

Expected: Ruff reports `All checks passed!`; pytest reports zero failures.

- [ ] **Step 2: Generate representative paragraphs from the real evidence store**

Load the real project and generate only these placeholders in one run:

```python
sample_names = [
    "中国宏观",
    "美国",
    "人工智能",
    "电子",
    "医药生物",
    "海外市场",
    "港股科技",
    "美国新闻",
    "黄金",
    "原油",
]
```

Use report date `2026-07-12`, lookback `7`, and the real `ReportProjectGenerationService`. Print each paragraph, Evidence count, and Evidence titles.

Expected for every paragraph: one natural paragraph; no Evidence identifier, source parenthesis, heading, list, analysis process, or investment advice. Analysis sections should have a clear main driver and transmission chain; the news brief should remain concise.

- [ ] **Step 3: Restart AlphaFoundry and verify health**

Run:

```bash
bash scripts/desktop/restart_app.sh
HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= https_proxy= http_proxy= all_proxy= curl --silent --show-error --fail --max-time 3 http://127.0.0.1:8765/health
```

Expected: AlphaFoundry reports healthy and `/health` returns `{"status":"ok", ...}`.

- [ ] **Step 4: Preserve the dirty shared workspace safely**

Do not commit `section_config.yaml`, `prompt_templates.md`, or `generation.py` automatically because they contain the user's earlier uncommitted oil, gold, reranker, and auto-refresh work. Report the verified files and leave all unrelated changes untouched.
