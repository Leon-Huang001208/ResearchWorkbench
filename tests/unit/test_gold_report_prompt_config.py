from pathlib import Path

import yaml

from reporting.projects.generation import (
    DatabaseEvidenceRetriever,
    EvidenceSnippet,
    build_retrieval_config,
    filter_and_rank_evidence,
)


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
    assert "黄金" in gold["retrieval"]["subject_keywords"]
    assert "不得重复前文价格数字" in gold_prompt
    assert "不写任何黄金价格、点位或涨跌幅数字" in gold_prompt
    assert "不得输出来源括号" in gold_prompt
    assert "直接解释本周国际金价" in gold_prompt


def test_subject_keywords_exclude_driver_news_that_does_not_discuss_gold():
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["黄金", "金价", "伦敦金"],
                "keywords": ["美联储", "美元指数", "美债收益率"],
            }
        },
        default_top_k=10,
    )
    evidence = [
        EvidenceSnippet(
            source="test",
            title="美联储发布货币政策报告",
            content="美股科技股上涨，美元指数有所波动。",
        ),
        EvidenceSnippet(
            source="test",
            title="国际金价本周承压",
            content="美债收益率上行削弱黄金配置吸引力。",
        ),
        EvidenceSnippet(
            source="test",
            title="全球央行继续增持黄金",
            content="黄金储备需求保持稳定。",
        ),
    ]

    ranked = filter_and_rank_evidence(
        evidence,
        retrieval_config,
        query="本周国际金价驱动因素",
    )

    assert [item.title for item in ranked] == [
        "国际金价本周承压",
        "全球央行继续增持黄金",
    ]


def test_subject_focused_excerpt_removes_unrelated_document_sections():
    retrieval_config = build_retrieval_config(
        {
            "retrieval": {
                "subject_keywords": ["黄金", "金价"],
                "keywords": ["黄金", "金价", "美债收益率", "美元指数"],
            }
        },
        default_top_k=10,
    )
    document = (
        "美股芯片板块大幅上涨，人工智能公司发布新品。\n"
        "国际金价本周承压，美债收益率上行削弱黄金配置吸引力。\n"
        "游戏行业进入暑期新品发布周期。"
    )

    excerpt = DatabaseEvidenceRetriever._compact_text(
        document,
        retrieval_config=retrieval_config,
    )

    assert excerpt == "国际金价本周承压，美债收益率上行削弱黄金配置吸引力。"
