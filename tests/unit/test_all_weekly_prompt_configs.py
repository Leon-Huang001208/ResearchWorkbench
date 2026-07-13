import re
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SECTION_CONFIG = ROOT / "report_projects" / "华安ETF周报" / "config" / "section_config.yaml"
PROMPT_TEMPLATES = ROOT / "report_projects" / "华安ETF周报" / "config" / "prompt_templates.md"


PARAGRAPH_CONTRACTS = [
    pytest.param(
        "中国宏观",
        [
            "中国经济",
            "国内宏观",
            "中国宏观",
            "中国人民银行",
            "国家统计局",
            "中国PMI",
            "中国社融",
        ],
        ["PMI", "CPI", "PPI", "社会融资", "货币政策", "财政政策", "房地产"],
        ["宏观环境", "核心驱动", "传导", "后续"],
        id="china-macro",
    ),
    pytest.param(
        "人工智能",
        ["人工智能", "生成式AI", "大模型", "AI算力"],
        ["资本开支", "AI芯片", "数据中心", "模型", "应用", "监管"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="artificial-intelligence",
    ),
    pytest.param(
        "电子",
        ["半导体", "消费电子", "电子元器件", "PCB", "存储芯片"],
        ["库存", "价格", "终端需求", "先进制程", "国产替代", "资本开支"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="electronics",
    ),
    pytest.param(
        "航天",
        ["商业航天", "卫星", "运载火箭", "航天器"],
        ["发射", "订单", "产能", "技术验证", "政策", "卫星应用"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="aerospace",
    ),
    pytest.param(
        "电力设备新能源",
        ["光伏", "风电", "储能", "电网", "锂电池", "新能源车"],
        ["装机", "招标", "产能", "价格", "出口", "技术迭代", "电网投资"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="power-equipment-new-energy",
    ),
    pytest.param(
        "消费",
        ["社会消费", "零售", "食品饮料", "家电", "旅游消费"],
        ["居民收入", "消费信心", "销量", "价格", "渠道库存", "促消费政策"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="consumer",
    ),
    pytest.param(
        "金融地产",
        ["银行", "保险", "券商", "房地产", "房企"],
        ["利率", "息差", "信贷", "成交", "销售", "融资", "房地产政策"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="finance-real-estate",
    ),
    pytest.param(
        "医药生物",
        ["创新药", "医疗器械", "生物科技", "CXO", "医疗服务"],
        ["临床", "审批", "医保", "授权交易", "需求", "研发", "商业化"],
        ["产业主线", "核心变化", "产业链", "后续"],
        id="healthcare-biotech",
    ),
    pytest.param(
        "海外市场",
        ["美股", "欧洲股市", "日本股市", "全球股市", "海外市场"],
        ["美联储", "欧洲央行", "日本央行", "美债收益率", "美元指数", "风险偏好"],
        ["方向和节奏", "核心驱动", "传导", "区域市场分化", "后续"],
        id="overseas-markets",
    ),
    pytest.param(
        "港股科技",
        ["恒生科技", "港股科技", "港股互联网", "港股半导体"],
        ["南向资金", "海外流动性", "平台经济", "业绩", "估值", "风险偏好"],
        ["方向和节奏", "核心驱动", "传导", "成分行业之间的分化", "后续"],
        id="hong-kong-tech",
    ),
    pytest.param(
        "港股央企红利",
        ["港股央企红利", "港股高股息", "央企红利", "恒生央企"],
        ["南向资金", "股息率", "利率", "银行", "能源", "通信", "公用事业"],
        ["方向和节奏", "核心驱动", "传导", "成分行业之间的分化", "后续"],
        id="hong-kong-central-soe-dividend",
    ),
    pytest.param(
        "美国",
        ["美国经济", "美国宏观", "美国通胀", "美国就业", "美国消费", "美国GDP"],
        ["非农", "CPI", "消费", "GDP", "美元指数", "美债收益率", "财政政策"],
        ["宏观环境", "核心驱动", "传导", "后续"],
        id="united-states",
    ),
    pytest.param(
        "欧洲",
        ["欧元区", "欧洲经济", "欧洲央行", "德国经济", "法国经济"],
        ["通胀", "经济增长", "利率", "欧元", "财政政策", "能源风险"],
        ["宏观环境", "核心驱动", "传导", "后续"],
        id="europe",
    ),
    pytest.param(
        "日本",
        ["日本经济", "日本央行", "日本通胀", "日本工资", "日本国债"],
        ["工资", "通胀", "利率", "日元汇率", "国债收益率", "财政政策"],
        ["宏观环境", "核心驱动", "传导", "后续"],
        id="japan",
    ),
    pytest.param(
        "美国新闻",
        ["美国", "美联储", "美股", "美元", "美债"],
        ["政策", "经济数据", "市场", "关税", "地缘政治"],
        ["一至两件", "直接影响"],
        id="united-states-news",
    ),
    pytest.param(
        "欧洲新闻",
        ["欧洲", "欧元区", "欧洲央行", "欧元", "欧债"],
        ["政策", "经济数据", "市场", "财政", "地缘政治"],
        ["一至两件", "直接影响"],
        id="europe-news",
    ),
]

SECTION_ONLY_TERMS = {
    "中国宏观": {
        "中国经济",
        "国内宏观",
        "中国宏观",
        "中国人民银行",
        "国家统计局",
        "中国PMI",
        "中国社融",
        "社会融资",
    },
    "人工智能": {"生成式AI", "AI算力", "AI芯片", "数据中心"},
    "电子": {
        "半导体",
        "消费电子",
        "电子元器件",
        "PCB",
        "存储芯片",
        "先进制程",
        "国产替代",
    },
    "航天": {"商业航天", "卫星", "运载火箭", "航天器", "技术验证", "卫星应用"},
    "电力设备新能源": {
        "光伏",
        "风电",
        "储能",
        "电网",
        "锂电池",
        "新能源车",
        "装机",
        "招标",
        "电网投资",
    },
    "消费": {
        "社会消费",
        "食品饮料",
        "旅游消费",
        "居民收入",
        "消费信心",
        "渠道库存",
        "促消费政策",
    },
    "金融地产": {"息差", "信贷", "房地产政策"},
    "医药生物": {
        "创新药",
        "医疗器械",
        "生物科技",
        "CXO",
        "医疗服务",
        "临床",
        "医保",
        "授权交易",
        "商业化",
    },
    "海外市场": {"欧洲股市", "日本股市", "全球股市", "海外市场", "美债收益率", "美元指数"},
    "港股科技": {
        "恒生科技",
        "港股科技",
        "港股互联网",
        "港股半导体",
        "南向资金",
        "海外流动性",
        "平台经济",
    },
    "港股央企红利": {
        "港股央企红利",
        "港股高股息",
        "央企红利",
        "恒生央企",
        "股息率",
        "公用事业",
    },
    "美国": {
        "美国经济",
        "美国宏观",
        "美国通胀",
        "美国就业",
        "美国消费",
        "美国GDP",
        "非农",
    },
    "欧洲": {"欧元区", "欧洲经济", "德国经济", "法国经济", "能源风险"},
    "日本": {"日本经济", "日本通胀", "日本工资", "日本国债", "日元汇率", "国债收益率"},
    "美国新闻": {"美股", "美债", "关税"},
    "欧洲新闻": {"欧债"},
}

INDUSTRY_STRUCTURE_CONTRACTS = {
    "人工智能": [
        "首句概括本周人工智能产业主线，聚焦证据最充分的一至两个方向",
        "提炼资本开支、AI芯片、数据中心、模型或应用中的核心变化，不逐项罗列新闻",
        "说明算力基础设施、模型能力与应用落地如何沿产业链传导",
        "末句判断景气变化并列出后续关注变量，不作投资建议",
    ],
    "电子": [
        "首句概括本周电子行业产业主线，聚焦证据最充分的一至两个方向",
        "提炼库存、价格、终端需求、先进制程或国产替代中的核心变化，不逐项罗列新闻",
        "说明终端需求如何经库存与价格传导至半导体、PCB和电子元器件产业链",
        "末句判断景气变化并列出后续关注变量，不作投资建议",
    ],
    "航天": [
        "首句概括本周航天产业主线，聚焦证据最充分的一至两个方向",
        "提炼发射、订单、产能、技术验证或政策中的核心变化，不逐项罗列新闻",
        "说明发射进度与订单如何向运载火箭、卫星和航天器制造产业链传导",
        "末句判断产业化进展并列出后续关注变量，不作投资建议",
    ],
    "电力设备新能源": [
        "首句概括本周电力设备新能源产业主线，聚焦证据最充分的一至两个方向",
        "提炼装机、招标、产能、价格、出口或技术迭代中的核心变化，不逐项罗列新闻",
        "说明装机与招标如何向设备需求、产能利用率、产业链价格和出口传导",
        "末句判断景气变化并列出后续关注变量，不作投资建议",
    ],
    "消费": [
        "首句概括本周消费产业主线，聚焦证据最充分的一至两个方向",
        "结合客流、同店、渠道库存或销量提炼需求与经营层面的核心变化，不逐项罗列新闻",
        "说明居民收入、消费信心或促消费政策如何向终端销量和消费产业链传导",
        "末句判断景气变化并列出后续关注变量，不作投资建议",
    ],
    "金融地产": [
        "首句概括本周金融地产产业主线，聚焦证据最充分的一至两个方向",
        "结合利率、息差、信用、房地产成交或融资提炼核心变化，不逐项罗列新闻",
        "说明政策与资金条件如何向银行信贷、房企销售和金融地产产业链传导",
        "末句判断风险与景气变化并列出后续关注变量，不作投资建议",
    ],
    "医药生物": [
        "首句概括本周医药生物产业主线，聚焦证据最充分的一至两个方向",
        "结合临床、审批、医保、授权交易或研发提炼核心变化，不逐项罗列新闻",
        "说明临床与审批进展如何经医保准入向产品商业化和医药产业链传导",
        "末句判断研发与商业化景气并列出后续关注变量，不作投资建议",
    ],
}

NEWS_STRUCTURE_CONTRACTS = {
    "美国新闻": [
        "优先写一件重大事件，仅在两件都重大时各写一句，不得为凑数罗列一至两件新闻",
        "只写最相关的一类资产影响，说明事件对权益、债券或汇率中一类资产的直接影响",
    ],
    "欧洲新闻": [
        "优先写一件重大事件，仅在两件都重大时各写一句，不得为凑数罗列一至两件新闻",
        "只写最相关的一类资产影响，说明事件对权益、债券或汇率中一类资产的直接影响",
    ],
}

FINANCE_FALLBACK_REQUIRED_KEYWORDS = [
    "中国",
    "国内",
    "A股",
    "港股",
    "沪深",
    "上交所",
    "深交所",
]

NEWS_SYNTHETIC_TITLE_LABELS = {
    "美国新闻": ["美国新闻"],
    "欧洲新闻": ["欧洲新闻"],
}

REAL_NEWS_QUERIES = {
    "美国新闻": "影响美元、美债、美股的新闻。",
    "欧洲新闻": "影响欧元、欧债、德国权益、法国权益的新闻。",
}

EXCLUDE_TITLE_KEYWORDS = ["下周", "即将", "将于", "明日"]
NEWS_FIRST_GROUP_SCOPE = "title_or_lead"
MEDICAL_FIRST_GROUP_SCOPE = "title"
HONG_KONG_TECH_BACKFILL_REQUIRED_KEYWORDS = ["港股", "香港", "恒生", "中概"]

SUBJECT_GROUP_CONTRACTS = {
    "人工智能": [
        ["人工智能", "生成式AI", "大模型", "AI算力"],
        ["资本开支", "AI芯片", "数据中心", "模型", "大模型", "应用", "监管", "算力", "算法"],
    ],
    "电子": [
        ["半导体", "消费电子", "电子元器件", "PCB", "存储芯片"],
        ["库存", "价格", "终端需求", "先进制程", "国产替代", "资本开支", "产能", "订单", "销量"],
    ],
    "航天": [
        ["商业航天", "卫星", "运载火箭", "航天器"],
        ["发射", "订单", "产能", "技术验证", "政策", "卫星应用"],
    ],
    "电力设备新能源": [
        ["光伏", "风电", "储能", "电网", "锂电池", "新能源车"],
        ["装机", "招标", "产能", "价格", "出口", "技术迭代", "电网投资", "销量", "订单", "以旧换新"],
    ],
    "消费": [
        ["社会消费", "零售", "食品饮料", "家电", "旅游消费"],
        ["居民", "消费", "以旧换新", "客流", "同店", "渠道", "库存", "销量", "价格", "收入", "促消费"],
    ],
    "金融地产": [
        ["银行", "保险", "券商", "房地产", "房企"],
        FINANCE_FALLBACK_REQUIRED_KEYWORDS,
        ["利率", "息差", "信贷", "成交", "销售", "融资", "房地产政策"],
    ],
    "医药生物": [
        [
            "创新药",
            "医疗器械",
            "生物科技",
            "CXO",
            "医疗服务",
            "医药",
            "新药",
            "药物",
            "制药",
            "生物医药",
        ],
        ["临床", "审批", "医保", "授权交易", "需求", "研发", "商业化"],
    ],
    "美国新闻": [
        ["美国", "美联储", "美股", "美元", "美债"],
        ["非农", "通胀", "CPI", "就业", "选举", "央行决议", "美联储决议", "企业业绩", "财报", "关税", "财政", "地缘政治"],
    ],
    "欧洲新闻": [
        ["欧洲", "欧元区", "欧洲央行", "欧元", "欧债"],
        ["通胀", "CPI", "就业", "选举", "央行决议", "欧洲央行决议", "企业业绩", "财报", "财政", "能源", "地缘政治"],
    ],
}

CROSS_SENTENCE_SUBJECT_CASES = {
    "人工智能": ("人工智能与大模型成为本周产业焦点。", "相关资本开支继续增长。"),
    "电子": ("存储芯片供需出现变化。", "产品价格成为市场关注重点。"),
    "航天": ("商业航天项目取得新进展。", "运载火箭发射计划正在推进。"),
    "电力设备新能源": ("新能源车市场延续活跃。", "终端销量出现新变化。"),
    "消费": ("居民家电需求受到关注。", "以旧换新带动渠道销量变化。"),
    "金融地产": ("银行板块经营情况受到关注。", "沪深市场讨论息差变化。"),
    "医药生物": ("创新药研发取得新进展。", "临床审批影响后续商业化。"),
    "美国新闻": ("美国资产进入重要观察窗口。", "非农与通胀数据影响预期。"),
    "欧洲新闻": ("欧洲市场进入重要观察窗口。", "通胀与央行决议影响预期。"),
}


class _RecordingLogger:
    def __init__(self):
        self.records = []

    def warning(self, event, **fields):
        self.records.append(("warning", event, fields))

    def info(self, event, **fields):
        self.records.append(("info", event, fields))


def _load_config():
    return yaml.safe_load(SECTION_CONFIG.read_text(encoding="utf-8"))


def _prompt_blocks(source):
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", source, flags=re.MULTILINE))
    blocks = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        blocks[match.group(1)] = source[match.end() : end].strip()
    return blocks


def _assert_exact_terms(actual, expected, *, context):
    actual_terms = set(actual)
    expected_terms = set(expected)
    assert actual_terms == expected_terms, (
        f"{context} 缺少 {sorted(expected_terms - actual_terms)}，"
        f"多出 {sorted(actual_terms - expected_terms)}"
    )


def test_expected_prompt_headings_are_unique_and_split_into_raw_blocks():
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    headings = re.findall(r"^##\s+(.+?)\s*$", prompt_source, flags=re.MULTILINE)
    parsed = _prompt_blocks(prompt_source)
    expected_names = [contract.values[0] for contract in PARAGRAPH_CONTRACTS]
    expected_names.append("A股市场回顾")

    for name in expected_names:
        assert headings.count(name) == 1, f"Prompt 二级标题 {name!r} 必须恰好出现一次"
        assert name in parsed, f"Prompt 切块函数未解析出 {name!r}"


def test_shared_retrieval_keeps_ten_reranked_candidates():
    config = _load_config()

    assert config["defaults"]["retrieval"]["top_k"] == 10


def test_shared_retrieval_excludes_future_schedule_terms_by_title_only():
    retrieval = _load_config()["defaults"]["retrieval"]

    assert retrieval.get("exclude_title_keywords") == EXCLUDE_TITLE_KEYWORDS


@pytest.mark.parametrize(
    "config, title, content",
    [
        (
            {"subject_keywords": ["中国经济"]},
            "下周中国PMI即将公布",
            "中国经济数据受到市场关注。",
        ),
        (
            {
                "subject_keywords": ["美国"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["美国"], ["非农"]],
            },
            "明日美国非农将于晚间公布",
            "美国非农数据受到市场关注。",
        ),
    ],
)
def test_future_schedule_titles_are_excluded_before_any_subject_match(config, title, content):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                **config,
                "exclude_title_keywords": EXCLUDE_TITLE_KEYWORDS,
            }
        },
        default_top_k=10,
    )
    assert getattr(retrieval_config, "exclude_title_keywords", None) == (
        EXCLUDE_TITLE_KEYWORDS
    )
    ranked = filter_and_rank_evidence(
        [EvidenceSnippet(source="test", title=title, content=content)],
        retrieval_config,
        query="测试",
    )

    assert ranked == []


def test_future_schedule_terms_in_content_do_not_trigger_title_exclusion():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["中国经济"],
                "exclude_title_keywords": EXCLUDE_TITLE_KEYWORDS,
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title="中国宏观政策回顾",
                content="中国经济本周已有变化，下周安排仅作为后续关注。",
            )
        ],
        retrieval_config,
        query="中国宏观",
    )

    assert [item.title for item in ranked] == ["中国宏观政策回顾"]


def test_report_period_defaults_are_dynamic_current_week_without_persisted_dates():
    report_period = _load_config()["defaults"]["report_period"]

    assert report_period.get("mode") == "current_week"
    assert report_period.get("lookback_days") == 7
    for fixed_date_key in ["report_date", "start_date", "end_date"]:
        assert fixed_date_key not in report_period


def test_scope_resolution_does_not_read_a_persisted_date_when_none_is_explicit(monkeypatch):
    import reporting.projects.generation as generation

    captured = {}

    def fake_compute(report_date, *, data_scope, lookback_days):
        captured.update(
            report_date=report_date,
            data_scope=data_scope,
            lookback_days=lookback_days,
        )
        return generation.ReportPeriod(start_date="2030-01-07", end_date="2030-01-13")

    monkeypatch.setattr(generation, "compute_report_period_for_scope", fake_compute)
    scope = generation.resolve_report_generation_scope(
        {
            "defaults": {
                "report_period": {"mode": "current_week", "lookback_days": 7}
            }
        }
    )

    assert captured == {
        "report_date": None,
        "data_scope": "current_week",
        "lookback_days": 7,
    }
    assert scope.report_period.start_date == "2030-01-07"
    assert scope.report_period.end_date == "2030-01-13"


def test_legacy_compaction_keeps_separate_driver_sentences_and_drops_unrelated_text():
    from reporting.projects.generation import (
        DatabaseEvidenceRetriever,
        build_retrieval_config,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["黄金", "金价"],
                "keywords": ["美债收益率", "美元指数"],
            }
        },
        default_top_k=10,
    )
    compacted = DatabaseEvidenceRetriever._compact_text(
        "黄金本周震荡上行。\n美债收益率回落，美元指数走弱。\n游戏新品进入发布周期。",
        retrieval_config=retrieval_config,
    )

    assert "黄金本周震荡上行。" in compacted
    assert "美债收益率回落，美元指数走弱。" in compacted
    assert "游戏新品进入发布周期。" not in compacted


@pytest.mark.parametrize("name, subjects, drivers, markers", PARAGRAPH_CONTRACTS)
def test_each_ai_paragraph_has_scoped_retrieval_structure_and_prompt(
    name,
    subjects,
    drivers,
    markers,
):
    config = _load_config()
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    parsed_prompts = _prompt_blocks(prompt_source)
    paragraph = config["placeholders"][name]
    retrieval = paragraph.get("retrieval", {})
    structure = "\n".join(paragraph.get("writing_structure", []))
    prompt = parsed_prompts[name]
    violations = []
    if paragraph.get("prompt_template") != name:
        violations.append(
            f"prompt_template 应为 {name!r}，实际为 {paragraph.get('prompt_template')!r}"
        )
    for key, expected in (("subject_keywords", subjects), ("keywords", drivers)):
        actual_terms = set(retrieval.get(key, []))
        expected_terms = set(expected)
        if actual_terms != expected_terms:
            violations.append(
                f"retrieval.{key} 缺少 {sorted(expected_terms - actual_terms)}，"
                f"多出 {sorted(actual_terms - expected_terms)}"
            )
    missing_markers = [marker for marker in markers if marker not in structure]
    if missing_markers:
        violations.append(f"writing_structure 缺少 {missing_markers}")
    if "top_k" in retrieval:
        violations.append("retrieval 不应覆盖共用 top_k")
    if "Evidence" not in prompt:
        violations.append("Prompt 缺少 Evidence")
    if "不得逐项罗列" not in prompt and "不罗列" not in prompt:
        violations.append("Prompt 缺少禁止逐项罗列约束")

    assert not violations, f"{name} 配置合同未满足: {'; '.join(violations)}"


@pytest.mark.parametrize("name, expected_structure", INDUSTRY_STRUCTURE_CONTRACTS.items())
def test_each_industry_has_its_own_exact_writing_structure(name, expected_structure):
    paragraph = _load_config()["placeholders"][name]

    assert paragraph.get("writing_structure") == expected_structure


@pytest.mark.parametrize("name, expected_structure", NEWS_STRUCTURE_CONTRACTS.items())
def test_news_prioritizes_major_events_and_one_asset_impact(name, expected_structure):
    paragraph = _load_config()["placeholders"][name]

    assert paragraph.get("writing_structure") == expected_structure


@pytest.mark.parametrize("name", ["美国新闻", "欧洲新闻"])
def test_news_prompt_only_uses_completed_report_period_events(name):
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    prompt = _prompt_blocks(prompt_source)[name]

    assert "只写报告期内已经发生并有结果的事件，未来安排不得作为快讯主体" in prompt


@pytest.mark.parametrize("name, expected_groups", SUBJECT_GROUP_CONTRACTS.items())
def test_selected_sections_require_one_subject_hit_from_every_exact_group(
    name,
    expected_groups,
):
    retrieval = _load_config()["placeholders"][name]["retrieval"]
    expected_subjects = next(
        contract.values[1]
        for contract in PARAGRAPH_CONTRACTS
        if contract.values[0] == name
    )

    assert retrieval.get("subject_match_mode") == "all_groups"
    assert set(expected_subjects) == set(retrieval.get("subject_keywords", []))
    assert [set(group) for group in retrieval.get("subject_keyword_groups", [])] == [
        set(group) for group in expected_groups
    ]


def test_finance_fallback_requires_an_exact_domestic_market_context():
    retrieval = _load_config()["placeholders"]["金融地产"]["retrieval"]

    _assert_exact_terms(
        retrieval.get("fallback_required_keywords", []),
        FINANCE_FALLBACK_REQUIRED_KEYWORDS,
        context="金融地产.retrieval.fallback_required_keywords",
    )


@pytest.mark.parametrize("name, expected_labels", NEWS_SYNTHETIC_TITLE_LABELS.items())
def test_news_config_declares_exact_synthetic_title_labels(name, expected_labels):
    retrieval = _load_config()["placeholders"][name]["retrieval"]

    _assert_exact_terms(
        retrieval.get("synthetic_title_labels", []),
        expected_labels,
        context=f"{name}.retrieval.synthetic_title_labels",
    )


@pytest.mark.parametrize("name", ["美国新闻", "欧洲新闻"])
def test_news_first_subject_group_is_scoped_to_title_or_lead(name):
    retrieval = _load_config()["placeholders"][name]["retrieval"]

    assert retrieval.get("first_group_scope") == NEWS_FIRST_GROUP_SCOPE


def test_medical_first_subject_group_is_scoped_to_title_only():
    retrieval = _load_config()["placeholders"]["医药生物"]["retrieval"]

    assert retrieval.get("first_group_scope") == MEDICAL_FIRST_GROUP_SCOPE


@pytest.mark.parametrize(
    "name, region, event",
    [("美国新闻", "美国", "非农"), ("欧洲新闻", "欧洲", "央行决议")],
)
def test_news_first_group_only_matches_title_or_first_two_hundred_content_chars(
    name,
    region,
    event,
):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    groups = SUBJECT_GROUP_CONTRACTS[name]
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": groups[0],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": groups,
                "first_group_scope": NEWS_FIRST_GROUP_SCOPE,
            }
        },
        default_top_k=10,
    )
    assert getattr(retrieval_config, "first_group_scope", None) == NEWS_FIRST_GROUP_SCOPE
    long_lead = "本周日历记录市场数据。" * 20
    evidence = [
        EvidenceSnippet(
            source="test",
            title=f"A股日历：{event}",
            content=f"{long_lead}{region}数据出现在后文。",
        ),
        EvidenceSnippet(
            source="test",
            title=f"{region}日历：{event}",
            content="正文仅列出已经公布的数值。",
        ),
        EvidenceSnippet(
            source="test",
            title=f"全球日历：{event}",
            content=f"{region}数据位于正文开头并已有结果。",
        ),
    ]
    ranked = filter_and_rank_evidence(evidence, retrieval_config, query=name)

    assert {item.title for item in ranked} == {
        f"{region}日历：{event}",
        f"全球日历：{event}",
    }


def test_medical_subject_must_appear_in_title_or_lead_not_only_late_content():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    groups = SUBJECT_GROUP_CONTRACTS["医药生物"]
    original_subjects = next(
        contract.values[1]
        for contract in PARAGRAPH_CONTRACTS
        if contract.values[0] == "医药生物"
    )
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": original_subjects,
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": groups,
                "first_group_scope": MEDICAL_FIRST_GROUP_SCOPE,
            }
        },
        default_top_k=10,
    )
    long_lead = "海外公司经营信息与一般行业动态。" * 20
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title="基金月报",
                content=f"创新药临床进展位于导语。{long_lead}",
            ),
            EvidenceSnippet(
                source="test",
                title="证券经纪业务动态",
                content=f"医药与新药临床信息位于导语。{long_lead}",
            ),
            EvidenceSnippet(
                source="test",
                title="CPU紧缺情况跟踪",
                content=f"生物医药与药物审批偶然出现在导语。{long_lead}",
            ),
            EvidenceSnippet(
                source="test",
                title="海西新药取得进展",
                content="临床试验已公布阶段性结果。",
            ),
        ],
        retrieval_config,
        query="医药生物",
    )

    assert [item.title for item in ranked] == ["海西新药取得进展"]


@pytest.mark.parametrize(
    "scope, content",
    [
        ("title", "行业背景说明结束后，末尾偶然提及新药临床进展。"),
        (
            "title_or_lead",
            "一般行业背景与市场信息。" * 25 + "正文末尾偶然提及新药临床进展。",
        ),
    ],
)
def test_all_groups_fallback_rejects_subject_hits_outside_first_group_scope(
    scope,
    content,
):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["医药", "新药"],
                "keywords": ["临床"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["医药", "新药"], ["审批"]],
                "first_group_scope": scope,
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title="基金月报",
                content=content,
            )
        ],
        retrieval_config,
        query="医药生物",
    )

    assert ranked == []


@pytest.mark.parametrize(
    "scope, title, content",
    [
        ("title", "海西新药经营动态", "临床结果已经公布。"),
        ("title_or_lead", "基金月报", "医药临床结果位于正文导语。"),
    ],
)
def test_all_groups_fallback_accepts_subject_and_driver_inside_first_group_scope(
    scope,
    title,
    content,
):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["医药", "新药"],
                "keywords": ["临床"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["医药", "新药"], ["审批"]],
                "first_group_scope": scope,
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [EvidenceSnippet(source="test", title=title, content=content)],
        retrieval_config,
        query="医药生物",
    )

    assert [item.title for item in ranked] == [title]


@pytest.mark.parametrize(
    "scope, title, content",
    [
        ("title", "海西新药经营动态", "审批结果已经公布。"),
        ("title_or_lead", "基金月报", "医药信息位于导语，后续审批结果已经公布。"),
    ],
)
def test_all_groups_strict_accepts_complete_groups_with_first_group_in_scope(
    scope,
    title,
    content,
):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["医药", "新药"],
                "keywords": ["临床"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["医药", "新药"], ["审批"]],
                "first_group_scope": scope,
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [EvidenceSnippet(source="test", title=title, content=content)],
        retrieval_config,
        query="医药生物",
    )

    assert [item.title for item in ranked] == [title]


def test_retrieval_config_defaults_synthetic_title_labels_to_empty():
    from reporting.projects.generation import build_retrieval_config

    retrieval_config = build_retrieval_config({"retrieval": {}}, default_top_k=10)

    assert getattr(retrieval_config, "synthetic_title_labels", None) == []


@pytest.mark.parametrize("name, expected_labels", NEWS_SYNTHETIC_TITLE_LABELS.items())
def test_retrieval_config_preserves_explicit_synthetic_title_labels(
    name,
    expected_labels,
):
    from reporting.projects.generation import build_retrieval_config

    retrieval_config = build_retrieval_config(
        {"retrieval": {"synthetic_title_labels": expected_labels}},
        default_top_k=10,
    )

    assert getattr(retrieval_config, "synthetic_title_labels", None) == expected_labels


@pytest.mark.parametrize("name, expected_groups", SUBJECT_GROUP_CONTRACTS.items())
def test_retrieval_filter_requires_at_least_one_hit_from_each_subject_group(
    name,
    expected_groups,
):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": expected_groups,
            }
        },
        default_top_k=10,
    )
    assert getattr(retrieval_config, "subject_match_mode", None) == "all_groups"
    assert getattr(retrieval_config, "subject_keyword_groups", None) == expected_groups

    all_groups_text = " ".join(group[0] for group in expected_groups)
    only_first_group_text = expected_groups[0][0]
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title=f"{name}完整联合命中",
                content=all_groups_text,
            ),
            EvidenceSnippet(
                source="test",
                title=f"{name}仅命中第一组",
                content=only_first_group_text,
            ),
        ],
        retrieval_config,
        query=name,
    )

    assert [item.title for item in ranked] == [f"{name}完整联合命中"]


@pytest.mark.parametrize(
    "name, title, content",
    [
        ("美国新闻", "美国非农报告公布", "新增就业人数为20万人，前值为15万人。"),
        ("欧洲新闻", "欧洲：央行决议公布", "基准利率调整25个基点，前值保持不变。"),
    ],
)
def test_strict_groups_match_across_title_and_numeric_content(name, title, content):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    expected_groups = SUBJECT_GROUP_CONTRACTS[name]
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": expected_groups[0],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": expected_groups,
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [EvidenceSnippet(source="test", title=title, content=content)],
        retrieval_config,
        query=name,
    )

    assert [item.title for item in ranked] == [title]


def test_real_news_title_keeps_meaningful_suffix_when_query_is_a_title_prefix():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    expected_groups = SUBJECT_GROUP_CONTRACTS["美国新闻"]
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": expected_groups[0],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": expected_groups,
            }
        },
        default_top_k=10,
    )
    evidence = [
        EvidenceSnippet(
            source="test",
            title="美国新闻：非农报告公布",
            content="新增就业人数为20万人，前值为15万人。",
        ),
        EvidenceSnippet(
            source="test",
            title="美国新闻",
            content="新增就业人数为20万人，前值为15万人。",
        ),
    ]
    ranked = filter_and_rank_evidence(
        evidence,
        retrieval_config,
        query="美国新闻",
    )

    assert [item.title for item in ranked] == ["美国新闻：非农报告公布"]


def _build_news_retrieval_config(name):
    from reporting.projects.generation import build_retrieval_config

    expected_groups = SUBJECT_GROUP_CONTRACTS[name]
    return build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": expected_groups[0],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": expected_groups,
                "synthetic_title_labels": NEWS_SYNTHETIC_TITLE_LABELS[name],
            }
        },
        default_top_k=10,
    )


@pytest.mark.parametrize(
    "name, content",
    [
        ("美国新闻", "非农新增就业20万人，前值为15万人。"),
        ("欧洲新闻", "通胀率为2.1%，前值为2.3%。"),
    ],
)
def test_synthetic_news_label_cannot_supply_the_regional_subject_group(name, content):
    from reporting.projects.generation import EvidenceSnippet, filter_and_rank_evidence

    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title=NEWS_SYNTHETIC_TITLE_LABELS[name][0],
                content=content,
            )
        ],
        _build_news_retrieval_config(name),
        query=REAL_NEWS_QUERIES[name],
    )

    assert ranked == []


@pytest.mark.parametrize(
    "name, meaningful_suffix, event_only_suffix, content",
    [
        ("美国新闻", "美国非农报告公布", "非农报告公布", "新增就业人数为20万人。"),
        ("欧洲新闻", "欧洲发布央行决议", "央行决议公布", "基准利率调整25个基点。"),
    ],
)
def test_real_query_prefix_is_removed_without_discarding_meaningful_title_suffix(
    name,
    meaningful_suffix,
    event_only_suffix,
    content,
):
    from reporting.projects.generation import EvidenceSnippet, filter_and_rank_evidence

    query = REAL_NEWS_QUERIES[name]
    valid_title = f"{query}｜{meaningful_suffix}"
    evidence = [
        EvidenceSnippet(
            source="test",
            title=valid_title,
            content=content,
        ),
        EvidenceSnippet(
            source="test",
            title=f"{query}｜{event_only_suffix}",
            content=content,
        ),
        EvidenceSnippet(
            source="test",
            title=query,
            content=content,
        ),
    ]
    ranked = filter_and_rank_evidence(
        evidence,
        _build_news_retrieval_config(name),
        query=query,
    )

    assert [item.title for item in ranked] == [valid_title]


@pytest.mark.parametrize(
    "name, event_only_suffix, valid_title",
    [
        ("美国新闻", "非农报告公布", "美国银行经营动态"),
        ("欧洲新闻", "央行决议公布", "欧洲银行经营动态"),
    ],
)
def test_news_fallback_uses_the_same_cleaned_text_as_strict_matching(
    name,
    event_only_suffix,
    valid_title,
):
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    expected_groups = SUBJECT_GROUP_CONTRACTS[name]
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": expected_groups[0],
                "keywords": ["市场", "政策"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": expected_groups,
                "synthetic_title_labels": NEWS_SYNTHETIC_TITLE_LABELS[name],
            }
        },
        default_top_k=10,
    )
    query = REAL_NEWS_QUERIES[name]
    evidence = [
        EvidenceSnippet(
            source="test",
            title=NEWS_SYNTHETIC_TITLE_LABELS[name][0],
            content="市场政策发生变化。",
        ),
        EvidenceSnippet(
            source="test",
            title=f"{query}｜{event_only_suffix}",
            content="市场政策发生变化。",
        ),
        EvidenceSnippet(
            source="test",
            title=valid_title,
            content="市场政策发生变化。",
        ),
    ]
    ranked = filter_and_rank_evidence(
        evidence,
        retrieval_config,
        query=query,
    )

    assert [item.title for item in ranked] == [valid_title]


def test_strict_group_matching_keeps_non_overlapping_span_requirement():
    from reporting.projects.generation import _contains_all_keyword_groups

    duplicated_groups = [["美国"], ["美国"]]

    assert not _contains_all_keyword_groups("美国", duplicated_groups)
    assert _contains_all_keyword_groups("美国 美国", duplicated_groups)


@pytest.mark.parametrize(
    "name, sentences",
    CROSS_SENTENCE_SUBJECT_CASES.items(),
)
def test_compaction_preserves_subject_group_hits_across_sentences(name, sentences):
    from reporting.projects.generation import (
        DatabaseEvidenceRetriever,
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    expected_groups = SUBJECT_GROUP_CONTRACTS[name]
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": expected_groups[0],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": expected_groups,
            }
        },
        default_top_k=10,
    )
    original = "\n".join(sentences)
    compacted = DatabaseEvidenceRetriever._compact_text(
        original,
        retrieval_config=retrieval_config,
    )

    assert all(sentence in compacted for sentence in sentences)
    ranked = filter_and_rank_evidence(
        [EvidenceSnippet(source="test", title=name, content=compacted)],
        retrieval_config,
        query=name,
    )
    assert [item.title for item in ranked] == [name]


def _fallback_retrieval_config():
    from reporting.projects.generation import build_retrieval_config

    return build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": ["人工智能"],
                "keywords": ["资本开支"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["人工智能"], ["大模型"]],
            }
        },
        default_top_k=10,
    )


def _fallback_evidence():
    from reporting.projects.generation import EvidenceSnippet

    return [
        EvidenceSnippet(
            source="test",
            title="subject-and-driver",
            content="人工智能企业增加资本开支。",
        ),
        EvidenceSnippet(
            source="test",
            title="subject-only",
            content="人工智能行业出现新变化。",
        ),
        EvidenceSnippet(
            source="test",
            title="driver-only",
            content="企业资本开支出现新变化。",
        ),
    ]


def test_all_groups_fallback_requires_both_subject_and_driver_when_strict_is_empty():
    from reporting.projects.generation import filter_and_rank_evidence

    ranked = filter_and_rank_evidence(
        _fallback_evidence(),
        _fallback_retrieval_config(),
        query="人工智能",
    )

    assert [item.title for item in ranked] == ["subject-and-driver"]


def test_all_groups_does_not_mix_fallback_candidates_when_strict_has_results():
    from reporting.projects.generation import EvidenceSnippet, filter_and_rank_evidence

    evidence = _fallback_evidence()
    evidence.insert(
        0,
        EvidenceSnippet(
            source="test",
            title="strict-all-groups",
            content="人工智能大模型取得新进展。",
        ),
    )
    ranked = filter_and_rank_evidence(
        evidence,
        _fallback_retrieval_config(),
        query="人工智能",
    )

    assert [item.title for item in ranked] == ["strict-all-groups"]


def test_zero_strict_matches_log_fallback_mode_and_counts(monkeypatch):
    import reporting.projects.generation as generation

    recording_logger = _RecordingLogger()
    monkeypatch.setattr(generation, "logger", recording_logger)

    generation.filter_and_rank_evidence(
        _fallback_evidence(),
        _fallback_retrieval_config(),
        query="人工智能",
    )

    fallback_records = [
        record for record in recording_logger.records if "fallback" in record[1].lower()
    ]
    assert len(fallback_records) == 1
    level, _event, fields = fallback_records[0]
    assert level in {"warning", "info"}
    assert fields == {
        "mode": "all_groups",
        "strict_count": 0,
        "fallback_count": 1,
    }


def test_invalid_explicit_all_groups_falls_back_to_subject_and_driver(monkeypatch):
    import reporting.projects.generation as generation

    recording_logger = _RecordingLogger()
    monkeypatch.setattr(generation, "logger", recording_logger)
    retrieval_config = generation.build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": ["人工智能"],
                "keywords": ["资本开支"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["人工智能"], []],
            }
        },
        default_top_k=10,
    )
    ranked = generation.filter_and_rank_evidence(
        _fallback_evidence(),
        retrieval_config,
        query="人工智能",
    )
    invalid_records = [
        record for record in recording_logger.records if "invalid" in record[1].lower()
    ]
    violations = []
    actual_titles = [item.title for item in ranked]
    if actual_titles != ["subject-and-driver"]:
        violations.append(f"兼容回退结果错误: {actual_titles}")
    if len(invalid_records) != 1:
        violations.append(f"invalid warning 数量应为1，实际为{len(invalid_records)}")
    else:
        level, _event, fields = invalid_records[0]
        if level != "warning":
            violations.append(f"invalid 配置日志级别应为 warning，实际为 {level}")
        if fields.get("mode") != "all_groups":
            violations.append(f"invalid 日志模式错误: {fields}")
        if fields.get("fallback_count") != 1:
            violations.append(f"invalid 日志回退计数错误: {fields}")

    assert not violations, "; ".join(violations)


def test_fallback_required_keywords_reject_foreign_and_allow_domestic_finance():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": ["银行", "房企"],
                "keywords": ["息差", "融资"],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": [["银行", "房企"], ["严格边界词"]],
                "fallback_required_keywords": FINANCE_FALLBACK_REQUIRED_KEYWORDS,
            }
        },
        default_top_k=10,
    )
    assert getattr(retrieval_config, "fallback_required_keywords", None) == (
        FINANCE_FALLBACK_REQUIRED_KEYWORDS
    )
    evidence = [
        EvidenceSnippet(
            source="test",
            title="美国银行息差承压",
            content="海外银行盈利能力发生变化。",
        ),
        EvidenceSnippet(
            source="test",
            title="欧洲房企融资变化",
            content="海外房地产企业调整融资计划。",
        ),
        EvidenceSnippet(
            source="test",
            title="中国银行息差改善",
            content="国内银行经营指标出现变化。",
        ),
        EvidenceSnippet(
            source="test",
            title="沪深银行息差变化",
            content="上市银行披露最新经营数据。",
        ),
    ]
    ranked = filter_and_rank_evidence(
        evidence,
        retrieval_config,
        query="金融地产",
    )

    assert {item.title for item in ranked} == {"中国银行息差改善", "沪深银行息差变化"}


def test_finance_strict_matching_requires_subject_domestic_context_and_driver():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    groups = SUBJECT_GROUP_CONTRACTS["金融地产"]
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": groups[0],
                "subject_match_mode": "all_groups",
                "subject_keyword_groups": groups,
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title="中国银行息差改善",
                content="银行经营指标出现变化。",
            ),
            EvidenceSnippet(
                source="test",
                title="中国银行经营动态",
                content="银行经营指标出现变化。",
            ),
        ],
        retrieval_config,
        query="金融地产",
    )

    assert [item.title for item in ranked] == ["中国银行息差改善"]


def test_legacy_subject_matching_remains_any_without_explicit_mode():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "mode": "keyword",
                "subject_keywords": ["人工智能"],
                "keywords": ["资本开支"],
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title="legacy-subject-only",
                content="人工智能行业出现新变化。",
            )
        ],
        retrieval_config,
        query="人工智能",
    )

    assert [item.title for item in ranked] == ["legacy-subject-only"]


def test_a_share_review_scopes_only_its_llm_writing_component():
    config = _load_config()
    review = config["placeholders"]["A股市场回顾"]
    llm_components = [
        component
        for component in review.get("components", [])
        if component.get("type") == "llm_writing"
    ]
    assert len(llm_components) == 1
    retrieval = llm_components[0].get("retrieval", {})

    _assert_exact_terms(
        retrieval.get("subject_keywords", []),
        ["A股", "沪深股市", "中国股市"],
        context="A股市场回顾.llm_writing.retrieval.subject_keywords",
    )
    _assert_exact_terms(
        retrieval.get("keywords", []),
        ["板块轮动", "市场热点", "资金", "政策", "景气度", "风险偏好"],
        context="A股市场回顾.llm_writing.retrieval.keywords",
    )
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    prompt = _prompt_blocks(prompt_source)["A股市场回顾"]
    assert "不重复前文指数和成交额数字" in prompt


def test_deterministic_placeholders_keep_their_existing_modes():
    placeholders = _load_config()["placeholders"]

    assert placeholders["开始日期"]["type"] == "field"
    assert placeholders["结束日期"]["type"] == "field"
    assert placeholders["黄金市场回顾"]["type"] == "excel_commodity_market_review"
    assert placeholders["原油市场回顾"]["type"] == "excel_commodity_market_review"
    assert placeholders["A股市场回顾"]["mode"] == "data_template_plus_evidence_ai"


def test_shared_generation_constraints_exclude_all_reviewed_section_only_terms():
    constraints = "\n".join(_load_config()["defaults"]["generation_constraints"])
    expected_by_section = {
        contract.values[0]: set(contract.values[1] + contract.values[2])
        for contract in PARAGRAPH_CONTRACTS
    }

    assert set(SECTION_ONLY_TERMS) == set(expected_by_section)
    for name, terms in SECTION_ONLY_TERMS.items():
        assert terms <= expected_by_section[name], f"{name} 的专属词必须来自该段合同"
        leaked = sorted(term for term in terms if term in constraints)
        assert not leaked, f"defaults.generation_constraints 泄漏 {name} 专属词: {leaked}"


def test_report_defaults_use_local_model_directories_and_period_only_constraints():
    defaults = _load_config()["defaults"]

    embedding_model = defaults["retrieval"]["embedding_model"]
    rerank_model = defaults["rerank"]["model"]
    assert embedding_model == "data/models/embeddings/bge-large-zh-v1.5"
    assert rerank_model == "data/models/rerankers/bge-reranker-large"
    assert (ROOT / embedding_model).is_dir()
    assert (ROOT / rerank_model).is_dir()

    constraints = defaults["generation_constraints"]
    assert "核心分析仅使用报告期内已发生的事实，未来安排只可作为后续关注变量" in constraints
    assert "正文不使用括号补充说明" in constraints
    assert defaults["validators"].get("forbid_parentheses") is True


@pytest.mark.parametrize("reverse_candidates", [False, True])
def test_relevance_scan_selects_older_matches_before_ranking_without_source_rules(
    reverse_candidates,
):
    """有界扫描应在相关性筛选前覆盖候选，且不按来源配额或白名单取材。"""
    from reporting.projects.generation import (
        EvidenceSnippet,
        RetrievalConfig,
        select_relevance_scan_candidates,
    )

    newer_generic = [
        EvidenceSnippet(
            source="ingestion:generic_feed",
            title=f"市场快讯 {index}",
            content="本周市场交投活跃，风险偏好出现波动。",
            published_at="2026-07-12",
        )
        for index in range(40)
    ]
    older_matched = [
        EvidenceSnippet(
            source="ingestion:zhiqiu_transcript",
            title="创新药临床进展",
            content="医药生物行业的创新药临床试验取得阶段性进展。",
            published_at="2026-07-01",
        ),
        EvidenceSnippet(
            source="ingestion:cnstock_flash",
            title="医疗器械审批动态",
            content="医药生物领域医疗器械审批流程迎来新进展。",
            published_at="2026-06-30",
        ),
    ]
    candidates = [*newer_generic, *older_matched]
    if reverse_candidates:
        candidates.reverse()
    retrieval_config = RetrievalConfig(
        top_k=10,
        must_any=["医药生物", "创新药", "医疗器械"],
        min_keyword_score=1.0,
    )

    selected = select_relevance_scan_candidates(
        candidates,
        retrieval_config,
        query="医药生物",
        relevance_scan_limit=400,
    )

    assert retrieval_config.source_types == []
    assert {snippet.title for snippet in selected} == {
        "创新药临床进展",
        "医疗器械审批动态",
    }
    assert {snippet.source for snippet in selected} == {
        "ingestion:zhiqiu_transcript",
        "ingestion:cnstock_flash",
    }
    assert not {snippet.title for snippet in selected} & {
        snippet.title for snippet in newer_generic
    }


def test_candidate_source_distribution_is_observability_only_and_preserves_ranking():
    """来源统计只供日志观测；同相关度候选不得因来源变化而改变既有排序。"""
    from reporting.projects.generation import (
        EvidenceSnippet,
        RetrievalConfig,
        filter_and_rank_evidence,
        summarize_evidence_sources,
    )

    candidates = [
        EvidenceSnippet(
            source="ingestion:zhiqiu_transcript",
            title="医药候选甲",
            content="医药生物临床进展。",
            published_at="2026-07-10",
        ),
        EvidenceSnippet(
            source="ingestion:cnstock_flash",
            title="医药候选乙",
            content="医药生物临床进展。",
            published_at="2026-07-10",
        ),
    ]
    source_only_changed = [
        EvidenceSnippet(
            source="ingestion:any_source",
            title=snippet.title,
            content=snippet.content,
            published_at=snippet.published_at,
        )
        for snippet in candidates
    ]
    retrieval_config = RetrievalConfig(
        top_k=10,
        must_any=["医药生物"],
        min_keyword_score=1.0,
    )

    baseline = filter_and_rank_evidence(
        candidates,
        retrieval_config,
        query="医药生物",
    )
    source_changed = filter_and_rank_evidence(
        source_only_changed,
        retrieval_config,
        query="医药生物",
    )

    assert summarize_evidence_sources(candidates) == {
        "ingestion:zhiqiu_transcript": 1,
        "ingestion:cnstock_flash": 1,
    }
    assert [snippet.title for snippet in source_changed] == [
        snippet.title for snippet in baseline
    ]
    assert [snippet.retrieval_rank for snippet in source_changed] == [
        snippet.retrieval_rank for snippet in baseline
    ]


def test_hong_kong_tech_enables_controlled_driver_backfill():
    retrieval = _load_config()["placeholders"]["港股科技"]["retrieval"]

    assert retrieval.get("subject_backfill_enabled") is True
    assert retrieval.get("min_backfill_keyword_matches") == 2
    assert retrieval.get("backfill_required_keywords") == (
        HONG_KONG_TECH_BACKFILL_REQUIRED_KEYWORDS
    )


def test_subject_backfill_fills_to_top_k_with_two_driver_hits_after_strict_results():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "top_k": 3,
                "subject_keywords": ["港股科技"],
                "keywords": ["南向资金", "估值", "业绩"],
                "subject_backfill_enabled": True,
                "min_backfill_keyword_matches": 2,
            }
        },
        default_top_k=10,
    )
    assert getattr(retrieval_config, "subject_backfill_enabled", None) is True
    assert getattr(retrieval_config, "min_backfill_keyword_matches", None) == 2
    strict = EvidenceSnippet(
        source="test",
        title="港股科技主线",
        content="港股科技获得南向资金关注。",
    )
    evidence = [
        strict,
        strict,
        EvidenceSnippet(
            source="test",
            title="平台公司估值与业绩",
            content="平台公司估值修复且业绩改善。",
        ),
        EvidenceSnippet(
            source="test",
            title="互联网公司资金与业绩",
            content="南向资金流入，企业业绩改善。",
        ),
        EvidenceSnippet(
            source="test",
            title="仅一项驱动",
            content="企业业绩改善。",
        ),
    ]
    ranked = filter_and_rank_evidence(evidence, retrieval_config, query="港股科技")
    titles = [item.title for item in ranked]

    assert titles[0] == "港股科技主线"
    assert len(titles) == 3
    assert set(titles) == {"港股科技主线", "平台公司估值与业绩", "互联网公司资金与业绩"}
    assert titles.count("港股科技主线") == 1


def test_subject_backfill_stays_disabled_for_gold():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["黄金"],
                "keywords": ["美债收益率", "美元指数"],
            }
        },
        default_top_k=10,
    )
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(source="test", title="黄金走势", content="黄金震荡。"),
            EvidenceSnippet(
                source="test",
                title="美元利率变化",
                content="美债收益率回落，美元指数走弱。",
            ),
        ],
        retrieval_config,
        query="黄金",
    )

    assert [item.title for item in ranked] == ["黄金走势"]


def test_hong_kong_tech_backfill_requires_hong_kong_market_context():
    from reporting.projects.generation import (
        EvidenceSnippet,
        build_retrieval_config,
        filter_and_rank_evidence,
    )

    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "top_k": 3,
                "subject_keywords": ["港股科技"],
                "keywords": ["南向资金", "估值", "业绩"],
                "subject_backfill_enabled": True,
                "min_backfill_keyword_matches": 2,
                "backfill_required_keywords": HONG_KONG_TECH_BACKFILL_REQUIRED_KEYWORDS,
            }
        },
        default_top_k=10,
    )
    assert getattr(retrieval_config, "backfill_required_keywords", None) == (
        HONG_KONG_TECH_BACKFILL_REQUIRED_KEYWORDS
    )
    ranked = filter_and_rank_evidence(
        [
            EvidenceSnippet(
                source="test",
                title="港股科技主线",
                content="港股科技获得南向资金关注。",
            ),
            EvidenceSnippet(
                source="test",
                title="A股科创板估值与业绩",
                content="科创板估值修复且业绩改善。",
            ),
            EvidenceSnippet(
                source="test",
                title="创业板资金与业绩",
                content="创业板资金流入且业绩改善。",
            ),
            EvidenceSnippet(
                source="test",
                title="香港平台公司估值与业绩",
                content="香港平台公司估值修复且业绩改善。",
            ),
            EvidenceSnippet(
                source="test",
                title="中概互联网资金与业绩",
                content="中概互联网获南向资金流入且业绩改善。",
            ),
        ],
        retrieval_config,
        query="港股科技",
    )
    titles = [item.title for item in ranked]

    assert titles[0] == "港股科技主线"
    assert set(titles) == {
        "港股科技主线",
        "香港平台公司估值与业绩",
        "中概互联网资金与业绩",
    }
